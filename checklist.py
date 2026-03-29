from datetime import datetime, timezone, timedelta

from calculator import calculate_rr
from calendar_alerts import fetch_today_events
from journal import get_open_trades
from streaks import get_current_loss_streak

# Currency pairs → constituent currencies for exposure check
def _currencies_in_pair(pair: str) -> tuple[str, str]:
    pair = pair.upper()
    if pair.startswith("XAU"):
        return "XAU", pair[3:]
    if len(pair) == 6:
        return pair[:3], pair[3:]
    return pair, ""


async def check_news_timing(pair: str, entry_time: datetime) -> dict:
    """Warn if a high-impact event is within 30 min of entry or in the next 2 hours."""
    try:
        base, quote = _currencies_in_pair(pair)
        relevant = {base, quote}
        events = await fetch_today_events()
        now = datetime.now(timezone.utc)

        if entry_time.tzinfo is None:
            entry_time = entry_time.replace(tzinfo=timezone.utc)

        for event in events:
            if event["currency"] not in relevant:
                continue
            ev_dt = event["datetime_utc"]
            diff_entry = abs((ev_dt - entry_time).total_seconds()) / 60
            mins_ahead = (ev_dt - now).total_seconds() / 60

            if diff_entry <= 30:
                return {
                    "passed": False,
                    "message": (
                        f"⚠️ High-impact news was released within 30 mins of your entry "
                        f"({event['name']}, {event['currency']}). News entries are high risk."
                    ),
                }
            if 0 < mins_ahead <= 120:
                return {
                    "passed": False,
                    "message": (
                        f"⏰ {event['name']} ({event['currency']}) is scheduled in "
                        f"{round(mins_ahead)} mins. Consider waiting for the dust to settle."
                    ),
                }
        return {"passed": True, "message": ""}
    except Exception:
        return {"passed": True, "message": ""}


def check_rr_ratio(
    entry: float, stop_loss: float, take_profit: float | None, pair: str
) -> dict:
    """Warn if R:R is below 1.5:1."""
    if take_profit is None:
        return {"passed": True, "message": ""}
    try:
        rr = calculate_rr(entry, stop_loss, take_profit, pair)
        if "error" in rr:
            return {"passed": True, "message": ""}
        ratio = rr["rr_ratio"]
        if ratio < 1.5:
            return {
                "passed": False,
                "message": (
                    f"📉 Your R:R is {ratio:.1f}:1 — below the recommended 1.5:1 minimum. "
                    f"Consider widening your TP or tightening your SL."
                ),
            }
        return {"passed": True, "message": ""}
    except Exception:
        return {"passed": True, "message": ""}


def check_position_size(lot_size_micro: float, balance: float) -> dict:
    """Warn if position size is outsized for the account."""
    try:
        if lot_size_micro > 10 or lot_size_micro > balance * 0.5:
            return {
                "passed": False,
                "message": (
                    f"🚨 Position size of {lot_size_micro} micro lots seems large for your account. "
                    f"Double-check your lot size."
                ),
            }
        return {"passed": True, "message": ""}
    except Exception:
        return {"passed": True, "message": ""}


def check_currency_exposure(pair: str) -> dict:
    """Warn if adding this pair would increase concentration on already-exposed currencies."""
    try:
        from journal import get_open_exposure
        exposure = get_open_exposure()

        base = pair[:3]
        quote = pair[3:] if len(pair) == 6 else "USD"

        warnings = []
        for currency in [base, quote]:
            if currency in exposure["currency_exposure"]:
                count = exposure["currency_exposure"][currency]["trade_count"]
                if count >= 2:
                    warnings.append(f"{currency} ({count} existing trades)")

        if warnings:
            return {
                "passed": False,
                "message": (
                    f"🔄 High {'/'.join(warnings)} exposure. "
                    f"Adding {pair} increases concentration risk on these currencies."
                ),
            }
        return {"passed": True, "message": ""}
    except Exception:
        return {"passed": True, "message": ""}


def check_loss_streak() -> dict:
    """Warn if currently on a 3+ loss streak."""
    try:
        n = get_current_loss_streak()
        if n >= 3:
            return {
                "passed": False,
                "message": (
                    f"🛑 You're on a {n}-trade losing streak. Trading while on a losing streak "
                    f"increases the risk of revenge trading. Are you sure this is your A+ setup?"
                ),
            }
        return {"passed": True, "message": ""}
    except Exception:
        return {"passed": True, "message": ""}


async def run_pretrade_checklist(
    pair: str,
    entry: float,
    stop_loss: float,
    take_profit: float | None,
    lot_size_micro: float,
    balance: float,
) -> str:
    """Run all 5 checks. Return warning block if any fail, empty string if all pass."""
    try:
        entry_time = datetime.now(timezone.utc)

        news_result     = await check_news_timing(pair, entry_time)
        rr_result       = check_rr_ratio(entry, stop_loss, take_profit, pair)
        size_result     = check_position_size(lot_size_micro, balance)
        exposure_result = check_currency_exposure(pair)
        streak_result   = check_loss_streak()

        failures = [
            r["message"]
            for r in [news_result, rr_result, size_result, exposure_result, streak_result]
            if not r["passed"]
        ]

        if not failures:
            return ""

        body = "\n".join(failures)
        return (
            f"⚡ Pre-Trade Checklist\n"
            f"{body}\n"
            f"Review these before confirming your trade."
        )
    except Exception:
        return ""
