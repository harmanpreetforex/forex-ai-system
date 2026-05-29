"""
Day 4 — OANDA Data Pipeline
EUR/USD · 1H · Last 30 Days
Run this locally: python oanda_pipeline.py
"""

import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from datetime import datetime, timezone, timedelta
import os
from pathlib import Path
from dotenv import load_dotenv

# ── Config ───────────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

API_TOKEN   = os.getenv("OANDA_API_TOKEN")
ACCOUNT_ID  = os.getenv("OANDA_ACCOUNT_ID")
BASE_URL    = "https://api-fxpractice.oanda.com"   # practice environment
INSTRUMENT  = "EUR_USD"
GRANULARITY = "H1"
DAYS        = 30
if not API_TOKEN or not ACCOUNT_ID:
    raise SystemExit("Missing OANDA_API_TOKEN or OANDA_ACCOUNT_ID — check your .env file.")

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type":  "application/json",
}

# ── Fetch ─────────────────────────────────────────────────────────────────────
end   = datetime.now(timezone.utc)
start = end - timedelta(days=DAYS)

params = {
    "granularity": GRANULARITY,
    "from":  start.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "to":    end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "price": "M",      # mid prices
}

url = f"{BASE_URL}/v3/instruments/{INSTRUMENT}/candles"
print(f"Fetching {INSTRUMENT} {GRANULARITY} — last {DAYS} days …")
resp = requests.get(url, headers=HEADERS, params=params)
resp.raise_for_status()
candles = resp.json().get("candles", [])
print(f"  → {len(candles)} candles received")

# ── Parse → DataFrame ─────────────────────────────────────────────────────────
rows = []
for c in candles:
    if not c.get("complete", True):
        continue
    mid = c["mid"]
    rows.append({
        "datetime": pd.to_datetime(c["time"]),
        "open":     float(mid["o"]),
        "high":     float(mid["h"]),
        "low":      float(mid["l"]),
        "close":    float(mid["c"]),
        "volume":   int(c["volume"]),
    })

df = pd.DataFrame(rows)
df.set_index("datetime", inplace=True)
df.index = df.index.tz_localize(None)

# ── Save CSV ──────────────────────────────────────────────────────────────────
csv_path = "data/eurusd_1h_30d.csv"
df.to_csv(csv_path)
print(f"  → CSV saved: {csv_path}  ({len(df)} rows)")

# ── Plot ──────────────────────────────────────────────────────────────────────
fig, (ax1, ax2) = plt.subplots(
    2, 1, figsize=(18, 10),
    gridspec_kw={"height_ratios": [3, 1]},
    facecolor="#0d1117"
)
for ax in (ax1, ax2):
    ax.set_facecolor("#0d1117")
    ax.tick_params(colors="#8b949e", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#21262d")

width_days = (df.index[1] - df.index[0]).total_seconds() / 86400 * 0.6

for ts, row in df.iterrows():
    x    = mdates.date2num(ts)
    bull = row["close"] >= row["open"]
    col  = "#26a641" if bull else "#f85149"
    ax1.plot([x, x], [row["low"], row["high"]], color=col, linewidth=0.7, zorder=2)
    body_h = abs(row["close"] - row["open"]) or 0.00001
    rect = Rectangle(
        (x - width_days / 2, min(row["open"], row["close"])),
        width_days, body_h, color=col, zorder=3
    )
    ax1.add_patch(rect)

df["sma20"] = df["close"].rolling(20).mean()
ax1.plot(
    mdates.date2num(df.index.to_pydatetime()),
    df["sma20"], color="#58a6ff", linewidth=1.2, label="SMA 20", zorder=4
)

ax1.set_xlim(mdates.date2num(df.index[0]), mdates.date2num(df.index[-1]))
ax1.yaxis.set_major_formatter(plt.FormatStrFormatter("%.5f"))
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
ax1.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))
ax1.set_title(
    f"EUR/USD  ·  1H  ·  Last {DAYS} Days  ·  {len(df)} Candles",
    color="#e6edf3", fontsize=13, fontweight="bold", pad=12
)
ax1.set_ylabel("Price", color="#8b949e", fontsize=9)
ax1.legend(facecolor="#161b22", edgecolor="#21262d", labelcolor="#8b949e", fontsize=8)
ax1.grid(axis="y", color="#21262d", linewidth=0.5)

xs   = mdates.date2num(df.index.to_pydatetime())
cols = ["#26a641" if c >= o else "#f85149"
        for c, o in zip(df["close"], df["open"])]
ax2.bar(xs, df["volume"], width=width_days, color=cols, alpha=0.8)
ax2.set_xlim(ax1.get_xlim())
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
ax2.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))
ax2.set_ylabel("Volume", color="#8b949e", fontsize=9)
ax2.grid(axis="y", color="#21262d", linewidth=0.5)

pr = df["high"].max() - df["low"].min()
fig.text(0.01, 0.01,
    f"Open: {df['open'].iloc[0]:.5f}  Close: {df['close'].iloc[-1]:.5f}  "
    f"High: {df['high'].max():.5f}  Low: {df['low'].min():.5f}  Range: {pr:.5f}",
    color="#8b949e", fontsize=8, va="bottom")

plt.tight_layout(rect=[0, 0.03, 1, 1])
chart_path = "data/eurusd_1h_30d_chart.png"
plt.savefig(chart_path, dpi=150, bbox_inches="tight", facecolor="#0d1117")
print(f"  → Chart saved: {chart_path}")
plt.close()

print(f"\n✅  Done  |  {len(df)} candles  |  {df.index[0]} → {df.index[-1]}")