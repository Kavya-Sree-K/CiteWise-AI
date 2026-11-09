import json
import time
import uuid
from typing import Literal

import bcrypt
from fastapi import FastAPI, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from app import conversations
from app.db import SessionLocal, upgrade_schema
from app.models import (User, Document, DocumentACL, AuditLog, AgentRun,
                        Feedback, IngestionJob, Conversation, Message)
from app.graph import ask
from app.graph import ask, prune_checkpoints

upgrade_schema()      # adds the conversations/messages tables and token columns if missing
prune_checkpoints()   # drop saved graph state older than 14 days

app = FastAPI(title="Knowledge Platform")

TOKEN_LIFETIME = 60 * 60      # login lasts 1 hour
MAX_FAILS = 5                 # wrong passwords allowed ...
FAIL_WINDOW = 5 * 60          # ... within 5 minutes
SESSIONS = {}                 # login code -> {"user_id", "expires"}
FAILS = {}                    # username -> list of failure times


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- request and response models (Pydantic) ----------
class LoginData(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class AskData(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    history: list[str] = Field(default_factory=list, max_length=6)   # only used without a conversation_id
    conversation_id: int | None = None


class FeedbackData(BaseModel):
    run_id: int
    rating: Literal[1, -1]
    comment: str = Field(default="", max_length=300)


class LoginOut(BaseModel):
    token: str
    name: str
    role: str


class SourceOut(BaseModel):
    title: str
    version: int
    page: int
    used: bool = True
    snippet: str = ""


class ComparisonRow(BaseModel):
    label: str
    value: str
    source: int


class AskOut(BaseModel):
    status: str
    answer: str
    sources: list[SourceOut]
    steps: list[str]
    details: list[str] = []
    procedure: list[str] = []
    comparison: list[ComparisonRow] = []
    follow_ups: list[str] = []
    run_id: int | None = None
    conversation_id: int | None = None
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class DocumentOut(BaseModel):
    id: int
    title: str
    department: str
    version: int
    sensitivity: str
    format: str
    pages: int


def percentile(values, p):
    if not values:
        return 0
    values = sorted(values)
    k = min(len(values) - 1, int(round(p / 100 * (len(values) - 1))))
    return values[k]


def admin_only(user):
    if user.role.name != "admin":
        raise HTTPException(status_code=403, detail="Admin only")


@app.get("/")
def home():
    return {"message": "Knowledge Platform API is running. Open /docs to test."}


@app.post("/login", response_model=LoginOut)
def login(data: LoginData, db=Depends(get_db)):
    now = time.time()
    recent = [t for t in FAILS.get(data.username, []) if now - t < FAIL_WINDOW]
    FAILS[data.username] = recent
    if len(recent) >= MAX_FAILS:
        raise HTTPException(status_code=429,
                            detail="Too many failed attempts. Try again in a few minutes.")

    user = db.query(User).filter(User.username == data.username).first()
    ok = user and bcrypt.checkpw(data.password.encode(), user.password_hash.encode())
    db.add(AuditLog(actor=data.username, action="login",
                    result="success" if ok else "failed"))
    db.commit()
    if not ok:
        FAILS[data.username].append(now)
        raise HTTPException(status_code=401, detail="Wrong username or password")

    FAILS.pop(data.username, None)
    token = str(uuid.uuid4())
    SESSIONS[token] = {"user_id": user.id, "expires": now + TOKEN_LIFETIME}
    return {"token": token, "name": user.full_name, "role": user.role.name,
            "username": user.username}


def current_user(x_token: str = Header(None), db=Depends(get_db)):
    info = SESSIONS.get(x_token)
    if not info or info["expires"] < time.time():
        SESSIONS.pop(x_token, None)
        raise HTTPException(status_code=401, detail="Session expired, please login again")
    user = db.get(User, info["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="Please login again")
    return user

class ChangePasswordData(BaseModel):
    old_password: str
    new_password: str


@app.post("/change-password")
def change_password(data: ChangePasswordData, user=Depends(current_user), db=Depends(get_db)):
    now = time.time()
    recent = [t for t in FAILS.get(user.username, []) if now - t < FAIL_WINDOW]
    FAILS[user.username] = recent
    if len(recent) >= MAX_FAILS:
        raise HTTPException(status_code=429,
                            detail="Too many failed attempts. Try again in a few minutes.")
    if not bcrypt.checkpw(data.old_password.encode(), user.password_hash.encode()):
        FAILS[user.username].append(now)
        db.add(AuditLog(actor=user.username, action="change_password",
                        result="failed: wrong current password"))
        db.commit()
        raise HTTPException(status_code=400, detail="Your current password is not correct")
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400,
                            detail="The new password must have at least 8 characters")
    if len(data.new_password.encode()) > 72:
        raise HTTPException(status_code=400,
                            detail="The new password can have at most 72 characters")
    if data.new_password == data.old_password:
        raise HTTPException(status_code=400,
                            detail="The new password must be different from the current one")
    user.password_hash = bcrypt.hashpw(data.new_password.encode(), bcrypt.gensalt()).decode()
    db.add(AuditLog(actor=user.username, action="change_password", result="success"))
    db.commit()
    return {"message": "Your password was changed."}


@app.post("/logout")
def logout(x_token: str = Header(None), user=Depends(current_user), db=Depends(get_db)):
    SESSIONS.pop(x_token, None)
    db.add(AuditLog(actor=user.username, action="logout", result="success"))
    db.commit()
    return {"message": "Signed out."}




@app.get("/documents", response_model=list[DocumentOut])
def my_documents(department: str | None = None,
                 user=Depends(current_user), db=Depends(get_db)):
    q = (db.query(Document)
           .join(DocumentACL, DocumentACL.document_id == Document.id)
           .filter(DocumentACL.role_id == user.role_id)
           .filter(Document.status == "active"))
    if department:
        q = q.filter(Document.department == department)
    return [{"id": d.id, "title": d.title, "department": d.department,
             "version": d.version, "sensitivity": d.sensitivity,
             "format": d.file_format, "pages": d.pages}
            for d in q.order_by(Document.title).all()]


@app.post("/ask", response_model=AskOut)
def ask_question(data: AskData, user=Depends(current_user), db=Depends(get_db)):
    question = data.question.strip()
    conv = conversations.get_or_create(db, user, data.conversation_id, question)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    # follow-up context comes from the database, not from the browser
    history = (conversations.recent_questions(db, conv.id) if data.conversation_id
               else [h[:500] for h in data.history])
    out = ask(db, user, question, history, conversation_id=conv.id)
    conversations.add_turn(db, conv, question, out)
    out["conversation_id"] = conv.id
    return out


@app.get("/conversations")
def my_conversations(user=Depends(current_user), db=Depends(get_db)):
    rows = (db.query(Conversation).filter(Conversation.username == user.username)
              .order_by(Conversation.updated_at.desc()).limit(50).all())
    return [{"id": c.id, "title": c.title, "updated": str(c.updated_at)} for c in rows]


def _own_conversation(db, user, conversation_id):
    conv = db.get(Conversation, conversation_id)
    if not conv or conv.username != user.username:      # even admins cannot read other chats
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@app.get("/conversations/{conversation_id}")
def conversation_detail(conversation_id: int, user=Depends(current_user), db=Depends(get_db)):
    conv = _own_conversation(db, user, conversation_id)
    msgs = (db.query(Message).filter(Message.conversation_id == conv.id)
              .order_by(Message.id).all())
    return {"id": conv.id, "title": conv.title,
            "messages": [conversations.message_view(m) for m in msgs]}


@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, user=Depends(current_user), db=Depends(get_db)):
    conv = _own_conversation(db, user, conversation_id)
    db.query(Message).filter(Message.conversation_id == conv.id).delete()
    db.query(AgentRun).filter(AgentRun.conversation_id == conv.id).update(
        {AgentRun.conversation_id: None})
    db.delete(conv)
    db.add(AuditLog(actor=user.username, action="conversation_deleted",
                    target=f"conversation {conversation_id}", result="ok"))
    db.commit()
    return {"deleted": True}


@app.post("/feedback")
def send_feedback(data: FeedbackData, user=Depends(current_user), db=Depends(get_db)):
    run = db.get(AgentRun, data.run_id)
    if not run or run.username != user.username:
        raise HTTPException(status_code=404, detail="Answer not found")
    db.add(Feedback(run_id=run.id, username=user.username,
                    rating=data.rating, comment=data.comment))
    db.add(AuditLog(actor=user.username, action="feedback",
                    target=f"run {run.id}",
                    result="helpful" if data.rating == 1 else "not helpful"))
    db.commit()
    return {"saved": True}


@app.get("/admin/all-documents")
def all_documents(user=Depends(current_user), db=Depends(get_db)):
    admin_only(user)
    return [{"id": d.id, "title": d.title, "department": d.department,
             "version": d.version, "status": d.status,
             "sensitivity": d.sensitivity, "ingestion": d.ingestion_status}
            for d in db.query(Document).order_by(Document.title).all()]


@app.get("/admin/unanswered")
def unanswered(user=Depends(current_user), db=Depends(get_db)):
    admin_only(user)
    rows = (db.query(AuditLog).filter(AuditLog.result.like("refused%"))
              .order_by(AuditLog.id.desc()).limit(50).all())
    return [{"user": r.actor, "question": r.target, "time": str(r.created_at)}
            for r in rows]


@app.get("/admin/dashboard")
def dashboard(user=Depends(current_user), db=Depends(get_db)):
    admin_only(user)
    runs = db.query(AgentRun).order_by(AgentRun.id.desc()).all()
    times = [r.duration_ms for r in runs if r.status != "error"]
    count = lambda s: sum(1 for r in runs if r.status == s)

    ratings = db.query(Feedback).all()
    bad = (db.query(Feedback, AgentRun)
             .join(AgentRun, AgentRun.id == Feedback.run_id)
             .filter(Feedback.rating == -1)
             .order_by(Feedback.id.desc()).limit(20).all())
    issues = (db.query(IngestionJob, Document)
                .join(Document, Document.id == IngestionJob.document_id)
                .filter(IngestionJob.status != "done").all())

    in_tok = sum(r.input_tokens or 0 for r in runs)
    out_tok = sum(r.output_tokens or 0 for r in runs)
    total_cost = sum(r.cost_usd or 0 for r in runs)
    n = len(runs) or 1
    usage_numbers = {
        "input_tokens": in_tok, "output_tokens": out_tok,
        "total_cost_usd": round(total_cost, 4),
        "avg_tokens_per_task": round((in_tok + out_tok) / n),
        "avg_cost_per_task_usd": round(total_cost / n, 6),
        "model_calls": sum(r.llm_calls or 0 for r in runs),
        "error_rate_pct": round(100 * count("error") / n, 1),
    }

    return {
        "usage": usage_numbers,
        "total": len(runs),
        "answered": count("answered"),
        "refused": count("insufficient_evidence"),
        "chitchat": count("chitchat"),
        "errors": count("error"),
        "fallbacks": sum(1 for r in runs if r.fallback),
        "p50_ms": percentile(times, 50),
        "p95_ms": percentile(times, 95),
        "helpful": sum(1 for f in ratings if f.rating == 1),
        "not_helpful": sum(1 for f in ratings if f.rating == -1),
        "recent_runs": [{"id": r.id, "user": r.username, "question": r.question,
                         "status": r.status, "ms": r.duration_ms,
                         "tokens": (r.input_tokens or 0) + (r.output_tokens or 0),
                         "cost_usd": round(r.cost_usd or 0, 6),
                         "fallback": r.fallback, "time": str(r.created_at)}
                        for r in runs[:20]],
        "bad_feedback": [{"run": f.run_id, "user": f.username,
                          "question": r.question, "time": str(f.created_at)}
                         for f, r in bad],
        "ingestion_issues": [{"file": d.filename, "status": j.status,
                              "reason": j.error} for j, d in issues],
    }


@app.get("/admin/run/{run_id}")
def run_detail(run_id: int, user=Depends(current_user), db=Depends(get_db)):
    admin_only(user)
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"question": run.question, "status": run.status, "answer": run.answer,
            "sources": json.loads(run.sources or "[]"),
            "steps": json.loads(run.steps or "[]"),
            "duration_ms": run.duration_ms, "fallback": run.fallback,
            "llm_calls": run.llm_calls, "input_tokens": run.input_tokens,
            "output_tokens": run.output_tokens, "cost_usd": run.cost_usd}



from app.admin import build_router
app.include_router(build_router(current_user, get_db))