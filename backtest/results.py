"""
backtest/results.py
--------------------------------------------------------------------
Reporting / analytics for backtests.
Deliberately kept OUT of the engine: the engine produces trades,
this module turns trades into things a human can actually judge.
--------------------------------------------------------------------
"""
import os
import csv
import matplotlib.pyplot as plt

RESULTS_DIR = "results"


def _ensure_results_dir():
    os.makedirs(RESULTS_DIR, exist_ok=True)


def equity_curve(trades):
    """Cumulative net pips after each closed trade. Starts at 0."""
    equity = [0.0]
    for t in trades:
        equity.append(equity[-1] + t["pnl"])
    return equity  # length = len(trades) + 1


def max_drawdown(trades):
    """
    Largest peak-to-trough drop on the cumulative-pip curve, as a
    POSITIVE number of pips (0.0 if the curve never went underwater).
    """
    curve = equity_curve(trades)
    peak = curve[0]
    worst = 0.0
    for value in curve:
        if value > peak:        # new high-water mark
            peak = value
        drop = peak - value     # how far below the peak we are now
        if drop > worst:
            worst = drop
    return worst


def write_trade_log(trades, filename="trade_log.csv"):
    """Full per-trade record so you can eyeball exactly what the engine did."""
    _ensure_results_dir()
    path = os.path.join(RESULTS_DIR, filename)
    fields = ["entry_time", "exit_time", "direction", "entry", "exit", "pnl"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(trades)
    print(f"Trade log written: {path}  ({len(trades)} trades)")
    return path


def plot_equity(trades, filename="equity_curve.png"):
    """Save the cumulative-pip equity curve. A picture catches what stats hide."""
    _ensure_results_dir()
    path = os.path.join(RESULTS_DIR, filename)
    curve = equity_curve(trades)
    plt.figure(figsize=(10, 5))
    plt.plot(range(len(curve)), curve, linewidth=1.5)
    plt.axhline(0, linestyle="--", linewidth=0.8)  # break-even reference
    plt.title("Equity Curve (cumulative net pips)")
    plt.xlabel("Trade #")
    plt.ylabel("Cumulative pips")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=120)
    plt.close()
    print(f"Equity curve saved: {path}")
    return path