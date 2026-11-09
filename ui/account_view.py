"""Profile menu in the sidebar, plus the account pages: profile, settings, password, help."""
import re

import requests
import streamlit as st

from brand import (AMBER, GREEN, INDIGO, TEAL, badge, esc, initials, page_header, section,
                   stat_strip)

DEPARTMENTS = ["HR", "IT", "Finance", "Legal", "Security", "Operations"]
ROW_CHOICES = [50, 100, 250, 500]

MENU = [("👤  My profile", "profile"), ("⚙️  Settings", "settings"),
        ("🔑  Change password", "password"), ("💡  Help and about", "help")]

ROLE_TEXT = {
    "employee": "You can ask questions and read documents marked Public or Internal.",
    "admin": ("You can search every document, upload new documents and versions, request "
              "archive or revoke, approve requests made by other admins, and see the dashboard."),
}
DEPT_ROLE_TEXT = ("You can read Public and Internal documents, plus the Confidential and "
                  "Restricted documents of your own department.")

ACCOUNT_CSS = """
.st-key-profile_menu{margin:.9rem 0 .5rem 0;}
.st-key-profile_menu button{width:100%;min-height:3.6rem;justify-content:flex-start;gap:.7rem;text-align:left;padding:.7rem .8rem;border-radius:12px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12);color:#fff;}
.st-key-profile_menu button:hover{background:rgba(255,255,255,.14);border-color:#F5B31B;color:#fff;}
.st-key-profile_menu button::before{content:"__INITIALS__";flex:0 0 36px;height:36px;border-radius:50%;background:#F5B31B;color:#0B1B3A;font-weight:700;display:flex;align-items:center;justify-content:center;}
.st-key-profile_menu button p{margin:0;font-weight:600;line-height:1.25;color:#fff;text-align:left;}
.st-key-profile_menu button p::after{content:"__ROLE__";display:block;font-weight:400;font-size:.8rem;color:#A9B6D3;}
.st-key-profile_menu [data-testid="stIconMaterial"]{margin-left:auto;}
[class*="st-key-nav_"] button{background:transparent !important;border:1px solid transparent !important;justify-content:flex-start;padding:.6rem .8rem;border-radius:10px;font-weight:500;}
[class*="st-key-nav_"] button:hover{background:rgba(255,255,255,.09) !important;color:#fff;}
[class*="st-key-nav_"] button[kind="primary"],[class*="st-key-nav_"] [data-testid="stBaseButton-primary"]{background:#4F46E5 !important;color:#fff;font-weight:600;}
.cw-acct-head{display:flex;align-items:center;gap:.9rem;margin-bottom:.4rem;}
.cw-acct-head .cw-avatar{width:48px;height:48px;font-size:1.1rem;}
.cw-acct-head .n{font-weight:700;font-size:1.1rem;color:#0B1B3A;}
.cw-acct-head .u{color:#64748B;font-size:.85rem;margin-bottom:.2rem;}
.cw-facts{background:#fff;border:1px solid #E3E7F0;border-radius:14px;padding:.4rem 1.2rem;margin:.4rem 0 1rem 0;}
.cw-fact{display:flex;gap:1rem;padding:.7rem 0;border-bottom:1px solid #EEF1F7;}
.cw-fact:last-child{border-bottom:none;}
.cw-fact .k{flex:0 0 9rem;color:#64748B;}
.cw-fact .v{color:#0B1B3A;font-weight:600;}
"""


def inject_account_css(name, role):
    ini = re.sub(r"[^A-Za-z0-9]", "", initials(name))[:2] or "?"
    role_text = re.sub(r"[^A-Za-z ]", "", str(role)).capitalize()
    css = ACCOUNT_CSS.replace("__INITIALS__", ini).replace("__ROLE__", role_text)
    css = "\n".join(line for line in css.splitlines() if line.strip())
    st.markdown("<style>" + css + "</style>", unsafe_allow_html=True)


def _keyed_container(key):
    try:
        return st.container(key=key)
    except TypeError:                         # older Streamlit: no keyed containers
        return st.container()


def _stretch_popover(label):
    try:
        return st.popover(label, use_container_width=True)
    except TypeError:
        return st.popover(label)


def _menu_body(name, role, username, sign_out):
    sub = f"@{esc(username)}" if username else ""
    st.markdown(f'<div class="cw-acct-head"><div class="cw-avatar">{esc(initials(name))}</div>'
                f'<div><div class="n">{esc(name)}</div><div class="u">{sub}</div>'
                f'{badge(str(role).capitalize(), "info")}</div></div>', unsafe_allow_html=True)
    st.divider()
    for label, view in MENU:
        if st.button(label, key=f"acct_{view}", use_container_width=True):
            st.session_state.account_view = view
            st.rerun()
    st.divider()
    if st.button("↩  Sign out", key="acct_signout", use_container_width=True, type="primary"):
        sign_out()


if hasattr(st, "dialog"):
    @st.dialog("Your account")
    def _account_dialog(name, role, username, sign_out):
        _menu_body(name, role, username, sign_out)


def profile_menu(name, role, username, sign_out):
    """The profile card in the sidebar. Clicking it opens the account menu."""
    with _keyed_container("profile_menu"):
        if hasattr(st, "dialog"):
            if st.button(name, key="profile_btn", use_container_width=True):
                _account_dialog(name, role, username, sign_out)
        else:
            with _stretch_popover(name):
                _menu_body(name, role, username, sign_out)


# ---------------- pages ----------------
def _facts(rows):
    cells = "".join(f'<div class="cw-fact"><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div></div>'
                    for k, v in rows)
    st.markdown(f'<div class="cw-facts">{cells}</div>', unsafe_allow_html=True)


def profile_page(headers, api):
    page_header("My profile", "Who you are in the system and what you can reach.")
    role = st.session_state.get("role", "")
    docs = requests.get(f"{api}/documents", headers=headers)
    chats = requests.get(f"{api}/conversations", headers=headers)
    n_docs = len(docs.json()) if docs.status_code == 200 else 0
    n_chats = len(chats.json()) if chats.status_code == 200 else 0
    stat_strip([
        {"label": "Role", "value": str(role).capitalize(), "color": INDIGO},
        {"label": "Documents you can search", "value": n_docs, "color": TEAL},
        {"label": "Saved chats", "value": n_chats, "color": AMBER}])
    _facts([("Name", st.session_state.get("name", "")),
            ("Username", st.session_state.get("username") or "not available"),
            ("Role", str(role).capitalize())])
    section("What your role allows")
    st.write(ROLE_TEXT.get(role, DEPT_ROLE_TEXT))


def settings_page(headers, api, error_text):
    page_header("Settings", "These choices are kept for this session.")
    section("Ask page")
    starters = st.toggle("Show starter questions in an empty chat",
                         value=st.session_state.get("pref_starters", True))
    st.session_state.pref_starters = starters
    st.caption("Show sources and technical details can be switched on in the sidebar.")

    section("Documents page")
    current = st.session_state.get("doc_dept", "All")
    options = ["All"] + DEPARTMENTS
    dept = st.selectbox("Department shown first", options,
                        index=options.index(current) if current in options else 0)
    st.session_state.doc_dept = dept
    rows = st.selectbox("Documents shown in the list", ROW_CHOICES,
                        index=ROW_CHOICES.index(st.session_state.get("pref_rows", 500)))
    st.session_state.pref_rows = rows

    section("Privacy", "Your chats are stored so you can reopen them. You can remove them at any time.")
    chats = requests.get(f"{api}/conversations", headers=headers)
    items = chats.json() if chats.status_code == 200 else []
    if st.session_state.get("flash_settings"):
        st.success(st.session_state.pop("flash_settings"))
    confirm = st.checkbox(f"I understand this deletes all {len(items)} of my saved chats",
                          disabled=not items)
    if st.button("Delete all my chats", disabled=not (items and confirm)):
        for c in items:
            requests.delete(f"{api}/conversations/{c['id']}", headers=headers)
        st.session_state.messages = []
        st.session_state.conversation_id = None
        st.session_state.flash_settings = "Your chats were deleted."
        st.rerun()


def password_page(headers, api, error_text):
    page_header("Change password", "Choose a new password for your account.")
    with st.form("password_form"):
        old = st.text_input("Current password", type="password")
        new = st.text_input("New password", type="password", help="At least 8 characters.")
        again = st.text_input("Repeat the new password", type="password")
        go = st.form_submit_button("Update password", use_container_width=True)
    if not go:
        return
    if not old or not new or not again:
        st.error("Fill in all three fields.")
    elif len(new) < 8:
        st.error("The new password must have at least 8 characters.")
    elif new != again:
        st.error("The two new passwords do not match.")
    elif new == old:
        st.error("The new password must be different from the current one.")
    else:
        r = requests.post(f"{api}/change-password", headers=headers,
                          json={"old_password": old, "new_password": new})
        if r.status_code == 200:
            st.success("Your password was changed. Use it the next time you sign in.")
        else:
            st.error(error_text(r))


def help_page():
    page_header("Help and about", "How to get good answers from CiteWise.")
    section("Asking questions")
    st.markdown(
        "- Ask in plain words, for example *How many days of annual leave do I get?*\n"
        "- Name the country or policy when it matters, for example *annual leave in India*.\n"
        "- To compare, name both, for example *Compare annual leave for the US and Singapore*.\n"
        "- Follow-up questions work. Ask *and for contractors?* after an answer.")
    section("Sources and refusals")
    st.markdown(
        "- Tick **Show sources and technical details** in the sidebar to see the document, "
        "version and page behind each answer.\n"
        "- If the documents do not contain the answer, CiteWise says so instead of guessing. "
        "Try the policy name, or ask an admin whether the document has been added.\n"
        "- Only the current version of a document is used. Superseded, archived and revoked "
        "documents never appear in answers.")
    section("About")
    _facts([("Product", "CiteWise"), ("Tagline", "Answers you can trace."),
            ("Access", "Your role decides which documents you can search.")])