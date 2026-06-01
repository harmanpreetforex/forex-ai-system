"""
OANDA Data Pipeline — multi-pair, paginated
EUR/USD · GBP/USD · USD/JPY  ·  1H  ·  multi-year history
Run locally from the repo root:  python data/oanda_pipeline.py

Day 10 extension of the Day 4 pipeline:
  - paginates past OANDA's ~5000-candle/request cap (from + count, walk the cursor)
  - pulls multiple instruments in one run, one CSV per pair
  - charts only a RECENT window (plotting 12k+ candles is unreadable and slow)

The CSV schema (datetime index + open/high/low/close/volume) is UNCHANGED, so
backtest/engine.py load_data() reads the new files without any edits.
"""

import time
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from dotenv import load_dotenv

# ── Config ───────────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

API_TOKEN  = os.getenv("OANDA_API_TOKEN")
ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID")
BASE_URL   = "https://api-fxpractice.oanda.com"   # practice environment

INSTRUMENTS       = ["EUR_USD", "GBP_USD", "USD_JPY"]
GRANULARITY       = "H1"
YEARS             = 2        # history depth. 2 = floor (≈260 trades). 3 is fine.
PRICE             = "M"      # mid prices; spread is modeled later in the backtester
MAX_PER_REQ       = 5000     # OANDA hard cap per candles request
CHART_RECENT_DAYS = 30       # only plot this tail; full history is useless as candles
OUT_DIR           = Path("data")

if not API_TOKEN or not ACCOUNT_ID:
    raise SystemExit("Missing OANDA_API_TOKEN or OANDA_ACCOUNT_ID — check your .env file.")

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type":  "application/json",
}

GRAN_LABEL = {"H1": "1h", "H4": "4h", "M15": "15m", "M5": "5m", "D": "1d"}.get(
    GRANULARITY, GRANULARITY.lower()
)


# ── Fetch (paginated) ──────────────────────────────────────────────────────────
def fetch_candles(instrument, granularity, start, end):
    """Walk forward in <=MAX_PER_REQ chunks until we reach `end` or run out of data.

    Uses from + count (NOT from + to) so each request is deterministic and always
    returns a full chunk when data exists. The cursor advances to just past the
    last candle of each batch; to_dataframe() then dedupes any 1-candle overlap.

    Termination: empty batch, a short batch (< MAX_PER_REQ → no more data), or the
    last candle passing `end`.
    """
    url = f"{BASE_URL}/v3/instruments/{instrument}/candles"
    raw = []
    cursor = start
    req = 0

    while cursor < end:
        params = {
            "granularity": granularity,
            "from":  cursor.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "count": MAX_PER_REQ,
            "price": PRICE,
        }
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        batch = resp.json().get("candles", [])
        req += 1

        if not batch:
            break

        raw.extend(batch)
        last_time = pd.to_datetime(batch[-1]["time"])  # tz-aware (UTC)
        print(f"    req {req:>2}: +{len(batch):>4} candles  (through {last_time:%Y-%m-%d %H:%M})")

        # short batch = end of available data; or we've caught up to `end`
        if len(batch) < MAX_PER_REQ or last_time >= end:
            break

        cursor = last_time + timedelta(seconds=1)  # +1s avoids re-fetching the same candle
        time.sleep(0.1)                            # be polite to the API

    return raw


# ── Parse → DataFrame ──────────────────────────────────────────────────────────
def to_dataframe(candles, end):
    """Same schema as Day 4: naive-UTC datetime index, OHLCV, complete candles only."""
    rows = []
    for c in candles:
        if not c.get("complete", True):
            continue                      # skip the still-forming candle
        ts = pd.to_datetime(c["time"])
        if ts > end:
            continue
        mid = c["mid"]
        rows.append({
            "datetime": ts,
            "open":   float(mid["o"]),
            "high":   float(mid["h"]),
            "low":    float(mid["l"]),
            "close":  float(mid["c"]),
            "volume": int(c["volume"]),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df.set_index("datetime", inplace=True)
    df = df[~df.index.duplicated(keep="first")]   # drop pagination overlap (1 candle/req)
    df.sort_index(inplace=True)
    df.index = df.index.tz_localize(None)         # naive UTC — identical to Day 4
    return df


# ── Plot (recent window only) ───────────────────────────────────────────────────
def plot_recent(df, instrument, days, gran_label):
    """Render only the last `days` of data — same dark theme as Day 4, but bounded
    so we never try to draw thousands of candle rectangles."""
    recent = df[df.index >= df.index[-1] - timedelta(days=days)]
    if len(recent) < 2:
        print("    (not enough recent candles to chart)")
        return

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(18, 10),
        gridspec_kw={"height_ratios": [3, 1]},
        facecolor="#0d1117",
    )
    for ax in (ax1, ax2):
        ax.set_facecolor("#0d1117")
        ax.tick_params(colors="#8b949e", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#21262d")

    width_days = (recent.index[1] - recent.index[0]).total_seconds() / 86400 * 0.6

    for ts, row in recent.iterrows():
        x    = mdates.date2num(ts)
        bull = row["close"] >= row["open"]
        col  = "#26a641" if bull else "#f85149"
        ax1.plot([x, x], [row["low"], row["high"]], color=col, linewidth=0.7, zorder=2)
        body_h = abs(row["close"] - row["open"]) or 0.00001
        ax1.add_patch(Rectangle(
            (x - width_days / 2, min(row["open"], row["close"])),
            width_days, body_h, color=col, zorder=3,
        ))

    sma20 = recent["close"].rolling(20).mean()
    ax1.plot(mdates.date2num(recent.index.to_pydatetime()),
             sma20, color="#58a6ff", linewidth=1.2, label="SMA 20", zorder=4)

    # JPY pairs quote to ~3 dp, USD pairs to ~5 — pick a sane format per scale
    fmt = "%.3f" if recent["close"].iloc[-1] > 10 else "%.5f"
    ax1.set_xlim(mdates.date2num(recent.index[0]), mdates.date2num(recent.index[-1]))
    ax1.yaxis.set_major_formatter(plt.FormatStrFormatter(fmt))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax1.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))
    ax1.set_title(
        f"{instrument.replace('_', '/')}  ·  {gran_label.upper()}  ·  "
        f"Last {days} Days  ·  {len(recent)} Candles",
        color="#e6edf3", fontsize=13, fontweight="bold", pad=12,
    )
    ax1.set_ylabel("Price", color="#8b949e", fontsize=9)
    ax1.legend(facecolor="#161b22", edgecolor="#21262d", labelcolor="#8b949e", fontsize=8)
    ax1.grid(axis="y", color="#21262d", linewidth=0.5)

    xs   = mdates.date2num(recent.index.to_pydatetime())
    cols = ["#26a641" if c >= o else "#f85149"
            for c, o in zip(recent["close"], recent["open"])]
    ax2.bar(xs, recent["volume"], width=width_days, color=cols, alpha=0.8)
    ax2.set_xlim(ax1.get_xlim())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax2.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))
    ax2.set_ylabel("Volume", color="#8b949e", fontsize=9)
    ax2.grid(axis="y", color="#21262d", linewidth=0.5)

    plt.tight_layout(rect=[0, 0.03, 1, 1])
    tag = instrument.replace("_", "").lower()
    chart_path = OUT_DIR / f"{tag}_{gran_label}_recent{days}d_chart.png"
    plt.savefig(chart_path, dpi=150, bbox_inches="tight", facecolor="#0d1117")
    plt.close()
    print(f"  → Chart: {chart_path}")


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    OUT_DIR.mkdir(exist_ok=True)
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=YEARS * 365)

    for inst in INSTRUMENTS:
        print(f"\nFetching {inst} {GRANULARITY} — {YEARS}y "
              f"({start:%Y-%m-%d} → {end:%Y-%m-%d})")
        raw = fetch_candles(inst, GRANULARITY, start, end)
        df  = to_dataframe(raw, end)

        if df.empty:
            print(f"  ⚠ no candles returned for {inst}")
            continue

        tag      = inst.replace("_", "").lower()              # EUR_USD -> eurusd
        csv_path = OUT_DIR / f"{tag}_{GRAN_LABEL}_{YEARS}y.csv"
        df.to_csv(csv_path)

        span_days = (df.index[-1] - df.index[0]).days
        print(f"  → {len(df)} candles  ({df.index[0]} → {df.index[-1]}, ~{span_days}d)")
        print(f"  → CSV:   {csv_path}")
        plot_recent(df, inst, CHART_RECENT_DAYS, GRAN_LABEL)

    print(f"\n✅  Done — {len(INSTRUMENTS)} instruments, {YEARS}y of {GRANULARITY}.")


if __name__ == "__main__":
    main()