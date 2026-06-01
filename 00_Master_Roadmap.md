# 00 — Master Roadmap

The fixed reference for the whole project. Phase goals don't change; weekly tactics can flex.

## North Star
- **Literal goal:** $1M in 6 months via AI-powered forex trading.
- **Practical goal:** profitable system + passed prop challenge ($100K–$400K capital) + personal account $1K → $5K–$50K, with the **system + skills as the real asset.**

## Constraints
- Capital < $1,000 | Time 1–2 hrs/day | Solo | MacBook + Wi-Fi | Mitchell, ON, Canada.
- Budget: $540 min, $700–900 comfortable across 6 months.

## Tech stack
- **Have/free:** Python 3.11+, VS Code, GitHub, TradingView free, MacBook.
- **Set up:** OANDA Canada demo (broker + API), Anthropic API (Month 3), dedicated Gmail + folder, GitHub repo.
- **Libraries:** pandas, numpy, oandapyV20, backtesting.py or vectorbt, matplotlib, ta, scikit-learn (Month 3), python-dotenv.
- **Paid later:** AI API ~$10–20/mo (M3+), VPS $5–10/mo (M4+), prop challenge ~$540 (M5).

## Avoid
Paid courses, signal services, MQL5 EAs, Bloomberg Terminal, premium TradingView early, "AI trading bot" SaaS.

---

## Month 1 — Foundation
Learn forex mechanics (pairs, pips, lots, leverage, sessions). Set up Python + OANDA. Place demo trades programmatically. Build risk tooling.
**Deliverable:** end-to-end pipeline — data → signal → sized order → demo execution → logged result. (Strategy can be crude.)

- **Week 1:** Setup + forex literacy (OANDA, GitHub, BabyPips, auth + data + order scripts).
- **Week 2:** Market mechanics + clean 5-year dataset across 4 majors, indicators computed.
- **Week 3:** Risk management — position sizer, trade logger, kill switch (respect prop drawdown rules).
- **Week 4:** First strategy skeleton (SMA crossover) wired end-to-end; refactor into modules; month review.

## Month 2 — Strategy & Backtesting
Code 2–3 classic strategies (trend-following, mean reversion, breakout). Backtest properly with backtesting.py / vectorbt. Avoid look-ahead/survivorship bias and overfitting; account for spread/slippage. Produce real metrics (Sharpe, max drawdown, win rate, profit factor) and walk-forward test out-of-sample.
**Deliverable:** ≥1 strategy with a documented edge across multiple pairs and conditions.

## Month 3 — AI Layer
Add AI two ways: (1) Claude/GPT API for forex news sentiment as a filter/signal; (2) scikit-learn for direction prediction from engineered features (RSI, MACD, volatility, time-of-day). Goal = beat the Month 2 baseline by a measurable margin. If it doesn't beat baseline, ship without it.
**Deliverable:** AI-enhanced strategy with documented improvement over baseline.

## Month 4 — Live Demo Trading
Run the system 24/5 on demo for a full month. Track every trade. Handle API disconnects, weekend gaps, real slippage, news spikes, losing streaks. Optionally move to a cheap VPS. Iterate: fix breaks, tighten risk, cut underperformers.
**Deliverable:** 30 days live-demo with results within reasonable tolerance of backtest.

## Month 5 — Prop Firm Challenge
Buy an FTMO / FundedNext-style challenge (~$540, $100K account). Hit profit target (~8–10%) within the window while never breaching daily (5%) or max (10%) drawdown. Kill switch + risk framework carry you. Failing first try is normal — fee is tuition; post-mortem and retry.
**Deliverable:** funded account, or a clear post-mortem on what to fix.

## Month 6 — Scale & Compound
If funded: trade the real account, take 80–90% profit splits, reinvest into more challenges (running 2–5 funded accounts in parallel is the standard scaling path). Harden infrastructure; consider a second uncorrelated strategy. Cement the system as a long-term asset.
**Deliverable:** repeatable income process + a codebase I fully own and understand.

## Honest expected outcome
Most likely month-6 reality: $5K–$50K personal account growth, one or two funded accounts yielding ~$2K–$10K/mo in splits, and a genuine ML + finance + systems portfolio piece. The skill stack is the durable win regardless of the dollar figure.
