"""Generate realistic sample data for all three reconciliation use cases."""
from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)
random.seed(SEED)

OUT = Path(__file__).parent.parent / "tests" / "fixtures"
OUT.mkdir(parents=True, exist_ok=True)

ISINS = [f"US{str(i).zfill(10)}" for i in range(1000, 1200)]
ACCOUNTS = [f"ACC-{i}" for i in range(10001, 10051)]
CURRENCIES = ["USD", "GBP", "EUR"]
BROKERS = [f"BROKER_{i:03d}" for i in range(1, 6)]


# ── Use Case 1: Positions ─────────────────────────────────────────────────────

def gen_positions():
    n = 300
    rows = []
    for i in range(n):
        acct = random.choice(ACCOUNTS)
        isin = random.choice(ISINS)
        qty = round(random.uniform(100, 5000), 0)
        price = round(random.uniform(10, 500), 4)
        mv = round(qty * price, 2)
        rows.append({
            "account_id": acct,
            "security_id": isin,
            "security_name": f"Security {isin[-4:]}",
            "asset_class": random.choice(["Equity", "Bond", "ETF"]),
            "quantity": qty,
            "price": price,
            "market_value": mv,
            "accrued_interest": round(random.uniform(0, 50), 2),
            "currency": random.choice(CURRENCIES),
            "price_date": "2024-01-15",
            "cost_basis": round(mv * random.uniform(0.85, 1.15), 2),
            "unrealized_pnl": round(mv * random.uniform(-0.15, 0.20), 2),
        })
    source = pd.DataFrame(rows).drop_duplicates(subset=["account_id", "security_id"])

    target = source.rename(columns={
        "account_id": "account_id", "security_id": "security_id",
        "security_name": "security_name", "asset_class": "asset_class",
    }).copy()

    # Inject breaks
    idx_price_break = source.index[:3].tolist()
    for i in idx_price_break:
        target.loc[i, "price"] = round(target.loc[i, "price"] * 1.005, 4)  # 0.5% off
        target.loc[i, "market_value"] = round(target.loc[i, "quantity"] * target.loc[i, "price"], 2)

    idx_mv_break = source.index[5:10].tolist()
    for i in idx_mv_break:
        target.loc[i, "market_value"] = round(target.loc[i, "market_value"] + random.uniform(1.5, 5.0), 2)

    # Normalise asset class to abbreviated form in target
    target["asset_class"] = target["asset_class"].map({"Equity": "EQ", "Bond": "BD", "ETF": "ETF"})

    # Add rounding noise to all prices
    target["price"] = target["price"].apply(lambda x: round(x + rng.uniform(-0.0001, 0.0001), 4))

    # Missing rows: 2 in source-only, 1 in target-only
    source_extra = source.iloc[[10, 11]].copy()
    source = pd.concat([source, source_extra.assign(account_id="ACC-99999")], ignore_index=True)

    target = target.drop(index=[20]).reset_index(drop=True)

    source.to_csv(OUT / "positions_source.csv", index=False)
    target.to_csv(OUT / "positions_target.csv", index=False)
    print(f"Positions: source={len(source)}, target={len(target)}")


# ── Use Case 2: Prices ────────────────────────────────────────────────────────

def gen_prices():
    n = 200
    isins = ISINS[:n]
    price_date = "2024-01-15"

    close_prices = rng.uniform(10, 500, n).round(4)
    rows_src = []
    rows_tgt = []

    for i, isin in enumerate(isins):
        cp = close_prices[i]
        # Target: add minor noise
        noise = rng.uniform(-0.00004, 0.00004)  # ~0.4 bps — within 5 bps threshold
        cp_tgt = round(cp * (1 + noise), 4)

        rows_src.append({
            "isin": isin, "close_price": cp,
            "bid_price": round(cp - 0.05, 4), "ask_price": round(cp + 0.05, 4),
            "volume": int(rng.integers(100_000, 5_000_000)),
            "price_date": price_date, "price_currency": "USD",
        })
        vol = rows_src[-1]["volume"]
        rows_tgt.append({
            "isin": isin, "close_price": cp_tgt,
            "bid_price": round(cp_tgt - random.uniform(0.01, 0.03), 4),
            "ask_price": round(cp_tgt + random.uniform(0.01, 0.03), 4),
            "volume": int(vol * rng.uniform(0.995, 1.005)),  # minor variance within 1%
            "price_date": price_date, "price_currency": "USD",
        })

    source = pd.DataFrame(rows_src)
    target = pd.DataFrame(rows_tgt)

    # Inject hard breaks (>5bps)
    for i in range(10):
        target.loc[i, "close_price"] = round(source.loc[i, "close_price"] * (1 + rng.uniform(0.001, 0.003)), 4)

    # Missing rows
    source = source.drop(index=[150, 151]).reset_index(drop=True)
    target = target.drop(index=[180]).reset_index(drop=True)

    source.to_csv(OUT / "prices_source.csv", index=False)
    target.to_csv(OUT / "prices_target.csv", index=False)
    print(f"Prices: source={len(source)}, target={len(target)}")


# ── Use Case 3: Transactions ──────────────────────────────────────────────────

def gen_transactions():
    n = 150
    rows_src = []
    for i in range(n):
        acct = random.choice(ACCOUNTS)
        isin = random.choice(ISINS[:50])
        qty = round(random.uniform(100, 1000), 0)
        price = round(random.uniform(10, 300), 4)
        gross = round(qty * price, 2)
        comm = round(gross * 0.001, 2)
        rows_src.append({
            "account_id": acct, "isin": isin,
            "transaction_type": random.choice(["BUY", "SELL"]),
            "trade_date": "2024-01-15", "settlement_date": "2024-01-17",
            "quantity": qty, "trade_price": price,
            "gross_amount": gross, "commission": comm,
            "net_amount": round(gross + comm, 2),
            "currency": "USD", "broker_id": random.choice(BROKERS), "status": "SETTLED",
        })

    source = pd.DataFrame(rows_src)
    target = source.copy()

    # Rename cols to simulate custodian naming
    target = target.rename(columns={
        "transaction_type": "transaction_type",
        "settlement_date": "settlement_date",
        "quantity": "quantity",
    })

    # Vocab mismatch: BUY → Purchase, SELL → Sale
    target["transaction_type"] = target["transaction_type"].map({"BUY": "Purchase", "SELL": "Sale"})

    # Inject net_amount breaks
    for i in range(2):
        target.loc[i, "net_amount"] = round(target.loc[i, "net_amount"] + random.uniform(1.5, 3.0), 2)

    # Rounding noise on prices
    target["trade_price"] = target["trade_price"].apply(lambda x: round(x + rng.uniform(-0.00001, 0.00001), 4))
    target["gross_amount"] = target["gross_amount"].apply(lambda x: round(x + rng.uniform(-0.01, 0.01), 2))

    # Missing rows
    source = source.drop(index=[100, 101, 102]).reset_index(drop=True)
    target = target.drop(index=[140]).reset_index(drop=True)

    source.to_csv(OUT / "transactions_source.csv", index=False)
    target.to_csv(OUT / "transactions_target.csv", index=False)
    print(f"Transactions: source={len(source)}, target={len(target)}")


if __name__ == "__main__":
    gen_positions()
    gen_prices()
    gen_transactions()
    print(f"\nAll sample data written to {OUT}")
