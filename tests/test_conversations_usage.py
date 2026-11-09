"""Stored conversations and token/cost tracking."""
import sqlite3
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

from app import composer, usage
from app.models import AgentRun, Conversation, Message

Q1 = "What is the security desk extension?"


# ---------------------------------------------------------------- conversations
def test_first_question_creates_a_conversation_and_stores_both_messages(client, emp, db):
    body = client.post("/ask", headers=emp, json={"question": Q1}).json()
    cid = body["conversation_id"]
    assert cid
    msgs = db.query(Message).filter(Message.conversation_id == cid).order_by(Message.id).all()
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[1].run_id == body["run_id"]


def test_following_question_joins_the_same_conversation(client, emp, db):
    cid = client.post("/ask", headers=emp, json={"question": Q1}).json()["conversation_id"]
    second = client.post("/ask", headers=emp, json={
        "question": "How do I report a security incident?", "conversation_id": cid}).json()
    assert second["conversation_id"] == cid
    assert db.query(Message).filter(Message.conversation_id == cid).count() == 4


def test_follow_up_context_comes_from_the_database_not_the_browser(client, emp, monkeypatch):
    import app.main as main
    cid = client.post("/ask", headers=emp, json={"question": Q1}).json()["conversation_id"]
    seen = {}
    real_ask = main.ask
    monkeypatch.setattr(main, "ask", lambda db, user, q, history, **kw:
                        (seen.update(history=history), real_ask(db, user, q, history, **kw))[1])
    client.post("/ask", headers=emp, json={"question": "and how fast?", "conversation_id": cid,
                                           "history": ["fake browser history"]})
    assert seen["history"] == [Q1]


def test_a_stored_conversation_can_be_reopened_with_its_details(client, emp):
    cid = client.post("/ask", headers=emp, json={"question": Q1}).json()["conversation_id"]
    r = client.get(f"/conversations/{cid}", headers=emp).json()
    assert [m["role"] for m in r["messages"]] == ["user", "assistant"]
    assert "sources" in r["messages"][1] and r["messages"][1]["run_id"]
    assert any(c["id"] == cid for c in client.get("/conversations", headers=emp).json())


def test_other_users_cannot_read_ask_in_or_delete_my_conversation(client, emp, hr, admin_a):
    cid = client.post("/ask", headers=emp, json={"question": Q1}).json()["conversation_id"]
    for other in (hr, admin_a):                       # even an admin is refused
        assert client.get(f"/conversations/{cid}", headers=other).status_code == 404
        assert client.delete(f"/conversations/{cid}", headers=other).status_code == 404
        assert client.post("/ask", headers=other, json={
            "question": Q1, "conversation_id": cid}).status_code == 404
        assert all(c["id"] != cid for c in client.get("/conversations", headers=other).json())


def test_deleting_a_conversation_removes_its_messages_but_keeps_the_run(client, emp, db):
    body = client.post("/ask", headers=emp, json={"question": Q1}).json()
    cid, run_id = body["conversation_id"], body["run_id"]
    assert client.delete(f"/conversations/{cid}", headers=emp).status_code == 200
    db.expire_all()
    assert client.get(f"/conversations/{cid}", headers=emp).status_code == 404
    assert db.query(Message).filter(Message.conversation_id == cid).count() == 0
    assert db.get(AgentRun, run_id).conversation_id is None      # audit data is kept


def test_personal_data_is_not_stored_in_the_conversation(client, emp, db):
    body = client.post("/ask", headers=emp, json={
        "question": "Mail john.doe@example.com about the security desk extension"}).json()
    texts = [m.content for m in db.query(Message).filter(
        Message.conversation_id == body["conversation_id"]).all()]
    conv = db.get(Conversation, body["conversation_id"])
    assert all("john.doe@example.com" not in t for t in texts + [conv.title])


# ---------------------------------------------------------------- token and cost
def test_ollama_usage_is_read_from_the_response_and_is_free_by_default(monkeypatch):
    usage.start()
    monkeypatch.delenv("OLLAMA_PRICE_IN", raising=False)
    usage.record("ollama", "qwen", 1200, 80)
    snap = usage.snapshot()
    assert (snap["input_tokens"], snap["output_tokens"], snap["calls"]) == (1200, 80, 1)
    assert snap["cost_usd"] == 0


def test_claude_cost_uses_the_configured_prices(monkeypatch):
    monkeypatch.setenv("CLAUDE_PRICE_IN", "3")
    monkeypatch.setenv("CLAUDE_PRICE_OUT", "15")
    usage.start()
    usage.record("claude", "m", 1_000_000, 100_000)
    assert usage.snapshot()["cost_usd"] == pytest.approx(3 + 1.5)


def test_tokens_are_estimated_when_the_model_reports_none():
    assert usage.estimate_tokens("a" * 400) == 100
    assert usage.estimate_tokens("") == 1


def test_a_question_stores_tokens_and_cost_and_the_dashboard_adds_them_up(
        client, emp, admin_a, db, monkeypatch):
    class FakeResponse:
        def raise_for_status(self): pass
        def json(self):
            return {"message": {"content": '{"enough_information": true, "answer": '
                                           '"The security desk extension is 5500 [1].", '
                                           '"sources_used": [1]}'},
                    "prompt_eval_count": 900, "eval_count": 40}
    monkeypatch.setattr(composer.requests, "post", lambda *a, **k: FakeResponse())
    monkeypatch.setenv("OLLAMA_PRICE_IN", "1")           # notional price: 1 USD per million tokens
    body = client.post("/ask", headers=emp, json={"question": Q1}).json()
    assert body["input_tokens"] == 900 and body["output_tokens"] == 40
    assert body["cost_usd"] == pytest.approx(900 / 1_000_000)
    db.expire_all()
    run = db.get(AgentRun, body["run_id"])
    assert (run.input_tokens, run.output_tokens, run.llm_calls) == (900, 40, 1)
    dash = client.get("/admin/dashboard", headers=admin_a).json()
    assert dash["usage"]["input_tokens"] >= 900
    assert dash["usage"]["avg_cost_per_task_usd"] >= 0
    assert "tokens" in dash["recent_runs"][0]


def test_non_admins_cannot_see_the_usage_dashboard(client, emp):
    assert client.get("/admin/dashboard", headers=emp).status_code == 403


# ---------------------------------------------------------------- upgrading an old database
def test_upgrade_schema_adds_missing_tables_and_columns_without_losing_rows():
    from app.db import upgrade_schema
    path = Path(tempfile.mkdtemp()) / "old.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE agent_runs (id INTEGER PRIMARY KEY, username VARCHAR(80), "
                "role VARCHAR(50), question VARCHAR(500), status VARCHAR(30), answer TEXT, "
                "sources TEXT, steps TEXT, fallback BOOLEAN, duration_ms INTEGER, created_at DATETIME)")
    con.execute("INSERT INTO agent_runs (username, role, question, status, answer, sources, steps, "
                "fallback, duration_ms) VALUES ('u','employee','old question','answered','a','[]','[]',0,5)")
    con.commit()
    con.close()
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    upgrade_schema(engine)
    upgrade_schema(engine)                                   # running twice is harmless
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("agent_runs")}
    assert {"input_tokens", "output_tokens", "cost_usd", "llm_calls", "conversation_id"} <= cols
    assert {"conversations", "messages"} <= set(insp.get_table_names())
    with engine.connect() as c:
        row = c.exec_driver_sql("SELECT question, input_tokens, cost_usd FROM agent_runs").fetchone()
    assert row == ("old question", 0, 0.0)