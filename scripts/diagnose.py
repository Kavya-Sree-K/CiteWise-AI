"""Run from the project folder:  python scripts/diagnose.py
Prints what data the app is really using and why a question is answered or refused."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import vectorstore
from app.db import SessionLocal
from app.graph import ask
from app.models import Chunk, Document, User

QUESTION = sys.argv[1] if len(sys.argv) > 1 else "What is the security desk extension?"
db = SessionLocal()
print("Documents:", db.query(Document).count(), "| Chunks:", db.query(Chunk).count(),
      "| Vectors:", vectorstore.count())
new = db.query(Document).filter(Document.title.like("Security Incident Reporting SOP%")).count()
print("Security Incident Reporting SOP documents:", new,
      "(0 means you still have the OLD data: delete knowledge.db and data/chroma, "
      "then run generate_docs.py, seed_db.py, ingest.py)")
done = db.query(Document).filter(Document.ingestion_status == "done").count()
print("Documents ingested OK:", done)

user = db.query(User).filter(User.username == "emp1").first()
r = ask(db, user, QUESTION, [])
print("\nQuestion:", QUESTION)
print("Status:", r["status"])
print("Answer:", r["answer"][:300])
print("Sources:", [(s["title"], s["version"], s["page"]) for s in r["sources"]])
print("Steps:")
for s in r["steps"]:
    print("  -", s)