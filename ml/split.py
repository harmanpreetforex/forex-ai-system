"""
ml/split.py
--------------------------------------------------------------------
Month 3, Session 1 deliverable (part 2 of 3): the SPLIT DISCIPLINE.

Lock this BEFORE any model fits. Two split tools, both strictly chronological,
both leakage-purged for the triple-barrier label:

  1. chronological_split() -- a single train/test cut (the Day 13 style), for
     fast iteration. ONE split is ONE coin flip; never trust it alone.
  2. walk_forward_folds()  -- the real bar. Non-overlapping rolling test windows,
     same geometry as backtest/walk_forward.py, so an ML result is judged on the
     EXACT standard that falsified the classical edges (Day 9-deep / Day 14).
     The tracker is explicit: success = clears this, not a single split.

THE LEAK THIS FILE EXISTS TO KILL
--------------------------------------------------------------------
The triple-barrier label at row i reads candles i+1 .. i+horizon. So a row whose
label window straddles a train/test boundary has SEEN test-side candles. If it
sits in train, the model trained on the future; if in test, its features were
chosen with boundary knowledge. Either way the boundary leaks.

Fix = PURGE: drop the `horizon` rows immediately before each test window from
train (their labels reach into the test window). We also EMBARGO a few rows
after the test window for symmetry / serial-correlation safety. This is the de
Prado purge+embargo, scoped to exactly our label horizon -- not a vibe, a
mechanical consequence of HORIZON.

Indices returned are positional (iloc) into the ORIGINAL dataframe, so callers
keep one source of truth for the data and never re-slice it inconsistently.
--------------------------------------------------------------------
"""
import numpy as np

from ml.labeling import HORIZON

# Window geometry mirrors backtest/walk_forward.py so ML is judged on the same
# windows that judged the classical strategies. Do NOT shrink TEST_SIZE to get
# more folds -- thin windows are the Day 14 self-defeat (sample below the noise
# floor invalidates the very test you're running).
TRAIN_SIZE = 3000
TEST_SIZE  = 2000
STEP       = TEST_SIZE     # non-overlapping test windows -> no double-counting
EMBARGO    = HORIZON       # rows purged on each side of a boundary (= label reach)


def chronological_split(n, train_frac=0.70, embargo=EMBARGO):
    """Single chronological cut. Returns (train_idx, test_idx) as positional
    arrays into a length-`n` dataframe.

    Train = older train_frac. Test = newer remainder. The `embargo` rows right
    before the boundary are PURGED from train (their label horizon reaches into
    test). Nothing is shuffled -- shuffling a time series leaks the future into
    the past, the fatal invisible bug oos_split.py already warns about.
    """
    split_i = int(n * train_frac)
    train_idx = np.arange(0, max(0, split_i - embargo))   # purge tail of train
    test_idx  = np.arange(split_i, n)
    return train_idx, test_idx


def walk_forward_folds(n, train_size=TRAIN_SIZE, test_size=TEST_SIZE,
                       step=STEP, embargo=EMBARGO):
    """Yield (fold_id, train_idx, test_idx) positional arrays for non-overlapping
    rolling test windows -- same geometry as backtest/walk_forward.py.

    For each fold the train block is everything from `train_start` up to the test
    window, MINUS the last `embargo` rows (purged: their labels reach into test).
    Train rolls forward with the test window (a moving, not anchored, train set),
    which keeps train size stable across folds and avoids stale-regime training.

    Read CONSISTENCY across folds, never a single fold's number (each test window
    is only ~2000 candles -> a few hundred labeled rows -> noisy on its own).
    """
    folds = []
    fold_id = 0
    test_start = train_size
    while test_start + test_size <= n:
        fold_id += 1
        test_end = test_start + test_size
        train_start = test_start - train_size
        train_idx = np.arange(train_start, max(train_start, test_start - embargo))
        test_idx  = np.arange(test_start, test_end)
        folds.append((fold_id, train_idx, test_idx))
        test_start += step
    return folds


def describe_folds(n, folds=None):
    """Human-readable geometry check. Run this to SEE the windows before trusting
    any fold metric -- the empty-window bug (walk_forward.py) is easy to hit and
    silent."""
    if folds is None:
        folds = walk_forward_folds(n)
    print(f"n={n} | train={TRAIN_SIZE} test={TEST_SIZE} step={STEP} "
          f"embargo={EMBARGO} -> {len(folds)} fold(s)")
    for fid, tr, te in folds:
        print(f"  fold {fid}: train [{tr[0]:>5}..{tr[-1]:>5}] ({len(tr)} rows, "
              f"purged {EMBARGO}) | test [{te[0]:>5}..{te[-1]:>5}] ({len(te)} rows)")
    return folds


if __name__ == "__main__":
    import os, sys
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, ROOT)
    from backtest.engine import load_data

    df = load_data(os.path.join(ROOT, "data", "eurusd_1h_2y.csv"))
    n = len(df)
    print("Walk-forward folds (the bar an ML edge must clear):")
    folds = describe_folds(n)

    # Leakage guard: no train index may fall within EMBARGO of its test start.
    for fid, tr, te in folds:
        if len(tr):
            assert te[0] - tr[-1] > EMBARGO, f"fold {fid}: train not purged off test"
    print("  purge guard: OK (every train block ends > EMBARGO before its test)")

    tr, te = chronological_split(n)
    print(f"\nSingle 70/30 split: train {len(tr)} (purged {EMBARGO}) | test {len(te)}")
