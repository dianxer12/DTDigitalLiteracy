from __future__ import annotations

import streamlit as st

from utils.display_utils import dataframe_from_json
from utils.file_store import (
    create_study,
    delete_study,
    get_study,
    list_datasets,
    list_runs,
    list_studies,
    migrate_legacy_projects,
)
from utils.study_selector import SESSION_KEY as STUDY_KEY, study_selector

st.set_page_config(page_title="科研数据分析平台", layout="wide")

# ── One-time migration ─────────────────────────────────────────────────────
if "migration_done" not in st.session_state:
    migrate_legacy_projects()
    st.session_state["migration_done"] = True

# ── Study selector ──────────────────────────────────────────────────────────
study_id = study_selector()

# ═══════════════════════════════════════════════════════════════════════════
# Empty state – no studies yet
# ═══════════════════════════════════════════════════════════════════════════
if study_id is None:
    st.title("科研数据分析平台")
    st.caption("文件系统存储 · 无数据库 · 支持 fsQCA")

    st.info("你还没有任何研究", icon="👋")
    st.markdown("点击下方开始你的第一次研究：")

    with st.form("create_first_study"):
        name = st.text_input("研究名称", placeholder="例如：护理实习生职业倦怠研究")
        desc = st.text_area("研究描述（可选）", placeholder="简要描述研究目的……")
        if st.form_submit_button("创建新研究", type="primary"):
            if not name.strip():
                st.error("研究名称不能为空")
            else:
                meta = create_study(name, desc)
                st.session_state[STUDY_KEY] = meta["study_id"]
                st.success(f"研究「{meta['name']}」已创建")
                st.rerun()
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════
# Study exists – workbench
# ═══════════════════════════════════════════════════════════════════════════
study_meta = get_study(study_id)
datasets = list_datasets(study_id)
runs = list_runs(study_id)

st.title("科研数据分析平台")
st.caption("文件系统存储 · 无数据库 · 支持 fsQCA")

# ── Overview cards ─────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
col1.metric("当前研究", study_meta.get("name", ""))
col2.metric("数据集数量", len(datasets))
col3.metric("分析记录数量", len(runs))
if study_meta.get("description"):
    st.caption(study_meta["description"])

# ── Quick actions ──────────────────────────────────────────────────────────
st.divider()
st.subheader("快速操作")
c1, c2, c3 = st.columns(3)
c1.page_link("pages/1_数据集管理.py", label="1. 上传问卷数据", use_container_width=True)
c2.page_link("pages/1_数据集管理.py", label="2. 构建维度得分", use_container_width=True)
c3.page_link("pages/2_新建fsQCA分析.py", label="3. 运行 fsQCA 分析", use_container_width=True)

# ── Datasets ───────────────────────────────────────────────────────────────
st.divider()
st.subheader("数据集列表")
if datasets:
    st.dataframe(dataframe_from_json(datasets), width="stretch")
else:
    st.info("还没有数据集。请进入「数据集管理」页面上传 Excel 或 CSV。")

# ── Analysis runs ──────────────────────────────────────────────────────────
st.subheader("分析记录列表")
if runs:
    st.dataframe(dataframe_from_json(runs), width="stretch")
else:
    st.info("还没有分析记录。请进入「新建fsQCA分析」页面创建分析。")

# ── Study management ───────────────────────────────────────────────────────
st.divider()
st.subheader("研究管理")

with st.expander("创建新研究"):
    with st.form("create_new_study"):
        new_name = st.text_input(
            "研究名称", placeholder="例如：护理实习生职业倦怠研究", key="new_study_name"
        )
        new_desc = st.text_area("研究描述（可选）", key="new_study_desc")
        if st.form_submit_button("创建", type="primary"):
            if not new_name.strip():
                st.error("研究名称不能为空")
            else:
                meta = create_study(new_name, new_desc)
                st.session_state[STUDY_KEY] = meta["study_id"]
                st.success(f"研究「{meta['name']}」已创建")
                st.rerun()

with st.expander("删除当前研究"):
    st.warning("删除研究将永久移除其所有数据集和分析记录，此操作不可撤销。")
    study_name = study_meta.get("name", "")
    confirm_name = st.text_input(
        f"请输入研究名称「{study_name}」以确认删除",
        key="delete_study_confirm",
    )
    if st.button(
        "确认删除",
        type="primary",
        disabled=(confirm_name != study_name),
    ):
        delete_study(study_id)
        remaining = list_studies()
        if remaining:
            st.session_state[STUDY_KEY] = remaining[0]["study_id"]
        else:
            st.session_state.pop(STUDY_KEY, None)
        st.success(f"研究「{study_name}」已删除。")
        st.rerun()
