"""Global CSS and styling utilities for the research analysis platform."""

from __future__ import annotations

import streamlit as st

CSS = """
<style>
/* ── Font & base ─────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans SC', -apple-system, 'PingFang SC', 'STHeiti', 'Hiragino Sans GB', sans-serif;
}

/* ── Sidebar ─────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #FEF3C7 0%, #FFFBEB 100%);
    border-right: 1px solid #FDE68A;
}
[data-testid="stSidebarNav"] {
    display: none;
}
[data-testid="stSidebar"] .st-emotion-cache-6qob1r {
    background: transparent;
}
[data-testid="stSidebar"] h2 {
    color: #B45309;
    font-weight: 600;
    font-size: 1.1rem;
}
[data-testid="stSidebar"] h3 {
    color: #78716C;
    font-weight: 500;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* ── Sidebar nav links ───────────────────────────────────────────────── */
[data-testid="stSidebar"] a {
    color: #92400E !important;
    font-weight: 500;
    text-decoration: none !important;
    padding: 0.35rem 0.5rem;
    border-radius: 6px;
    display: block;
    transition: background 0.15s ease;
}
[data-testid="stSidebar"] a:hover {
    background: rgba(217, 119, 6, 0.08);
    color: #B45309 !important;
}

/* ── Metric cards ────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #FAEEE1;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    box-shadow: 0 1px 3px rgba(217, 119, 6, 0.06);
    transition: box-shadow 0.2s ease;
}
[data-testid="stMetric"]:hover {
    box-shadow: 0 4px 12px rgba(217, 119, 6, 0.10);
}
[data-testid="stMetric"] label {
    color: #78716C;
    font-size: 0.8rem;
    font-weight: 500;
    letter-spacing: 0.02em;
}
[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #92400E;
    font-weight: 700;
    font-size: 1.75rem;
}

/* ── Primary button ──────────────────────────────────────────────────── */
button[kind="primary"] {
    background: linear-gradient(135deg, #D97706, #F59E0B) !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    color: #FFFFFF !important;
    transition: all 0.2s ease !important;
}
button[kind="primary"]:hover {
    background: linear-gradient(135deg, #B45309, #D97706) !important;
    box-shadow: 0 2px 8px rgba(217, 119, 6, 0.30);
}
button[kind="secondary"] {
    border-radius: 8px !important;
    border-color: #FDE68A !important;
    color: #92400E !important;
}

/* ── Expander / sections ──────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid #FAEEE1 !important;
    border-radius: 10px !important;
    box-shadow: 0 1px 3px rgba(217, 119, 6, 0.04);
}

/* ── Dataframe / table ───────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    overflow: hidden;
}
[data-testid="stDataFrame"] th {
    background: #FEF3C7 !important;
    color: #92400E !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
}

/* ── Info / warning / success boxes ──────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 8px;
}

/* ── Page link cards (dashboard step buttons) ────────────────────────── */
a[data-testid="stPageLink-NavLink"] {
    background: linear-gradient(135deg, #D97706, #F59E0B);
    color: #FFFFFF !important;
    border-radius: 8px;
    padding: 0.6rem 1rem;
    font-weight: 600;
    text-decoration: none;
    display: block;
    text-align: center;
    transition: all 0.2s ease;
}
a[data-testid="stPageLink-NavLink"]:hover {
    background: linear-gradient(135deg, #B45309, #D97706);
    box-shadow: 0 4px 12px rgba(217, 119, 6, 0.30);
}

/* ── Selectbox / inputs ───────────────────────────────────────────────── */
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    border-radius: 8px;
}

/* ── Container border cards ───────────────────────────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 12px;
    border: 1px solid #FAEEE1 !important;
    box-shadow: 0 1px 3px rgba(217, 119, 6, 0.04);
    padding: 1rem 1.25rem;
}

/* ── Horizontal rule ──────────────────────────────────────────────────── */
hr {
    border-color: #FAEEE1 !important;
}

/* ── Title & headings ─────────────────────────────────────────────────── */
h1 {
    color: #92400E !important;
    font-weight: 700 !important;
}
h2 {
    color: #B45309 !important;
    font-weight: 600 !important;
    font-size: 1.3rem !important;
}
h3 {
    color: #92400E !important;
    font-weight: 600 !important;
}
</style>
"""


def inject_css():
    """Inject global custom CSS. Call once at the top of each page."""
    st.set_page_config(
        page_title="科研数据分析平台",
        page_icon=":material/bar_chart:",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CSS, unsafe_allow_html=True)


def render_sidebar_nav():
    """Render consistent sidebar navigation across all pages.

    Returns study_id from the study selector, or None.
    """
    from utils.study_selector import study_selector

    with st.sidebar:
        st.markdown("## 科研数据分析平台")

        study_id = study_selector()

        st.divider()

        st.markdown("### 导航")
        st.page_link("app.py", label="首页仪表盘", icon=":material/dashboard:")
        st.page_link("pages/1_数据集管理.py", label="数据集管理", icon=":material/folder:")
        st.page_link("pages/2_新建fsQCA分析.py", label="新建fsQCA分析", icon=":material/experiment:")
        st.page_link("pages/3_分析结果.py", label="分析结果", icon=":material/description:")

        st.divider()
        st.caption("文件系统存储 · 无数据库 · fsQCA v1.0")

        return study_id
