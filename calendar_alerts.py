import time
from datetime import datetime, timedelta, timezone

import aiohttp

from config import JBLANKED_API_KEY

_BASE = "https://www.jblanked.com/news/api/forex-factory/calendar"
_HEADERS = {"Authorization": f"Api-Key {JBLANKED_API_KEY}"}
_TIMEOUT = aiohttp.ClientTimeout(total=10)
_WAT = timezone(timedelta(hours=1))

CACHE_TTL = 300  # seconds

_cache = {
    "today": {"data": [], "fetched_at": None},
    "week":  {"data": [], "fetched_at": None},
}

_alerted_events: set = set()
_alerted_reset_date: str = ""  # tracks the last reset date (YYYY-MM-DD)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(raw: dict) -> dict:
    """Convert a raw API event dict into our internal data model."""
    dt_utc = datetime.strptime(raw["Date"], "%Y.%m.%d %H:%M").replace(
        tzinfo=timezone.utc
    )
    actual = raw.get("Actual")
    return {
        "name":         raw.get("Name", ""),
        "currency":     raw.get("Currency", ""),
        "datetime_utc": dt_utc,
        "datetime_wat": dt_utc.astimezone(_WAT),
        "forecast":     raw.get("Forecast") or "--",
        "previous":     raw.get("Previous") or "--",
        "actual":       actual if actual else "TBA",
        "is_released":  actual is not None,
    }


async def _fetch_endpoint(key: str, url: str, force: bool) -> list:
    """Shared fetch logic for today/week endpoints with caching."""
    cache = _cache[key]
    now = time.monotonic()

    if not force and cache["fetched_at"] is not None:
        if now - cache["fetched_at"] < CACHE_TTL:
            return cache["data"]

    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(url, headers=_HEADERS) as resp:
                raw_list = await resp.json(content_type=None)

        if not isinstance(raw_list, list):
            print(f"[calendar] Unexpected response from {url}: {raw_list}")
            return cache["data"]

        events = [_normalize(e) for e in raw_list]
        cache["data"] = events
        cache["fetched_at"] = now
        return events

    except Exception as exc:
        print(f"[calendar] Error fetching {url}: {exc}")
        return cache["data"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def fetch_today_events(force: bool = False) -> list:
    return await _fetch_endpoint(
        "today",
        f"{_BASE}/today/?impact=High",
        force,
    )


async def fetch_week_events(force: bool = False) -> list:
    return await _fetch_endpoint(
        "week",
        f"{_BASE}/week/?impact=High",
        force,
    )


def get_upcoming_events(events: list, hours_ahead: int = 2) -> list:
    """Return unreleased events within the next hours_ahead hours, sorted ascending."""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=hours_ahead)
    upcoming = [
        e for e in events
        if not e["is_released"] and now <= e["datetime_utc"] <= cutoff
    ]
    return sorted(upcoming, key=lambda e: e["datetime_utc"])


def format_event(event: dict) -> str:
    if event["is_released"]:
        return (
            f"✅ {event['currency']} — {event['name']}\n"
            f"📊 Actual: {event['actual']} | "
            f"Forecast: {event['forecast']} | "
            f"Previous: {event['previous']}"
        )
    time_str = event["datetime_wat"].strftime("%H:%M")
    return (
        f"⚡ {event['currency']} — {event['name']}\n"
        f"🕐 {time_str} WAT | "
        f"Forecast: {event['forecast']} | "
        f"Previous: {event['previous']}"
    )


def format_calendar_message(events: list, title: str = "📅 Economic Calendar") -> str:
    if not events:
        return "📅 No high-impact events today. Good day to trade your setup! ✅"

    body = "\n".join(format_event(e) for e in events)
    return (
        f"{title}\n"
        f"{body}\n"
        f"─────────────────\n"
        f"⚠️ Avoid trading 30 mins before/after these events.\n"
        f"Times shown in West Africa Time (WAT/UTC+1)."
    )


async def check_upcoming_and_alert(bot, chat_id: int) -> None:
    """Send Telegram alerts for events in the next 60 minutes (once per event)."""
    global _alerted_reset_date

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _alerted_reset_date != today_str:
        _alerted_events.clear()
        _alerted_reset_date = today_str

    events = await fetch_today_events()
    upcoming = get_upcoming_events(events, hours_ahead=1)

    for event in upcoming:
        key = f"{event['name']}_{event['datetime_utc']}"
        if key in _alerted_events:
            continue
        _alerted_events.add(key)
        msg = (
            f"⚠️ High-Impact Event in <60 min!\n"
            f"{format_event(event)}"
        )
        await bot.send_message(chat_id=chat_id, text=msg)
