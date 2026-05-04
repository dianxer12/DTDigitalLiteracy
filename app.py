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
from utils.style import inject_css, render_sidebar_nav

inject_css()

# ── One-time migration ─────────────────────────────────────────────────────
if "migration_done" not in st.session_state:
    migrate_legacy_projects()
    st.session_state["migration_done"] = True

# ── Sidebar navigation + study selector ────────────────────────────────────
study_id = render_sidebar_nav()

# ═══════════════════════════════════════════════════════════════════════════
# Empty state – no studies yet
# ═══════════════════════════════════════════════════════════════════════════
if study_id is None:
    st.title("科研数据分析平台")
    st.markdown("##### 基于 fsQCA 的护理学研究工具")

    with st.container():
        st.info("你还没有任何研究", icon=":material/bar_chart:")
        st.markdown("点击下方开始你的第一次研究：")

    col_form, col_spacer = st.columns([1, 1])
    with col_form:
        with st.form("create_first_study"):
            name = st.text_input("研究名称", placeholder="例如：护理实习生职业倦怠研究")
            desc = st.text_area("研究描述（可选）", placeholder="简要描述研究目的……")
            if st.form_submit_button("创建新研究", type="primary", use_container_width=True):
                if not name.strip():
                    st.error("研究名称不能为空")
                else:
                    meta = create_study(name, desc)
                    st.session_state.current_study_id = meta["study_id"]
                    st.success(f"研究「{meta['name']}」已创建")
                    st.rerun()
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════
# Dashboard
# ═══════════════════════════════════════════════════════════════════════════
study_meta = get_study(study_id)
datasets = list_datasets(study_id)
runs = list_runs(study_id)

st.title("科研数据分析平台")
st.markdown("##### 基于 fsQCA 的护理学研究工具")

# ── Overview cards ─────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric("当前研究", study_meta.get("name", "") if study_meta else "")
col2.metric("数据集", len(datasets))
col3.metric("分析记录", len(runs))
col4.metric("最近分析状态", "✅ 完成" if runs and runs[0].get("status") == "completed" else "—")

if study_meta and study_meta.get("description"):
    st.caption(f"📝 {study_meta['description']}")

# ── Quick actions ──────────────────────────────────────────────────────────
st.divider()
st.subheader("开始分析流程")

c1, c2, c3 = st.columns(3)
with c1:
    with st.container(border=True):
        st.markdown("#### 步骤 1")
        st.markdown("上传 Excel/CSV 问卷数据")
        st.page_link("pages/1_数据集管理.py", label="上传数据", icon=":material/upload_file:", use_container_width=True)
with c2:
    with st.container(border=True):
        st.markdown("#### 步骤 2")
        st.markdown("加载预设量表，构建维度得分")
        st.page_link("pages/1_数据集管理.py", label="构建维度", icon=":material/function:", use_container_width=True)
with c3:
    with st.container(border=True):
        st.markdown("#### 步骤 3")
        st.markdown("配置变量与校准锚点，运行 fsQCA")
        st.page_link("pages/2_新建fsQCA分析.py", label="运行分析", icon=":material/science:", use_container_width=True)

# ── Data overview ──────────────────────────────────────────────────────────
st.divider()
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("数据集")
    if datasets:
        st.dataframe(dataframe_from_json(datasets), width="stretch", hide_index=True)
    else:
        st.info("还没有数据集。请点击上方「步骤 1」上传数据。")

with col_right:
    st.subheader("分析记录")
    if runs:
        st.dataframe(dataframe_from_json(runs), width="stretch", hide_index=True)
    else:
        st.info("还没有分析记录。请完成步骤 1-2 后运行分析。")

# ── Study management ───────────────────────────────────────────────────────
st.divider()
st.subheader("研究管理")

c_new, c_del = st.columns(2)
with c_new:
    with st.expander("创建新研究", expanded=False):
        with st.form("create_new_study"):
            new_name = st.text_input("研究名称", placeholder="例如：护理实习生职业倦怠研究", key="new_study_name")
            new_desc = st.text_area("研究描述（可选）", key="new_study_desc")
            if st.form_submit_button("创建", type="primary", use_container_width=True):
                if not new_name.strip():
                    st.error("研究名称不能为空")
                else:
                    meta = create_study(new_name, new_desc)
                    st.session_state.current_study_id = meta["study_id"]
                    st.success(f"研究「{meta['name']}」已创建")
                    st.rerun()

with c_del:
    with st.expander("删除当前研究", expanded=False):
        st.warning("删除研究将永久移除其所有数据集和分析记录，此操作不可撤销。")
        study_name = study_meta.get("name", "") if study_meta else ""
        confirm_name = st.text_input(
            f"请输入研究名称「{study_name}」以确认删除",
            key="delete_study_confirm",
        )
        if st.button(
            "确认删除",
            type="primary",
            disabled=(confirm_name != study_name),
            use_container_width=True,
        ):
            delete_study(study_id)
            remaining = list_studies()
            if remaining:
                st.session_state.current_study_id = remaining[0]["study_id"]
            else:
                st.session_state.pop("current_study_id", None)
            st.success(f"研究「{study_name}」已删除。")
            st.rerun()
