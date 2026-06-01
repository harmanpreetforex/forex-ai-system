"""
execution/oanda_order.py
--------------------------------------------------------------------
Month 4, Session 1: the ORDER-EXECUTION LAYER — the ENTIRE broker surface.

Design rule (tracker Open Q "MT5 portability"): every call that touches the
broker lives behind these functions. The live loop, the kill switch, and the
journal all go through `place_market_order` / `close_trade` and never import
oandapyV20 themselves. When Month 5 needs MetaTrader, only this file is rewritten
-- the strategy, sizing, and loop code don't change.

What it does:
  * place_market_order(pair, units, sl_pips, tp_pips) -> submit a MARKET order
    with SL (and optional TP) attached ON FILL, so the protective stop exists
    from the instant the position opens (no race where we're live without a
    stop). units sign = direction: +ve BUY, -ve SELL.
  * close_trade(trade_id) -> flatten a specific open trade.
  * get_open_trades() -> what the broker thinks we hold (restart-safety later).

SAFETY: this module SENDS REAL ORDERS to whatever account .env points at (it
should be the PRACTICE account). Nothing here fires on import. `place_market_order`
has dry_run=True available to build+validate the payload without sending, and the
__main__ block is dry-run unless you pass --send. Treat every send as real.

The engine works in PIPS; OANDA wants price DISTANCES. We convert with the same
pip convention as the rest of the system and format to the instrument's price
precision (5 dp majors, 3 dp JPY) so OANDA never rejects on precision.
--------------------------------------------------------------------
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from oandapyV20 import API
from oandapyV20.endpoints.orders import OrderCreate
from oandapyV20.endpoints.trades import TradeClose, OpenTrades

# Reuse the canonical pip size (Day-12 lesson: don't redefine shared logic and
# let the copies drift). pip_size: 0.01 for JPY pairs, 0.0001 otherwise.
from risk.position_sizer import pip_size

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


class OrderError(RuntimeError):
    """Raised when OANDA rejects/cancels an order, or the response lacks a fill.
    Carries the raw transaction so the caller (and the journal) can see WHY."""
    def __init__(self, message, transaction=None):
        super().__init__(message)
        self.transaction = transaction


def _make_client():
    token = os.getenv("OANDA_API_TOKEN")
    env = os.getenv("OANDA_ENVIRONMENT", "practice")
    if not token:
        raise OrderError("OANDA_API_TOKEN missing -- check .env")
    return API(access_token=token, environment=env)


def _account_id():
    acct = os.getenv("OANDA_ACCOUNT_ID")
    if not acct:
        raise OrderError("OANDA_ACCOUNT_ID missing -- check .env")
    return acct


def _price_precision(pair):
    """OANDA price precision: JPY majors quote to 3 dp, the rest to 5 dp. Matches
    the pip convention (JPY pip 0.01, others 0.0001)."""
    return 3 if "JPY" in pair.upper() else 5


def _distance(pips, pair):
    """Pips -> a positive price-distance string at the instrument's precision.
    Used for stopLossOnFill/takeProfitOnFill `distance`, which is symmetric for
    BUY and SELL (OANDA places it the correct side of the fill automatically) --
    so we never have to know the fill price up front to attach a protective stop.
    """
    prec = _price_precision(pair)
    return f"{abs(pips) * pip_size(pair):.{prec}f}"


def build_market_order(pair, units, sl_pips, tp_pips=None):
    """Construct the OrderCreate payload. Pure + side-effect-free, so it's unit-
    testable and the live loop can log EXACTLY what it will send before sending.

    A stop-loss is MANDATORY (sl_pips must be > 0): the whole risk framework
    assumes every position has a real stop -- an unstopped trade can breach the
    prop max-drawdown in one candle. units must be a non-zero int; its sign is
    the direction.
    """
    units = int(units)
    if units == 0:
        raise OrderError("units must be non-zero (sign = direction).")
    if sl_pips is None or sl_pips <= 0:
        raise OrderError("sl_pips must be > 0 -- every order needs a real stop.")

    order = {
        "type": "MARKET",
        "instrument": pair,
        "units": str(units),
        "timeInForce": "FOK",          # fill-or-kill: no partial mystery fills
        "positionFill": "DEFAULT",
        "stopLossOnFill": {"distance": _distance(sl_pips, pair), "timeInForce": "GTC"},
    }
    if tp_pips is not None:
        order["takeProfitOnFill"] = {"distance": _distance(tp_pips, pair),
                                     "timeInForce": "GTC"}
    return {"order": order}


def _parse_fill(resp, pair):
    """Pull the fill out of an OrderCreate response, or raise with the reason.
    OANDA signals rejection via orderCancelTransaction / orderRejectTransaction
    and a fill via orderFillTransaction -- we fail LOUD on anything but a clean
    fill so a silently-rejected order can't masquerade as an open position."""
    if "orderCancelTransaction" in resp:
        reason = resp["orderCancelTransaction"].get("reason", "UNKNOWN")
        raise OrderError(f"order cancelled by OANDA: {reason}",
                         resp["orderCancelTransaction"])
    if "orderRejectTransaction" in resp:
        reason = resp["orderRejectTransaction"].get("rejectReason", "UNKNOWN")
        raise OrderError(f"order rejected by OANDA: {reason}",
                         resp["orderRejectTransaction"])
    fill = resp.get("orderFillTransaction")
    if not fill:
        raise OrderError("no orderFillTransaction in response (no fill?)", resp)

    opened = fill.get("tradeOpened") or {}
    return {
        "trade_id": opened.get("tradeID"),
        "order_id": fill.get("orderID"),
        "fill_price": float(fill["price"]),
        "units": int(float(fill.get("units", opened.get("units", 0)))),
        "pair": pair,
        "time": fill.get("time"),
        "half_spread_cost": float(fill.get("halfSpreadCost", "nan")),
        "raw": fill,
    }


def place_market_order(pair, units, sl_pips, tp_pips=None, *,
                       client=None, account_id=None, dry_run=False):
    """Submit a market order with SL (+optional TP) attached on fill.

    Returns a fill dict (trade_id, fill_price, units, time, half_spread_cost...).
    dry_run=True returns the payload WITHOUT sending -- use it to validate /
    journal-preview. Raises OrderError on any non-fill so callers never assume an
    order opened when it didn't.
    """
    payload = build_market_order(pair, units, sl_pips, tp_pips)
    if dry_run:
        return {"dry_run": True, "payload": payload}

    client = client or _make_client()
    account_id = account_id or _account_id()
    req = OrderCreate(account_id, data=payload)
    client.request(req)
    return _parse_fill(req.response, pair)


def close_trade(trade_id, *, client=None, account_id=None):
    """Flatten one open trade by ID. Returns the close fill (price, realized P/L).
    Raises OrderError if OANDA didn't confirm a close fill."""
    client = client or _make_client()
    account_id = account_id or _account_id()
    req = TradeClose(account_id, tradeID=str(trade_id))
    client.request(req)
    fill = req.response.get("orderFillTransaction")
    if not fill:
        raise OrderError(f"trade {trade_id} close not confirmed", req.response)
    return {
        "trade_id": str(trade_id),
        "close_price": float(fill["price"]),
        "realized_pl": float(fill.get("pl", "nan")),
        "time": fill.get("time"),
        "raw": fill,
    }


def get_open_trades(*, client=None, account_id=None):
    """List currently-open trades the broker holds. The live loop uses this on
    restart to avoid double-entering a position it already has."""
    client = client or _make_client()
    account_id = account_id or _account_id()
    req = OpenTrades(account_id)
    client.request(req)
    return req.response.get("trades", [])


# ── Acceptance test (Month 4 S1): place + close ONE tiny trade, reconcile ──────
# DRY-RUN BY DEFAULT. Sends a real (practice) order only with --send.
if __name__ == "__main__":
    import sys

    PAIR, UNITS, SL, TP = "EUR_USD", 100, 15, 15   # 100 units ≈ a few $ of risk
    send = "--send" in sys.argv

    print(f"Acceptance test: {('SEND' if send else 'DRY-RUN')}  "
          f"{PAIR} units={UNITS} sl={SL} tp={TP}")
    print("payload OANDA would receive:")
    import json
    print(json.dumps(build_market_order(PAIR, UNITS, SL, TP), indent=2))

    if not send:
        print("\n(dry-run -- no order sent. Re-run with --send to place a real "
              "practice trade.)")
        sys.exit(0)

    print("\nSending order to OANDA practice ...")
    fill = place_market_order(PAIR, UNITS, SL, TP)
    print(f"  FILLED: trade {fill['trade_id']} @ {fill['fill_price']} "
          f"({fill['units']} units) at {fill['time']}")
    print(f"  half-spread cost paid: {fill['half_spread_cost']}")

    print("Closing the trade ...")
    close = close_trade(fill["trade_id"])
    print(f"  CLOSED @ {close['close_price']}  realized P/L {close['realized_pl']}")
    slip = (close["close_price"] - fill["fill_price"])
    print(f"  round-trip price move: {slip:+.5f}  "
          f"({slip / pip_size(PAIR):+.1f} pips, incl. spread)")
    print("Open trades remaining:", len(get_open_trades()))
