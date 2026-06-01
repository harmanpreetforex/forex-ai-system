"""
execution/live_loop.py
--------------------------------------------------------------------
Month 4, Session 3: the LIVE LOOP — run the bridge once per closed H1 candle,
24/5, without falling over.

The loop adds NO trading logic. It is pure orchestration + resilience around
`signal_bridge.run_once`; all the decisions, sizing, and the no-lookahead rule
already live there. What this file owns is staying alive:

  * CANDLE CADENCE: sleep to just past each H1 boundary, so we wake once the
    latest candle has CLOSED (matching the bridge's closed-candle rule). One wake
    = one new candle.
  * ONE DECISION PER CANDLE: track the last candle time acted on per pair and
    pass it as `since`, so a restart or clock wobble inside the same hour can't
    double-fire (belt; the broker double-entry guard is suspenders).
  * DISCONNECT/TIMEOUT: every broker call for a pair is wrapped in retry-with-
    backoff; if it still fails, we log and move on. A bad tick on one pair never
    kills the loop or blocks the others.
  * WEEKEND/CLOSED MARKET: skip the heavy work when FX is closed (approx Fri
    21:00 → Sun 21:00 UTC). If the estimate is wrong, run_once tolerates a closed
    market anyway (no candle / not tradeable -> hold).
  * RESTART-SAFE: state is re-derived from the broker (open trades) each tick via
    the bridge's guard; the loop holds no durable position state of its own.
  * JOURNAL: every tick's decision is appended to results/live_journal.csv (the
    Month-4 evidence trail + Session-5 reconciliation input). results/ is
    gitignored, so runtime data stays out of the repo.

SAFE BY DEFAULT: dry-run unless --send. --send re-asserts the practice account.
--once runs a single tick and exits (how we validate without a 24/5 process).

    python -m execution.live_loop --once          # one dry-run tick, exit
    python -m execution.live_loop                  # dry-run, loop forever
    python -m execution.live_loop --send           # LIVE (practice), loop forever
--------------------------------------------------------------------
"""
import csv
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import oandapyV20.endpoints.accounts as accounts

from execution.signal_bridge import run_once
from execution.oanda_order import _make_client, _account_id
from risk.kill_switch import KillSwitch

ROOT = Path(__file__).resolve().parents[1]
JOURNAL = ROOT / "results" / "live_journal.csv"
PAIRS = ("EUR_USD", "GBP_USD", "USD_JPY")
GRANULARITY_SECONDS = 3600          # H1
CANDLE_BUFFER = 15                  # wait this long past the boundary for the close
RETRY_ATTEMPTS = 4
RETRY_BASE_DELAY = 2.0             # seconds; doubles each attempt

JOURNAL_COLS = ["tick_utc", "pair", "as_of", "signal", "action", "units",
                "risk_cash", "balance", "reason", "trade_id", "fill_price"]


# ── timing ────────────────────────────────────────────────────────────────────
def seconds_to_next_candle(now=None, period=GRANULARITY_SECONDS, buffer=CANDLE_BUFFER):
    """Seconds until just past the next candle boundary. Epoch-based so it's
    correct for any period that divides the hour and immune to local-tz issues."""
    now = now or datetime.now(timezone.utc)
    epoch = now.timestamp()
    next_boundary = (int(epoch // period) + 1) * period
    return (next_boundary - epoch) + buffer


def is_market_open(now=None):
    """Approximate FX hours: closed Saturday, Sunday before 21:00 UTC, and Friday
    after 21:00 UTC. Deliberately conservative — run_once tolerates being wrong."""
    now = now or datetime.now(timezone.utc)
    wd, hr = now.weekday(), now.hour      # Mon=0 .. Sun=6
    if wd == 5:                            # Saturday
        return False
    if wd == 6 and hr < 21:                # Sunday morning/day
        return False
    if wd == 4 and hr >= 21:               # Friday evening
        return False
    return True


# ── resilience ─────────────────────────────────────────────────────────────────
def with_retries(fn, *, attempts=RETRY_ATTEMPTS, base_delay=RETRY_BASE_DELAY,
                 label=""):
    """Call fn() with exponential backoff on ANY exception. Returns (ok, value):
    (True, result) on success, (False, last_exception) if every attempt failed.
    Never raises — the loop must outlive a flaky API."""
    delay = base_delay
    last = None
    for i in range(1, attempts + 1):
        try:
            return True, fn()
        except Exception as e:                       # noqa: BLE001 — loop must survive
            last = e
            print(f"    [retry {i}/{attempts}] {label}: {type(e).__name__}: {e}")
            if i < attempts:
                time.sleep(delay)
                delay *= 2
    return False, last


# ── journal ────────────────────────────────────────────────────────────────────
def journal_append(decision, tick_utc):
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    new = not JOURNAL.exists()
    fill = decision.get("fill") or {}
    # dry-run fills carry only a payload; live fills carry trade_id/fill_price
    trade_id = fill.get("trade_id") if isinstance(fill, dict) else None
    fill_price = fill.get("fill_price") if isinstance(fill, dict) else None
    row = {
        "tick_utc": tick_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pair": decision["pair"],
        "as_of": str(decision.get("as_of")),
        "signal": decision.get("signal"),
        "action": decision.get("action"),
        "units": decision.get("units"),
        "risk_cash": decision.get("risk_cash"),
        "balance": decision.get("balance"),
        "reason": decision.get("reason"),
        "trade_id": trade_id,
        "fill_price": fill_price,
    }
    with open(JOURNAL, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=JOURNAL_COLS)
        if new:
            w.writeheader()
        w.writerow(row)


# ── one tick across all pairs ───────────────────────────────────────────────────
def _nav(client, account_id):
    req = accounts.AccountSummary(account_id)
    client.request(req)
    return float(req.response["account"]["NAV"])


def tick(client, account_id, last_seen, *, send=False, kill_switch=None):
    """Process one candle for every pair. Updates last_seen in place. Returns the
    list of decisions (also journaled).

    Kill switch is evaluated ONCE per tick on current NAV; if it blocks, every
    pair's entry is gated off (can_enter=False) so a real signal is journaled as
    a halt, never sent. If we can't even read NAV, we FAIL SAFE -> block entries."""
    tick_utc = datetime.now(timezone.utc)
    can_enter, halt_reason = True, None
    if kill_switch is not None:
        ok_nav, nav = with_retries(lambda: _nav(client, account_id), label="NAV")
        if ok_nav:
            can_enter, halt_reason, m = kill_switch.check(nav)
            if not can_enter:
                print(f"  KILL SWITCH: entries blocked — {halt_reason} "
                      f"(NAV {m['nav']:.0f})")
        else:
            can_enter, halt_reason = False, "NAV unavailable — failing safe (no entries)"
            print(f"  KILL SWITCH: {halt_reason}")

    decisions = []
    for pair in PAIRS:
        ok, result = with_retries(
            lambda p=pair: run_once(p, send=send, since=last_seen.get(p),
                                    can_enter=can_enter, halt_reason=halt_reason,
                                    client=client, account_id=account_id),
            label=pair,
        )
        if not ok:
            decisions.append({"pair": pair, "action": "error", "units": 0,
                              "reason": f"{type(result).__name__}: {result}",
                              "as_of": None, "signal": None, "fill": None})
            journal_append(decisions[-1], tick_utc)
            continue

        d = result
        if d.get("as_of") is not None:
            last_seen[pair] = d["as_of"]             # advance the one-per-candle marker
        decisions.append(d)
        journal_append(d, tick_utc)

        line = (f"  {pair}  as_of {str(d.get('as_of'))[:16]}  "
                f"signal={d.get('signal')} -> {d.get('action')}")
        if d.get("units"):
            line += f"  units={d['units']} risk={d.get('risk_cash')} CAD"
        if d.get("reason"):
            line += f"  ({d['reason']})"
        print(line)
    return decisions


# ── main loop ────────────────────────────────────────────────────────────────────
def main():
    once = "--once" in sys.argv
    send = "--send" in sys.argv
    if send and os.getenv("OANDA_ENVIRONMENT", "practice") != "practice":
        raise SystemExit("ENVIRONMENT is not practice -- refusing to --send.")

    client, account_id = _make_client(), _account_id()
    last_seen = {}
    kill_switch = KillSwitch()
    mode = "SEND (practice)" if send else "DRY-RUN"
    print(f"Live loop: {mode} | pairs={','.join(PAIRS)} | H1 | journal -> {JOURNAL}")

    if once:
        print(f"\n[single tick {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}Z]")
        tick(client, account_id, last_seen, send=send, kill_switch=kill_switch)
        return

    try:
        while True:
            if is_market_open():
                stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
                print(f"\n[tick {stamp}]")
                tick(client, account_id, last_seen, send=send, kill_switch=kill_switch)
            else:
                print(f"[{datetime.now(timezone.utc):%a %H:%MZ}] market closed — idle")
            sleep_s = seconds_to_next_candle()
            print(f"  sleeping {sleep_s:.0f}s to next H1 candle")
            time.sleep(sleep_s)
    except KeyboardInterrupt:
        print("\nStopped (Ctrl-C). Open positions are left as-is on the broker.")


if __name__ == "__main__":
    main()
