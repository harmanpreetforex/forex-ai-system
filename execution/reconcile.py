"""
execution/reconcile.py
--------------------------------------------------------------------
Month 4, Session 5: DAILY RECONCILIATION — does live execution match the
backtest's assumptions? This is the actual Month-4 deliverable (execution
fidelity), turned into a number you can read each day of the soak.

It answers three questions over a lookback window:

  1. SPREAD FIDELITY. For every entry fill, the real spread paid (top-of-book
     ask-bid at the fill, in pips) vs the spread the backtest MODELS for that
     pair (EUR 1.6 / GBP 1.9 / JPY 1.7). If live spread >> modeled, the backtest
     was optimistic and its PnL is a mirage. (First live tick already matched:
     trade 5 entry spread == 1.6 pips, and its round-trip halfSpreadCost 0.022
     CAD == the modeled 1.6-pip cost.)
  2. ACTIVITY RECONCILIATION. journal 'sent' rows vs actual entry fills, per pair
     — catches MISSED trades (signal sent, no fill) and EXTRA fills (fill with no
     journalled signal). A divergence here means the loop and the broker disagree
     about reality, which is the scariest kind of bug.
  3. PnL. realized P/L per pair from closed trades, as a sanity total.

Pulls ORDER_FILL transactions from OANDA (the broker's own record, the source of
truth), reads results/live_journal.csv for the loop's intent, and prints a table.
Read-only: it sends no orders and changes nothing.

    python -m execution.reconcile               # last 30 days
    python -m execution.reconcile --days 1      # yesterday+today (a daily check)
--------------------------------------------------------------------
"""
import csv
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

import oandapyV20.endpoints.accounts as accounts
import oandapyV20.endpoints.transactions as tx

from execution.oanda_order import _make_client, _account_id
from risk.position_sizer import pip_size

ROOT = Path(__file__).resolve().parents[1]
JOURNAL = ROOT / "results" / "live_journal.csv"

# The spreads the backtest assumes (oos_split.py / run_backtest.py). The whole
# point is to check live against THESE specific numbers.
MODELED_SPREAD = {"EUR_USD": 1.6, "GBP_USD": 1.9, "USD_JPY": 1.7}


def fetch_fills(client, account_id, lookback_days):
    """All ORDER_FILL transactions within the lookback window. Walks back from the
    last transaction id (demo accounts have few, so one SinceID call suffices; if
    that ever caps out, this is where pagination would go)."""
    r = accounts.AccountSummary(account_id)
    client.request(r)
    last = int(r.response["account"]["lastTransactionID"])

    req = tx.TransactionsSinceID(account_id, params={"id": str(max(0, last - 1000))})
    client.request(req)
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    fills = []
    for t in req.response.get("transactions", []):
        if t.get("type") != "ORDER_FILL":
            continue
        when = datetime.fromisoformat(t["time"].replace("Z", "+00:00"))
        if when < cutoff:
            continue
        fills.append(t)
    return fills


def entry_spread_pips(fill, pair):
    """Real spread paid at this fill = top-of-book (ask - bid) in pips. Uses the
    tradeable bids/asks (NOT the wider closeout prices). Returns None if absent."""
    fp = fill.get("fullPrice", {})
    bids, asks = fp.get("bids"), fp.get("asks")
    if not bids or not asks:
        return None
    spread = float(asks[0]["price"]) - float(bids[0]["price"])
    return spread / pip_size(pair)


def journal_sent_counts():
    """Per-pair count of orders the loop intended to SEND (action == 'sent')."""
    counts = defaultdict(int)
    if not JOURNAL.exists():
        return counts, False
    with open(JOURNAL) as f:
        for row in csv.DictReader(f):
            if row.get("action") == "sent":
                counts[row["pair"]] += 1
    return counts, True


def reconcile(lookback_days):
    client, account_id = _make_client(), _account_id()
    fills = fetch_fills(client, account_id, lookback_days)

    entries = defaultdict(list)     # pair -> [entry spread pips]
    n_entries = defaultdict(int)
    realized = defaultdict(float)
    n_closed = defaultdict(int)
    for f in fills:
        pair = f["instrument"]
        if f.get("tradeOpened"):
            n_entries[pair] += 1
            sp = entry_spread_pips(f, pair)
            if sp is not None:
                entries[pair].append(sp)
        for c in (f.get("tradesClosed") or []):
            n_closed[pair] += 1
            realized[pair] += float(c.get("realizedPL", 0))

    sent_counts, have_journal = journal_sent_counts()

    print(f"Reconciliation — last {lookback_days} day(s)  "
          f"({len(fills)} ORDER_FILL txns)\n")
    if not fills:
        print("No live fills in window yet. Run the soak "
              "(python -m execution.live_loop --send), then reconcile daily.")
        return

    hdr = (f"{'pair':<9}{'entries':>8}{'spread(live)':>14}{'modeled':>9}"
           f"{'Δpips':>7}{'closed':>8}{'realPL CAD':>12}{'sent':>6}{'flag':>8}")
    print(hdr); print("-" * len(hdr))
    for pair in MODELED_SPREAD:
        n = n_entries[pair]
        live_sp = sum(entries[pair]) / len(entries[pair]) if entries[pair] else float("nan")
        model = MODELED_SPREAD[pair]
        d = live_sp - model if entries[pair] else float("nan")
        sent = sent_counts.get(pair, 0) if have_journal else None
        # flag: live spread materially worse than modeled, or sent!=filled
        flag = ""
        if entries[pair] and d > 0.5:
            flag = "SPREAD"
        if have_journal and sent is not None and sent != n:
            flag = (flag + "+" if flag else "") + "MISMATCH"
        sent_s = "  n/a" if sent is None else f"{sent:>6}"
        live_s = "   nan" if not entries[pair] else f"{live_sp:>9.2f}"
        d_s = "  nan" if not entries[pair] else f"{d:>+6.2f}"
        print(f"{pair:<9}{n:>8}{live_s:>14}{model:>9}{d_s:>7}"
              f"{n_closed[pair]:>8}{realized[pair]:>12.2f}{sent_s}{flag:>8}")

    total_pl = sum(realized.values())
    print("-" * len(hdr))
    print(f"total realized P/L: {total_pl:+.2f} CAD")
    if not have_journal:
        print("(no live_journal.csv yet — activity reconciliation skipped)")
    print("\nRead it: Δpips near 0 = live spread matches the backtest (good). "
          "SPREAD flag = backtest was optimistic. MISMATCH = loop intent and "
          "broker fills disagree — investigate before trusting either.")


if __name__ == "__main__":
    days = 30
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    reconcile(days)
