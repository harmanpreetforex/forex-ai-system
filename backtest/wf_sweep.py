"""
backtest/wf_sweep.py
--------------------------------------------------------------------
Walk-forward the liquidity-sweep-reversal kernel (strategies/liquidity_sweep.py) —
the one falsifiable piece of the ICT/SMC day-trading video.

Tested on H1 MAJORS (the finest data available + a healthy sample size) AND daily
FX. Variable structure-based stop and opposite-level target, so it has its own
loop (the pip engine uses fixed stops). Same bar as everything else: PF>1
consistency across non-overlapping out-of-sample windows, spread charged,
no lookahead (signal at bar i fills at bar i+1 open), stop-first on same-bar
stop+target.

HONEST CAVEAT: H1 is a proxy for his 1m/5m intraday timeframe (data we don't have),
and this kernel is a proxy for his full discretionary multi-confluence method. It
tests the OBJECTIVE essence (sweep -> reversal -> opposite-level target), which is
the only falsifiable part.

Run:  python -m backtest.wf_sweep
"""

import statistics as st
import pandas as pd

from backtest.engine import load_data, get_pip
from strategies.liquidity_sweep import signals, LOOKBACK

WARMUP = LOOKBACK + 5
SPREAD = {"EUR_USD": 1.6, "GBP_USD": 1.9, "USD_JPY": 1.7,
          "AUD_USD": 1.5, "USD_CAD": 2.0, "USD_CHF": 2.0}

H1 = [("EUR_USD", "data/eurusd_1h_2y.csv", 2000),
      ("GBP_USD", "data/gbpusd_1h_2y.csv", 2000),
      ("USD_JPY", "data/usdjpy_1h_2y.csv", 2000)]
DAILY = [(p, f"data/basket_daily/{p}.csv", 400) for p in SPREAD]


def backtest(df, pair, spread):
    pip = get_pip(pair)
    sig = signals(df)
    trades, open_t, pending = [], None, None

    for i in range(len(df)):
        c = df.iloc[i]

        if pending and open_t is None:
            entry = c["open"]; d = pending["dir"]
            stop, tp = pending["stop"], pending["target"]
            risk = abs(entry - stop)
            # only take it if there's real risk AND the target is on the profit side
            good = risk > 0 and ((d == 1 and tp > entry) or (d == -1 and tp < entry))
            if good:
                open_t = {"direction": d, "entry": entry, "entry_time": c["time"],
                          "sl": stop, "tp": tp}
            pending = None

        if open_t:
            d = open_t["direction"]
            if d == 1:
                hit_sl, hit_tp = c["low"] <= open_t["sl"], c["high"] >= open_t["tp"]
            else:
                hit_sl, hit_tp = c["high"] >= open_t["sl"], c["low"] <= open_t["tp"]
            exit_px = open_t["sl"] if hit_sl else (open_t["tp"] if hit_tp else None)
            if exit_px is not None:
                pnl = (exit_px - open_t["entry"]) / pip if d == 1 else \
                      (open_t["entry"] - exit_px) / pip
                open_t["pnl"] = pnl - spread
                trades.append(open_t); open_t = None

        if open_t is None and pending is None:
            s = sig.iloc[i]
            if s["dir"] != 0 and not pd.isna(s["stop"]) and not pd.isna(s["target"]):
                pending = {"dir": int(s["dir"]), "stop": float(s["stop"]),
                           "target": float(s["target"])}
    return trades


def pf_of(trades):
    pnls = [t["pnl"] for t in trades]
    if not pnls:
        return None, 0
    gw = sum(p for p in pnls if p > 0); gl = -sum(p for p in pnls if p < 0)
    return (gw / gl if gl > 0 else float("inf")), len(pnls)


def walk_forward(df, pair, spread, test_size):
    n = len(df); out, start = [], WARMUP
    while start + test_size <= n:
        seg = df.iloc[max(0, start - WARMUP):start + test_size].reset_index(drop=True)
        trades = backtest(seg, pair, spread)
        cutoff = pd.to_datetime(df.iloc[start]["time"])
        test = [t for t in trades if pd.to_datetime(t["entry_time"]) >= cutoff]
        pf, ntr = pf_of(test)
        if pf is not None:
            out.append((pf, ntr))
        start += test_size
    return out


def run_block(title, config):
    print("\n" + "=" * 70); print(title); print("=" * 70)
    all_pfs, grand = [], 0
    for pair, path, test_size in config:
        try:
            df = load_data(path)
        except FileNotFoundError:
            print(f"  {pair:<9} — no data ({path})"); continue
        res = walk_forward(df, pair, SPREAD[pair], test_size)
        pfs = [pf for pf, _ in res if pf != float("inf")]
        n = sum(nt for _, nt in res); grand += n; all_pfs += pfs
        if pfs:
            above = sum(1 for p in pfs if p > 1)
            wins = " ".join(f"{p:.2f}" for p in pfs)
            print(f"  {pair:<9} windows {len(pfs)} | PF>1 {above}/{len(pfs)} | "
                  f"med {st.median(pfs):.2f} | trades {n:>5} | [{wins}]")
        else:
            print(f"  {pair:<9} — no trades (n={n})")
    if all_pfs:
        above = sum(1 for p in all_pfs if p > 1)
        print(f"\n  AGGREGATE: {len(all_pfs)} windows | PF>1 {above}/{len(all_pfs)} "
              f"| median PF {st.median(all_pfs):.2f} | total trades {grand}")
        verdict = "PASSES" if above >= len(all_pfs) * 0.7 else \
                  "MARGINAL" if above > len(all_pfs) / 2 else "FAILS"
        print(f"  VERDICT: {verdict} the bar.")


if __name__ == "__main__":
    run_block("LIQUIDITY-SWEEP REVERSAL — H1 MAJORS (best sample)", H1)
    run_block("LIQUIDITY-SWEEP REVERSAL — DAILY FX", DAILY)
