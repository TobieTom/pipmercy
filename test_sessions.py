from sessions import (
    get_current_session,
    get_session_for_pair,
    format_session_message,
    should_warn_about_session,
)

SEP = "-" * 55

# 1. Current session
print("TEST 1 — get_current_session()")
print(SEP)
s = get_current_session()
print(f"Session:        {s['name']}")
print(f"WAT time:       {s['current_wat']}")
print(f"UTC time:       {s['current_utc']}")
print(f"Volatility:     {s['volatility']}")
print(f"Best pairs:     {', '.join(s['best_pairs']) or 'None'}")
print(f"Avoid pairs:    {', '.join(s['avoid_pairs']) or 'None'}")
print(f"Is weekend:     {s['is_weekend']}")
print(f"Next session:   {s['next_session_name']} in {s['minutes_to_next_session']} mins")
print()

# 2. Pair advice — EURUSD
print("TEST 2 — get_session_for_pair('EURUSD')")
print(SEP)
info = get_session_for_pair("EURUSD")
print(f"Optimal: {info['optimal']} | Caution: {info['caution']}")
print(info["message"])
print()

# 3. Pair advice — USDJPY
print("TEST 3 — get_session_for_pair('USDJPY')")
print(SEP)
info = get_session_for_pair("USDJPY")
print(f"Optimal: {info['optimal']} | Caution: {info['caution']}")
print(info["message"])
print()

# 4. Full session message
print("TEST 4 — format_session_message()")
print(SEP)
print(format_session_message())
print()

# 5. Session warning for EURUSD
print("TEST 5 — should_warn_about_session('EURUSD')")
print(SEP)
warning = should_warn_about_session("EURUSD")
print(warning if warning else "None — no warning (EURUSD is fine in current session)")
