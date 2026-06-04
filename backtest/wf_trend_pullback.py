"""
backtest/wf_trend_pullback.py
--------------------------------------------------------------------
Walk-forward the trend+pullback strategy on BOTH timeframes, fixed 20/40 SL/TP,
held to the SAME bar as every prior strategy: PF>1 consistency across non-
overlapping out-of-sample windows, costs (spread) included, no lookahead.

SCOPE NOTE: the daily test uses FX PAIRS ONLY. Fixed pip-based stops (20/40 pips)
are a forex concept; a 20-pip stop on a 5000-point index or a bond is meaningless,
so the mixed basket is out of scope for THIS (pip-engine) strategy. That's an
honest constraint, not a cherry-pick.

Run:  python -m backtest.wf_trend_pullback
"""

import statistics as st
import pandas as pd

from backtest.engine import load_data, run_backtest
from strategies.trend_pullback import strategy_fn, SMA_TREND

SL_PIPS, TP_PIPS = 20, 40
WARMUP = SMA_TREND + 30          # seed SMA200 + stochastic before a window opens

# per-pair measured/estimated round-trip spread in pips
SPREAD = {
    "EUR_USD": 1.6, "GBP_USD": 1.9, "USD_JPY": 1.7,
    "AUD_USD": 1.5, "USD_CAD": 2.0, "USD_CHF": 2.0,
}

H1 = [   # (pair, csv, test_window_candles)
    ("EUR_USD", "data/eurusd_1h_2y.csv", 2000),
    ("GBP_USD", "data/gbpusd_1h_2y.csv", 2000),
    ("USD_JPY", "data/usdjpy_1h_2y.csv", 2000),
]
DAILY = [(p, f"data/basket_daily/{p}.csv", 400) for p in SPREAD]   # all 6 FX majors


def pf_dd(trades):
    pnls = [t["pnl"] for t in trades]
    if not pnls:
        return None
    gw = sum(p for p in pnls if p > 0)
    gl = -sum(p for p in pnls if p < 0)
    pf = gw / gl if gl > 0 else float("inf")
    eq = peak = dd = 0.0
    for p in pnls:
        eq += p; peak = max(peak, eq); dd = max(dd, peak - eq)
    win = 100 * sum(1 for p in pnls if p > 0) / len(pnls)
    return dict(n=len(pnls), pf=pf, win=win, dd=dd, total=sum(pnls))


def walk_forward(df, pair, spread, test_size):
    n = len(df)
    out, start = [], WARMUP
    while start + test_size <= n:
        seg = df.iloc[max(0, start - WARMUP):start + test_size].reset_index(drop=True)
        trades = run_backtest(seg, pair, strategy_fn, sl_pips=SL_PIPS, tp_pips=TP_PIPS,
                              spread_pips=spread, signal_exit=False)
        cutoff = pd.to_datetime(df.iloc[start]["time"])
        test = [t for t in trades if pd.to_datetime(t["entry_time"]) >= cutoff]
        m = pf_dd(test)
        if m:
            m["from"] = str(df.iloc[start]["time"])[:10]
            out.append(m)
        start += test_size
    return out


def run_block(title, config):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)
    all_pfs, grand_trades = [], 0
    for pair, path, test_size in config:
        try:
            df = load_data(path)
        except FileNotFoundError:
            print(f"  {pair:<9} — data not found ({path})"); continue
        res = walk_forward(df, pair, SPREAD[pair], test_size)
        pfs = [r["pf"] for r in res if r["pf"] != float("inf")]
        n = sum(r["n"] for r in res)
        grand_trades += n
        all_pfs += pfs
        if pfs:
            above = sum(1 for p in pfs if p > 1)
            wins = " ".join(f"{p:.2f}" for p in pfs)
            print(f"  {pair:<9} windows {len(pfs)} | PF>1 {above}/{len(pfs)} | "
                  f"med {st.median(pfs):.2f} | trades {n:>4} | [{wins}]")
        else:
            print(f"  {pair:<9} — no trades in any window (n={n})")
    if all_pfs:
        above = sum(1 for p in all_pfs if p > 1)
        print(f"\n  AGGREGATE: {len(all_pfs)} windows | PF>1 {above}/{len(all_pfs)} "
              f"| median PF {st.median(all_pfs):.2f} | total trades {grand_trades}")
        verdict = "PASSES" if above >= len(all_pfs) * 0.7 else \
                  "MARGINAL" if above > len(all_pfs) / 2 else "FAILS"
        print(f"  VERDICT: {verdict} the bar.")
    return all_pfs


if __name__ == "__main__":
    h1 = run_block("TREND+PULLBACK — H1 MAJORS (apples-to-apples w/ old SMA/RSI)", H1)
    dl = run_block("TREND+PULLBACK — DAILY FX MAJORS", DAILY)
