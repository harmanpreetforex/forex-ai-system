"""
risk/kill_switch.py
--------------------------------------------------------------------
Month 4, Session 4: the LIVE KILL SWITCH.

Enforces the circuit breakers from 02_Risk_Rules.md, which are deliberately
TIGHTER than the prop limits so there's always headroom:

    daily loss   >= 3%  -> no new entries for the rest of the (UTC) day
    weekly loss  >= 5%  -> no new entries for the rest of the (ISO) week
    total drawdown >= 10% (from initial balance) -> halt entirely (the prop
                          "instant fail" line; should NEVER be reached if the
                          3%/5% breakers do their job, but it's the last fence)

Because our daily breaker (3%) sits under the prop daily cap (5%), respecting
this switch automatically respects the prop daily limit too.

WHAT IT DOES NOT DO: it never closes existing trades. Every position already
carries a stop attached on fill (execution layer), so open risk is bounded; the
switch only BLOCKS NEW ENTRIES. Yanking open trades on a drawdown would just
realize losses early and fight the stops we set deliberately.

Equity basis = NAV (balance + unrealized P/L), not balance — prop firms check
floating equity, and a daily limit you can dodge by not closing losers is no
limit. Drawdown uses anchors captured at each period boundary (Day-8 lesson:
measure the drop from a real running/period peak, never a global one).

State persists to results/kill_switch_state.json so a restart mid-day doesn't
reset the anchors and silently re-enable trading after a breach. results/ is
gitignored (runtime data).
--------------------------------------------------------------------
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "results" / "kill_switch_state.json"

DAILY_LIMIT  = 0.03      # 02_Risk_Rules: daily loss limit (tighter than prop 5%)
WEEKLY_LIMIT = 0.05      # 02_Risk_Rules: weekly loss limit
TOTAL_LIMIT  = 0.10      # prop max total drawdown (catastrophic backstop)


class KillSwitch:
    def __init__(self, state_path=STATE_PATH):
        self.state_path = Path(state_path)
        self.state = self._load()

    def _load(self):
        if self.state_path.exists():
            return json.loads(self.state_path.read_text())
        return {}

    def _save(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, indent=2))

    def check(self, nav, now=None):
        """Given current NAV, roll the period anchors and decide if new entries
        are allowed. Returns (allowed: bool, reason: str|None, metrics: dict).
        Persists state every call so anchors survive restarts."""
        now = now or datetime.now(timezone.utc)
        day_key = now.strftime("%Y-%m-%d")
        week_key = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"
        s = self.state

        # First ever call: seed the initial baseline + both period anchors.
        if "initial_nav" not in s:
            s["initial_nav"] = nav
        # New UTC day -> reset the daily anchor to today's opening NAV.
        if s.get("day_key") != day_key:
            s["day_key"] = day_key
            s["day_start_nav"] = nav
        # New ISO week -> reset the weekly anchor.
        if s.get("week_key") != week_key:
            s["week_key"] = week_key
            s["week_start_nav"] = nav
        s["peak_nav"] = max(s.get("peak_nav", nav), nav)

        daily_dd  = (s["day_start_nav"]  - nav) / s["day_start_nav"]
        weekly_dd = (s["week_start_nav"] - nav) / s["week_start_nav"]
        total_dd  = (s["initial_nav"]    - nav) / s["initial_nav"]
        self._save()

        metrics = {"nav": nav, "daily_dd": daily_dd, "weekly_dd": weekly_dd,
                   "total_dd": total_dd, "day_start_nav": s["day_start_nav"],
                   "week_start_nav": s["week_start_nav"], "initial_nav": s["initial_nav"]}

        # Order matters: report the most severe breach first.
        if total_dd >= TOTAL_LIMIT:
            return False, f"TOTAL drawdown {total_dd:.1%} >= {TOTAL_LIMIT:.0%} (HALT)", metrics
        if weekly_dd >= WEEKLY_LIMIT:
            return False, f"weekly loss {weekly_dd:.1%} >= {WEEKLY_LIMIT:.0%} (stop for week)", metrics
        if daily_dd >= DAILY_LIMIT:
            return False, f"daily loss {daily_dd:.1%} >= {DAILY_LIMIT:.0%} (stop for day)", metrics
        return True, None, metrics


if __name__ == "__main__":
    # Offline self-test on a temp state file: walk NAV down through each breaker.
    import tempfile, os
    tmp = Path(tempfile.mkdtemp()) / "ks.json"
    ks = KillSwitch(state_path=tmp)
    t = datetime(2026, 6, 1, 0, 30, tzinfo=timezone.utc)   # Monday

    def show(nav, now, note):
        ok, why, m = ks.check(nav, now)
        print(f"  NAV {nav:>8.0f} {note:<22} -> {'ALLOW' if ok else 'BLOCK'}"
              f"  (d {m['daily_dd']:+.1%} w {m['weekly_dd']:+.1%} tot {m['total_dd']:+.1%})"
              + (f"  [{why}]" if why else ""))

    print("Day 1 (initial 100000):")
    show(100000, t, "open")
    show(98000, t.replace(hour=10), "down 2% intraday")          # allow
    show(96900, t.replace(hour=14), "down 3.1% intraday")        # BLOCK daily
    from datetime import timedelta
    t2 = t + timedelta(days=1)                                   # Tuesday — daily resets
    print("Day 2 (daily anchor resets to 96900):")
    show(96900, t2, "open")                                       # allow (new day)
    show(94800, t2.replace(hour=12), "day -2.2% / week -5.2%")    # BLOCK weekly
    print("Catastrophic:")
    show(89000, t2.replace(hour=15), "total -11% from initial")  # BLOCK total
