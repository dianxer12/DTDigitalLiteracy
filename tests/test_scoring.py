"""
Tests for scoring.py – dimension score computation from raw questionnaire items.
"""
import sys
from pathlib import Path

# Make utils importable from tests/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest

from utils.scoring import (
    compute_dimension_scores,
    reverse_score,
    compute_scale_scores,
    ScaleDefinition,
    DimensionDef,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_os_data() -> pd.DataFrame:
    """Simulate a 23-item OS scale for 3 respondents, all items rated 0–6."""
    rng = [
        [6, 2, 5, 5, 3, 2, 4, 3, 4, 4, 4, 2, 2, 2, 2, 4, 3, 4, 3, 3, 3, 4, 3],
        [6, 0, 6, 6, 0, 0, 6, 6, 6, 6, 6, 0, 0, 0, 0, 5, 1, 6, 1, 1, 4, 6, 1],
        [4, 3, 4, 3, 4, 3, 4, 3, 3, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3, 4, 3],
    ]
    cols = [f"os{i+1}" for i in range(23)]
    return pd.DataFrame(rng, columns=cols)


@pytest.fixture
def sample_we_data() -> pd.DataFrame:
    """Simulate a 17-item WE scale for 3 respondents."""
    rng = [
        [3, 5, 4, 5, 4, 3, 4, 5, 3, 4, 5, 5, 4, 3, 4, 4, 5],
        [1, 5, 6, 1, 5, 6, 3, 1, 3, 5, 4, 4, 3, 3, 3, 3, 3],
        [3, 4, 4, 3, 4, 4, 3, 4, 4, 3, 4, 4, 3, 4, 4, 3, 4],
    ]
    cols = [f"we{i+1}" for i in range(17)]
    return pd.DataFrame(rng, columns=cols)


@pytest.fixture
def os_scale_def() -> ScaleDefinition:
    return ScaleDefinition(
        name="组织支持",
        columns=[f"os{i+1}" for i in range(23)],
        reverse_items=[1, 4, 5, 7, 11, 12, 13, 14, 16, 19, 22],  # 0-based index
        reverse_max=6,
        dimensions=[
            DimensionDef(name="os_work_support", label="工作支持", items=list(range(0, 11)), aggregation="mean"),
            DimensionDef(name="os_value_identity", label="价值认同", items=list(range(11, 18)), aggregation="mean"),
            DimensionDef(name="os_benefit_care", label="利益关心", items=list(range(18, 23)), aggregation="mean"),
            DimensionDef(name="os_total", label="组织支持总量表", items=list(range(0, 23)), aggregation="mean"),
        ],
    )


# ---------------------------------------------------------------------------
# Tests: reverse_score
# ---------------------------------------------------------------------------

class TestReverseScore:
    def test_reverse_basic(self):
        s = pd.Series([0, 1, 2, 3, 4, 5, 6])
        result = reverse_score(s, max_val=6)
        expected = pd.Series([6, 5, 4, 3, 2, 1, 0])
        pd.testing.assert_series_equal(result, expected)

    def test_reverse_with_nan(self):
        s = pd.Series([1, None, 5, float("nan")])
        result = reverse_score(s, max_val=6)
        assert result.iloc[0] == 5
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == 1
        assert pd.isna(result.iloc[3])


# ---------------------------------------------------------------------------
# Tests: compute_dimension_scores
# ---------------------------------------------------------------------------

class TestComputeDimensionScores:
    def test_mean_aggregation(self, sample_os_data, os_scale_def):
        dim = os_scale_def.dimensions[0]  # os_work_support: items 0-10, already reversed
        # First reverse the items that need reversing
        df_rev = sample_os_data.copy()
        for ri in os_scale_def.reverse_items:
            df_rev.iloc[:, ri] = reverse_score(df_rev.iloc[:, ri], os_scale_def.reverse_max)
        scores = compute_dimension_scores(df_rev, dim)
        assert scores.shape == (3,)
        assert scores.name == "os_work_support"
        # Row 0 items 0-10 raw=[6,2,5,5,3,2,4,3,4,4,4]
        # Reverse os2(pos1) 6-2=4, os5(pos4) 6-3=3, os6(pos5) 6-2=4, os8(pos7) 6-3=3
        # → [6,4,5,5,3,4,4,3,4,4,4] mean=46/11≈4.1818
        assert round(scores.iloc[0], 4) == 4.1818

    def test_mean_aggregation_row1(self, sample_os_data, os_scale_def):
        dim = os_scale_def.dimensions[0]
        df_rev = sample_os_data.copy()
        for ri in os_scale_def.reverse_items:
            df_rev.iloc[:, ri] = reverse_score(df_rev.iloc[:, ri], os_scale_def.reverse_max)
        scores = compute_dimension_scores(df_rev, dim)
        # Row 1 raw: [6,0,6,6,0,0,6,6,6,6,6]
        # os1 stays 6, os2(rev) 0→6, os3 6, os4 6, os5(rev) 0→6, os6(rev) 0→6, os7 6, os8(rev) 6→0, os9 6, os10 6, os11 6
        # → [6,6,6,6,6,6,6,0,6,6,6] mean=60/11≈5.454545
        assert round(scores.iloc[1], 4) == 5.4545

    def test_sum_aggregation(self, sample_os_data):
        dim = DimensionDef(name="test_sum", label="求和测试", items=[0, 1, 2], aggregation="sum")
        s = compute_dimension_scores(sample_os_data, dim)
        expected = sample_os_data.iloc[:, 0] + sample_os_data.iloc[:, 1] + sample_os_data.iloc[:, 2]
        pd.testing.assert_series_equal(s, expected, check_names=False)

    def test_missing_values_mean(self):
        df = pd.DataFrame({"a": [4, None, 6], "b": [5, 5, None], "c": [None, 3, 5]})
        dim = DimensionDef(name="x", label="x", items=["a", "b", "c"], aggregation="mean")
        result = compute_dimension_scores(df, dim)
        # Row 0: mean(4,5)=4.5; Row 1: mean(5,3)=4.0; Row 2: mean(6,5)=5.5
        assert result.iloc[0] == 4.5
        assert result.iloc[1] == 4.0
        assert result.iloc[2] == 5.5

    def test_all_missing(self):
        df = pd.DataFrame({"a": [None, None], "b": [None, None]})
        dim = DimensionDef(name="x", label="x", items=["a", "b"], aggregation="mean")
        result = compute_dimension_scores(df, dim)
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])


# ---------------------------------------------------------------------------
# Tests: compute_scale_scores
# ---------------------------------------------------------------------------

class TestComputeScaleScores:
    def test_returns_correct_dimensions(self, sample_os_data, os_scale_def):
        result = compute_scale_scores(sample_os_data, os_scale_def)
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["os_work_support", "os_value_identity", "os_benefit_care", "os_total"]
        assert result.shape == (3, 4)

    def test_reversal_applied(self, sample_os_data, os_scale_def):
        result = compute_scale_scores(sample_os_data, os_scale_def)
        # Row 1 os2 raw=0 → reversed to 6 → os_work_support comes out ~5.45 as calculated above
        assert round(result["os_work_support"].iloc[1], 4) == 5.4545

    def test_no_reverse_items(self, sample_we_data):
        scale = ScaleDefinition(
            name="工作投入",
            columns=[f"we{i+1}" for i in range(17)],
            reverse_items=[],
            reverse_max=6,
            dimensions=[
                DimensionDef(name="we_total", label="总量表", items=list(range(0, 17)), aggregation="mean"),
            ],
        )
        result = compute_scale_scores(sample_we_data, scale)
        assert result.shape == (3, 1)
        # Row 0: all items sum=70 → mean ≈ 4.1176
        assert round(result["we_total"].iloc[0], 2) == 4.12

    def test_reverse_item_out_of_range_ignored(self, sample_os_data, os_scale_def):
        os_scale_def.reverse_items.append(999)
        result = compute_scale_scores(sample_os_data, os_scale_def)
        assert result.shape == (3, 4)

    def test_empty_dimensions(self, sample_os_data, os_scale_def):
        os_scale_def.dimensions = []
        result = compute_scale_scores(sample_os_data, os_scale_def)
        assert result.empty
        assert result.shape[1] == 0


# ---------------------------------------------------------------------------
# Tests: ScaleDefinition
# ---------------------------------------------------------------------------

class TestScaleDefinition:
    def test_to_from_dict_roundtrip(self, os_scale_def):
        d = os_scale_def.to_dict()
        restored = ScaleDefinition.from_dict(d)
        assert restored.name == os_scale_def.name
        assert restored.reverse_items == os_scale_def.reverse_items
        assert restored.reverse_max == os_scale_def.reverse_max
        assert [dim.name for dim in restored.dimensions] == [dim.name for dim in os_scale_def.dimensions]

    def test_dimensiondef_to_from_dict(self):
        dim = DimensionDef(name="test", label="测试", items=[0, 1, 2], aggregation="sum")
        d = dim.to_dict()
        restored = DimensionDef.from_dict(d)
        assert restored.name == "test"
        assert restored.label == "测试"
        assert restored.items == [0, 1, 2]
        assert restored.aggregation == "sum"

    def test_dimensiondef_default_aggregation(self):
        dim = DimensionDef(name="test", label="测试", items=[0, 1])
        assert dim.aggregation == "mean"
