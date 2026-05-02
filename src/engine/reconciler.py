from __future__ import annotations

import pandas as pd

from src.data_layer.validators import validate_inputs
from src.engine import matcher, tolerance_engine, variance_classifier, summary_builder
from src.engine.models import ReconciliationReport, ReconConfig


def run(
    source: pd.DataFrame,
    target: pd.DataFrame,
    config: ReconConfig,
) -> ReconciliationReport:
    """
    Main orchestration entry point. Runs the full reconciliation pipeline.
    """
    src_keys = [k.source_col for k in config.matching_keys]
    tgt_keys = [k.target_col for k in config.matching_keys]

    # 1. Pre-flight validation
    validation = validate_inputs(source, target, src_keys, tgt_keys)
    warnings = validation.warnings[:]
    if not validation.passed:
        raise ValueError("\n".join(validation.errors))

    # 2. Match rows — three-pass join
    matched, source_only, target_only = matcher.join(source, target, config.matching_keys)

    # 3. Evaluate tolerances on matched pairs
    if not matched.empty and config.field_configs:
        matched = tolerance_engine.evaluate(matched, config.field_configs)

        # 4. Classify each row: MATCHED / TOLERANCE / BREAK
        matched = variance_classifier.classify(matched, config.field_configs, config.classification_mode)
    else:
        matched["recon_status"] = "MATCHED"
        matched["recon_severity"] = "LOW"

    # 5. Tag missing rows
    source_only, target_only = variance_classifier.tag_missing(
        source_only, target_only, config.missing_row_severity
    )

    # 6. Build KPIs and field stats
    kpis = summary_builder.build_kpis(matched, source_only, target_only, len(source), len(target))
    field_stats = summary_builder.build_field_stats(matched, config.field_configs)

    # 7. Separate break and tolerance records
    break_records = matched[matched["recon_status"] == "BREAK"].reset_index(drop=True)
    tolerance_records = matched[matched["recon_status"] == "TOLERANCE"].reset_index(drop=True)
    matched_clean = matched[matched["recon_status"] == "MATCHED"].reset_index(drop=True)

    return ReconciliationReport(
        kpis=kpis,
        break_records=break_records,
        tolerance_records=tolerance_records,
        matched_df=matched_clean,
        source_only_df=source_only,
        target_only_df=target_only,
        field_stats=field_stats,
        config=config,
        warnings=warnings,
    )
