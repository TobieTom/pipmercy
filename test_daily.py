from database import init_db
from journal import get_today_summary, format_daily_summary

SEP = "-" * 55

init_db()

# 1. Raw summary dict
print("TEST 1 — get_today_summary() raw dict")
print(SEP)
summary = get_today_summary()
for k, v in summary.items():
    if k not in ("best_today", "worst_today"):
        print(f"  {k}: {v}")
print(f"  best_today: {summary['best_today']['pair'] + ' ' + summary['best_today']['direction'] if summary['best_today'] else None}")
print(f"  worst_today: {summary['worst_today']['pair'] + ' ' + summary['worst_today']['direction'] if summary['worst_today'] else None}")
print()

# 2. Full formatted message
print("TEST 2 — format_daily_summary() formatted output")
print(SEP)
print(format_daily_summary(summary))
print()

# 3. No-trades scenario
print("TEST 3 — format_daily_summary() with no trades today")
print(SEP)
empty_summary = {
    "date": "29 Mar 2026",
    "trades_opened": 0,
    "trades_closed": 0,
    "wins_today": 0,
    "losses_today": 0,
    "pnl_today": 0.0,
    "open_trades": 2,
    "open_exposure": 1.50,
    "weekly_pnl": 0.50,
    "weekly_trades": 3,
    "best_today": None,
    "worst_today": None,
}
print(format_daily_summary(empty_summary))
