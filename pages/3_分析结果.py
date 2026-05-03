from __future__ import annotations

import json

import streamlit as st

from utils.display_utils import download_file, show_csv_table
from utils.file_store import DEFAULT_PROJECT_ID, ensure_default_project, get_run_dir, list_runs, read_json


st.set_page_config(page_title="分析结果", layout="wide")
ensure_default_project()

st.title("分析结果")
runs = list_runs(DEFAULT_PROJECT_ID)
if not runs:
    st.info("暂无分析记录。")
    st.stop()

options = {f"{r['run_id']} | {r.get('dataset_name', '')} | {r.get('status', '')}": r["run_id"] for r in runs}
run_id = options[st.selectbox("选择 run", list(options.keys()))]
run_dir = get_run_dir(run_id, DEFAULT_PROJECT_ID)

status = read_json(run_dir / "status.json", {})
config = read_json(run_dir / "config.json", {})

st.subheader("运行状态")
st.json(status)

tables_dir = run_dir / "output" / "tables"
figures_dir = run_dir / "output" / "figures"
report_dir = run_dir / "output" / "report"
files_dir = run_dir / "output" / "files"
logs_dir = run_dir / "output" / "logs"

st.subheader("结果表格")
csv_files = sorted(tables_dir.glob("*.csv"))
if csv_files:
    for path in csv_files:
        show_csv_table(path)
else:
    st.info("没有 CSV 结果表。")

st.subheader("结果图片")
for path in sorted(figures_dir.glob("*.png")):
    st.image(str(path), caption=path.name, use_container_width=True)
for path in sorted(figures_dir.glob("*.svg")):
    st.image(str(path), caption=path.name, use_container_width=True)

st.subheader("报告")
report = report_dir / "report.md"
if report.exists():
    st.markdown(report.read_text(encoding="utf-8"))
else:
    st.info("没有报告文件。")

st.subheader("下载文件")
for folder in [files_dir, tables_dir, figures_dir, report_dir, logs_dir]:
    for path in sorted(folder.glob("*")):
        if path.is_file():
            download_file(path)

st.subheader("复现配置 config.json")
st.code(json.dumps(config, ensure_ascii=False, indent=2), language="json")
