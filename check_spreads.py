"""
check_spreads.py — measure REAL average spread per pair from OANDA.
Run from the repo ROOT (so it finds .env):
    python check_spreads.py

Weekend-safe by design: it reads recent HISTORICAL bid/ask candles, not a live
snapshot. Live spreads are blown out 5-10x while the market is closed (weekends),
so a Sunday snapshot would badly mislead you. Historical candles don't have that
problem because the gap hours simply have no candles.
"""
import os
import statistics
from datetime import datetime, timezone, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()  # finds .env in the current dir when run from repo root

TOKEN   = os.getenv("OANDA_API_TOKEN")
BASE    = "https://api-fxpractice.oanda.com"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

PAIRS = ["EUR_USD", "GBP_USD", "USD_JPY"]
DAYS  = 30   # ~500 H1 candles per pair — one request each, no pagination needed

if not TOKEN:
    raise SystemExit("Missing OANDA_API_TOKEN — run from the repo root so .env loads.")


def pip(pair):
    return 0.01 if pair.upper().endswith("JPY") else 0.0001


end   = datetime.now(timezone.utc)
start = end - timedelta(days=DAYS)

print(f"Measuring spread from the last {DAYS} days of H1 bid/ask candles\n")
print(f"{'pair':<9}{'median':>9}{'mean':>9}{'90th pct':>10}{'n':>7}")
print("-" * 44)

for p in PAIRS:
    params = {
        "granularity": "H1",
        "from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "to":   end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "price": "BA",                       # B = bid, A = ask
    }
    r = requests.get(f"{BASE}/v3/instruments/{p}/candles", headers=HEADERS, params=params)
    r.raise_for_status()

    spreads = []
    for c in r.json().get("candles", []):
        if not c.get("complete", True):
            continue
        ask = float(c["ask"]["c"])
        bid = float(c["bid"]["c"])
        spreads.append((ask - bid) / pip(p))   # spread in pips

    if not spreads:
        print(f"{p:<9}{'no data':>9}")
        continue

    spreads.sort()
    median = statistics.median(spreads)
    mean   = statistics.mean(spreads)
    p90    = spreads[int(len(spreads) * 0.9)]
    print(f"{p:<9}{median:>9.2f}{mean:>9.2f}{p90:>10.2f}{len(spreads):>7}")

print("\nUse the MEDIAN as your backtest spread_pips (it's robust to weekend/news")
print("spikes that inflate the mean). The 90th pct just shows how ugly it gets.")