# 02 — Risk Rules  (NON-NEGOTIABLE)

These exist so the account survives long enough for the edge to play out. Claude must never suggest anything that violates these, and should flag me if I try to.

## The prime directive
**Protect capital first. Returns are second.** A strategy that survives a bad month beats one that wins big then blows up.

## Per-trade rules
- Risk **≤ 1%** of account per trade (0.5% while learning). Never "just this once" more.
- Every trade has a **stop loss set at entry**. No exceptions, no mental stops.
- Minimum reward:risk of **1:1.5** unless a backtest justifies otherwise.
- Position size is **calculated**, never eyeballed (use `position_sizer`).

## Daily / weekly circuit breakers (the kill switch)
- **Daily loss limit: 3%.** Hit it → no new trades that day.
- **Weekly loss limit: 5%.** Hit it → stop for the week, review.
- These are tighter than prop limits on purpose, to leave margin.

## Prop firm survival math (FTMO-style $100K)
- **Max daily drawdown: 5%** ($5,000) — breach = instant fail.
- **Max total drawdown: 10%** ($10,000) — breach = instant fail.
- Profit target: typically **8–10%**.
- Rule of thumb: trade so a *terrible* day still leaves comfortable headroom under 5%. Risking 1%/trade with a 3% daily kill switch keeps me safe.

## Backtesting honesty (so the edge is real, not imaginary)
- Always model **spread + slippage + commission** (OANDA EUR/USD ~1 pip).
- No **look-ahead bias** — never use data the strategy couldn't have had in real time.
- Test **out-of-sample** / walk-forward, not just the period I tuned on.
- Beware **overfitting**: more parameters = more lies. Simpler usually generalizes better.
- A backtest is a hypothesis, not a promise.

## Behavioral rules (the part that actually blows accounts)
- **No revenge trading** after a loss. Walk away; the kill switch enforces it.
- **No moving stops** to avoid taking a loss.
- **No risking money I can't afford to lose.** Sub-$1K personal account = learning capital.
- **No new shiny tool/strategy** mid-stream without finishing the current test.
- Losing streaks are expected (a 45% win rate means ~4–5 losses in a row happen normally). Don't change the system mid-streak on emotion.

## Money / scope discipline
- Stay within the ~$540–900 six-month budget.
- No paid courses, signals, marketplace EAs, or trading-bot SaaS.
- The prop challenge fee is **tuition**, not a bet — only pay it when the system has earned the right (passed Month 4 live demo).

## Not financial advice
I (Harman) own every trading decision. Claude is a mentor and engineer, not a licensed advisor. Forex trading carries a high risk of loss.
