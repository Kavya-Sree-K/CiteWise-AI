r"""Print the saved graph state of one question, step by step.

    python scripts\show_trace.py                       the 10 most recent trace ids
    python scripts\show_trace.py q1793691457-8e8b93    one question, step by step
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import CHECKPOINT_FILE, GRAPH

NOTHING_YET = "No questions have been traced yet. Ask a question in the app first."

if len(sys.argv) < 2:
    con = sqlite3.connect(CHECKPOINT_FILE)
    try:
        rows = con.execute("SELECT DISTINCT thread_id FROM checkpoints "
                           "ORDER BY thread_id DESC LIMIT 10").fetchall()
    except sqlite3.OperationalError:            # the tables appear with the first question
        rows = []
    if not rows:
        sys.exit(NOTHING_YET)
    print("Recent trace ids (also the last line of 'How this answer was produced'):")
    for (thread_id,) in rows:
        print(" ", thread_id)
    sys.exit()

history = list(GRAPH.get_state_history({"configurable": {"thread_id": sys.argv[1]}}))
if not history:
    sys.exit("No saved state for that trace id. Run the script without an id to list them.")
snapshots = list(reversed(history))
begin = datetime.fromisoformat(snapshots[0].created_at)
for snap in snapshots:
    seconds = (datetime.fromisoformat(snap.created_at) - begin).total_seconds()
    last_step = (snap.values.get("steps") or ["(start)"])[-1]
    next_node = ", ".join(snap.next) or "finished"
    print(f"+{seconds:5.2f}s  next: {next_node:<10} last step: {last_step}")
final = history[0].values
print("\nFinal status:", final.get("status"), "| question as stored:", final.get("question"))