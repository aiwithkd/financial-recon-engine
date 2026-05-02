from __future__ import annotations

import os
import sys
from pathlib import Path

# Works both locally and on Streamlit Cloud (cwd = project root when launched via app.py)
ROOT = Path(os.getcwd())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.data_layer.key_detector import detect_keys
from src.data_layer.loader import load_file, get_sheet_names
from src.data_layer.schema_inferrer import infer_schema
from src.engine import reconciler
from src.engine.config_loader import load_use_case, list_use_cases, from_dict
from src.engine.models import FieldConfig, MatchKey, ReconConfig
from src.reporting.excel_exporter import export as export_excel
from src.ui import state

# Page config
st.set_page_config(
    page_title="Financial Recon Engine",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Global styles
st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; }
.stAlert { border-radius: 8px; }
.block-container { padding-top: 1.5rem; }
div[data-testid="column"] { padding: 0 0.4rem; }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/color/96/scales.png", width=56)
    st.title("Recon Engine")
    st.caption("Financial Data Reconciliation & Variance Engine")
    st.divider()

    app_state = state.get()

    # Stage indicator
    stages = {"upload": "1 — Upload", "configure": "2 — Configure", "results": "3 — Results"}
    for s, label in stages.items():
        icon = "✅" if (
            (s == "upload" and app_state.source_df is not None) or
            (s == "configure" and app_state.config is not None) or
            (s == "results" and app_state.report is not None)
        ) else "○"
        st.markdown(f"{'**' if app_state.stage == s else ''}{icon} {label}{'**' if app_state.stage == s else ''}")

    st.divider()
    if st.button("🔄 Start Over", use_container_width=True):
        state.reset()
        st.rerun()



# Upload stage

def render_upload():
    st.title("⚖️ Financial Data Reconciliation Engine")
    st.markdown("Compare two financial datasets row-by-row with configurable tolerance thresholds, auto-detected join keys, and a colour-coded break report.")
    st.divider()

    # Use case or custom
    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.subheader("📂 Upload Files")
        mode = st.radio("Data source", ["Use sample data", "Upload your own files"], horizontal=True)

        if mode == "Use sample data":
            use_cases = list_use_cases()
            uc = st.selectbox("Select use case", use_cases, format_func=lambda x: x.replace("_", " ").title())
            fixtures_dir = ROOT / "tests" / "fixtures"
            src_path = fixtures_dir / f"{uc}_source.csv"
            tgt_path = fixtures_dir / f"{uc}_target.csv"

            if not src_path.exists():
                st.warning("Sample data not found. Run `python scripts/generate_sample_data.py` first.")
                return

            src_df = load_file(src_path)
            tgt_df = load_file(tgt_path)
            src_name = f"{uc}_source.csv"
            tgt_name = f"{uc}_target.csv"
            preset_config = load_use_case(uc)

        else:
            use_cases = list_use_cases()
            preset_name = st.selectbox(
                "Start with a preset config (optional)",
                ["None (manual setup)"] + use_cases,
                format_func=lambda x: x.replace("_", " ").title() if x != "None (manual setup)" else x,
            )
            preset_config = load_use_case(preset_name) if preset_name != "None (manual setup)" else None

            src_file = st.file_uploader("Source file (CSV or Excel)", type=["csv", "xlsx", "xls"], key="src_upload")
            tgt_file = st.file_uploader("Target file (CSV or Excel)", type=["csv", "xlsx", "xls"], key="tgt_upload")

            if not src_file or not tgt_file:
                st.info("Upload both files to continue.")
                return

            # Sheet selection for Excel
            src_sheets = get_sheet_names(src_file)
            tgt_sheets = get_sheet_names(tgt_file)

            src_sheet = 0
            tgt_sheet = 0
            if src_sheets:
                src_sheet_name = st.selectbox("Source sheet", src_sheets)
                src_sheet = src_sheets.index(src_sheet_name)
                src_file.seek(0)
            if tgt_sheets:
                tgt_sheet_name = st.selectbox("Target sheet", tgt_sheets)
                tgt_sheet = tgt_sheets.index(tgt_sheet_name)
                tgt_file.seek(0)

            try:
                src_df = load_file(src_file, sheet_name=src_sheet)
                tgt_file.seek(0)
                tgt_df = load_file(tgt_file, sheet_name=tgt_sheet)
            except Exception as e:
                st.error(f"Error loading files: {e}")
                return

            src_name = src_file.name
            tgt_name = tgt_file.name

    with col_right:
        st.subheader("📋 File Preview")
        if "src_df" in dir() and "tgt_df" in dir():
            tab_src, tab_tgt = st.tabs([f"Source ({src_name})", f"Target ({tgt_name})"])
            with tab_src:
                st.caption(f"{len(src_df):,} rows × {len(src_df.columns)} columns")
                st.dataframe(src_df.head(8).astype(str), use_container_width=True, height=240)
            with tab_tgt:
                st.caption(f"{len(tgt_df):,} rows × {len(tgt_df.columns)} columns")
                st.dataframe(tgt_df.head(8).astype(str), use_container_width=True, height=240)
        else:
            st.info("File preview will appear here once files are loaded.")

    if "src_df" not in dir():
        return

    st.divider()
    if st.button("Continue to Configuration →", type="primary", use_container_width=False):
        state.update(
            source_df=src_df, target_df=tgt_df,
            source_name=src_name, target_name=tgt_name,
            config=preset_config,
            stage="configure",
        )
        st.rerun()



# Configure stage

def render_configure():
    app = state.get()
    src = app.source_df
    tgt = app.target_df

    st.title("⚙️ Configure Reconciliation")
    st.caption(f"Source: **{app.source_name}** ({len(src):,} rows) → Target: **{app.target_name}** ({len(tgt):,} rows)")
    st.divider()

    col_keys, col_fields = st.columns([1, 1], gap="large")

    # Matching keys
    with col_keys:
        st.subheader("🔑 Matching Keys")

        # Auto-detect suggestions
        if st.button("✨ Auto-detect join keys", use_container_width=True):
            with st.spinner("Analysing column patterns..."):
                candidates = detect_keys(src, tgt, top_n=5)
                st.session_state["_key_candidates"] = candidates

        if "_key_candidates" in st.session_state:
            st.markdown("**Suggested keys** (click to use):")
            for c in st.session_state["_key_candidates"]:
                conf_color = "🟢" if c.confidence > 0.7 else "🟡" if c.confidence > 0.4 else "🔴"
                st.markdown(f"{conf_color} `{c.source_col}` ↔ `{c.target_col}` — {c.confidence:.0%} confidence")

        st.markdown("**Define matching keys:**")
        n_keys = st.number_input("Number of keys", min_value=1, max_value=5, value=max(1, len(app.config.matching_keys) if app.config else 1))

        src_cols = list(src.columns)
        tgt_cols = list(tgt.columns)

        key_rows: list[MatchKey] = []
        for i in range(int(n_keys)):
            c1, c2, c3 = st.columns([2, 2, 1])
            default_sc = app.config.matching_keys[i].source_col if (app.config and i < len(app.config.matching_keys)) else src_cols[0]
            default_tc = app.config.matching_keys[i].target_col if (app.config and i < len(app.config.matching_keys)) else tgt_cols[0]
            default_norm = app.config.matching_keys[i].normalization if (app.config and i < len(app.config.matching_keys)) else "none"

            sc = c1.selectbox(f"Source key {i+1}", src_cols, index=src_cols.index(default_sc) if default_sc in src_cols else 0, key=f"sk_{i}")
            tc = c2.selectbox(f"Target key {i+1}", tgt_cols, index=tgt_cols.index(default_tc) if default_tc in tgt_cols else 0, key=f"tk_{i}")
            nm = c3.selectbox("Norm", ["none", "uppercase", "isin", "numeric", "date"], index=["none", "uppercase", "isin", "numeric", "date"].index(default_norm) if default_norm in ["none", "uppercase", "isin", "numeric", "date"] else 0, key=f"nm_{i}")
            key_rows.append(MatchKey(sc, tc, nm))

    # Field tolerances
    with col_fields:
        st.subheader("📐 Field Tolerances")
        st.caption("Only fields listed here will be compared. Others are ignored.")

        src_non_key = [c for c in src.columns if c not in [k.source_col for k in key_rows]]
        tgt_non_key = [c for c in tgt.columns if c not in [k.target_col for k in key_rows]]
        comparable = list({c for c in src_non_key if c in tgt_non_key})

        preset_fields = app.config.field_configs if app.config else {}
        default_selection = list(preset_fields.keys()) if preset_fields else comparable[:min(6, len(comparable))]
        selected_fields = st.multiselect("Fields to compare", comparable, default=[f for f in default_selection if f in comparable])

        field_configs: dict[str, FieldConfig] = {}
        tol_types = ["absolute", "percentage", "basis_points", "exact", "date_days"]

        for f in selected_fields:
            preset = preset_fields.get(f)
            with st.expander(f"⚙ {f}", expanded=False):
                c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                ttype = c1.selectbox("Type", tol_types, index=tol_types.index(preset.tolerance_type) if preset else 0, key=f"tt_{f}")
                tval = c2.number_input("Threshold", value=float(preset.tolerance_value) if preset else 0.01, min_value=0.0, format="%.4f", key=f"tv_{f}")
                weight = c3.slider("Weight", 0.0, 1.0, float(preset.weight) if preset else 1.0, 0.1, key=f"wt_{f}")
                is_reg = c4.checkbox("Regulatory", value=bool(preset.is_regulatory) if preset else False, key=f"rg_{f}")
                field_configs[f] = FieldConfig(ttype, tval, weight, is_reg)

    st.divider()
    c1, c2, c3 = st.columns([1, 1, 4])
    if c1.button("← Back", use_container_width=True):
        state.update(stage="upload")
        st.rerun()

    if c2.button("▶ Run Reconciliation", type="primary", use_container_width=True):
        if not key_rows:
            st.error("Define at least one matching key.")
            return
        config = ReconConfig(
            matching_keys=key_rows,
            field_configs=field_configs,
            use_case_name=app.config.use_case_name if app.config else "Custom",
        )
        with st.spinner("Running reconciliation..."):
            try:
                report = reconciler.run(app.source_df, app.target_df, config)
                state.update(config=config, report=report, stage="results", warnings=report.warnings)
                st.rerun()
            except Exception as e:
                st.error(f"Reconciliation failed: {e}")



# Results stage

def render_results():
    app = state.get()
    report = app.report
    kpis = report.kpis

    if app.warnings:
        for w in app.warnings:
            st.warning(w)

    st.title(f"📊 Reconciliation Results — {report.config.use_case_name}")
    st.caption(f"Run at {report.run_timestamp.strftime('%Y-%m-%d %H:%M UTC')} | Source: {app.source_name} | Target: {app.target_name}")

    # KPI cards
    cols = st.columns(7)
    metrics = [
        ("Match Rate", f"{kpis.match_rate_pct:.1f}%", ""),
        ("Matched", f"{kpis.matched:,}", ""),
        ("Tolerance Hits", f"{kpis.tolerance_hits:,}", ""),
        ("Breaks", f"{kpis.breaks:,}", "↑" if kpis.breaks > 0 else ""),
        ("Missing in Tgt", f"{kpis.missing_tgt:,}", ""),
        ("Missing in Src", f"{kpis.missing_src:,}", ""),
        ("High Severity", f"{kpis.high_severity_breaks:,}", ""),
    ]
    for col, (label, val, delta) in zip(cols, metrics):
        col.metric(label, val, delta if delta else None)

    st.divider()

    # Charts
    chart_col, heatmap_col = st.columns([1, 1], gap="large")

    with chart_col:
        st.subheader("Reconciliation Breakdown")
        categories = ["Matched", "Tolerance", "Breaks", "Missing Tgt", "Missing Src"]
        values = [kpis.matched, kpis.tolerance_hits, kpis.breaks, kpis.missing_tgt, kpis.missing_src]
        colors = ["#2ecc71", "#f39c12", "#e74c3c", "#95a5a6", "#bdc3c7"]

        fig = go.Figure(go.Bar(
            x=categories, y=values,
            marker_color=colors,
            text=values, textposition="outside",
        ))
        fig.update_layout(
            height=320, margin=dict(t=20, b=20, l=20, r=20),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(showgrid=True, gridcolor="#f0f0f0"),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    with heatmap_col:
        st.subheader("Break Rate by Field")
        if not report.field_stats.empty:
            fs = report.field_stats.sort_values("break_rate_pct", ascending=True)
            fig2 = go.Figure(go.Bar(
                x=fs["break_rate_pct"],
                y=fs["field"],
                orientation="h",
                marker_color=[
                    "#e74c3c" if v > 20 else "#f39c12" if v > 5 else "#2ecc71"
                    for v in fs["break_rate_pct"]
                ],
                text=fs["break_rate_pct"].apply(lambda x: f"{x:.1f}%"),
                textposition="outside",
            ))
            fig2.update_layout(
                height=320, margin=dict(t=20, b=20, l=120, r=60),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                xaxis_title="Break Rate %", showlegend=False,
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No field comparison data available.")

    st.divider()

    # Detail tables
    tab_breaks, tab_tol, tab_missing, tab_matched, tab_fields = st.tabs([
        f"🔴 Breaks ({kpis.breaks})",
        f"🟡 Tolerance ({kpis.tolerance_hits})",
        f"⚫ Missing ({kpis.missing_src + kpis.missing_tgt})",
        f"🟢 Matched ({kpis.matched})",
        "📋 Field Stats",
    ])

    with tab_breaks:
        _render_table(report.break_records, "No breaks found.")

    with tab_tol:
        _render_table(report.tolerance_records, "No tolerance hits.")

    with tab_missing:
        if not report.source_only_df.empty or not report.target_only_df.empty:
            t1, t2 = st.tabs([f"Missing in Target ({kpis.missing_tgt})", f"Missing in Source ({kpis.missing_src})"])
            with t1:
                _render_table(report.source_only_df, "None.")
            with t2:
                _render_table(report.target_only_df, "None.")
        else:
            st.success("No missing rows in either dataset.")

    with tab_matched:
        _render_table(report.matched_df, "No matched rows.", max_rows=200)

    with tab_fields:
        if not report.field_stats.empty:
            st.dataframe(
                report.field_stats.style.format({
                    "break_rate_pct": "{:.2f}%",
                    "avg_variance": "{:.6f}",
                    "max_variance": "{:.6f}",
                }),
                use_container_width=True,
            )
        else:
            st.info("No field statistics available.")

    st.divider()

    # Export
    c1, c2 = st.columns([1, 5])
    with c1:
        with st.spinner("Preparing Excel report..."):
            excel_bytes = export_excel(report)
        st.download_button(
            label="📥 Download Excel Report",
            data=excel_bytes,
            file_name=f"recon_report_{report.run_timestamp.strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )
    with c2:
        if st.button("← Reconfigure", use_container_width=False):
            state.update(stage="configure", report=None)
            st.rerun()


def _render_table(df: pd.DataFrame, empty_msg: str, max_rows: int = 500):
    if df.empty:
        st.success(empty_msg)
        return
    display = df.head(max_rows).astype(str).replace("nan", "").replace("<NA>", "")
    if len(df) > max_rows:
        st.caption(f"Showing {max_rows:,} of {len(df):,} rows. Download the Excel report for the full dataset.")
    st.dataframe(display, use_container_width=True, height=380)



# Route to current stage

app = state.get()

if app.stage == "upload":
    render_upload()
elif app.stage == "configure":
    render_configure()
elif app.stage == "results":
    render_results()
