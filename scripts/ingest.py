import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app import vectorstore
from app.db import Base, engine, SessionLocal
from app.ingest import ingest_one, now
from app.models import Chunk, Document, IngestionJob

RESET = "--reset" in sys.argv       # wipe everything first (old behaviour)
MISSING = "--missing" in sys.argv   # only documents without chunks or stuck in 'processing'

Base.metadata.create_all(engine)
db = SessionLocal()

if RESET:
    db.query(Chunk).delete()
    db.query(IngestionJob).delete()
    db.commit()
    vectorstore.reset()
db.execute(text("DROP TABLE IF EXISTS chunks_fts"))   # derived data, rebuilt on the first search
db.commit()

docs = db.query(Document).order_by(Document.id).all()
have_chunks = {r[0] for r in db.query(Chunk.document_id).distinct()}
mode = "reset" if RESET else "missing only" if MISSING else "replace one by one"
print(f"Ingesting {len(docs)} documents ({mode}). The first run takes a few minutes.")

summary = {"done": 0, "failed": 0, "duplicate": 0, "flagged": 0, "skipped": 0}
problems = []

try:
    for i, doc in enumerate(docs, 1):
        doc_id, filename = doc.id, doc.filename
        if MISSING and doc_id in have_chunks and doc.ingestion_status != "processing":
            summary["skipped"] += 1
            continue

        db.query(IngestionJob).filter(IngestionJob.document_id == doc_id).delete()
        db.commit()

        same = (db.query(Document)
                  .filter(Document.file_hash == doc.file_hash, Document.id < doc_id)
                  .first())
        if same:
            status, error = "duplicate", f"Same file as document {same.id}"
            db.add(IngestionJob(document_id=doc_id, status=status, error=error,
                                finished_at=now()))
            doc.ingestion_status = status
            db.commit()
        else:
            status, error = ingest_one(db, doc_id)    # replaces this document's chunks only
        summary[status] += 1
        if status != "done":
            problems.append((filename, status, error))
        print(f"[{i}/{len(docs)}] {filename}: {status}")
except KeyboardInterrupt:
    print("\nStopped early. Documents already processed keep their chunks, and the rest "
          "keep their old ones.\nTo finish only what is missing, run: "
          "python scripts\\ingest.py --missing")

print("\nResult:", summary)
print("Chunks:", db.query(Chunk).count(), "| Vectors:", vectorstore.count())
for p in problems:
    print(" -", p)
db.close()