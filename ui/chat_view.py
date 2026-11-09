import os
import re
import textwrap

import pandas as pd
import requests
import streamlit as st
from datetime import datetime, timezone

API = os.getenv("API_URL", "http://127.0.0.1:8000")
CITE_MARK = re.compile(r"\s*\[\d+\]")
DANGLING = re.compile(r"\s*\b(?:according to|as stated in|as per)\s*(?=[.,;]|$)", re.I)


def error_text(r):
    try:
        return r.json().get("detail", "Error")
    except ValueError:
        return f"Server error ({r.status_code}). Check the backend window."


def flow_dot(steps):
    """Turn a list of steps into a flowchart (Graphviz text)."""
    direction = "LR" if len(steps) <= 4 else "TB"
    lines = [f'digraph {{ rankdir={direction}; '
             'node [shape=box, style="rounded,filled", fillcolor="#E3F4F4", '
             'color="#0F8B8D", fontname="Helvetica", fontsize=11]; edge [color="#5F6B7A"];']
    for i, step in enumerate(steps):
        text = textwrap.fill(re.sub(r"\[\d+\]", "", step).strip(), 26)
        text = text.replace('"', "'").replace("\n", "\\n")
        lines.append(f'n{i} [label="{i + 1}. {text}"];')
        if i:
            lines.append(f"n{i - 1} -> n{i};")
    lines.append("}")
    return "\n".join(lines)


def send_feedback(headers, message, rating):
    r = requests.post(f"{API}/feedback", headers=headers,
                      json={"run_id": message["run_id"], "rating": rating})
    if r.status_code == 200:
        message["rated"] = True
    st.rerun()


def show_answer(m, headers, idx):
    """Friendly mode (default): answer, comparison table, flow chart, 'Good to know'
    points and follow-up buttons. Sources, passages, model usage and the processing
    steps appear only when 'Show sources and technical details' is ticked."""
    technical = st.session_state.get("show_details", False)
    status = m.get("status")

    def clean(t):
        if technical:
            return t
        t = DANGLING.sub("", CITE_MARK.sub("", t))
        return re.sub(r"\s+([.,;])", r"\1", t).strip()

    text = clean(m["text"])

    if status == "insufficient_evidence":
        st.info(text)
        if technical:
            st.caption("Tip: include the policy or document name, or open the "
                       "Documents page to see what you can access.")
    elif status == "error":
        st.error(text)
    else:
        st.markdown(text)

    if m.get("comparison"):
        table = pd.DataFrame(m["comparison"]).rename(
            columns={"label": "Item", "value": "Value", "source": "Source"})
        if not technical:
            table = table.drop(columns=["Source"])
        st.table(table.set_index("Item"))

    if m.get("procedure"):
        st.markdown("**Step by step**")
        st.graphviz_chart(flow_dot(m["procedure"]))

    if m.get("details"):
        st.markdown("**Good to know**")
        for d in m["details"]:
            st.markdown(f"- {clean(d)}")

    if technical:
        sources = m.get("sources", [])
        used = [(i, s) for i, s in enumerate(sources, 1) if s.get("used", True)]
        other = [(i, s) for i, s in enumerate(sources, 1) if not s.get("used", True)]
        if used:
            st.markdown("**Sources**")
            for i, s in used:
                st.caption(f"[{i}] {s['title']} · version {s['version']} · page {s['page']}")
            with st.expander("Show the passages used"):
                for i, s in used:
                    st.markdown(f"**[{i}] {s['title']}** (page {s['page']})")
                    if s.get("snippet"):
                        st.write(f"> {s['snippet']}")
        if other:
            with st.expander("Other documents that were checked"):
                for i, s in other:
                    st.caption(f"[{i}] {s['title']} · version {s['version']} · page {s['page']}")
        if m.get("input_tokens") or m.get("output_tokens"):
            st.caption(f"Model usage: {m.get('input_tokens', 0)} tokens in, "
                       f"{m.get('output_tokens', 0)} tokens out, "
                       f"cost ${m.get('cost_usd') or 0:.4f}")
        if m.get("steps"):
            with st.expander("How this answer was produced"):
                st.text("\n".join(f"{i}. {x}" for i, x in enumerate(m["steps"], 1)))

    if m.get("follow_ups") and m.get("run_id"):
        st.caption("You could also ask:")
        for j, q in enumerate(m["follow_ups"]):
            if st.button(q, key=f"fu{idx}_{j}"):
                st.session_state.pending_question = q
                st.rerun()

    if m.get("run_id") and not m.get("rated"):
        c1, c2, _ = st.columns([1, 1, 8])
        if c1.button("👍", key=f"up{idx}", help="Helpful"):
            send_feedback(headers, m, 1)
        if c2.button("👎", key=f"down{idx}", help="Not helpful"):
            send_feedback(headers, m, -1)
    elif m.get("rated"):
        st.caption("Thanks for your feedback.")


def to_message(d):
    """Turn an API answer (or a stored message) into the dict the page displays."""
    if d.get("role") == "user":
        return {"role": "user", "text": d["text"]}
    return {"role": "assistant", "text": d.get("text") or d.get("answer", ""),
            "status": d.get("status"), "sources": d.get("sources") or [],
            "steps": d.get("steps") or [], "details": d.get("details") or [],
            "comparison": d.get("comparison") or [], "procedure": d.get("procedure") or [],
            "follow_ups": d.get("follow_ups") or [], "run_id": d.get("run_id"),
            "input_tokens": d.get("input_tokens", 0), "output_tokens": d.get("output_tokens", 0),
            "cost_usd": d.get("cost_usd", 0.0)}


def open_conversation(headers, conversation_id):
    r = requests.get(f"{API}/conversations/{conversation_id}", headers=headers)
    if r.status_code == 200:
        st.session_state.conversation_id = conversation_id
        st.session_state.messages = [to_message(m) for m in r.json()["messages"]]
    else:
        st.sidebar.error(error_text(r))


CHAT_CSS = """
.cw-chat-group{margin:.9rem 0 .3rem 0;color:#A9B6D3;font-size:.8rem;font-weight:600;}
[data-testid="stSidebar"] .stButton button{background:rgba(255,255,255,.07);color:#fff;border:1px solid rgba(255,255,255,.14);}
[data-testid="stSidebar"] .stButton button:hover{background:rgba(255,255,255,.15);border-color:#F5B31B;color:#fff;}
[data-testid="stSidebar"] .stButton button p{color:#fff;}
[data-testid="stSidebar"] .stButton button[kind="primary"],[data-testid="stSidebar"] .stButton [data-testid="stBaseButton-primary"]{background:rgba(79,70,229,.45);border-color:#818CF8;}
[class*="st-key-conv_"] button{justify-content:flex-start;text-align:left;padding:.45rem .7rem;min-height:2.4rem;}
[class*="st-key-conv_"] button p{margin:0;white-space:nowrap;font-weight:500;}
[class*="st-key-del_"] button{min-height:2.4rem;padding:0;background:transparent !important;border:1px solid transparent !important;opacity:.75;}
[class*="st-key-del_"] button:hover{opacity:1;background:rgba(244,63,94,.18) !important;border-color:rgba(244,63,94,.5) !important;}
"""


def _age_group(updated):
    """Group chats by age. The server stores UTC times, so this does not depend on your time zone."""
    try:
        t = datetime.fromisoformat(str(updated))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        hours = (datetime.now(timezone.utc) - t).total_seconds() / 3600
    except ValueError:
        return "Earlier"
    if hours < 24:
        return "Last 24 hours"
    if hours < 24 * 7:
        return "Last 7 days"
    return "Older"


def delete_chat(headers, conversation_id):
    r = requests.delete(f"{API}/conversations/{conversation_id}", headers=headers)
    if r.status_code != 200:
        return
    if st.session_state.get("conversation_id") == conversation_id:   # the open chat was deleted
        st.session_state.conversation_id = None
        st.session_state.messages = []
    try:
        st.toast("Chat deleted.")
    except AttributeError:                       # older Streamlit
        pass


def chats_sidebar(headers):
    """The user's saved chats, newest first. Each row has its own delete button on the right."""
    st.markdown("<style>" + "\n".join(l for l in CHAT_CSS.splitlines() if l.strip()) + "</style>",
                unsafe_allow_html=True)
    st.sidebar.divider()
    st.sidebar.subheader("Your chats")
    if st.sidebar.button("➕ New chat", use_container_width=True):
        st.session_state.conversation_id = None
        st.session_state.messages = []
        st.rerun()
    r = requests.get(f"{API}/conversations", headers=headers)
    if r.status_code != 200:
        return
    current = st.session_state.get("conversation_id")
    last_group = None
    for c in r.json()[:20]:
        group = _age_group(c.get("updated"))
        if group != last_group:
            st.sidebar.markdown(f'<div class="cw-chat-group">{group}</div>', unsafe_allow_html=True)
            last_group = group
        title = c["title"]
        short = title if len(title) <= 26 else title[:25].rstrip() + "…"
        open_col, delete_col = st.sidebar.columns([6, 1])
        when = str(c.get("updated", ""))[:16]
        if open_col.button(short, key=f"conv_{c['id']}", use_container_width=True,
                           help=f"{title}\nLast activity {when} UTC",
                           type="primary" if c["id"] == current else "secondary"):
            open_conversation(headers, c["id"])
            st.rerun()
        delete_col.button("🗑", key=f"del_{c['id']}", help="Delete this chat",
                          on_click=delete_chat, args=(headers, c["id"]))


def chat_page(headers):
    st.header("Ask a question")
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("conversation_id", None)
    chats_sidebar(headers)

    for idx, m in enumerate(st.session_state.messages):
        with st.chat_message(m["role"]):
            if m["role"] == "assistant":
                show_answer(m, headers, idx)
            else:
                st.write(m["text"])

    typed = st.chat_input("Ask about company policies", max_chars=500)
    question = st.session_state.pop("pending_question", None) or typed
    if question:
        with st.spinner("Searching your documents and writing the answer..."):
            r = requests.post(f"{API}/ask", headers=headers, timeout=300,
                              json={"question": question,
                                    "conversation_id": st.session_state.conversation_id})
        st.session_state.messages.append({"role": "user", "text": question})
        if r.status_code == 200:
            d = r.json()
            st.session_state.conversation_id = d.get("conversation_id")
            st.session_state.messages.append(to_message(d))
        else:
            st.session_state.messages.append(
                {"role": "assistant", "text": error_text(r), "status": "error"})
        st.rerun()