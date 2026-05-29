"""
strategies/sma_crossover.py
--------------------------------------------------------------------
A simple moving-average crossover strategy.

This file holds the IDEA being tested. The engine doesn't know or care
what's inside here - it just calls strategy_fn(history, pip) on every
candle and reacts to what you return.

Contract: return "BUY", "SELL", or None.
  history -> a DataFrame of every candle up to and including "now"
  pip     -> the pip size for this pair (you may not need it here)
--------------------------------------------------------------------
"""

FAST = 10   # fast moving-average window (number of candles)
SLOW = 30   # slow moving-average window


def strategy_fn(history, pip):
    # Need enough candles to compute the slow MA, plus one bar back to spot a cross
    if len(history) < SLOW + 1:
        return None

    close = history["close"]
    fast_ma = close.rolling(FAST).mean()
    slow_ma = close.rolling(SLOW).mean()

    prev_fast, prev_slow = fast_ma.iloc[-2], slow_ma.iloc[-2]
    curr_fast, curr_slow = fast_ma.iloc[-1], slow_ma.iloc[-1]

    # Fast MA crosses ABOVE slow MA -> momentum turning up -> go long
    if prev_fast <= prev_slow and curr_fast > curr_slow:
        return "BUY"

    # Fast MA crosses BELOW slow MA -> momentum turning down -> go short
    if prev_fast >= prev_slow and curr_fast < curr_slow:
        return "SELL"

    return None