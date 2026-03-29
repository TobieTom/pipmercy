import asyncio
import json
from datetime import datetime, timezone, timedelta

from groq import Groq

from config import GROQ_API_KEY
from journal import get_trade_context
from calendar_alerts import fetch_today_events, get_upcoming_events

_groq = Groq(api_key=GROQ_API_KEY)

_COACH_SYSTEM = (
    "You are PipMercy, a forex trading coach for a beginner trader named Mercylina (Mercy). "
    "Your job is to review her just-closed trade and give her honest, constructive coaching.\n\n"
    "Be warm but direct. Max 4 sentences total. Structure your response as:\n\n"
    "Line 1: One sentence on the outcome — celebrate a win genuinely, acknowledge a loss honestly without being harsh.\n"
    "Line 2: One sentence on execution quality — comment on R:R achievement, early exit, or over-holding if applicable. "
    "If execution was clean, say so.\n"
    "Line 3: One sentence on one pattern or habit you notice — reference her win rate, pair performance, "
    "or news timing if relevant.\n"
    "Line 4: One actionable takeaway — something specific she can do differently or keep doing next trade.\n\n"
    "Do not use bullet points. Do not use headers. Just 4 warm, direct sentences.\n"
    "Never say 'Not financial advice'. Never be robotic."
)


async def check_news_timing(trade_created_at: str) -> bool:
    """Return True if the trade was opened within 30 minutes of a high-impact event."""
    try:
        events = await fetch_today_events()
        try:
            trade_dt = datetime.strptime(trade_created_at[:19], "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
        except Exception:
            return False
        for event in events:
            diff = abs((event["datetime_utc"] - trade_dt).total_seconds())
            if diff <= 1800:
                return True
        return False
    except Exception:
        return False


async def generate_trade_review(trade_id: int) -> str:
    """Generate a 4-sentence Groq coaching review for a closed trade."""
    try:
        ctx = get_trade_context(trade_id)
        trade = ctx["trade"]

        if not trade:
            return ""

        # --- math analysis ---
        pnl = trade.get("pnl")
        risk_amount = trade.get("risk_amount")
        planned_rr = trade.get("risk_reward")
        outcome = trade.get("outcome", "")

        actual_rr = None
        if pnl is not None and risk_amount and risk_amount != 0:
            actual_rr = round(abs(pnl) / risk_amount, 2)

        rr_achieved = None
        if actual_rr is not None and planned_rr and planned_rr != 0:
            rr_achieved = actual_rr / planned_rr

        early_exit = bool(outcome == "WIN" and rr_achieved is not None and rr_achieved < 0.7)
        over_loss = bool(
            outcome == "LOSS"
            and pnl is not None
            and risk_amount
            and abs(pnl) > risk_amount * 1.2
        )

        # --- news timing ---
        news_risk = await check_news_timing(trade.get("created_at", ""))

        # --- build context dict ---
        payload = {
            "pair":              trade["pair"],
            "direction":         trade["direction"],
            "outcome":           outcome,
            "pnl":               pnl,
            "risk_amount":       risk_amount,
            "planned_rr":        planned_rr,
            "actual_rr":         actual_rr,
            "rr_achieved_pct":   round(rr_achieved * 100) if rr_achieved is not None else None,
            "early_exit":        early_exit,
            "over_loss":         over_loss,
            "news_risk":         news_risk,
            "overall_win_rate":  ctx["win_rate"],
            "pair_win_rate":     ctx["same_pair_win_rate"],
            "total_trades":      ctx["total_closed_trades"],
        }

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: _groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": _COACH_SYSTEM},
                    {"role": "user", "content": f"Trade just closed: {json.dumps(payload)}"},
                ],
            ),
        )
        review_text = response.choices[0].message.content.strip()
        return f"🎓 Trade Review — #{trade_id}\n{review_text}"

    except Exception:
        return ""
