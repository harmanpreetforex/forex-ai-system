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
--------------------------------------------------------------------
"""
import pandas as pd
from backtest.results import max_drawdown   # absolute import, matches run_backtest.py


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
    """Open a trade at THIS candle's open (the candle AFTER the signal)."""
    entry = candle["open"]
    if signal == "BUY":
        sl = entry - sl_pips * pip
        tp = entry + tp_pips * pip
    else:  # SELL
        sl = entry + sl_pips * pip
        tp = entry - tp_pips * pip
    return {
        "direction": signal,
        "entry": entry,
        "entry_time": candle.get("time"),
        "sl": sl,
        "tp": tp,
        "stop_pips": sl_pips,   # entry-to-stop distance; the runner needs this to size positions
        "closed": False,
    }


def check_exit(trade, candle, pip, spread_pips):
    """Did this candle's high/low touch the stop loss or take profit?"""
    high, low = candle["high"], candle["low"]
    hit_sl = hit_tp = False

    if trade["direction"] == "BUY":
        if low <= trade["sl"]:
            hit_sl = True
        if high >= trade["tp"]:
            hit_tp = True
    else:  # SELL
        if high >= trade["sl"]:
            hit_sl = True
        if low <= trade["tp"]:
            hit_tp = True

    if not (hit_sl or hit_tp):
        return trade  # still open, nothing to do

    # If BOTH could have hit in the same candle we can't know the order,
    # so we assume the stop loss hit first - the honest, pessimistic choice.
    exit_price = trade["sl"] if hit_sl else trade["tp"]

    if trade["direction"] == "BUY":
        pnl = (exit_price - trade["entry"]) / pip
    else:
        pnl = (trade["entry"] - exit_price) / pip

    trade["exit"] = exit_price
    trade["exit_time"] = candle.get("time")
    trade["pnl"] = pnl - spread_pips  # subtract the cost of entering the trade
    trade["closed"] = True
    return trade


def run_backtest(df, pair, strategy_fn, sl_pips=20, tp_pips=40, spread_pips=1.0):
    """
    The core loop. One pass through the data, candle by candle.

    Two rules keep it honest:
      1. A signal generated on candle i is entered on candle i+1's OPEN.
         (Entering on the same candle that generated the signal = lookahead bias.)
      2. Exits are checked against each candle's own high/low.
    """
    pip = get_pip(pair)
    trades = []
    open_trade = None
    pending_signal = None

    for i in range(len(df)):
        candle = df.iloc[i]

        # 1. Execute any entry that was decided on the PREVIOUS candle's close
        if pending_signal and open_trade is None:
            open_trade = open_new_trade(pending_signal, candle, pip, sl_pips, tp_pips)
            pending_signal = None

        # 2. Check whether the open trade hits SL/TP on THIS candle
        if open_trade:
            open_trade = check_exit(open_trade, candle, pip, spread_pips)
            if open_trade["closed"]:
                trades.append(open_trade)
                open_trade = None

        # 3. Ask the strategy for a signal, using data UP TO this candle's close
        if open_trade is None and pending_signal is None:
            history = df.iloc[: i + 1]
            signal = strategy_fn(history, pip)
            if signal in ("BUY", "SELL"):
                pending_signal = signal  # will be entered on the next candle's open

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