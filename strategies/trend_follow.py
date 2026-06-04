"""
strategies/trend_follow.py
--------------------------------------------------------------------
Time-series momentum signal — the canonical managed-futures / CTA trend rule.

The signal is deliberately DUMB and has ONE parameter (lookback):

    +1 (long)  if today's close is ABOVE its value `lookback` days ago
    -1 (short) if today's close is BELOW its value `lookback` days ago

That's it. "Has this market gone up or down over the last ~5 months?" — bet it
continues. This is the rule with the strongest out-of-sample academic evidence
(Moskowitz, Ooi & Pedersen 2012, "Time Series Momentum"). The edge does NOT come
from this signal being clever — it comes from applying it across many uncorrelated
markets with volatility-scaled sizing (both handled in backtest/portfolio.py).

Vectorized (returns a position series), because trend-following is evaluated as a
continuously-held portfolio in return-space, NOT as discrete SL/TP trades. It does
NOT plug into the pip engine — it plugs into the portfolio backtester. Keeping it
here preserves the convention: every idea is a file in strategies/.

NO LOOKAHEAD here: the signal at row t uses only closes up to and including t.
The 1-day execution lag (you can't trade on a close until the next bar) is applied
once, centrally, in portfolio.py — not duplicated per strategy.
"""

import numpy as np


def trend_signal(close, lookback=100):
    """+1 / -1 / 0 direction series from a close-price series.

    Returns 0 until `lookback` bars exist (no signal before there's history),
    so the warm-up region contributes nothing rather than guessing.
    """
    mom = close - close.shift(lookback)
    sig = np.sign(mom)          # +1, -1, or 0 (exactly flat, rare)
    return sig.fillna(0.0)
