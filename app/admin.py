import hashlib
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import (APIRouter, BackgroundTasks, Depends, File, Form,
                     HTTPException, UploadFile)
from pydantic import BaseModel, Field

from app.ingest import process_upload, read_pages
from app.integrations import notify
from app.models import (AgentRun, Approval, AuditLog, Document, DocumentACL,
                        Notification, Role, User)

BASE = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE / "data" / "uploads"
MAX_MB = 10
ALLOWED_TYPES = {".pdf", ".docx", ".txt", ".csv"}
DEPARTMENTS = ["HR", "IT", "Finance", "Legal", "Security", "Operations"]
SENSITIVITY = ["Public", "Internal", "Confidential", "Restricted"]
DEPT_ROLE = {"HR": "hr", "IT": "it", "Finance": "finance",
             "Legal": "legal", "Security": "it", "Operations": "it"}
# which current statuses allow which request
ALLOWED_FROM = {"archive": ("active", "superseded"),
                "revoke": ("active", "superseded", "archived")}


class RequestData(BaseModel):
    action: Literal["archive", "revoke"]
    reason: str = Field(min_length=3, max_length=300)


class DecideData(BaseModel):
    decision: Literal["approve", "reject"]
    comment: str = Field(default="", max_length=300)


def audit(db, actor, action, target="", result=""):
    db.add(AuditLog(actor=actor, action=action, target=target[:200],
                    result=result[:500]))
    db.commit()


def admin_only(user):
    if user.role.name != "admin":
        raise HTTPException(status_code=403, detail="Admin only")


def grant_access(db, doc):
    """Same access rule as the seed script."""
    roles = {r.name: r.id for r in db.query(Role).all()}
    if doc.sensitivity in ("Public", "Internal"):
        allowed = set(roles)
    else:
        allowed = {DEPT_ROLE.get(doc.department, "admin"), "admin"}
    for name in allowed:
        db.add(DocumentACL(document_id=doc.id, role_id=roles[name]))


def build_router(current_user, get_db):
    router = APIRouter()

    @router.post("/admin/upload")
    async def upload(background: BackgroundTasks,
                     file: UploadFile = File(...),
                     department: str = Form(...),
                     owner: str = Form(...),
                     effective_date: date = Form(...),
                     sensitivity: str = Form(...),
                     title: str = Form(""),
                     new_version_of: int | None = Form(None),
                     user=Depends(current_user), db=Depends(get_db)):
        admin_only(user)

        name = file.filename or ""
        ext = Path(name).suffix.lower()
        if ext not in ALLOWED_TYPES:
            raise HTTPException(400, "Only PDF, DOCX, TXT and CSV files are allowed")
        if department not in DEPARTMENTS:
            raise HTTPException(400, "Unknown department")
        if sensitivity not in SENSITIVITY:
            raise HTTPException(400, "Unknown sensitivity level")
        if not owner.strip():
            raise HTTPException(400, "Please enter the owner")

        content = await file.read()
        if not content.strip():
            raise HTTPException(400, "The file is empty")
        if len(content) > MAX_MB * 1024 * 1024:
            raise HTTPException(413, f"The file is larger than {MAX_MB} MB")

        digest = hashlib.sha256(content).hexdigest()
        same = db.query(Document).filter(Document.file_hash == digest).first()
        if same:
            audit(db, user.username, "upload", name, f"rejected: duplicate of document {same.id}")
            raise HTTPException(
                409, f"Duplicate: this file is already stored as '{same.title}' "
                     f"(document {same.id}, v{same.version})")

        old = None
        if new_version_of is not None:
            old = db.get(Document, new_version_of)
            if not old or old.status != "active":
                raise HTTPException(400, "The document to replace must exist and be active")
            doc_title, doc_dept, version = old.title, old.department, old.version + 1
        else:
            if not title.strip():
                raise HTTPException(400, "Please enter a title")
            doc_title, doc_dept, version = title.strip(), department, 1

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
        path = UPLOAD_DIR / f"{uuid.uuid4().hex[:8]}_{safe}"
        path.write_bytes(content)

        doc = Document(filename=name, title=doc_title, department=doc_dept,
                       version=version, status="draft", sensitivity=sensitivity,
                       owner=owner.strip(), effective_date=effective_date,
                       file_format=ext[1:], pages=1, file_hash=digest,
                       file_path=str(path), ingestion_status="queued")
        db.add(doc)
        db.flush()
        grant_access(db, doc)
        db.add(AuditLog(actor=user.username, action="upload",
                        target=f"document {doc.id}: {doc_title} v{version}",
                        result="accepted, processing in background"))
        db.commit()

        background.add_task(process_upload, doc.id, old.id if old else None,
                            user.username)
        return {"document_id": doc.id, "version": version,
                "message": f"Upload accepted as '{doc_title}' v{version}. "
                           "Processing in the background - refresh the table to see the status."}

    @router.get("/admin/documents/{doc_id}/preview")
    def preview(doc_id: int, user=Depends(current_user), db=Depends(get_db)):
        admin_only(user)
        doc = db.get(Document, doc_id)
        if not doc:
            raise HTTPException(404, "Document not found")
        try:
            pages = read_pages(doc.file_path)
        except Exception as e:
            raise HTTPException(422, f"Cannot read this file: {str(e)[:150]}")
        first = pages[0][1] if pages else ""
        return {"pages": len(pages), "text": " ".join(first.split())[:1500]}

    @router.post("/admin/documents/{doc_id}/request")
    def request_action(doc_id: int, data: RequestData, background: BackgroundTasks,
                    user=Depends(current_user), db=Depends(get_db)):
        admin_only(user)
        doc = db.get(Document, doc_id)
        if not doc:
            raise HTTPException(404, "Document not found")
        if doc.status not in ALLOWED_FROM[data.action]:
            raise HTTPException(400, f"Cannot {data.action} a document that is {doc.status}")
        waiting = (db.query(Approval)
                     .filter(Approval.document_id == doc.id, Approval.status == "pending")
                     .first())
        if waiting:
            raise HTTPException(409, "This document already has a request waiting for review")
        ap = Approval(action=data.action, document_id=doc.id,
                      requested_by=user.username, reason=data.reason)
        db.add(ap)
        audit(db, user.username, "approval_requested",
              f"document {doc.id}: {data.action}",
              f"pending review. Reason: {data.reason}")
        others = [u.username for u in
                  db.query(User).join(Role, Role.id == User.role_id)
                    .filter(Role.name == "admin", User.username != user.username).all()]
        background.add_task(
            notify, others, f"Approval needed: {data.action} {doc.title}",
            f"{user.username} asks to {data.action} '{doc.title}' v{doc.version}. "
            f"Reason: {data.reason}")
        return {"approval_id": ap.id}

    @router.get("/admin/approvals")
    def list_approvals(user=Depends(current_user), db=Depends(get_db)):
        admin_only(user)
        rows = (db.query(Approval, Document)
                  .join(Document, Document.id == Approval.document_id)
                  .order_by(Approval.id.desc()).all())
        return [{"id": a.id, "action": a.action, "document_id": d.id,
                 "document": d.title, "version": d.version, "doc_status": d.status,
                 "requested_by": a.requested_by, "reason": a.reason,
                 "status": a.status, "reviewed_by": a.reviewed_by,
                 "comment": a.review_comment, "created": str(a.created_at),
                 "decided": str(a.decided_at or "")} for a, d in rows]

    @router.post("/admin/approvals/{approval_id}/decide")
    def decide(approval_id: int, data: DecideData, background: BackgroundTasks,
               user=Depends(current_user), db=Depends(get_db)):
        admin_only(user)
        ap = db.get(Approval, approval_id)
        if not ap:
            raise HTTPException(404, "Request not found")
        if ap.status != "pending":
            raise HTTPException(409, "This request was already decided")
        if ap.requested_by == user.username:
            raise HTTPException(403, "You cannot review your own request. Another admin must do it.")

        doc = db.get(Document, ap.document_id)
        if data.decision == "approve":
            if doc.status not in ALLOWED_FROM[ap.action]:
                raise HTTPException(409, f"The document is now {doc.status}, so this request no longer applies")
            target = "archived" if ap.action == "archive" else "revoked"
            before = doc.status
            doc.status = target
            ap.status = "approved"
            result = f"applied: document {doc.id} changed from {before} to {target}"
        else:
            ap.status = "rejected"
            result = f"rejected: document {doc.id} stays {doc.status}"

        ap.reviewed_by = user.username
        ap.review_comment = data.comment
        ap.decided_at = datetime.now(timezone.utc).replace(tzinfo=None)
        audit(db, user.username, f"approval_{ap.status}",
              f"document {doc.id}: {ap.action}", result)
        background.add_task(
            notify, [ap.requested_by],
            f"Your {ap.action} request was {ap.status}",
            f"{user.username} reviewed your request: {result}")
        return {"status": ap.status, "result": result}

    @router.get("/admin/runs")
    def all_runs(user=Depends(current_user), db=Depends(get_db)):
        admin_only(user)
        rows = db.query(AgentRun).order_by(AgentRun.id.desc()).limit(1000).all()
        return [{"id": r.id, "time": str(r.created_at), "user": r.username,
                 "role": r.role, "question": r.question, "status": r.status,
                 "ms": r.duration_ms, "fallback": r.fallback,
                 "llm_calls": r.llm_calls, "input_tokens": r.input_tokens,
                 "output_tokens": r.output_tokens, "cost_usd": r.cost_usd,
                 "answer": r.answer} for r in rows]
    
    @router.get("/admin/notifications")
    def notifications(user=Depends(current_user), db=Depends(get_db)):
        admin_only(user)
        rows = db.query(Notification).order_by(Notification.id.desc()).limit(50).all()
        return [{"time": str(n.created_at), "to": n.to_username, "email": n.to_email,
                 "subject": n.subject, "status": n.status, "detail": n.detail}
                for n in rows]
    return router