from __future__ import annotations

import subprocess
import shutil
import tempfile
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


def _cn_font_properties():
    """Return FontProperties for the first available Chinese font on macOS."""
    from matplotlib import font_manager as fm

    # Preferred Chinese fonts in order — PingFang is the best for modern macOS
    preferred = [
        "PingFang SC", "PingFang HK", "PingFang TC",
        "Heiti SC", "Heiti TC", "STHeiti",
        "Lantinghei SC", "Songti SC", "Kaiti SC",
        "Noto Sans CJK SC", "Noto Sans SC",
    ]
    for f in fm.fontManager.ttflist:
        if f.name in preferred:
            return fm.FontProperties(fname=f.fname)
    # Fallback: pick any font with a Chinese-looking name
    for f in fm.fontManager.ttflist:
        if any(k in f.name.lower() for k in ("sc", "tc", "cn", "hei", "song", "ming", "kai", "ping")):
            return fm.FontProperties(fname=f.fname)
    return None


def generate_configuration_figures(run_dir: Path) -> None:
    """Generate solution metrics bar chart from R output.

    R already generates the primary figures (solution_bars.png, config_table.svg).
    This generates a supplementary Python chart as a reliable fallback.
    """
    import json

    figures_dir = ensure_dir(run_dir / "output" / "figures")
    tables_dir = run_dir / "output" / "tables"

    # If R already generated figures, skip (they are primary)
    if (figures_dir / "solution_bars.png").exists() and (figures_dir / "config_table.svg").exists():
        return

    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    var_labels = config.get("variable_labels", {})

    # Try to read solution metrics from R output
    metrics_path = tables_dir / "solution_metrics_high.csv"
    if not metrics_path.exists():
        return

    try:
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib import pyplot as plt

        cn_font = _cn_font_properties()

        df = pd.read_csv(metrics_path)
        inter = df[df["solution_type"] == "intermediate"]
        if inter.empty:
            return

        paths = inter["path"].tolist()
        cons = inter["consistency"].tolist()
        covs = inter["raw_coverage"].tolist()

        x = range(len(paths))
        w = 0.35

        fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
        ax.bar([i - w/2 for i in x], cons, w, label="一致性", color="#2563EB")
        ax.bar([i + w/2 for i in x], covs, w, label="原始覆盖率", color="#F59E0B")

        for i in x:
            ax.text(i - w/2, cons[i] + 0.02, f"{cons[i]:.3f}", ha="center", fontsize=9)
            ax.text(i + w/2, covs[i] + 0.02, f"{covs[i]:.3f}", ha="center", fontsize=9)

        outcome = config.get("outcome", "")
        outcome_label = var_labels.get(outcome, outcome)

        ax.set_title(f"高{outcome_label}的组态路径指标", fontproperties=cn_font, fontsize=14, fontweight="bold")
        ax.set_xticks(list(x))
        ax.set_xticklabels(paths)
        ax.set_ylim(0, 1.15)
        ax.legend(loc="upper right")
        ax.set_ylabel("")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        fig.tight_layout()
        fig.savefig(figures_dir / "configuration_path.png", dpi=150, bbox_inches="tight")
        plt.close(fig)
    except Exception:
        pass


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

        cmd = ["Rscript", str(script_path), str(tmp_run_dir)]
        result = subprocess.run(cmd, cwd=APP_ROOT, text=True, capture_output=True, check=False)

        if (tmp_run_dir / "output").exists():
            if (run_dir / "output").exists():
                shutil.rmtree(run_dir / "output")
            shutil.copytree(tmp_run_dir / "output", run_dir / "output")

        generate_configuration_figures(run_dir)

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
