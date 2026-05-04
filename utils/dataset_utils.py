from __future__ import annotations

from pathlib import Path

import pandas as pd

from .file_store import ensure_dir, new_id, now_iso, safe_name, write_json


def read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in [".xlsx", ".xls"]:
        return pd.read_excel(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported file type: {suffix}")


def column_type(series: pd.Series) -> str:
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    return "categorical"


def build_columns_metadata(df: pd.DataFrame) -> list[dict]:
    rows = []
    for col in df.columns:
        s = df[col]
        numeric = pd.to_numeric(s, errors="coerce")
        is_num = pd.api.types.is_numeric_dtype(s) or numeric.notna().sum() >= max(3, int(len(s) * 0.7))
        rows.append(
            {
                "name": str(col),
                "type": "numeric" if is_num else column_type(s),
                "missing_count": int(s.isna().sum()),
                "missing_rate": round(float(s.isna().mean()), 6),
                "unique_count": int(s.nunique(dropna=True)),
                "mean": round(float(numeric.mean()), 6) if is_num else None,
                "std": round(float(numeric.std()), 6) if is_num else None,
                "min": round(float(numeric.min()), 6) if is_num else None,
                "max": round(float(numeric.max()), 6) if is_num else None,
            }
        )
    return rows


def create_metadata(dataset_dir: Path, df: pd.DataFrame, dataset_id: str, name: str, original_file: Path) -> dict:
    prepared_dir = ensure_dir(dataset_dir / "prepared")
    metadata_dir = ensure_dir(dataset_dir / "metadata")
    data_csv = prepared_dir / "data.csv"
    df.to_csv(data_csv, index=False)

    columns = build_columns_metadata(df)
    preview = df.head(20).where(pd.notna(df), None).to_dict(orient="records")
    missing = [
        {
            "name": str(col),
            "missing_count": int(df[col].isna().sum()),
            "missing_rate": round(float(df[col].isna().mean()), 6),
        }
        for col in df.columns
    ]
    descriptive = [row for row in columns if row["type"] == "numeric"]

    dataset = {
        "dataset_id": dataset_id,
        "name": name,
        "original_filename": original_file.name,
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "prepared_path": str(data_csv.relative_to(dataset_dir)),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }

    write_json(dataset_dir / "dataset.json", dataset)
    write_json(metadata_dir / "columns.json", columns)
    write_json(metadata_dir / "preview.json", preview)
    write_json(metadata_dir / "missing_summary.json", missing)
    write_json(metadata_dir / "descriptive_summary.json", descriptive)
    return dataset


def ingest_dataset(study_dir: Path, original_file: Path, display_name: str | None = None) -> dict:
    df = read_table(original_file)
    dataset_id = new_id("dataset")
    name = display_name or safe_name(original_file.stem)
    dataset_dir = study_dir / "datasets" / dataset_id
    ensure_dir(dataset_dir / "original")
    stored_original = dataset_dir / "original" / original_file.name
    original_file.replace(stored_original)
    return create_metadata(dataset_dir, df, dataset_id, name, stored_original)


def load_prepared_data(dataset_dir: Path) -> pd.DataFrame:
    return pd.read_csv(dataset_dir / "prepared" / "data.csv")


def numeric_columns(df: pd.DataFrame) -> list[str]:
    cols = []
    for col in df.columns:
        numeric = pd.to_numeric(df[col], errors="coerce")
        if numeric.notna().sum() >= max(3, int(len(df) * 0.7)):
            cols.append(str(col))
    return cols


def quantile_thresholds(series: pd.Series) -> tuple[float, float, float]:
    s = pd.to_numeric(series, errors="coerce").dropna()
    q = s.quantile([0.25, 0.50, 0.75]).tolist()
    return tuple(round(float(x), 6) for x in q)
