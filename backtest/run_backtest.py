"""
backtest/run_backtest.py
--------------------------------------------------------------------
The GLUE. Pick a data file, pick a strategy, run the engine, print results.

Day 8 addition: the engine works in pips; THIS file converts those pips
into a compounding CAD account balance using the position sizer. Each
trade is sized off the CURRENT balance, risking RISK_PCT against its own
stop distance - so the dollar curve reflects real per-trade sizing, not
a flat "1 pip = $X" assumption.

Run it from the project root:
    python -m backtest.run_backtest
--------------------------------------------------------------------
"""
import os
import sys

# Make the project root importable no matter how this script is launched
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import matplotlib.pyplot as plt

from backtest.engine import load_data, run_backtest, summarize
from backtest.results import write_trade_log, plot_equity
from risk.position_sizer import position_size
from strategies.rsi_reversal import strategy_fn


DATA_FILE = os.path.join(ROOT, "data", "eurusd_1h_30d.csv")
PAIR = "EUR_USD"

# --- Money config (per 02_Risk_Rules.md) -----------------------------
STARTING_BALANCE = 900.0     # roughly your real personal account
RISK_PCT         = 0.005     # 0.5% per trade WHILE LEARNING
QUOTE_TO_ACCOUNT = 1.37      # USD -> CAD. Constant approximation (see caveat below).
# CAVEAT: a fully correct backtest converts at each trade's actual-timestamp
# rate. Over a 30-day window the error is small; do NOT mistake this dollar
# curve for precision it doesn't have. Fix it when we go multi-month.
# ---------------------------------------------------------------------


def simulate_balance(trades, pair, starting_balance, risk_pct, quote_to_account):
    """
    Replay the engine's pip results as a compounding CAD balance.

    Sizing is done off the balance BEFORE each trade, so wins grow the next
    position and losses shrink it - the actual compounding you'd experience.
    Mutates each trade dict with 'units' and 'pnl_cash' so the trade log can
    show real dollars. Returns (equity_curve, final_balance).
    """
    balance = starting_balance
    equity = [balance]

    for t in trades:
        sized = position_size(balance, risk_pct, t["stop_pips"], pair, quote_to_account)
        # pnl is in pips and ALREADY includes the spread cost from the engine.
        pnl_cash = t["pnl"] * sized.pip_value * sized.units   # CAD
        t["units"] = sized.units
        t["pnl_cash"] = round(pnl_cash, 2)
        balance += pnl_cash
        equity.append(balance)

    return equity, balance


def plot_dollar_equity(equity, out_dir):
    """Save the CAD equity curve - the version that actually means something."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "equity_dollars.png")
    plt.figure(figsize=(10, 5))
    plt.plot(equity, marker="o", linewidth=1.5)
    plt.axhline(equity[0], linestyle="--", linewidth=0.8, alpha=0.6)
    plt.title(f"Account equity (CAD) - start ${equity[0]:,.0f} @ {RISK_PCT*100:.1f}% risk/trade")
    plt.xlabel("Trade #")
    plt.ylabel("Balance (CAD)")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=120)
    plt.close()
    print(f"Saved dollar equity curve -> {path}")


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
    print("\n----- BACKTEST RESULTS (pips) -----")
    for k, v in stats.items():
        print(f"{k:>18}: {v}")

    if not trades:
        print("\nNo trades - skipping money simulation and outputs.")
        return

    # --- Day 8: convert pips -> compounding CAD balance ---------------
    equity, final = simulate_balance(
        trades, PAIR, STARTING_BALANCE, RISK_PCT, QUOTE_TO_ACCOUNT
    )
    pct = (final / STARTING_BALANCE - 1) * 100
     # Max drawdown = largest peak-to-trough drop using a RUNNING peak,
    # not the global peak. (The global-peak version reads $0 whenever the
    # curve ends at its high.)
    running_peak = equity[0]
    dd_dollars = 0.0
    for bal in equity:
        running_peak = max(running_peak, bal)
        dd_dollars = max(dd_dollars, running_peak - bal)

    print("\n----- ACCOUNT SIMULATION (CAD) -----")
    print(f"   starting balance: ${STARTING_BALANCE:,.2f}")
    print(f"      final balance: ${final:,.2f}  ({pct:+.1f}%)")
    print(f"   max $ drawdown  : ${dd_dollars:,.2f}")
    print(f"   risk per trade  : {RISK_PCT*100:.1f}%  (~${STARTING_BALANCE*RISK_PCT:,.2f} at start)")

    print("\nFirst 5 trades (with sizing):")
    for t in trades[:5]:
        print(
            f"  {t['direction']:>4} @ {t['entry']:.5f} -> {t.get('exit', 0):.5f}  "
            f"({t['pnl']:+.1f} pips, {t['units']:,} units, ${t['pnl_cash']:+,.2f})"
        )

    # Day 6 reporting (pips) + Day 8 reporting (dollars)
    write_trade_log(trades)
    plot_equity(trades)
    plot_dollar_equity(equity, os.path.join(ROOT, "results"))


if __name__ == "__main__":
    main()