from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import pandas as pd

from src.data_layer.normalizer import coerce_numeric, coerce_date, is_isin


ColType = Literal["numeric", "date", "isin", "identifier", "text"]

_ISIN_HINT = re.compile(r"isin|security_id|secid", re.I)
_DATE_HINT = re.compile(r"date|dt|_at$|_on$|timestamp", re.I)
_NUMERIC_HINT = re.compile(r"price|qty|quantity|value|amount|pnl|nav|cost|volume|units|weight|rate|fee|commission|interest", re.I)
_ID_HINT = re.compile(r"id$|_id$|account|acct|ref|code|ticker|cusip|sedol|lei|number|num$", re.I)


@dataclass
class ColumnProfile:
    name: str
    inferred_type: ColType
    null_rate: float
    uniqueness_ratio: float
    sample_values: list


def infer_schema(df: pd.DataFrame) -> dict[str, ColumnProfile]:
    profiles: dict[str, ColumnProfile] = {}
    for col in df.columns:
        s = df[col]
        null_rate = s.isna().mean()
        non_null = s.dropna().astype(str).str.strip()
        uniqueness = non_null.nunique() / max(len(non_null), 1)
        col_type = _infer_type(col, non_null)
        profiles[col] = ColumnProfile(
            name=col,
            inferred_type=col_type,
            null_rate=round(null_rate, 4),
            uniqueness_ratio=round(uniqueness, 4),
            sample_values=non_null.head(3).tolist(),
        )
    return profiles


def _infer_type(col_name: str, series: pd.Series) -> ColType:
    if series.empty:
        return "text"

    # ISIN check first — high confidence pattern
    if _ISIN_HINT.search(col_name) or is_isin(series).mean() > 0.8:
        return "isin"

    # Date check
    if _DATE_HINT.search(col_name):
        return "date"
    coerced_date = coerce_date(series)
    if coerced_date.notna().mean() > 0.85:
        return "date"

    # Numeric check
    if _NUMERIC_HINT.search(col_name):
        return "numeric"
    coerced_num = coerce_numeric(series)
    if coerced_num.notna().mean() > 0.85:
        return "numeric"

    # Identifier check (high uniqueness, short values)
    if _ID_HINT.search(col_name):
        return "identifier"
    avg_len = series.str.len().mean()
    if avg_len and avg_len < 25 and series.nunique() / max(len(series), 1) > 0.7:
        return "identifier"

    return "text"
