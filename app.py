"""FinSight AI entry point. Run with: streamlit run app.py"""
import streamlit as st

import config
from finsight.database import init_database
from finsight.ui import components, pages

st.set_page_config(page_title=config.APP_NAME, page_icon="💹", layout="wide", initial_sidebar_state="expanded")
init_database()
components.apply_theme()

with st.sidebar:
    st.markdown('<div class="fs-brand">FinSight <span>AI</span></div>', unsafe_allow_html=True)
    st.caption(config.TAGLINE)
    page = st.radio("Navigate", pages.PAGE_NAMES, label_visibility="collapsed", key="nav")
    st.divider()
    start, end, label = components.period_selector()
    st.divider()
    st.caption(f"Currency: {config.DEFAULT_CURRENCY} · Data stored locally")

pages.render(page, start, end, label)
