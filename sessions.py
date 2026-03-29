from datetime import datetime, timezone, timedelta

_WAT = timezone(timedelta(hours=1))

SESSIONS = {
    "asian": {
        "name": "Asian Session 🌏",
        "start_utc": 0,
        "end_utc": 9,
        "wat_start": "1:00 AM",
        "wat_end": "10:00 AM",
        "character": "Low volatility, range-bound. Good for JPY, AUD, NZD pairs.",
        "best_pairs": ["USDJPY", "AUDUSD", "NZDUSD", "GBPJPY", "EURJPY"],
        "avoid_pairs": ["EURUSD", "GBPUSD"],
        "tip": "Asian session tends to range. If you're trading EUR/GBP pairs, wait for London.",
        "volatility": "low",
    },
    "london": {
        "name": "London Session 🇬🇧",
        "start_utc": 8,
        "end_utc": 16,
        "wat_start": "9:00 AM",
        "wat_end": "5:00 PM",
        "character": "Highest volume session. Strong trends form here. EUR, GBP pairs most active.",
        "best_pairs": ["EURUSD", "GBPUSD", "EURGBP", "GBPJPY", "EURJPY", "USDCHF"],
        "avoid_pairs": [],
        "tip": "London open (9-11 AM WAT) is the most powerful time to trade. Breakouts are common.",
        "volatility": "high",
    },
    "london_ny_overlap": {
        "name": "London/NY Overlap 🔥",
        "start_utc": 13,
        "end_utc": 16,
        "wat_start": "2:00 PM",
        "wat_end": "5:00 PM",
        "character": "Peak liquidity. Most volatile window of the day. Best spreads, biggest moves.",
        "best_pairs": ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "XAUUSD"],
        "avoid_pairs": [],
        "tip": "This is the golden window. Most professional setups trigger here. Be sharp.",
        "volatility": "very_high",
    },
    "new_york": {
        "name": "New York Session 🗽",
        "start_utc": 13,
        "end_utc": 22,
        "wat_start": "2:00 PM",
        "wat_end": "11:00 PM",
        "character": "USD-heavy session. Major US data releases hit here. Volatile around news.",
        "best_pairs": ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "USDCHF", "XAUUSD"],
        "avoid_pairs": [],
        "tip": "Watch for USD news at 2:30 PM WAT (NFP, CPI, FOMC). Avoid trading 10 mins before/after.",
        "volatility": "high",
    },
    "dead_zone": {
        "name": "Dead Zone 💤",
        "start_utc": 22,
        "end_utc": 24,
        "wat_start": "11:00 PM",
        "wat_end": "1:00 AM",
        "character": "Market closes NY, Asia not open yet. Very thin liquidity, wide spreads.",
        "best_pairs": [],
        "avoid_pairs": ["EURUSD", "GBPUSD", "USDJPY"],
        "tip": "Avoid new positions during this window. Spreads are wide and moves are unreliable.",
        "volatility": "very_low",
    },
}

# Order of sessions by UTC start for next-session calculation
_SESSION_ORDER = ["asian", "london", "london_ny_overlap", "new_york", "dead_zone"]

_VOLATILITY_LABELS = {
    "very_low": "Very Low",
    "low": "Low",
    "high": "High",
    "very_high": "Very High",
}

# Which session is best for each pair (for "wait for X" messages)
_PAIR_BEST_SESSION = {
    "EURUSD": "London/NY Overlap 🔥",
    "GBPUSD": "London/NY Overlap 🔥",
    "EURGBP": "London Session 🇬🇧",
    "USDJPY": "New York Session 🗽",
    "GBPJPY": "London Session 🇬🇧",
    "EURJPY": "London Session 🇬🇧",
    "AUDUSD": "Asian Session 🌏",
    "NZDUSD": "Asian Session 🌏",
    "USDCAD": "New York Session 🗽",
    "USDCHF": "London Session 🇬🇧",
    "XAUUSD": "London/NY Overlap 🔥",
}


def _session_key_for_hour(hour: int) -> str:
    if 13 <= hour < 16:
        return "london_ny_overlap"
    if 8 <= hour < 16:
        return "london"
    if 13 <= hour < 22:
        return "new_york"
    if 0 <= hour < 9:
        return "asian"
    return "dead_zone"


def _mins_to_next_session(now_utc: datetime) -> tuple[int, str]:
    """Return (minutes_until, next_session_name)."""
    hour = now_utc.hour
    minute = now_utc.minute

    # Next major session openings in UTC
    transitions = [
        (0,  "asian",    "Asian Session 🌏"),
        (8,  "london",   "London Session 🇬🇧"),
        (13, "overlap",  "London/NY Overlap 🔥"),
        (22, "dead",     "Dead Zone 💤"),
    ]

    for target_hour, _, name in transitions:
        if target_hour > hour or (target_hour == hour and minute == 0):
            mins = (target_hour - hour) * 60 - minute
            return mins, name

    # Next one is tomorrow's asian (00:00)
    mins = (24 - hour) * 60 - minute
    return mins, "Asian Session 🌏"


def get_current_session() -> dict:
    now = datetime.now(timezone.utc)
    now_wat = now.astimezone(_WAT)
    hour = now.hour
    weekday = now.weekday()  # 5=Sat, 6=Sun

    key = _session_key_for_hour(hour)
    session = dict(SESSIONS[key])

    mins_to_next, next_name = _mins_to_next_session(now)

    session["current_utc"] = now.strftime("%H:%M UTC")
    session["current_wat"] = now_wat.strftime("%H:%M WAT")
    session["is_weekend"] = weekday >= 5
    session["minutes_to_next_session"] = mins_to_next
    session["next_session_name"] = next_name
    session["session_key"] = key
    return session


def get_session_for_pair(pair: str) -> dict:
    pair = pair.upper().replace("/", "")
    session = get_current_session()
    best_pairs = session.get("best_pairs", [])
    avoid_pairs = session.get("avoid_pairs", [])
    session_name = session["name"]

    optimal = pair in best_pairs
    caution = pair in avoid_pairs
    best_session = _PAIR_BEST_SESSION.get(pair, "London/NY Overlap 🔥")

    if optimal:
        message = f"✅ {pair} is well-suited for the current {session_name}."
    elif caution:
        message = f"⚠️ {pair} has thin liquidity right now. Consider waiting for {best_session}."
    else:
        message = f"🔵 {pair} can be traded but isn't the most active right now."

    return {
        **session,
        "pair": pair,
        "optimal": optimal,
        "caution": caution,
        "message": message,
    }


def format_session_message() -> str:
    session = get_current_session()

    if session["is_weekend"]:
        return (
            "📅 Weekend — Market Closed\n"
            "The forex market is closed until Sunday 10:00 PM WAT.\n"
            "Use this time to review your trades with /review or plan next week's setups."
        )

    vol_label = _VOLATILITY_LABELS.get(session["volatility"], session["volatility"])
    best = " • ".join(session["best_pairs"]) if session["best_pairs"] else "None"
    mins = session["minutes_to_next_session"]
    next_name = session["next_session_name"]

    lines = [
        "🕐 Current Session",
        session["name"],
        f"⏰ {session['current_wat']} ({session['current_utc']})",
        f"📊 Volatility: {vol_label}",
        f"💬 {session['character']}",
        f"🎯 Best pairs now:\n{best}",
        f"💡 {session['tip']}",
        f"⏭ Next: {next_name} in {mins} mins",
    ]
    return "\n".join(lines)


def should_warn_about_session(pair: str) -> str | None:
    pair = pair.upper().replace("/", "")
    session = get_current_session()

    if session["is_weekend"]:
        return (
            f"🕐 Session Alert\n"
            f"The forex market is closed on weekends. "
            f"Your trade has been logged but will execute at Sunday open."
        )

    key = session["session_key"]
    name = session["name"]
    best_session = _PAIR_BEST_SESSION.get(pair, "London/NY Overlap 🔥")

    if key == "dead_zone":
        return (
            f"🕐 Session Alert\n"
            f"You're trading {pair} during the {name} — "
            f"spreads are very wide and liquidity is thin.\n"
            f"Best time for {pair}: {best_session}."
        )

    if pair in session.get("avoid_pairs", []):
        return (
            f"🕐 Session Alert\n"
            f"You're trading {pair} during the {name} — "
            f"this pair has low liquidity in this session.\n"
            f"Best time for {pair}: {best_session}."
        )

    return None
