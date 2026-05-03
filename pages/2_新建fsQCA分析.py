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
    st.info("请先在「数据集管理」页面上传数据。")
    st.stop()

options = {f"{d['name']} ({d['dataset_id']})": d for d in datasets}
selected_label = st.selectbox("选择数据集", list(options.keys()))
dataset = options[selected_label]
ddir = get_dataset_dir(dataset["dataset_id"], DEFAULT_PROJECT_ID)
df = load_prepared_data(ddir)
num_cols = numeric_columns(df)

st.subheader("数据预览")
st.dataframe(df.head(20), use_container_width=True)

st.subheader("变量选择")
outcome = st.selectbox("Outcome 结果变量", num_cols)
condition_candidates = [c for c in num_cols if c != outcome]
conditions = st.multiselect("Conditions 条件变量", condition_candidates, default=condition_candidates[: min(5, len(condition_candidates))])

if not outcome or not conditions:
    st.warning("请选择 outcome 和至少一个 condition。")
    st.stop()

st.subheader("校准设置")
calibration = {}
all_vars = [outcome] + conditions
for var in all_vars:
    with st.expander(f"{var} 校准", expanded=True):
        method = st.radio("校准方式", ["quantile", "manual"], horizontal=True, key=f"method_{var}")
        q25, q50, q75 = quantile_thresholds(df[var])
        st.caption(f"自动分位数：P25={q25}, P50={q50}, P75={q75}")
        if q25 == q50 or q50 == q75:
            st.warning("P25/P50/P75 存在重复，可能有天花板效应或地板效应，建议手动设置。")
        if method == "manual":
            c1, c2, c3 = st.columns(3)
            low = c1.number_input("完全非隶属", value=float(q25), key=f"low_{var}")
            mid = c2.number_input("交叉点", value=float(q50), key=f"mid_{var}")
            high = c3.number_input("完全隶属", value=float(q75), key=f"high_{var}")
            thresholds = [low, mid, high]
        else:
            thresholds = [q25, q50, q75]
        calibration[var] = {"method": method, "thresholds": thresholds}

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
