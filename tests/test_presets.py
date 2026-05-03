"""
Tests for presets.py – pre-configured scale definitions for the
双师型护理教师数字素养 questionnaire.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from utils.presets import (
    build_presets,
    get_default_presets,
    PRESET_SCALES,
)
from utils.scoring import ScaleDefinition


class TestPresetScales:
    def test_four_scales_defined(self):
        presets = get_default_presets()
        names = [s.name for s in presets]
        assert "OS" in names
        assert "WE" in names
        assert "DC" in names
        assert "DL" in names
        assert len(presets) == 4

    def test_os_has_11_reverse_items(self):
        os_scale = [s for s in get_default_presets() if s.name == "OS"][0]
        assert len(os_scale.reverse_items) == 11
        # Specific indices from R script
        assert 1 in os_scale.reverse_items   # os2
        assert 4 in os_scale.reverse_items   # os5
        assert 7 in os_scale.reverse_items   # os8
        assert 22 in os_scale.reverse_items  # os23

    def test_os_has_4_dimensions(self):
        os_scale = [s for s in get_default_presets() if s.name == "OS"][0]
        dim_names = [d.name for d in os_scale.dimensions]
        assert "os_work_support" in dim_names
        assert "os_value_identity" in dim_names
        assert "os_benefit_care" in dim_names
        assert "os_total" in dim_names

    def test_we_has_no_reverse_items(self):
        we_scale = [s for s in get_default_presets() if s.name == "WE"][0]
        assert we_scale.reverse_items == []

    def test_dc_has_7_dimensions(self):
        dc_scale = [s for s in get_default_presets() if s.name == "DC"][0]
        assert len(dc_scale.dimensions) == 7

    def test_dl_has_6_dimensions(self):
        dl_scale = [s for s in get_default_presets() if s.name == "DL"][0]
        assert len(dl_scale.dimensions) == 6

    def test_column_ranges_non_overlapping(self):
        """Ensure scale column ranges don't overlap."""
        presets = get_default_presets()
        all_cols = set()
        for s in presets:
            for c in s.columns:
                assert c not in all_cols, f"Column {c} appears in multiple scales"
                all_cols.add(c)

    def test_dimension_items_within_scale_range(self):
        for scale in get_default_presets():
            n_cols = len(scale.columns)
            for dim in scale.dimensions:
                for item in dim.items:
                    assert 0 <= item < n_cols, (
                        f"{scale.name}/{dim.name}: item {item} out of range [0, {n_cols})"
                    )

    def test_all_dimensions_use_mean(self):
        for scale in get_default_presets():
            for dim in scale.dimensions:
                assert dim.aggregation == "mean", (
                    f"{scale.name}/{dim.name} should use mean aggregation"
                )

    def test_build_presets_with_custom_ranges(self):
        """build_presets allows overriding column ranges."""
        custom = build_presets(
            os_range=(10, 33),
            we_range=(33, 50),
            dc_range=(50, 72),
            dl_range=(72, 105),
        )
        os_scale = custom["OS"]
        assert os_scale.columns == list(range(10, 33))
        # Dimensions use 0-based indices within the scale, should remain unchanged
        assert os_scale.dimensions[0].items[0] == 0

    def test_preset_serialization_roundtrip(self):
        presets = get_default_presets()
        for scale in presets:
            d = scale.to_dict()
            restored = ScaleDefinition.from_dict(d)
            assert restored.name == scale.name
            assert restored.reverse_items == scale.reverse_items
            assert len(restored.dimensions) == len(scale.dimensions)
