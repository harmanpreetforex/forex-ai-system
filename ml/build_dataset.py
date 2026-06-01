"""
ml/build_dataset.py
--------------------------------------------------------------------
Month 3, Session 1 -- the FRAMING HARNESS that ties labeling + features + split
together and PROVES the discipline holds, without fitting a single model. Run
this to confirm the data plumbing is leak-free before any sklearn estimator is
allowed near it.

What it does, per pair:
  1. load OHLC (reusing backtest.engine.load_data -- one data loader, no drift)
  2. build past-only features (ml/features)
  3. build triple-barrier labels (ml/labeling)
  4. align them and drop (a) front warm-up NaNs and (b) the unlabelable tail
  5. report class balance + walk-forward fold geometry
  6. assert the leakage contracts (feature non-anticipation, label tail, fold
     purge) so a future edit that breaks them fails LOUD here, not silently in a
     backtest six steps later.

It writes nothing and trains nothing. The next session adds a model that fits on
fold train indices and is scored ONLY on fold test indices -- the gate is in
ml/split.walk_forward_folds, already locked.

Run from project root:
    python -m ml.build_dataset
--------------------------------------------------------------------
"""
import os

import numpy as np
import pandas as pd

from backtest.engine import load_data
from ml.features import make_features, FEATURE_COLUMNS
from ml.labeling import triple_barrier_labels, label_summary, HORIZON
from ml.split import walk_forward_folds, describe_folds, EMBARGO

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAIRS = {
    "EUR_USD": "eurusd_1h_2y.csv",
    "GBP_USD": "gbpusd_1h_2y.csv",
    "USD_JPY": "usdjpy_1h_2y.csv",
}


def build_pair(pair, csv):
    """Return (X, y) aligned and clean: past-only features + triple-barrier label,
    front warm-up and unlabelable tail removed, index preserved for traceability."""
    df = load_data(os.path.join(ROOT, "data", csv))
    X = make_features(df, pair)
    y = triple_barrier_labels(df, pair)

    # Join, then drop any row with a NaN feature (front warm-up) or NaN label
    # (the final HORIZON rows). Inner alignment on the shared index.
    data = X.copy()
    data["label"] = y
    clean = data.dropna()
    X_clean = clean[FEATURE_COLUMNS]
    y_clean = clean["label"].astype(np.int8)
    return df, X_clean, y_clean


def main():
    print("=" * 70)
    print("Month 3 dataset framing -- leakage + geometry check (NO model fit)")
    print(f"label: triple-barrier tp/sl/horizon locked in ml/labeling.py "
          f"(horizon={HORIZON}, embargo={EMBARGO})")
    print("=" * 70)

    for pair, csv in PAIRS.items():
        df, X, y = build_pair(pair, csv)
        s = label_summary(triple_barrier_labels(df, pair))

        print(f"\n===== {pair} =====")
        print(f"  rows raw: {len(df)} | usable (X,y): {len(X)} "
              f"| features: {X.shape[1]}")
        print(f"  class balance: up(1)={int((y==1).sum())} "
              f"down/flat(0)={int((y==0).sum())} "
              f"| base rate up = {s['base_rate_up_%']}%  "
              f"<- the all-0 baseline a model must beat")

        # --- leakage contract 1: feature non-anticipation -------------------
        cut = min(8000, len(df) - 1)
        full = make_features(df, pair).iloc[:cut]
        trunc = make_features(df.iloc[:cut], pair)
        pd.testing.assert_frame_equal(full, trunc)

        # --- leakage contract 2: exactly the last HORIZON rows are unlabeled -
        lab = triple_barrier_labels(df, pair)
        assert lab.tail(HORIZON).isna().all()
        assert lab.iloc[:-HORIZON].notna().all()

        # --- geometry + purge contract --------------------------------------
        folds = walk_forward_folds(len(df))
        for fid, tr, te in folds:
            if len(tr):
                assert te[0] - tr[-1] > EMBARGO, f"{pair} fold {fid} not purged"
        print(f"  leakage guards: OK | walk-forward folds: {len(folds)} "
              f"(the bar an edge must clear)")

    print("\n" + "=" * 70)
    print("Fold geometry (identical to backtest/walk_forward.py windows):")
    describe_folds(len(df))   # geometry is pair-independent (same row count band)
    print("\nDiscipline locked. Success criterion (from the tracker): a model")
    print("must beat the per-pair base rate AND clear these walk-forward folds")
    print("consistently -- not a single split. No goalpost-moving mid-stream.")


if __name__ == "__main__":
    main()
