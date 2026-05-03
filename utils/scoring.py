"""
Scoring module – reverse-code items and compute dimension scores from raw
questionnaire items.

Supports:
  - Reverse scoring: max_val - x
  - Aggregation: mean (default) or sum
  - Scale → Dimension hierarchy
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DimensionDef:
    """Definition of one dimension within a scale.

    Attributes:
        name: Machine-friendly identifier, e.g. "os_work_support".
        label: Human-readable Chinese name.
        items: Indices (0‑based within the scale) of the items belonging to
               this dimension, or column names.
        aggregation: "mean" or "sum".
    """

    name: str
    label: str
    items: list[int | str]
    aggregation: Literal["mean", "sum"] = "mean"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "items": self.items,
            "aggregation": self.aggregation,
        }

    @classmethod
    def from_dict(cls, d: dict) -> DimensionDef:
        return cls(
            name=d["name"],
            label=d["label"],
            items=d["items"],
            aggregation=d.get("aggregation", "mean"),
        )


@dataclass
class ScaleDefinition:
    """Full definition of a questionnaire scale.

    Attributes:
        name: Machine-friendly scale id, e.g. "OS".
        label: Human-readable name, e.g. "组织支持".
        columns: Column names or indices in the raw DataFrame for this scale.
        reverse_items: 0‑based indices (within the scale's columns) that need
                       reverse scoring.
        reverse_max: Maximum value on the Likert scale (e.g. 6 for 0‑6).
        dimensions: List of DimensionDef that define sub‑scales / totals.
    """

    name: str
    label: str = ""
    columns: list[int | str] = field(default_factory=list)
    reverse_items: list[int] = field(default_factory=list)
    reverse_max: int = 6
    dimensions: list[DimensionDef] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "columns": self.columns,
            "reverse_items": self.reverse_items,
            "reverse_max": self.reverse_max,
            "dimensions": [d.to_dict() for d in self.dimensions],
        }

    @classmethod
    def from_dict(cls, d: dict) -> ScaleDefinition:
        return cls(
            name=d["name"],
            label=d.get("label", ""),
            columns=d.get("columns", []),
            reverse_items=d.get("reverse_items", []),
            reverse_max=d.get("reverse_max", 6),
            dimensions=[DimensionDef.from_dict(dim) for dim in d.get("dimensions", [])],
        )


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def reverse_score(series: pd.Series, max_val: int | float = 6) -> pd.Series:
    """Reverse-score a Likert-scale series: *max_val - x*.

    Missing values (NaN) are preserved.
    """
    return series.apply(lambda x: max_val - x if pd.notna(x) else x)


def _resolve_columns(df: pd.DataFrame, items: list[int | str]) -> list[str]:
    """Convert item indices or names to column-name list."""
    cols = []
    for item in items:
        if isinstance(item, int):
            cols.append(df.columns[item])
        else:
            cols.append(item)
    return cols


def compute_dimension_scores(df: pd.DataFrame, dim: DimensionDef) -> pd.Series:
    """Compute scores for a single dimension.

    Parameters
    ----------
    df : pd.DataFrame
        Data already reversed where needed.  Columns must match *dim.items*.
    dim : DimensionDef
        Dimension definition.

    Returns
    -------
    pd.Series named after *dim.name*.
    """
    cols = _resolve_columns(df, dim.items)
    sub = df[cols]

    if dim.aggregation == "sum":
        scores = sub.sum(axis=1, numeric_only=False)
    else:
        scores = sub.mean(axis=1, numeric_only=False)

    scores.name = dim.name
    return scores


def compute_scale_scores(df: pd.DataFrame, scale: ScaleDefinition) -> pd.DataFrame:
    """Reverse-code items and compute all dimension scores for one scale.

    Parameters
    ----------
    df : pd.DataFrame
        Raw data containing (at least) the columns specified in *scale.columns*.
    scale : ScaleDefinition
        Scale definition.

    Returns
    -------
    pd.DataFrame
        One column per dimension, named after ``DimensionDef.name``.
    """
    cols = _resolve_columns(df, scale.columns)
    work = df[cols].copy()

    # Reverse-code
    n_cols = len(cols)
    for ri in scale.reverse_items:
        if 0 <= ri < n_cols:
            work.iloc[:, ri] = reverse_score(work.iloc[:, ri], scale.reverse_max)

    # Compute each dimension
    results = {}
    for dim in scale.dimensions:
        results[dim.name] = compute_dimension_scores(work, dim)

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results)
