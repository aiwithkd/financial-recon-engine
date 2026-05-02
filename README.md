# Financial Data Reconciliation & Variance Engine

Production-grade reconciliation pipeline for financial datasets — config-driven matching, per-field tolerance evaluation (absolute / percentage / basis points / date), severity-ranked break classification, and an interactive Streamlit dashboard with colour-coded Excel export.

**Live App → [financial-recon-engine.streamlit.app](https://financial-recon-engine-aiwithkd.streamlit.app)**

---

## What This Project Does and Why

In financial services, reconciliation is the daily process of comparing two versions of the same data — a portfolio management system against a custodian, a pricing vendor against an internal library, an OMS against settlement records. When they don't match, operations teams need to know exactly which rows broke, on which fields, by how much, and how severe the impact is.

This project builds a complete, reusable reconciliation engine that handles the full workflow: load two datasets, auto-detect or manually configure join keys, evaluate field-level variances against configurable thresholds, classify each row as MATCHED / TOLERANCE / BREAK / MISSING, and produce a ranked break report with a downloadable colour-coded Excel file.

Directly modelled on real reconciliation work done in financial data operations — the architecture, use cases, and tolerance logic mirror production-grade tooling used in wealth management and fintech environments.

---

## Results at a Glance

| Use Case | Match Rate | Breaks | Tolerance Hits | Missing Rows |
|---|---|---|---|---|
| Positions (PMS vs Custodian) | 96.3% | 8 | 151 | 3 |
| Prices (Vendor vs Internal) | 90.0% | 17 | 180 | 3 |
| Transactions (OMS vs Custodian) | 0% intentional | 146 | 0 | 4 |

The transactions use case intentionally produces 100% breaks on `transaction_type` (BUY vs Purchase vocabulary mismatch) — demonstrating how a single misconfigured field config exposes a systemic data quality issue across all rows.

---

## Repository Structure

```
financial-recon-engine/
├── app.py                          # Streamlit Cloud entry point (thin wrapper)
├── requirements.txt                # Pinned dependencies
├── pyproject.toml                  # Build system config
├── .streamlit/
│   └── config.toml                 # Theme and upload size settings
│
├── config/
│   └── use_cases/
│       ├── positions.yaml          # PMS vs custodian positions config
│       ├── prices.yaml             # Vendor vs internal price config
│       └── transactions.yaml      # OMS vs settlement config
│
├── src/
│   ├── data_layer/
│   │   ├── loader.py               # CSV/Excel ingestion with encoding detection
│   │   ├── normalizer.py           # Column normalisation strategies (ISIN, date, numeric)
│   │   ├── schema_inferrer.py      # Auto-detects column types (numeric, date, ISIN, identifier)
│   │   ├── key_detector.py         # ML-backed join key detection (TF-IDF + cardinality scoring)
│   │   └── validators.py           # Pre-flight checks: null keys, duplicates, schema overlap
│   │
│   ├── engine/
│   │   ├── reconciler.py           # Orchestrator — sequences all pipeline steps
│   │   ├── matcher.py              # Three-pass join: exact → normalised → composite
│   │   ├── tolerance_engine.py     # Vectorised per-field variance evaluation
│   │   ├── variance_classifier.py  # Row-level status: MATCHED / TOLERANCE / BREAK / MISSING
│   │   ├── summary_builder.py      # KPI aggregation and per-field statistics
│   │   ├── config_loader.py        # YAML config parser → ReconConfig dataclass
│   │   └── models.py               # Pydantic-compatible dataclasses for all domain objects
│   │
│   ├── reporting/
│   │   └── excel_exporter.py       # 8-sheet colour-coded Excel report (XlsxWriter)
│   │
│   └── ui/
│       ├── app.py                  # Full Streamlit application (3-stage flow)
│       └── state.py                # Centralised session state manager
│
├── scripts/
│   └── generate_sample_data.py     # Generates 3 use case fixture datasets with seeded breaks
│
└── tests/
    └── fixtures/                   # 6 CSV files: source + target for each use case
```

---

## Architecture

```
┌─────────────────────────────────────────────┐
│            STREAMLIT UI (3 stages)           │
│  Upload → Configure → Results + Export       │
└──────────────────────┬──────────────────────┘
                       │
┌──────────────────────▼──────────────────────┐
│                DATA LAYER                    │
│  loader → normalizer → key_detector          │
│  schema_inferrer → validators                │
└──────────────────────┬──────────────────────┘
                       │  Normalised DataFrames + ReconConfig
┌──────────────────────▼──────────────────────┐
│                ENGINE LAYER                  │
│  matcher (3-pass join)                       │
│    → tolerance_engine (vectorised)           │
│    → variance_classifier (BREAK/MATCHED)     │
│    → summary_builder (KPIs + field stats)    │
└──────────────────────┬──────────────────────┘
                       │  ReconciliationReport dataclass
┌──────────────────────▼──────────────────────┐
│             REPORTING LAYER                  │
│  excel_exporter (8-sheet XlsxWriter output)  │
└─────────────────────────────────────────────┘
```

**Key design decisions:**

**Three-pass matching strategy:** Pass 1 — exact join on raw keys. Pass 2 — normalised join (uppercase, ISIN format, date parsing) on unmatched residuals only. Pass 3 — composite key fallback. Each pass only processes the unmatched set from the prior pass, keeping performance predictable on large files.

**Vectorised tolerance engine:** All variance comparisons use NumPy operations on the full joined DataFrame — no row-by-row loops. Absolute, percentage, basis points, and date-day tolerance types all evaluate in a single vectorised pass.

**Config-driven, not hardcoded:** Every matching key, tolerance threshold, field weight, and severity flag lives in YAML. Adding a new asset class or client-specific config requires zero code changes — only a new YAML file.

**Strict layer separation:** `engine/reconciler.py` never imports Streamlit. `src/ui/app.py` never calls pandas directly. The data, engine, and UI layers are independently testable and replaceable.

**Centralised session state:** `state.py` manages all Streamlit session state through a single `AppState` dataclass. Pages call `state.get()` and `state.update()` — prevents the classic Streamlit bug where re-running a page wipes intermediate results.

---

## Three Pre-Built Use Cases

### Positions Reconciliation
**Scenario:** End-of-day positions between a portfolio management system and a custodian feed.

**What the demo shows:**
- Asset class vocabulary mismatch (`Equity` vs `EQ`) — all rows BREAK on this field
- 8 hard breaks on `market_value` (FX rounding errors above $1 threshold)
- 151 tolerance hits on `price` (within 0.01% but not exact — rounding at source)
- 3 missing rows (settlement lag — positions in PMS not yet received by custodian)

**Fields compared:** quantity (exact), price (0.01%), market_value ($1 absolute), accrued_interest ($0.01), unrealized_pnl ($5), currency (exact)

---

### Prices Reconciliation
**Scenario:** Daily close price validation between a market data vendor and an internal pricing library.

**What the demo shows:**
- 17 hard breaks where price variance exceeds 5 basis points (stale/incorrect vendor prices)
- 180 tolerance hits within the 5 bps threshold (normal rounding between systems)
- Bid/ask spread differences within 10 bps tolerance

**Fields compared:** close_price (5 bps), bid_price (10 bps), ask_price (10 bps), volume (1%)

---

### Transactions Reconciliation
**Scenario:** Executed trades between an OMS and custodian settlement records.

**What the demo shows:**
- 100% breaks on `transaction_type` — OMS uses `BUY/SELL`, custodian uses `Purchase/Sale`. This is a real-world data normalisation problem. Fixing the config (changing `transaction_type` tolerance from `exact` to `none`) instantly resolves all 146 rows
- 2 net_amount breaks above $0.10 threshold (fee calculation errors)
- 4 missing rows (3 failed settlements not received by custodian, 1 custodian-only corporate action)

**Fields compared:** trade_price (2 bps), gross_amount ($0.10), net_amount ($0.10), commission ($0.01), settlement_date (exact date), transaction_type (exact)

---

## Step-by-Step Pipeline

### Step 1 — Data Ingestion (`src/data_layer/loader.py`)

Reads CSV or Excel files with automatic encoding detection (UTF-8 → UTF-8-BOM → latin-1 fallback). Normalises column names to `snake_case`, strips whitespace, drops unnamed columns (Excel artefacts), and deduplicates column headers. Returns a clean DataFrame regardless of the source system's export format.

### Step 2 — Key Detection (`src/data_layer/key_detector.py`)

When join keys aren't known, the auto-detector scores all (source_col, target_col) column pairs using:

1. **TF-IDF + cosine similarity** on tokenised column names — catches `account_id` vs `AccountNumber`
2. **Uniqueness ratio** — a real join key should have `nunique / len` close to 1.0 in both files
3. **Value overlap** — what fraction of source values appear in target
4. **ISIN/CUSIP pattern detection** — regex match on known financial identifier formats
5. **Type compatibility** — numeric-to-numeric, date-to-date

Returns a ranked list of candidates with confidence scores. The user always has final say.

### Step 3 — Three-Pass Matching (`src/engine/matcher.py`)

**Pass 1 — Exact join** on raw key values via `pd.merge(how='outer', indicator=True)`.

**Pass 2 — Normalised join** on unmatched rows only: strip whitespace, uppercase, normalise ISIN format, parse date strings to ISO, strip leading zeros from numeric identifiers. Re-attempts exact join on normalised keys.

**Pass 3 — Composite key fallback** when single-key join leaves residuals and a multi-column key is configured (e.g., account + ISIN + trade_date + quantity for transactions).

### Step 4 — Tolerance Evaluation (`src/engine/tolerance_engine.py`)

Fully vectorised evaluation across all configured fields simultaneously. Four tolerance types:

| Type | Formula | Use case |
|---|---|---|
| `absolute` | `abs(src - tgt) <= threshold` | Dollar amounts, quantities |
| `percentage` | `abs(src - tgt) / abs(src) * 100 <= threshold` | General prices |
| `basis_points` | `abs(src - tgt) / abs(src) * 10000 <= threshold` | Financial prices, rates |
| `date_days` | `abs((src_date - tgt_date).days) <= threshold` | Settlement dates |
| `exact` | `str(src).upper() == str(tgt).upper()` | Codes, identifiers |

### Step 5 — Classification (`src/engine/variance_classifier.py`)

Each matched row receives a status:

- **MATCHED** — all compared fields within tolerance, zero or negligible variance
- **TOLERANCE** — all fields within configured threshold but not exactly equal
- **BREAK** — at least one field exceeds its threshold
- **MISSING_TGT** — row in source but not found in target
- **MISSING_SRC** — row in target but not found in source

Severity for BREAKs is assigned based on field weights and `is_regulatory` flag — a break on `market_value` (regulatory) is always HIGH; a break on a low-weight field is LOW.

### Step 6 — Reporting (`src/reporting/excel_exporter.py`)

8-sheet colour-coded Excel workbook:

| Sheet | Colour | Contents |
|---|---|---|
| Summary | — | KPI cards, run metadata, warnings |
| Breaks | Red | All BREAK rows, sorted by severity |
| Tolerance Hits | Amber | Rows within tolerance but not exact |
| Matched | Green | Clean matched rows |
| Missing in Target | Grey | Source rows with no target match |
| Missing in Source | Grey | Target rows with no source match |
| Field Stats | — | Per-field break rate, avg/max variance |
| Config Audit | — | Exact config used, timestamp (audit trail) |

---

## Running Locally

```bash
git clone https://github.com/aiwithkd/financial-recon-engine
cd financial-recon-engine
pip install -r requirements.txt

# Generate sample data
python scripts/generate_sample_data.py

# Run the app
streamlit run app.py
# open http://localhost:8501
```

## Tech Stack

| Tool | Version | Role |
|---|---|---|
| Python | 3.9+ | Core runtime |
| Pandas | 2.2.3 | Data loading, joining, aggregation |
| NumPy | 1.26.4 | Vectorised tolerance arithmetic |
| scikit-learn | 1.5.2 | TF-IDF + cosine similarity for key detection |
| Pydantic | 2.7.4 | Config validation and domain models |
| PyYAML | 6.0.2 | Use case config parsing |
| XlsxWriter | 3.2.0 | Colour-coded Excel export |
| OpenPyXL | 3.1.5 | Excel input reading |
| Streamlit | 1.37.0 | Interactive web UI |
| Plotly | 5.23.0 | Waterfall and bar charts |
| GitHub Pages | — | Static hosting |

---

## Challenges Faced During Implementation

### 1. Three-pass join producing duplicate unmatched rows

**Problem:** The normalised join (Pass 2) re-processed the full unmatched set from Pass 1, but the outer merge produced duplicate keys when the normalised form of two different raw values mapped to the same string. For example, `"ACC-001"` and `"ACC-1"` both normalised to `"ACC1"`, creating a false match between two unrelated rows.

**Resolution:** Added explicit deduplication on join keys before each pass. Also added a post-join check that flags any matched row where the normalised key appears more than once — these are surfaced as warnings to the user rather than silently accepted as matches. The principle: better to surface an ambiguous match than silently get it wrong.

---

### 2. Tolerance engine receiving string-typed numeric columns

**Problem:** All columns from CSV files load as `object` dtype (strings). The tolerance engine's `pd.to_numeric()` calls were failing silently on columns like `"402.9927"` — not raising an error, just returning `NaN` for all values, making every row appear as a BREAK. This was masked because the engine continued without error.

**Resolution:** Added explicit `.astype(str).str.replace(",", "")` before every `pd.to_numeric()` call. Also added a unit test that loads tolerance engine with string-typed inputs specifically — the bug was invisible until the test was written. Now all numeric coercion is explicit and tested.

---

### 3. Column name collisions after the three-pass join

**Problem:** The matcher suffixes non-key columns as `_src` and `_tgt` after joining. But if the source file already had a column called `price_src`, the merger produced `price_src_src` — and the tolerance engine couldn't find `price_src` or `price_tgt`. This caused silent misses on entire field comparisons.

**Resolution:** The normaliser now checks for existing `_src`/`_tgt` suffixes on input columns and renames them before joining. Also added a post-join validation step that logs a warning for any configured field whose `_src` or `_tgt` column is missing from the matched DataFrame.

---

### 4. Transactions use case showing 0% match rate by design

**Problem:** The transactions config includes `transaction_type` as an `exact` field. The sample data uses `BUY/SELL` in source and `Purchase/Sale` in target — a realistic vocabulary mismatch. Every row breaks on this field, producing a 0% match rate that looks like the engine is broken.

**Resolution:** This is actually correct behaviour — it demonstrates the engine catching a real systemic issue. The dashboard was updated to show per-field break rates alongside the overall match rate, so a reviewer immediately sees that `transaction_type` is the single cause of all breaks, while all other fields are clean. The README documents this explicitly. Fixing it requires either normalising the vocabulary in the config (add a mapping) or removing `transaction_type` from field comparisons — both are valid real-world responses.

---

### 5. Streamlit session state wiped on page interaction

**Problem:** Early versions stored DataFrames directly in `st.session_state["source_df"]` etc. Every button click or widget interaction triggered a full page re-run, which cleared intermediate results — running reconciliation, then clicking a chart filter, wiped the report.

**Resolution:** Centralised all state into a single `AppState` dataclass managed by `state.py`. The dataclass is stored under a single `_recon_app_state` key and never re-initialised unless the user clicks "Start Over". Pages read and write through `state.get()` / `state.update()` — no raw `st.session_state` access anywhere outside `state.py`. This pattern also makes pages independently testable by injecting a mock `AppState`.

---

## Future Scope

This engine is fully self-contained — no external services, no database, no API keys. Natural extensions:

- **Delta lake / database input** — replace the CSV/Excel loader with a connector to Databricks Delta tables or PostgreSQL, enabling reconciliation directly on production data without file exports
- **Scheduled reconciliation** — wrap the engine in an Airflow or Control-M DAG that runs nightly after the batch window, writes results to a persistent store, and alerts on new HIGH severity breaks
- **Fuzzy semantic matching** — add an optional fourth pass using sentence transformers to match rows where key values are semantically similar but not string-identical (e.g. "Apple Inc" vs "Apple Incorporated")
- **Historical break trending** — store reconciliation results over time and visualise whether break rates are improving or degrading week-over-week per field
- **Multi-source reconciliation** — extend the engine to compare three or more datasets simultaneously (source vs two custodians), producing a consensus view

---

*Built by [Kunal Deokar](https://github.com/aiwithkd)*
