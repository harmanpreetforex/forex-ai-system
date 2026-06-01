# Month 3 — AI Layer (ML direction model)

Session 1 deliverable: **environment + framing locked before any model touches the data.**
This folder is the scaffolding; no estimator has been fit yet, on purpose.

## The honest reframing (read first)
The roadmap framed Month 3 as *beating a Month 2 baseline*. **There is no profitable
baseline** — Days 9–14 closed the classical edge investigation *negative*: raw price+SMA
and RSI have no robust edge on H1 majors. So the real question is harder:

> Can engineered features find an edge the raw signal could not?

These features are all derived from the **same OHLC** that proved edgeless, so they may
inherit the same edgelessness. This is **one disciplined attempt**, not an open-ended
feature hunt. If it doesn't clear the bar below, the honest conclusion is that H1 majors
via this data don't offer a retail-accessible edge — and the banked value is the system +
skill stack, exactly as the North Star anticipated.

## Success criterion (locked — do not move mid-stream)
A model is a *candidate edge* only if, on **out-of-fold test data**, it:
1. **Beats the per-pair base rate** (the all-0 baseline): EUR 48.1% · GBP 49.7% · JPY 47.2%
   up-moves under the locked label. Beating accuracy isn't enough on its own —
2. **Translates to a backtest edge** routed through `backtest/engine.py` (real spread, SL/TP,
   no-lookahead fills), and
3. **Clears the 4-window walk-forward consistently** — the *same* bar (`backtest/walk_forward.py`
   geometry) that falsified the classical edges. Consistency across folds is the signal;
   a single good fold is one coin flip (Day 9-deep). PF>1 in 1/4 folds is a fail.

If it clears 1 but not 2–3, it's an interesting classifier with no tradeable edge — log it
and ship without it (roadmap: "If it doesn't beat baseline, ship without it").

## The three locked pieces
| File | What it locks | Leakage guard |
|------|---------------|---------------|
| `labeling.py` | **Triple-barrier label**: +15 / −15 pips, 24-candle horizon, first-touch, stop-wins-ties (identical to engine). Entry ref = next open. | Last `HORIZON` rows are NaN (future runs off the end) → must be dropped, never filled. |
| `features.py` | **Past-only features**: multi-horizon returns, distance-from-MA (pips + ATR units), RSI(14), ATR + return-std volatility, cyclical time-of-day. | `make_features(df[:i])` ≡ `make_features(df)[:i]` — deleting future rows can't change a feature. |
| `split.py` | **Chronological splits**: single 70/30 + **4-window walk-forward** (mirrors `backtest/walk_forward.py`). | **Purge/embargo** `HORIZON` rows around every boundary so no label window straddles train↔test. |

`build_dataset.py` ties them together and **asserts all three guards** across all pairs
without fitting anything. Run it first whenever this code changes — a broken guard fails
loud here, not silently in a backtest six steps later.

## Anti-curve-fit rules carried over from Months 2
- **Do NOT sweep tp/sl/horizon** to flatter results — that curve-fits the *label itself*,
  the subtlest Day 14 trap.
- **Do NOT grid-search session hours**; the model gets cyclical hour features and may learn
  to ignore them. We don't hand-pick the window.
- **Do NOT shrink TEST_SIZE** for more folds — thin windows fall below the noise floor and
  self-defeat the test (Day 14).
- A real edge shows **consistency across folds and pairs**; one fold up / others flat is
  variance wearing an edge costume.

## Run
```bash
python -m ml.build_dataset   # framing harness: class balance + fold geometry + leakage asserts
python -m ml.labeling        # label smoke test (one pair)
python -m ml.features        # feature smoke test + non-anticipation check
python -m ml.split           # fold geometry + purge check
```

## Session 2 outcome — the OHLC direction model is a clean NEGATIVE
`ml/model.py` fit logistic regression and a depth-capped random forest on each fold's
train rows and judged them on the locked bar. Result:

- **Trading gate: failed.** `PF>1 in 0/12` fold×pair runs, **both** models. Median PF ~0.76.
  Every fold loses to spread (15/15 bracket needs ~55% win; the chosen-trade win rate
  sits at ~48–53%).
- **Classification gate: failed.** Out-of-fold **test AUC = 0.49–0.53 ≈ coin flip** on every
  pair/model. Accuracy ≈ the majority-class baseline, sometimes below it.
- **It's edgelessness, not a bug.** A deep RF memorizes train (AUC **1.000**) while its test
  AUC stays **0.493** — the harness is sound; the model *can* fit, there's just nothing to
  generalize. LogReg's tiny train fit (~0.56) and the forest's overfit (~0.68) both collapse
  to ~0.50 OOS.

**Conclusion (honest, locked):** engineered features from H1-majors OHLC carry **no
out-of-sample directional edge** for this label — they inherited the edgelessness the raw
price+SMA signal already showed (Days 9–14). Per the roadmap, we **ship without it**. We did
NOT threshold-tune (pointless at AUC≈0.5), sweep the label, or add features to chase the 0/12.

This is a *market* finding, not a process failure: the disciplined attempt was made, held to
the same walk-forward bar that caught the classical false positives, and the bar did its job
for ~$0.

## What remains in Month 3 (different information, not the same OHLC)
The **news-sentiment** lever (Claude/GPT API) is the one untried Month 3 source whose
information is **not derived from the same OHLC**, so it does not inherit the edgelessness by
the argument above. It needs the Anthropic API set up (tracker "Accounts & access"). That —
not more OHLC features — is the only honest next swing inside Month 3.
