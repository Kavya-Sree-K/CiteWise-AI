import sqlite3

c = sqlite3.connect("knowledge.db")
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
job = next((t for t in tables if "ingest" in t.lower() and "job" in t.lower()), None)
print("job table:", job)
if job:
    cols = [r[1] for r in c.execute(f"PRAGMA table_info({job})")]
    print("columns:", cols)
    for row in c.execute(f"SELECT * FROM {job} ORDER BY 1 DESC LIMIT 400"):
        text = " | ".join(str(v) for v in row)
        if "fail" in text.lower():
            print(text[:300])
            break
    seen = {}
    for row in c.execute(f"SELECT * FROM {job}"):
        for v in row:
            s = str(v)
            if any(k in s for k in ("Error", "error", "Exception", "timed out", "refused")):
                seen[s[:120]] = seen.get(s[:120], 0) + 1
    for msg, n in sorted(seen.items(), key=lambda x: -x[1])[:8]:
        print(n, "x", msg)