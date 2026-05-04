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
    delete_dataset,
    ensure_default_project,
    get_dataset_dir,
    list_datasets,
    new_id,
    safe_name,
)
from utils.presets import build_presets
from utils.scoring import DimensionDef, ScaleDefinition, compute_scale_scores

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(page_title="数据集管理", layout="wide")
ensure_default_project()

st.title("数据集管理")

# Session-state keys
if "preset_map_editable" not in st.session_state:
    st.session_state["preset_map_editable"] = None
if "use_preset" not in st.session_state:
    st.session_state["use_preset"] = True

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
            st.session_state["preset_map_editable"] = None  # reset for new data
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
        st.dataframe(dataframe_from_json(datasets), width="stretch")

        # Delete dataset – confirmation via session state
        st.divider()
        st.caption("删除数据集（包含其所有分析记录）")
        if "delete_confirm_id" not in st.session_state:
            st.session_state["delete_confirm_id"] = None

        ds_options = [f"{d['name']} ({d['dataset_id']})" for d in datasets]
        ds_map = {f"{d['name']} ({d['dataset_id']})": d["dataset_id"] for d in datasets}
        col_ds, col_btn = st.columns([3, 1])
        with col_ds:
            del_choice = st.selectbox("选择要删除的数据集", ds_options, key="del_dataset_select")
        with col_btn:
            if st.button("🗑️ 删除", key="del_dataset_btn", type="secondary"):
                st.session_state["delete_confirm_id"] = ds_map[del_choice]

        if st.session_state["delete_confirm_id"]:
            target_id = st.session_state["delete_confirm_id"]
            st.warning(f"⚠️ 确认删除数据集 `{target_id}`？此操作不可撤销，其关联的所有分析记录也会被删除。")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ 确认删除", key="del_confirm", type="primary"):
                    delete_dataset(target_id)
                    st.session_state["delete_confirm_id"] = None
                    st.session_state.pop("del_dataset_select", None)
                    st.success("已删除。")
                    st.rerun()
            with c2:
                if st.button("❌ 取消", key="del_cancel"):
                    st.session_state["delete_confirm_id"] = None
                    st.rerun()

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

    # ---- Column browser ----
    with st.expander("🔧 数据列浏览", expanded=True):
        col_info = pd.DataFrame({
            "索引": list(range(n_cols)),
            "列名": df.columns.tolist(),
            "示例值": df.iloc[0].astype(str).tolist(),
        })
        st.dataframe(col_info, width="stretch", height=300)

    # ---- Step 1: Metadata stripping ----
    st.subheader("步骤1：剔除元数据列")
    st.caption("选中需要排除的列（如序号、提交时间、姓名等），剩余列将作为量表题项。")

    metadata_cols = st.multiselect(
        "排除列（索引）",
        options=list(range(n_cols)),
        default=list(range(8)),
        format_func=lambda i: f"[{i}] {str(df.columns[i])[:40]}",
    )
    usable_indices = [i for i in range(n_cols) if i not in metadata_cols]
    n_usable = len(usable_indices)
    if n_usable == 0:
        st.warning("所有列都被排除了，请至少保留一列。")
        st.stop()
    st.success(f"排除 {len(metadata_cols)} 列后，剩余 {n_usable} 个题项列。")

    # ---- Step 2: Load / reset preset ----
    st.subheader("步骤2：加载预设配置")
    c1, c2 = st.columns([2, 1])
    with c1:
        st.session_state["use_preset"] = st.checkbox(
            "使用预设量表配置（双师型护理教师数字素养 4 量表）",
            value=st.session_state["use_preset"],
        )
    with c2:
        if st.button("🔄 重置为预设默认值"):
            st.session_state["preset_map_editable"] = None
            st.rerun()

    if not st.session_state["use_preset"]:
        st.info("自定义配置暂未实现，请勾选预设后编辑。")
        st.stop()

    if n_usable != 95:
        st.warning(f"预设期望 95 个题项，当前有 {n_usable} 个。请检查排除列是否正确。")

    # Load presets (or from session)
    if st.session_state["preset_map_editable"] is None:
        preset_map = build_presets(
            os_range=(0, 23), we_range=(23, 40), dc_range=(40, 62), dl_range=(62, 95),
        )
    else:
        preset_map = st.session_state["preset_map_editable"]

    usable_col_names = [str(df.columns[usable_indices[i]]) for i in range(n_usable)]

    st.success("已加载预设：OS(23) → WE(17) → DC(22) → DL(33)")

    # ---- Step 3: Edit ----
    st.subheader("步骤3：编辑量表配置")
    st.caption("展开每个量表可修改反向题、维度名称、维度内题项和聚合方式。")

    edited_map: dict[str, ScaleDefinition] = {}

    for scale_name, scale in preset_map.items():
        n_items = len(scale.columns)
        with st.expander(
            f"📋 {scale_name} - {scale.label}（{n_items} 题，{len(scale.dimensions)} 维度）",
            expanded=False,
        ):
            # ---------- Reverse items ----------
            st.markdown("##### 反向题项")
            st.caption("勾选需反向计分的题（公式：最大值 - x）")
            cols_per_row = 12
            n_rows = (n_items + cols_per_row - 1) // cols_per_row
            new_rev: list[int] = []
            for row_idx in range(n_rows):
                row_cols = st.columns(cols_per_row)
                for c in range(cols_per_row):
                    i = row_idx * cols_per_row + c
                    if i >= n_items:
                        break
                    is_rev = i in scale.reverse_items
                    if row_cols[c].checkbox(
                        f"第{i+1}题", value=is_rev, key=f"rev_{scale_name}_{i}"
                    ):
                        new_rev.append(i)

            st.divider()

            # ---------- Dimensions ----------
            st.markdown("##### 维度定义")

            new_dimensions: list[DimensionDef] = []
            for dim_idx, dim in enumerate(scale.dimensions):
                with st.container():
                    dc1, dc2, dc3 = st.columns([2, 2, 1])
                    new_name = dc1.text_input(
                        "变量名", value=dim.name,
                        key=f"dim_name_{scale_name}_{dim_idx}",
                        help="英文字母+下划线，如 os_work_support",
                    )
                    new_label = dc2.text_input(
                        "中文标签", value=dim.label,
                        key=f"dim_label_{scale_name}_{dim_idx}",
                    )
                    agg_options = ["mean", "sum"]
                    new_agg = dc3.selectbox(
                        "聚合", agg_options,
                        index=0 if dim.aggregation == "mean" else 1,
                        format_func=lambda x: "均值" if x == "mean" else "求和",
                        key=f"dim_agg_{scale_name}_{dim_idx}",
                    )

                    # Item picker for this dimension
                    st.caption(f"题项（当前 {len(dim.items)} 题）")
                    item_rows = (n_items + 9) // 10
                    new_items: list[int] = []
                    for ir in range(item_rows):
                        icols = st.columns(10)
                        for c in range(10):
                            i = ir * 10 + c
                            if i >= n_items:
                                break
                            selected = i in dim.items
                            if icols[c].checkbox(
                                f"第{i+1}题", value=selected,
                                key=f"dimitem_{scale_name}_{dim_idx}_{i}",
                            ):
                                new_items.append(i)

                    if new_items:
                        new_dimensions.append(DimensionDef(
                            name=new_name.strip() or dim.name,
                            label=new_label.strip() or dim.label,
                            items=new_items,
                            aggregation=new_agg,
                        ))
                    else:
                        st.warning(f"「{dim.label}」没有选中任何题项，将跳过。")
                    st.markdown("---")

            # Add dimension button
            if st.button(f"➕ 添加维度到 {scale_name}", key=f"add_dim_{scale_name}"):
                scale.dimensions.append(DimensionDef(
                    name=f"{scale_name.lower()}_new_{len(scale.dimensions)}",
                    label="新维度", items=[], aggregation="mean",
                ))
                st.session_state["preset_map_editable"] = preset_map
                st.rerun()

            edited_map[scale_name] = ScaleDefinition(
                name=scale.name,
                label=scale.label,
                columns=scale.columns,
                reverse_items=new_rev,
                reverse_max=scale.reverse_max,
                dimensions=new_dimensions if new_dimensions else scale.dimensions,
            )

    # Persist
    st.session_state["preset_map_editable"] = edited_map

    # ---- Step 4: Compute ----
    st.subheader("步骤4：计算维度得分")

    if st.button("🔢 计算维度得分", type="primary"):
        with st.spinner("正在计算各维度得分..."):
            usable_df = df.iloc[:, usable_indices].copy()
            usable_df.columns = [str(c) for c in usable_df.columns]
            for c in usable_df.columns:
                usable_df[c] = pd.to_numeric(usable_df[c], errors="coerce")

            score_dfs = []
            for scale in edited_map.values():
                if scale.dimensions:
                    scored = compute_scale_scores(usable_df, scale)
                    score_dfs.append(scored)

            all_scores = pd.concat(score_dfs, axis=1)

            scored_id = new_id("scored")
            scored_dir = datasets_dir(DEFAULT_PROJECT_ID) / scored_id
            meta = create_metadata(
                scored_dir, all_scores, scored_id,
                f"{dataset['name']}_scored", Path("scored_data.csv"),
            )
            st.session_state["last_scored_id"] = scored_id
            st.success(f"✅ 维度得分已保存！")

        st.subheader("维度得分预览")
        st.dataframe(all_scores.head(20), width="stretch")

        st.subheader("描述统计")
        st.dataframe(all_scores.describe().T, width="stretch")

        st.markdown(f"""
        ---
        ### 🎉 维度数据集已创建

        **{meta['name']}**（`{scored_id}`）
        共 **{all_scores.shape[1]}** 个维度变量，**{all_scores.shape[0]}** 条记录。
        """)
        st.page_link("pages/2_新建fsQCA分析.py", label="🚀 前往新建 fsQCA 分析", icon="🚀")
