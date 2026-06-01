# Forex AI Trading System — Project Log & Roadmap

**Owner:** Harman · **GitHub:** `harmanpreetforex/forex-ai-system` (private)
**Platform:** macOS · Python 3.11 (venv) · OANDA fxTrade Practice (CAD, $100k virtual)
**Goal:** Build a forex algorithmic/AI trading system step by step — from raw market data, to a backtester, to a strategy, and eventually to a machine-learning model paper-traded on a live demo feed.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.11 |
| Data / math | pandas, numpy |
| Broker API | OANDA v20 REST (`oandapyV20`) |
| Charts | matplotlib |
| Secrets | python-dotenv (`.env`) |
| Version control | git + GitHub (private repo) |

---

## Current Repository Structure

```
forex-ai-system/
├── data/
│   ├── oanda_pipeline.py        # fetches OHLC from OANDA (paginated, multi-pair) -> CSV + chart
│   ├── eurusd_1h_2y.csv         # generated: EUR/USD 1H, ~2yr (~12.4k candles)  [gitignored]
│   ├── gbpusd_1h_2y.csv         # generated: GBP/USD 1H, ~2yr                    [gitignored]
│   ├── usdjpy_1h_2y.csv         # generated: USD/JPY 1H, ~2yr (JPY pip = 0.01)   [gitignored]
│   └── *_chart.png              # generated candlestick charts                    [gitignored]
├── src/
│   ├── day2_account_check.py    # authenticates + prints account balance
│   └── day3_live_prices.py      # pulls live/streaming prices
├── strategies/
│   ├── sma_crossover.py         # trend strategy: 10/30 moving-average crossover
│   └── rsi_reversal.py          # mean-reversion strategy: RSI overbought/oversold
├── risk/
│   └── position_sizer.py        # pips -> CAD P&L: risk-per-trade %, pip value × lot
├── backtest/
│   ├── engine.py                # the backtesting engine (strategy-agnostic; fixed-TP + signal-exit)
│   ├── run_backtest.py          # per-pair PAIRS config + portfolio comparison table
│   ├── oos_split.py             # chronological 70/30 in-sample/out-of-sample test
│   ├── walk_forward.py          # 4-window non-overlapping walk-forward test
│   └── results.py               # equity curve + metrics plotting helpers
├── results/                     # generated equity curves + trade-log CSVs        [gitignored]
├── notes/
├── 00_Master_Roadmap.md         # fixed reference: 6-month phase plan
├── 01_Progress_Tracker.md       # single source of truth for "where am I now" (update often)
├── 02_Risk_Rules.md             # risk framework / prop drawdown rules
├── venv/                        # gitignored
├── .env                         # secrets — gitignored, never committed
├── .env.example                 # variable names only, safe to commit
├── .gitignore
├── requirements.txt
├── LICENSE
└── README.md
```

> **Source of truth note:** day-by-day status lives in `01_Progress_Tracker.md` (kept current). This log captures the narrative arc; the tracker captures the latest state.

---

## Progress Log (Days 1–5)

### Day 1 — Foundations & Accounts
- Created OANDA fxTrade Practice account (CAD, $100k virtual money).
- Generated API token; created a dedicated project Gmail with 2FA.
- Created the private GitHub repo `forex-ai-system` with a Python `.gitignore` and MIT license.
- Added `.env` and `.DS_Store` to `.gitignore` from day one.
- Learned core forex vocabulary: currency pairs, pips, lots, spread, long/short, leverage, stop loss (via BabyPips Preschool + Kindergarten).

### Day 2 — Python Environment & First API Call
- Installed Python 3.11, created a virtual environment (`venv`).
- Installed `pandas numpy oandapyV20 matplotlib python-dotenv`; froze to `requirements.txt`.
- Wrote `day2_account_check.py` — authenticates with OANDA and prints the account balance.
- Established the project folder structure.

### Day 3 — Live Prices
- Wrote `day3_live_prices.py` to pull current/live market prices from the OANDA API.

### Day 4 — Historical Data Pipeline
- Built `oanda_pipeline.py` — a reusable script that fetches OHLC candles for any instrument/timeframe.
- Pulled EUR/USD, 1-hour candles, last 30 days → **528 candles**.
- Saved `eurusd_1h_30d.csv` (the data the backtester reads) and `eurusd_1h_30d_chart.png` (first visual look at the market).

### Day 5 — The Backtester (the core milestone)
- Built `backtest/engine.py`, a **strategy-agnostic** engine:
  - `load_data()` — reads and normalizes the CSV.
  - `get_pip()` — returns `0.01` for JPY pairs, `0.0001` otherwise.
  - `run_backtest()` — the candle-by-candle loop.
  - `check_exit()` / `open_new_trade()` — trade lifecycle.
  - `summarize()` — win rate, total/avg pips, profit factor.
- Wrote `strategies/sma_crossover.py` — the first tradeable idea (10/30 MA crossover).
- Wrote `backtest/run_backtest.py` — the glue that picks data + strategy and runs the engine.
- **Two honesty rules baked into the engine:**
  1. A signal on candle *i* is entered on candle *i+1*'s **open** (no lookahead bias).
  2. Exits use each candle's actual high/low; if both stop and target could hit in one candle, it assumes the **stop hit first** (pessimistic on purpose).
- Spread is subtracted from every trade so results aren't artificially rosy.
- **Security cleanup:** moved the OANDA token out of `oanda_pipeline.py` and into `.env` (loaded via `python-dotenv`), revoked the old token and generated a fresh one, and added a committed `.env.example`.
- Committed `backtest/` and `strategies/` to GitHub.

**Key learning from Day 5:** the basic SMA crossover was net negative on the test data — and that's the *point*. The value of a backtester is that it tells you the truth about an idea before any money is at risk.

---

## Progress Log (Days 6–14)

### Day 6 — Visible & trustworthy results
- Added running equity total + `plot_equity()`; equity curves saved to `results/`.
- Added **max drawdown** (pip + dollar) to `summarize()`.
- Wrote a full **trade-log CSV** (entry/exit/direction/pips/timestamps).
- Added `__pycache__/`, `results/`, `data/*.csv`, `data/*.png` to `.gitignore`.

### Day 7 — Second strategy + fair comparison
- Added `strategies/rsi_reversal.py` (mean reversion) alongside SMA.
- Runner compares strategies on the **same data + same costs** (apples to apples).

### Day 8 — Risk & position sizing (pips → real money)
- `risk/position_sizer.py`: risk-per-trade %, pip value × lot, simulated CAD balance.
- **Caught + fixed a max-drawdown $0.00 bug** (global-peak vs running-peak).
- Logged constant-FX-rate caveat (fixed 1.37 USD→CAD; JPY needs ~0.0092).

### Day 10 — Scale to multiple pairs
- Extended `oanda_pipeline.py` with pagination + multi-pair → EUR/GBP/JPY, ~2yr H1, ~12.4k candles each.
- Refactored `run_backtest.py` to a per-pair `PAIRS` config with a portfolio comparison table.
- Measured **real OANDA practice spreads** (EUR 1.6 / GBP 1.9 / JPY 1.7 pips, all-hours).

### Day 11 — Fair comparison closed (negative)
- Ran SMA crossover through the 3-pair harness: PF 0.79–0.84, win 31–32%, all pairs down 20–25%.
- Statistically identical to RSI reversal → **both trend and reversal entries are edgeless on raw H1 majors**; result dominated by spread + effectively-random entries.

### Day 12 — Signal-based exits + a contamination bug
- Added generic signal-exit to the engine (flatten on direction flip; next-open fill; no lookahead).
- **Caught + fixed a duplicate-import bug** in `run_backtest.py` that had silently made the "SMA baseline" actually re-run RSI.
- Signal-exit beat fixed-TP on all 3 pairs in-sample (EUR PF 1.11→1.38) — but GBP still negative; all in-sample.

### Day 13 — Out-of-sample (70/30) test
- `oos_split.py`: chronological 70/30, indicators warmed across the boundary, entry-time attribution.
- EUR/USD signal-exit SMA "survived" OOS (train PF 1.35 → test 1.44, stable win%). **Later superseded by Day 9-deep.**

### Day 9-deep — Walk-forward (the falsifier)
- `walk_forward.py`: 4 non-overlapping ~2000-candle windows, fixed params.
- EUR/USD PF per window 0.94 / 0.91 / 1.44 / 0.83 — PF>1 only 1/4, **median 0.93**.
- Conclusion: Day 13's OOS "survival" was one lucky window, **not an edge**. One OOS split is one coin flip; walk-forward is the minimum bar.

### Day 14 — Session/overlap filter (falsified)
- Tested London/NY overlap-only ({12,13,14,15} UTC) vs all-hours, same spreads, full 2yr / 3 pairs.
- EUR full-period PF 1.38→1.47 but only by cutting to 94 trades/2yr (~15–20 per walk-forward window = noise); JPY got *worse*, GBP stayed dead. No consistent cross-pair mechanism.
- **Conclusion:** the filter improves the exact aggregate metric Day 9-deep already proved lies, while shrinking the sample below the walk-forward floor — it self-defeats the only test that could validate it. Did **not** grid-search hours (would curve-fit an edgeless base).

**Headline through Day 14:** Month 2 (Strategy & Backtesting) closes **negative — no robust edge** found on raw H1 majors via this data. That's an honest finding about the market, not a process failure: every candidate was falsified for ~$0 *before* anything was stacked on top. Next: Month 3 ML feature work, held to the same walk-forward bar.

---

## Core Design Principle (carry this forward)

> The **engine** never knows what strategy it's running.

`run_backtest()` takes a `strategy_fn` as an argument. Every new idea is a new file in `strategies/` that returns `"BUY"`, `"SELL"`, or `None`. You test new ideas by swapping one import line — never by editing the engine. This separation is what makes everything below possible.

---

## Roadmap — Day 6 Onwards

### Day 6 — Make Results Visible & Trustworthy
Summary stats hide what matters most. Turn output into something you can judge.
- [ ] Track a running equity total across trades; add `plot_equity()` (matplotlib) and save the curve to a new `results/` folder.
- [ ] Add **max drawdown** (biggest peak-to-trough drop) to `summarize()` — the number that tells you if a strategy is *survivable*, not just profitable.
- [ ] Write a full **trade log CSV** to `results/` (entry, exit, direction, pips, timestamps) so you can inspect exactly what the engine did and catch logic bugs.
- [ ] Add `__pycache__/`, `results/`, and (your choice) `data/*.csv` + `data/*.png` to `.gitignore`.

### Day 7 — A Second Strategy + Fair Comparison
- [ ] Write a second strategy (e.g. `strategies/rsi_reversal.py` or a breakout).
- [ ] Refactor the runner to accept a strategy as an argument or loop over a list of strategies.
- [ ] Compare metrics side by side **on the same data and same costs** — apples to apples.

### Day 8 — Risk & Position Sizing (pips → real money)
- [ ] Convert pips into account-currency (CAD) P&L using pip value × lot size.
- [ ] Implement **risk-per-trade %** (e.g. risk 1% of balance per trade) to size lots dynamically.
- [ ] Track a simulated **account balance**, not just cumulative pips.

### Day 9 — Optimization & the Overfitting Trap
- [ ] Grid-search parameters (FAST/SLOW windows, SL/TP distances).
- [ ] Split data into **in-sample (train)** and **out-of-sample (test)** — only trust results on data the parameters never saw.
- [ ] Learn why a strategy that looks perfect on past data often fails forward (curve-fitting).

### Day 10 — Scale: Multiple Pairs & Timeframes
- [ ] Extend `oanda_pipeline.py` to fetch GBP/USD and USD/JPY (**remember the JPY pip = 0.01**).
- [ ] Run the backtest across all three pairs and review portfolio-level results.

### Days 11–13 — Introduce the "AI"
- [ ] Add `scikit-learn` to the environment.
- [ ] **Feature engineering** from OHLC: returns, distance from moving averages, RSI, recent volatility.
- [ ] **Labeling:** did price move +N pips within the next M candles? (your prediction target)
- [ ] Train a simple classifier (logistic regression or decision tree) on the **training split only**.
- [ ] Wrap the trained model as a `strategy_fn` — it plugs straight into your existing engine.
- [ ] Backtest the ML strategy on the **untouched test split** (separation is critical, or you're fooling yourself).

### Days 14+ — Forward Testing & Paper Trading
- [ ] Connect your strategy logic to the **live OANDA practice feed**.
- [ ] Paper-trade on the demo account in real time; log every decision.
- [ ] Compare live-demo results against the backtest — the real reality check.
- [ ] Add error handling, reconnection logic, scheduling, and risk kill-switches.

---

## A Realistic Note (worth re-reading before going live)

This is a software-engineering and learning project first. A strategy that's profitable in a backtest very often is not profitable live — because of overfitting, changing market conditions, slippage, and costs the backtest underestimates. The honest backtesting habits you built on Day 5 (no lookahead, pessimistic fills, spread included) exist precisely to keep you from fooling yourself. **Do not risk real money** until a strategy has survived out-of-sample testing *and* an extended period of live paper trading on the demo account — and even then, treat any capital as money you can afford to lose entirely. Most retail forex traders lose money; building the system is the rewarding part, and it's worth doing for the engineering and ML skills regardless of trading outcome.

---

*Last updated: Day 14 complete (Month 2 closed negative — no robust edge on raw H1 majors). Next up: Month 3 — ML feature engineering (scikit-learn), held to the same walk-forward bar. See `01_Progress_Tracker.md` for live status.*
