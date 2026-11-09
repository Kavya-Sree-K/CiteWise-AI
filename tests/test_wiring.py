"""Regression tests for the bugs that made the UI look 'unchanged':
the structured composer, run ids, feedback and the dashboard must all be connected."""
from app.models import AgentRun


def test_every_question_is_saved_as_an_agent_run_and_returns_a_run_id(client, emp, db):
    before = db.query(AgentRun).count()
    r = client.post("/ask", headers=emp, json={"question": "How do I report a security incident?"})
    body = r.json()
    assert r.status_code == 200 and body["run_id"]
    db.expire_all()
    assert db.query(AgentRun).count() == before + 1


def test_security_incident_question_is_answered_from_the_sop(client, emp):
    body = client.post("/ask", headers=emp,
                       json={"question": "How do I report a security incident?"}).json()
    assert body["status"] == "answered"
    assert any("Incident Reporting" in s["title"] for s in body["sources"])


def test_answer_carries_the_structured_fields_the_ui_expects(client, emp):
    body = client.post("/ask", headers=emp,
                       json={"question": "What is the security desk extension?"}).json()
    for key in ("details", "procedure", "comparison", "follow_ups", "sources", "steps"):
        assert key in body


def test_feedback_works_and_shows_in_the_dashboard(client, emp, admin_a):
    run_id = client.post("/ask", headers=emp,
                         json={"question": "How many days of annual leave do I get?"}).json()["run_id"]
    assert client.post("/feedback", headers=emp,
                       json={"run_id": run_id, "rating": -1, "comment": "test"}).status_code == 200
    dash = client.get("/admin/dashboard", headers=admin_a).json()
    assert dash["total"] >= 1 and dash["not_helpful"] >= 1
    assert any(b["run"] == run_id for b in dash["bad_feedback"])


def test_refused_questions_appear_in_the_unanswered_list(client, emp, admin_a):
    client.post("/ask", headers=emp, json={"question": "What is the cafeteria menu on Friday?"})
    rows = client.get("/admin/unanswered", headers=admin_a).json()
    assert any("cafeteria" in r["question"].lower() for r in rows)


def test_plural_words_still_match(client, emp):
    body = client.post("/ask", headers=emp,
                       json={"question": "When do I need a receipt? (global)"}).json()
    assert body["status"] == "answered"
