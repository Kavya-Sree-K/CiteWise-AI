"""CiteWise look and feel: name, logo, colours, CSS and small HTML components.

Only appearance lives here. Answer content and layout stay in chat_view.py.
"""
import html

import streamlit as st

APP_NAME = "CiteWise"
TAGLINE = "Answers you can trace."

INK = "#0B1B3A"
INDIGO = "#4F46E5"
TEAL = "#14B8A6"
AMBER = "#F5B31B"      # the highlighter: used for citations and key marks
CORAL = "#F43F5E"
GREEN = "#10B981"
SLATE = "#64748B"


def esc(value):
    """Escape text for HTML. The dollar sign is escaped so Markdown never reads it as maths."""
    return html.escape(str(value)).replace("$", "&#36;")


def logo_svg(size=40):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="{size}" '
        f'height="{size}" role="img" aria-label="{APP_NAME} logo">'
        '<rect width="64" height="64" rx="15" fill="#4F46E5"/>'
        '<path d="M20 12h17l9 9v29a3 3 0 0 1-3 3H20a3 3 0 0 1-3-3V15a3 3 0 0 1 3-3z" fill="#fff"/>'
        '<path d="M37 12v9h9z" fill="#C7D2FE"/>'
        '<rect x="23" y="27" width="12" height="3" rx="1.5" fill="#C7D2FE"/>'
        '<rect x="21" y="33" width="22" height="8" rx="2.5" fill="#F5B31B"/>'
        '<rect x="24" y="35.5" width="16" height="3" rx="1.5" fill="#0B1B3A"/>'
        '<rect x="23" y="45" width="12" height="3" rx="1.5" fill="#C7D2FE"/></svg>')


def brand_html(size=36, on_dark=False):
    cls = "cw-brand on-dark" if on_dark else "cw-brand"
    return (f'<div class="{cls}">{logo_svg(size)}'
            f'<span class="cw-brand-name">{APP_NAME}</span></div>')


CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&display=swap');
:root{--ink:#0B1B3A;--indigo:#4F46E5;--teal:#14B8A6;--amber:#F5B31B;--coral:#F43F5E;--green:#10B981;--muted:#64748B;--line:#E3E7F0;--paper:#F6F7FB;}
.stApp{font-family:'Inter',system-ui,-apple-system,'Segoe UI',sans-serif;background:var(--paper);}
.stApp h1,.stApp h2,.stApp h3,.cw-serif{font-family:'Fraunces',Georgia,'Times New Roman',serif;color:var(--ink);letter-spacing:-.015em;font-weight:600;}
#MainMenu,footer,[data-testid="stDeployButton"]{visibility:hidden;height:0;}
header[data-testid="stHeader"]{background:transparent;}
.block-container{padding-top:2.2rem;padding-bottom:4rem;max-width:1240px;}

/* sidebar */
[data-testid="stSidebar"]{background:var(--ink);border-right:none;}
[data-testid="stSidebar"] *{color:#DCE3F2;}
[data-testid="stSidebar"] hr{border-color:rgba(255,255,255,.12);}
[data-testid="stSidebar"] .stButton>button{background:rgba(255,255,255,.07);color:#fff;border:1px solid rgba(255,255,255,.14);width:100%;justify-content:flex-start;}
[data-testid="stSidebar"] .stButton>button:hover{background:rgba(255,255,255,.15);border-color:var(--amber);color:#fff;transform:none;box-shadow:none;}
[data-testid="stSidebar"] [role="radiogroup"]{gap:.2rem;}
[data-testid="stSidebar"] label[data-baseweb="radio"]{padding:.55rem .8rem;border-radius:10px;width:100%;margin:0;}
[data-testid="stSidebar"] label[data-baseweb="radio"]>div:first-child{display:none;}
[data-testid="stSidebar"] label[data-baseweb="radio"]:hover{background:rgba(255,255,255,.08);}
[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked){background:var(--indigo);}
[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) *{color:#fff;font-weight:600;}

/* profile dropdown */
.cw-profile-dropdown {
    padding-top: 0.5rem;
    padding-bottom: 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
}

.cw-profile-dropdown .stButton > button {
    background: transparent;
    border: none;
    color: #DCE3F2; /* Use existing sidebar text color */
    width: 100%;
    justify-content: flex-start;
    padding: 0.5rem 0.8rem; /* Match radio button padding */
    border-radius: 10px; /* Match existing border-radius */
}

.cw-profile-dropdown .stButton > button:hover {
    background: rgba(255,255,255,.08); /* Match radio button hover */
    color: #fff;
    border-color: transparent; /* Ensure no border appears on hover */
    box-shadow: none;
    transform: none;
}
/* end profile dropdown */

/* buttons, inputs, tables */
.stButton>button,[data-testid="stDownloadButton"] button,[data-testid="stFormSubmitButton"] button{border-radius:10px;font-weight:600;border:1px solid var(--line);transition:border-color .15s,box-shadow .15s;}
.stButton>button:hover,[data-testid="stDownloadButton"] button:hover{border-color:var(--indigo);color:var(--indigo);box-shadow:0 2px 10px rgba(79,70,229,.14);}
button[kind="primary"],[data-testid="stBaseButton-primary"],[data-testid="stFormSubmitButton"] button{background:var(--indigo);color:#fff;border:1px solid var(--indigo);}
button[kind="primary"]:hover,[data-testid="stBaseButton-primary"]:hover,[data-testid="stFormSubmitButton"] button:hover{background:#4338CA;color:#fff;border-color:#4338CA;}
[data-baseweb="input"],[data-baseweb="select"]>div,[data-baseweb="textarea"]{border-radius:10px !important;}
[data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:12px;overflow:hidden;}
[data-testid="stExpander"]{border:1px solid var(--line);border-radius:12px;background:#fff;}
[data-testid="stAlert"]{border-radius:12px;}
[data-testid="stForm"]{background:#fff;border:1px solid var(--line);border-radius:16px;padding:1.4rem;}
.stTabs [data-baseweb="tab-list"]{gap:.3rem;border-bottom:1px solid var(--line);}
.stTabs [data-baseweb="tab"]{padding:.6rem 1rem;font-weight:600;color:var(--muted);}
.stTabs [aria-selected="true"]{color:var(--indigo);}
[data-testid="stChatMessage"]{background:#fff;border:1px solid var(--line);border-radius:14px;padding:1rem 1.2rem;margin-bottom:.7rem;}

/* brand */
.cw-brand{display:flex;align-items:center;gap:.7rem;}
.cw-brand-name{font-family:'Fraunces',Georgia,serif;font-weight:700;font-size:1.45rem;color:var(--ink);letter-spacing:-.02em;}
.cw-brand.on-dark .cw-brand-name{color:#fff;}

/* page header and sections */
.cw-head{margin:0 0 1.4rem 0;}
.cw-head h1{margin:0;font-size:2.1rem;line-height:1.15;}
.cw-head p{margin:.35rem 0 0 0;color:var(--muted);font-size:1rem;}
.cw-section{margin:1.6rem 0 .6rem 0;}
.cw-section h3{margin:0;font-size:1.25rem;}
.cw-section p{margin:.15rem 0 0 0;color:var(--muted);font-size:.9rem;}

/* stat strip */
.cw-strip{display:flex;flex-wrap:wrap;background:#fff;border:1px solid var(--line);border-radius:14px;margin:0 0 1rem 0;overflow:hidden;}
.cw-stat{flex:1 1 150px;padding:1rem 1.2rem;border-right:1px solid var(--line);}
.cw-stat:last-child{border-right:none;}
.cw-stat-label{display:flex;align-items:center;gap:.45rem;color:var(--muted);font-size:.85rem;font-weight:500;}
.cw-dot{width:9px;height:9px;border-radius:50%;display:inline-block;}
.cw-stat-value{font-family:'Fraunces',Georgia,serif;font-size:2rem;font-weight:600;color:var(--ink);line-height:1.2;margin-top:.25rem;}
.cw-stat-sub{color:var(--muted);font-size:.8rem;min-height:1.1rem;}

/* badges and sidebar bits */
.cw-badge{display:inline-block;padding:.12rem .6rem;border-radius:999px;font-size:.78rem;font-weight:600;}
.cw-badge.ok{background:#D1FAE5;color:#047857;}
.cw-badge.warn{background:#FEF3C7;color:#92400E;}
.cw-badge.bad{background:#FFE4E6;color:#BE123C;}
.cw-badge.info{background:#E0E7FF;color:#3730A3;}
.cw-badge.neutral{background:#E2E8F0;color:#334155;}
.cw-user{display:flex;align-items:center;gap:.7rem;padding:.8rem;margin:.9rem 0 .6rem 0;border-radius:12px;background:rgba(255,255,255,.07);}
.cw-avatar{width:36px;height:36px;border-radius:50%;background:var(--amber);color:var(--ink)!important;font-weight:700;display:flex;align-items:center;justify-content:center;}
.cw-user-name{font-weight:600;color:#fff;line-height:1.2;}
.cw-user-role{font-size:.8rem;color:#A9B6D3;}
.cw-pending{margin:.4rem 0 .8rem 0;padding:.5rem .8rem;border-radius:10px;background:rgba(245,179,27,.16);color:#FCD34D;font-size:.88rem;}

/* sign-in screen */
.cw-hero{background:var(--ink);border-radius:20px;padding:2.4rem 2.2rem;color:#fff;}
.cw-hero h1{color:#fff!important;font-size:2.9rem;line-height:1.1;margin:1.6rem 0 .8rem 0;}
.cw-hero .lead{color:#B8C4DE;font-size:1.05rem;max-width:30rem;}
.cw-sample{background:#fff;color:var(--ink);border-radius:14px;padding:1.1rem 1.2rem;margin:1.6rem 0 1.4rem 0;}
.cw-sample .q{font-weight:600;margin-bottom:.5rem;}
.cw-sample .a{line-height:1.55;}
.cw-sample .src{margin-top:.7rem;padding-top:.6rem;border-top:1px solid var(--line);color:var(--muted);font-size:.82rem;}
.cw-sample .tag{color:var(--muted);font-size:.78rem;margin-bottom:.4rem;}
.cw-cite{display:inline-block;min-width:1.25rem;text-align:center;background:var(--amber);color:var(--ink);font-weight:700;font-size:.72rem;border-radius:5px;padding:0 .3rem;margin-left:.15rem;vertical-align:1px;}
.cw-points{list-style:none;padding:0;margin:0;}
.cw-points li{color:#DCE3F2;padding:.3rem 0 .3rem 1.4rem;position:relative;}
.cw-points li:before{content:"";position:absolute;left:0;top:.7rem;width:.55rem;height:.55rem;border-radius:2px;background:var(--teal);}
.cw-signin h2{margin:.4rem 0 .2rem 0;font-size:1.9rem;}
.cw-signin p{color:var(--muted);margin:0 0 1rem 0;}
"""


def inject_css():
    css = "\n".join(line for line in CSS.splitlines() if line.strip())
    st.markdown("<style>" + css + "</style>", unsafe_allow_html=True)


def hide_sidebar():
    st.markdown("<style>[data-testid='stSidebar'],[data-testid='collapsedControl'],"
                "[data-testid='stSidebarCollapsedControl']{display:none;}</style>",
                unsafe_allow_html=True)


def page_header(title, subtitle=""):
    sub = f"<p>{esc(subtitle)}</p>" if subtitle else ""
    st.markdown(f'<div class="cw-head"><h1>{esc(title)}</h1>{sub}</div>',
                unsafe_allow_html=True)


def section(title, hint=""):
    sub = f"<p>{esc(hint)}</p>" if hint else ""
    st.markdown(f'<div class="cw-section"><h3>{esc(title)}</h3>{sub}</div>',
                unsafe_allow_html=True)


def stat_strip(items):
    """items: dicts with label, value, optional sub and colour."""
    cells = "".join(
        '<div class="cw-stat"><div class="cw-stat-label">'
        f'<span class="cw-dot" style="background:{it.get("color", INDIGO)}"></span>{esc(it["label"])}</div>'
        f'<div class="cw-stat-value">{esc(it["value"])}</div>'
        f'<div class="cw-stat-sub">{esc(it.get("sub", ""))}</div></div>'
        for it in items)
    st.markdown(f'<div class="cw-strip">{cells}</div>', unsafe_allow_html=True)


def badge(text, kind="neutral"):
    return f'<span class="cw-badge {kind}">{esc(text)}</span>'


def initials(name):
    parts = [p for p in str(name).split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def user_card(name, role):
    return (f'<div class="cw-user"><div class="cw-avatar">{esc(initials(name))}</div>'
            f'<div><div class="cw-user-name">{esc(name)}</div>'
            f'<div class="cw-user-role">{esc(role).capitalize()}</div></div></div>')


def sign_in_hero():
    return (
        '<div class="cw-hero">' + brand_html(40, on_dark=True) +
        f'<h1>{esc(TAGLINE)}</h1>'
        '<div class="lead">Ask about company policies and procedures. Every answer '
        'comes with the document and page it was taken from.</div>'
        '<div class="cw-sample"><div class="tag">Example answer</div>'
        '<div class="q">How many days of annual leave do I get?</div>'
        '<div class="a">Full-time employees receive 24 days of paid annual leave '
        'per calendar year<span class="cw-cite">1</span></div>'
        '<div class="src"><span class="cw-cite" style="margin:0 .4rem 0 0">1</span>'
        'Leave Policy (Global), version 4, page 1</div></div>'
        '<ul class="cw-points"><li>You only see the documents your role can access.</li>'
        '<li>Superseded and revoked documents are never used in answers.</li>'
        '<li>Archiving or revoking a document needs a second admin to approve.</li></ul>'
        '</div>')