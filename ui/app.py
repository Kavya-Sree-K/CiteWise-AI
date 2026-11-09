import os

import pandas as pd
import requests
import streamlit as st

from brand import (APP_NAME, brand_html, badge, esc, hide_sidebar, inject_css, page_header,
                   section, sign_in_hero, stat_strip, user_card, INDIGO, TEAL, AMBER, GREEN)
from chat_view import chat_page
from dashboard_view import dashboard_page
from documents_view import documents_page
from account_view import (help_page, inject_account_css, password_page, profile_menu,
                          profile_page, settings_page)

API = os.getenv("API_URL", "http://127.0.0.1:8000")
DEPARTMENTS = ["HR", "IT", "Finance", "Legal", "Security", "Operations"]
SENSITIVITY = ["Public", "Internal", "Confidential", "Restricted"]

st.set_page_config(page_title=APP_NAME, page_icon="📚", layout="wide",
                   initial_sidebar_state="expanded")
inject_css()

if "token" not in st.session_state:
    st.session_state.token = None
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.history = []

STARTERS = ["How many days of annual leave do I get?",
            "How do I apply for leave?",
            "Compare annual leave for the US and Singapore",
            "What is the security desk extension?"]


def error_text(r):
    try:
        return r.json().get("detail", "Error")
    except ValueError:
        return f"Server error ({r.status_code}). Check the backend window."


def set_flash(kind, message):
    st.session_state.flash = (kind, message)


def show_flash():
    if st.session_state.get("flash"):
        kind, message = st.session_state.pop("flash")
        (st.success if kind == "ok" else st.error)(message)


# ---------------- sign in ----------------
def login_page():
    hide_sidebar()
    left, right = st.columns([1.25, 1], gap="large")
    with left:
        st.markdown(sign_in_hero(), unsafe_allow_html=True)
    with right:
        st.markdown('<div class="cw-signin" style="margin-top:3rem"><h2>Sign in</h2>'
                    '<p>Use the account your company gave you.</p></div>',
                    unsafe_allow_html=True)
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            go = st.form_submit_button("Sign in", use_container_width=True)
        if go:
            if not username.strip() or not password:
                st.error("Enter your username and password.")
                return
            try:
                with st.spinner("Signing in..."):
                    r = requests.post(f"{API}/login",
                                      json={"username": username, "password": password})
            except requests.exceptions.RequestException:
                st.error("The server is not reachable. Start the backend and try again.")
                return
            if r.status_code == 200:
                d = r.json()
                st.session_state.token = d["token"]
                st.session_state.name = d["name"]
                st.session_state.role = d["role"]
                st.session_state.username = d.get("username") or username.strip()
                st.rerun()
            else:
                st.error(error_text(r))


# ---------------- documents (everyone) ----------------
# def documents_page(headers):
#     page_header("My documents", "The documents your role is allowed to search.")
#     dept = st.selectbox("Department", ["All"] + DEPARTMENTS)
#     params = {} if dept == "All" else {"department": dept}
#     r = requests.get(f"{API}/documents", headers=headers, params=params)
#     if r.status_code != 200:
#         st.error(error_text(r))
#         return
#     rows = r.json()
#     df = pd.DataFrame(rows)
#     stat_strip([
#         {"label": "Documents", "value": len(rows), "color": INDIGO},
#         {"label": "Departments", "value": df["department"].nunique() if rows else 0, "color": TEAL},
#         {"label": "Pages", "value": int(df["pages"].sum()) if rows else 0, "color": AMBER}])
#     if rows:
#         st.dataframe(df, use_container_width=True)
#     else:
#         st.info("No documents match this filter.")


# ---------------- document management (admin) ----------------
def request_action(headers, doc_id, action, reason):
    if len(reason.strip()) < 3:
        st.error("Give a reason of at least 3 characters.")
        return
    r = requests.post(f"{API}/admin/documents/{doc_id}/request", headers=headers,
                      json={"action": action, "reason": reason})
    if r.status_code == 200:
        set_flash("ok", f"The {action} request was sent to the approval queue.")
    else:
        set_flash("err", error_text(r))
    st.rerun()


def management_page(headers):
    page_header("Manage documents", "Upload documents and versions, and request archive or revoke.")
    show_flash()
    docs_r = requests.get(f"{API}/admin/all-documents", headers=headers)
    if docs_r.status_code != 200:
        st.error(error_text(docs_r))
        return
    docs = docs_r.json()
    t_up, t_all, t_life = st.tabs(["Upload", "All documents", "Preview and lifecycle"])

    with t_up:
        mode = st.radio("This upload is",
                        ["A new document", "A new version of an existing document"],
                        horizontal=True)
        title, base_id = "", None
        if mode == "A new document":
            title = st.text_input("Title")
        else:
            active = [d for d in docs if d["status"] == "active"]
            choice = st.selectbox(
                "Which active document does it replace?", active,
                format_func=lambda d: f"{d['id']} - {d['title']} (v{d['version']})")
            base_id = choice["id"] if choice else None
            st.caption("A new version keeps the title and department of the document it replaces.")

        c1, c2, c3 = st.columns(3)
        department = c1.selectbox("Department", DEPARTMENTS)
        owner = c2.text_input("Owner")
        sensitivity = c3.selectbox("Sensitivity", SENSITIVITY)
        effective = st.date_input("Effective date")
        up = st.file_uploader("File (PDF, DOCX, TXT or CSV, up to 10 MB)",
                              type=["pdf", "docx", "txt", "csv"])

        if st.button("Upload document", type="primary"):
            if not up:
                st.error("Choose a file.")
            elif not owner.strip():
                st.error("Enter the owner.")
            elif mode == "A new document" and not title.strip():
                st.error("Enter a title.")
            elif mode != "A new document" and base_id is None:
                st.error("There is no active document to replace.")
            else:
                data = {"department": department, "owner": owner,
                        "sensitivity": sensitivity, "effective_date": str(effective),
                        "title": title}
                if base_id:
                    data["new_version_of"] = base_id
                with st.spinner("Uploading..."):
                    r = requests.post(f"{API}/admin/upload", headers=headers,
                                      data=data, files={"file": (up.name, up.getvalue())},
                                      timeout=120)
                if r.status_code == 200:
                    st.success(r.json()["message"])
                else:
                    st.error(error_text(r))

    with t_all:
        df = pd.DataFrame(docs)
        counts = df["status"].value_counts() if docs else {}
        stat_strip([
            {"label": "Documents", "value": len(docs), "color": INDIGO},
            {"label": "Active", "value": int(counts.get("active", 0)), "color": GREEN},
            {"label": "Superseded", "value": int(counts.get("superseded", 0)), "color": AMBER}])
        if st.button("Refresh table"):
            st.rerun()
        st.dataframe(df, use_container_width=True)
        st.download_button("Export documents as CSV", df.to_csv(index=False),
                           "documents.csv", "text/csv")

    with t_life:
        chosen = st.selectbox(
            "Choose a document", docs, key="manage_doc",
            format_func=lambda d: f"{d['id']} - {d['title']} (v{d['version']}, {d['status']})")
        if chosen:
            if st.button("Preview first page"):
                p = requests.get(f"{API}/admin/documents/{chosen['id']}/preview", headers=headers)
                if p.status_code == 200:
                    st.caption(f"{p.json()['pages']} page(s) found. First page:")
                    st.text(p.json()["text"])
                else:
                    st.error(error_text(p))
            reason = st.text_input("Reason for archive or revoke (required)", key="reason")
            a, b, _ = st.columns([1, 1, 5])
            if a.button("Request archive"):
                request_action(headers, chosen["id"], "archive", reason)
            if b.button("Request revoke"):
                request_action(headers, chosen["id"], "revoke", reason)
            st.caption("Archive retires a document normally. Revoke withdraws it immediately "
                       "(for example, it was wrong). Both stop it from being used in answers "
                       "once another admin approves.")


# ---------------- approval queue (admin) ----------------
def decide(headers, approval_id, decision, comment):
    r = requests.post(f"{API}/admin/approvals/{approval_id}/decide", headers=headers,
                      json={"decision": decision, "comment": comment})
    if r.status_code == 200:
        set_flash("ok", r.json()["result"])
    else:
        set_flash("err", error_text(r))
    st.rerun()


def approvals_page(headers):
    page_header("Approval queue", "A second admin must approve archive and revoke requests.")
    show_flash()
    r = requests.get(f"{API}/admin/approvals", headers=headers)
    if r.status_code != 200:
        st.error(error_text(r))
        return
    items = r.json()
    pending = [a for a in items if a["status"] == "pending"]
    done = [a for a in items if a["status"] != "pending"]
    stat_strip([
        {"label": "Waiting for review", "value": len(pending), "color": AMBER},
        {"label": "Decided", "value": len(done), "color": GREEN}])

    section("Waiting for review")
    if not pending:
        st.info("Nothing is waiting.")
    for a in pending:
        with st.container(border=True):
            kind = "bad" if a["action"] == "revoke" else "warn"
            st.markdown(f"{badge(a['action'].capitalize(), kind)} &nbsp; **{esc(a['document'])}** "
                        f"(version {esc(a['version'])}, currently {esc(a['doc_status'])})",
                        unsafe_allow_html=True)
            st.caption(f"Requested by {a['requested_by']} at {a['created']}. Reason: {a['reason']}")
            comment = st.text_input("Comment (optional)", key=f"c{a['id']}")
            x, y, _ = st.columns([1, 1, 5])
            if x.button("Approve", key=f"ok{a['id']}", type="primary"):
                decide(headers, a["id"], "approve", comment)
            if y.button("Reject", key=f"no{a['id']}"):
                decide(headers, a["id"], "reject", comment)

    section("History")
    if done:
        st.dataframe(pd.DataFrame(done)[["id", "action", "document", "status",
                                         "requested_by", "reviewed_by", "comment",
                                         "decided"]], use_container_width=True)
    else:
        st.info("No decisions yet.")

    section("Notifications", "Messages sent by the mock email service")
    n = requests.get(f"{API}/admin/notifications", headers=headers)
    if n.status_code == 200 and n.json():
        st.dataframe(pd.DataFrame(n.json()), use_container_width=True)
    else:
        st.info("No notifications yet.")


# ---------------- main ----------------
PAGES = [("💬", "Ask", "Ask", False), ("📄", "Documents", "Documents", False),
         ("🗂️", "Manage documents", "Document management", True),
         ("✅", "Approval queue", "Approval queue", True),
         ("📊", "Dashboard", "Dashboard", True)]
ACCOUNT_VIEWS = ("profile", "settings", "password", "help")


def go_to(page):
    st.session_state.page = page
    st.session_state.pop("account_view", None)


def sign_out():
    try:
        requests.post(f"{API}/logout", headers={"X-Token": st.session_state.token}, timeout=3)
    except requests.exceptions.RequestException:
        pass
    for key in list(st.session_state.keys()):
        try:
            del st.session_state[key]
        except Exception:
            pass
    st.session_state.token = None
    st.rerun()


def starter_questions():
    st.markdown("**Try asking**")
    cols = st.columns(2)
    for i, q in enumerate(STARTERS):
        if cols[i % 2].button(q, key=f"starter{i}", use_container_width=True):
            st.session_state.pending_question = q
            st.rerun()


if not st.session_state.token:
    login_page()
else:
    headers = {"X-Token": st.session_state.token}
    is_admin = st.session_state.role == "admin"
    name, role = st.session_state.name, st.session_state.role
    inject_account_css(name, role)
    page = st.session_state.get("page", "Ask")
    if page not in [key for _, _, key, _ in PAGES] or (page != "Ask" and not is_admin and
            page in [key for _, _, key, admin_only in PAGES if admin_only]):
        page = "Ask"
    view = st.session_state.get("account_view")

    with st.sidebar:
        st.markdown(brand_html(34, on_dark=True), unsafe_allow_html=True)
        profile_menu(name, role, st.session_state.get("username", ""), sign_out)
        for icon, label, key, admin_only in PAGES:
            if admin_only and not is_admin:
                continue
            st.button(f"{icon}  {label}", key=f"nav_{key.replace(' ', '_')}",
                      use_container_width=True, on_click=go_to, args=(key,),
                      type="primary" if (page == key and not view) else "secondary")
        if is_admin:
            try:
                ap = requests.get(f"{API}/admin/approvals", headers=headers, timeout=3)
                waiting = sum(1 for a in ap.json() if a["status"] == "pending") if ap.status_code == 200 else 0
            except (requests.exceptions.RequestException, ValueError):
                waiting = 0
            if waiting:
                st.markdown(f'<div class="cw-pending">{waiting} approval(s) waiting for review</div>',
                            unsafe_allow_html=True)
        st.checkbox("Show sources and technical details", key="show_details",
                    help="Off: only the friendly answer. On: sources, pages, "
                         "passages and how the answer was produced.")
        st.divider()

    if view in ACCOUNT_VIEWS:
        if view == "profile":
            profile_page(headers, API)
        elif view == "settings":
            settings_page(headers, API, error_text)
        elif view == "password":
            password_page(headers, API, error_text)
        else:
            help_page()
    elif page == "Ask":
        chat_page(headers)
        if st.session_state.get("pref_starters", True) and not st.session_state.get("messages"):
            starter_questions()
    elif page == "Documents":
        documents_page(headers, API, error_text)
    elif page == "Document management":
        management_page(headers)
    elif page == "Approval queue":
        approvals_page(headers)
    else:
        dashboard_page(headers, API, error_text)