import csv, hashlib, sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bcrypt
from app.db import Base, engine, SessionLocal
from app.models import Role, User, Document, DocumentACL

SEED = Path("data/seed")
ROLES = ["employee", "hr", "it", "finance", "legal", "admin"]
DEPT_ROLE = {"HR": "hr", "IT": "it", "Finance": "finance",
             "Legal": "legal", "Security": "it", "Operations": "it"}
DEMO_USERS = [
    ("emp1", "Eva Employee", "employee"),
    ("hr1", "Hari HR", "hr"),
    ("it1", "Ivan IT", "it"),
    ("fin1", "Fiona Finance", "finance"),
    ("legal1", "Leo Legal", "legal"),
    ("admin1", "Asha Admin", "admin"),
    ("admin2", "Second Admin", "admin"),
]
DEMO_PASSWORD = "Passw0rd!"   # demo only; never use in real deployments

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()

    roles = {n: Role(name=n) for n in ROLES}
    db.add_all(roles.values())
    db.flush()

    pw = bcrypt.hashpw(DEMO_PASSWORD.encode(), bcrypt.gensalt()).decode()
    for username, full, role in DEMO_USERS:
        db.add(User(username=username, full_name=full, password_hash=pw,
                    role_id=roles[role].id))

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
                allowed = ROLES                                   # everyone
            else:
                allowed = {DEPT_ROLE.get(row["department"], "admin"), "admin"}
            for r in allowed:
                db.add(DocumentACL(document_id=doc.id, role_id=roles[r].id))

    db.commit()
    print("Seed complete:",
          db.query(Role).count(), "roles,",
          db.query(User).count(), "users,",
          db.query(Document).count(), "documents,",
          db.query(DocumentACL).count(), "ACL rows")
    db.close()

if __name__ == "__main__":
    main()