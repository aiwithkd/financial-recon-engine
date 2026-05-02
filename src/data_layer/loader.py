from __future__ import annotations

import io
from pathlib import Path
from typing import Union

import pandas as pd


def load_file(source: Union[str, Path, io.BytesIO], sheet_name: int = 0) -> pd.DataFrame:
    """Load CSV or Excel into a DataFrame with basic normalisation applied."""
    if isinstance(source, (str, Path)):
        path = Path(source)
        suffix = path.suffix.lower()
    else:
        suffix = ".xlsx"

    if suffix in (".xlsx", ".xls"):
        df = pd.read_excel(source, sheet_name=sheet_name, dtype=str)
    elif suffix == ".csv":
        df = _read_csv_with_encoding_detection(source)
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Expected .csv, .xlsx, or .xls")

    return _clean(df)


def _read_csv_with_encoding_detection(source) -> pd.DataFrame:
    """Try UTF-8 first, fall back to latin-1 which never fails."""
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(source, dtype=str, encoding=enc)
        except UnicodeDecodeError:
            if hasattr(source, "seek"):
                source.seek(0)
    raise ValueError("Could not decode file with UTF-8 or latin-1 encoding.")


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise column names and strip leading/trailing whitespace from all cells."""
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    # Drop fully unnamed columns (Excel artefacts)
    df = df.loc[:, ~df.columns.str.match(r"^unnamed")]

    # Deduplicate column names
    seen: dict[str, int] = {}
    new_cols = []
    for col in df.columns:
        if col in seen:
            seen[col] += 1
            new_cols.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            new_cols.append(col)
    df.columns = new_cols

    # Strip whitespace from all string cells
    str_cols = df.select_dtypes(include="object").columns
    df[str_cols] = df[str_cols].apply(lambda s: s.str.strip())

    # Drop rows that are entirely empty
    df = df.dropna(how="all").reset_index(drop=True)

    return df


def get_sheet_names(source: Union[str, Path, io.BytesIO]) -> list[str]:
    """Return sheet names for Excel files."""
    try:
        xl = pd.ExcelFile(source)
        return xl.sheet_names
    except Exception:
        return []
