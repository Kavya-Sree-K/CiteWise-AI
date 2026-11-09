"""Admin dashboard: same numbers as before, shown as KPI strips, charts and tables."""
import altair as alt
import pandas as pd
import requests
import streamlit as st

from brand import (AMBER, CORAL, GREEN, INDIGO, SLATE, TEAL, esc, page_header,
                   section, stat_strip)

OUTCOME_COLORS = {"Answered": GREEN, "Refused": AMBER, "Chit-chat": TEAL, "Errors": CORAL}
FEEDBACK_COLORS = {"Helpful": GREEN, "Not helpful": CORAL}
DOC_STATUS_COLORS = {"active": GREEN, "superseded": AMBER, "archived": SLATE, "revoked": CORAL}
INGEST_COLORS = {"done": GREEN, "failed": CORAL, "duplicate": SLATE, "flagged": AMBER,
                 "processing": INDIGO, "queued": TEAL}


def show(chart):
    chart = chart.configure_view(strokeWidth=0).configure_axis(
        labelColor="#475569", titleColor="#475569", gridColor="#E3E7F0", domain=False)
    try:
        st.altair_chart(chart, use_container_width=True)
    except TypeError:                       # newer Streamlit versions
        st.altair_chart(chart)


def donut(pairs, colors, height=250):
    df = pd.DataFrame(pairs, columns=["label", "value"])
    df = df[df["value"] > 0]
    if df.empty:
        st.info("Nothing to show yet.")
        return
    scale = alt.Scale(domain=list(df["label"]), range=[colors.get(x, SLATE) for x in df["label"]])
    arc = alt.Chart(df).mark_arc(innerRadius=62, outerRadius=100, cornerRadius=3).encode(
        theta=alt.Theta("value:Q", stack=True),
        color=alt.Color("label:N", scale=scale, legend=alt.Legend(orient="bottom", title=None)),
        tooltip=[alt.Tooltip("label:N", title="Type"), alt.Tooltip("value:Q", title="Count")])
    show(arc.properties(height=height))


def latency_chart(runs, p50_ms, p95_ms):
    df = pd.DataFrame(runs)
    if df.empty or "ms" not in df:
        st.info("No questions asked yet.")
        return
    df = df.sort_values("id")
    df["Run"] = "#" + df["id"].astype(str)
    df["Seconds"] = (df["ms"] / 1000).round(2)
    df["Result"] = df["status"].map({"answered": "Answered", "insufficient_evidence": "Refused",
                                     "chitchat": "Chit-chat", "error": "Errors"}).fillna("Other")
    scale = alt.Scale(domain=list(OUTCOME_COLORS), range=list(OUTCOME_COLORS.values()))
    bars = alt.Chart(df).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X("Run:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Seconds:Q", title="Seconds"),
        color=alt.Color("Result:N", scale=scale, legend=alt.Legend(orient="bottom", title=None)),
        tooltip=["Run", "Seconds", "Result"])
    rules = alt.Chart(pd.DataFrame({"y": [p50_ms / 1000, p95_ms / 1000], "Line": ["p50", "p95"]})
                      ).mark_rule(strokeDash=[5, 4], strokeWidth=2).encode(
        y="y:Q", color=alt.Color("Line:N", scale=alt.Scale(domain=["p50", "p95"],
                                                         range=[INDIGO, CORAL]),
                                 legend=alt.Legend(orient="bottom", title=None)))
    show(alt.layer(bars, rules).resolve_scale(color="independent").properties(height=280))


def docs_by_department(docs):
    df = pd.DataFrame(docs)
    if df.empty:
        st.info("No documents yet.")
        return
    counts = df.groupby(["department", "status"]).size().reset_index(name="Documents")
    scale = alt.Scale(domain=list(DOC_STATUS_COLORS), range=list(DOC_STATUS_COLORS.values()))
    chart = alt.Chart(counts).mark_bar().encode(
        y=alt.Y("department:N", sort="-x", title=None),
        x=alt.X("Documents:Q", title="Documents", axis=alt.Axis(tickMinStep=1, format="d")),
        color=alt.Color("status:N", scale=scale, legend=alt.Legend(orient="bottom", title=None)),
        tooltip=["department", "status", "Documents"])
    show(chart.properties(height=280))


def usage_numbers(u):
    """Show whatever the usage summary contains, with readable labels."""
    labels = {"input_tokens": "Input tokens", "output_tokens": "Output tokens",
              "total_tokens": "Total tokens", "calls": "Model calls", "llm_calls": "Model calls",
              "avg_tokens_per_task": "Tokens per task", "avg_cost_per_task_usd": "Cost per task",
              "total_cost_usd": "Total cost", "error_rate": "Error rate"}
    colors = [INDIGO, TEAL, AMBER, GREEN, CORAL, SLATE]
    items = []
    for i, (key, value) in enumerate(u.items()):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if "cost" in key:
            text = f"${value:.5f}" if "avg" in key else f"${value:.4f}"
        elif "rate" in key:
            text = f"{value * 100:.1f}%" if value <= 1 else f"{value:.1f}%"
        elif isinstance(value, float):
            text = f"{value:,.1f}"
        else:
            text = f"{value:,}"
        items.append({"label": labels.get(key, key.replace("_", " ").capitalize()),
                      "value": text, "color": colors[i % len(colors)]})
    for start in range(0, len(items), 4):
        stat_strip(items[start:start + 4])
    return len(items)


def dashboard_page(headers, api, error_text):
    page_header("Dashboard", "How the assistant is used, how well it answers, and the state of your documents.")
    r = requests.get(f"{api}/admin/dashboard", headers=headers)
    if r.status_code != 200:
        st.error(error_text(r))
        return
    d = r.json()
    total = d.get("total", 0)
    answered, refused, errors = d.get("answered", 0), d.get("refused", 0), d.get("errors", 0)
    pct = lambda n: f"{100 * n / total:.0f}% of questions" if total else ""

    stat_strip([
        {"label": "Questions asked", "value": total, "color": INDIGO},
        {"label": "Answered", "value": answered, "sub": pct(answered), "color": GREEN},
        {"label": "Refused", "value": refused, "sub": pct(refused), "color": AMBER},
        {"label": "Errors", "value": errors, "sub": pct(errors), "color": CORAL}])
    stat_strip([
        {"label": "Response time p50", "value": f"{d.get('p50_ms', 0) / 1000:.1f} s", "color": INDIGO},
        {"label": "Response time p95", "value": f"{d.get('p95_ms', 0) / 1000:.1f} s", "color": INDIGO},
        {"label": "Helpful", "value": d.get("helpful", 0), "color": GREEN},
        {"label": "Not helpful", "value": d.get("not_helpful", 0), "color": CORAL},
        {"label": "AI fallbacks", "value": d.get("fallbacks", 0), "sub": "model unavailable",
         "color": AMBER}])

    t_over, t_docs, t_usage, t_feed, t_runs = st.tabs(
        ["Overview", "Documents", "Usage and cost", "Feedback", "Questions"])

    with t_over:
        a, b = st.columns(2)
        with a:
            section("Question outcomes", f"{total} questions in total")
            donut([("Answered", answered), ("Refused", refused),
                   ("Chit-chat", d.get("chitchat", 0)), ("Errors", errors)], OUTCOME_COLORS)
        with b:
            helpful, bad = d.get("helpful", 0), d.get("not_helpful", 0)
            rated = f"{100 * helpful / (helpful + bad):.0f}% rated helpful" if helpful + bad else "No ratings yet"
            section("Answer feedback", rated)
            donut([("Helpful", helpful), ("Not helpful", bad)], FEEDBACK_COLORS)
        section("Response time of recent questions", "Dashed lines show the p50 and p95 of all questions")
        latency_chart(d.get("recent_runs", []), d.get("p50_ms", 0), d.get("p95_ms", 0))

    with t_docs:
        docs_r = requests.get(f"{api}/admin/all-documents", headers=headers)
        docs = docs_r.json() if docs_r.status_code == 200 else []
        a, b = st.columns(2)
        with a:
            section("Documents by department", "Coloured by lifecycle status")
            docs_by_department(docs)
        with b:
            section("Ingestion status", f"{len(docs)} documents in total")
            counts = pd.Series([x.get("ingestion", "unknown") for x in docs]).value_counts()
            donut([(k, int(v)) for k, v in counts.items()], INGEST_COLORS)
        section("Ingestion problems", "Documents that could not be processed")
        if d.get("ingestion_issues"):
            st.dataframe(pd.DataFrame(d["ingestion_issues"]), use_container_width=True)
        else:
            st.success("No ingestion problems.")

    with t_usage:
        section("Model usage", "Tokens and cost across all questions")
        if not usage_numbers(d.get("usage") or {}):
            st.info("No usage has been recorded yet. Ask a question and it will appear here.")
        u = d.get("usage") or {}
        if u.get("input_tokens") or u.get("output_tokens"):
            section("Input and output tokens")
            donut([("Input tokens", u.get("input_tokens", 0)),
                   ("Output tokens", u.get("output_tokens", 0))],
                  {"Input tokens": INDIGO, "Output tokens": TEAL})
        st.caption("A local model has no per-token charge, so cost is only shown "
                   "when notional prices are set.")

    with t_feed:
        section("Answers marked not helpful")
        if d.get("bad_feedback"):
            st.dataframe(pd.DataFrame(d["bad_feedback"]), use_container_width=True)
        else:
            st.success("No answers have been marked not helpful.")
        section("Unanswered questions", "Questions the assistant refused. These point to missing documents.")
        u_r = requests.get(f"{api}/admin/unanswered", headers=headers)
        if u_r.status_code == 200 and u_r.json():
            st.dataframe(pd.DataFrame(u_r.json()), use_container_width=True)
        else:
            st.success("No unanswered questions.")

    with t_runs:
        section("Recent questions")
        if d.get("recent_runs"):
            st.dataframe(pd.DataFrame(d["recent_runs"]), use_container_width=True)
            run_id = st.selectbox("See the steps of a question", [x["id"] for x in d["recent_runs"]])
            rr = requests.get(f"{api}/admin/run/{run_id}", headers=headers)
            if rr.status_code == 200:
                detail = rr.json()
                st.markdown(f"**Answer:** {detail['answer']}")
                st.text("\n".join(f"{i}. {s}" for i, s in enumerate(detail["steps"], 1)))
            export = requests.get(f"{api}/admin/runs", headers=headers)
            if export.status_code == 200:
                st.download_button("Export all questions as CSV",
                                   pd.DataFrame(export.json()).to_csv(index=False),
                                   "runs.csv", "text/csv")
        else:
            st.info("No questions have been asked yet.")