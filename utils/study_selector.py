"""Study selector — reusable Streamlit widget for all pages."""

from __future__ import annotations

import streamlit as st

from utils.file_store import list_studies

SESSION_KEY = "current_study_id"


def study_selector() -> str | None:
    """Render the study selector dropdown.

    Returns current study_id or None if no studies exist. Maintains
    st.session_state[SENDER_KEY] and triggers rerun on switch.
    """
    studies = list_studies()
    if not studies:
        if SESSION_KEY in st.session_state:
            del st.session_state[SESSION_KEY]
        return None

    options = {f"{s['name']} ({s['study_id']})": s["study_id"] for s in studies}

    current = st.session_state.get(SESSION_KEY)
    if current not in options.values():
        current = studies[0]["study_id"]
        st.session_state[SESSION_KEY] = current

    option_keys = list(options.keys())
    current_idx = next(
        (i for i, v in enumerate(options.values()) if v == current), 0
    )

    selected_label = st.selectbox(
        "当前研究",
        option_keys,
        index=current_idx,
        key="__study_selector_widget",
    )
    selected_id = options[selected_label]

    if selected_id != st.session_state[SESSION_KEY]:
        st.session_state[SESSION_KEY] = selected_id
        st.rerun()

    return selected_id


def require_study() -> str:
    """Return current study_id; show guidance + stop if no studies exist."""
    study_id = study_selector()
    if study_id is None:
        st.warning("还没有研究。请先到首页创建研究。")
        st.page_link("app.py", label="返回首页创建研究")
        st.stop()
    return study_id
