"""
Day 3 — Live Price Fetcher
Pulls real-time bid/ask for EUR/USD, USD/CAD, GBP/USD from OANDA
Displays in a clean terminal table and stores ticks to prices.csv
"""

import os
import csv
import time
from datetime import datetime
from dotenv import load_dotenv
import oandapyV20
from oandapyV20.endpoints.pricing import PricingInfo

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
API_TOKEN    = os.getenv("OANDA_API_TOKEN")
ACCOUNT_ID   = os.getenv("OANDA_ACCOUNT_ID")
ENVIRONMENT  = os.getenv("OANDA_ENVIRONMENT", "practice")   # "practice" or "live"

PAIRS = ["EUR_USD", "USD_CAD", "GBP_USD"]
CSV_FILE = "prices.csv"
POLL_INTERVAL = 5      # seconds between each fetch
NUM_TICKS     = 12     # how many rounds to capture (set to 0 for infinite loop)

# ── OANDA client ──────────────────────────────────────────────────────────────
client = oandapyV20.API(access_token=API_TOKEN, environment=ENVIRONMENT)


def fetch_prices() -> list[dict]:
    """Fetch current bid/ask for all pairs. Returns list of tick dicts."""
    params = {"instruments": ",".join(PAIRS)}
    r = PricingInfo(accountID=ACCOUNT_ID, params=params)
    client.request(r)

    ticks = []
    for price in r.response["prices"]:
        instrument = price["instrument"]
        bid        = float(price["bids"][0]["price"])
        ask        = float(price["asks"][0]["price"])
        spread     = round((ask - bid) * 10_000, 1)   # spread in pips (4-decimal pairs)
        tradeable  = price.get("tradeable", False)
        ticks.append({
            "timestamp":  datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "pair":       instrument,
            "bid":        bid,
            "ask":        ask,
            "spread_pip": spread,
            "tradeable":  tradeable,
        })
    return ticks


def print_table(ticks: list[dict], tick_num: int) -> None:
    """Print a clean aligned table to the terminal."""
    header = f"  {'PAIR':<12} {'BID':>10} {'ASK':>10} {'SPREAD':>8}  {'STATUS':<10}"
    divider = "  " + "─" * (len(header) - 2)

    print(f"\n  Tick #{tick_num}  ·  {ticks[0]['timestamp']} UTC")
    print(divider)
    print(header)
    print(divider)
    for t in ticks:
        status = "✓ live" if t["tradeable"] else "✗ closed"
        print(
            f"  {t['pair']:<12} "
            f"{t['bid']:>10.5f} "
            f"{t['ask']:>10.5f} "
            f"{t['spread_pip']:>7.1f}p  "
            f"{status:<10}"
        )
    print(divider)


def append_to_csv(ticks: list[dict]) -> None:
    """Append ticks to prices.csv, writing header only on first write."""
    file_exists = os.path.isfile(CSV_FILE)
    fieldnames = ["timestamp", "pair", "bid", "ask", "spread_pip", "tradeable"]

    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(ticks)


def main():
    print("\n  ┌─────────────────────────────────────────┐")
    print("  │   OANDA Live Price Feed  ·  Day 3        │")
    print("  │   EUR/USD · USD/CAD · GBP/USD            │")
    print("  └─────────────────────────────────────────┘")
    print(f"\n  Saving to: {CSV_FILE}")
    print(f"  Polling every {POLL_INTERVAL}s  ·  {NUM_TICKS if NUM_TICKS else '∞'} ticks\n")
    print("  Press Ctrl+C to stop early.\n")

    tick_count = 0
    try:
        while True:
            tick_count += 1
            ticks = fetch_prices()
            print_table(ticks, tick_count)
            append_to_csv(ticks)

            if NUM_TICKS and tick_count >= NUM_TICKS:
                print(f"\n  ✓ Captured {tick_count} ticks → {CSV_FILE}\n")
                break

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print(f"\n\n  Stopped.  {tick_count} ticks saved to {CSV_FILE}\n")


if __name__ == "__main__":
    main()