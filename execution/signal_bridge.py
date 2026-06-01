"""
execution/signal_bridge.py
--------------------------------------------------------------------
Month 4, Session 2: the SIGNAL -> ORDER bridge.

Turns "what does the strategy say RIGHT NOW" into "a correctly-sized order on the
demo account", reusing the EXACT pieces the backtest used so live can't silently
diverge from the thing we validated:

  * SIGNAL: the same `strategy_fn(history, pip)` the engine calls. We do NOT
    re-implement the crossover here -- duplicated signal logic is the Day-12 trap
    (two copies drift, and you trade one while you backtested the other).
  * SIZE:   risk/position_sizer.position_size(), off the LIVE balance.
  * ORDER:  execution/oanda_order.place_market_order().

THE NO-LOOKAHEAD RULE (non-negotiable)
--------------------------------------------------------------------
We decide only on CLOSED candles. OANDA's latest candle is still forming; acting
on it means reacting to a bar that can still change -- the live version of the
lookahead bias the whole backtest was built to avoid. latest_candles() drops the
incomplete candle, so `history.iloc[-1]` is always the last COMPLETED bar, just
like the engine saw.

DOUBLE-ENTRY GUARD: if the broker already holds a trade on this pair, we HOLD
rather than stack a second one. (Restart-safety + not over-risking one pair; the
full loop in Session 3 leans on this too.)

Safe-by-default: run_once(send=False) builds + logs the order WITHOUT sending.
The __main__ block is dry-run across all pairs unless you pass --send, and --send
re-asserts the practice account first (same gate as oanda_order).

Run from project root:
    python -m execution.signal_bridge            # dry-run, all pairs
    python -m execution.signal_bridge --send     # live (practice) -- only fires on a real cross
--------------------------------------------------------------------
"""
import os

import pandas as pd
from oandapyV20.endpoints.instruments import InstrumentsCandles
from oandapyV20.endpoints.pricing import PricingInfo
import oandapyV20.endpoints.accounts as accounts

from strategies.sma_crossover import strategy_fn as sma_signal
from risk.position_sizer import position_size, pip_size
from execution.oanda_order import (
    place_market_order, get_open_trades, _make_client, _account_id, OrderError,
)

# Least-bad strategy (tracker): we run it to exercise the loop, not for profit.
# Brackets match the backtest's SL; a TP keeps each order self-contained until the
# Session-3 loop can do signal-exit. risk_pct from 02_Risk_Rules (1%).
RISK_PCT = 0.01
SL_PIPS  = 20
TP_PIPS  = 40
HISTORY  = 200          # plenty to warm SMA(30); cheap to fetch


def latest_candles(pair, client, count=HISTORY, granularity="H1"):
    """Fetch the most recent `count` candles and DROP the still-forming one, so
    the last row is the last CLOSED bar. Schema matches load_data() (lowercase
    OHLC + naive-UTC 'time') so strategy_fn sees exactly the backtest's columns."""
    params = {"granularity": granularity, "count": count, "price": "M"}
    req = InstrumentsCandles(instrument=pair, params=params)
    client.request(req)
    rows = []
    for c in req.response["candles"]:
        if not c.get("complete", False):
            continue                                  # never act on a forming bar
        m = c["mid"]
        rows.append({
            "time":  pd.to_datetime(c["time"]).tz_localize(None),
            "open":  float(m["o"]), "high": float(m["h"]),
            "low":   float(m["l"]), "close": float(m["c"]),
        })
    return pd.DataFrame(rows)


def _mids(instruments, client, account_id):
    """Live mid prices for a set of instruments -> {instrument: mid}."""
    params = {"instruments": ",".join(instruments)}
    req = PricingInfo(accountID=account_id, params=params)
    client.request(req)
    out = {}
    for p in req.response["prices"]:
        bid = float(p["bids"][0]["price"])
        ask = float(p["asks"][0]["price"])
        out[p["instrument"]] = (bid + ask) / 2
    return out


def quote_to_account(pair, client, account_id):
    """CAD per 1 unit of the pair's QUOTE currency -- the rate position_sizer needs.

    quote ccy is the second leg (EUR_USD -> USD, USD_JPY -> JPY). Account is CAD.
      USD quote -> USD/CAD mid                      (CAD per USD)
      JPY quote -> USD_CAD / USD_JPY                (CAD per JPY, via the USD leg)
      CAD quote -> 1.0
    Fetched LIVE so the dollar risk is current, not a stale constant (the Day-8
    fixed-1.37 caveat). Mirrors position_sizer's quote_to_account contract."""
    quote = pair.split("_")[1].upper()
    if quote == "CAD":
        return 1.0
    if quote == "USD":
        return _mids(["USD_CAD"], client, account_id)["USD_CAD"]
    if quote == "JPY":
        m = _mids(["USD_CAD", "USD_JPY"], client, account_id)
        return m["USD_CAD"] / m["USD_JPY"]
    raise OrderError(f"no CAD conversion wired for quote ccy {quote} ({pair})")


def balance(client, account_id):
    req = accounts.AccountSummary(account_id)
    client.request(req)
    return float(req.response["account"]["balance"])


def run_once(pair, *, strategy_fn=sma_signal, risk_pct=RISK_PCT,
             sl_pips=SL_PIPS, tp_pips=TP_PIPS, send=False,
             client=None, account_id=None):
    """One decision for one pair. Returns a decision dict (always), having placed
    an order only if there was a signal, no existing position, and send=True.

    The returned dict is the journal row the Session-3 loop will persist."""
    client = client or _make_client()
    account_id = account_id or _account_id()

    hist = latest_candles(pair, client)
    pip = pip_size(pair)
    signal = strategy_fn(hist, pip)
    last_time = hist["time"].iloc[-1] if len(hist) else None

    decision = {"pair": pair, "as_of": last_time, "signal": signal,
                "action": "hold", "units": 0, "reason": None, "fill": None}

    if signal not in ("BUY", "SELL"):
        decision["reason"] = "no cross on latest closed candle"
        return decision

    # Double-entry guard: don't stack onto an existing position in this pair.
    open_here = [t for t in get_open_trades(client=client, account_id=account_id)
                 if t.get("instrument") == pair]
    if open_here:
        decision["reason"] = f"already in {pair} (trade {open_here[0]['id']})"
        return decision

    qta = quote_to_account(pair, client, account_id)
    bal = balance(client, account_id)
    size = position_size(bal, risk_pct, sl_pips, pair, qta)
    units = int(size.units)                       # truncate toward zero (risk-safe)
    if units <= 0:
        decision["reason"] = f"sized units rounded to 0 (balance {bal:.0f})"
        return decision

    signed = units if signal == "BUY" else -units
    decision.update(units=signed, risk_cash=round(size.risk_cash, 2),
                    quote_to_account=round(qta, 5), balance=round(bal, 2))

    result = place_market_order(pair, signed, sl_pips, tp_pips,
                                client=client, account_id=account_id,
                                dry_run=not send)
    decision["action"] = "sent" if send else "dry_run"
    decision["fill"] = result
    return decision


def _assert_practice():
    if os.getenv("OANDA_ENVIRONMENT", "practice") != "practice":
        raise SystemExit("ENVIRONMENT is not practice -- refusing to --send.")


if __name__ == "__main__":
    import sys, json
    send = "--send" in sys.argv
    if send:
        _assert_practice()

    client, account_id = _make_client(), _account_id()
    print(f"Signal bridge: {('SEND (practice)' if send else 'DRY-RUN')}  "
          f"strategy=sma_crossover risk={RISK_PCT:.0%} sl={SL_PIPS} tp={TP_PIPS}\n")

    for pair in ("EUR_USD", "GBP_USD", "USD_JPY"):
        d = run_once(pair, send=send, client=client, account_id=account_id)
        line = (f"{d['pair']}  as_of {str(d['as_of'])[:16]}  signal={d['signal']}  "
                f"-> {d['action']}")
        if d["units"]:
            line += f"  units={d['units']}  risk_cash={d.get('risk_cash')} CAD"
        if d["reason"]:
            line += f"  ({d['reason']})"
        print(line)
        if d["action"] == "dry_run" and d["fill"]:
            print("    would send:", json.dumps(d["fill"]["payload"]["order"]))
