from __future__ import annotations

import subprocess
import shutil
import tempfile
import textwrap
from pathlib import Path

import pandas as pd

from .file_store import APP_ROOT, ensure_dir, new_id, now_iso, write_json
from .presets import get_variable_labels


def _svg_escape(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _variable_label(var_name: str, var_labels: dict[str, str], include_code: bool = False) -> str:
    raw = str(var_name).strip()
    base = raw[2:] if raw.startswith("f_") else raw
    label = var_labels.get(base, base)
    return f"{label}（{base}）" if include_code and label != base else label


def _formula_to_label(formula: str, var_labels: dict[str, str], include_code: bool = False) -> str:
    if pd.isna(formula) or str(formula).strip() == "":
        return ""
    or_parts = []
    for part in str(formula).split("+"):
        tokens = []
        for token in part.split("*"):
            token = token.strip()
            if not token:
                continue
            negated = token.startswith("~")
            clean = token[1:] if negated else token
            label = _variable_label(clean, var_labels, include_code=include_code)
            tokens.append(f"非{label}" if negated else label)
        if tokens:
            or_parts.append(" × ".join(tokens))
    return " 或 ".join(or_parts)


def _friendly_metric_table(df: pd.DataFrame, var_labels: dict[str, str]) -> pd.DataFrame:
    out = df.copy()
    if "formula" in out.columns:
        out["组态路径"] = out["formula"].map(lambda x: _formula_to_label(x, var_labels))
        out = out.drop(columns=["formula"])
    rename = {
        "path": "路径",
        "solution_type": "解类型",
        "consistency": "一致性",
        "raw_coverage": "原始覆盖率",
        "unique_coverage": "唯一覆盖率",
    }
    return out.rename(columns=rename)


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _save_solution_bars(
    metrics_path: Path,
    output_path: Path,
    title: str,
    var_labels: dict[str, str],
) -> None:
    if not metrics_path.exists():
        return
    df = pd.read_csv(metrics_path)
    inter = df[df["solution_type"] == "intermediate"].copy()
    if inter.empty:
        return

    n = len(inter)
    width = max(900, 260 * n + 180)
    height = 560
    left = 90
    top = 80
    chart_h = 310
    base_y = top + chart_h
    group_w = (width - left - 70) / n
    bar_w = min(42, group_w * 0.18)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<style>text { font-family: "PingFang SC", "STHeiti", "Hiragino Sans GB", "Arial Unicode MS", "Heiti SC", sans-serif; } .small { font-size: 13px; } .label { font-size: 12px; }</style>',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width / 2}" y="34" text-anchor="middle" font-size="20" font-weight="700" fill="#0F172A">{_svg_escape(title)}</text>',
    ]
    for tick in [0, 0.25, 0.5, 0.75, 1.0]:
        y = base_y - tick * chart_h
        lines.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - 45}" y2="{y:.1f}" stroke="#E5E7EB" stroke-width="1"/>')
        lines.append(f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" class="small" fill="#475569">{tick:.2f}</text>')
    lines.append(f'<line x1="{left}" y1="{base_y}" x2="{width - 45}" y2="{base_y}" stroke="#CBD5E1" stroke-width="1.2"/>')

    for i, row in inter.reset_index(drop=True).iterrows():
        cx = left + group_w * i + group_w / 2
        cons = float(row["consistency"])
        cov = float(row["raw_coverage"])
        for offset, value, color in [(-bar_w / 1.8, cons, "#2563EB"), (bar_w / 1.8, cov, "#F59E0B")]:
            h = value * chart_h
            x = cx + offset - bar_w / 2
            y = base_y - h
            lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="3" fill="{color}"/>')
            lines.append(f'<text x="{x + bar_w / 2:.1f}" y="{y - 8:.1f}" text-anchor="middle" class="small" fill="#0F172A">{value:.3f}</text>')
        formula = _formula_to_label(row["formula"], var_labels)
        lines.append(f'<text x="{cx:.1f}" y="{base_y + 30}" text-anchor="middle" font-size="13" font-weight="700" fill="#1E293B">{_svg_escape(str(row["path"]))}</text>')
        for j, wrapped in enumerate(textwrap.wrap(formula, width=16)[:4]):
            lines.append(f'<text x="{cx:.1f}" y="{base_y + 52 + j * 18}" text-anchor="middle" class="label" fill="#334155">{_svg_escape(wrapped)}</text>')

    legend_y = height - 28
    lines.extend([
        f'<rect x="{width / 2 - 125}" y="{legend_y - 12}" width="14" height="14" fill="#2563EB"/>',
        f'<text x="{width / 2 - 104}" y="{legend_y}" class="small" fill="#334155">一致性</text>',
        f'<rect x="{width / 2 + 12}" y="{legend_y - 12}" width="14" height="14" fill="#F59E0B"/>',
        f'<text x="{width / 2 + 33}" y="{legend_y}" class="small" fill="#334155">原始覆盖率</text>',
        '</svg>',
    ])
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _save_config_table(config_path: Path, output_path: Path, title: str) -> None:
    if not config_path.exists():
        return
    df = pd.read_csv(config_path)
    if df.empty:
        return

    status_symbol = {
        "core_present": "●",
        "peripheral_present": "●",
        "core_absent": "⊗",
        "peripheral_absent": "⊙",
        "irrelevant": "—",
    }
    status_color = {
        "core_present": "#1E40AF",
        "peripheral_present": "#60A5FA",
        "core_absent": "#DC2626",
        "peripheral_absent": "#FCA5A5",
        "irrelevant": "#64748B",
    }

    paths = list(df["path"].drop_duplicates())
    conditions = list(df["condition"].drop_duplicates())
    labels = {
        row["condition"]: row["label"]
        for _, row in df.drop_duplicates("condition").iterrows()
    }

    label_w = 360
    cell_w = 130
    row_h = 42
    header_h = 86
    width = label_w + cell_w * len(paths) + 60
    height = header_h + row_h * len(conditions) + 70

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<style>text { font-family: "PingFang SC", "STHeiti", "Hiragino Sans GB", "Arial Unicode MS", "Heiti SC", sans-serif; }</style>',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width / 2}" y="34" text-anchor="middle" font-size="20" font-weight="700" fill="#0F172A">{_svg_escape(title)}</text>',
    ]
    x0 = 30
    y0 = 58
    lines.append(f'<rect x="{x0}" y="{y0}" width="{label_w}" height="{row_h}" fill="#EFF6FF" stroke="#CBD5E1"/>')
    lines.append(f'<text x="{x0 + label_w - 16}" y="{y0 + 27}" text-anchor="end" font-size="14" font-weight="700" fill="#1E3A8A">条件</text>')
    for i, path in enumerate(paths):
        x = x0 + label_w + i * cell_w
        lines.append(f'<rect x="{x}" y="{y0}" width="{cell_w}" height="{row_h}" fill="#EFF6FF" stroke="#CBD5E1"/>')
        lines.append(f'<text x="{x + cell_w / 2}" y="{y0 + 27}" text-anchor="middle" font-size="14" font-weight="700" fill="#1E3A8A">{_svg_escape(path)}</text>')

    for r, cond in enumerate(conditions):
        y = y0 + row_h * (r + 1)
        lines.append(f'<rect x="{x0}" y="{y}" width="{label_w}" height="{row_h}" fill="#F8FAFC" stroke="#CBD5E1"/>')
        label = labels.get(cond, cond)
        lines.append(f'<text x="{x0 + label_w - 16}" y="{y + 27}" text-anchor="end" font-size="13" fill="#0F172A">{_svg_escape(label)}</text>')
        for c, path in enumerate(paths):
            x = x0 + label_w + c * cell_w
            hit = df[(df["condition"] == cond) & (df["path"] == path)]
            status = hit.iloc[0]["status"] if not hit.empty else "irrelevant"
            color = status_color.get(status, "#64748B")
            symbol = status_symbol.get(status, "—")
            size = 24 if "core" in status else 19
            lines.append(f'<rect x="{x}" y="{y}" width="{cell_w}" height="{row_h}" fill="white" stroke="#CBD5E1"/>')
            lines.append(f'<text x="{x + cell_w / 2}" y="{y + 28}" text-anchor="middle" font-size="{size}" fill="{color}">{symbol}</text>')

    legend_y = height - 24
    legend = "● 核心条件存在    ● 边缘条件存在    ⊗ 核心条件缺失    ⊙ 边缘条件缺失    — 无关"
    lines.append(f'<text x="{width / 2}" y="{legend_y}" text-anchor="middle" font-size="13" fill="#334155">{_svg_escape(legend)}</text>')
    lines.append("</svg>")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _build_report(run_dir: Path, config: dict, var_labels: dict[str, str]) -> None:
    tables_dir = run_dir / "output" / "tables"
    report_dir = ensure_dir(run_dir / "output" / "report")

    outcome = config.get("outcome", "")
    conditions = config.get("conditions", [])
    outcome_label = _variable_label(outcome, var_labels)
    thresholds = _read_csv(tables_dir / "calibration_thresholds.csv")
    necessity = _read_csv(tables_dir / "necessity_high.csv")
    metrics_high = _read_csv(tables_dir / "solution_metrics_high.csv")
    overall_high = _read_csv(tables_dir / "solution_overall_high.csv")
    metrics_low = _read_csv(tables_dir / "solution_metrics_low.csv")
    overall_low = _read_csv(tables_dir / "solution_overall_low.csv")

    lines = [
        "# fsQCA 分析报告",
        "",
        "## 1. 分析概况",
        "",
        f"- 数据集：{config.get('dataset_name', '-')}",
        f"- 结果变量：{outcome_label}（{outcome}）",
        "- 条件变量：",
    ]
    lines.extend([f"  - {_variable_label(v, var_labels)}（{v}）" for v in conditions])
    lines.extend([
        f"- 一致性阈值：{config.get('incl_cut')}",
        f"- PRI 阈值：{config.get('pri_cut')}",
        f"- 频数阈值：{config.get('n_cut')}",
        "",
        "## 2. 校准锚点",
        "",
        "| 变量 | 完全不隶属 | 交叉点 | 完全隶属 |",
        "|------|------------|--------|----------|",
    ])
    for _, row in thresholds.iterrows():
        label = row.get("label") or _variable_label(row.get("variable", ""), var_labels)
        lines.append(
            f"| {label} | {row['full_exclusion']:.3f} | {row['crossover']:.3f} | {row['full_inclusion']:.3f} |"
        )

    lines.extend(["", "## 3. 必要条件分析", "", "| 条件 | 一致性 | 覆盖率 |", "|------|--------|--------|"])
    for _, row in necessity.iterrows():
        lines.append(f"| {row['label']} | {row['consistency']:.4f} | {row['coverage']:.4f} |")

    sig = necessity[necessity["consistency"].fillna(0) >= 0.90] if not necessity.empty else pd.DataFrame()
    if not sig.empty:
        parts = [f"{r['label']}（一致性={r['consistency']:.4f}）" for _, r in sig.iterrows()]
        lines.extend([
            "",
            f"**解读：** {'、'.join(parts)}达到 0.90 的必要条件判断标准。必要条件不等于充分条件，仍需结合组态路径解释。",
        ])
    else:
        lines.extend([
            "",
            "**解读：** 各单项条件的一致性未达到 0.90，单一条件不构成结果的必要条件，结果更可能由多个条件组合形成。",
        ])

    def add_solution_section(title: str, metrics: pd.DataFrame, overall: pd.DataFrame) -> None:
        lines.extend(["", title, ""])
        inter_overall = overall[overall["solution_type"] == "intermediate"] if not overall.empty else pd.DataFrame()
        inter_metrics = metrics[metrics["solution_type"] == "intermediate"] if not metrics.empty else pd.DataFrame()
        if inter_overall.empty or int(inter_overall.iloc[0]["n_paths"]) == 0 or inter_metrics.empty:
            lines.append("未获得中间解路径。")
            return
        ov = inter_overall.iloc[0]
        lines.extend([
            f"中间解共识别出 **{int(ov['n_paths'])} 条** 组态路径。",
            f"总体解一致性：{ov['solution_consistency']:.4f}，总体解覆盖度：{ov['solution_coverage']:.4f}",
            "",
            "| 路径 | 组态路径 | 一致性 | 原始覆盖率 | 唯一覆盖率 |",
            "|------|----------|--------|------------|------------|",
        ])
        for _, row in inter_metrics.iterrows():
            formula = _formula_to_label(row["formula"], var_labels)
            unique = "NA" if pd.isna(row["unique_coverage"]) else f"{row['unique_coverage']:.4f}"
            lines.append(
                f"| {row['path']} | {formula} | {row['consistency']:.4f} | {row['raw_coverage']:.4f} | {unique} |"
            )

    add_solution_section("## 4. 充分条件组态分析（高结果）", metrics_high, overall_high)
    if config.get("run_low"):
        add_solution_section("## 5. 充分条件组态分析（低结果）", metrics_low, overall_low)

    lines.extend([
        "",
        "## 6. 因果非对称性",
        "",
        "高结果与低结果路径并不必然互为镜像。应分别解释促进高数字素养的条件组合，以及导致低数字素养的条件组合。",
    ])

    (report_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    files_dir = ensure_dir(run_dir / "output" / "files")
    solution_lines = [
        "fsQCA 充分条件分析结果",
        "",
        f"结果变量：{outcome_label}（{outcome}）",
        "条件变量：",
    ]
    solution_lines.extend([f"- {_variable_label(v, var_labels)}（{v}）" for v in conditions])
    solution_lines.extend(["", "高结果中间解："])
    high_inter = metrics_high[metrics_high["solution_type"] == "intermediate"] if not metrics_high.empty else pd.DataFrame()
    if high_inter.empty:
        solution_lines.append("未获得中间解路径。")
    else:
        for _, row in high_inter.iterrows():
            solution_lines.append(
                f"- {row['path']}：{_formula_to_label(row['formula'], var_labels)}"
                f"；一致性={row['consistency']:.4f}；原始覆盖率={row['raw_coverage']:.4f}"
            )
    if config.get("run_low"):
        solution_lines.extend(["", "低结果中间解："])
        low_inter = metrics_low[metrics_low["solution_type"] == "intermediate"] if not metrics_low.empty else pd.DataFrame()
        if low_inter.empty:
            solution_lines.append("未获得中间解路径。")
        else:
            for _, row in low_inter.iterrows():
                solution_lines.append(
                    f"- {row['path']}：{_formula_to_label(row['formula'], var_labels)}"
                    f"；一致性={row['consistency']:.4f}；原始覆盖率={row['raw_coverage']:.4f}"
                )
    (files_dir / "qca_solutions.txt").write_text("\n".join(solution_lines), encoding="utf-8")


def generate_presentation_outputs(run_dir: Path) -> None:
    """Generate all user-facing report and figures in Python."""
    import json

    figures_dir = ensure_dir(run_dir / "output" / "figures")
    tables_dir = run_dir / "output" / "tables"

    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    var_labels = config.get("variable_labels", {})
    outcome_label = _variable_label(config.get("outcome", ""), var_labels)

    for old in figures_dir.glob("*"):
        if old.is_file():
            old.unlink()

    _save_solution_bars(
        tables_dir / "solution_metrics_high.csv",
        figures_dir / "solution_bars.svg",
        f"高{outcome_label}组态路径指标",
        var_labels,
    )
    if config.get("run_low"):
        _save_solution_bars(
            tables_dir / "solution_metrics_low.csv",
            figures_dir / "solution_bars_low.svg",
            f"低{outcome_label}组态路径指标",
            var_labels,
        )
    _save_config_table(
        tables_dir / "config_table_high.csv",
        figures_dir / "config_table.svg",
        f"高{outcome_label}组态路径（中间解）",
    )
    _build_report(run_dir, config, var_labels)


def create_run(
    study_dir: Path,
    dataset: dict,
    df: pd.DataFrame,
    outcome: str,
    conditions: list[str],
    calibration: dict,
    incl_cut: float,
    pri_cut: float,
    n_cut: int,
    run_low: bool,
    robustness: bool,
    spec: dict | None = None,
) -> Path:
    run_id = new_id("run")
    run_dir = study_dir / "analyses" / run_id
    for sub in [
        "input",
        "output/tables",
        "output/figures",
        "output/files",
        "output/report",
        "output/logs",
    ]:
        ensure_dir(run_dir / sub)

    selected_cols = [outcome] + conditions
    selected = df[selected_cols].copy()
    selected.to_csv(run_dir / "input" / "selected_data.csv", index=False)

    config = {
        "run_id": run_id,
        "spec_id": spec.get("spec_id") if spec else None,
        "spec_name": spec.get("name") if spec else None,
        "dataset_id": dataset["dataset_id"],
        "dataset_name": dataset["name"],
        "algorithm": "fsQCA",
        "outcome": outcome,
        "conditions": conditions,
        "calibration": calibration,
        "incl_cut": incl_cut,
        "pri_cut": pri_cut,
        "n_cut": n_cut,
        "run_low": run_low,
        "robustness": robustness,
        "variable_labels": get_variable_labels(),
        "created_at": now_iso(),
    }
    run = {
        "run_id": run_id,
        "spec_id": spec.get("spec_id") if spec else None,
        "spec_name": spec.get("name") if spec else None,
        "dataset_id": dataset["dataset_id"],
        "dataset_name": dataset["name"],
        "algorithm": "fsQCA",
        "created_at": now_iso(),
        "run_dir": str(run_dir),
    }
    status = {"state": "created", "message": "运行目录已创建。", "created_at": now_iso(), "updated_at": now_iso()}

    write_json(run_dir / "run.json", run)
    write_json(run_dir / "config.json", config)
    write_json(run_dir / "status.json", status)
    return run_dir


def run_fsqca(run_dir: Path) -> None:
    status_path = run_dir / "status.json"
    write_json(status_path, {"state": "running", "message": "Rscript 正在运行。", "updated_at": now_iso()})

    script_path = APP_ROOT / "scripts" / "run_fsqca.R"
    stdout_path = run_dir / "output" / "logs" / "stdout.log"
    stderr_path = run_dir / "output" / "logs" / "stderr.log"

    try:
        tmp_parent = Path(tempfile.mkdtemp(prefix="research_analysis_app_"))
        tmp_run_dir = tmp_parent / run_dir.name
        shutil.copytree(run_dir, tmp_run_dir)
        tmp_output = tmp_run_dir / "output"
        if tmp_output.exists():
            shutil.rmtree(tmp_output)
        for sub in ["tables", "figures", "files", "report", "logs"]:
            ensure_dir(tmp_output / sub)

        cmd = ["Rscript", str(script_path), str(tmp_run_dir)]
        result = subprocess.run(cmd, cwd=APP_ROOT, text=True, capture_output=True, check=False)

        if (tmp_run_dir / "output").exists():
            if (run_dir / "output").exists():
                shutil.rmtree(run_dir / "output")
            shutil.copytree(tmp_run_dir / "output", run_dir / "output")

        generate_presentation_outputs(run_dir)

        stdout_path.write_text(result.stdout, encoding="utf-8")
        stderr_path.write_text(result.stderr, encoding="utf-8")
        if result.returncode == 0:
            write_json(
                status_path,
                {
                    "state": "completed",
                    "message": "fsQCA 分析成功完成。",
                    "returncode": result.returncode,
                    "updated_at": now_iso(),
                },
            )
        else:
            write_json(
                status_path,
                {
                    "state": "failed",
                    "message": "Rscript 运行失败，请查看 output/logs/stderr.log。",
                    "returncode": result.returncode,
                    "updated_at": now_iso(),
                },
            )
        shutil.rmtree(tmp_parent, ignore_errors=True)
    except FileNotFoundError:
        write_json(
            status_path,
            {
                "state": "failed",
                "message": "未找到 Rscript，请安装 R 并确保 Rscript 在系统 PATH 中。",
                "updated_at": now_iso(),
            },
        )
