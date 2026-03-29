from database import init_db
from streaks import (
    update_today_streak,
    get_current_journaling_streak,
    get_current_win_streak,
    get_current_loss_streak,
    get_discipline_score,
    format_streak_message,
    check_and_warn_loss_streak,
)

SEP = "-" * 50

init_db()

# 1. Simulate today's activity
print("STEP 1 — update_today_streak(traded=True, journaled=True, respected_risk=True)")
print(SEP)
update_today_streak(traded=True, journaled=True, respected_risk=True)
print("Done.")
print()

# 2. Journaling streak
print("STEP 2 — get_current_journaling_streak()")
print(SEP)
j = get_current_journaling_streak()
print(f"Journaling streak: {j} day(s)")
print()

# 3. Win/loss streaks
print("STEP 3 — win/loss streaks")
print(SEP)
print(f"Win streak:  {get_current_win_streak()}")
print(f"Loss streak: {get_current_loss_streak()}")
print()

# 4. Discipline score
print("STEP 4 — get_discipline_score(7)")
print(SEP)
sd = get_discipline_score(7)
for k, v in sd.items():
    print(f"  {k}: {v}")
print()

# 5. Full dashboard
print("STEP 5 — format_streak_message()")
print(SEP)
print(format_streak_message())
print()

# 6. Loss streak warning
print("STEP 6 — check_and_warn_loss_streak()")
print(SEP)
warning = check_and_warn_loss_streak()
print(warning if warning else "None — no warning triggered")
