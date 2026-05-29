"""RSI mean-reversion strategy.

Fades extremes: BUY when RSI crosses back UP out of oversold, SELL when it
crosses back DOWN out of overbought. "Cross back out" (not "is below 30")
gives one entry per swing, not one per candle.

Engine contract (confirmed by tracing): the engine calls
    strategy_fn(window, pip)
where `window` is the data SO FAR (current candle = last row) and `pip` is the
pip size (0.0001, or 0.01 for JPY). There is NO integer index:
    now  = window.iloc[-1]
    prev = window.iloc[-2]

Returns "BUY", "SELL", or None. Pure pandas — no new dependency.
"""

import pandas as pd

PERIOD = 14
OVERSOLD = 30
OVERBOUGHT = 70


def compute_rsi(prices: pd.Series, period: int = PERIOD) -> pd.Series:
    """Wilder's RSI. No lookahead: RSI at row k uses only closes <= k."""
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def strategy_fn(df, pip):
    # Need period+1 candles to have a valid RSI on both current and previous.
    if len(df) < PERIOD + 1:
        return None

    rsi = compute_rsi(df["close"])
    prev = rsi.iloc[-2]   # previous candle's RSI
    now = rsi.iloc[-1]    # current candle's RSI
    if pd.isna(prev) or pd.isna(now):
        return None

    if prev < OVERSOLD and now >= OVERSOLD:       # bounced up out of oversold
        return "BUY"
    if prev > OVERBOUGHT and now <= OVERBOUGHT:   # rolled down out of overbought
        return "SELL"
    return None