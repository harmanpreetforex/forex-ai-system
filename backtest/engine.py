"""
backtest/engine.py
--------------------------------------------------------------------
The backtesting ENGINE. It knows NOTHING about any specific strategy.
It just walks your data candle by candle and calls whatever strategy
function you hand it. This file should rarely change once it works -
you build new ideas by writing new files in strategies/, not by
editing this one.

The engine works entirely in PIPS. It knows nothing about money,
account currency, or position size - that conversion lives in the
runner (run_backtest.py), so the engine stays clean and reusable.

Day 9-deep+ : run_backtest() gained `allowed_entry_hours`, an OPTIONAL
entry-hour filter (an execution constraint, parallel to spread/risk --
NOT a strategy change). Entries are gated to the given UTC hours; exits
are NEVER gated (you don't want the clock to trap an open position).
--------------------------------------------------------------------
"""
import pandas as pd
from backtest.results import max_drawdown   # absolute import, matches run_backtest.py


def _close(trade, exit_price, exit_time, pip, spread_pips, reason):
    if trade["direction"] == "BUY":
        pnl = (exit_price - trade["entry"]) / pip
    else:
        pnl = (trade["entry"] - exit_price) / pip
    trade["exit"] = exit_price
    trade["exit_time"] = exit_time
    trade["pnl"] = pnl - spread_pips          # spread still nets out here
    trade["exit_reason"] = reason             # "sl" | "tp" | "signal"
    trade["closed"] = True
    return trade

def load_data(path):
    """Read the OHLC CSV from your Day 4 pipeline into a clean DataFrame."""
    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]

    # Find whatever the time column is called, normalise it to 'time'
    time_col = next(
        (c for c in df.columns if c in ("time", "datetime", "date", "timestamp")),
        None,
    )
    if time_col:
        df[time_col] = pd.to_datetime(df[time_col])
        df = df.sort_values(time_col).reset_index(drop=True)
        df = df.rename(columns={time_col: "time"})
    return df


def get_pip(pair):
    """JPY pairs use 0.01 as a pip; everything else uses 0.0001."""
    return 0.01 if "JPY" in pair.upper() else 0.0001


def open_new_trade(signal, candle, pip, sl_pips, tp_pips):
    entry = candle["open"]
    if signal == "BUY":
        sl = entry - sl_pips * pip
        tp = entry + tp_pips * pip if tp_pips is not None else None
    else:
        sl = entry + sl_pips * pip
        tp = entry - tp_pips * pip if tp_pips is not None else None
    return {"direction": signal, "entry": entry, "entry_time": candle.get("time"),
            "sl": sl, "tp": tp, "stop_pips": sl_pips, "closed": False}



def check_exit(trade, candle, pip, spread_pips):
    high, low = candle["high"], candle["low"]
    hit_sl = hit_tp = False
    if trade["direction"] == "BUY":
        if low <= trade["sl"]: hit_sl = True
        if trade["tp"] is not None and high >= trade["tp"]: hit_tp = True
    else:
        if high >= trade["sl"]: hit_sl = True
        if trade["tp"] is not None and low <= trade["tp"]: hit_tp = True
    if not (hit_sl or hit_tp):
        return trade
    # both possible in one candle -> assume stop first (pessimistic, unchanged)
    if hit_sl:
        _close(trade, trade["sl"], candle.get("time"), pip, spread_pips, "sl")
    else:
        _close(trade, trade["tp"], candle.get("time"), pip, spread_pips, "tp")
    return trade


def run_backtest(df, pair, strategy_fn, sl_pips=20, tp_pips=40,
                 spread_pips=1.0, signal_exit=False, allowed_entry_hours=None):
    """
    signal_exit=False -> original behaviour (exit only on SL/TP).
    signal_exit=True  -> also exit when the strategy's desired direction flips
                         opposite to the open trade. Exit fills at the NEXT
                         candle's open (same no-lookahead rule as entries);
                         the open is checked BEFORE that candle's high/low.

    allowed_entry_hours -> None (default) = no filter, behaviour unchanged.
                           A set of UTC hours (e.g. {12,13,14,15}) = only OPEN
                           a trade when the entry candle's hour is in the set.
                           EXITS are never filtered. PRECONDITION: candle
                           timestamps must be UTC (verify your pipeline).
    """
    pip = get_pip(pair)
    trades, open_trade = [], None
    pending_signal, pending_exit = None, False

    for i in range(len(df)):
        candle = df.iloc[i]

        # 1. fill pending ENTRY at this open -- gated by the entry-hour filter.
        #    `candle` here IS the entry candle: the signal was set last iteration
        #    (at candle i-1's close) and fills at THIS open, so we gate on THIS
        #    candle's hour, not i+1's.
        if pending_signal and open_trade is None:
            entry_time = candle.get("time")
            if allowed_entry_hours is not None and entry_time is None:
                # Fail LOUD rather than silently letting every trade through --
                # a filter that quietly does nothing is the dangerous kind of bug.
                raise ValueError(
                    "allowed_entry_hours is set but candles have no 'time' column; "
                    "cannot filter by hour. Check load_data() / the source CSV."
                )
            in_window = (allowed_entry_hours is None
                         or entry_time.hour in allowed_entry_hours)
            if in_window:
                open_trade = open_new_trade(pending_signal, candle, pip, sl_pips, tp_pips)
            # Clear the pending signal EITHER WAY. A cross whose entry candle falls
            # outside the window is DROPPED, not deferred. (If strategy_fn returns
            # persistent STATE rather than a cross EVENT, step 4 will re-signal on the
            # next candle and effectively defer entry to the next in-window candle --
            # so the drop-vs-defer behaviour is set by your strategy file, not here.
            # Worth a glance at sma_crossover.py to know which one you have.)
            pending_signal = None

        # 2. fill pending SIGNAL-EXIT at this open (before the candle's high/low)
        if open_trade and pending_exit:
            _close(open_trade, candle["open"], candle.get("time"),
                   pip, spread_pips, "signal")
            trades.append(open_trade); open_trade = None; pending_exit = False

        # 3. SL / TP against this candle
        if open_trade:
            open_trade = check_exit(open_trade, candle, pip, spread_pips)
            if open_trade["closed"]:
                trades.append(open_trade); open_trade = None

        # 4. consult strategy on data up to this close
        if signal_exit or (open_trade is None and pending_signal is None):
            signal = strategy_fn(df.iloc[: i + 1], pip)
            if open_trade is None and pending_signal is None:
                if signal in ("BUY", "SELL"):
                    pending_signal = signal               # enter next open
            elif open_trade is not None and signal_exit and not pending_exit:
                opposite = {"BUY": "SELL", "SELL": "BUY"}[open_trade["direction"]]
                if signal == opposite:
                    pending_exit = True

    return trades


def summarize(trades):
    """Turn a list of closed trades into headline performance numbers."""
    if not trades:
        return {"trades": 0, "note": "No trades were taken on this data."}

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    total_pnl = sum(t["pnl"] for t in trades)
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))

    return {
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_%": round(len(wins) / len(trades) * 100, 1),
        "total_pnl_pips": round(total_pnl, 1),
        "avg_pnl_pips": round(total_pnl / len(trades), 2),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else float("inf"),
        # Survivability number: biggest peak-to-trough drop on the equity curve.
        # total_pnl tells you if an edge exists; this tells you if you'd survive to use it.
        "max_drawdown_pips": round(max_drawdown(trades), 1),
    }