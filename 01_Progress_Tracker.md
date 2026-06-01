# 01 — Progress Tracker  (UPDATE ME OFTEN)

> This is the single source of truth for "where am I right now." Update it at the end of each work session or at least weekly. Any Claude chat should read this first.

## Current status
- **Today's date:** 1 June 2026
- **Current phase:** **Month 3 (AI Layer) — open and underway.** Classical-strategy exploration on raw H1 majors is exhausted with **no robust edge found**. Month 3 Session 1 (env + framing) is **done**: scikit-learn installed, labeling scheme + leak-free split discipline locked before any model touches the data.
- **Current week:** Risk tooling + honest-backtesting discipline are done. Week numbering has decoupled from the roadmap (calendar sessions ran ahead of phase days) — track by phase, not week, from here.
- **Overall vibe / momentum:** Discipline holding, and that's the headline. The walk-forward (Day 9-deep) and now the session filter (Day 14) both **falsified** candidate edges for ~$0, *before* anything got stacked on top. Engineering and validation habits are strong. There is still **no confirmed edge** — that's an honest finding about the market, not a failure of the process.

## Right now
- **Working on:** Month 3 Session 2 complete — first ML direction model fit and **falsified on the locked bar**. Logistic regression + depth-capped random forest, both routed through `backtest/engine.py` (15/15 bracket = label barriers, real spread). Result: **PF>1 in 0/12 fold×pair runs**, test AUC 0.49–0.53 (coin flip), for BOTH models. Confirmed it's edgelessness not a bug (deep RF memorizes train AUC 1.000, test 0.493). The scikit-learn OHLC-feature direction model is a **clean negative** — features inherited the raw-signal edgelessness. Shipping without it, per roadmap.
- **Blocked by:** nothing.
- **Next action (the one thing):** **Decision point — the only untried Month 3 lever is news-sentiment via the Claude/GPT API**, whose information is NOT derived from the same OHLC (so it doesn't inherit the edgelessness by the same argument). Requires Anthropic API setup (see "Accounts & access"). EITHER take that one swing, OR call Month 3 done-negative and bank the system+skill stack, moving to Month 4 (live-demo wiring) as the durable-asset play. Do NOT keep adding OHLC features to chase the 0/12 — that's the curve-fit trap. (Roadmap North Star always treated the system+skills as the real asset.)

## Account & money snapshot
- Personal account balance: _[$ — update]_
- Demo account balance: $100,000 (OANDA fxTrade Practice, CAD virtual)
- Spend so far (of $540–900 budget): **~$0** (all tooling free to date)
- Prop challenge status: not started

## Accounts & access set up
- [x] OANDA Canada demo + API token
- [x] GitHub repo (`forex-ai-system`)
- [x] Dedicated Gmail / folder
- [ ] TradingView free
- [ ] Anthropic API (Month 3 — only needed for the news-sentiment piece; the scikit-learn direction model is local and needs no API)
- [ ] VPS (Month 4, optional)

## Milestone checklist
**Month 1 — Foundation**
- Foundation pipeline (data → signal → sized order → execution → logged result): data + engine + position sizing + logging all built. **Live demo execution wiring still pending** (Month 4 / Days 14+ roadmap).

**Month 2 — Strategy & Backtesting**
- [x] 2–3 strategies coded (SMA crossover + RSI reversal; fixed-TP vs signal-exit variants)
- [x] Proper backtest engine + metrics (PF, win%, max drawdown $ + pip, equity curve, trade-log CSV)
- [x] Walk-forward / out-of-sample tested (single 70/30 OOS Day 13; 4-window walk-forward Day 9-deep; session filter Day 14)
- [x] **Edge investigation COMPLETE — conclusion: NO robust edge** on raw H1 majors. SMA crossover and RSI reversal both edgeless (Day 11); signal-exit improved in-sample but failed walk-forward (median PF 0.93, Day 9-deep); London/NY session filter did not rescue it and self-defeated validation by sample size (Day 14). This deliverable is **closed negative** — an honest result, not an open task.

**Month 3 — AI Layer**  ← now current
- [x] scikit-learn direction model (feature-engineered from OHLC) — **CLOSED NEGATIVE (Session 2).** LogReg + random forest, 13 past-only features, triple-barrier label, judged on the same 4-window walk-forward. PF>1 in 0/12 fold×pair runs; test AUC ~0.50 (coin flip). Deep RF memorizes train (AUC 1.000) but test 0.493 → harness sound, signal genuinely absent OOS. Engineered features inherited the raw price+SMA edgelessness, exactly as the Session-1 reframing feared. Ship without it (roadmap rule). An honest market finding, caught for ~$0 by the discipline.
- [ ] News sentiment via Claude/GPT API
- [ ] **Honest reframing (read this):** the roadmap framed Month 3 as *beating a Month 2 baseline*. There is **no profitable baseline to beat** — raw price+SMA has no edge here. So the real question changes to: *can engineered features find an edge the raw signal could not?* That is a **harder, lower-odds** question, and features derived from the same OHLC may inherit the same edgelessness. Worth **one disciplined attempt** held to the same walk-forward bar. If it doesn't clear that bar, the honest conclusion is that H1 majors via this data don't offer a retail-accessible edge — and the banked value is the **system + skill stack**, exactly as the roadmap's North Star anticipated.

**Month 4 — Live Demo**
- [ ] System runs 24/5 on demo
- [ ] 30 days logged
- [ ] Results within tolerance of backtest

**Month 5 — Prop Challenge**
- [ ] Challenge purchased
- [ ] Profit target hit / drawdown respected
- [ ] Passed (or post-mortem written)

**Month 6 — Scale**
- [ ] Funded account live
- [ ] Profit split taken
- [ ] Scaling plan / 2nd strategy

## Session log (newest at top)
> One line per session: date — what I did — what I learned — what broke.

Month 3 · Session 2 (1 Jun): First ML direction model — **falsified on the locked bar, clean negative.** Fit logistic regression + depth-capped random forest (depth 4, min_leaf 50) on each walk-forward fold's TRAIN rows (StandardScaler fit on train only, inside a Pipeline → no scaling leakage), predicted P(up) on TEST rows, routed predicted-up as long-only BUY through backtest/engine.py with a 15/15 bracket (= label barriers) and real measured spread (1.6/1.9/1.7). RESULT: PF>1 in **0/12** fold×pair runs for BOTH models (median PF ~0.76–0.77, range 0.59–0.97). Test AUC **0.49–0.53 ≈ coin flip** everywhere; accuracy ≈ majority baseline, sometimes below. Spread math is the executioner: 15/15 with ~1.6 spread needs ~55% win rate, chosen-trade win rate sits at ~48–53%. Ran a train-vs-test AUC diagnostic to rule out a broken harness: deep RF **memorizes train AUC 1.000 but tests 0.493**, logreg train ~0.56→test ~0.50, forest train ~0.68→test ~0.50 — so the wiring is sound and the model CAN fit; there is simply no out-of-sample directional signal to generalize. CONCLUSION: engineered features from H1-majors OHLC carry no edge for this label — they inherited the raw price+SMA edgelessness (Days 9–14), exactly as the Session-1 honest reframing predicted. Shipped without it (roadmap: "if it doesn't beat baseline, ship without it"). Did NOT threshold-tune (pointless at AUC≈0.5 — no ranking ability), sweep the label, or pile on OHLC features to chase the 0/12. Cost ~$0 (local sklearn). Only untried Month 3 lever left = news-sentiment via Claude API (different info source, not the same OHLC).
Lessons: (1) Test AUC≈0.50 with train AUC clearly >0.50 (and a deep model hitting 1.000) is the textbook fingerprint of NO edge + a WORKING harness — always run that train/test diagnostic before trusting a negative, so you don't mistake a bug for a market finding (or vice versa). (2) When AUC≈0.5 there is no ranking signal, so threshold/precision tuning cannot help — recognizing that stopped a curve-fit spiral cold. (3) The spread breakeven win rate (~55% here) is the real bar a classifier must clear, not 50% — a model can be "better than a coin flip" and still lose every fold. (4) Same-source features inheriting same-source edgelessness is now an OBSERVED result, not just a worry: the next genuine swing has to bring NEW information (news/sentiment), not re-encode OHLC.

Month 3 · Session 1 (1 Jun): Opened the AI layer — environment + framing ONLY, no model fit (deliberate). Installed scikit-learn 1.8.0 (+scipy/joblib/threadpoolctl) into venv + requirements.txt. Built `ml/` scaffolding: (1) `labeling.py` — triple-barrier label (+15/−15 pips, 24-candle horizon, first-touch, stop-wins-ties exactly like engine.check_exit; entry ref = next open, no lookahead). (2) `features.py` — past-only features (multi-horizon log returns, distance-from-MA in pips & ATR units, RSI(14) reused from rsi_reversal, ATR + return-std volatility, cyclical sin/cos hour). (3) `split.py` — chronological 70/30 + 4-window walk-forward mirroring backtest/walk_forward.py geometry, with **purge/embargo of HORIZON rows around every boundary** so no label window straddles train↔test. (4) `build_dataset.py` — ties them together and ASSERTS three leakage guards (feature non-anticipation, label-tail NaN, fold purge) across all 3 pairs without fitting anything. All guards pass. KEY FRAMING NUMBER: under a symmetric 1:1 barrier the up-move base rate is ~47–50% (EUR 48.1 / GBP 49.7 / JPY 47.2) — almost a coin flip, so that's the honest all-0 baseline the model must beat. Success bar (locked in ml/README.md): beat base rate AND clear the 4-window walk-forward consistently — not a single split. Resisted fitting a model this session and resisted any label/hour sweeping. Cost ~$0 (local sklearn, no API).
Lessons: (1) Lock the label + split BEFORE modelling — the leakage guards are assert-backed so a future edit that breaks non-anticipation fails LOUD in build_dataset, not silently in a backtest. (2) A symmetric triple-barrier base rate near 50% is itself a finding: there's no free directional asymmetry to exploit; any edge must come from the features conditioning that ~48%. (3) Purge/embargo = HORIZON is mechanical, not a vibe — the label literally reads HORIZON candles ahead, so that's exactly how far the boundary leaks.

Day 14: Session-filter test — signal-exit SMA, all-hours vs London/NY overlap ({12,13,14,15} UTC), SAME spread (1.6/1.9/1.7), full 2yr / 3-pair. EUR PF 1.38→1.47 but win% 34.0→30.9 and n 306→94 (PF rose only via bigger avg pip on fewer trades). JPY got WORSE 1.16→1.08; GBP still dead 0.85→0.89. No consistent cross-pair effect (one up, one down, one flat = thin-sample variance signature, not a mechanism). Returns fell hard (EUR +41.8%→+15.0%, JPY +21.3%→+2.4%) — lower drawdowns are mostly just from trading ~70% less. CONCLUSION: full-period PF is the exact metric Day 9-deep proved lies for this setup (all-hours aggregate 1.38 vs walk-forward median 0.93), so 1.47 is untrustworthy until windowed — AND 94 EUR trades/2yr ≈ 15–20 per walk-forward window = noise, which means the filter **self-defeated the only test that could validate it**. Raw price+SMA has no robust edge on H1 majors; the filter doesn't rescue it. Fallback fires → Month 3 ML feature work next. Did NOT grid-search hours. Cost ~$0.
Lessons: (1) A filter that improves the full-period aggregate isn't validated — it's validated only if it survives walk-forward, and shrinking the sample below the windowing floor makes that impossible. (2) PF↑ while win%↓ on fewer trades is not automatically "better trades"; check whether the aggregate metric is one you've already caught lying. (3) Inconsistent cross-pair response = variance, not edge.

Day 9-deep: Walk-forward (4 non-overlapping ~2000-candle test windows, fixed params, signal-exit SMA, EUR/USD 2yr). PF per window 0.94 / 0.91 / 1.44 / 0.83 — PF>1 only 1/4, median 0.93, 265 trades. Win% unstable across windows (31–44%) vs the stable 33.9/34.1 within the Day 13 split. Conclusion: Day 13's OOS "survival" was a single lucky period (the 1.44 window), not an edge. Raw signal-exit SMA on H1 EUR/USD has no robust edge. Do NOT grid-search (would curve-fit an edgeless base). Next: session/overlap filter on the same 4 windows [→ became Day 14, falsified].

Day 13: Out-of-sample test (chronological 70/30, warm indicators across boundary, entry-time attribution) of signal-exit SMA. EUR/USD held OOS: train PF 1.35 → test 1.44 (win% 33.9/34.1, stable). USD/JPY degraded but stayed positive: 1.18 → 1.09 (win% 19/28). GBP/USD consistently negative: 0.89 → 0.77. Win rates near-identical train vs test on all pairs = stable behaviour, not curve-fit. First strategy to survive OOS. [SUPERSEDED by Day 9-deep: walk-forward falsified this.]
Caveats: test n small (EUR 85, JPY 94) — JPY 1.09 not trustworthy on that sample. One split = one data point. GBP dead → per-pair effect, not a systemic H1-majors edge.

Day 12: Added generic signal-based exits to engine (signal_exit flag + exit_reason tag; engine stays strategy-agnostic — flattens on direction flip, fills next-open, no lookahead). Caught + fixed contamination: Day 11's "SMA baseline" was actually rsi_reversal re-run (duplicate import silently overrode the strategy selector in run_backtest.py). Re-established real SMA fixed-TP baseline: EUR 1.11 / GBP 0.70 / JPY 1.04 PF. Then two-variant harness (fixed-TP vs signal-exit, same data/costs/risk): signal-exit beat fixed-TP on all 3 pairs — EUR 1.11→1.38, GBP 0.70→0.85, JPY 1.04→1.16. Win% fell (38→34, 29→21, 37→21) while PF rose = trend signature; 40-pip TP cap was capping runners. Not an edge: GBP still negative (−20.6%), all in-sample, drawdowns grew with returns (EUR pip-DD 292→479). Signal-exit is now default exit for trend strategies.
Lessons: (1) Duplicate import = silent strategy swap; "identical to RSI" was the symptom that should've caught it sooner. (2) Exit logic is a real lever, not just entry signal. (3) Win%↓ + PF↑ is the trend-following fingerprint, not a bug.

Day 11: Ran Day-5 SMA crossover (10/30) through the 3-pair harness — same data, costs, 1% risk, 2:1 R:R. Result: EUR 0.81 / GBP 0.79 / JPY 0.84 PF, win 31–32%, all down 20–25%, ~1000 trades. Statistically identical to rsi_reversal → trend AND reversal entry signals both edgeless on raw H1 majors; result dominated by spread + random entry, not directional thesis. Day 7 fair-comparison deliverable closed. Caveat: fixed 40-pip target handicaps trend strategies (caps the runner). Next: test SMA with "exit on opposite cross" to resolve signal-vs-exit before moving to filters/ML.

Day 10: Extended oanda_pipeline.py (pagination + multi-pair) → pulled EUR/GBP/JPY, 2yr H1, ~12.4k candles each, verified distinct by price scale. Refactored run_backtest.py to a per-pair PAIRS config (correct quote→CAD rates + real measured spreads) with a portfolio comparison table. Measured real OANDA practice spreads (EUR 1.6 / GBP 1.9 / JPY 1.7 pip median, all-hours). Result: rsi_reversal has no edge — PF 0.79–0.84, win 31–32% vs 33.3% breakeven = random entries + spread drag, three independent pairs, ~1000 trades total.
Lessons: (1) FX rate cancels in fixed-fractional sizing — only spread bites the dollar curve. (2) Don't run OOS on an in-sample loser. (3) Reversal signal + 2:1 trend payoff is thesis-incoherent. (4) Measured all-hours spread is an argument for a session filter — overlap-only trading would pay ~1.0 not ~1.7. [Tested Day 14: filter didn't rescue the edge.]

Day 8: Position sizing + CAD account sim (risk-per-trade %, pip value × lot, simulated balance). Caught + fixed max-drawdown $0.00 bug (global-peak vs running-peak). Logged constant-FX-rate caveat (fixed 1.37 USD→CAD; JPY needs ~0.0092).

- _[YYYY-MM-DD] — set up project + files — ready to start Day 1_

## Open questions for Claude
- **ML framing (next session):** with no profitable baseline to beat, the ML task is "find an edge, not enhance one." Decide up front what counts as success (must clear the same 4-window walk-forward, not just a single split) so we don't move the goalposts mid-stream the way Day 13 nearly let us.
- **Labeling + split discipline:** lock the labeling scheme and a strictly chronological train/test split (no leakage across the boundary, warm indicators correctly) BEFORE training anything. This is where ML projects fool themselves.
- **Month 5:** prop firms run MetaTrader, not OANDA — execution layer will need an MQL5 port or a Python-MT5 bridge; keep order code isolated behind one function now to make that cheap later.

## Things that broke / lessons (the gold)

**Session filter improves the aggregate but can't be validated (Day 14):** the London/NY overlap filter nudged EUR full-period PF 1.38→1.47, but (a) full-period PF is the exact metric Day 9-deep proved lies for this strategy (walk-forward median 0.93), so the improvement is untrustworthy until windowed, and (b) the filter cut EUR to 94 trades/2yr ≈ 15–20 per walk-forward window, which is noise — so it self-defeated the only test that could confirm it. Lesson: a filter that only improves the full-period aggregate has improved nothing you can trust; and any "improvement" that shrinks your sample below the walk-forward floor has destroyed its own evidence. Also: an edge mechanism should show up across pairs — EUR up, JPY down, GBP flat is variance wearing an edge costume. Resisted the temptation to grid-search session hours ({13,14}, wider "active hours") to keep the idea alive — that's curve-fitting an edgeless base, the trap the roadmap put walk-forward ahead of.

**False-positive edge from a single OOS split (Day 9-deep):** Day 13's 70/30 split showed EUR/USD signal-exit SMA "surviving" OOS (test PF 1.44). Walk-forward across 4 windows revealed PF>1 in only 1/4 (the 1.44 was one lucky quarter, the same period the 70/30 test happened to land on); median 0.93. Lesson: one OOS split is one coin flip — "survived OOS" on a single split is not an edge. Walk-forward (multiple rolling windows) is the minimum bar before trusting a result, and the tell of a real edge is STABLE behaviour across windows (here win% swung 31–44%, the opposite of stable). This is exactly why the roadmap put walk-forward before grid-search/ML: it caught the false positive for ~$0 before anything got built on top.

**Max-drawdown $0.00 bug (Day 8):** dollar drawdown computed the drop after the GLOBAL peak instead of using a RUNNING peak → reports $0 whenever the equity curve ends at its high. Fixed with a running-peak loop. Lesson: max drawdown is the survivability number the prop limits (5% daily / 10% total) get checked against — a function that can silently report $0 is the kind of bug that tells you a strategy is safe when it isn't. What exposed it: pip drawdown (105) and $ drawdown ($0) disagreed when they should agree. Keep cross-checking two numbers that ought to match.

**Constant-FX-rate caveat (Day 8):** backtest converts USD→CAD at a fixed 1.37, not each trade's actual-timestamp rate. Error is small over 30 days; do NOT mistake the dollar curve for precision it lacks. Fix when going multi-month. Also: quote_to_account is per-pair — USD/JPY needs JPY→CAD (~0.0092), not 1.37. Handled Day 10.

**Duplicate-import contamination (Day 12):** a second strategy import in run_backtest.py silently overrode the strategy selector, so the "SMA baseline" was actually RSI re-running. Symptom was results being statistically identical to RSI — that coincidence should have triggered suspicion sooner. Lesson: when two things that should differ come out identical, treat it as a bug signal, not a finding. (Same family caught again Day 14 in engine.py: a duplicated `elif` dead-code branch in the signal-exit logic — removed.)