# scratch_rsi_check.py — throwaway diagnostic, delete after
import os, sys
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from backtest.engine import load_data
from strategies.rsi_reversal import compute_rsi

df = load_data(os.path.join(ROOT, "data", "eurusd_1h_30d.csv"))
print("columns:", list(df.columns))

rsi = compute_rsi(df["close"], 14)
print(f"RSI valid (non-NaN): {rsi.notna().sum()} / {len(rsi)}")
print(f"RSI min={rsi.min():.1f}  max={rsi.max():.1f}")
print(f"candles oversold  (<30): {(rsi < 30).sum()}")
print(f"candles overbought(>70): {(rsi > 70).sum()}")

# the exact cross-back events the strategy fires on
prev, now = rsi.shift(1), rsi
buys  = ((prev < 30) & (now >= 30)).sum()
sells = ((prev > 70) & (now <= 70)).sum()
print(f"BUY  signals (cross up out of 30):   {buys}")
print(f"SELL signals (cross down out of 70): {sells}")