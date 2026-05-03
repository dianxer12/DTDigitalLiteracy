from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.dataset_utils import load_prepared_data, numeric_columns, quantile_thresholds
from utils.file_store import DEFAULT_PROJECT_ID, ensure_default_project, get_dataset_dir, list_datasets, read_json
from utils.fsqca_runner import create_run, run_fsqca


st.set_page_config(page_title="新建fsQCA分析", layout="wide")
project_dir = ensure_default_project()

st.title("新建 fsQCA 分析")

datasets = list_datasets(DEFAULT_PROJECT_ID)
if not datasets:
    st.info("请先在「数据集管理」页面上传数据并构建维度。")
    st.stop()

# ---- Classify datasets: scored vs raw ----
def _looks_scored(d: dict, df: pd.DataFrame) -> bool:
    if "_scored" in d.get("name", "").lower():
        return True
    dim_prefixes = ("os_", "we_", "dc_", "dl_")
    if df.shape[1] <= 25 and any(str(c).startswith(dim_prefixes) for c in df.columns):
        return True
    return False

_scored_map: dict[str, bool] = {}
for d in datasets:
    try:
        _df = load_prepared_data(get_dataset_dir(d["dataset_id"], DEFAULT_PROJECT_ID))
        _scored_map[d["dataset_id"]] = _looks_scored(d, _df)
    except Exception:
        _scored_map[d["dataset_id"]] = False

scored_list = [d for d in datasets if _scored_map.get(d["dataset_id"], False)]
raw_list = [d for d in datasets if not _scored_map.get(d["dataset_id"], False)]

if not scored_list:
    st.warning("⚠️ 没有找到已构建维度的数据集。")
    st.markdown("请先到 **数据集管理 → 构建维度** 加载预设并点击「计算维度得分」。")
    if raw_list:
        st.caption(f"当前有 {len(raw_list)} 个原始数据集，但尚未计算维度得分。")
    st.stop()

# Build selector – mark scored vs raw
def _opt_label(d: dict) -> str:
    tag = " ✅维度" if _scored_map.get(d["dataset_id"]) else " 📄原始"
    return f"{d.get('name', d['dataset_id'])} ({d['dataset_id']}){tag}"

# Default to the last scored dataset
default_idx = next(
    (i for i, d in enumerate(datasets) if _scored_map.get(d["dataset_id"])),
    0,
)

options = {_opt_label(d): d for d in datasets}
selected_label = st.selectbox("选择数据集", list(options.keys()), index=default_idx)
dataset = options[selected_label]
ddir = get_dataset_dir(dataset["dataset_id"], DEFAULT_PROJECT_ID)
df = load_prepared_data(ddir)
num_cols = numeric_columns(df)
is_scored = _scored_map.get(dataset["dataset_id"], False)

st.subheader("数据预览")
st.caption(f"{df.shape[0]} 行 × {df.shape[1]} 列")
st.dataframe(df.head(10), use_container_width=True)

if not is_scored:
    st.warning("⚠️ 当前数据集是原始问卷数据，不包含维度变量。请回到「数据集管理 → 构建维度」计算维度得分后再来。")

# ---- Quick model presets ----
st.subheader("快速模型选择")
MODEL_PRESETS = {
    "5条件DC维度模型": {
        "outcome": "dl_total",
        "conditions": ["os_total", "we_total", "dc_teaching_learning", "dc_assessment_feedback", "dc_facilitating_digital"],
        "desc": "3前因(OS/WEO/DC) + DC子维度 → DL",
    },
    "3条件总模型": {
        "outcome": "dl_total",
        "conditions": ["os_total", "we_total", "dc_total"],
        "desc": "OS总量表 + WE总量表 + DC总量表 → DL",
    },
}

col_preset, col_custom = st.columns([1, 2])
with col_preset:
    preset_choice = st.selectbox("预设模型", ["自定义"] + list(MODEL_PRESETS.keys()))
    if preset_choice != "自定义":
        preset = MODEL_PRESETS[preset_choice]
        # Validate preset columns exist
        missing_outcome = preset["outcome"] not in num_cols
        missing_conds = [c for c in preset["conditions"] if c not in num_cols]
        if missing_outcome or missing_conds:
            st.warning(f"预设变量在当前数据中不存在，请确认已构建维度。")
            if missing_outcome:
                st.caption(f"缺少 outcome: {preset['outcome']}")
            if missing_conds:
                st.caption(f"缺少 conditions: {missing_conds}")
        else:
            st.success(f"✅ {preset['desc']}")

# ---- Variable selection ----
st.subheader("变量选择")
if preset_choice != "自定义":
    preset = MODEL_PRESETS[preset_choice]
    if preset["outcome"] in num_cols and all(c in num_cols for c in preset["conditions"]):
        outcome = st.selectbox("Outcome 结果变量", num_cols, index=num_cols.index(preset["outcome"]))
        default_conds = [c for c in preset["conditions"] if c in num_cols]
    else:
        outcome = st.selectbox("Outcome 结果变量", num_cols)
        default_conds = []
else:
    outcome = st.selectbox("Outcome 结果变量", num_cols)
    default_conds = []

condition_candidates = [c for c in num_cols if c != outcome]
conditions = st.multiselect(
    "Conditions 条件变量",
    condition_candidates,
    default=default_conds if default_conds else condition_candidates[: min(5, len(condition_candidates))],
)

if not outcome or not conditions:
    st.warning("请选择 outcome 和至少一个 condition。")
    st.stop()

# ---- Calibration ----
st.subheader("校准设置")
st.caption("DC 维度建议手动设为 [2, 3, 4]；DL 结果变量建议 [4, 4.5, 5]；其余可用分位数自动计算。")

calibration = {}
all_vars = [outcome] + conditions
for var in all_vars:
    with st.expander(f"{var} 校准", expanded=True):
        method = st.radio("校准方式", ["quantile", "manual"], horizontal=True, key=f"method_{var}")
        q25, q50, q75 = quantile_thresholds(df[var])
        st.caption(f"自动分位数：P25={q25}, P50={q50}, P75={q75}")
        if q25 == q50 or q50 == q75:
            st.warning("P25/P50/P75 存在重复，可能有天花板效应或地板效应，建议手动设置。")

        # Suggest manual thresholds for known variable types
        default_low, default_mid, default_high = float(q25), float(q50), float(q75)
        if var.startswith("dc_"):
            default_low, default_mid, default_high = 2.0, 3.0, 4.0
        elif var == "dl_total":
            default_low, default_mid, default_high = 4.0, 4.5, 5.0

        if method == "manual":
            c1, c2, c3 = st.columns(3)
            low = c1.number_input("完全非隶属", value=default_low, key=f"low_{var}")
            mid = c2.number_input("交叉点", value=default_mid, key=f"mid_{var}")
            high = c3.number_input("完全隶属", value=default_high, key=f"high_{var}")
            thresholds = [low, mid, high]
        else:
            thresholds = [q25, q50, q75]
        calibration[var] = {"method": method, "thresholds": thresholds}

# ---- fsQCA parameters ----
st.subheader("fsQCA 参数")
c1, c2, c3 = st.columns(3)
incl_cut = c1.number_input("incl_cut", min_value=0.0, max_value=1.0, value=0.80, step=0.01)
pri_cut = c2.number_input("pri_cut", min_value=0.0, max_value=1.0, value=0.70, step=0.01)
n_cut = c3.number_input("n_cut", min_value=1, value=1, step=1)
run_low = st.checkbox("运行低结果分析", value=True)
robustness = st.checkbox("运行稳健性检验", value=False)

if st.button("创建并运行 fsQCA", type="primary"):
    run_dir = create_run(
        project_dir=project_dir,
        dataset=dataset,
        df=df,
        outcome=outcome,
        conditions=conditions,
        calibration=calibration,
        incl_cut=float(incl_cut),
        pri_cut=float(pri_cut),
        n_cut=int(n_cut),
        run_low=run_low,
        robustness=robustness,
    )
    with st.spinner("正在调用 Rscript 运行 fsQCA..."):
        run_fsqca(run_dir)
    status = read_json(run_dir / "status.json", {})
    if status.get("state") == "completed":
        st.success(f"运行完成：{run_dir.name}")
    else:
        st.error(status.get("message", "运行失败"))
    st.code(str(run_dir))
