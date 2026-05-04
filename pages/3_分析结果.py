from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from utils.display_utils import download_file
from utils.file_store import delete_run, get_run_dir, list_runs, read_json
from utils.style import inject_css, render_sidebar_nav

# --- CSV filename → Chinese label mapping ---
CSV_LABELS = {
    "calibration_thresholds.csv": "校准阈值表",
    "calibrated_data.csv": "校准后数据",
    "necessity_high.csv": "必要条件分析（高结果）",
    "necessity_low.csv": "必要条件分析（低结果）",
    "truth_table_high.csv": "真值表（高结果）",
    "truth_table_low.csv": "真值表（低结果）",
}

inject_css()
study_id = render_sidebar_nav()

st.title("分析结果")
runs = list_runs(study_id)
if not runs:
    st.info("暂无分析记录。")
    st.stop()

options = {f"{r['run_id']} | {r.get('dataset_name', '')} | {r.get('status', '')}": r["run_id"] for r in runs}
option_keys = list(options.keys())
# Ensure the stored selectbox value is still valid after deletion
sel_key = "run_select"
if sel_key in st.session_state and st.session_state[sel_key] not in option_keys:
    del st.session_state[sel_key]
default_idx = 0
if sel_key in st.session_state:
    default_idx = option_keys.index(st.session_state[sel_key])

col_sel, col_del = st.columns([4, 1])
with col_sel:
    run_id = options[st.selectbox("选择分析记录", option_keys, index=default_idx, key=sel_key)]

# --- Delete run ---
with col_del:
    st.write("")
    if "delete_run_confirm" not in st.session_state:
        st.session_state["delete_run_confirm"] = False
    if st.button("🗑️ 删除此记录", key="del_run_btn", type="secondary"):
        st.session_state["delete_run_confirm"] = True

if st.session_state.get("delete_run_confirm"):
    st.warning(f"⚠️ 确认删除分析记录 `{run_id}`？此操作不可撤销。")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ 确认删除", key="del_run_ok", type="primary"):
            delete_run(run_id, study_id)
            st.session_state["delete_run_confirm"] = False
            st.session_state.pop("run_select", None)
            st.success("已删除。")
            st.rerun()
    with c2:
        if st.button("❌ 取消", key="del_run_cancel"):
            st.session_state["delete_run_confirm"] = False
            st.rerun()

run_dir = get_run_dir(run_id, study_id)

status = read_json(run_dir / "status.json", {})
config = read_json(run_dir / "config.json", {})

tables_dir = run_dir / "output" / "tables"
figures_dir = run_dir / "output" / "figures"
report_dir = run_dir / "output" / "report"
files_dir = run_dir / "output" / "files"
logs_dir = run_dir / "output" / "logs"

# --- Status badge ---
state = status.get("state", "unknown")
state_emoji = {"completed": "✅", "running": "⏳", "failed": "❌", "created": "📝"}.get(state, "❓")
state_text = {"completed": "完成", "running": "运行中", "failed": "失败", "created": "已创建"}.get(state, state)
st.caption(f"{state_emoji} 状态：{state_text} ｜ 数据集：{config.get('dataset_name', '-')} ｜ Run ID：{run_id}")

# ============================================================================
# Tab 1: Report (main content)
# ============================================================================
tab_report, tab_figures, tab_tables, tab_config = st.tabs(["📋 分析报告", "📊 图表", "📑 数据表", "⚙️ 配置与下载"])

with tab_report:
    report = report_dir / "report.md"
    if report.exists():
        st.markdown(report.read_text(encoding="utf-8"))
    else:
        st.info("报告文件尚未生成。")

# ============================================================================
# Tab 2: Figures
# ============================================================================
with tab_figures:
    png_files = sorted(figures_dir.glob("*.png"))
    svg_files = sorted(figures_dir.glob("*.svg"))

    if png_files or svg_files:
        st.subheader("组态路径图")
        for path in png_files:
            st.image(str(path), caption="组态路径图 (PNG)", width="stretch")
        for path in svg_files:
            st.image(str(path), caption="组态路径图 (SVG)", width="stretch")
    else:
        st.info("暂无结果图片。")

# ============================================================================
# Tab 3: Data tables
# ============================================================================
with tab_tables:
    csv_files = sorted(tables_dir.glob("*.csv"))
    if csv_files:
        for path in csv_files:
            label = CSV_LABELS.get(path.name, path.name)
            with st.expander(f"📄 {label}", expanded=False):
                try:
                    st.dataframe(pd.read_csv(path), width="stretch")
                except Exception as exc:
                    st.warning(f"无法渲染：{exc}")
                download_file(path, label=f"下载 {label}")
    else:
        st.info("没有 CSV 结果表。")

# ============================================================================
# Tab 4: Config & downloads
# ============================================================================
with tab_config:
    # Run status detail
    with st.expander("📌 运行状态详情", expanded=False):
        st.json(status)

    # Config
    with st.expander("🔧 分析配置 (config.json)", expanded=False):
        st.code(json.dumps(config, ensure_ascii=False, indent=2), language="json")

    # Logs
    with st.expander("📜 运行日志", expanded=False):
        stdout_log = logs_dir / "stdout.log"
        stderr_log = logs_dir / "stderr.log"
        if stdout_log.exists():
            st.caption("stdout.log")
            st.code(stdout_log.read_text(encoding="utf-8")[:5000], language="text")
        if stderr_log.exists():
            st.caption("stderr.log")
            st.code(stderr_log.read_text(encoding="utf-8")[:5000], language="text")

    # Bulk downloads
    with st.expander("📥 下载所有文件", expanded=False):
        for folder in [files_dir, tables_dir, figures_dir, report_dir, logs_dir]:
            for path in sorted(folder.glob("*")):
                if path.is_file():
                    label = CSV_LABELS.get(path.name)
                    download_file(path, label=label, key_suffix="bulk")
