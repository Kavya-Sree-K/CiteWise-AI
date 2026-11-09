import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from seed_db import SEED, ROLES, DEPT_ROLE, sha256          # same folder, reused as is
from app.db import SessionLocal
from app.models import Role, Document, DocumentACL, Chunk, IngestionJob

db = SessionLocal()
roles = {r.name: r for r in db.query(Role).all()}

# replace only the document data; users, chats and usage history stay
db.query(Chunk).delete()
db.query(IngestionJob).delete()
db.query(DocumentACL).delete()
db.query(Document).delete()
db.execute(text("DROP TABLE IF EXISTS chunks_fts"))
db.flush()

with open(SEED / "metadata.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        path = SEED / row["file"]
        doc = Document(
            filename=row["file"], title=row["title"], department=row["department"],
            version=int(row["version"]), status=row["status"],
            sensitivity=row["sensitivity"], owner=row["owner"],
            effective_date=date.fromisoformat(row["effective_date"]),
            file_format=row["format"], pages=int(row["pages"]),
            file_hash=sha256(path), file_path=str(path),
            edge_case_note=row["edge_case_note"],
        )
        db.add(doc)
        db.flush()
        if row["sensitivity"] in ("Public", "Internal"):
            allowed = ROLES
        else:
            allowed = {DEPT_ROLE.get(row["department"], "admin"), "admin"}
        for r in allowed:
            db.add(DocumentACL(document_id=doc.id, role_id=roles[r].id))

db.commit()
print("Reloaded", db.query(Document).count(), "documents,",
      db.query(DocumentACL).count(), "ACL rows")
db.close()