from datetime import datetime, timezone
from pathlib import Path

from docx import Document as DocxFile
from pypdf import PdfReader

from app import vectorstore
from app.chunking import build_chunks, csv_chunks, page_units
from app.db import SessionLocal
from app.embeddings import embed
from app.models import AuditLog, Chunk, Document, IngestionJob
from app.safety import looks_like_injection


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def read_pages(path):
    """Return a list of (page_number, text)."""
    raw = Path(path).read_bytes()
    if len(raw.strip()) == 0:
        raise ValueError("File is empty")

    if raw.startswith(b"%PDF") or path.lower().endswith(".pdf"):
        reader = PdfReader(path)
        return [(i + 1, p.extract_text() or "") for i, p in enumerate(reader.pages)]

    if path.lower().endswith(".docx"):
        doc = DocxFile(path)
        pages, lines, n = [], [], 1
        for p in doc.paragraphs:
            if p.text.strip():
                lines.append(p.text)
            if 'w:type="page"' in p._p.xml:
                pages.append((n, "\n".join(lines)))
                lines, n = [], n + 1
        pages.append((n, "\n".join(lines)))
        return pages

    return [(1, raw.decode("utf-8", errors="replace"))]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def plan_chunks(file_format, pages):
    """Return a list of (page, section, text) using the right strategy per file type."""
    if file_format == "csv":
        return [(1, sec, txt) for sec, txt in csv_chunks(pages[0][1])]

    per_page, section = [], ""
    for page_no, text in pages:
        units, section = page_units(text, section)
        if units:
            per_page.append((page_no, units))

    flat = [sentence for _, units in per_page for _, sentence in units]
    vectors = embed(flat, "document") if len(flat) >= 6 else []   # for topic shifts

    out, pos = [], 0
    for page_no, units in per_page:
        sims = None
        if vectors:
            vs = vectors[pos:pos + len(units)]
            sims = [dot(vs[i], vs[i + 1]) for i in range(len(vs) - 1)]
        pos += len(units)
        for sec, txt in build_chunks(units, sims):
            out.append((page_no, sec, txt))
    return out


def ingest_one(db, doc_id):
    doc = db.get(Document, doc_id)
    job = IngestionJob(document_id=doc_id, status="processing")
    db.add(job)
    doc.ingestion_status = "processing"
    db.commit()
    job_id, path = job.id, doc.file_path
    title, dept, version, fmt = doc.title, doc.department, doc.version, doc.file_format

    try:
        pages = read_pages(path)
        hit = looks_like_injection(" ".join(t for _, t in pages))
        if hit:
            status, error = "flagged", f"Possible prompt injection: {hit}"
        else:
            planned = plan_chunks(fmt, pages)
            if not planned:
                raise ValueError("No text found")
            # the embedding text carries the title, department and section
            vectors = embed([f"{title}, {dept}. {sec}\n{txt}" for _, sec, txt in planned],
                            "document")

            db.query(Chunk).filter(Chunk.document_id == doc_id).delete()
            vectorstore.delete_document(doc_id)
            rows, counters = [], {}
            for page_no, sec, txt in planned:
                n = counters.get(page_no, 0)
                counters[page_no] = n + 1
                row = Chunk(document_id=doc_id, page=page_no, chunk_no=n,
                            section=sec[:200], text=txt)
                db.add(row)
                rows.append(row)
            db.flush()
            vectorstore.add(
                [r.id for r in rows], vectors,
                [{"document_id": doc_id, "page": r.page, "version": version} for r in rows],
                [r.text for r in rows])
            db.get(Document, doc_id).pages = len(pages)
            status, error = "done", ""
    except Exception as e:
        db.rollback()
        try:
            vectorstore.delete_document(doc_id)
        except Exception:
            pass
        status, error = "failed", str(e)[:200]

    job = db.get(IngestionJob, job_id)
    job.status, job.error, job.finished_at = status, error, now()
    db.get(Document, doc_id).ingestion_status = status
    db.commit()
    return status, error


def process_upload(doc_id, replaces_id, actor):
    """Runs in the background after an upload."""
    db = SessionLocal()
    try:
        status, error = ingest_one(db, doc_id)
        doc = db.get(Document, doc_id)
        if status == "done":
            doc.status = "active"
            result = f"activated as v{doc.version}"
            if replaces_id:
                old = db.get(Document, replaces_id)
                if old and old.status == "active":
                    old.status = "superseded"
                    result += f"; document {old.id} v{old.version} superseded"
        else:
            result = f"not activated: {status} - {error}"
        db.add(AuditLog(actor=actor, action="ingestion",
                        target=f"document {doc_id}", result=result[:500]))
        db.commit()
    finally:
        db.close()
