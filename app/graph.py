import json
import logging
import time
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from app import usage
from app.composer import compose
from app.models import AgentRun
from app.rag import (route, rewrite_query, ensure_index, retrieve, verify,
                     log, MIN_COVERAGE, REFUSAL)
from app.safety import redact, citations_ok
from app.tracing import trace_run

logger = logging.getLogger("knowledge.graph")
FRIENDLY_ERROR = ("Sorry, something went wrong while I was looking that up. "
                  "Please try again in a moment.")


# ---------- shared state that travels through the graph ----------
class State(TypedDict, total=False):
    question: str
    safe_question: str
    history: list
    type: str
    query: str
    used_query: str
    department: Any
    chunks: list
    coverage: float
    retries: int
    answer: str
    status: str
    sources: list
    steps: list
    details: list
    procedure: list
    comparison: list
    follow_ups: list
    fallback: bool


# ---------- tool allowlist: each agent may only use its own tools ----------
ALLOWED_TOOLS = {
    "router": {"route", "redact", "rewrite_query"},
    "retrieval": {"ensure_index", "retrieve"},
    "verifier": {"verify"},
    "composer": {"compose", "citations_ok", "redact"},
    "audit": {"log"},
}


def call_tool(agent, name, fn, *args):
    if name not in ALLOWED_TOOLS.get(agent, set()):
        raise PermissionError(f"{agent} is not allowed to use {name}")
    return fn(*args)


def ctx(config):
    c = config["configurable"]
    return c["db"], c["user"]


# ---------- agents (nodes) ----------
def router_node(state: State, config: RunnableConfig):
    q = state["question"]
    plan = call_tool("router", "route", route, q, state["history"])
    if plan["query"] != q and state["history"]:      # follow-up: rewrite it as a full question
        plan["query"] = call_tool("router", "rewrite_query", rewrite_query,
                                  state["history"][-1], q, plan["query"])
    safe = call_tool("router", "redact", redact, q)
    steps = list(state["steps"])
    if safe != q:
        steps.append("Guardrail: personal data hidden before logging and before the AI")
    note = f"Router: {plan['type']}"
    if plan["department"]:
        note += f", department {plan['department']}"
    if plan["query"] != q:
        note += ", follow-up joined with previous question"
    steps.append(note)
    return {"type": plan["type"], "query": plan["query"],
            "department": plan["department"], "safe_question": safe,
            "steps": steps}


def chitchat_node(state: State, config: RunnableConfig):
    return {"status": "chitchat", "sources": [],
            "answer": "Hello! Ask me a question about company policies."}


def retrieval_node(state: State, config: RunnableConfig):
    db, user = ctx(config)
    call_tool("retrieval", "ensure_index", ensure_index, db)
    if state["retries"] == 0:
        query, dept = state["query"], state["department"]
    else:                                   # retry: plain question, all departments
        query, dept = state["question"], None
    chunks = call_tool("retrieval", "retrieve", retrieve, db, user.role_id, query, dept)
    mode = chunks[0]["mode"] if chunks else "no results"
    steps = state["steps"] + [f"Retrieval ({mode}): {len(chunks)} chunks found"]
    return {"chunks": chunks, "used_query": query, "steps": steps}


def verifier_node(state: State, config: RunnableConfig):
    cov = call_tool("verifier", "verify", verify, state["used_query"], state["chunks"])
    steps = state["steps"] + [
        f"Verifier: evidence score {cov:.2f} (needs {MIN_COVERAGE:.2f})"]
    return {"coverage": cov, "steps": steps}


def retry_node(state: State, config: RunnableConfig):
    steps = state["steps"] + ["Verifier: weak evidence, retrying once with the plain question"]
    return {"retries": state["retries"] + 1, "steps": steps}


def composer_node(state: State, config: RunnableConfig):
    # the composer sees the full (de-personalised) question, so a follow-up
    # such as "and for contractors?" still makes sense to the model
    question = call_tool("composer", "redact", redact, state["used_query"])
    result, note = call_tool("composer", "compose", compose, question, state["chunks"])
    steps = state["steps"] + [note]
    fallback = "simple mode" in note or "Claude" in note
    if result.get("not_enough"):
        steps.append("Composer: sources do not answer the question, refusing")
        return {"answer": REFUSAL, "status": "insufficient_evidence",
                "sources": [], "steps": steps, "fallback": fallback}
    answer, sources = result["answer"], result["sources"]
    if not call_tool("composer", "citations_ok", citations_ok, answer, len(sources)):
        steps.append("Guardrail: answer cited a source that does not exist, using plain text")
        answer = "Here is the closest passage I found: " + state["chunks"][0]["text"][:400]
    return {"answer": answer, "status": "answered", "sources": sources,
            "details": result["details"], "procedure": result["procedure"],
            "comparison": result["comparison"], "follow_ups": result["follow_ups"],
            "steps": steps, "fallback": fallback}


def refusal_node(state: State, config: RunnableConfig):
    steps = state["steps"] + ["Verifier: insufficient evidence, refusing"]
    return {"answer": REFUSAL, "status": "insufficient_evidence",
            "sources": [], "steps": steps}


RESULT = {"answered": "answered",
          "insufficient_evidence": "refused: not enough evidence",
          "chitchat": "chitchat"}


def audit_node(state: State, config: RunnableConfig):
    db, user = ctx(config)
    call_tool("audit", "log", log, db, user, state["safe_question"],
              RESULT[state["status"]])
    return {"steps": state["steps"] + ["Audit: saved"]}


# ---------- conditional routing ----------
def after_router(state: State):
    return "chitchat" if state["type"] == "chitchat" else "retrieval"


def after_verifier(state: State):
    if state["coverage"] >= MIN_COVERAGE:
        return "composer"
    can_retry = state["retries"] < 1 and (
        state["department"] or state["query"] != state["question"])
    return "retry" if can_retry else "refusal"


# ---------- build the graph ----------
g = StateGraph(State)
g.add_node("router", router_node)
g.add_node("chitchat", chitchat_node)
g.add_node("retrieval", retrieval_node)
g.add_node("verifier", verifier_node)
g.add_node("retry", retry_node)
g.add_node("composer", composer_node)
g.add_node("refusal", refusal_node)
g.add_node("audit", audit_node)

g.add_edge(START, "router")
g.add_conditional_edges("router", after_router,
                        {"chitchat": "chitchat", "retrieval": "retrieval"})
g.add_edge("retrieval", "verifier")
g.add_conditional_edges("verifier", after_verifier,
                        {"composer": "composer", "retry": "retry", "refusal": "refusal"})
g.add_edge("retry", "retrieval")
g.add_edge("composer", "audit")
g.add_edge("refusal", "audit")
g.add_edge("chitchat", "audit")
g.add_edge("audit", END)

# GRAPH = g.compile()

CHECKPOINT_FILE = os.getenv("CHECKPOINT_DB", "data/checkpoints.sqlite")
Path(CHECKPOINT_FILE).parent.mkdir(parents=True, exist_ok=True)
CHECKPOINTER = SqliteSaver(sqlite3.connect(CHECKPOINT_FILE, check_same_thread=False))
GRAPH = g.compile(checkpointer=CHECKPOINTER)     # the state after every step is saved


def prune_checkpoints(days=14):
    """Drop saved graph state older than `days`, so the checkpoint file stays small."""
    cutoff = f"q{int(time.time() - days * 86400)}"      # trace ids start with the time
    conn = sqlite3.connect(CHECKPOINT_FILE)
    try:
        for table in ("writes", "checkpoints"):
            try:
                conn.execute(f"DELETE FROM {table} WHERE thread_id < ?", (cutoff,))
            except sqlite3.OperationalError:            # tables do not exist yet
                pass
        conn.commit()
    finally:
        conn.close()


def save_run(db, user, question, out, fallback, ms, conversation_id=None):
    """One AgentRun row per question: feeds feedback, dashboard and unanswered list."""
    run = AgentRun(username=user.username, role=user.role.name,
                   question=question[:500], status=out["status"],
                   answer=out.get("answer", ""),
                   sources=json.dumps(out.get("sources", [])),
                   steps=json.dumps(out.get("steps", [])),
                   fallback=fallback, duration_ms=ms, conversation_id=conversation_id,
                   llm_calls=out.get("llm_calls", 0),
                   input_tokens=out.get("input_tokens", 0),
                   output_tokens=out.get("output_tokens", 0),
                   cost_usd=out.get("cost_usd", 0.0))
    db.add(run)
    db.commit()
    return run.id


def ask(db, user, question, history=None, conversation_id=None):
    start = time.perf_counter()
    usage.start()                     # count tokens and cost of every model call
    safe = redact(question)
    # The graph, its saved checkpoints and the traces only ever see the redacted text.
    history = [redact(h) for h in (history or [])]
    steps = (["Guardrail: personal data hidden before logging and before the AI"]
             if safe != question else [])
    trace_id = f"q{int(time.time())}-{uuid.uuid4().hex[:6]}"
    with trace_run(user, conversation_id, trace_id) as callbacks:
        try:
            state = GRAPH.invoke(
                {"question": safe, "history": history, "retries": 0, "steps": steps},
                config={"configurable": {"db": db, "user": user, "thread_id": trace_id},
                        "callbacks": callbacks})
            out = {"status": state["status"], "answer": state["answer"],
                   "sources": state.get("sources", []), "steps": state["steps"],
                   "details": state.get("details", []),
                   "procedure": state.get("procedure", []),
                   "comparison": state.get("comparison", []),
                   "follow_ups": state.get("follow_ups", [])}
            fallback = bool(state.get("fallback", False))
        except Exception:
            logger.exception("agent run failed")
            db.rollback()
            out = {"status": "error", "answer": FRIENDLY_ERROR, "sources": [],
                   "steps": ["Error: the request failed, see the server log"]}
            fallback = False
    out["steps"] = list(out["steps"]) + [f"Trace id: {trace_id}"]
    ms = int((time.perf_counter() - start) * 1000)
    used = usage.snapshot()
    out.update(llm_calls=used["calls"], input_tokens=used["input_tokens"],
               output_tokens=used["output_tokens"], cost_usd=used["cost_usd"])
    out["run_id"] = save_run(db, user, safe, out, fallback, ms, conversation_id)
    return out