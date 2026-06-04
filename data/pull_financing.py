"""
Snapshot the current financing (swap) rates for the basket -> data/financing_rates.csv

These are the raw material for the carry strategy. HONEST LIMITATION (read this):
this is a CURRENT snapshot, not a historical series. Interest rates moved a lot
2016-2026, so using one snapshot as a static signal over the whole backtest is an
approximation with mild look-ahead. The carry backtest is therefore INDICATIVE,
not validated to the trend strategy's standard (whose price-only data needed no
external modeling). Documented so the result is never over-read.

longRate  = annual financing rate applied to a LONG position (per unit)
shortRate = annual financing rate applied to a SHORT position (per unit)
true differential  c = (longRate - shortRate) / 2     (broker markup removed)
broker markup      m = -(longRate + shortRate) / 2     (cost, always paid)

Run from repo root:  python data/pull_financing.py   (read-only GET)
"""

import os
import csv
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
API_TOKEN  = os.getenv("OANDA_API_TOKEN")
ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID")
BASE_URL   = "https://api-fxpractice.oanda.com"
HEADERS    = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}

OUT = Path("data/financing_rates.csv")

# Same basket as pull_basket_daily.py
BASKET = [
    "EUR_USD", "USD_JPY", "GBP_USD", "AUD_USD", "USD_CAD", "USD_CHF",
    "SPX500_USD", "NAS100_USD", "DE30_EUR", "UK100_GBP",
    "WTICO_USD", "NATGAS_USD", "XCU_USD", "CORN_USD",
    "USB10Y_USD", "USB02Y_USD", "DE10YB_EUR",
    "XAU_USD", "XAG_USD",
]


def main():
    r = requests.get(f"{BASE_URL}/v3/accounts/{ACCOUNT_ID}/instruments", headers=HEADERS)
    r.raise_for_status()
    fin = {i["name"]: i.get("financing", {}) for i in r.json()["instruments"]}

    rows = []
    for name in BASKET:
        f = fin.get(name, {})
        lr, sr = f.get("longRate"), f.get("shortRate")
        if lr is None or sr is None:
            print(f"  ⚠ {name}: no financing data")
            continue
        lr, sr = float(lr), float(sr)
        c = (lr - sr) / 2          # true differential
        rows.append({"instrument": name, "longRate": lr, "shortRate": sr,
                     "carry_c": c, "direction": 1 if c > 0 else -1})

    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["instrument", "longRate", "shortRate",
                                           "carry_c", "direction"])
        w.writeheader()
        w.writerows(rows)

    print(f"✓ wrote {len(rows)} financing rows -> {OUT}")
    longs = [r["instrument"] for r in rows if r["direction"] == 1]
    shorts = [r["instrument"] for r in rows if r["direction"] == -1]
    print(f"  carry says LONG ({len(longs)}): {', '.join(longs)}")
    print(f"  carry says SHORT ({len(shorts)}): {', '.join(shorts)}")


if __name__ == "__main__":
    main()
