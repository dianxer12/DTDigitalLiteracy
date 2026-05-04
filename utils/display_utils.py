from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st


def dataframe_from_json(items: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(items) if items else pd.DataFrame()


def show_json(label: str, data) -> None:
    with st.expander(label, expanded=False):
        st.json(data)


def show_csv_table(path: Path) -> None:
    st.subheader(path.name)
    try:
        st.dataframe(pd.read_csv(path), width="stretch")
    except Exception as exc:
        st.warning(f"无法渲染 {path.name}：{exc}")


def download_file(path: Path, label: str | None = None, key_suffix: str = "") -> None:
    st.download_button(
        label or f"下载 {path.name}",
        data=path.read_bytes(),
        file_name=path.name,
        mime="application/octet-stream",
        key=f"{path}_{key_suffix}",
    )
