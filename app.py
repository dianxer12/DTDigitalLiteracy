from __future__ import annotations

import streamlit as st

from utils.display_utils import dataframe_from_json
from utils.file_store import DEFAULT_PROJECT_ID, ensure_default_project, list_datasets, list_runs, read_json


st.set_page_config(page_title="科研数据分析平台 MVP", layout="wide")

project_dir = ensure_default_project()
project = read_json(project_dir / "project.json", {})

st.title("科研数据分析平台 MVP")
st.caption("文件系统存储 · 无数据库 · 第一版支持 fsQCA")

st.subheader("项目概览")
col1, col2, col3 = st.columns(3)
datasets = list_datasets(DEFAULT_PROJECT_ID)
runs = list_runs(DEFAULT_PROJECT_ID)
col1.metric("项目", project.get("name", DEFAULT_PROJECT_ID))
col2.metric("数据集数量", len(datasets))
col3.metric("分析记录数量", len(runs))

st.divider()
st.subheader("数据集列表")
if datasets:
    st.dataframe(dataframe_from_json(datasets), width="stretch")
else:
    st.info("还没有数据集。请进入「数据集管理」页面上传 Excel 或 CSV。")

st.subheader("分析记录列表")
if runs:
    st.dataframe(dataframe_from_json(runs), width="stretch")
else:
    st.info("还没有分析记录。请进入「新建fsQCA分析」页面创建分析。")
