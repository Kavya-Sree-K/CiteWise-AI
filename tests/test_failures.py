"""Failure handling: model outage, timeout, invalid input, missing login."""
import requests

from app import composer

Q = "What is the security desk extension?"


def _fail_with(exc):
    def boom(*args, **kwargs):
        raise exc
    return boom


def test_model_outage_falls_back_to_simple_mode(client, emp, monkeypatch):
    monkeypatch.setattr(requests, "post",
                        _fail_with(requests.exceptions.ConnectionError("ollama down")))
    r = client.post("/ask", headers=emp, json={"question": Q})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "answered"                 # still answers from the documents
    assert any("simple mode" in s for s in body["steps"])


def test_model_timeout_falls_back_to_simple_mode(client, emp, monkeypatch):
    monkeypatch.setattr(requests, "post",
                        _fail_with(requests.exceptions.Timeout("too slow")))
    r = client.post("/ask", headers=emp, json={"question": Q})
    assert r.status_code == 200
    assert any("simple mode" in s for s in r.json()["steps"])


def test_garbage_model_output_is_rejected_by_the_safety_checks():
    assert composer.build_result(composer.parse_json("not json at all"), []) is None
    assert composer.build_result({"answer": "I do not know"}, [
        {"title": "Policy", "text": "The desk is open.", "version": 1, "page": 1}]) is None


def test_empty_question_is_rejected(client, emp):
    r = client.post("/ask", headers=emp, json={"question": ""})
    assert r.status_code in (400, 422)


def test_missing_question_field_is_rejected(client, emp):
    assert client.post("/ask", headers=emp, json={}).status_code == 422


def test_asking_without_login_is_refused(client):
    assert client.post("/ask", json={"question": Q}).status_code in (401, 403)