from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
import xlsxwriter

from src.engine.models import ReconciliationReport


# Colour palette
_RED = "#FFCCCC"
_AMBER = "#FFF2CC"
_GREEN = "#CCFFCC"
_GREY = "#E8E8E8"
_BLUE_HEADER = "#1F3864"
_WHITE = "#FFFFFF"


def export(report: ReconciliationReport) -> bytes:
    """Build a colour-coded multi-sheet Excel report and return as bytes."""
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True, "nan_inf_to_errors": True})

    _add_summary_sheet(wb, report)
    _add_data_sheet(wb, "Breaks", report.break_records, _RED)
    _add_data_sheet(wb, "Tolerance Hits", report.tolerance_records, _AMBER)
    _add_data_sheet(wb, "Matched", report.matched_df, _GREEN)
    _add_data_sheet(wb, "Missing in Target", report.source_only_df, _GREY)
    _add_data_sheet(wb, "Missing in Source", report.target_only_df, _GREY)
    _add_field_stats_sheet(wb, report)
    _add_config_audit_sheet(wb, report)

    wb.close()
    return buf.getvalue()


def _header_fmt(wb, bg="#1F3864"):
    return wb.add_format({
        "bold": True, "font_color": "#FFFFFF", "bg_color": bg,
        "border": 1, "text_wrap": True, "valign": "vcenter",
    })


def _cell_fmt(wb, bg="#FFFFFF"):
    return wb.add_format({"bg_color": bg, "border": 1, "valign": "top", "text_wrap": False})


def _add_summary_sheet(wb, report: ReconciliationReport):
    ws = wb.add_worksheet("Summary")
    ws.set_column(0, 1, 36)

    title_fmt = wb.add_format({"bold": True, "font_size": 14, "font_color": _BLUE_HEADER})
    label_fmt = wb.add_format({"bold": True})
    kpi_fmt = wb.add_format({"num_format": "#,##0", "border": 1})
    pct_fmt = wb.add_format({"num_format": "0.00\"%\"", "border": 1})

    ws.write(0, 0, f"Reconciliation Report — {report.config.use_case_name}", title_fmt)
    ws.write(1, 0, f"Run at: {report.run_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    ws.write(2, 0, "")

    kpis = [
        ("Source Rows", report.kpis.total_source_rows, kpi_fmt),
        ("Target Rows", report.kpis.total_target_rows, kpi_fmt),
        ("Matched", report.kpis.matched, kpi_fmt),
        ("Tolerance Hits", report.kpis.tolerance_hits, kpi_fmt),
        ("Breaks", report.kpis.breaks, kpi_fmt),
        ("Missing in Target", report.kpis.missing_tgt, kpi_fmt),
        ("Missing in Source", report.kpis.missing_src, kpi_fmt),
        ("Match Rate %", report.kpis.match_rate_pct / 100, pct_fmt),
        ("Break Rate %", report.kpis.break_rate_pct / 100, pct_fmt),
        ("High Severity Breaks", report.kpis.high_severity_breaks, kpi_fmt),
        ("Medium Severity Breaks", report.kpis.medium_severity_breaks, kpi_fmt),
        ("Low Severity Breaks", report.kpis.low_severity_breaks, kpi_fmt),
    ]

    row = 3
    for label, val, fmt in kpis:
        ws.write(row, 0, label, label_fmt)
        ws.write(row, 1, val, fmt)
        row += 1

    if report.warnings:
        row += 1
        ws.write(row, 0, "Warnings", label_fmt)
        for w in report.warnings:
            row += 1
            ws.write(row, 0, w)

    ws.freeze_panes(0, 0)


def _add_data_sheet(wb, name: str, df: pd.DataFrame, row_color: str):
    ws = wb.add_worksheet(name[:31])
    if df.empty:
        ws.write(0, 0, f"No {name} records.")
        return

    hdr = _header_fmt(wb)
    cell = _cell_fmt(wb, row_color)

    for col_idx, col in enumerate(df.columns):
        ws.write(0, col_idx, col, hdr)
        ws.set_column(col_idx, col_idx, max(12, min(len(str(col)) + 4, 40)))

    for row_idx, row_data in enumerate(df.itertuples(index=False), start=1):
        for col_idx, val in enumerate(row_data):
            safe = "" if (val is None or (isinstance(val, float) and val != val)) else val
            ws.write(row_idx, col_idx, safe, cell)

    ws.freeze_panes(1, 0)
    ws.autofilter(0, 0, len(df), len(df.columns) - 1)


def _add_field_stats_sheet(wb, report: ReconciliationReport):
    _add_data_sheet(wb, "Field Stats", report.field_stats, _WHITE)


def _add_config_audit_sheet(wb, report: ReconciliationReport):
    ws = wb.add_worksheet("Config Audit")
    ws.set_column(0, 1, 40)
    label_fmt = wb.add_format({"bold": True})

    rows = [
        ("Use Case", report.config.use_case_name),
        ("Classification Mode", report.config.classification_mode),
        ("Missing Row Severity", report.config.missing_row_severity),
        ("Run Timestamp (UTC)", report.run_timestamp.isoformat()),
        ("", ""),
        ("Matching Keys", ""),
    ]
    r = 0
    for label, val in rows:
        ws.write(r, 0, label, label_fmt if label else None)
        ws.write(r, 1, str(val) if val else "")
        r += 1

    for k in report.config.matching_keys:
        ws.write(r, 0, f"  {k.source_col} ↔ {k.target_col}")
        ws.write(r, 1, f"normalisation: {k.normalization}")
        r += 1

    r += 1
    ws.write(r, 0, "Field Configurations", label_fmt)
    r += 1
    ws.write(r, 0, "Field")
    ws.write(r, 1, "Tolerance Type")
    ws.write(r, 2, "Threshold")
    ws.write(r, 3, "Weight")
    ws.write(r, 4, "Regulatory")
    r += 1

    for field, cfg in report.config.field_configs.items():
        ws.write(r, 0, field)
        ws.write(r, 1, cfg.tolerance_type)
        ws.write(r, 2, cfg.tolerance_value)
        ws.write(r, 3, cfg.weight)
        ws.write(r, 4, str(cfg.is_regulatory))
        r += 1
