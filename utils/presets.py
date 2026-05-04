"""
Pre-configured scale definitions for the 双师型护理教师数字素养 questionnaire.

Matches the R scripts in:
  - 04_fsqca_dc_dimensions.R (scoring logic)
  - 03_fsqca_total_model.R (model variables)
"""

from __future__ import annotations

from utils.scoring import DimensionDef, ScaleDefinition

# ---------------------------------------------------------------------------
# Dimension definitions  (item indices are 0‑based within the scale)
# ---------------------------------------------------------------------------

_OS_DIMENSIONS = [
    DimensionDef("os_work_support", "组织支持-工作支持", list(range(0, 11)), "mean"),
    DimensionDef("os_value_identity", "组织支持-价值认同", list(range(11, 18)), "mean"),
    DimensionDef("os_benefit_care", "组织支持-利益关心", list(range(18, 23)), "mean"),
    DimensionDef("os_total", "组织支持-总量表", list(range(0, 23)), "mean"),
]

_WE_DIMENSIONS = [
    DimensionDef("we_vigor", "工作投入-活力", [0, 3, 7, 11, 14, 16], "mean"),
    DimensionDef("we_dedication", "工作投入-奉献", [1, 4, 6, 9, 12], "mean"),
    DimensionDef("we_absorption", "工作投入-专注", [2, 5, 8, 10, 13, 15], "mean"),
    DimensionDef("we_total", "工作投入-总量表", list(range(0, 17)), "mean"),
]

_DC_DIMENSIONS = [
    DimensionDef("dc_professional_engagement", "数字胜任力-专业参与", [0, 1, 2, 3], "mean"),
    DimensionDef("dc_digital_resources", "数字胜任力-数字资源", [4, 5, 6], "mean"),
    DimensionDef("dc_teaching_learning", "数字胜任力-教学与学习", [7, 8, 9, 10], "mean"),
    DimensionDef("dc_assessment_feedback", "数字胜任力-评价与反馈", [11, 12, 13], "mean"),
    DimensionDef("dc_empowering_learners", "数字胜任力-促进学习者发展", [14, 15, 16], "mean"),
    DimensionDef("dc_facilitating_digital", "数字胜任力-促进数字能力", [17, 18, 19, 20, 21], "mean"),
    DimensionDef("dc_total", "数字胜任力-总量表", list(range(0, 22)), "mean"),
]

_DL_DIMENSIONS = [
    DimensionDef("dl_concept_awareness", "数字素养-观念与意识", list(range(0, 6)), "mean"),
    DimensionDef("dl_knowledge_skills", "数字素养-知识与技能", list(range(6, 13)), "mean"),
    DimensionDef("dl_application_eval", "数字素养-应用与评价", list(range(13, 24)), "mean"),
    DimensionDef("dl_security_respons", "数字素养-安全与责任", list(range(24, 28)), "mean"),
    DimensionDef("dl_professional_dev", "数字素养-专业发展", list(range(28, 33)), "mean"),
    DimensionDef("dl_total", "数字素养-总量表", list(range(0, 33)), "mean"),
]

# Reverse-coded items within OS (0‑based within the 23‑item scale)
# From R: os_rev_idx <- c(2, 5, 6, 8, 12, 13, 14, 15, 17, 20, 23)
_OS_REVERSE = [1, 4, 5, 7, 11, 12, 13, 14, 16, 19, 22]

# ---------------------------------------------------------------------------
# Preset builders
# ---------------------------------------------------------------------------


def build_presets(
    os_range: tuple[int, int] = (0, 23),
    we_range: tuple[int, int] = (23, 40),
    dc_range: tuple[int, int] = (40, 62),
    dl_range: tuple[int, int] = (62, 95),
) -> dict[str, ScaleDefinition]:
    """Build preset scale definitions with custom column ranges.

    Column indices are the positions **within the uploaded DataFrame**
    (after stripping metadata columns).  Defaults assume metadata has
    been removed and items are contiguous.

    Parameters
    ----------
    os_range : (start, end) for OS items (exclusive end)
    we_range : (start, end) for WE items
    dc_range : (start, end) for DC items
    dl_range : (start, end) for DL items

    Returns
    -------
    dict[str, ScaleDefinition]
        Keys: "OS", "WE", "DC", "DL"
    """
    return {
        "OS": ScaleDefinition(
            name="OS",
            label="组织支持",
            columns=list(range(*os_range)),
            reverse_items=_OS_REVERSE,
            reverse_max=6,
            dimensions=_OS_DIMENSIONS,
        ),
        "WE": ScaleDefinition(
            name="WE",
            label="工作投入",
            columns=list(range(*we_range)),
            reverse_items=[],
            reverse_max=6,
            dimensions=_WE_DIMENSIONS,
        ),
        "DC": ScaleDefinition(
            name="DC",
            label="数字胜任力",
            columns=list(range(*dc_range)),
            reverse_items=[],
            reverse_max=6,
            dimensions=_DC_DIMENSIONS,
        ),
        "DL": ScaleDefinition(
            name="DL",
            label="数字素养",
            columns=list(range(*dl_range)),
            reverse_items=[],
            reverse_max=6,
            dimensions=_DL_DIMENSIONS,
        ),
    }


def get_default_presets() -> list[ScaleDefinition]:
    """Return the four default scale definitions as a flat list.

    Uses contiguous 0‑based column indexing (no metadata columns).
    """
    return list(build_presets().values())


def get_variable_labels() -> dict[str, str]:
    """Return a mapping from variable names to Chinese labels."""
    labels: dict[str, str] = {}
    for scale in get_default_presets():
        for dim in scale.dimensions:
            labels[dim.name] = dim.label
    return labels


# For backward-compatible import
PRESET_SCALES = get_default_presets()
