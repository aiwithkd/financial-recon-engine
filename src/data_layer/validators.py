from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ValidationResult:
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.passed = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


def validate_inputs(
    source: pd.DataFrame,
    target: pd.DataFrame,
    key_cols_src: list[str],
    key_cols_tgt: list[str],
) -> ValidationResult:
    result = ValidationResult(passed=True)

    # Existence checks
    if source.empty:
        result.add_error("Source file is empty.")
    if target.empty:
        result.add_error("Target file is empty.")
    if result.errors:
        return result

    # Key columns exist
    for col in key_cols_src:
        if col not in source.columns:
            result.add_error(f"Key column '{col}' not found in source file. Available: {list(source.columns)}")
    for col in key_cols_tgt:
        if col not in target.columns:
            result.add_error(f"Key column '{col}' not found in target file. Available: {list(target.columns)}")
    if result.errors:
        return result

    # Null keys
    src_null = source[key_cols_src].isnull().any(axis=1).sum()
    tgt_null = target[key_cols_tgt].isnull().any(axis=1).sum()
    if src_null > 0:
        result.add_warning(f"Source has {src_null} rows with null key values — these rows will be treated as MISSING_TGT.")
    if tgt_null > 0:
        result.add_warning(f"Target has {tgt_null} rows with null key values — these rows will be treated as MISSING_SRC.")

    # Duplicate keys
    src_dup = source.duplicated(subset=key_cols_src).sum()
    tgt_dup = target.duplicated(subset=key_cols_tgt).sum()
    if src_dup > 0:
        result.add_warning(f"Source has {src_dup} duplicate key rows. Only the first occurrence will be used.")
    if tgt_dup > 0:
        result.add_warning(f"Target has {tgt_dup} duplicate key rows. Only the first occurrence will be used.")

    # Size warning
    total = len(source) + len(target)
    if total > 100_000:
        result.add_warning(f"Large file detected ({total:,} total rows). Reconciliation may take 10–30 seconds.")

    return result
