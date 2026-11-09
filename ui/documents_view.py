"""My documents: colour-coded department tiles, search and a classic ledger-style table."""
import pandas as pd
import requests
import streamlit as st

from brand import AMBER, INDIGO, TEAL, esc, page_header, stat_strip

DEPARTMENTS = ["HR", "IT", "Finance", "Legal", "Security", "Operations"]
SENSITIVITY = ["Public", "Internal", "Confidential", "Restricted"]
DEPT_COLORS = {"HR": "#DB2777", "IT": "#4F46E5", "Finance": "#059669",
               "Legal": "#7C3AED", "Security": "#334155", "Operations": "#D97706"}
SENS_STYLE = {"Public": ("#D1FAE5", "#047857"), "Internal": ("#E0E7FF", "#3730A3"),
              "Confidential": ("#FEF3C7", "#92400E"), "Restricted": ("#FFE4E6", "#BE123C")}
FORMAT_STYLE = {"pdf": ("#FEE2E2", "#B91C1C"), "docx": ("#DBEAFE", "#1D4ED8"),
                "txt": ("#E2E8F0", "#334155"), "csv": ("#DCFCE7", "#15803D")}
SORTS = ["Title A to Z", "Newest version first", "Most pages first", "Department"]
MAX_ROWS = 500

TABLE_CSS = """
.dv-wrap{max-height:580px;overflow:auto;background:#fff;border:1px solid #E3E7F0;border-radius:14px;}
.dv-table{width:100%;border-collapse:collapse;font-size:.92rem;}
.dv-table th{position:sticky;top:0;z-index:1;background:#F1F4FA;color:#475569;text-align:left;font-weight:600;font-size:.82rem;padding:.75rem .9rem;border-bottom:1px solid #E3E7F0;}
.dv-table td{padding:.7rem .9rem;border-bottom:1px solid #EEF1F7;color:#0B1B3A;vertical-align:middle;}
.dv-table tr:hover td{background:#F7F8FF;}
.dv-table td.id{color:#94A3B8;width:64px;font-variant-numeric:tabular-nums;}
.dv-table td.title{font-weight:600;}
.dv-table th.num,.dv-table td.num{text-align:right;font-variant-numeric:tabular-nums;}
.dv-chip{display:inline-block;padding:.14rem .65rem;border-radius:999px;font-size:.78rem;font-weight:600;white-space:nowrap;}
"""


def tile_css():
    rules = []
    for dept, color in {"All": INDIGO, **DEPT_COLORS}.items():
        k = f".st-key-dept_{dept}"
        rules += [
            f"{k} button{{background:#fff;color:#0B1B3A;border:1px solid #E3E7F0;border-top:4px solid {color};border-radius:12px;padding:.7rem .3rem;min-height:3.3rem;}}",
            f"{k} button p{{font-weight:600;color:inherit;}}",
            f"{k} button:hover{{border-color:{color};color:{color};}}",
            f"{k} button[kind='primary'],{k} [data-testid='stBaseButton-primary']{{background:{color};color:#fff;border-color:{color};}}",
            f"{k} button[kind='primary']:hover,{k} [data-testid='stBaseButton-primary']:hover{{background:{color};color:#fff;filter:brightness(1.1);}}",
        ]
    return "".join(rules)


def chip(text, bg, fg):
    return f'<span class="dv-chip" style="background:{bg};color:{fg}">{esc(text)}</span>'


def table_html(rows):
    head = ("<tr><th>ID</th><th>Title</th><th>Department</th><th>Version</th>"
            "<th>Sensitivity</th><th>Format</th><th class=\"num\">Pages</th></tr>")
    body = []
    for r in rows:
        color = DEPT_COLORS.get(r.get("department"), "#64748B")
        s_bg, s_fg = SENS_STYLE.get(r.get("sensitivity"), ("#E2E8F0", "#334155"))
        f_bg, f_fg = FORMAT_STYLE.get(str(r.get("format")).lower(), ("#E2E8F0", "#334155"))
        body.append(
            f'<tr><td class="id" style="border-left:4px solid {color}">{esc(r.get("id"))}</td>'
            f'<td class="title">{esc(r.get("title"))}</td>'
            f'<td>{chip(r.get("department"), color + "1A", color)}</td>'
            f'<td>{chip("v" + str(r.get("version")), "#EEF2FF", "#3730A3")}</td>'
            f'<td>{chip(r.get("sensitivity"), s_bg, s_fg)}</td>'
            f'<td>{chip(str(r.get("format")).upper(), f_bg, f_fg)}</td>'
            f'<td class="num">{esc(r.get("pages"))}</td></tr>')
    return f'<div class="dv-wrap"><table class="dv-table">{head}{"".join(body)}</table></div>'


def set_dept(dept):
    st.session_state.doc_dept = dept


def documents_page(headers, api, error_text):
    page_header("My documents", "The documents your role is allowed to search.")
    st.markdown("<style>" + TABLE_CSS + tile_css() + "</style>", unsafe_allow_html=True)
    st.session_state.setdefault("doc_dept", "All")

    r = requests.get(f"{api}/documents", headers=headers)
    if r.status_code != 200:
        st.error(error_text(r))
        return
    rows = r.json()
    counts = pd.Series([x.get("department") for x in rows]).value_counts()

    tiles = st.columns(len(DEPARTMENTS) + 1)
    for col, dept in zip(tiles, ["All"] + DEPARTMENTS):
        n = len(rows) if dept == "All" else int(counts.get(dept, 0))
        col.button(f"{dept} ({n})", key=f"dept_{dept}", use_container_width=True,
                   type="primary" if st.session_state.doc_dept == dept else "secondary",
                   on_click=set_dept, args=(dept,))

    c1, c2, c3 = st.columns([3, 2, 2])
    query = c1.text_input("Search", placeholder="Search by title", label_visibility="collapsed")
    levels = c2.multiselect("Sensitivity", SENSITIVITY, placeholder="All sensitivity levels",
                            label_visibility="collapsed")
    order = c3.selectbox("Sort by", SORTS, label_visibility="collapsed")

    shown = [x for x in rows
             if (st.session_state.doc_dept == "All" or x.get("department") == st.session_state.doc_dept)
             and (not query.strip() or query.strip().lower() in str(x.get("title", "")).lower())
             and (not levels or x.get("sensitivity") in levels)]
    key = {"Title A to Z": lambda x: str(x.get("title", "")).lower(),
           "Newest version first": lambda x: -int(x.get("version") or 0),
           "Most pages first": lambda x: -int(x.get("pages") or 0),
           "Department": lambda x: (str(x.get("department", "")), str(x.get("title", "")).lower())}[order]
    shown.sort(key=key)

    stat_strip([
        {"label": "Documents shown", "value": len(shown), "sub": f"of {len(rows)} you can access", "color": INDIGO},
        {"label": "Departments", "value": len({x.get("department") for x in shown}), "color": TEAL},
        {"label": "Pages", "value": sum(int(x.get("pages") or 0) for x in shown), "color": AMBER}])

    if not shown:
        st.info("No documents match your filters. Clear the search or choose another department.")
        return
    limit = int(st.session_state.get("pref_rows", MAX_ROWS))
    st.markdown(table_html(shown[:limit]), unsafe_allow_html=True)
    if len(shown) > limit:
        st.caption(f"Showing the first {limit} documents. Narrow the search to see the rest.")
    st.download_button("Export as CSV", pd.DataFrame(shown).to_csv(index=False),
                       "documents.csv", "text/csv")