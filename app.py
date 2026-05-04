from __future__ import annotations

from pathlib import Path

import streamlit as st

from utils.display_utils import dataframe_from_json
from utils.file_store import (
    create_study,
    delete_study,
    get_study,
    list_analysis_specs,
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
specs = list_analysis_specs(study_id)
runs = list_runs(study_id)

st.title(study_meta.get("name", "研究工作台") if study_meta else "研究工作台")
st.markdown("##### 研究总览 · 数据集 · 分析方案 · 运行结果")

# ── Overview cards ─────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric("数据集", len(datasets))
col2.metric("分析方案", len(specs))
col3.metric("运行结果", len(runs))
latest_status = "完成" if runs and runs[0].get("status") == "completed" else ("运行中" if runs and runs[0].get("status") == "running" else "—")
col4.metric("最近状态", latest_status)

if study_meta and study_meta.get("description"):
    st.caption(f"📝 {study_meta['description']}")

# ── Next step guidance ─────────────────────────────────────────────────────
has_scored_dataset = any("_scored" in d.get("name", "").lower() for d in datasets)
has_ai_interpretation = any(
    (Path(r.get("run_dir", "")) / "output" / "ai_interpretations" / "interpretations.json").exists()
    for r in runs
    if r.get("run_dir")
)
if not datasets:
    next_msg = "下一步：上传或导入本研究的数据集。"
    next_page = ("pages/1_数据集管理.py", "去管理数据集", ":material/upload_file:")
elif not has_scored_dataset:
    next_msg = "下一步：在数据集页面构建维度得分，形成可用于 fsQCA 的维度数据。"
    next_page = ("pages/1_数据集管理.py", "去构建维度", ":material/function:")
elif not specs:
    next_msg = "下一步：基于维度数据创建分析方案，把算法、变量和校准锚点保存下来。"
    next_page = ("pages/2_新建fsQCA分析.py", "去建立分析方案", ":material/schema:")
elif not runs:
    next_msg = "下一步：运行一个已保存的分析方案，生成真值表、组态路径和报告。"
    next_page = ("pages/2_新建fsQCA分析.py", "去运行方案", ":material/science:")
elif not has_ai_interpretation:
    next_msg = "下一步：为关键图表或数据表生成 AI 解读，沉淀到研究结果中。"
    next_page = ("pages/3_分析结果.py", "去生成AI解读", ":material/psychology:")
else:
    next_msg = "当前研究已经形成数据、方案、结果和 AI 解读，可以继续补充模型或整理报告。"
    next_page = ("pages/3_分析结果.py", "查看结果与解读", ":material/description:")

with st.container(border=True):
    c_msg, c_action = st.columns([3, 1])
    c_msg.markdown(f"**{next_msg}**")
    with c_action:
        st.page_link(next_page[0], label=next_page[1], icon=next_page[2], use_container_width=True)

# ── Quick actions ──────────────────────────────────────────────────────────
st.divider()
st.subheader("研究流程")

c1, c2, c3 = st.columns(3)
with c1:
    with st.container(border=True):
        st.markdown("#### 步骤 1")
        st.markdown("上传 Excel/CSV 问卷数据")
        st.page_link("pages/1_数据集管理.py", label="管理数据集", icon=":material/upload_file:", use_container_width=True)
with c2:
    with st.container(border=True):
        st.markdown("#### 步骤 2")
        st.markdown("配置模型、变量和校准锚点")
        st.page_link("pages/2_新建fsQCA分析.py", label="建立分析方案", icon=":material/schema:", use_container_width=True)
with c3:
    with st.container(border=True):
        st.markdown("#### 步骤 3")
        st.markdown("运行方案、查看结果和 AI 解读")
        st.page_link("pages/3_分析结果.py", label="查看运行结果", icon=":material/science:", use_container_width=True)

# ── Data overview ──────────────────────────────────────────────────────────
st.divider()
st.subheader("研究对象关系")
st.caption("一个研究可以包含多个数据集；一个分析方案可以关联一个或多个数据集；一个方案可以产生多次运行结果。")

dataset_names = {d["dataset_id"]: d.get("name", d["dataset_id"]) for d in datasets}
spec_names = {s["spec_id"]: s.get("name", s["spec_id"]) for s in specs}

relation_rows = []
for spec in specs:
    linked_runs = [r for r in runs if r.get("spec_id") == spec["spec_id"]]
    relation_rows.append({
        "分析方案": spec["name"],
        "算法": spec.get("algorithm", "-"),
        "关联数据集": "；".join(dataset_names.get(i, i) for i in spec.get("dataset_ids", [])) or "—",
        "结果变量": spec.get("outcome", "-"),
        "条件数": len(spec.get("conditions", [])),
        "运行次数": len(linked_runs),
        "最近运行状态": linked_runs[0].get("status", "—") if linked_runs else "—",
    })
if relation_rows:
    st.dataframe(dataframe_from_json(relation_rows), width="stretch", hide_index=True)
else:
    st.info("还没有分析方案。先创建一个方案，把数据集和算法关联起来。")

st.divider()
col_left, col_mid, col_right = st.columns(3)

with col_left:
    st.subheader("数据集")
    if datasets:
        st.dataframe(dataframe_from_json(datasets), width="stretch", hide_index=True)
    else:
        st.info("还没有数据集。")

with col_mid:
    st.subheader("分析方案")
    if specs:
        st.dataframe(dataframe_from_json([
            {
                "name": s.get("name"),
                "algorithm": s.get("algorithm"),
                "datasets": "；".join(dataset_names.get(i, i) for i in s.get("dataset_ids", [])),
                "updated_at": s.get("updated_at"),
            }
            for s in specs
        ]), width="stretch", hide_index=True)
    else:
        st.info("还没有分析方案。")

with col_right:
    st.subheader("运行结果")
    if runs:
        st.dataframe(dataframe_from_json([
            {
                "run_id": r.get("run_id"),
                "方案": r.get("spec_name") or spec_names.get(r.get("spec_id"), "未关联方案"),
                "数据集": r.get("dataset_name"),
                "状态": r.get("status"),
                "created_at": r.get("created_at"),
            }
            for r in runs
        ]), width="stretch", hide_index=True)
    else:
        st.info("还没有运行结果。")

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
