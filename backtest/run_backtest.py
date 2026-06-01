"""
backtest/run_backtest.py
--------------------------------------------------------------------
The GLUE. Run ONE strategy across MULTIPLE pairs on the same costs and
compare them apples-to-apples (Day 7 fairness + Day 10 portfolio view).

Day 9-deep+ change (SESSION FILTER TEST): each pair now runs the
signal-exit SMA under TWO entry-hour regimes in one pass --
  all-hours     (no filter; this is the Day 9-deep baseline, re-confirmed)
  overlap-only  (entries gated to the London/NY overlap; exits unrestricted)
...so the all-hours vs overlap delta is a true apples-to-apples comparison
(same data, same costs, same risk) -- it isolates ONE hypothesis: do
overlap-hour entries trade better at the SAME spread?

  IMPORTANT -- what this run is NOT testing:
  Both variants use the SAME measured all-hours spreads (1.6/1.9/1.7 pip).
  That is on purpose. It isolates TRADE QUALITY. The separate COST hypothesis
  -- that overlap hours also cost ~1.0 pip instead of ~1.6 (Day 10 measurement)
  -- is NOT bundled here. If overlap-only wins at the SAME spread, that's a real
  signal-quality finding. Run the cheaper-spread variant separately AFTER, so you
  never confuse "better trades" with "cheaper trades."

  AND -- this runs the FULL 2yr series, not the 4 walk-forward windows. It's a
  first look with good n. The decision rule (median PF>1 AND stable across the
  same 4 windows) still has to go through the Day 9-deep walk-forward harness.

On the FX rate (important, learned the hard way):
  Under fixed-fractional sizing the quote->CAD rate CANCELS out of the
  dollar equity curve -- it appears in both the unit count and the cash
  P&L. It only sets the (physically real) `units` number and a small
  int()-floor rounding. SPREAD, by contrast, is a flat deduction per
  trade and does NOT cancel -- it genuinely changes the results.

Each pair is simulated as its own independent $900 account (fair
comparison: which pair does the strategy like best). A TRUE shared-account
portfolio sim -- trades interleaved by timestamp, one balance, correlation
between pairs -- is a separate, harder task and is deliberately NOT done here.

Run from the project root:
    python -m backtest.run_backtest
--------------------------------------------------------------------
"""
import os, sys, csv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import matplotlib.pyplot as plt
from backtest.engine import load_data, run_backtest, summarize
from risk.position_sizer import position_size
from strategies.sma_crossover import strategy_fn as sma_fn   # ONE import, aliased


# --- Pairs: data + CORRECT quote->CAD rate + REAL spread -------------
# quote_to_cad converts the pair's QUOTE currency into CAD:
#   EUR_USD / GBP_USD -> quote is USD -> USD/CAD  (~1.37)
#   USD_JPY           -> quote is JPY -> JPY/CAD  (~0.0092 = 1.37 / ~149)
# spread_pips: ALL-HOURS measured medians (Day 10). Held constant for BOTH
# variants on purpose -- see the cost-vs-quality note in the docstring.
PAIRS = {
    "EUR_USD": {"data": "eurusd_1h_2y.csv", "quote_to_cad": 1.37,   "spread_pips": 1.6},
    "GBP_USD": {"data": "gbpusd_1h_2y.csv", "quote_to_cad": 1.37,   "spread_pips": 1.9},
    "USD_JPY": {"data": "usdjpy_1h_2y.csv", "quote_to_cad": 0.0092, "spread_pips": 1.7},
}

# --- London/NY overlap, in UTC ---------------------------------------
# Winter (GMT/EST): overlap 13:00-16:00 UTC -> {13,14,15}
# Summer (BST/EDT): overlap 12:00-15:00 UTC -> {12,13,14}
# Union {12,13,14,15} catches the meat in both regimes.
#   CAVEAT (log it, like the constant-FX-rate one): this is a DST approximation,
#   not exact session boundaries. Tighten to {13,14} later if the idea survives.
#   PRECONDITION: candle timestamps MUST be UTC. Verify before trusting this
#   (OANDA v20 returns UTC; confirm oanda_pipeline.py didn't localize anywhere).
OVERLAP_HOURS_UTC = {12, 13, 14, 15}

# --- One strategy + identical risk params across all pairs (fairness) -
STRATEGY = sma_fn
# Day 9-deep falsified the raw signal-exit SMA (median PF 0.93 across 4 walk-forward
# windows, PF>1 in only 1/4). This run asks the one principled follow-up before
# declaring raw price+SMA edgeless: are OVERLAP-hour entries better, at the SAME cost?
# Both variants are signal-exit; ONLY the entry-hour gate differs.
VARIANTS = [
    ("all-hours",    dict(tp_pips=None, signal_exit=True, allowed_entry_hours=None)),
    ("overlap-only", dict(tp_pips=None, signal_exit=True, allowed_entry_hours=OVERLAP_HOURS_UTC)),
]
SL_PIPS          = 20
STARTING_BALANCE = 900.0        # roughly your real personal account
RISK_PCT         = 0.005        # 0.5% per trade WHILE LEARNING
RESULTS_DIR      = os.path.join(ROOT, "results")


def simulate_balance(trades, pair, starting_balance, risk_pct, quote_to_cad):
    """Replay pip results as a compounding CAD balance. Sizes off the balance
    BEFORE each trade, so wins grow the next position and losses shrink it.
    Mutates each trade with 'units' and 'pnl_cash'. Returns (equity, final)."""
    balance = starting_balance
    equity = [balance]
    for t in trades:
        sized = position_size(balance, risk_pct, t["stop_pips"], pair, quote_to_cad)
        pnl_cash = t["pnl"] * sized.pip_value * sized.units   # CAD; pnl already nets spread
        t["units"] = sized.units
        t["pnl_cash"] = round(pnl_cash, 2)
        balance += pnl_cash
        equity.append(balance)
    return equity, balance


def max_dollar_drawdown(equity):
    """Largest peak-to-trough drop using a RUNNING peak (not the global peak --
    that version silently reads $0 when the curve ends at its high)."""
    running_peak = equity[0]
    dd = 0.0
    for bal in equity:
        running_peak = max(running_peak, bal)
        dd = max(dd, running_peak - bal)
    return dd


def quick_metrics(trades):
    """Computed straight from the trade dicts so we don't depend on summarize()'s
    key names. pnl is in pips and already includes spread."""
    n = len(trades)
    if n == 0:
        return {"trades": 0, "win_rate": 0.0, "profit_factor": 0.0, "total_pips": 0.0}
    wins = sum(1 for t in trades if t["pnl"] > 0)
    gross_win = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gross_loss = -sum(t["pnl"] for t in trades if t["pnl"] < 0)
    pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    return {
        "trades": n,
        "win_rate": wins / n * 100,
        "profit_factor": pf,
        "total_pips": sum(t["pnl"] for t in trades),
    }


def plot_dollar_equity(equity, name, out_dir):
    """Per-(pair,variant) CAD equity curve. `name` carries pair+variant so the
    curves don't clobber each other's PNGs."""
    os.makedirs(out_dir, exist_ok=True)
    safe = name.lower().replace(" ", "_")
    path = os.path.join(out_dir, f"equity_dollars_{safe}.png")
    plt.figure(figsize=(10, 5))
    plt.plot(equity, linewidth=1.4)
    plt.axhline(equity[0], linestyle="--", linewidth=0.8, alpha=0.6)
    plt.title(f"{name} — equity (CAD) — start ${equity[0]:,.0f} @ {RISK_PCT*100:.1f}% risk/trade")
    plt.xlabel("Trade #")
    plt.ylabel("Balance (CAD)")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=120)
    plt.close()
    return path


def write_combined_log(rows, out_dir):
    """One portfolio-level CSV with `pair` + `variant` columns — every trade
    across all pairs and both entry-hour variants.
    (Additive to your Day 6 per-pair results.py log, not a replacement.)"""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "trade_log_all_pairs.csv")
    cols = ["pair", "variant", "direction", "entry", "exit",
            "pnl_pips", "exit_reason", "units", "pnl_cash"]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([
                r["pair"], r.get("variant", ""), r["direction"],
                f"{r['entry']:.5f}", f"{r.get('exit', 0):.5f}",
                f"{r['pnl']:.1f}", r.get("exit_reason", ""),
                r.get("units", 0), r.get("pnl_cash", 0.0),
            ])
    return path


def main():
    comparison = []
    all_trades = []

    for vlabel, vkwargs in VARIANTS:
        for pair, cfg in PAIRS.items():
            data_path = os.path.join(ROOT, "data", cfg["data"])
            df = load_data(data_path)
            print(f"\n===== {pair}  [{vlabel}] =====")
            print(f"Loaded {len(df)} candles from {cfg['data']}  "
                  f"(spread {cfg['spread_pips']} pip, quote->CAD {cfg['quote_to_cad']})")

            trades = run_backtest(
                df, pair=pair, strategy_fn=STRATEGY,
                sl_pips=SL_PIPS, spread_pips=cfg["spread_pips"],
                **vkwargs,        # tp_pips + signal_exit + allowed_entry_hours per variant
            )

            # pips view (your existing summary) for the detail
            for k, v in summarize(trades).items():
                print(f"  {k:>18}: {v}")

            label = f"{pair} [{vlabel}]"
            if not trades:
                comparison.append((label, 0, 0.0, 0.0, STARTING_BALANCE, 0.0, 0.0))
                continue

            equity, final = simulate_balance(
                trades, pair, STARTING_BALANCE, RISK_PCT, cfg["quote_to_cad"]
            )
            m = quick_metrics(trades)
            dd = max_dollar_drawdown(equity)
            ret_pct = (final / STARTING_BALANCE - 1) * 100

            print(f"  {'final balance':>18}: ${final:,.2f}  ({ret_pct:+.1f}%)")
            print(f"  {'max $ drawdown':>18}: ${dd:,.2f}")

            plot_dollar_equity(equity, label, RESULTS_DIR)
            for t in trades:
                all_trades.append({**t, "pair": pair, "variant": vlabel})
            comparison.append(
                (label, m["trades"], m["win_rate"], m["profit_factor"],
                 final, ret_pct, dd)
            )

    # --- Comparison table: all-hours block, then overlap-only block ---
    print("\n" + "=" * 86)
    print("SMA signal-exit: all-hours vs overlap-only  "
          "(independent $%.0f accounts, %.1f%% risk/trade, SAME spread)"
          % (STARTING_BALANCE, RISK_PCT * 100))
    print("=" * 86)
    hdr = (f"{'pair [variant]':<24}{'trades':>8}{'win%':>8}{'PF':>8}"
           f"{'final $':>12}{'return%':>10}{'maxDD$':>10}")
    print(hdr)
    print("-" * len(hdr))
    for name, n, wr, pf, final, ret, dd in comparison:
        pf_s = "inf" if pf == float("inf") else f"{pf:.2f}"
        print(f"{name:<24}{n:>8}{wr:>8.1f}{pf_s:>8}{final:>12,.2f}{ret:>10.1f}{dd:>10,.2f}")

    print("\nRead trade COUNT, not just PF: the overlap filter cuts ~80%+ of candles,"
          "\nso a small n can fake a good PF in either direction (Day 9-deep lesson).")

    if all_trades:
        log = write_combined_log(all_trades, RESULTS_DIR)
        print(f"\nCombined trade log -> {log}")

    print("\nReminder: log this run in 01_Progress_Tracker.md "
          "(full-data look only -- still need the 4-window walk-forward to decide).")


if __name__ == "__main__":
    main()