from __future__ import annotations

import subprocess
import shutil
import tempfile
from pathlib import Path

import pandas as pd

from .file_store import APP_ROOT, ensure_dir, new_id, now_iso, write_json


def _svg_escape(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def generate_configuration_figures(run_dir: Path) -> None:
    """Generate lightweight configuration figures in Python.

    R still performs fsQCA. Figures are generated here to avoid platform-specific
    R graphics device issues and to keep PNG/SVG output stable.
    """
    config = __import__("json").loads((run_dir / "config.json").read_text(encoding="utf-8"))
    figures_dir = ensure_dir(run_dir / "output" / "figures")
    outcome = config["outcome"]
    conditions = config.get("conditions", [])
    c1 = conditions[0] if len(conditions) > 0 else "condition_1"
    c2 = conditions[1] if len(conditions) > 1 else "condition_2"

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="620" viewBox="0 0 1200 620">
<defs>
  <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
    <path d="M0,0 L0,6 L9,3 z" fill="#2E7D32"/>
  </marker>
</defs>
<rect width="100%" height="100%" fill="white"/>
<text x="600" y="70" text-anchor="middle" font-size="30" font-family="Arial, sans-serif" font-weight="700">fsQCA Configuration Path</text>
<rect x="100" y="190" width="260" height="80" fill="#E8F3EA" stroke="#2E7D32" stroke-width="3"/>
<text x="230" y="238" text-anchor="middle" font-size="20" font-family="Arial, sans-serif">{_svg_escape(c1)}</text>
<rect x="100" y="330" width="260" height="80" fill="#E8F3EA" stroke="#2E7D32" stroke-width="3"/>
<text x="230" y="378" text-anchor="middle" font-size="20" font-family="Arial, sans-serif">{_svg_escape(c2)}</text>
<rect x="500" y="190" width="260" height="80" fill="#F2FAF2" stroke="#2E7D32" stroke-width="3"/>
<text x="630" y="238" text-anchor="middle" font-size="20" font-family="Arial, sans-serif">Configuration A</text>
<rect x="500" y="330" width="260" height="80" fill="#F2FAF2" stroke="#2E7D32" stroke-width="3"/>
<text x="630" y="378" text-anchor="middle" font-size="20" font-family="Arial, sans-serif">Configuration B</text>
<rect x="920" y="260" width="210" height="90" fill="#D9EFD9" stroke="#2E7D32" stroke-width="3"/>
<text x="1025" y="313" text-anchor="middle" font-size="20" font-family="Arial, sans-serif">{_svg_escape(outcome)}</text>
<line x1="360" y1="230" x2="500" y2="230" stroke="#2E7D32" stroke-width="3" marker-end="url(#arrow)"/>
<line x1="360" y1="370" x2="500" y2="370" stroke="#2E7D32" stroke-width="3" marker-end="url(#arrow)"/>
<line x1="760" y1="230" x2="920" y2="300" stroke="#2E7D32" stroke-width="3" marker-end="url(#arrow)"/>
<line x1="760" y1="370" x2="920" y2="315" stroke="#2E7D32" stroke-width="3" marker-end="url(#arrow)"/>
</svg>"""
    (figures_dir / "configuration_path.svg").write_text(svg, encoding="utf-8")

    try:
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import pyplot as plt
        from matplotlib.patches import FancyArrowPatch, Rectangle

        fig, ax = plt.subplots(figsize=(10, 5), dpi=180)
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 5)
        ax.axis("off")
        fig.patch.set_facecolor("white")

        def box(x, y, w, h, label, fc):
            ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, facecolor=fc, edgecolor="#2E7D32", linewidth=1.5))
            ax.text(x, y, label, ha="center", va="center", fontsize=10)

        def arrow(x1, y1, x2, y2):
            ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="->", mutation_scale=14, linewidth=1.5, color="#2E7D32"))

        ax.text(5, 4.6, "fsQCA Configuration Path", ha="center", fontsize=15, fontweight="bold")
        box(1.7, 3.2, 2.2, 0.65, c1, "#E8F3EA")
        box(1.7, 2.0, 2.2, 0.65, c2, "#E8F3EA")
        box(5.0, 3.2, 2.2, 0.65, "Configuration A", "#F2FAF2")
        box(5.0, 2.0, 2.2, 0.65, "Configuration B", "#F2FAF2")
        box(8.3, 2.6, 1.8, 0.75, outcome, "#D9EFD9")
        arrow(2.8, 3.2, 3.9, 3.2)
        arrow(2.8, 2.0, 3.9, 2.0)
        arrow(6.1, 3.2, 7.4, 2.75)
        arrow(6.1, 2.0, 7.4, 2.45)
        fig.savefig(figures_dir / "configuration_path.png", bbox_inches="tight", pad_inches=0.2)
        plt.close(fig)
    except Exception as exc:
        (run_dir / "output" / "logs" / "python_figure_error.log").write_text(str(exc), encoding="utf-8")


def create_run(
    project_dir: Path,
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
    run_dir = project_dir / "analyses" / run_id
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
    status = {"state": "created", "message": "Run folder created.", "created_at": now_iso(), "updated_at": now_iso()}

    write_json(run_dir / "run.json", run)
    write_json(run_dir / "config.json", config)
    write_json(run_dir / "status.json", status)
    return run_dir


def run_fsqca(run_dir: Path) -> None:
    status_path = run_dir / "status.json"
    write_json(status_path, {"state": "running", "message": "Rscript is running.", "updated_at": now_iso()})

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
                    "message": "fsQCA completed successfully.",
                    "returncode": result.returncode,
                    "updated_at": now_iso(),
                },
            )
        else:
            write_json(
                status_path,
                {
                    "state": "failed",
                    "message": "Rscript failed. Check output/logs/stderr.log.",
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
                "message": "Rscript not found. Install R and ensure Rscript is on PATH.",
                "updated_at": now_iso(),
            },
        )
