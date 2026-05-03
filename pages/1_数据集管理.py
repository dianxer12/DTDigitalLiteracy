"""
数据集管理 – 上传问卷原始数据 → 构建维度 → 生成得分 → 进入 fsQCA
"""
from __future__ import annotations

import shutil
from pathlib import Path

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
from utils.presets import build_presets
from utils.scoring import ScaleDefinition, compute_scale_scores

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(page_title="数据集管理", layout="wide")
ensure_default_project()

st.title("数据集管理")

# ---------------------------------------------------------------------------
# Tab 1 – Upload
# ---------------------------------------------------------------------------
tab_upload, tab_scoring = st.tabs(["📤 上传数据", "🧮 构建维度"])

# ========================== TAB: UPLOAD ======================================
with tab_upload:
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
            create_metadata(ddir, df, dataset_id, name, temp_original)
            st.session_state["last_dataset_id"] = dataset_id
            st.success(f"数据集已保存：{dataset_id}")
            st.info("👉 切换到「构建维度」标签页进行量表配置")
        except Exception as exc:
            shutil.rmtree(ddir, ignore_errors=True)
            st.error(f"数据集处理失败：{exc}")

    st.divider()
    datasets = list_datasets(DEFAULT_PROJECT_ID)
    st.subheader("已有数据集")
    if not datasets:
        st.info("暂无数据集。")
    else:
        st.dataframe(dataframe_from_json(datasets), use_container_width=True)

# ========================== TAB: SCORING ======================================
with tab_scoring:
    st.subheader("维度构建与计分")

    datasets = list_datasets(DEFAULT_PROJECT_ID)
    if not datasets:
        st.info("请先在「上传数据」标签页上传数据。")
        st.stop()

    # Select dataset
    options = {f"{d['name']} ({d['dataset_id']})": d for d in datasets}
    selected_label = st.selectbox("选择数据集", list(options.keys()))
    dataset = options[selected_label]
    ddir = get_dataset_dir(dataset["dataset_id"], DEFAULT_PROJECT_ID)
    prepared_path = ddir / "prepared" / "data.csv"

    if not prepared_path.exists():
        st.error("数据文件不存在。")
        st.stop()

    df = pd.read_csv(prepared_path)
    n_cols = df.shape[1]

    st.caption(f"数据维度：{df.shape[0]} 行 × {n_cols} 列")

    # ---- Column selector for metadata stripping ----
    with st.expander("🔧 数据列浏览", expanded=True):
        col_info = pd.DataFrame(
            {
                "索引": list(range(n_cols)),
                "列名": df.columns.tolist(),
                "示例值": df.iloc[0].astype(str).tolist(),
            }
        )
        st.dataframe(col_info, use_container_width=True, height=300)

    # ---- Metadata stripping ----
    st.subheader("步骤1：剔除元数据列")
    st.caption("选中需要排除的列（如序号、提交时间、姓名等），剩余列将作为量表题项。")

    metadata_cols = st.multiselect(
        "排除列（索引）",
        options=list(range(n_cols)),
        default=list(range(8)),  # default: first 8 columns are metadata
        format_func=lambda i: f"[{i}] {str(df.columns[i])[:40]}",
    )

    # Compute usable columns
    usable_indices = [i for i in range(n_cols) if i not in metadata_cols]
    n_usable = len(usable_indices)

    if n_usable == 0:
        st.warning("所有列都被排除了，请至少保留一列。")
        st.stop()

    st.success(f"排除 {len(metadata_cols)} 列后，剩余 {n_usable} 个题项列。")

    # ---- Apply preset ----
    st.subheader("步骤2：配置量表与维度")

    use_preset = st.checkbox(
        "使用预设量表配置（双师型护理教师数字素养 4 量表）",
        value=True,
        help="自动配置 OS/WE/DC/DL 四个量表及其子维度",
    )

    if use_preset:
        # Auto-compute ranges from usable columns
        # The preset expects 0-based indices into the usable data
        if n_usable != 95:
            st.warning(f"预设期望 95 个题项，当前有 {n_usable} 个。请检查排除列是否正确。")

        # Build presets with 0-based indices into the USABLE columns only
        preset_map = build_presets(
            os_range=(0, 23),
            we_range=(23, 40),
            dc_range=(40, 62),
            dl_range=(62, 95),
        )

        st.success("已加载预设：OS(23) → WE(17) → DC(22) → DL(33)")

        # Show scales overview
        scale_summary = []
        for name, scale in preset_map.items():
            dims_str = ", ".join(d.label for d in scale.dimensions)
            rev_str = f"，{len(scale.reverse_items)} 题反向" if scale.reverse_items else ""
            scale_summary.append(
                {
                    "量表": f"{name} - {scale.label}",
                    "题项数": len(scale.columns),
                    "维度": f"{len(scale.dimensions)} 个",
                    "维度列表": dims_str,
                    "反向题": rev_str,
                }
            )
        st.dataframe(pd.DataFrame(scale_summary), use_container_width=True)

        # Show detailed OS reverse items
        with st.expander("OS 反向题详情"):
            os_scale = preset_map["OS"]
            os_cols = [df.columns[usable_indices[i]] for i in os_scale.columns]
            rev_info = pd.DataFrame(
                {
                    "量表内序号": [i + 1 for i in os_scale.reverse_items],
                    "列名": [os_cols[i] for i in os_scale.reverse_items],
                }
            )
            st.dataframe(rev_info, use_container_width=True)

        # ---- Compute scores ----
        if st.button("🔢 计算维度得分", type="primary"):
            with st.spinner("正在计算各维度得分..."):
                # Subset to usable columns
                usable_df = df.iloc[:, usable_indices].copy()
                usable_df.columns = [str(c) for c in usable_df.columns]

                # Ensure numeric
                for c in usable_df.columns:
                    usable_df[c] = pd.to_numeric(usable_df[c], errors="coerce")

                # Compute scores for each scale, then merge
                score_dfs = []
                for scale in preset_map.values():
                    scored = compute_scale_scores(usable_df, scale)
                    score_dfs.append(scored)

                all_scores = pd.concat(score_dfs, axis=1)

                # Save scored data as a NEW prepared dataset
                scored_id = new_id("scored")
                scored_dir = datasets_dir(DEFAULT_PROJECT_ID) / scored_id
                meta = create_metadata(
                    scored_dir,
                    all_scores,
                    scored_id,
                    f"{dataset['name']}_scored",
                    Path("scored_data.csv"),
                )

                st.session_state["last_scored_id"] = scored_id
                st.success(f"维度得分已保存：{scored_id}")

            # Show preview
            st.subheader("维度得分预览")
            st.dataframe(all_scores.head(20), use_container_width=True)

            # Summary stats
            st.subheader("描述统计")
            desc = all_scores.describe().T
            st.dataframe(desc, use_container_width=True)

            st.info(f"👉 前往「新建fsQCA分析」页面，选择数据集「{meta['name']}」开始分析")
    else:
        st.info("手动配置暂未实现，请勾选预设配置。")
