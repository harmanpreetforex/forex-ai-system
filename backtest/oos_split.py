"""
backtest/oos_split.py
--------------------------------------------------------------------
Day 9 / Day 13 deliverable: the train/test (in-sample / out-of-sample) split.

Why this file exists
--------------------
Every PF number you've seen so far is IN-SAMPLE: computed on the same 2
years you've been staring at since Day 10. A strategy can look good on its
own history purely by luck or curve-fit. The only number that distinguishes
a real edge from a flattering coincidence is performance on data the
strategy NEVER touched while you were deciding anything about it.

Method (the honest way for time series)
---------------------------------------
- Split CHRONOLOGICALLY, never randomly. Train = older 70%, test = newer 30%.
  (Random shuffling leaks the future into the past -- a fatal, invisible bug.)
- Warm-up: a 10/30 SMA needs ~30 prior candles. If we sliced the test set and
  ran it standalone, its first ~30 bars would have no history. So we feed the
  engine the FULL dataframe (indicators stay warm across the boundary) and
  attribute each trade to train or test by its ENTRY index.
- Same strategy, same costs, same risk, same exit (signal-exit) as Day 12.

What to look for
----------------
- Test PF roughly tracks train PF, on multiple pairs  -> plausible real effect.
- Test PF collapses vs train                          -> in-sample was noise / curve-fit.
- One pair holds, others collapse                     -> not a portfolio edge.

Run from project root:
    python -m backtest.oos_split
--------------------------------------------------------------------
"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backtest.engine import load_data, run_backtest
from strategies.sma_crossover import strategy_fn as sma_fn


# Reuse the SAME pair config + costs as run_backtest.py (apples-to-apples).
PAIRS = {
    "EUR_USD": {"data": "eurusd_1h_2y.csv", "spread_pips": 1.6},
    "GBP_USD": {"data": "gbpusd_1h_2y.csv", "spread_pips": 1.9},
    "USD_JPY": {"data": "usdjpy_1h_2y.csv", "spread_pips": 1.7},
}

STRATEGY    = sma_fn
SL_PIPS     = 20
SIGNAL_EXIT = True          # Day 12 verdict: signal-exit is the default for trend
TRAIN_FRAC  = 0.70          # older 70% train, newer 30% test


def pf_winrate(trades):
    """Profit factor + win% from a list of closed trades (pnl in pips, nets spread)."""
    n = len(trades)
    if n == 0:
        return 0, 0.0, 0.0, 0.0
    wins = sum(1 for t in trades if t["pnl"] > 0)
    gross_win = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gross_loss = -sum(t["pnl"] for t in trades if t["pnl"] < 0)
    pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    total = sum(t["pnl"] for t in trades)
    return n, wins / n * 100, pf, total


def split_trades(trades, boundary_time):
    """Attribute each trade to train/test by its ENTRY time vs the split boundary.
    Using entry (not exit) keeps a trade wholly in the window where it was decided."""
    train = [t for t in trades if t["entry_time"] is not None and t["entry_time"] < boundary_time]
    test  = [t for t in trades if t["entry_time"] is not None and t["entry_time"] >= boundary_time]
    return train, test


def main():
    rows = []
    print(f"Signal-exit SMA — in-sample vs out-of-sample (train {TRAIN_FRAC:.0%} / "
          f"test {1-TRAIN_FRAC:.0%}, chronological)\n")

    for pair, cfg in PAIRS.items():
        df = load_data(os.path.join(ROOT, "data", cfg["data"]))
        n = len(df)
        split_i = int(n * TRAIN_FRAC)
        boundary_time = df.iloc[split_i]["time"]

        # Run the engine ONCE on the full df (indicators warm across the boundary),
        # then attribute trades to train/test by entry time.
        trades = run_backtest(
            df, pair=pair, strategy_fn=STRATEGY,
            sl_pips=SL_PIPS, tp_pips=None,
            spread_pips=cfg["spread_pips"], signal_exit=SIGNAL_EXIT,
        )
        train, test = split_trades(trades, boundary_time)

        tr_n, tr_wr, tr_pf, tr_tot = pf_winrate(train)
        te_n, te_wr, te_pf, te_tot = pf_winrate(test)

        print(f"===== {pair} =====")
        print(f"  boundary: {boundary_time}  (candle {split_i}/{n})")
        print(f"  TRAIN (in-sample) : {tr_n:>4} trades  win {tr_wr:4.1f}%  PF {tr_pf:.2f}  ({tr_tot:+.0f} pips)")
        print(f"  TEST  (OUT-sample): {te_n:>4} trades  win {te_wr:4.1f}%  PF {te_pf:.2f}  ({te_tot:+.0f} pips)\n")
        rows.append((pair, tr_n, tr_pf, te_n, te_pf))

    print("=" * 64)
    print("VERDICT TABLE  (test PF is the only one that counts)")
    print("=" * 64)
    hdr = f"{'pair':<9}{'train n':>9}{'train PF':>10}{'test n':>9}{'test PF':>10}"
    print(hdr); print("-" * len(hdr))
    for pair, trn, trpf, ten, tepf in rows:
        trpf_s = "inf" if trpf == float("inf") else f"{trpf:.2f}"
        tepf_s = "inf" if tepf == float("inf") else f"{tepf:.2f}"
        print(f"{pair:<9}{trn:>9}{trpf_s:>10}{ten:>9}{tepf_s:>10}")

    print("\nRead it honestly: if test PF doesn't hold up vs train, the in-sample")
    print("positives were noise. Log the test PFs (not the train PFs) in the tracker.")


if __name__ == "__main__":
    main()