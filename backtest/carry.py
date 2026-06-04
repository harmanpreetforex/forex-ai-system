"""
backtest/carry.py
--------------------------------------------------------------------
Carry strategy + trend/carry COMBINATION, in the same return-space portfolio
backtester as backtest/portfolio.py.

CARRY MODEL (per instrument):
  - direction = SIGN of the true rate differential c=(longRate-shortRate)/2,
    taken from data/financing_rates.csv. STATIC over the whole backtest.
  - position magnitude = vol-scaled to equal risk (same machinery as trend).
  - daily total return = position * spot_return            (you bear price risk)
                       + |position| * held_rate / 252      (you collect the swap)
                       - turnover cost
    held_rate = longRate if direction>0 else shortRate (the rate for the side you
    hold). This is the whole point of carry: the financing is added to the price
    return because your candles do NOT contain it.

⚠️ HONEST LIMITATIONS (do not over-read the carry numbers):
  1. STATIC SNAPSHOT signal: today's carry direction applied to the whole past.
     Rates moved 2016-2026, so this is an approximation with mild look-ahead.
     A clean test needs HISTORICAL financing/rate data (a real data-build).
  2. The financing accrual is MODELED, not taken from realized swap events.
  So carry here is INDICATIVE. Trend (price-only) remains the validated edge; the
  valuable question is whether carry, even approximate, DIVERSIFIES trend.

Run:  python -m backtest.carry
"""

from pathlib import Path

import numpy as np
import pandas as pd

import backtest.portfolio as tf   # reuse load_basket, metrics, walk_forward, constants

FIN_PATH = Path("data/financing_rates.csv")


def load_financing():
    df = pd.read_csv(FIN_PATH).set_index("instrument")
    return df


def instrument_carry_returns(close, direction, held_rate):
    """Net daily return for ONE instrument held statically in its carry direction."""
    r = close.pct_change()

    vol = r.rolling(tf.VOL_WINDOW).std()
    target_daily = tf.TARGET_VOL_ANN / np.sqrt(tf.TRADING_DAYS)

    size = (target_daily / vol).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    size = size.clip(0, tf.MAX_LEVERAGE)
    raw_pos = direction * size                      # signed, vol-scaled
    pos = raw_pos.shift(1).fillna(0.0)              # execution lag (no lookahead)

    spot = pos * r
    financing = pos.abs() * (held_rate / tf.TRADING_DAYS)   # modeled swap accrual
    turnover = pos.diff().abs().fillna(pos.abs())
    cost = turnover * tf.COST_FRAC
    return (spot + financing - cost).fillna(0.0)


def carry_portfolio(wide, fin):
    cols = {}
    for name in wide.columns:
        if name not in fin.index:
            continue
        d = int(fin.loc[name, "direction"])
        held = fin.loc[name, "longRate"] if d > 0 else fin.loc[name, "shortRate"]
        cols[name] = instrument_carry_returns(wide[name], d, float(held))
    return pd.DataFrame(cols).mean(axis=1)


def run_walk_forward(name, port_ret):
    print(f"\n{name}")
    print(f"{'win':>3} {'from':>11} {'to':>11} {'days':>5} "
          f"{'PF':>6} {'CAGR':>8} {'Sharpe':>7} {'maxDD':>7}")
    res = tf.walk_forward(port_ret)
    for r in res:
        print(f"{r['window']:>3} {r['from']:>11} {r['to']:>11} {r['n']:>5} "
              f"{r['pf']:>6.2f} {r['cagr']:>+8.1%} {r['sharpe']:>7.2f} {r['maxdd']:>7.1%}")
    pfs = [r["pf"] for r in res if r["n"] > 0 and np.isfinite(r["pf"])]
    above = sum(1 for p in pfs if p > 1)
    full = tf.metrics(port_ret.iloc[tf.WARMUP:])
    print(f"   -> PF>1: {above}/{len(pfs)} | median PF {np.median(pfs):.2f} | "
          f"full-period Sharpe {full['sharpe']:.2f} CAGR {full['cagr']:+.1%} "
          f"maxDD {full['maxdd']:.1%}")
    return full, (above, len(pfs))


def report():
    wide = tf.load_basket()
    fin = load_financing()

    print("=" * 74)
    print(f"CARRY + TREND/CARRY COMBO — {wide.shape[1]} instruments, daily, "
          f"{str(wide.index[0].date())} → {str(wide.index[-1].date())}")
    print(f"trend lookback={tf.LOOKBACK}d | carry=STATIC snapshot (INDICATIVE) | "
          f"cost={tf.COST_FRAC*1e4:.0f}bps")
    print("=" * 74)

    trend = tf.portfolio_returns(wide)
    carry = carry_portfolio(wide, fin)
    # 50/50 equal-risk blend of the two daily-return streams
    combo = pd.concat([trend, carry], axis=1).mean(axis=1)

    # correlation of the two return streams (post-warmup) — the diversification test
    sl = slice(tf.WARMUP, None)
    corr = trend.iloc[sl].corr(carry.iloc[sl])

    run_walk_forward("TREND ONLY", trend)
    run_walk_forward("CARRY ONLY  (INDICATIVE — static snapshot, modeled swap)", carry)
    run_walk_forward("COMBO 50/50", combo)

    print(f"\n--- diversification check ---")
    print(f"corr(trend, carry) daily returns = {corr:+.2f}  "
          f"(near 0 or negative = genuinely different bets = the combo should be "
          f"steadier than either alone)")


if __name__ == "__main__":
    report()
