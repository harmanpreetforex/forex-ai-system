"""
Pull DAILY history for a diversified ~19-instrument basket — all 5 asset classes.
This is the data layer for the trend-following / managed-futures test.

WHY DAILY (not H1): trend-following captures multi-week/month moves. On daily bars,
trading costs are tiny relative to the moves, and the signal isn't drowned in
intraday noise — the opposite of the H1-majors setup that proved edgeless.

WHY THIS BASKET: 19 instruments spanning FX, stock indices, commodities, bonds,
and metals — things that move on DIFFERENT drivers. Diversification across
uncorrelated markets IS the trend-following edge; 3 correlated FX majors (the old
setup) can't provide it.

Reuses the paginated fetch pattern from oanda_pipeline.py. Mid prices; spread/cost
is modeled later in the portfolio backtester. One CSV per instrument:
    data/basket_daily/<name>.csv   (gitignored, like the other generated data)

Run from repo root:  python data/pull_basket_daily.py
Read-only against OANDA (GET candles only). Sends no orders.
"""

import time
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

API_TOKEN = os.getenv("OANDA_API_TOKEN")
BASE_URL  = "https://api-fxpractice.oanda.com"

if not API_TOKEN:
    raise SystemExit("Missing OANDA_API_TOKEN — check your .env file.")

HEADERS = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}

# ── The diversified basket (asset class in the comment) ──────────────────────
BASKET = [
    # FX majors (6) — different blocs, not all USD-vs-one-thing
    "EUR_USD", "USD_JPY", "GBP_USD", "AUD_USD", "USD_CAD", "USD_CHF",
    # Stock indices (4) — US tech, US broad, Germany, UK
    "SPX500_USD", "NAS100_USD", "DE30_EUR", "UK100_GBP",
    # Commodities (4) — energy, gas, industrial metal, grain
    "WTICO_USD", "NATGAS_USD", "XCU_USD", "CORN_USD",
    # Government bonds (3) — US 10y, US 2y, German Bund
    "USB10Y_USD", "USB02Y_USD", "DE10YB_EUR",
    # Precious metals (2)
    "XAU_USD", "XAG_USD",
]

GRANULARITY = "D"
YEARS       = 10
PRICE       = "M"     # mid; cost modeled later
MAX_PER_REQ = 5000
OUT_DIR     = Path("data/basket_daily")


def fetch_candles(instrument, granularity, start, end):
    url = f"{BASE_URL}/v3/instruments/{instrument}/candles"
    raw, cursor, req = [], start, 0
    while cursor < end:
        params = {
            "granularity": granularity,
            "from":  cursor.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "count": MAX_PER_REQ,
            "price": PRICE,
        }
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        batch = resp.json().get("candles", [])
        req += 1
        if not batch:
            break
        raw.extend(batch)
        last_time = pd.to_datetime(batch[-1]["time"])
        if len(batch) < MAX_PER_REQ or last_time >= end:
            break
        cursor = last_time + timedelta(seconds=1)
        time.sleep(0.1)
    return raw


def to_dataframe(candles, end):
    rows = []
    for c in candles:
        if not c.get("complete", True):
            continue
        ts = pd.to_datetime(c["time"])
        if ts > end:
            continue
        mid = c["mid"]
        rows.append({
            "datetime": ts,
            "open":  float(mid["o"]),
            "high":  float(mid["h"]),
            "low":   float(mid["l"]),
            "close": float(mid["c"]),
            "volume": int(c["volume"]),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df.set_index("datetime", inplace=True)
    df = df[~df.index.duplicated(keep="first")]
    df.sort_index(inplace=True)
    df.index = df.index.tz_localize(None)
    return df


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=YEARS * 365)

    summary = []
    for inst in BASKET:
        raw = fetch_candles(inst, GRANULARITY, start, end)
        df  = to_dataframe(raw, end)
        if df.empty:
            print(f"  ⚠ {inst:<12} no candles returned")
            summary.append((inst, 0, "", ""))
            continue
        csv_path = OUT_DIR / f"{inst}.csv"
        df.to_csv(csv_path)
        span = (df.index[-1] - df.index[0]).days
        print(f"  ✓ {inst:<12} {len(df):>5} bars  "
              f"{df.index[0].date()} → {df.index[-1].date()}  (~{span//365}y)")
        summary.append((inst, len(df), df.index[0].date(), df.index[-1].date()))

    got = [s for s in summary if s[1] > 0]
    print(f"\n✅ {len(got)}/{len(BASKET)} instruments pulled to {OUT_DIR}/")
    if got:
        shortest = min(got, key=lambda s: s[1])
        print(f"   Shortest history: {shortest[0]} with {shortest[1]} bars "
              f"(from {shortest[2]}) — this bounds the common backtest window.")


if __name__ == "__main__":
    main()
