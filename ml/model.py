"""
ml/model.py
--------------------------------------------------------------------
Month 3, Session 2: the FIRST MODEL — judged on the locked bar, no shortcuts.

What this does, per pair, per walk-forward fold (geometry from ml/split.py, the
same windows that falsified the classical edges):
  1. Standardize features (scaler FIT ON TRAIN ONLY) + fit a classifier on the
     fold's TRAIN rows.
  2. Predict P(up) on the fold's TEST rows. Report accuracy vs the majority-class
     baseline (the "beat the base rate" gate) and ROC-AUC.
  3. Route predicted-up rows as long-only BUY signals through backtest/engine.py
     with REAL measured spread and a 15/15 bracket (= the label's barriers), and
     read PF per fold (the "clear walk-forward" gate).
  4. Summarize CONSISTENCY across folds — PF>1 count + median — because one good
     fold is one coin flip (Day 9-deep).

TWO HONEST CAVEATS, surfaced not hidden
--------------------------------------------------------------------
* Label vs engine timeout mismatch: the label times out at HORIZON candles
  (flat -> 0); the engine has no timer, so a 15/15 bracket resolves EVERY trade
  at +/-15 eventually. The engine is therefore the STRICTER, more realistic
  judge — a "flat" the label forgave can become a real loss. We accept that; the
  backtest is reality, the label is just the training target.
* The spread bar is brutal and explicit: with tp=sl=15 and ~1.6 pip spread, a
  win is +13.4 and a loss is -16.6 pips, so breakeven win rate is ~55%. The
  base rate is ~48%. The model must lift the win rate of the rows it CHOOSES to
  trade from 48% past 55% — that is the whole game, and it's a hard one.

No threshold tuning on test, no label sweeping, no per-fold cherry-picking.
Run from project root:
    python -m ml.model
--------------------------------------------------------------------
"""
import os
import statistics as st

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

from backtest.engine import load_data, run_backtest
from backtest.walk_forward import metrics_from_trades
from ml.features import make_features, FEATURE_COLUMNS
from ml.labeling import triple_barrier_labels, TP_PIPS, SL_PIPS
from ml.split import walk_forward_folds

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Same pairs + measured spreads as oos_split.py / run_backtest.py (apples-to-apples).
PAIRS = {
    "EUR_USD": {"data": "eurusd_1h_2y.csv", "spread_pips": 1.6},
    "GBP_USD": {"data": "gbpusd_1h_2y.csv", "spread_pips": 1.9},
    "USD_JPY": {"data": "usdjpy_1h_2y.csv", "spread_pips": 1.7},
}

THRESHOLD = 0.50    # P(up) >= this -> trade. Fixed, NOT tuned on test.


def models():
    """The two estimators, simplest first. Pipeline standardizes inside each fold
    (scaler.fit sees train only) so there's no cross-fold leakage through scaling.
    RF is depth-capped to blunt the obvious overfit on ~3k noisy rows."""
    return {
        "logreg": Pipeline([
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000)),
        ]),
        "forest": Pipeline([
            ("scale", StandardScaler()),
            ("clf", RandomForestClassifier(
                n_estimators=200, max_depth=4, min_samples_leaf=50,
                random_state=0, n_jobs=-1)),
        ]),
    }


def make_full_xy(pair, csv):
    """Full-length (NaN-containing) features + label, index = positional RangeIndex,
    so iloc[fold_idx] aligns with df.iloc[fold_idx] and the engine slice. Cleaning
    happens per-fold (drop NaN within the subset), never globally."""
    df = load_data(os.path.join(ROOT, "data", csv))
    X = make_features(df, pair)
    y = triple_barrier_labels(df, pair)
    return df, X, y


def subset(X, y, idx):
    """Positional fold subset with NaN rows (warm-up/tail) dropped jointly.
    Returns (Xc, yc, positions) where positions are the surviving RangeIndex ints
    — the bridge back to df rows / candle times for the backtest."""
    block = X.iloc[idx].copy()
    block["label"] = y.iloc[idx]
    block = block.dropna()
    return block[FEATURE_COLUMNS], block["label"].astype(int), block.index


def make_ml_strategy(buy_times):
    """Closure: BUY at decision candles the model flagged up, else flat. Long-only
    (the label is up-vs-not, so there's no honest short signal). Fill is the next
    open via the engine's pending_signal — identical no-lookahead rule the label
    used (entry = open[i+1])."""
    bt = set(buy_times)
    def strategy_fn(window, pip):
        return "BUY" if window.iloc[-1]["time"] in bt else None
    return strategy_fn


def backtest_fold(df, pair, spread_pips, test_idx, buy_positions):
    """Run the engine on the fold's test slice with a 15/15 bracket (= label
    barriers) and the model's BUY rows. Returns trade metrics dict."""
    test_start, test_end = test_idx[0], test_idx[-1] + 1
    window_df = df.iloc[test_start:test_end].reset_index(drop=True)
    buy_times = df.iloc[buy_positions]["time"]
    trades = run_backtest(
        window_df, pair, make_ml_strategy(buy_times),
        sl_pips=SL_PIPS, tp_pips=TP_PIPS,
        spread_pips=spread_pips, signal_exit=False,
    )
    return metrics_from_trades(trades)


def run_model(name, factory):
    print("\n" + "=" * 78)
    print(f"MODEL: {name}   (15/15 bracket = label barriers, real spread, long-only)")
    print("=" * 78)

    grand_pfs = []
    for pair, cfg in PAIRS.items():
        df, X, y = make_full_xy(pair, cfg["data"])
        folds = walk_forward_folds(len(df))

        print(f"\n----- {pair}  (spread {cfg['spread_pips']} pip) -----")
        print(f"{'fold':>4} {'tr':>5} {'te':>5} {'maj%':>6} {'acc%':>6} "
              f"{'auc':>5} {'trades':>7} {'win%':>6} {'PF':>6}")
        pair_pfs = []
        for fid, tr_idx, te_idx in folds:
            Xtr, ytr, _ = subset(X, y, tr_idx)
            Xte, yte, te_pos = subset(X, y, te_idx)

            model = factory()
            model.fit(Xtr, ytr)
            proba = model.predict_proba(Xte)[:, 1]
            pred = (proba >= THRESHOLD).astype(int)

            # classification gate: beat the majority-class baseline
            maj = max(yte.mean(), 1 - yte.mean()) * 100
            acc = (pred == yte.to_numpy()).mean() * 100
            auc = roc_auc_score(yte, proba) if yte.nunique() > 1 else float("nan")

            # trading gate: route predicted-up through the engine
            buy_positions = te_pos[pred == 1]
            m = backtest_fold(df, pair, cfg["spread_pips"], te_idx, buy_positions)
            pf = m["pf"]
            if m["n"] > 0 and pf != float("inf"):
                pair_pfs.append(pf); grand_pfs.append(pf)

            pf_s = " inf" if pf == float("inf") else f"{pf:6.2f}"
            win_s = "   nan" if m["n"] == 0 else f"{m['win_pct']:6.1f}"
            print(f"{fid:>4} {len(ytr):>5} {len(yte):>5} {maj:>6.1f} {acc:>6.1f} "
                  f"{auc:>5.2f} {m['n']:>7} {win_s} {pf_s}")

        if pair_pfs:
            above = sum(1 for p in pair_pfs if p > 1)
            print(f"  -> PF>1 in {above}/{len(pair_pfs)} folds | "
                  f"median PF {st.median(pair_pfs):.2f}")

    if grand_pfs:
        above = sum(1 for p in grand_pfs if p > 1)
        print(f"\n  ALL PAIRS x FOLDS: PF>1 in {above}/{len(grand_pfs)} | "
              f"median PF {st.median(grand_pfs):.2f} | "
              f"min {min(grand_pfs):.2f} | max {max(grand_pfs):.2f}")
    return grand_pfs


def main():
    print("Month 3 Session 2 — first ML direction model on the walk-forward bar.")
    print(f"label barriers tp={TP_PIPS}/sl={SL_PIPS} | trade threshold P(up)>={THRESHOLD}")
    print("Read CONSISTENCY across folds, not any one number (each test window is")
    print("~600-900 labeled trades' worth of candles; a single fold's PF is noisy).")
    for name, _ in models().items():
        run_model(name, lambda n=name: models()[n])
    print("\nVerdict rule (locked, ml/README.md): an edge must beat the base rate")
    print("AND clear these folds CONSISTENTLY (PF>1 across folds & pairs). One good")
    print("fold is one coin flip. If it doesn't clear, ship without it.")


if __name__ == "__main__":
    main()
