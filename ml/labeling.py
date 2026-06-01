"""
ml/labeling.py
--------------------------------------------------------------------
Month 3, Session 1 deliverable (part 1 of 3): the LABELING SCHEME.

Lock this BEFORE any model touches the data. The tracker's open question is
blunt about why: "This is where ML projects fool themselves." A sloppy label
is a leak, and a leak manufactures an edge that evaporates live.

THE SCHEME (triple-barrier, the honest version of "did price move?")
--------------------------------------------------------------------
Stand at the close of candle i. Look FORWARD over the next `horizon` candles
(i+1 .. i+horizon) and ask which barrier the price touches FIRST:

    +tp_pips  before -sl_pips   ->  label 1  (an up-move worth trading)
    -sl_pips  before +tp_pips   ->  label 0  (a down/stop move)
    neither barrier touched     ->  label 0  (timed out = not a tradeable up-move)

Why first-touch and not "close-to-close return": a +N pip close in `horizon`
candles is worthless if price went -3N first and stopped you out on the way.
The barrier order is what a real SL/TP order would actually experience, so the
label matches the thing the backtester (engine.py check_exit) already models.

Why this exact framing:
  * It mirrors the engine's SL/TP logic (same pips, same first-touch, same
    pessimistic "stop wins ties" rule) -> label and backtest agree on reality.
  * Binary, slightly imbalanced toward 0 -> a model that predicts all-0 is the
    trivial baseline we must beat, and class balance tells us the base rate up
    front (no surprises after training).
  * tp/sl/horizon are the ONLY label knobs. We pick them ONCE from trading
    logic (e.g. tp=sl for a 1:1, horizon = how long we'd hold an H1 idea), and
    we do NOT sweep them to flatter results -- that would curve-fit the label
    itself, the subtlest version of the Day 14 trap.

LEAKAGE CONTRACT (the part that matters)
--------------------------------------------------------------------
The label at row i is a function of FUTURE candles (i+1 .. i+horizon). That is
fine for a *target* -- but it has two consequences the split MUST respect, so
they are enforced here, loudly:

  1. The last `horizon` rows of ANY dataframe cannot be labeled (their future
     is off the end). They are returned as NaN and must be dropped, never
     filled.
  2. A label near a train/test boundary peeks ACROSS it. So the split layer
     (ml/split.py) must PURGE/EMBARGO `horizon` rows around every boundary.
     This file exposes `HORIZON`-awareness via the returned column so the split
     layer can do that; it does not split anything itself.

Pips, first-touch, and the pessimistic tie rule are intentionally identical to
backtest/engine.py so the label can never describe a move the engine wouldn't.
--------------------------------------------------------------------
"""
import numpy as np
import pandas as pd

# Defaults chosen from trading logic, NOT swept. 1:1 barrier, ~1 trading day of
# H1 candles. Documented here so any change is a deliberate, visible decision.
TP_PIPS = 15
SL_PIPS = 15
HORIZON = 24          # candles to look forward (~1 day of H1)


def get_pip(pair):
    """Pip size, identical rule to backtest/engine.get_pip (single source of truth
    would be nicer; duplicated deliberately to keep ml/ import-independent of
    the backtester for now -- revisit if it ever drifts)."""
    return 0.01 if "JPY" in pair.upper() else 0.0001


def triple_barrier_labels(df, pair, tp_pips=TP_PIPS, sl_pips=SL_PIPS,
                          horizon=HORIZON):
    """Return an int8 Series aligned to df.index: 1 if +tp_pips is touched before
    -sl_pips within the next `horizon` candles, else 0. The final `horizon` rows
    are NaN (their outcome runs off the end of the data) -> caller must drop them.

    First-touch within a candle uses high/low (same bars the engine checks), and
    ties inside one candle resolve to the STOP (label 0) -- the same pessimistic
    rule as engine.check_exit, so we never label a move more favourably than the
    backtest would fill it.

    Entry reference is the NEXT candle's open (i+1), matching the engine's
    no-lookahead fill: the signal forms at close i, the position opens at open
    i+1. So barriers are measured from open[i+1], not close[i].
    """
    pip = get_pip(pair)
    o = df["open"].to_numpy()
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    n = len(df)

    labels = np.full(n, np.nan)
    up = tp_pips * pip
    dn = sl_pips * pip

    for i in range(n - horizon):
        entry = o[i + 1]                       # fill at next open, like the engine
        tp = entry + up
        sl = entry - dn
        outcome = 0                            # default: timed out -> not a buy
        for j in range(i + 1, i + 1 + horizon):
            hit_tp = h[j] >= tp
            hit_sl = l[j] <= sl
            if hit_sl:                         # stop wins ties (pessimistic)
                outcome = 0
                break
            if hit_tp:
                outcome = 1
                break
        labels[i] = outcome

    return pd.Series(labels, index=df.index, name="label")


def label_summary(labels, horizon=HORIZON):
    """Base-rate sanity check: how many rows are labelable and what's the class
    balance. Print this BEFORE modelling so the all-0 base rate (the trivial
    baseline a model must beat) is on the record."""
    valid = labels.dropna()
    n_valid = len(valid)
    n_pos = int((valid == 1).sum())
    return {
        "total_rows": len(labels),
        "labelable": n_valid,
        "dropped_tail": len(labels) - n_valid,   # the final `horizon` rows
        "horizon": horizon,
        "pos": n_pos,
        "neg": n_valid - n_pos,
        "base_rate_up_%": round(100 * n_pos / n_valid, 2) if n_valid else float("nan"),
    }


if __name__ == "__main__":
    # Smoke test on one pair: confirm the tail is NaN and report class balance.
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, ROOT)
    from backtest.engine import load_data

    df = load_data(os.path.join(ROOT, "data", "eurusd_1h_2y.csv"))
    lab = triple_barrier_labels(df, "EUR_USD")
    s = label_summary(lab)
    print("EUR/USD triple-barrier labels "
          f"(tp={TP_PIPS} sl={SL_PIPS} horizon={HORIZON}):")
    for k, v in s.items():
        print(f"  {k:>16}: {v}")
    assert lab.tail(HORIZON).isna().all(), "tail rows must be NaN (no future)"
    assert lab.iloc[:-HORIZON].notna().all(), "all non-tail rows must be labeled"
    print("  leakage guard: OK (exactly the last horizon rows are unlabeled)")
