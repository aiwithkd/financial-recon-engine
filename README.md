# Financial Data Reconciliation & Variance Engine

A reconciliation tool for comparing two financial datasets side by side - configurable join keys, per-field tolerance thresholds (absolute, percentage, basis points, date), break severity ranking, and a Streamlit UI with Excel export.

**Live App: [financial-recon-engine-aiwithkd.streamlit.app](https://financial-recon-engine-aiwithkd.streamlit.app)**

---

## Background

Reconciliation is something every financial ops team does daily - you have a position file from your PMS and one from the custodian, and you need to know where they differ, by how much, and whether it matters. Most of the time this is done manually in Excel or with rigid scripts that break the moment a column gets renamed.

I built this to handle the full workflow properly: load two datasets, auto-detect or pick your join keys, evaluate field-level variances against configurable thresholds, classify each row as MATCHED / TOLERANCE / BREAK / MISSING, and get a ranked break report you can actually act on.

---

## Results

| Use Case | Match Rate | Breaks | Tolerance Hits | Missing Rows |
|---|---|---|---|---|
| Positions (PMS vs Custodian) | 96.3% | 8 | 151 | 3 |
| Prices (Vendor vs Internal) | 90.0% | 17 | 180 | 3 |
| Transactions (OMS vs Custodian) | 0% intentional | 146 | 0 | 4 |

The transactions result is intentional - the source uses `BUY/SELL` and the target uses `Purchase/Sale`. Every row breaks on `transaction_type`. This is the kind of systemic vocabulary mismatch that's easy to miss until you see 100% breaks on a single field, at which point the fix is obvious.

---

## Project Structure

```
financial-recon-engine/
├── app.py                        # Streamlit entry point
├── requirements.txt
├── config/
│   └── use_cases/
│       ├── positions.yaml        # field configs + tolerances per use case
│       ├── prices.yaml
│       └── transactions.yaml
├── src/
│   ├── data_layer/
│   │   ├── loader.py             # CSV/Excel reader with encoding fallback
│   │   ├── normalizer.py         # ISIN, date, numeric normalisation
│   │   ├── schema_inferrer.py    # column type detection
│   │   ├── key_detector.py       # TF-IDF based join key suggestions
│   │   └── validators.py         # pre-run checks (nulls, dupes, schema overlap)
│   ├── engine/
│   │   ├── reconciler.py         # main pipeline orchestrator
│   │   ├── matcher.py            # 3-pass join logic
│   │   ├── tolerance_engine.py   # vectorised field comparison
│   │   ├── variance_classifier.py
│   │   ├── summary_builder.py    # KPIs and field stats
│   │   ├── config_loader.py      # YAML parser
│   │   └── models.py             # dataclasses
│   ├── reporting/
│   │   └── excel_exporter.py     # 8-sheet colour-coded Excel output
│   └── ui/
│       ├── app.py                # 3-stage Streamlit app
│       └── state.py              # session state manager
├── scripts/
│   └── generate_sample_data.py
└── tests/
    └── fixtures/                 # source + target CSVs for each use case
```

---

## How It Works

### Matching

Three passes to maximise rows matched before giving up:

1. Exact join on raw key values
2. Normalised join on unmatched rows only (uppercase, ISIN format, date parsing, strip leading zeros)
3. Composite key fallback for multi-column keys

Each pass only touches the rows the previous pass missed, so it stays fast on larger files.

### Tolerance Evaluation

All comparisons are vectorised across the full joined DataFrame - no row loops.

| Type | Formula | When to use |
|---|---|---|
| `absolute` | `abs(src - tgt) <= threshold` | Dollar amounts, quantities |
| `percentage` | `abs(src - tgt) / abs(src) * 100 <= threshold` | Prices |
| `basis_points` | `abs(src - tgt) / abs(src) * 10000 <= threshold` | Financial prices, rates |
| `date_days` | `abs((src_date - tgt_date).days) <= threshold` | Settlement dates |
| `exact` | `str(src).upper() == str(tgt).upper()` | Codes, identifiers |

### Classification

Each matched row gets a status based on its worst-performing field:
- **MATCHED** - all fields within tolerance
- **TOLERANCE** - within threshold but not exact
- **BREAK** - at least one field over threshold
- **MISSING_TGT / MISSING_SRC** - row only exists on one side

Severity is based on field weight and whether the field is flagged as regulatory. A break on `market_value` with `is_regulatory: true` is always HIGH.

### Excel Export

8 sheets: Summary, Breaks (red), Tolerance Hits (amber), Matched (green), Missing in Target, Missing in Source, Field Stats, Config Audit.

---

## Pre-Built Use Cases

### Positions
End-of-day PMS vs custodian. Demo shows asset class vocabulary mismatch (Equity vs EQ), 8 market value breaks from FX rounding, 151 price tolerance hits, 3 missing rows from settlement lag.

Fields: quantity (exact), price (0.01%), market_value ($1), accrued_interest ($0.01), unrealized_pnl ($5), currency (exact)

### Prices
Daily close price validation between a vendor feed and internal library. 17 breaks where variance exceeds 5 bps (stale prices), 180 tolerance hits from normal rounding.

Fields: close_price (5 bps), bid_price (10 bps), ask_price (10 bps), volume (1%)

### Transactions
OMS vs custodian settlement records. 100% breaks on transaction_type due to BUY/SELL vs Purchase/Sale vocabulary difference. All other fields are clean - this shows how one misconfigured field dominates the break report.

Fields: trade_price (2 bps), gross_amount ($0.10), net_amount ($0.10), commission ($0.01), settlement_date (exact), transaction_type (exact)

---

## Running Locally

```bash
git clone https://github.com/aiwithkd/financial-recon-engine
cd financial-recon-engine
pip install -r requirements.txt
python scripts/generate_sample_data.py
streamlit run app.py
```

---

## Tech Stack

| Tool | Role |
|---|---|
| Python 3.9+ | Core |
| Pandas 2.2+ | Data loading, joining, aggregation |
| NumPy 1.26+ | Vectorised tolerance arithmetic |
| scikit-learn | TF-IDF + cosine similarity for key detection |
| Pydantic | Config models |
| PyYAML | Use case configs |
| XlsxWriter | Excel export |
| Streamlit | UI |
| Plotly | Charts |

---

## Challenges

### 1. Normalised join creating false matches

When both `ACC-001` and `ACC-1` normalise to `ACC1`, the join matches two unrelated rows. Fixed by deduplicating on normalised keys before each pass, and flagging any match where the normalised key appears more than once. Better to surface the ambiguity than silently accept a wrong match.

### 2. Silent NaN from string-typed numeric columns

CSV files load everything as strings. `pd.to_numeric()` was silently returning NaN on values like `"402.99"` because of the quotes, making every row look like a BREAK. Added explicit `.astype(str).str.replace(",", "")` before all numeric coercion. The bug was invisible until I wrote a test specifically for string-typed inputs.

### 3. Column name collisions after joining

Matcher suffixes columns as `_src` and `_tgt`. If the source already had a column called `price_src`, the join produced `price_src_src`. Tolerance engine then couldn't find either column and silently skipped the field comparison. Fixed by checking and renaming existing `_src`/`_tgt` suffixes before the join, plus a post-join validation that warns when any configured field's suffixed columns are missing.

### 4. Transactions showing 0% match rate

The transactions config has `transaction_type` as `exact`. Source uses `BUY/SELL`, target uses `Purchase/Sale`. Every row breaks on that field, which looks like the engine is broken. It's not - it's catching a real systemic issue. Updated the dashboard to show per-field break rates so you immediately see that transaction_type is the only cause and every other field is clean.

### 5. Streamlit session state wiped on every interaction

Stored DataFrames directly in `st.session_state["source_df"]` etc. Every widget interaction re-ran the page and cleared the results. Fixed by centralising all state into one `AppState` dataclass under a single session key. Nothing resets unless the user clicks "Start Over".

---

## What I'd Add Next

- Database input connector (Snowflake, Postgres) so you can reconcile without file exports
- Scheduled runs via Airflow or similar, with alerting on new HIGH severity breaks
- A fourth matching pass using fuzzy string similarity for cases where key values are semantically the same but not string-identical
- Historical break trending to track whether data quality is improving over time

---

*[Kunal Deokar](https://github.com/aiwithkd)*
