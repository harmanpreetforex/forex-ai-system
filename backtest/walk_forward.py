"""
backtest/walk_forward.py

Walk-forward validation for the EUR/USD signal-exit SMA.

WHY THIS EXISTS
---------------
Day 13 gave us ONE out-of-sample data point (a single 70/30 split): EUR/USD
held up, train PF 1.35 -> test PF 1.44. Encouraging, but one split is one coin
flip. Walk-forward turns that single point into K of them by sliding
train->test windows across the full 2yr series and reporting PF per window.
The question is NOT "what's the best PF" -- it's "does the edge show up
consistently across periods, or did the one split get lucky?"

Params are FIXED on purpose (no grid search yet). With fixed params the 'train'
window selects nothing; it only warms the indicators. We keep a real train slot
so the optimizer can drop into it later (Day 9-real) without rebuilding this.

HONEST CAVEAT: each test window holds only ~40-70 trades. PF on 50 trades is
noisy. Read CONSISTENCY across windows, not any single window's number.
"""

import statistics as st
import pandas as pd
from backtest.engine import load_data, run_backtest
from strategies.sma_crossover import strategy_fn   # <-- confirm this is the real fn name


# ---- run config -------------------------------------------------------------
DATA_PATH   = "data/eurusd_1h_2y.csv"   # your 2yr EUR/USD H1 file
PAIR        = "EUR_USD"                  # exact string get_pip() expects
SPREAD_PIPS = 1.6                        # measured EUR/USD median (Day 10)
SL_PIPS     = 20                         # match what you ran on Day 13
TP_PIPS     = 40
SIGNAL_EXIT = True                       # signal-exit default for trend (Day 12)

# ---- window geometry (candles) ---------------------------------------------
TRAIN_SIZE  = 3000                       # warm-up / future optimization slot
TEST_SIZE   = 2000                       # non-overlapping -> no double-counting
STEP        = TEST_SIZE
WARMUP      = 60                         # candles to seed SMAs before a window

# ---- trade-dict accessors (confirmed from your engine) ----------------------
PNL_KEY     = "pnl"                      # realized P&L per trade
ENTRY_KEY   = "entry_time"
TIME_COL    = "time"                     # timestamp column in the dataframe
# -----------------------------------------------------------------------------


def metrics_from_trades(trades):
    """PF, win%, count, worst drawdown from a list of completed trades.

    Uses each trade's realized pnl. PF = gross win / gross loss; win% counts
    pnl > 0; drawdown uses a RUNNING peak (Day 8 lesson: global peak reads 0)."""
    pnls = [t[PNL_KEY] for t in trades]
    if not pnls:
        return dict(n=0, win_pct=float("nan"), pf=float("nan"), dd=0.0)

    gross_win  = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    pf = gross_win / gross_loss if gross_loss > 0 else float("inf")
    win_pct = 100 * sum(1 for p in pnls if p > 0) / len(pnls)

    eq = peak = dd = 0.0
    for p in pnls:
        eq += p
        peak = max(peak, eq)
        dd = max(dd, peak - eq)

    return dict(n=len(pnls), win_pct=win_pct, pf=pf, dd=dd)


def walk_forward(df):
    n = len(df)
    results = []
    win_id = 0
    test_start = TRAIN_SIZE

    while test_start + TEST_SIZE <= n:
        win_id += 1
        test_end = test_start + TEST_SIZE

        # Slice = warm-up prefix + test window, so the SMAs are seeded before
        # the window opens (no cold start, no lookahead).
        slice_start = max(0, test_start - WARMUP)
        window_df = df.iloc[slice_start:test_end].reset_index(drop=True)

        trades = run_backtest(
            window_df,
            PAIR,
            strategy_fn,
            sl_pips=SL_PIPS,
            tp_pips=TP_PIPS,
            spread_pips=SPREAD_PIPS,
            signal_exit=SIGNAL_EXIT,
        )

        # Keep only trades whose ENTRY falls inside the real test window.
        # Normalize BOTH sides to pandas Timestamps so a string-vs-Timestamp
        # mismatch can't silently filter everything out (that was the empty-
        # window bug). If your entry_time is already a Timestamp this is a noop.
        cutoff = pd.to_datetime(df.iloc[test_start][TIME_COL])
        test_trades = [
            t for t in trades
            if pd.to_datetime(t[ENTRY_KEY]) >= cutoff
        ]

        m = metrics_from_trades(test_trades)
        m["window"]       = win_id
        m["test_from"]    = df.iloc[test_start][TIME_COL]
        m["test_to"]      = df.iloc[test_end - 1][TIME_COL]
        m["raw_trades"]   = len(trades)        # before entry-time filter
        results.append(m)

        test_start += STEP

    return results


def report(results):
    print(f"{'win':>3} {'from':>12} {'to':>12} {'n':>5} {'raw':>5} "
          f"{'win%':>6} {'PF':>6} {'dd':>8}")
    for r in results:
        pf  = "  inf" if r["pf"] == float("inf") else f"{r['pf']:>6.2f}"
        win = "   nan" if r["n"] == 0 else f"{r['win_pct']:>6.1f}"
        print(f"{r['window']:>3} {str(r['test_from'])[:10]:>12} "
              f"{str(r['test_to'])[:10]:>12} {r['n']:>5} {r['raw_trades']:>5} "
              f"{win} {pf} {r['dd']:>8.2f}")

    pfs = [r["pf"] for r in results if r["n"] > 0 and r["pf"] != float("inf")]
    total = sum(r["n"] for r in results)
    raw   = sum(r["raw_trades"] for r in results)

    if not pfs:
        print(f"\nNo windows produced (filtered) trades. raw trades across all "
              f"windows = {raw}.")
        if raw > 0:
            print("Engine IS trading -- the entry-time filter is dropping "
                  "everything. Check that entry_time and the 'time' column are "
                  "the same format/timezone.")
        else:
            print("Engine produced zero trades at all -- check DATA_PATH, the "
                  "strategy function, and window sizing.")
        return

    above = sum(1 for p in pfs if p > 1)
    print("\n--- consistency (the real signal, not any one window) ---")
    print(f"windows w/ trades: {len(pfs)} | PF>1: {above}/{len(pfs)} | "
          f"median PF: {st.median(pfs):.2f} | min PF: {min(pfs):.2f} | "
          f"max PF: {max(pfs):.2f} | total trades: {total}")


if __name__ == "__main__":
    df = load_data(DATA_PATH)
    report(walk_forward(df))