"""
strategies/trend_pullback.py
--------------------------------------------------------------------
Trend + pullback — the testable, internally-consistent version of the popular
"trend trading with stochastic/RSI" idea.

The trick that resolves the contradiction in the marketing description (trend-
follow vs. overbought/oversold reversion): the TREND decides DIRECTION, the
OSCILLATOR only decides TIMING — you buy temporary DIPS inside an uptrend, so the
oscillator joins the trend at a better price instead of fighting it.

RULES (fixed textbook params, NOT grid-searched — every knob is a curve-fit risk):
  - Trend filter: 200-period SMA of close.
        close > SMA200  -> uptrend  -> LONGS ONLY
        close < SMA200  -> downtrend -> SHORTS ONLY
  - Timing: slow stochastic %K (14, smoothed 3).
        uptrend  : BUY  when %K crosses back UP   above 20 (was oversold, rebounding)
        downtrend: SELL when %K crosses back DOWN below 80 (was overbought, rolling over)
  "Cross back out" (not merely "is below 20") = one entry per swing, not one per bar.

Engine contract (same as sma_crossover / rsi_reversal): strategy_fn(window, pip)
returns "BUY" | "SELL" | None; `window` is all data up to and including now, so
the last row is the current candle. No lookahead — every value uses closes/highs/
lows <= now. Exits (fixed 20/40 SL-TP) are handled by the engine, not here.
"""

import pandas as pd

SMA_TREND   = 200
STOCH_K     = 14
STOCH_SMOOTH = 3
OVERSOLD    = 20
OVERBOUGHT  = 80


def slow_stoch_k(df, k=STOCH_K, smooth=STOCH_SMOOTH):
    """Slow %K = 3-period SMA of raw %K. No lookahead: row n uses bars <= n."""
    low_n  = df["low"].rolling(k).min()
    high_n = df["high"].rolling(k).max()
    rng = (high_n - low_n).replace(0, pd.NA)        # avoid 0/0 on flat ranges
    raw_k = 100 * (df["close"] - low_n) / rng
    return raw_k.rolling(smooth).mean()


def strategy_fn(window, pip):
    # need the 200-SMA plus the stochastic warm-up, plus one prior bar for a cross
    if len(window) < SMA_TREND + 1:
        return None

    sma = window["close"].rolling(SMA_TREND).mean()
    k = slow_stoch_k(window)

    close_now = window["close"].iloc[-1]
    sma_now   = sma.iloc[-1]
    k_prev, k_now = k.iloc[-2], k.iloc[-1]
    if pd.isna(sma_now) or pd.isna(k_prev) or pd.isna(k_now):
        return None

    uptrend   = close_now > sma_now
    downtrend = close_now < sma_now

    # buy the dip rebounding, but only in an uptrend
    if uptrend and k_prev < OVERSOLD and k_now >= OVERSOLD:
        return "BUY"
    # sell the rally rolling over, but only in a downtrend
    if downtrend and k_prev > OVERBOUGHT and k_now <= OVERBOUGHT:
        return "SELL"
    return None
