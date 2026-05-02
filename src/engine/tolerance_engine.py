from __future__ import annotations

import numpy as np
import pandas as pd

from src.engine.models import FieldConfig, ToleranceType


def evaluate(
    matched: pd.DataFrame,
    field_configs: dict[str, FieldConfig],
) -> pd.DataFrame:
    """
    For each configured field, compute variance and within_tolerance flag.
    Expects matched to have columns {field}_src and {field}_tgt.
    Returns matched with added columns: {field}_variance, {field}_within_tol.
    """
    result = matched.copy()

    for field, cfg in field_configs.items():
        # Support both suffixed (from matcher) and plain column names
        src_col = f"{field}_src" if f"{field}_src" in result.columns else field
        tgt_col = f"{field}_tgt" if f"{field}_tgt" in result.columns else field

        if src_col not in result.columns or tgt_col not in result.columns:
            continue

        variance_col = f"{field}_variance"
        within_col = f"{field}_within_tol"

        if cfg.tolerance_type == "exact":
            result[variance_col] = (
                result[src_col].astype(str).str.strip().str.upper()
                != result[tgt_col].astype(str).str.strip().str.upper()
            ).astype(float)
            result[within_col] = result[variance_col] == 0.0

        elif cfg.tolerance_type == "absolute":
            src_num = pd.to_numeric(result[src_col].astype(str).str.replace(",", ""), errors="coerce")
            tgt_num = pd.to_numeric(result[tgt_col].astype(str).str.replace(",", ""), errors="coerce")
            abs_diff = (src_num - tgt_num).abs()
            result[variance_col] = abs_diff
            result[within_col] = abs_diff <= cfg.tolerance_value

        elif cfg.tolerance_type == "percentage":
            src_num = pd.to_numeric(result[src_col].astype(str).str.replace(",", ""), errors="coerce")
            tgt_num = pd.to_numeric(result[tgt_col].astype(str).str.replace(",", ""), errors="coerce")
            abs_diff = (src_num - tgt_num).abs()
            denom = src_num.abs().replace(0, np.nan)
            pct_diff = abs_diff / denom * 100
            result[variance_col] = pct_diff.round(6)
            result[within_col] = pct_diff <= cfg.tolerance_value

        elif cfg.tolerance_type == "basis_points":
            src_num = pd.to_numeric(result[src_col].astype(str).str.replace(",", ""), errors="coerce")
            tgt_num = pd.to_numeric(result[tgt_col].astype(str).str.replace(",", ""), errors="coerce")
            abs_diff = (src_num - tgt_num).abs()
            denom = src_num.abs().replace(0, np.nan)
            bps_diff = abs_diff / denom * 10_000
            result[variance_col] = bps_diff.round(4)
            result[within_col] = bps_diff <= cfg.tolerance_value

        elif cfg.tolerance_type == "date_days":
            src_dt = pd.to_datetime(result[src_col], errors="coerce")
            tgt_dt = pd.to_datetime(result[tgt_col], errors="coerce")
            day_diff = (src_dt - tgt_dt).abs().dt.days
            result[variance_col] = day_diff
            result[within_col] = day_diff <= int(cfg.tolerance_value)

        # NaN in either side → not within tolerance
        null_mask = result[src_col].isna() | result[tgt_col].isna()
        result.loc[null_mask, within_col] = False

    return result
