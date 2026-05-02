from __future__ import annotations

import re

import numpy as np
import pandas as pd
from dateutil import parser as date_parser


_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
_CUSIP_RE = re.compile(r"^[0-9A-Z]{9}$")


def normalize_column(series: pd.Series, strategy: str) -> pd.Series:
    """Apply a named normalisation strategy to a Series."""
    s = series.copy().astype(str).str.strip()
    if strategy == "uppercase":
        return s.str.upper()
    if strategy == "lowercase":
        return s.str.lower()
    if strategy == "isin":
        return s.str.upper().str.replace(r"\s+", "", regex=True)
    if strategy == "numeric":
        return _normalize_numeric_str(s)
    if strategy == "date":
        return _normalize_date_str(s)
    if strategy == "none":
        return s
    return s


def _normalize_numeric_str(series: pd.Series) -> pd.Series:
    """Remove commas, currency symbols, strip leading zeros from identifiers."""
    cleaned = series.str.replace(r"[,$£€]", "", regex=True).str.strip()
    # Attempt coercion to remove leading zeros for numeric-looking values
    numeric = pd.to_numeric(cleaned, errors="coerce")
    mask = numeric.notna()
    result = cleaned.copy()
    result[mask] = numeric[mask].apply(lambda x: f"{x:g}")
    return result


def _normalize_date_str(series: pd.Series) -> pd.Series:
    """Parse heterogeneous date strings to ISO YYYY-MM-DD."""
    def _parse(val: str) -> str:
        if not val or val.lower() in ("nan", "none", "nat", ""):
            return ""
        try:
            return date_parser.parse(val, dayfirst=False).strftime("%Y-%m-%d")
        except Exception:
            return val

    return series.apply(_parse)


def coerce_numeric(series: pd.Series) -> pd.Series:
    """Best-effort coercion to float, preserving NaN."""
    cleaned = series.astype(str).str.replace(r"[,$£€,]", "", regex=True).str.strip()
    return pd.to_numeric(cleaned, errors="coerce")


def coerce_date(series: pd.Series) -> pd.Series:
    """Best-effort coercion to datetime."""
    return pd.to_datetime(series, errors="coerce", infer_datetime_format=True)


def is_isin(series: pd.Series) -> pd.Series:
    """Boolean mask: True where value matches ISIN format."""
    return series.astype(str).str.strip().str.upper().str.match(_ISIN_RE)
