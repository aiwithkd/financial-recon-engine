from __future__ import annotations

import pandas as pd

from src.engine.models import FieldConfig, KPISummary


def build_kpis(
    matched: pd.DataFrame,
    source_only: pd.DataFrame,
    target_only: pd.DataFrame,
    total_source: int,
    total_target: int,
) -> KPISummary:
    status_counts = matched["recon_status"].value_counts().to_dict() if not matched.empty else {}
    sev_counts = matched["recon_severity"].value_counts().to_dict() if not matched.empty else {}

    n_matched = status_counts.get("MATCHED", 0)
    n_tolerance = status_counts.get("TOLERANCE", 0)
    n_breaks = status_counts.get("BREAK", 0)
    n_missing_src = len(target_only)
    n_missing_tgt = len(source_only)

    total_processed = n_matched + n_tolerance + n_breaks + n_missing_src + n_missing_tgt
    match_rate = round((n_matched + n_tolerance) / max(total_processed, 1) * 100, 2)
    break_rate = round(n_breaks / max(total_processed, 1) * 100, 2)

    return KPISummary(
        total_source_rows=total_source,
        total_target_rows=total_target,
        matched=n_matched,
        tolerance_hits=n_tolerance,
        breaks=n_breaks,
        missing_src=n_missing_src,
        missing_tgt=n_missing_tgt,
        match_rate_pct=match_rate,
        break_rate_pct=break_rate,
        high_severity_breaks=sev_counts.get("HIGH", 0),
        medium_severity_breaks=sev_counts.get("MEDIUM", 0),
        low_severity_breaks=sev_counts.get("LOW", 0),
    )


def build_field_stats(
    matched: pd.DataFrame,
    field_configs: dict[str, FieldConfig],
) -> pd.DataFrame:
    rows = []
    for field in field_configs:
        within_col = f"{field}_within_tol"
        variance_col = f"{field}_variance"
        if within_col not in matched.columns:
            continue
        total = len(matched)
        within = matched[within_col].sum()
        outside = total - within
        break_rate = round(outside / max(total, 1) * 100, 2)
        avg_var = matched[variance_col].mean() if variance_col in matched.columns else None
        max_var = matched[variance_col].max() if variance_col in matched.columns else None
        rows.append({
            "field": field,
            "total_compared": total,
            "within_tolerance": int(within),
            "outside_tolerance": int(outside),
            "break_rate_pct": break_rate,
            "avg_variance": round(avg_var, 6) if avg_var is not None and pd.notna(avg_var) else None,
            "max_variance": round(max_var, 6) if max_var is not None and pd.notna(max_var) else None,
            "tolerance_type": field_configs[field].tolerance_type,
            "tolerance_value": field_configs[field].tolerance_value,
            "is_regulatory": field_configs[field].is_regulatory,
        })
    return pd.DataFrame(rows)
