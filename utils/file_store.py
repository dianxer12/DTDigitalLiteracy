from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4


APP_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = APP_ROOT / "workspace"
STUDIES_DIR = WORKSPACE_DIR / "studies"


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


# ── Study paths ────────────────────────────────────────────────────────────


def study_dir(study_id: str) -> Path:
    return STUDIES_DIR / study_id


def datasets_dir(study_id: str) -> Path:
    return study_dir(study_id) / "datasets"


def analyses_dir(study_id: str) -> Path:
    return study_dir(study_id) / "analyses"


# ── Study CRUD ─────────────────────────────────────────────────────────────


def list_studies() -> list[dict]:
    if not STUDIES_DIR.exists():
        return []
    studies = []
    for path in sorted(STUDIES_DIR.iterdir()):
        if not path.is_dir():
            continue
        meta = read_json(path / "study.json")
        if meta:
            studies.append(meta)
    return sorted(studies, key=lambda x: (x.get("created_at", ""), x.get("study_id", "")), reverse=True)


def get_study(study_id: str) -> dict | None:
    return read_json(study_dir(study_id) / "study.json", None)


def create_study(name: str, description: str = "") -> dict:
    if not name or not name.strip():
        raise ValueError("研究名称不能为空")
    study_id = new_id("study")
    sdir = study_dir(study_id)
    ensure_dir(sdir / "datasets")
    ensure_dir(sdir / "analyses")
    meta = {
        "study_id": study_id,
        "name": name.strip(),
        "description": description.strip(),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    write_json(sdir / "study.json", meta)
    return meta


def delete_study(study_id: str) -> bool:
    sdir = study_dir(study_id)
    if sdir.exists():
        shutil.rmtree(sdir, ignore_errors=True)
        return True
    return False


# ── Dataset / Run CRUD ─────────────────────────────────────────────────────


def list_datasets(study_id: str) -> list[dict]:
    ds_dir = datasets_dir(study_id)
    if not ds_dir.exists():
        return []
    items = []
    for path in sorted(ds_dir.iterdir()):
        if not path.is_dir():
            continue
        meta = read_json(path / "dataset.json")
        if meta:
            items.append(meta)
    return sorted(items, key=lambda x: (x.get("created_at", ""), x.get("dataset_id", "")), reverse=True)


def list_runs(study_id: str) -> list[dict]:
    analyses_path = analyses_dir(study_id)
    if not analyses_path.exists():
        return []
    items = []
    for path in sorted(analyses_path.glob("run_*")):
        run = read_json(path / "run.json")
        if run:
            status = read_json(path / "status.json", {})
            run["status"] = status.get("state", "unknown")
            items.append(run)
    return sorted(items, key=lambda x: (x.get("created_at", ""), x.get("run_id", "")), reverse=True)


def get_dataset_dir(dataset_id: str, study_id: str) -> Path:
    return datasets_dir(study_id) / dataset_id


def get_run_dir(run_id: str, study_id: str) -> Path:
    return analyses_dir(study_id) / run_id


def copy_uploaded_file(uploaded_file, target_dir: Path) -> Path:
    ensure_dir(target_dir)
    target = target_dir / uploaded_file.name
    with target.open("wb") as f:
        f.write(uploaded_file.getbuffer())
    return target


def copy_file(src: Path, dest: Path) -> None:
    ensure_dir(dest.parent)
    shutil.copy2(src, dest)


def delete_dataset(dataset_id: str, study_id: str) -> bool:
    ds_dir = datasets_dir(study_id) / dataset_id
    if ds_dir.exists():
        shutil.rmtree(ds_dir, ignore_errors=True)
        return True
    return False


def delete_run(run_id: str, study_id: str) -> bool:
    run_dir = analyses_dir(study_id) / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir, ignore_errors=True)
        return True
    return False


# ── Legacy migration ───────────────────────────────────────────────────────


def migrate_legacy_projects() -> bool:
    """Migrate workspace/projects/ → workspace/studies/ if needed.

    Returns True if migration was performed. Idempotent — safe to call
    repeatedly.
    """
    old_projects_dir = WORKSPACE_DIR / "projects"
    if not old_projects_dir.exists():
        return False

    # Only migrate project_default
    old_dir = old_projects_dir / "project_default"
    old_meta = read_json(old_dir / "project.json", {})
    if not old_meta:
        return False

    # Already migrated?
    if STUDIES_DIR.exists() and any(
        p.is_dir() for p in STUDIES_DIR.iterdir()
    ):
        return False

    ensure_dir(STUDIES_DIR)
    study_id = new_id("study")
    sdir = study_dir(study_id)
    ensure_dir(sdir / "datasets")
    ensure_dir(sdir / "analyses")

    for sub in ["datasets", "analyses"]:
        src = old_dir / sub
        if src.exists():
            shutil.copytree(src, sdir / sub, dirs_exist_ok=True)

    write_json(
        sdir / "study.json",
        {
            "study_id": study_id,
            "name": old_meta.get("name", "已迁移研究"),
            "description": "（从旧版项目自动迁移）",
            "created_at": old_meta.get("created_at", now_iso()),
            "updated_at": now_iso(),
        },
    )

    shutil.rmtree(old_projects_dir, ignore_errors=True)
    return True
