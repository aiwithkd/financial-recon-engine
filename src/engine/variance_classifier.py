from __future__ import annotations

import pandas as pd

from src.engine.models import ClassificationMode, FieldConfig, RowStatus


def classify(
    matched: pd.DataFrame,
    field_configs: dict[str, FieldConfig],
    mode: ClassificationMode,
) -> pd.DataFrame:
    """
    Add recon_status and recon_severity columns to matched DataFrame.
    """
    result = matched.copy()
    within_cols = [f"{f}_within_tol" for f in field_configs if f"{f}_within_tol" in result.columns]

    if not within_cols:
        result["recon_status"] = "MATCHED"
        result["recon_severity"] = "LOW"
        return result

    within_matrix = result[within_cols]
    all_within = within_matrix.all(axis=1)
    any_outside = ~within_matrix.all(axis=1)
    all_outside = (~within_matrix).all(axis=1)

    if mode == "worst_field":
        # BREAK if any field outside tolerance; TOLERANCE if all within
        result["recon_status"] = "MATCHED"
        result.loc[within_matrix.all(axis=1), "recon_status"] = "MATCHED"
        # TOLERANCE: within tol but not exact (variance > 0 but within threshold)
        variance_cols = [f"{f}_variance" for f in field_configs if f"{f}_variance" in result.columns]
        if variance_cols:
            any_nonzero = (result[variance_cols].fillna(0) > 0).any(axis=1)
            result.loc[all_within & any_nonzero, "recon_status"] = "TOLERANCE"
        result.loc[any_outside, "recon_status"] = "BREAK"
    else:  # any_break
        result["recon_status"] = "MATCHED"
        result.loc[any_outside, "recon_status"] = "BREAK"

    # Severity for BREAKs
    result["recon_severity"] = "LOW"
    result.loc[result["recon_status"] == "TOLERANCE", "recon_severity"] = "LOW"

    # Severity based on field weights and regulatory flags
    def _compute_severity(row) -> str:
        if row["recon_status"] != "BREAK":
            return row["recon_severity"]
        for field, cfg in field_configs.items():
            within_col = f"{field}_within_tol"
            if within_col in row.index and not row[within_col]:
                if cfg.is_regulatory:
                    return "HIGH"
                if cfg.weight >= 0.8:
                    return "MEDIUM"
        return "LOW"

    break_mask = result["recon_status"] == "BREAK"
    if break_mask.any():
        result.loc[break_mask, "recon_severity"] = result[break_mask].apply(_compute_severity, axis=1)

    return result


def tag_missing(
    source_only: pd.DataFrame,
    target_only: pd.DataFrame,
    severity: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    src = source_only.copy()
    tgt = target_only.copy()
    src["recon_status"] = "MISSING_TGT"
    src["recon_severity"] = severity
    tgt["recon_status"] = "MISSING_SRC"
    tgt["recon_severity"] = severity
    return src, tgt
