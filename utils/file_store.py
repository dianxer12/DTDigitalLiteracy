from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4


APP_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = APP_ROOT / "workspace"
PROJECTS_DIR = WORKSPACE_DIR / "projects"
DEFAULT_PROJECT_ID = "project_default"
DEFAULT_PROJECT_NAME = "双师型护理教师数字素养研究"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_name(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name.strip())
    return cleaned or "dataset"


def new_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"


def project_dir(project_id: str = DEFAULT_PROJECT_ID) -> Path:
    return PROJECTS_DIR / project_id


def datasets_dir(project_id: str = DEFAULT_PROJECT_ID) -> Path:
    return project_dir(project_id) / "datasets"


def analyses_dir(project_id: str = DEFAULT_PROJECT_ID) -> Path:
    return project_dir(project_id) / "analyses"


def ensure_default_project() -> Path:
    ensure_dir(PROJECTS_DIR)
    pdir = project_dir()
    ensure_dir(pdir / "datasets")
    ensure_dir(pdir / "analyses")

    project_json = pdir / "project.json"
    if not project_json.exists():
        write_json(
            project_json,
            {
                "project_id": DEFAULT_PROJECT_ID,
                "name": DEFAULT_PROJECT_NAME,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            },
        )

    update_project_index(DEFAULT_PROJECT_ID)
    return pdir


def list_datasets(project_id: str = DEFAULT_PROJECT_ID) -> list[dict]:
    ensure_default_project()
    items = []
    for path in sorted(datasets_dir(project_id).glob("dataset_*")):
        meta = read_json(path / "dataset.json")
        if meta:
            items.append(meta)
    return sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)


def list_runs(project_id: str = DEFAULT_PROJECT_ID) -> list[dict]:
    ensure_default_project()
    items = []
    for path in sorted(analyses_dir(project_id).glob("run_*")):
        run = read_json(path / "run.json")
        if run:
            status = read_json(path / "status.json", {})
            run["status"] = status.get("state", "unknown")
            items.append(run)
    return sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)


def get_dataset_dir(dataset_id: str, project_id: str = DEFAULT_PROJECT_ID) -> Path:
    return datasets_dir(project_id) / dataset_id


def get_run_dir(run_id: str, project_id: str = DEFAULT_PROJECT_ID) -> Path:
    return analyses_dir(project_id) / run_id


def copy_uploaded_file(uploaded_file, target_dir: Path) -> Path:
    ensure_dir(target_dir)
    target = target_dir / uploaded_file.name
    with target.open("wb") as f:
        f.write(uploaded_file.getbuffer())
    return target


def copy_file(src: Path, dest: Path) -> None:
    ensure_dir(dest.parent)
    shutil.copy2(src, dest)


def update_project_index(project_id: str = DEFAULT_PROJECT_ID) -> None:
    pdir = project_dir(project_id)
    dataset_ids = []
    analysis_ids = []
    datasets_path = pdir / "datasets"
    analyses_path = pdir / "analyses"
    if datasets_path.exists():
        for path in sorted(datasets_path.glob("dataset_*")):
            if (path / "dataset.json").exists():
                dataset_ids.append(path.name)
    if analyses_path.exists():
        for path in sorted(analyses_path.glob("run_*")):
            if (path / "run.json").exists():
                analysis_ids.append(path.name)
    index = {
        "project_id": project_id,
        "updated_at": now_iso(),
        "datasets": dataset_ids,
        "analyses": analysis_ids,
    }
    write_json(pdir / "project_index.json", index)
