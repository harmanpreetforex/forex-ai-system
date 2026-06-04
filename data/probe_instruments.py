"""
Account capability probe — read-only.

Answers the three gating questions for Tier-1 strategies:
  1. Which instruments can this account trade, grouped by asset class?
     (diversification breadth for TREND-FOLLOWING)
  2. What are the real financing / swap rates per instrument?
     (the entire edge for CARRY — retail brokers often shave these badly)
  3. Daily-data availability is implied (anything tradeable here can be pulled by
     oanda_pipeline.py with GRANULARITY="D").

Run from repo root:  python data/probe_instruments.py
Sends NO orders, changes nothing. Pure GET requests.
"""

import os
from pathlib import Path
from collections import defaultdict

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

API_TOKEN  = os.getenv("OANDA_API_TOKEN")
ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID")
BASE_URL   = "https://api-fxpractice.oanda.com"

if not API_TOKEN or not ACCOUNT_ID:
    raise SystemExit("Missing OANDA_API_TOKEN or OANDA_ACCOUNT_ID — check your .env file.")

HEADERS = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}


def get(path, params=None):
    r = requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params or {})
    r.raise_for_status()
    return r.json()


def main():
    # ── 1. All tradeable instruments on this account, grouped by type ──────────
    data = get(f"/v3/accounts/{ACCOUNT_ID}/instruments")
    instruments = data["instruments"]

    by_type = defaultdict(list)
    for ins in instruments:
        by_type[ins["type"]].append(ins)

    print("=" * 70)
    print(f"ACCOUNT INSTRUMENT UNIVERSE — {len(instruments)} total")
    print("=" * 70)
    for typ in sorted(by_type):
        names = sorted(i["name"] for i in by_type[typ])
        print(f"\n{typ}  ({len(names)}):")
        # print in rows of 6
        for i in range(0, len(names), 6):
            print("   " + "  ".join(f"{n:<12}" for n in names[i:i + 6]))

    # ── 2. Financing / swap rates (the carry edge) ─────────────────────────────
    # The long/short financing rates live on the instrument record under
    # 'financing'. Positive longRate = you GET PAID to hold long; negative = you PAY.
    print("\n" + "=" * 70)
    print("FINANCING / SWAP RATES  (annualized; long_minus_short = carry signal)")
    print("=" * 70)
    print(f"{'instrument':<14}{'longRate':>12}{'shortRate':>12}{'long-short':>14}")
    print("-" * 52)

    rows = []
    for ins in instruments:
        fin = ins.get("financing", {})
        lr = fin.get("longRate")
        sr = fin.get("shortRate")
        if lr is None or sr is None:
            continue
        lr, sr = float(lr), float(sr)
        rows.append((ins["name"], lr, sr, lr - sr))

    # sort by the carry spread (long_minus_short) — biggest positive carry first
    rows.sort(key=lambda x: x[3], reverse=True)
    for name, lr, sr, spread in rows:
        print(f"{name:<14}{lr:>12.4f}{sr:>12.4f}{spread:>14.4f}")

    print("\nNote: longRate/shortRate are OANDA's annualized financing rates.")
    print("A positive long-short spread is a structural tailwind for going long that")
    print("instrument; deeply negative = tailwind for short. This is the raw carry edge")
    print("BEFORE costs — the next step is checking it survives spread + drawdown risk.")


if __name__ == "__main__":
    main()
