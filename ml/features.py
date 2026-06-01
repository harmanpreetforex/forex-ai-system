"""
ml/features.py
--------------------------------------------------------------------
Month 3, Session 1 deliverable (part 3 of 3): FEATURE ENGINEERING.

The tracker's framing is the thing to keep in front of you while reading this:
raw price+SMA has NO edge on H1 majors. These features are all derived from the
SAME OHLC, so they may inherit the same edgelessness. This module exists to give
that question ONE disciplined, leak-free shot -- not to keep adding features
until something fits.

THE ONE RULE: every feature at row i uses ONLY candles <= i.
--------------------------------------------------------------------
A feature that peeks at candle i+1 leaks the label's future into the inputs and
manufactures an edge that dies live. So:
  * Use .rolling()/.ewm()/.diff()/.shift(+k) only (all backward-looking).
  * NEVER .shift(-k), NEVER center=True, NEVER a forward fill from the future.
  * The current candle's CLOSE is known at decision time (that's when the engine
    consults the strategy), so close[i] is allowed; open[i+1] is the fill, not a
    feature.

The feature families (deliberately the tracker's list, nothing exotic):
  returns          -- 1/3/6/12-candle log returns (momentum at several scales)
  distance-from-MA -- close vs SMA20/SMA50 in pips and in ATR units (where are
                      we relative to trend, scale-free)
  rsi              -- the Day-10 RSI (reuses strategies/rsi_reversal.compute_rsi)
  volatility       -- ATR(14) in pips, and rolling std of returns (regime)
  time-of-day      -- hour as cyclical sin/cos (NOT a raw int: hour 23 and 0 are
                      adjacent, an int makes them maximally far apart). Captures
                      session structure WITHOUT the Day 14 session-filter trap --
                      the model may learn to ignore it; we don't hand-pick hours.

Leading rows with NaN (indicators not warmed) are the caller's job to drop,
jointly with the label's unlabelable tail -- see ml/build_dataset.py.
--------------------------------------------------------------------
"""
import numpy as np
import pandas as pd

from strategies.rsi_reversal import compute_rsi   # reuse the Day-10 Wilder RSI


def _atr(df, period=14):
    """Average True Range in PRICE units (backward-looking). True range uses the
    prior close, so row i needs close[i-1] -- still past-only."""
    h, l, c = df["high"], df["low"], df["close"]
    prev_close = c.shift(1)
    tr = pd.concat([
        h - l,
        (h - prev_close).abs(),
        (l - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def make_features(df, pair):
    """Return a DataFrame of past-only features aligned to df.index.

    pip-scaling makes distance/vol features comparable across EUR/GBP/JPY (JPY
    quotes ~150, EUR ~1.08 -- raw price diffs would be on wildly different scales
    and a single model couldn't pool pairs). ATR-relative features go one better:
    they're unit-free, so 'how far from the MA in *volatility* terms' means the
    same thing in every regime.
    """
    pip = 0.01 if "JPY" in pair.upper() else 0.0001
    close = df["close"]
    feats = pd.DataFrame(index=df.index)

    # --- returns (momentum at several horizons) ------------------------------
    logc = np.log(close)
    for k in (1, 3, 6, 12):
        feats[f"ret_{k}"] = logc.diff(k)

    # --- volatility / regime -------------------------------------------------
    atr = _atr(df, 14)
    feats["atr_pips"] = atr / pip
    feats["ret_std_12"] = feats["ret_1"].rolling(12).std()

    # --- distance from moving averages (pips AND atr-units) -------------------
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    feats["dist_sma20_pips"] = (close - sma20) / pip
    feats["dist_sma50_pips"] = (close - sma50) / pip
    feats["dist_sma20_atr"] = (close - sma20) / atr     # unit-free
    feats["sma20_50_spread_pips"] = (sma20 - sma50) / pip

    # --- RSI (reuse, do not re-derive) ---------------------------------------
    feats["rsi_14"] = compute_rsi(close)

    # --- time of day (cyclical, not categorical) -----------------------------
    # PRECONDITION: timestamps are UTC (oanda_pipeline.py guarantees this).
    if "time" in df.columns:
        hour = pd.to_datetime(df["time"]).dt.hour
    else:
        hour = pd.to_datetime(df.index).hour
    feats["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    feats["hour_cos"] = np.cos(2 * np.pi * hour / 24)

    return feats


FEATURE_COLUMNS = [
    "ret_1", "ret_3", "ret_6", "ret_12",
    "atr_pips", "ret_std_12",
    "dist_sma20_pips", "dist_sma50_pips", "dist_sma20_atr", "sma20_50_spread_pips",
    "rsi_14",
    "hour_sin", "hour_cos",
]


if __name__ == "__main__":
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, ROOT)
    from backtest.engine import load_data

    df = load_data(os.path.join(ROOT, "data", "eurusd_1h_2y.csv"))
    X = make_features(df, "EUR_USD")
    print(f"EUR/USD features: {X.shape[0]} rows x {X.shape[1]} cols")
    print(f"  columns: {list(X.columns)}")
    warm = X.dropna()
    print(f"  warm-up NaN rows dropped from front: {len(X) - len(warm)} "
          f"(SMA50 needs ~50 candles)")
    assert list(X.columns) == FEATURE_COLUMNS, "FEATURE_COLUMNS out of sync"
    # Leakage smoke test: features must not change if FUTURE rows are deleted.
    cut = 8000
    X_full = make_features(df, "EUR_USD").iloc[:cut]
    X_trunc = make_features(df.iloc[:cut], "EUR_USD")
    pd.testing.assert_frame_equal(X_full, X_trunc)
    print("  leakage guard: OK (features at row i are unchanged by deleting rows > i)")
