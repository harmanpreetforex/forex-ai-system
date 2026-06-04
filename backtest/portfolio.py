"""
backtest/portfolio.py
--------------------------------------------------------------------
A RETURN-SPACE portfolio backtester for the trend-following basket.

WHY A SEPARATE BACKTESTER (and not the pip engine):
  - Trend-following's edge lives at the PORTFOLIO level — many instruments held
    at once, returns summed. A one-instrument-at-a-time loop literally cannot
    show the diversification that IS the edge.
  - You cannot add pips across asset classes (a pip of gold != a point of the
    S&P != a tick of a bond). Aggregating a mixed basket REQUIRES working in
    returns (%), not pips. This is math, not preference.
  - Sizing is continuous and vol-scaled, not a fixed SL/TP. The pip engine's
    trade-by-trade model doesn't fit.
So this sits ALONGSIDE engine.py — the pip engine stays the tool for discrete
chart-trade strategies; this is the tool for continuous portfolio strategies.

WHAT IT DOES, per instrument (all info-as-of-close-t, then lagged 1 bar so you
never trade on a bar you couldn't have seen):
  1. daily return r_t = close_t / close_{t-1} - 1
  2. realized vol_t = rolling std of r (VOL_WINDOW)
  3. direction = trend_signal(close, LOOKBACK)        [+1 / -1 / 0]
  4. position = direction * (TARGET_VOL_DAILY / vol_t), capped at MAX_LEVERAGE
     -> "same risk in every market": small size in wild markets, big in calm ones
  5. lag the position 1 bar (no-lookahead execution), earn position * r_t
  6. subtract cost = |Δposition| * COST_FRAC   (you pay the spread on turnover)

Portfolio return = EQUAL-WEIGHT MEAN across instruments (equal because each is
already vol-scaled to the same risk). Equity = cumulative product of (1 + ret).

VALIDATION: same walk-forward bar that killed every prior strategy — fixed params
(no grid search), non-overlapping test windows, costs included. Primary read =
PF>1 CONSISTENCY across windows, not any single number. CAGR / Sharpe / maxDD are
printed as context, but the pass bar is the same as before.

Run from repo root:  python -m backtest.portfolio
"""

from pathlib import Path

import numpy as np
import pandas as pd

from strategies.trend_follow import trend_signal

# ── Fixed config (FEW knobs on purpose — every parameter is a curve-fit risk) ──
DATA_DIR        = Path("data/basket_daily")
LOOKBACK        = 100      # trend lookback in trading days (~5 months). ONE choice, NOT grid-searched.
VOL_WINDOW      = 60       # days to estimate each instrument's volatility for sizing
TARGET_VOL_ANN  = 0.10     # annual vol target PER instrument (10%) -> equal risk per market
MAX_LEVERAGE    = 2.0      # cap per-instrument position so a tiny-vol estimate can't explode size
COST_FRAC       = 0.0002   # 2 bps of notional per unit of position change (conservative daily cost)
TRADING_DAYS    = 252

# Walk-forward geometry (daily bars). ~2500 bars -> 4 non-overlapping test windows.
WARMUP          = LOOKBACK + VOL_WINDOW   # bars to seed signal+vol before a window opens
TEST_SIZE       = 500                     # ~2 trading years per window
STEP            = TEST_SIZE                # non-overlapping


def load_basket():
    """Wide DataFrame of daily CLOSE prices, one column per instrument.

    Outer-join on date + forward-fill: a missing daily bar = a market holiday for
    that instrument, so carry the last price (its return that day becomes 0, i.e.
    it simply contributes nothing — the honest treatment of a closed market).
    """
    closes = {}
    for csv in sorted(DATA_DIR.glob("*.csv")):
        df = pd.read_csv(csv, parse_dates=["datetime"]).set_index("datetime")
        closes[csv.stem] = df["close"]
    if not closes:
        raise SystemExit(f"No CSVs in {DATA_DIR} — run data/pull_basket_daily.py first.")
    wide = pd.DataFrame(closes).sort_index()
    wide = wide.ffill()        # holidays -> carry last price
    return wide


def instrument_returns(close):
    """Net daily strategy return series for ONE instrument (lagged, cost-charged)."""
    r = close.pct_change()

    vol = r.rolling(VOL_WINDOW).std()
    target_daily = TARGET_VOL_ANN / np.sqrt(TRADING_DAYS)

    direction = trend_signal(close, LOOKBACK)            # info as-of close t
    raw_pos = direction * (target_daily / vol)
    raw_pos = raw_pos.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    raw_pos = raw_pos.clip(-MAX_LEVERAGE, MAX_LEVERAGE)

    # Execution lag: the position computed from close_t is only tradeable from t+1.
    pos = raw_pos.shift(1).fillna(0.0)

    gross = pos * r
    turnover = pos.diff().abs().fillna(pos.abs())        # first day's establish counts as turnover
    cost = turnover * COST_FRAC
    return (gross - cost).fillna(0.0)


def portfolio_returns(wide):
    """Equal-weight mean of the per-instrument net returns -> portfolio daily return."""
    per = pd.DataFrame({name: instrument_returns(wide[name]) for name in wide.columns})
    return per.mean(axis=1)          # equal weight = equal RISK (each leg vol-scaled)


def metrics(ret):
    """PF + risk/return stats for a daily-return series."""
    ret = ret.dropna()
    if ret.empty or ret.abs().sum() == 0:
        return dict(n=0, pf=float("nan"), cagr=float("nan"),
                    sharpe=float("nan"), maxdd=float("nan"))
    pos = ret[ret > 0].sum()
    neg = -ret[ret < 0].sum()
    pf = pos / neg if neg > 0 else float("inf")

    eq = (1 + ret).cumprod()
    years = len(ret) / TRADING_DAYS
    cagr = eq.iloc[-1] ** (1 / years) - 1 if years > 0 else float("nan")
    sharpe = (ret.mean() / ret.std() * np.sqrt(TRADING_DAYS)) if ret.std() > 0 else float("nan")
    maxdd = (eq / eq.cummax() - 1).min()
    return dict(n=len(ret), pf=pf, cagr=cagr, sharpe=sharpe, maxdd=maxdd)


def walk_forward(port_ret):
    """Non-overlapping test windows after a fixed warm-up; metrics per window."""
    n = len(port_ret)
    results = []
    test_start = WARMUP
    win = 0
    while test_start + TEST_SIZE <= n:
        win += 1
        seg = port_ret.iloc[test_start:test_start + TEST_SIZE]
        m = metrics(seg)
        m["window"] = win
        m["from"] = str(seg.index[0].date())
        m["to"]   = str(seg.index[-1].date())
        results.append(m)
        test_start += STEP
    return results


def report():
    wide = load_basket()
    port = portfolio_returns(wide)

    print("=" * 74)
    print(f"TREND-FOLLOWING BASKET — {wide.shape[1]} instruments, daily, "
          f"{str(wide.index[0].date())} → {str(wide.index[-1].date())}")
    print(f"params: lookback={LOOKBACK}d  vol_window={VOL_WINDOW}d  "
          f"target_vol={TARGET_VOL_ANN:.0%}/inst  cost={COST_FRAC*1e4:.0f}bps  "
          f"(FIXED, no grid search)")
    print("=" * 74)

    full = metrics(port.iloc[WARMUP:])
    print(f"\nFULL-PERIOD (post-warmup, in+out mixed — context only, NOT the bar):")
    print(f"   PF {full['pf']:.2f}   CAGR {full['cagr']:+.1%}   "
          f"Sharpe {full['sharpe']:.2f}   maxDD {full['maxdd']:.1%}   "
          f"days {full['n']}")

    print(f"\nWALK-FORWARD (the bar — read CONSISTENCY across windows):")
    print(f"{'win':>3} {'from':>11} {'to':>11} {'days':>5} "
          f"{'PF':>6} {'CAGR':>8} {'Sharpe':>7} {'maxDD':>7}")
    results = walk_forward(port)
    for r in results:
        print(f"{r['window']:>3} {r['from']:>11} {r['to']:>11} {r['n']:>5} "
              f"{r['pf']:>6.2f} {r['cagr']:>+8.1%} {r['sharpe']:>7.2f} {r['maxdd']:>7.1%}")

    pfs = [r["pf"] for r in results if r["n"] > 0 and np.isfinite(r["pf"])]
    above = sum(1 for p in pfs if p > 1)
    print("\n--- consistency (the real signal, not any one window) ---")
    if pfs:
        print(f"windows: {len(pfs)} | PF>1: {above}/{len(pfs)} | "
              f"median PF: {np.median(pfs):.2f} | "
              f"min {min(pfs):.2f} | max {max(pfs):.2f}")
        verdict = "PASSES the bar" if above >= max(3, len(pfs) - 1) else \
                  "MARGINAL" if above > len(pfs) / 2 else "FAILS the bar"
        print(f"VERDICT: {verdict} (need PF>1 in most/all windows, like every prior test).")
    else:
        print("No windows produced returns — check data/params.")


if __name__ == "__main__":
    report()
