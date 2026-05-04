"""
Tests for file_store.py — study CRUD, dataset/run CRUD, and legacy migration.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import utils.file_store as fs


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_workspace(monkeypatch):
    """Point WORKSPACE_DIR and STUDIES_DIR at a temp directory."""
    tmp = Path(tempfile.mkdtemp(prefix="fsqca_test_"))
    monkeypatch.setattr(fs, "WORKSPACE_DIR", tmp)
    monkeypatch.setattr(fs, "STUDIES_DIR", tmp / "studies")
    yield tmp
    import shutil

    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def study(tmp_workspace):
    """Create one study and return its meta dict."""
    return fs.create_study("测试研究")


@pytest.fixture
def study2(tmp_workspace):
    """Create a second study for isolation / multi-study tests."""
    return fs.create_study("研究二", "描述")


# ═══════════════════════════════════════════════════════════════════════════════
# Study CRUD
# ═══════════════════════════════════════════════════════════════════════════════


class TestCreateStudy:
    def test_creates_and_returns_meta(self, tmp_workspace):
        meta = fs.create_study("护理实习生职业倦怠研究")
        assert meta["name"] == "护理实习生职业倦怠研究"
        assert meta["study_id"].startswith("study_")
        assert "created_at" in meta
        assert meta["description"] == ""

    def test_creates_with_description(self, tmp_workspace):
        meta = fs.create_study("研究A", "这是一项关于数字素养的研究")
        assert meta["description"] == "这是一项关于数字素养的研究"

    def test_creates_directories(self, tmp_workspace):
        meta = fs.create_study("研究X")
        sdir = fs.study_dir(meta["study_id"])
        assert sdir.exists()
        assert (sdir / "datasets").exists()
        assert (sdir / "analyses").exists()
        assert (sdir / "study.json").exists()

    def test_empty_name_raises(self, tmp_workspace):
        with pytest.raises(ValueError, match="研究名称不能为空"):
            fs.create_study("")

    def test_whitespace_name_raises(self, tmp_workspace):
        with pytest.raises(ValueError, match="研究名称不能为空"):
            fs.create_study("   ")

    def test_name_with_special_chars_saved_as_is(self, tmp_workspace):
        meta = fs.create_study("护理/研究:test")
        assert meta["name"] == "护理/研究:test"
        # study_id is auto-generated, not derived from name
        assert meta["study_id"].startswith("study_")


class TestListStudies:
    def test_empty_when_no_studies(self, tmp_workspace):
        assert fs.list_studies() == []

    def test_returns_all_studies_sorted_by_created_at_desc(self, tmp_workspace):
        a = fs.create_study("A")
        b = fs.create_study("B")
        studies = fs.list_studies()
        assert len(studies) == 2
        assert studies[0]["study_id"] == b["study_id"]  # newest first
        assert studies[1]["study_id"] == a["study_id"]

    def test_ignores_non_directory_entries(self, tmp_workspace):
        fs.create_study("A")
        (fs.STUDIES_DIR / "random_file.txt").write_text("garbage")
        assert len(fs.list_studies()) == 1


class TestGetStudy:
    def test_returns_meta(self, study):
        meta = fs.get_study(study["study_id"])
        assert meta == study

    def test_returns_none_for_missing(self, tmp_workspace):
        assert fs.get_study("study_nonexistent") is None


class TestDeleteStudy:
    def test_removes_directory(self, study):
        study_id = study["study_id"]
        assert fs.study_dir(study_id).exists()
        assert fs.delete_study(study_id) is True
        assert not fs.study_dir(study_id).exists()

    def test_returns_true_if_exists(self, study):
        assert fs.delete_study(study["study_id"]) is True

    def test_returns_false_if_not_exists(self, tmp_workspace):
        assert fs.delete_study("study_nonexistent") is False

    def test_removed_study_not_in_list(self, study):
        fs.delete_study(study["study_id"])
        assert fs.list_studies() == []


# ═══════════════════════════════════════════════════════════════════════════════
# Path helpers
# ═══════════════════════════════════════════════════════════════════════════════


class TestPathFunctions:
    def test_study_dir(self, tmp_workspace):
        assert fs.study_dir("sid") == fs.STUDIES_DIR / "sid"

    def test_datasets_dir(self, tmp_workspace):
        assert fs.datasets_dir("sid") == fs.STUDIES_DIR / "sid" / "datasets"

    def test_analyses_dir(self, tmp_workspace):
        assert fs.analyses_dir("sid") == fs.STUDIES_DIR / "sid" / "analyses"

    def test_get_dataset_dir(self, tmp_workspace):
        assert fs.get_dataset_dir("ds_1", "sid") == fs.STUDIES_DIR / "sid" / "datasets" / "ds_1"

    def test_get_run_dir(self, tmp_workspace):
        assert fs.get_run_dir("run_1", "sid") == fs.STUDIES_DIR / "sid" / "analyses" / "run_1"


# ═══════════════════════════════════════════════════════════════════════════════
# Dataset / Run CRUD (study-aware)
# ═══════════════════════════════════════════════════════════════════════════════


class TestListDatasets:
    def test_empty_for_fresh_study(self, study):
        assert fs.list_datasets(study["study_id"]) == []

    def test_returns_dataset_meta(self, study):
        ds_dir = fs.datasets_dir(study["study_id"]) / "dataset_abc"
        fs.ensure_dir(ds_dir)
        fs.write_json(ds_dir / "dataset.json", {
            "dataset_id": "dataset_abc",
            "name": "my_data",
            "created_at": "2026-05-04T12:00:00",
        })
        ds_list = fs.list_datasets(study["study_id"])
        assert len(ds_list) == 1
        assert ds_list[0]["name"] == "my_data"

    def test_sorted_by_created_at_desc(self, study):
        d1 = fs.datasets_dir(study["study_id"]) / "old"
        d2 = fs.datasets_dir(study["study_id"]) / "new"
        fs.ensure_dir(d1)
        fs.ensure_dir(d2)
        fs.write_json(d1 / "dataset.json", {"dataset_id": "old", "name": "old", "created_at": "2026-01-01"})
        fs.write_json(d2 / "dataset.json", {"dataset_id": "new", "name": "new", "created_at": "2026-12-31"})
        result = fs.list_datasets(study["study_id"])
        assert result[0]["dataset_id"] == "new"
        assert result[1]["dataset_id"] == "old"

    def test_study_isolation(self, study, study2):
        fs.ensure_dir(fs.datasets_dir(study["study_id"]) / "ds_a")
        fs.write_json(fs.datasets_dir(study["study_id"]) / "ds_a" / "dataset.json",
                      {"dataset_id": "ds_a", "name": "A", "created_at": "2026-01-01"})
        assert len(fs.list_datasets(study["study_id"])) == 1
        assert len(fs.list_datasets(study2["study_id"])) == 0

    def test_missing_study_returns_empty(self, tmp_workspace):
        assert fs.list_datasets("study_nonexistent") == []


class TestListRuns:
    def test_empty_for_fresh_study(self, study):
        assert fs.list_runs(study["study_id"]) == []

    def test_returns_run_with_status(self, study):
        run_dir = fs.analyses_dir(study["study_id"]) / "run_xyz"
        fs.ensure_dir(run_dir)
        fs.write_json(run_dir / "run.json", {
            "run_id": "run_xyz", "dataset_id": "ds",
            "dataset_name": "data", "algorithm": "fsQCA",
            "created_at": "2026-05-04T12:00:00",
        })
        fs.write_json(run_dir / "status.json", {"state": "completed"})
        result = fs.list_runs(study["study_id"])
        assert len(result) == 1
        assert result[0]["status"] == "completed"

    def test_missing_status_defaults_to_unknown(self, study):
        run_dir = fs.analyses_dir(study["study_id"]) / "run_nostat"
        fs.ensure_dir(run_dir)
        fs.write_json(run_dir / "run.json", {
            "run_id": "run_nostat", "dataset_id": "ds",
            "dataset_name": "data", "algorithm": "fsQCA",
            "created_at": "2026-01-01",
        })
        assert fs.list_runs(study["study_id"])[0]["status"] == "unknown"

    def test_study_isolation(self, study, study2):
        run_dir = fs.analyses_dir(study["study_id"]) / "run_1"
        fs.ensure_dir(run_dir)
        fs.write_json(run_dir / "run.json", {"run_id": "run_1", "dataset_id": "ds", "created_at": "2026-01-01"})
        assert len(fs.list_runs(study["study_id"])) == 1
        assert len(fs.list_runs(study2["study_id"])) == 0

    def test_missing_analyses_dir_returns_empty(self, study):
        result = fs.list_runs(study["study_id"])
        assert isinstance(result, list)
        assert result == []


class TestDeleteDataset:
    def test_removes_directory(self, study):
        ds_dir = fs.datasets_dir(study["study_id"]) / "ds_x"
        fs.ensure_dir(ds_dir)
        fs.write_json(ds_dir / "dataset.json", {"dataset_id": "ds_x"})
        assert fs.delete_dataset("ds_x", study["study_id"]) is True
        assert not ds_dir.exists()

    def test_nonexistent_returns_false(self, study):
        assert fs.delete_dataset("no_such", study["study_id"]) is False


class TestDeleteRun:
    def test_removes_directory(self, study):
        run_dir = fs.analyses_dir(study["study_id"]) / "run_x"
        fs.ensure_dir(run_dir)
        assert fs.delete_run("run_x", study["study_id"]) is True
        assert not run_dir.exists()

    def test_nonexistent_returns_false(self, study):
        assert fs.delete_run("no_such", study["study_id"]) is False


# ═══════════════════════════════════════════════════════════════════════════════
# Legacy migration
# ═══════════════════════════════════════════════════════════════════════════════


class TestMigrateLegacyProjects:
    def _setup_legacy(self, tmp_workspace):
        """Create a fake legacy workspace/projects/project_default structure."""
        projects_dir = tmp_workspace / "projects"
        old_dir = projects_dir / "project_default"
        fs.ensure_dir(old_dir / "datasets" / "ds_legacy")
        fs.ensure_dir(old_dir / "analyses" / "run_legacy")
        fs.write_json(old_dir / "project.json", {
            "project_id": "project_default",
            "name": "旧项目",
            "created_at": "2025-01-01T00:00:00",
        })
        fs.write_json(old_dir / "datasets" / "ds_legacy" / "dataset.json", {
            "dataset_id": "ds_legacy", "name": "旧数据", "created_at": "2025-01-01",
        })
        fs.write_json(old_dir / "analyses" / "run_legacy" / "run.json", {
            "run_id": "run_legacy", "dataset_id": "ds_legacy", "created_at": "2025-01-01",
        })
        return old_dir

    def test_migrates_and_returns_true(self, tmp_workspace):
        self._setup_legacy(tmp_workspace)
        assert fs.migrate_legacy_projects() is True

    def test_creates_study_from_old_project(self, tmp_workspace):
        self._setup_legacy(tmp_workspace)
        fs.migrate_legacy_projects()
        studies = fs.list_studies()
        assert len(studies) == 1
        assert studies[0]["name"] == "旧项目"
        assert studies[0]["description"] == "（从旧版项目自动迁移）"

    def test_copies_datasets(self, tmp_workspace):
        self._setup_legacy(tmp_workspace)
        fs.migrate_legacy_projects()
        study_id = fs.list_studies()[0]["study_id"]
        ds_list = fs.list_datasets(study_id)
        assert len(ds_list) == 1
        assert ds_list[0]["name"] == "旧数据"

    def test_copies_analyses(self, tmp_workspace):
        self._setup_legacy(tmp_workspace)
        fs.migrate_legacy_projects()
        study_id = fs.list_studies()[0]["study_id"]
        runs = fs.list_runs(study_id)
        assert len(runs) == 1
        assert runs[0]["run_id"] == "run_legacy"

    def test_removes_old_projects_dir(self, tmp_workspace):
        self._setup_legacy(tmp_workspace)
        fs.migrate_legacy_projects()
        assert not (tmp_workspace / "projects").exists()

    def test_no_legacy_dir_returns_false(self, tmp_workspace):
        assert fs.migrate_legacy_projects() is False

    def test_no_project_json_returns_false(self, tmp_workspace):
        projects_dir = tmp_workspace / "projects"
        (projects_dir / "project_default").mkdir(parents=True)
        assert fs.migrate_legacy_projects() is False

    def test_idempotent_second_call_returns_false(self, tmp_workspace):
        self._setup_legacy(tmp_workspace)
        assert fs.migrate_legacy_projects() is True
        assert fs.migrate_legacy_projects() is False

    def test_already_migrated_studies_skips(self, tmp_workspace):
        self._setup_legacy(tmp_workspace)
        # Create studies dir directly to simulate prior migration
        fs.ensure_dir(fs.STUDIES_DIR / "existing_study")
        assert fs.migrate_legacy_projects() is False


# ═══════════════════════════════════════════════════════════════════════════════
# Data isolation (Epic 5 / US-5.1)
# ═══════════════════════════════════════════════════════════════════════════════


class TestStudyIsolation:
    def test_delete_study_cascades_to_datasets(self, study):
        ds_dir = fs.datasets_dir(study["study_id"]) / "ds_1"
        fs.ensure_dir(ds_dir)
        fs.write_json(ds_dir / "dataset.json", {"dataset_id": "ds_1"})
        fs.delete_study(study["study_id"])
        assert fs.list_datasets(study["study_id"]) == []

    def test_delete_study_cascades_to_runs(self, study):
        run_dir = fs.analyses_dir(study["study_id"]) / "run_1"
        fs.ensure_dir(run_dir)
        fs.delete_study(study["study_id"])
        assert fs.list_runs(study["study_id"]) == []

    def test_create_study_produces_unique_ids(self, tmp_workspace):
        ids = {fs.create_study(f"研究_{i}")["study_id"] for i in range(5)}
        assert len(ids) == 5
