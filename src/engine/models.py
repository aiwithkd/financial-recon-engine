from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional

import pandas as pd


ToleranceType = Literal["absolute", "percentage", "basis_points", "exact", "date_days"]
Severity = Literal["HIGH", "MEDIUM", "LOW"]
RowStatus = Literal["MATCHED", "TOLERANCE", "BREAK", "MISSING_SRC", "MISSING_TGT"]
ClassificationMode = Literal["worst_field", "any_break"]


@dataclass
class MatchKey:
    source_col: str
    target_col: str
    normalization: str = "none"


@dataclass
class FieldConfig:
    tolerance_type: ToleranceType
    tolerance_value: float
    weight: float = 1.0
    is_regulatory: bool = False


@dataclass
class ReconConfig:
    matching_keys: list[MatchKey]
    field_configs: dict[str, FieldConfig]
    classification_mode: ClassificationMode = "worst_field"
    missing_row_severity: Severity = "HIGH"
    use_case_name: str = "Custom"


@dataclass
class KPISummary:
    total_source_rows: int
    total_target_rows: int
    matched: int
    tolerance_hits: int
    breaks: int
    missing_src: int
    missing_tgt: int
    match_rate_pct: float
    break_rate_pct: float
    high_severity_breaks: int
    medium_severity_breaks: int
    low_severity_breaks: int


@dataclass
class ReconciliationReport:
    kpis: KPISummary
    break_records: pd.DataFrame
    tolerance_records: pd.DataFrame
    matched_df: pd.DataFrame
    source_only_df: pd.DataFrame
    target_only_df: pd.DataFrame
    field_stats: pd.DataFrame
    config: ReconConfig
    run_timestamp: datetime = field(default_factory=datetime.utcnow)
    warnings: list[str] = field(default_factory=list)
