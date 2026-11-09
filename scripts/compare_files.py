import os
import sqlite3

c = sqlite3.connect("knowledge.db")
cols = [r[1] for r in c.execute("PRAGMA table_info(documents)")]
print("documents columns:", cols)

name_col = next((x for x in cols if x in ("filename", "file_name", "file", "path", "file_path", "source_file")), None)
print("file column:", name_col)
if not name_col:
    raise SystemExit("No file column found, paste the columns line above.")

on_disk = set(os.listdir("data/seed"))
rows = c.execute(f"SELECT id, title, {name_col}, ingestion_status FROM documents").fetchall()
missing = [(i, t, os.path.basename(str(f)), s) for i, t, f, s in rows
           if os.path.basename(str(f)) not in on_disk]
db_files = {os.path.basename(str(f)) for _, _, f, _ in rows}
extra = sorted(on_disk - db_files - {"metadata.csv", "facts.csv", "golden_questions.csv"})

print(len(rows), "documents in DB;", len(missing), "have no file on disk")
for m in missing[:15]:
    print("MISSING:", m)
print(len(extra), "files on disk that the DB does not know")
for e in extra[:15]:
    print("EXTRA:", e)