import sqlite3
from datetime import date

c = sqlite3.connect("knowledge.db")
today = date.today().isoformat()

print("== active Leave Policy documents ==")
print("title | ver | ingestion | effective | chunks | roles")
for r in c.execute(
        "SELECT d.title, d.version, d.ingestion_status, d.effective_date, "
        "(SELECT COUNT(*) FROM chunks k WHERE k.document_id = d.id), "
        "(SELECT group_concat(role_id) FROM document_acl a WHERE a.document_id = d.id) "
        "FROM documents d WHERE d.title LIKE 'Leave Policy%' AND d.status = 'active' "
        "ORDER BY d.title"):
    print(r)

print("\n== search index ==")
print("chunks:", c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
try:
    print("chunks_fts rows:", c.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0])
    print("fts rows matching 'leave':",
          c.execute("SELECT COUNT(*) FROM chunks_fts WHERE chunks_fts MATCH '\"leave\"'").fetchone()[0])
except Exception as e:
    print("chunks_fts problem:", e)

print("\n== documents by ingestion status ==")
print(c.execute("SELECT ingestion_status, COUNT(*) FROM documents GROUP BY 1").fetchall())
print("\nemployee (role 1) can see", c.execute(
    "SELECT COUNT(*) FROM documents d JOIN document_acl a ON a.document_id = d.id "
    "WHERE a.role_id = 1 AND d.status='active' AND d.ingestion_status='done' "
    "AND d.effective_date <= ?", (today,)).fetchone()[0], "documents")