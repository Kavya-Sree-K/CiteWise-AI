"""Saved graph state (checkpoints) and optional tracing."""
from app import tracing
from app.graph import GRAPH, prune_checkpoints


def test_every_question_saves_its_graph_state_without_personal_data(client, emp):
    body = client.post("/ask", headers=emp, json={
        "question": "Mail john.doe@example.com about the security desk extension"}).json()
    assert body["steps"][-1].startswith("Trace id: ")
    trace_id = body["steps"][-1].split(": ", 1)[1]
    history = list(GRAPH.get_state_history({"configurable": {"thread_id": trace_id}}))
    assert len(history) >= 5                                   # one checkpoint per step
    assert "john.doe@example.com" not in str(history[0].values)


def test_tracing_is_off_without_langfuse_keys(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    assert not tracing.enabled()
    tracing.record_generation("m", "prompt", "answer", 1, 1)   # does nothing, raises nothing


def test_pruning_old_checkpoints_does_not_fail():
    prune_checkpoints(days=14)
    