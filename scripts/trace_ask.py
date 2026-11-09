import sys
sys.path.insert(0, ".")
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app import rag

question = " ".join(sys.argv[1:]) or "How many days of annual leave do I get?"
db = Session(create_engine("sqlite:///knowledge.db"))

roles = db.execute(text("SELECT * FROM roles")).fetchall()
print("roles:", roles)
role_id = db.execute(text("SELECT id FROM roles WHERE name = 'employee'")).scalar() or roles[0][0]

rag.ensure_index(db)
ids = rag.allowed_document_ids(db, role_id)
print("role", role_id, "can search", len(ids), "documents")

chunks = rag.retrieve(db, role_id, question, None)
print("chunks:", [(c["title"], c["page"]) for c in chunks])
print("verify score:", round(rag.verify(question, chunks), 2), "needs", rag.MIN_COVERAGE)
print("keywords:", rag.keywords(question))
print("unknown words:", chunks[0].get("unknown") if chunks else None)