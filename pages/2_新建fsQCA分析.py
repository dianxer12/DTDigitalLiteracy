from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.dataset_utils import load_prepared_data, numeric_columns, quantile_thresholds
from utils.file_store import (
    create_analysis_spec,
    get_dataset_dir,
    list_analysis_specs,
    list_datasets,
    list_runs,
    read_json,
    study_dir,
    update_analysis_spec,
)
from utils.fsqca_runner import create_run, run_fsqca
from utils.presets import get_variable_labels
from utils.style import inject_css, render_sidebar_nav


inject_css()
study_id = render_sidebar_nav()

_var_labels = get_variable_labels()


def _label_of(v: str) -> str:
    lbl = _var_labels.get(v)
    return f"{lbl}（{v}）" if lbl else v


def _looks_scored(d: dict, df: pd.DataFrame) -> bool:
    if "_scored" in d.get("name", "").lower():
        return True
    dim_prefixes = ("os_", "we_", "dc_", "dl_")
    return df.shape[1] <= 25 and any(str(c).startswith(dim_prefixes) for c in df.columns)


def _load_dataset_options(study_id: str) -> tuple[list[dict], dict[str, bool]]:
    datasets = list_datasets(study_id)
    scored_map: dict[str, bool] = {}
    for d in datasets:
        try:
            df = load_prepared_data(get_dataset_dir(d["dataset_id"], study_id))
            scored_map[d["dataset_id"]] = _looks_scored(d, df)
        except Exception:
            scored_map[d["dataset_id"]] = False
    return datasets, scored_map


def _dataset_option_label(d: dict, scored_map: dict[str, bool]) -> str:
    tag = "维度数据" if scored_map.get(d["dataset_id"]) else "原始数据"
    return f"{d.get('name', d['dataset_id'])}｜{tag}｜{d['dataset_id']}"


def _run_spec(spec: dict, dataset: dict, df: pd.DataFrame) -> None:
    params = spec.get("default_params", {})
    run_dir = create_run(
        study_dir=study_dir(study_id),
        dataset=dataset,
        df=df,
        outcome=spec["outcome"],
        conditions=spec["conditions"],
        calibration=spec["calibration"],
        incl_cut=float(params.get("incl_cut", 0.8)),
        pri_cut=float(params.get("pri_cut", 0.7)),
        n_cut=int(params.get("n_cut", 1)),
        run_low=bool(params.get("run_low", True)),
        robustness=bool(params.get("robustness", False)),
        spec=spec,
    )
    with st.spinner("正在调用 Rscript 运行 fsQCA..."):
        run_fsqca(run_dir)
    status = read_json(run_dir / "status.json", {})
    if status.get("state") == "completed":
        st.success(f"运行完成：{run_dir.name}")
        st.page_link("pages/3_分析结果.py", label="查看分析结果", icon=":material/description:")
    else:
        st.error(status.get("message", "运行失败"))
    st.code(str(run_dir))


def _spec_summary(spec: dict, dataset_names: dict[str, str]) -> dict:
    params = spec.get("default_params", {})
    return {
        "方案名称": spec.get("name", ""),
        "算法": spec.get("algorithm", "-"),
        "关联数据集": "；".join(dataset_names.get(i, i) for i in spec.get("dataset_ids", [])) or "—",
        "结果变量": _label_of(spec.get("outcome", "")),
        "条件变量": "；".join(_label_of(v) for v in spec.get("conditions", [])),
        "一致性阈值": params.get("incl_cut"),
        "PRI 阈值": params.get("pri_cut"),
        "案例数阈值": params.get("n_cut"),
        "低结果分析": "是" if params.get("run_low") else "否",
        "稳健性检验": "是" if params.get("robustness") else "否",
        "更新时间": spec.get("updated_at", spec.get("created_at", "")),
    }


def _run_history_rows(spec: dict, runs: list[dict], dataset_names: dict[str, str]) -> list[dict]:
    rows = []
    for run in runs:
        if run.get("spec_id") != spec.get("spec_id"):
            continue
        rows.append({
            "运行ID": run.get("run_id"),
            "数据集": run.get("dataset_name") or dataset_names.get(run.get("dataset_id"), run.get("dataset_id")),
            "状态": run.get("status"),
            "创建时间": run.get("created_at"),
        })
    return rows


st.title("分析方案")
st.caption("分析方案把算法、数据集、变量、校准锚点和运行参数绑定起来；同一方案可以反复运行，形成多个结果版本。")

datasets, scored_map = _load_dataset_options(study_id)
if not datasets:
    st.info("请先在「数据集」页面上传数据并构建维度。")
    st.stop()

scored_datasets = [d for d in datasets if scored_map.get(d["dataset_id"])]
if not scored_datasets:
    st.warning("当前研究还没有维度得分数据集。请先到「数据集 → 构建维度」计算维度得分。")
    st.stop()

MODEL_PRESETS = {
    "5条件DC维度模型": {
        "outcome": "dl_total",
        "conditions": ["os_total", "we_total", "dc_teaching_learning", "dc_assessment_feedback", "dc_facilitating_digital"],
        "desc": "组织支持、工作投入与 3 个数字胜任力维度共同解释数字素养",
    },
    "3条件总模型": {
        "outcome": "dl_total",
        "conditions": ["os_total", "we_total", "dc_total"],
        "desc": "组织支持总分、工作投入总分、数字胜任力总分共同解释数字素养",
    },
}

tab_create, tab_existing = st.tabs(["新建/运行方案", "已有方案"])

with tab_existing:
    specs = list_analysis_specs(study_id)
    if not specs:
        st.info("当前研究还没有保存的分析方案。")
    else:
        runs = list_runs(study_id)
        rows = []
        dataset_names = {d["dataset_id"]: d.get("name", d["dataset_id"]) for d in datasets}
        for spec in specs:
            spec_runs = [r for r in runs if r.get("spec_id") == spec["spec_id"]]
            rows.append({
                "方案": spec["name"],
                "算法": spec.get("algorithm", "-"),
                "数据集": "；".join(dataset_names.get(i, i) for i in spec.get("dataset_ids", [])),
                "结果变量": _label_of(spec.get("outcome", "")),
                "条件数": len(spec.get("conditions", [])),
                "运行次数": len(spec_runs),
                "更新时间": spec.get("updated_at", spec.get("created_at", "")),
                "spec_id": spec["spec_id"],
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

        spec_options = {f"{s['name']}｜{s['spec_id']}": s for s in specs}
        chosen = st.selectbox("选择方案", list(spec_options.keys()))
        spec = spec_options[chosen]

        st.subheader("方案详情")
        st.dataframe(pd.DataFrame([_spec_summary(spec, dataset_names)]), width="stretch", hide_index=True)

        with st.expander("编辑方案", expanded=False):
            linked_ids = [i for i in spec.get("dataset_ids", []) if i in {d["dataset_id"] for d in scored_datasets}]
            ds_label_map = {_dataset_option_label(d, scored_map): d["dataset_id"] for d in scored_datasets}
            selected_dataset_labels = [
                label for label, dsid in ds_label_map.items()
                if dsid in linked_ids
            ]
            edit_name = st.text_input("方案名称", value=spec.get("name", ""), key=f"edit_name_{spec['spec_id']}")
            edit_desc = st.text_area("方案说明", value=spec.get("description", ""), key=f"edit_desc_{spec['spec_id']}")
            edit_dataset_labels = st.multiselect(
                "关联数据集",
                list(ds_label_map.keys()),
                default=selected_dataset_labels,
                key=f"edit_datasets_{spec['spec_id']}",
            )
            edit_dataset_ids = [ds_label_map[label] for label in edit_dataset_labels]

            edit_ref_dataset = next((d for d in scored_datasets if d["dataset_id"] in edit_dataset_ids), scored_datasets[0])
            edit_df = load_prepared_data(get_dataset_dir(edit_ref_dataset["dataset_id"], study_id))
            edit_num_cols = numeric_columns(edit_df)

            current_outcome = spec.get("outcome") if spec.get("outcome") in edit_num_cols else edit_num_cols[0]
            edit_outcome = st.selectbox(
                "结果变量",
                edit_num_cols,
                index=edit_num_cols.index(current_outcome),
                format_func=_label_of,
                key=f"edit_outcome_{spec['spec_id']}",
            )
            edit_condition_candidates = [c for c in edit_num_cols if c != edit_outcome]
            edit_conditions = st.multiselect(
                "条件变量",
                edit_condition_candidates,
                default=[c for c in spec.get("conditions", []) if c in edit_condition_candidates],
                format_func=_label_of,
                key=f"edit_conditions_{spec['spec_id']}",
            )

            st.markdown("##### 校准锚点")
            edit_calibration = {}
            for var in [edit_outcome] + edit_conditions:
                existing = spec.get("calibration", {}).get(var, {})
                existing_thresholds = existing.get("thresholds")
                q25, q50, q75 = quantile_thresholds(edit_df[var])
                default_thresholds = existing_thresholds if existing_thresholds and len(existing_thresholds) == 3 else [q25, q50, q75]
                with st.expander(f"{_label_of(var)}", expanded=False):
                    method = st.radio(
                        "校准方式",
                        ["quantile", "manual"],
                        index=0 if existing.get("method", "quantile") == "quantile" else 1,
                        horizontal=True,
                        key=f"edit_method_{spec['spec_id']}_{var}",
                    )
                    st.caption(f"自动分位数：P25={q25}, P50={q50}, P75={q75}")
                    if method == "manual":
                        c1, c2, c3 = st.columns(3)
                        low = c1.number_input("完全非隶属", value=float(default_thresholds[0]), key=f"edit_low_{spec['spec_id']}_{var}")
                        mid = c2.number_input("交叉点", value=float(default_thresholds[1]), key=f"edit_mid_{spec['spec_id']}_{var}")
                        high = c3.number_input("完全隶属", value=float(default_thresholds[2]), key=f"edit_high_{spec['spec_id']}_{var}")
                        thresholds = [low, mid, high]
                    else:
                        thresholds = [q25, q50, q75]
                    edit_calibration[var] = {"method": method, "thresholds": thresholds}

            st.markdown("##### 默认运行参数")
            old_params = spec.get("default_params", {})
            c1, c2, c3 = st.columns(3)
            edit_incl = c1.number_input("一致性阈值", min_value=0.0, max_value=1.0, value=float(old_params.get("incl_cut", 0.8)), step=0.01, key=f"edit_incl_{spec['spec_id']}")
            edit_pri = c2.number_input("PRI 阈值", min_value=0.0, max_value=1.0, value=float(old_params.get("pri_cut", 0.7)), step=0.01, key=f"edit_pri_{spec['spec_id']}")
            edit_n = c3.number_input("案例数阈值", min_value=1, value=int(old_params.get("n_cut", 1)), step=1, key=f"edit_n_{spec['spec_id']}")
            edit_low = st.checkbox("运行低结果分析", value=bool(old_params.get("run_low", True)), key=f"edit_run_low_{spec['spec_id']}")
            edit_robust = st.checkbox("运行稳健性检验", value=bool(old_params.get("robustness", False)), key=f"edit_robust_{spec['spec_id']}")

            if st.button("保存方案修改", type="primary", key=f"save_edit_{spec['spec_id']}"):
                if not edit_dataset_ids:
                    st.error("至少关联一个数据集。")
                elif not edit_conditions:
                    st.error("至少选择一个条件变量。")
                else:
                    update_analysis_spec(
                        study_id,
                        spec["spec_id"],
                        {
                            "name": edit_name,
                            "description": edit_desc,
                            "dataset_ids": edit_dataset_ids,
                            "outcome": edit_outcome,
                            "conditions": edit_conditions,
                            "calibration": edit_calibration,
                            "default_params": {
                                "incl_cut": float(edit_incl),
                                "pri_cut": float(edit_pri),
                                "n_cut": int(edit_n),
                                "run_low": edit_low,
                                "robustness": edit_robust,
                            },
                        },
                    )
                    st.success("方案已更新。")
                    st.rerun()

        st.subheader("运行历史")
        history_rows = _run_history_rows(spec, runs, dataset_names)
        if history_rows:
            st.dataframe(pd.DataFrame(history_rows), width="stretch", hide_index=True)
        else:
            st.info("这个方案还没有运行记录。")

        st.subheader("运行方案")
        linked = [d for d in datasets if d["dataset_id"] in spec.get("dataset_ids", [])]
        if not linked:
            st.warning("该方案关联的数据集不存在，可能已被删除。")
        else:
            dataset_options = {_dataset_option_label(d, scored_map): d for d in linked}
            dataset = dataset_options[st.selectbox("选择本次运行使用的数据集", list(dataset_options.keys()))]
            df = load_prepared_data(get_dataset_dir(dataset["dataset_id"], study_id))
            missing = [v for v in [spec["outcome"]] + spec["conditions"] if v not in df.columns]
            if missing:
                st.error(f"当前数据集缺少方案变量：{missing}")
            elif st.button("运行选中方案", type="primary"):
                _run_spec(spec, dataset, df)

with tab_create:
    dataset_options = {_dataset_option_label(d, scored_map): d for d in scored_datasets}
    selected_label = st.selectbox("选择数据集", list(dataset_options.keys()))
    dataset = dataset_options[selected_label]
    ddir = get_dataset_dir(dataset["dataset_id"], study_id)
    df = load_prepared_data(ddir)
    num_cols = numeric_columns(df)

    c_info1, c_info2, c_info3 = st.columns(3)
    c_info1.metric("数据集", dataset.get("name", dataset["dataset_id"]))
    c_info2.metric("样本数", df.shape[0])
    c_info3.metric("变量数", df.shape[1])

    with st.expander("数据预览", expanded=False):
        st.dataframe(df.head(10), width="stretch")

    st.subheader("1. 选择模型")
    c_model, c_name = st.columns([1, 2])
    with c_model:
        preset_choice = st.selectbox("预设模型", ["自定义"] + list(MODEL_PRESETS.keys()), index=1)
    with c_name:
        default_name = preset_choice if preset_choice != "自定义" else "自定义 fsQCA 方案"
        spec_name = st.text_input("方案名称", value=default_name)
    spec_desc = st.text_area("方案说明（可选）", value=MODEL_PRESETS.get(preset_choice, {}).get("desc", ""))

    preset = MODEL_PRESETS.get(preset_choice)
    if preset and preset["outcome"] in num_cols and all(c in num_cols for c in preset["conditions"]):
        outcome_default = preset["outcome"]
        cond_defaults = preset["conditions"]
        st.success(preset["desc"])
    else:
        outcome_default = num_cols[0]
        cond_defaults = [c for c in num_cols if c != outcome_default][: min(5, len(num_cols) - 1)]
        if preset:
            missing = [v for v in [preset["outcome"]] + preset["conditions"] if v not in num_cols]
            st.warning(f"当前数据集缺少预设变量：{missing}")

    st.subheader("2. 变量选择")
    outcome = st.selectbox("结果变量", num_cols, index=num_cols.index(outcome_default), format_func=_label_of)
    condition_candidates = [c for c in num_cols if c != outcome]
    conditions = st.multiselect(
        "条件变量",
        condition_candidates,
        default=[c for c in cond_defaults if c in condition_candidates],
        format_func=_label_of,
    )
    if not conditions:
        st.warning("请选择至少一个条件变量。")
        st.stop()

    st.subheader("3. 校准设置")
    st.caption("DC 维度建议手动设为 [2, 3, 4]；DL 结果变量建议 [4, 4.5, 5]；其余可用分位数自动计算。")

    calibration = {}
    for var in [outcome] + conditions:
        with st.expander(f"{_label_of(var)} 校准", expanded=False):
            method = st.radio("校准方式", ["quantile", "manual"], horizontal=True, key=f"method_{var}")
            q25, q50, q75 = quantile_thresholds(df[var])
            st.caption(f"自动分位数：P25={q25}, P50={q50}, P75={q75}")
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

    st.subheader("4. 运行参数")
    c1, c2, c3 = st.columns(3)
    incl_cut = c1.number_input("一致性阈值", min_value=0.0, max_value=1.0, value=0.80, step=0.01)
    pri_cut = c2.number_input("PRI 阈值", min_value=0.0, max_value=1.0, value=0.70, step=0.01)
    n_cut = c3.number_input("案例数阈值", min_value=1, value=1, step=1)
    run_low = st.checkbox("运行低结果分析", value=True)
    robustness = st.checkbox("运行稳健性检验", value=False)

    params = {
        "incl_cut": float(incl_cut),
        "pri_cut": float(pri_cut),
        "n_cut": int(n_cut),
        "run_low": run_low,
        "robustness": robustness,
    }

    save_only, save_and_run = st.columns(2)
    with save_only:
        if st.button("保存分析方案", type="secondary", use_container_width=True):
            spec = create_analysis_spec(
                study_id,
                name=spec_name,
                description=spec_desc,
                algorithm="fsQCA",
                dataset_ids=[dataset["dataset_id"]],
                outcome=outcome,
                conditions=conditions,
                calibration=calibration,
                default_params=params,
            )
            st.success(f"方案已保存：{spec['name']}")
            st.rerun()
    with save_and_run:
        if st.button("保存并运行", type="primary", use_container_width=True):
            spec = create_analysis_spec(
                study_id,
                name=spec_name,
                description=spec_desc,
                algorithm="fsQCA",
                dataset_ids=[dataset["dataset_id"]],
                outcome=outcome,
                conditions=conditions,
                calibration=calibration,
                default_params=params,
            )
            _run_spec(spec, dataset, df)
