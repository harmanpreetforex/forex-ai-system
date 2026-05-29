"""
backtest/run_backtest.py
--------------------------------------------------------------------
The GLUE. Pick a data file, pick a strategy, run the engine, print results.

Run it from the project root:
    python -m backtest.run_backtest
or simply:
    python backtest/run_backtest.py
--------------------------------------------------------------------
"""
import os
import sys

# Make the project root importable no matter how this script is launched
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backtest.engine import load_data, run_backtest, summarize
from strategies.sma_crossover import strategy_fn

DATA_FILE = os.path.join(ROOT, "data", "eurusd_1h_30d.csv")
PAIR = "EUR_USD"


def main():
    df = load_data(DATA_FILE)
    print(f"Loaded {len(df)} candles from {os.path.basename(DATA_FILE)}")

    trades = run_backtest(
        df,
        pair=PAIR,
        strategy_fn=strategy_fn,
        sl_pips=20,       # stop-loss distance in pips
        tp_pips=40,       # take-profit distance (2:1 reward-to-risk)
        spread_pips=1.0,  # cost charged on every trade entry
    )

    stats = summarize(trades)
    print("\n----- BACKTEST RESULTS -----")
    for k, v in stats.items():
        print(f"{k:>16}: {v}")

    print("\nFirst 5 trades:")
    for t in trades[:5]:
        print(
            f"  {t['direction']:>4} @ {t['entry']:.5f} -> "
            f"{t.get('exit', 0):.5f}  ({t['pnl']:+.1f} pips)"
        )


if __name__ == "__main__":
    main()