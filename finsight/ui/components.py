"""Reusable Streamlit components and the visual theme."""
from __future__ import annotations

from datetime import date, timedelta
from html import escape

import streamlit as st

from finsight.dates import month_bounds, previous_month

PERIOD_PRESETS = ("This month", "Last month", "Last 90 days", "This year", "Custom range")

CSS = """
<style>
:root { --fs-bg:#0B1220; --fs-panel:#111B2E; --fs-border:#1E2C44; --fs-text:#E2E8F0;
        --fs-muted:#8A9BB4; --fs-accent:#10B981; --fs-danger:#F87171; }
.stApp { background: var(--fs-bg); color: var(--fs-text); }
section[data-testid="stSidebar"] { background:#0D1729; border-right:1px solid var(--fs-border); }
h1, h2, h3 { color: var(--fs-text); letter-spacing:-0.01em; }
.fs-brand { font-weight:700; font-size:1.25rem; color:var(--fs-text); }
.fs-brand span { color: var(--fs-accent); }
.fs-card { background:var(--fs-panel); border:1px solid var(--fs-border); border-radius:14px;
           padding:16px 18px; min-height:112px; }
.fs-label { color:var(--fs-muted); font-size:0.75rem; text-transform:uppercase; letter-spacing:0.06em; }
.fs-value { font-size:1.55rem; font-weight:650; margin-top:6px; color:var(--fs-text); }
.fs-sub { color:var(--fs-muted); font-size:0.8rem; margin-top:4px; }
.fs-pos { color: var(--fs-accent) !important; }
.fs-neg { color: var(--fs-danger) !important; }
.fs-empty { border:1px dashed var(--fs-border); border-radius:14px; padding:28px; text-align:center;
            color:var(--fs-muted); margin:8px 0; }
@media (max-width: 768px) { .fs-value { font-size:1.2rem; } .fs-card { min-height:auto; } }
</style>
"""


def apply_theme() -> None:
    """Inject the FinSight stylesheet once per page run."""
    st.markdown(CSS, unsafe_allow_html=True)


def metric_card(label: str, value: str, sub: str = "", tone: str = "") -> None:
    """Render a summary card. tone may be 'pos', 'neg' or empty."""
    tone_class = {"pos": "fs-pos", "neg": "fs-neg"}.get(tone, "")
    st.markdown(
        f'<div class="fs-card"><div class="fs-label">{escape(label)}</div>'
        f'<div class="fs-value {tone_class}">{escape(value)}</div>'
        f'<div class="fs-sub">{escape(sub)}</div></div>',
        unsafe_allow_html=True,
    )


def empty_state(message: str) -> None:
    """Render a friendly placeholder when there is no data to show."""
    st.markdown(f'<div class="fs-empty">{escape(message)}</div>', unsafe_allow_html=True)


def period_selector() -> tuple[date, date, str]:
    """Sidebar control for the reporting period. Returns (start, end, label)."""
    today = date.today()
    choice = st.sidebar.selectbox("Reporting period", PERIOD_PRESETS, index=0, key="period_preset")
    if choice == "Custom range":
        col_from, col_to = st.sidebar.columns(2)
        start = col_from.date_input("From", value=today.replace(day=1), key="period_from")
        end = col_to.date_input("To", value=today, key="period_to")
        if start > end:
            st.sidebar.error("Start date must be on or before end date. Showing this month.")
            start, end = today.replace(day=1), today
        return start, end, "Custom range"
    if choice == "This month":
        start, end = today.replace(day=1), today
    elif choice == "Last month":
        start, end = month_bounds(*previous_month(today.year, today.month))
    elif choice == "Last 90 days":
        start, end = today - timedelta(days=89), today
    else:
        start, end = date(today.year, 1, 1), today
    return start, end, choice
