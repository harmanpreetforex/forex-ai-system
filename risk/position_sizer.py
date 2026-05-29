# risk/position_sizer.py
"""
Turns a risk decision into a concrete order size.

    risk_cash = balance * risk_pct
    loss_at_stop = units * stop_pips * pip_size * (quote_ccy -> account_ccy)
    -> solve for units

Account currency = CAD (OANDA practice). Majors are quoted in USD, so we
usually need a USD->CAD conversion to express pip value in CAD.
"""
from dataclasses import dataclass


def pip_size(pair: str) -> float:
    """0.01 for JPY pairs, 0.0001 otherwise. Mirrors engine.get_pip()."""
    return 0.01 if pair.upper().endswith("JPY") else 0.0001


@dataclass
class SizeResult:
    units: int          # OANDA lets you trade arbitrary unit counts
    risk_cash: float    # account ccy on the line if the stop hits
    pip_value: float    # value of 1 pip for 1 unit, in account ccy
    stop_pips: float


def position_size(balance, risk_pct, stop_pips, pair, quote_to_account):
    """
    balance          : current balance in account ccy (CAD)
    risk_pct         : fraction to risk, e.g. 0.01 for 1%
    stop_pips        : entry-to-stop distance, in pips (MUST be real)
    pair             : "EUR_USD", "USD_JPY", ...
    quote_to_account : rate converting the pair's QUOTE ccy into CAD
                         EUR_USD (quote USD) -> pass USD/CAD  (~1.37)
                         USD_JPY (quote JPY) -> pass JPY/CAD  (~0.0092)
                         a *_CAD pair        -> pass 1.0
    """
    if stop_pips <= 0:
        raise ValueError("stop_pips must be > 0 — every trade needs a real stop.")

    pip_value_per_unit = pip_size(pair) * quote_to_account   # CAD per pip per unit
    risk_cash = balance * risk_pct
    units = risk_cash / (stop_pips * pip_value_per_unit)

    return SizeResult(
        units=int(units),            # floor = conservative
        risk_cash=risk_cash,
        pip_value=pip_value_per_unit,
        stop_pips=stop_pips,
    )


if __name__ == "__main__":
    # Sanity checks — eyeball these against your gut.
    USDCAD = 1.37

    # Prop-style $100k, 1% risk, 30-pip stop:
    r = position_size(100_000, 0.01, 30, "EUR_USD", USDCAD)
    print(f"$100k  1%  30pip  -> {r.units:,} units  (risk ${r.risk_cash:,.2f})")

    # YOUR sub-$1k personal account, 0.5% while learning:
    r = position_size(900, 0.005, 30, "EUR_USD", USDCAD)
    print(f"$900  0.5%  30pip -> {r.units:,} units  (risk ${r.risk_cash:,.2f})")