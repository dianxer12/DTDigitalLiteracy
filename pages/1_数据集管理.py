from __future__ import annotations

import shutil

import pandas as pd
import streamlit as st

from utils.dataset_utils import create_metadata, read_table
from utils.display_utils import dataframe_from_json
from utils.file_store import (
    DEFAULT_PROJECT_ID,
    copy_uploaded_file,
    datasets_dir,
    ensure_default_project,
    get_dataset_dir,
    list_datasets,
    new_id,
    safe_name,
)


st.set_page_config(page_title="数据集管理", layout="wide")
project_dir = ensure_default_project()

st.title("数据集管理")

uploaded = st.file_uploader("上传 Excel 或 CSV 数据", type=["xlsx", "xls", "csv"])
dataset_name = st.text_input("数据集名称", placeholder="例如：教师数字素养问卷数据")

if uploaded and st.button("保存并生成元数据", type="primary"):
    dataset_id = new_id("dataset")
    ddir = datasets_dir(DEFAULT_PROJECT_ID) / dataset_id
    original_dir = ddir / "original"
    temp_original = copy_uploaded_file(uploaded, original_dir)
    try:
        df = read_table(temp_original)
        name = dataset_name.strip() or safe_name(uploaded.name.rsplit(".", 1)[0])
        dataset = create_metadata(ddir, df, dataset_id, name, temp_original)
        st.success(f"数据集已保存：{dataset['dataset_id']}")
    except Exception as exc:
        shutil.rmtree(ddir, ignore_errors=True)
        st.error(f"数据集处理失败：{exc}")

st.divider()
datasets = list_datasets(DEFAULT_PROJECT_ID)
st.subheader("已有数据集")
if not datasets:
    st.info("暂无数据集。")
    st.stop()

st.dataframe(dataframe_from_json(datasets), use_container_width=True)
options = {f"{d['name']} ({d['dataset_id']})": d["dataset_id"] for d in datasets}
selected_label = st.selectbox("选择数据集查看", list(options.keys()))
dataset_id = options[selected_label]
ddir = get_dataset_dir(dataset_id, DEFAULT_PROJECT_ID)

df = pd.read_csv(ddir / "prepared" / "data.csv")
columns = pd.read_json(ddir / "metadata" / "columns.json")

st.subheader("前20行数据")
st.dataframe(df.head(20), use_container_width=True)

st.subheader("变量信息")
st.dataframe(columns, use_container_width=True)

st.link_button("基于此数据运行 fsQCA", "2_新建fsQCA分析")
