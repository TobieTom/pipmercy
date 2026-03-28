import asyncio
from calendar_alerts import (
    fetch_today_events,
    fetch_week_events,
    get_upcoming_events,
    format_calendar_message,
)

SEP = "-" * 50

async def main():
    # 1. Today's events
    print("TEST 1 — fetch_today_events()")
    print(SEP)
    today = await fetch_today_events()
    print(f"Fetched {len(today)} high-impact events today:")
    for e in today:
        wat = e["datetime_wat"].strftime("%H:%M WAT")
        print(f"  [{e['currency']}] {e['name']} @ {wat}")
    print()

    # 2. Week events (first 5)
    print("TEST 2 — fetch_week_events()")
    print(SEP)
    week = await fetch_week_events()
    print(f"Fetched {len(week)} high-impact events this week. First 5:")
    for e in week[:5]:
        day = e["datetime_utc"].strftime("%a %d %b")
        print(f"  [{e['currency']}] {e['name']} — {day}")
    print()

    # 3. Upcoming within 24 hours
    print("TEST 3 — get_upcoming_events(hours_ahead=24)")
    print(SEP)
    upcoming = get_upcoming_events(today, hours_ahead=24)
    print(f"{len(upcoming)} unreleased events in next 24 hours:")
    for e in upcoming:
        wat = e["datetime_wat"].strftime("%H:%M WAT")
        print(f"  [{e['currency']}] {e['name']} @ {wat} | F: {e['forecast']} | P: {e['previous']}")
    print()

    # 4. Full formatted calendar message
    print("TEST 4 — format_calendar_message(today)")
    print(SEP)
    print(format_calendar_message(today, title="📅 Today's High-Impact Events"))

asyncio.run(main())
