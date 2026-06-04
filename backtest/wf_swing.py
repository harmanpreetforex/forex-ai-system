"""
backtest/wf_swing.py
--------------------------------------------------------------------
Best-effort MECHANICAL backtest of the "swing trading" YouTube video.

IMPORTANT HONESTY NOTE: the video contains NO mechanical strategy — it's trading
philosophy + a sales funnel ("DM me Sunday swings"). The presenter explicitly says
"this is not my exact strategy... that's where my strategy comes in." So the entry
RULES below are MY faithful mechanization of the OBJECTIVE claims in the video,
not his actual (withheld) method. The one genuinely new element vs. prior tests is
STRUCTURE-BASED stops (beyond the recent swing low/high) with an R-multiple target,
instead of fixed 20/40 pips — which is why this needs its own backtester (the pip
engine uses fixed stops).

RULES (daily; fixed textbook params, NOT grid-searched):
  - Trend filter: EMA(50). Long-only if close>EMA, short-only if close<EMA.   ("above my EMA")
  - Entry: breakout of the prior DONCHIAN_N-day high (long) / low (short).     ("trade with the trend/structure")
  - Stop : beyond the recent SWING_N-day swing low (long) / high (short).      ("stop below the zone, not 27 pips")
  - Target: entry +/- R_MULT * risk, where risk = |entry - stop|.              (his "1:2")
  - One position at a time. Spread cost charged. Pessimistic: if stop & target
    are both touched in one bar, assume STOP first (same rule as engine.py).
  - No lookahead: signal at bar i (close known) fills at bar i+1 OPEN.

Bar = SAME walk-forward bar as everything else: PF>1 consistency across non-
overlapping out-of-sample windows.

Run:  python -m backtest.wf_swing
"""

import statistics as st
import pandas as pd

from backtest.engine import load_data, get_pip

EMA_TREND   = 50
DONCHIAN_N  = 20      # breakout lookback (structure high/low)
SWING_N     = 10      # swing low/high lookback for the stop
R_MULT      = 2.0     # target = R_MULT x risk
WARMUP      = EMA_TREND + DONCHIAN_N + 5
TEST_SIZE   = 400     # ~1.5 trading years of daily bars per window

SPREAD = {            # round-trip spread in pips
    "EUR_USD": 1.6, "GBP_USD": 1.9, "USD_JPY": 1.7,
    "AUD_USD": 1.5, "USD_CAD": 2.0, "USD_CHF": 2.0,
}
PAIRS = [(p, f"data/basket_daily/{p}.csv") for p in SPREAD]


def add_indicators(df):
    df = df.copy()
    df["ema"] = df["close"].ewm(span=EMA_TREND, adjust=False).mean()
    # prior-N channel (shift 1 so the current bar isn't in its own breakout window)
    df["donch_hi"] = df["high"].rolling(DONCHIAN_N).max().shift(1)
    df["donch_lo"] = df["low"].rolling(DONCHIAN_N).min().shift(1)
    df["swing_lo"] = df["low"].rolling(SWING_N).min()    # info as-of bar i
    df["swing_hi"] = df["high"].rolling(SWING_N).max()
    return df


def backtest(df, pair, spread):
    pip = get_pip(pair)
    df = add_indicators(df)
    trades, open_t, pending = [], None, None

    for i in range(len(df)):
        c = df.iloc[i]

        # 1) fill a pending entry at this bar's OPEN
        if pending and open_t is None:
            entry = c["open"]
            d = pending["dir"]
            stop = pending["stop"]
            risk = abs(entry - stop)
            if risk <= 0:
                pending = None
            else:
                tp = entry + R_MULT * risk if d == "BUY" else entry - R_MULT * risk
                open_t = {"direction": d, "entry": entry, "entry_time": c["time"],
                          "sl": stop, "tp": tp}
                pending = None

        # 2) manage an open position against THIS bar's high/low (stop-first)
        if open_t:
            d = open_t["direction"]
            hit_sl = (c["low"] <= open_t["sl"]) if d == "BUY" else (c["high"] >= open_t["sl"])
            hit_tp = (c["high"] >= open_t["tp"]) if d == "BUY" else (c["low"] <= open_t["tp"])
            exit_px = None
            if hit_sl:
                exit_px = open_t["sl"]
            elif hit_tp:
                exit_px = open_t["tp"]
            if exit_px is not None:
                pnl = (exit_px - open_t["entry"]) / pip if d == "BUY" else \
                      (open_t["entry"] - exit_px) / pip
                open_t["pnl"] = pnl - spread
                trades.append(open_t); open_t = None

        # 3) look for a new signal on this CLOSE (fills next open)
        if open_t is None and pending is None:
            if pd.isna(c["donch_hi"]) or pd.isna(c["ema"]):
                continue
            uptrend = c["close"] > c["ema"]
            downtrend = c["close"] < c["ema"]
            if uptrend and c["close"] > c["donch_hi"] and not pd.isna(c["swing_lo"]):
                pending = {"dir": "BUY", "stop": c["swing_lo"]}
            elif downtrend and c["close"] < c["donch_lo"] and not pd.isna(c["swing_hi"]):
                pending = {"dir": "SELL", "stop": c["swing_hi"]}

    return trades


def pf_of(trades):
    pnls = [t["pnl"] for t in trades]
    if not pnls:
        return None, 0
    gw = sum(p for p in pnls if p > 0)
    gl = -sum(p for p in pnls if p < 0)
    return (gw / gl if gl > 0 else float("inf")), len(pnls)


def walk_forward(df, pair, spread):
    n = len(df)
    out, start = [], WARMUP
    while start + TEST_SIZE <= n:
        seg = df.iloc[max(0, start - WARMUP):start + TEST_SIZE].reset_index(drop=True)
        trades = backtest(seg, pair, spread)
        cutoff = pd.to_datetime(df.iloc[start]["time"])
        test = [t for t in trades if pd.to_datetime(t["entry_time"]) >= cutoff]
        pf, n_tr = pf_of(test)
        if pf is not None:
            out.append((pf, n_tr))
        start += TEST_SIZE
    return out


def main():
    print("=" * 70)
    print("SWING (daily breakout + EMA trend + structure stop + 2R target)")
    print("faithful mechanization of the video's OBJECTIVE claims — see header")
    print("=" * 70)
    all_pfs, grand = [], 0
    for pair, path in PAIRS:
        try:
            df = load_data(path)
        except FileNotFoundError:
            print(f"  {pair:<9} — no data ({path})"); continue
        res = walk_forward(df, pair, SPREAD[pair])
        pfs = [pf for pf, _ in res if pf != float("inf")]
        n = sum(nt for _, nt in res)
        grand += n
        all_pfs += pfs
        if pfs:
            above = sum(1 for p in pfs if p > 1)
            wins = " ".join(f"{p:.2f}" for p in pfs)
            print(f"  {pair:<9} windows {len(pfs)} | PF>1 {above}/{len(pfs)} | "
                  f"med {st.median(pfs):.2f} | trades {n:>4} | [{wins}]")
        else:
            print(f"  {pair:<9} — no trades (n={n})")
    if all_pfs:
        above = sum(1 for p in all_pfs if p > 1)
        print(f"\n  AGGREGATE: {len(all_pfs)} windows | PF>1 {above}/{len(all_pfs)} "
              f"| median PF {st.median(all_pfs):.2f} | total trades {grand}")
        verdict = "PASSES" if above >= len(all_pfs) * 0.7 else \
                  "MARGINAL" if above > len(all_pfs) / 2 else "FAILS"
        print(f"  VERDICT: {verdict} the bar.")


if __name__ == "__main__":
    main()
