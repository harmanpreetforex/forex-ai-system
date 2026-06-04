"""
strategies/liquidity_sweep.py
--------------------------------------------------------------------
The ONE falsifiable kernel of the ICT / "Smart Money Concepts" day-trading video:
the LIQUIDITY SWEEP REVERSAL (a.k.a. stop-hunt / "Turtle Soup").

The full video method is NOT mechanically testable: it needs 1m/5m data we don't
have, and it stacks 4+ discretionary, post-hoc "confluences" (FVG / IFVG / breaker
block / order block / equilibrium / 79% Fib) chosen by eye AFTER the move, with the
real definitions outsourced to a paid course. An "A or B or C or D, pick whichever
fits" rule is infinitely flexible = unfalsifiable. So we test the objective ESSENCE
of his steps 1-2 instead:

  - "draw on liquidity"  -> a prior N-bar high/low (the key level)
  - "key level gets hit" -> price SWEEPS it (new extreme beyond the level)
  - "reversal"           -> but the bar CLOSES BACK INSIDE the level (failed breakout)
  -> enter the reversal, stop beyond the sweep extreme, target the OPPOSITE level
     (his "exit at the other draws on liquidity").

This compresses his discretionary reversal+continuation confluences into the single
objective event that underlies them. It is a FAITHFUL PROXY for the kernel, not his
full (untestable) method. No lookahead: the level uses bars < current; the signal is
read at the current close and filled at the next bar's open by the backtester.

Returns a DataFrame with columns: dir (+1/-1/0), stop, target — one row per bar.
"""

import numpy as np
import pandas as pd

LOOKBACK = 20      # bars defining the "draw on liquidity" level


def signals(df, n=LOOKBACK):
    high, low, close = df["high"], df["low"], df["close"]
    prior_hi = high.rolling(n).max().shift(1)     # level known BEFORE this bar
    prior_lo = low.rolling(n).min().shift(1)

    swept_hi = (high > prior_hi) & (close < prior_hi)   # ran the highs, closed back below -> short
    swept_lo = (low < prior_lo) & (close > prior_lo)    # ran the lows, closed back above  -> long

    direction = np.where(swept_hi, -1, np.where(swept_lo, 1, 0))
    stop   = np.where(swept_hi, high, np.where(swept_lo, low, np.nan))
    target = np.where(swept_hi, prior_lo, np.where(swept_lo, prior_hi, np.nan))

    return pd.DataFrame({"dir": direction, "stop": stop, "target": target}, index=df.index)
