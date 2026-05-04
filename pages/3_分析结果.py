from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.ai_interpreter import (
    AI_PROVIDERS,
    generate_interpretation,
    interpretation_key,
    load_interpretations,
)
from utils.display_utils import download_file
from utils.file_store import delete_run, get_run_dir, list_analysis_specs, list_runs, read_json
from utils.fsqca_runner import _formula_to_label, _friendly_metric_table, _variable_label
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


def _solution_type_label(value: str) -> str:
    return {
        "intermediate": "中间解",
        "parsimonious": "精简解",
        "complex": "复杂解",
    }.get(str(value), str(value))


def _friendly_column_name(name: str, var_labels: dict[str, str]) -> str:
    if name.startswith("f_"):
        return f"校准值：{_variable_label(name, var_labels)}"
    if name in var_labels:
        return var_labels[name]
    return {
        "OUT": "结果",
        "n": "案例数",
        "incl": "一致性",
        "PRI": "PRI",
        "cases": "案例",
        "condition": "条件",
        "variable": "变量",
        "label": "中文标签",
        "full_exclusion": "完全不隶属",
        "crossover": "交叉点",
        "full_inclusion": "完全隶属",
        "consistency": "一致性",
        "coverage": "覆盖率",
        "solution_type": "解类型",
        "solution_consistency": "总体一致性",
        "solution_coverage": "总体覆盖率",
        "n_paths": "路径数",
        "path": "路径",
        "raw_coverage": "原始覆盖率",
        "unique_coverage": "唯一覆盖率",
    }.get(name, name)


def _friendly_table(path, var_labels: dict[str, str]) -> pd.DataFrame:
    df = pd.read_csv(path)
    if df.empty:
        return df

    if path.name.startswith("solution_metrics"):
        df = _friendly_metric_table(df, var_labels)
    else:
        if "formula" in df.columns:
            df["组态路径"] = df["formula"].map(lambda x: _formula_to_label(x, var_labels))
            df = df.drop(columns=["formula"])
        if "condition" in df.columns:
            df["condition"] = df["condition"].map(lambda x: _variable_label(str(x), var_labels, include_code=True))
        if "variable" in df.columns:
            df["variable"] = df["variable"].map(lambda x: _variable_label(str(x), var_labels, include_code=True))
        if "solution_type" in df.columns:
            df["solution_type"] = df["solution_type"].map(_solution_type_label)
        df = df.rename(columns={c: _friendly_column_name(c, var_labels) for c in df.columns})

    if "解类型" in df.columns:
        df["解类型"] = df["解类型"].map(_solution_type_label)
    return df


def _render_config_summary(config: dict, var_labels: dict[str, str]) -> None:
    outcome = config.get("outcome", "")
    conditions = config.get("conditions", [])
    rows = [
        {"项目": "数据集", "内容": config.get("dataset_name", "-")},
        {"项目": "结果变量", "内容": f"{_variable_label(outcome, var_labels)}（{outcome}）"},
        {"项目": "条件变量", "内容": "；".join(f"{_variable_label(v, var_labels)}（{v}）" for v in conditions)},
        {"项目": "一致性阈值", "内容": config.get("incl_cut")},
        {"项目": "PRI 阈值", "内容": config.get("pri_cut")},
        {"项目": "频数阈值", "内容": config.get("n_cut")},
        {"项目": "低结果分析", "内容": "是" if config.get("run_low") else "否"},
        {"项目": "稳健性检验", "内容": "是" if config.get("robustness") else "否"},
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def _run_label(run: dict) -> str:
    return f"{run.get('created_at', '')}｜{run.get('dataset_name', '')}｜{run['run_id']}｜{run.get('status', '')}"


def _run_summary_rows(runs: list[dict]) -> list[dict]:
    return [
        {
            "运行ID": r.get("run_id"),
            "数据集": r.get("dataset_name"),
            "状态": r.get("status"),
            "创建时间": r.get("created_at"),
        }
        for r in runs
    ]


def _label_from_presets(var_name: str) -> str:
    labels = {
        "os_work_support": "组织支持-工作支持",
        "os_value_identity": "组织支持-价值认同",
        "os_benefit_care": "组织支持-利益关心",
        "os_total": "组织支持-总量表",
        "we_vigor": "工作投入-活力",
        "we_dedication": "工作投入-奉献",
        "we_absorption": "工作投入-专注",
        "we_total": "工作投入-总量表",
        "dc_professional_engagement": "数字胜任力-专业参与",
        "dc_digital_resources": "数字胜任力-数字资源",
        "dc_teaching_learning": "数字胜任力-教学与学习",
        "dc_assessment_feedback": "数字胜任力-评价与反馈",
        "dc_empowering_learners": "数字胜任力-促进学习者发展",
        "dc_facilitating_digital": "数字胜任力-促进数字能力",
        "dc_total": "数字胜任力-总量表",
        "dl_total": "数字素养-总量表",
    }
    label = labels.get(var_name)
    return f"{label}（{var_name}）" if label else var_name


def _render_ai_settings(scope: str) -> dict:
    st.markdown("**AI 解读设置**")
    provider_names = list(AI_PROVIDERS.keys())
    provider = st.selectbox("服务商", provider_names, key=f"ai_provider_{scope}")
    preset = AI_PROVIDERS[provider]
    default_base = st.session_state.get(f"ai_base_url_{scope}", preset.base_url)
    default_model = st.session_state.get(f"ai_model_{scope}", preset.model)
    if st.session_state.get(f"ai_provider_prev_{scope}") != provider:
        default_base = preset.base_url
        default_model = preset.model
        st.session_state[f"ai_provider_prev_{scope}"] = provider
    c1, c2 = st.columns(2)
    with c1:
        base_url = st.text_input("API Base URL", value=default_base, key=f"ai_base_url_{scope}")
    with c2:
        model = st.text_input("模型", value=default_model, key=f"ai_model_{scope}")
    api_key = st.text_input("API Token", type="password", key=f"ai_token_{scope}")
    st.caption(f"{preset.note} 也可以改成任何 OpenAI-compatible 的 base URL。Token 只保存在当前页面会话中。")
    return {
        "provider": provider,
        "base_url": base_url.strip(),
        "model": model.strip(),
        "api_key": api_key,
    }


def _render_interpretation(
    run_dir,
    target_type: str,
    target_id: str,
    title: str,
    ai_settings: dict,
    saved: dict,
) -> None:
    key = interpretation_key(target_type, target_id)
    existing = saved.get(key, {})
    if existing.get("content"):
        with st.expander(f"AI 解读：{title}", expanded=False):
            st.caption(f"{existing.get('provider', '')} / {existing.get('model', '')} ｜ {existing.get('created_at', '')}")
            st.markdown(existing["content"])

    if st.button(f"生成/更新 AI 解读：{title}", key=f"ai_{target_type}_{target_id}"):
        if not ai_settings["api_key"]:
            st.warning("请先在上方填写 API Token。")
            return
        with st.spinner("正在把结构化数据发送给 AI 生成解读..."):
            try:
                content = generate_interpretation(
                    run_dir=run_dir,
                    target_type=target_type,
                    target_id=target_id,
                    api_key=ai_settings["api_key"],
                    base_url=ai_settings["base_url"],
                    model=ai_settings["model"],
                    provider=ai_settings["provider"],
                )
            except Exception as exc:
                st.error(str(exc))
                return
        st.success("AI 解读已生成。")
        st.markdown(content)


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

specs = list_analysis_specs(study_id)
spec_by_id = {s["spec_id"]: s for s in specs}
group_options: dict[str, str] = {}
for spec in specs:
    count = sum(1 for r in runs if r.get("spec_id") == spec["spec_id"])
    group_options[f"{spec['name']}｜{count} 次运行｜{spec['spec_id']}"] = spec["spec_id"]
unlinked_runs = [r for r in runs if not r.get("spec_id")]
if unlinked_runs:
    group_options[f"未关联方案｜{len(unlinked_runs)} 次运行"] = "__unlinked__"

if not group_options:
    group_options["全部运行记录"] = "__all__"

group_keys = list(group_options.keys())
group_key = "result_spec_select"
if group_key in st.session_state and st.session_state[group_key] not in group_keys:
    del st.session_state[group_key]
selected_group_label = st.selectbox("选择分析方案", group_keys, key=group_key)
selected_spec_id = group_options[selected_group_label]

if selected_spec_id == "__unlinked__":
    group_runs = unlinked_runs
    selected_spec = None
elif selected_spec_id == "__all__":
    group_runs = runs
    selected_spec = None
else:
    selected_spec = spec_by_id.get(selected_spec_id)
    group_runs = [r for r in runs if r.get("spec_id") == selected_spec_id]

if selected_spec:
    params = selected_spec.get("default_params", {})
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("方案", selected_spec.get("name", ""))
        c2.metric("算法", selected_spec.get("algorithm", "-"))
        c3.metric("运行次数", len(group_runs))
        c4.metric("默认阈值", f"{params.get('incl_cut', '-')}/{params.get('pri_cut', '-')}")
        st.caption("结果变量：" + _label_from_presets(selected_spec.get("outcome", "")))
        st.caption("条件变量：" + "；".join(_label_from_presets(v) for v in selected_spec.get("conditions", [])))

if group_runs:
    st.subheader("方案运行历史")
    st.dataframe(pd.DataFrame(_run_summary_rows(group_runs)), width="stretch", hide_index=True)
else:
    st.info("该方案还没有运行记录。")
    st.stop()

run_options = {_run_label(r): r["run_id"] for r in group_runs}
option_keys = list(run_options.keys())
sel_key = f"run_select_{selected_spec_id}"
if sel_key in st.session_state and st.session_state[sel_key] not in option_keys:
    del st.session_state[sel_key]

col_sel, col_del = st.columns([4, 1])
with col_sel:
    run_id = run_options[st.selectbox("选择运行记录", option_keys, key=sel_key)]

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
var_labels = config.get("variable_labels", {})

tables_dir = run_dir / "output" / "tables"
figures_dir = run_dir / "output" / "figures"
report_dir = run_dir / "output" / "report"
files_dir = run_dir / "output" / "files"
logs_dir = run_dir / "output" / "logs"
interpretations = load_interpretations(run_dir)

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
    with st.expander("AI 解读设置", expanded=False):
        ai_settings_figures = _render_ai_settings("figures")

    config_svg = figures_dir / "config_table.svg"
    bars_svg = figures_dir / "solution_bars.svg"
    bars_low = figures_dir / "solution_bars_low.svg"

    if config_svg.exists():
        st.subheader("组态路径表（核心/边缘条件）")
        st.image(str(config_svg), width="stretch")
        _render_interpretation(run_dir, "figure", "config_table_high", "组态路径表（高结果）", ai_settings_figures, interpretations)

    if bars_svg.exists():
        st.subheader("路径一致性 & 覆盖率")
        st.image(str(bars_svg), width="stretch")
        _render_interpretation(run_dir, "figure", "solution_bars_high", "路径一致性与覆盖率（高结果）", ai_settings_figures, interpretations)

    if bars_low.exists():
        st.subheader("低结果路径一致性 & 覆盖率")
        st.image(str(bars_low), width="stretch")
        _render_interpretation(run_dir, "figure", "solution_bars_low", "路径一致性与覆盖率（低结果）", ai_settings_figures, interpretations)

    # Fallback: old generic figure
    if not config_svg.exists() and not bars_svg.exists():
        other_figures = sorted(list(figures_dir.glob("*.png")) + list(figures_dir.glob("*.svg")))
        if other_figures:
            for p in other_figures:
                st.image(str(p), caption=p.name, width="stretch")
        else:
            st.info("暂无结果图片。")

# ============================================================================
# Tab 3: Data tables
# ============================================================================
with tab_tables:
    with st.expander("AI 解读设置", expanded=False):
        ai_settings_tables = _render_ai_settings("tables")

    csv_files = sorted(tables_dir.glob("*.csv"))
    if csv_files:
        # Show config table first with special rendering
        config_csv = tables_dir / "config_table_high.csv"
        if config_csv.exists():
            st.subheader("组态路径表（高结果·中间解）")
            _render_config_table(config_csv)
            _render_interpretation(run_dir, "table", "config_table_high.csv", "组态路径表（高结果·中间解）", ai_settings_tables, interpretations)
            st.divider()

        for path in csv_files:
            if path.name in ("config_table_high.csv", "config_table_low.csv"):
                continue  # handled above
            label = CSV_LABELS.get(path.name, path.name)
            with st.expander(f"📄 {label}", expanded=False):
                try:
                    st.dataframe(_friendly_table(path, var_labels), width="stretch")
                except Exception as exc:
                    st.warning(f"无法渲染：{exc}")
                _render_interpretation(run_dir, "table", path.name, label, ai_settings_tables, interpretations)
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
    with st.expander("🔧 分析配置", expanded=False):
        _render_config_summary(config, var_labels)

    # Logs
    with st.expander("📜 技术日志（调试用）", expanded=False):
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
