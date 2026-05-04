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
    "solution_metrics_high.csv": "组态路径指标（高结果）",
    "solution_metrics_low.csv": "组态路径指标（低结果）",
    "solution_overall_high.csv": "总体解指标（高结果）",
    "solution_overall_low.csv": "总体解指标（低结果）",
    "config_table_high.csv": "组态路径表（核心/边缘条件·高结果）",
    "config_table_low.csv": "组态路径表（核心/边缘条件·低结果）",
}

# --- Config table CSV → styled dataframe ───────────────────────────────────
def _render_config_table(csv_path):
    """Render config_table CSV with core/peripheral symbols."""
    df = pd.read_csv(csv_path)
    if df.empty:
        st.info("无解。")
        return

    # Pivot: conditions as rows, paths as columns
    status_map = {
        "core_present": "● 核心",
        "peripheral_present": "● 边缘",
        "core_absent": "⊗ 核心缺",
        "peripheral_absent": "⊙ 边缘缺",
        "irrelevant": "—",
    }

    # Build display table
    paths = df["path"].unique()
    conditions = df["condition"].unique()
    cond_labels = {}
    for _, row in df.iterrows():
        if row["condition"] not in cond_labels:
            cond_labels[row["condition"]] = row["label"]

    # Highlight function
    def highlight(val):
        if val.startswith("●"):
            return "background-color: #DBEAFE; color: #1E40AF; font-weight: 600;"
        elif val.startswith("⊗"):
            return "background-color: #FEE2E2; color: #DC2626; font-weight: 600;"
        elif val.startswith("⊙"):
            return "background-color: #FEF2F2; color: #EF4444;"
        elif val.startswith("●"):
            return "background-color: #EFF6FF; color: #60A5FA;"
        return ""

    display_df = pd.DataFrame({"条件": [cond_labels.get(c, c) for c in conditions]})
    for path in paths:
        col_vals = []
        for cond in conditions:
            r = df[(df["path"] == path) & (df["condition"] == cond)]
            col_vals.append(status_map.get(r["status"].values[0], "?") if len(r) > 0 else "?")
        display_df[path] = col_vals

    st.dataframe(display_df.style.applymap(highlight, subset=paths.tolist()), width="stretch", hide_index=True)

    # Legend
    st.caption("● 核心条件存在 ｜ ● 边缘条件存在 ｜ ⊗ 核心条件缺失 ｜ ⊙ 边缘条件缺失 ｜ — 无关紧要")

    # Metrics summary per path
    st.markdown("**各路径指标：**")
    for path in paths:
        row = df[df["path"] == path].iloc[0]
        st.caption(f"{path}：一致性={row['consistency']:.4f}  原始覆盖率={row['raw_coverage']:.4f}")

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
    config_svg = figures_dir / "config_table.svg"
    bars_png = figures_dir / "solution_bars.png"
    bars_low = figures_dir / "solution_bars_low.png"
    old_png = figures_dir / "configuration_path.png"

    if config_svg.exists():
        st.subheader("组态路径表（核心/边缘条件）")
        st.image(str(config_svg), width="stretch")

    if bars_png.exists():
        st.subheader("路径一致性 & 覆盖率")
        st.image(str(bars_png), width="stretch")

    if bars_low.exists():
        st.subheader("低结果路径一致性 & 覆盖率")
        st.image(str(bars_low), width="stretch")

    # Fallback: old generic figure
    if not config_svg.exists() and not bars_png.exists():
        other_pngs = sorted(figures_dir.glob("*.png"))
        other_svgs = sorted(figures_dir.glob("*.svg"))
        if other_pngs or other_svgs:
            for p in other_pngs:
                st.image(str(p), caption=p.name, width="stretch")
            for p in other_svgs:
                st.image(str(p), caption=p.name, width="stretch")
        else:
            st.info("暂无结果图片。")

# ============================================================================
# Tab 3: Data tables
# ============================================================================
with tab_tables:
    csv_files = sorted(tables_dir.glob("*.csv"))
    if csv_files:
        # Show config table first with special rendering
        config_csv = tables_dir / "config_table_high.csv"
        if config_csv.exists():
            st.subheader("组态路径表（高结果·中间解）")
            _render_config_table(config_csv)
            st.divider()

        for path in csv_files:
            if path.name in ("config_table_high.csv", "config_table_low.csv"):
                continue  # handled above
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
