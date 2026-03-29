import asyncio
import json

from groq import Groq

import calculator
import journal
import news as news_module
import calendar_alerts
from prices import get_price, get_multiple_prices, format_price_message, format_multiple_prices_message
from config import GROQ_API_KEY

_groq = Groq(api_key=GROQ_API_KEY)

_INTENT_SYSTEM = """
You are PipMercy's intent detection engine. Extract the intent and data from the trader's message.

Return ONLY a valid JSON object. No explanation, no markdown, no backticks.

Intents and their extracted_data shapes:

LOG_TRADE: trader describing a trade they took or want to take
  extracted_data: {
    "pair": "EURUSD",
    "direction": "BUY",
    "entry_price": 1.0850,
    "stop_loss": 1.0800,
    "take_profit": 1.0950,
    "notes": null
  }

CLOSE_TRADE: trader closing a trade
  extracted_data: {
    "trade_id": 3,
    "outcome": "WIN",
    "pnl": 1.20
  }

CHECK_PRICE: trader wants current price
  extracted_data: {
    "pairs": ["EURUSD", "XAUUSD"]
  }

POSITION_SIZE: trader wants lot size calculation
  extracted_data: {
    "pair": "EURUSD",
    "direction": "BUY",
    "entry_price": 1.0850,
    "stop_loss": 1.0800,
    "take_profit": null,
    "balance": null,
    "risk_percent": null
  }

CALENDAR: trader wants economic calendar
  extracted_data: {}

NEWS: trader wants market news
  extracted_data: {
    "pair": null   # specific pair or null. Extract pair from phrases like:
    # "news on gold" → "XAUUSD"
    # "what's happening with the pound" → "GBPUSD"
    # "EURUSD news" → "EURUSD"
    # "how is dollar doing" → "USD"
    # "cable" → "GBPUSD"
    # "fiber" → "EURUSD"
    # "aussie" → "AUDUSD"
    # "loonie" → "USDCAD"
    # "swissy" → "USDCHF"
    # "kiwi" → "NZDUSD"
  }

WEEKLY_SUMMARY: trader wants their weekly performance
  extracted_data: {}

VIEW_TRADES: trader wants to see their trades
  extracted_data: {
    "filter": "open"
  }

SETTINGS: trader wants to change balance or risk
  extracted_data: {
    "key": "default_balance",
    "value": "75"
  }

GENERAL: anything else
  extracted_data: {
    "message": "original message text"
  }

Return format:
{
  "intent": "INTENT_NAME",
  "extracted_data": { ... },
  "confidence": 0.95
}
""".strip()

_GENERAL_SYSTEM = (
    "You are PipMercy, a friendly forex trading assistant for a beginner trader named "
    "Mercylina (Mercy for short). You help her understand forex concepts, review her trades, "
    "and stay disciplined. Keep responses concise, warm, and educational. Use simple language. "
    "Occasionally use light emojis. Never give financial advice — always frame things as education."
)


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

async def detect_intent(message: str) -> dict:
    _fallback = {"intent": "GENERAL", "extracted_data": {"message": message}, "confidence": 0.5}
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: _groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": _INTENT_SYSTEM},
                    {"role": "user", "content": message},
                ],
                temperature=0,
            ),
        )
        raw = response.choices[0].message.content.strip()
        return json.loads(raw)
    except Exception:
        return _fallback


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def handle_log_trade(data: dict) -> str:
    settings = journal.get_settings()
    balance = settings.get("default_balance", 50.0)
    risk_percent = settings.get("default_risk_percent", 1.0)

    if data.get("entry_price") is None or data.get("stop_loss") is None:
        return "I need your entry price and stop loss to log this trade. What were they?"

    pair = (data.get("pair") or "").upper()
    direction = (data.get("direction") or "BUY").upper()
    entry = float(data["entry_price"])
    sl = float(data["stop_loss"])
    tp = data.get("take_profit")

    pos = calculator.calculate_position_size(balance, risk_percent, entry, sl, pair)
    if "error" in pos:
        return f"❌ {pos['error']}"

    rr_val = None
    if tp is not None:
        rr = calculator.calculate_rr(entry, sl, float(tp), pair)
        rr_val = rr.get("rr_ratio") if "error" not in rr else None

    trade_dict = {
        "pair": pair,
        "direction": direction,
        "entry_price": entry,
        "stop_loss": sl,
        "take_profit": float(tp) if tp is not None else None,
        "lot_size": pos["lot_size_micro"],
        "risk_amount": pos["risk_amount"],
        "risk_reward": rr_val,
        "notes": data.get("notes"),
    }

    result = journal.save_trade(trade_dict)
    if "error" in result:
        return f"❌ {result['error']}"

    try:
        import streaks
        streaks.update_today_streak(traded=True)
    except Exception:
        pass

    position_msg = calculator.format_position_message(
        pair, direction, entry, sl, float(tp) if tp is not None else None,
        balance, risk_percent,
    )
    response = (
        f"✅ Trade logged! #{result['trade_id']}\n"
        f"{position_msg}\n"
        f"💾 Saved to your journal. Good luck Mercy! 🎯"
    )

    checklist_warnings = ""
    try:
        from checklist import run_pretrade_checklist
        checklist_warnings = await run_pretrade_checklist(
            pair=pair,
            entry=entry,
            stop_loss=sl,
            take_profit=float(tp) if tp is not None else None,
            lot_size_micro=pos["lot_size_micro"],
            balance=balance,
        )
    except Exception:
        pass

    if checklist_warnings:
        response = response + f"\n\n{checklist_warnings}"

    return response


async def handle_close_trade(data: dict) -> str:
    trade_id = data.get("trade_id")
    outcome = (data.get("outcome") or "").upper()
    pnl = data.get("pnl")

    if trade_id is None:
        open_trades = journal.get_open_trades()
        if not open_trades:
            return "You have no open trades to close."
        if len(open_trades) == 1:
            trade_id = open_trades[0]["id"]
        else:
            lines = ["Which trade are you closing? Open trades:"]
            for t in open_trades:
                lines.append(f"  #{t['id']} {t['pair']} {t['direction']} — opened {t['created_at'][:10]}")
            lines.append("\nReply with the trade number, outcome (WIN/LOSS), and P&L.")
            return "\n".join(lines)

    result = journal.close_trade(int(trade_id), outcome, pnl)
    if "error" in result:
        return f"❌ {result['error']}"

    trade = journal.get_trade_by_id(int(trade_id))
    close_confirmation = f"{result['message']}\n\n{journal.format_trade_card(trade)}"

    try:
        import streaks
        risk_ok = True
        if trade and trade.get("pnl") and trade.get("risk_amount"):
            if abs(trade["pnl"]) > trade["risk_amount"] * 1.2 and trade["outcome"] == "LOSS":
                risk_ok = False
        streaks.update_today_streak(journaled=True, respected_risk=risk_ok)
    except Exception:
        pass

    review = ""
    try:
        from coach import generate_trade_review
        review = await generate_trade_review(int(trade_id))
    except Exception:
        pass

    response = f"{close_confirmation}\n\n{review}" if review else close_confirmation

    try:
        import streaks as _streaks
        warning = _streaks.check_and_warn_loss_streak()
        if warning:
            response = response + f"\n\n{warning}"
    except Exception:
        pass

    return response


async def handle_check_price(data: dict) -> str:
    pairs = data.get("pairs", [])
    if not pairs:
        return "Which pair do you want the price for? (e.g. EURUSD, XAUUSD)"
    if len(pairs) == 1:
        price_data = await get_price(pairs[0])
        return format_price_message(price_data)
    prices_dict = await get_multiple_prices(pairs)
    return format_multiple_prices_message(prices_dict)


async def handle_position_size(data: dict) -> str:
    if data.get("entry_price") is None or data.get("stop_loss") is None:
        return "I need your entry and stop loss to calculate position size."

    settings = journal.get_settings()
    balance = float(data["balance"]) if data.get("balance") else settings.get("default_balance", 50.0)
    risk_percent = float(data["risk_percent"]) if data.get("risk_percent") else settings.get("default_risk_percent", 1.0)

    pair = (data.get("pair") or "EURUSD").upper()
    direction = (data.get("direction") or "BUY").upper()
    entry = float(data["entry_price"])
    sl = float(data["stop_loss"])
    tp = float(data["take_profit"]) if data.get("take_profit") else None

    return calculator.format_position_message(pair, direction, entry, sl, tp, balance, risk_percent)


async def handle_calendar(data: dict) -> str:
    events = await calendar_alerts.fetch_today_events()
    return calendar_alerts.format_calendar_message(events, title="📅 Today's High-Impact Events")


async def handle_news(data: dict) -> str:
    pair = data.get("pair")
    if pair:
        intel = await news_module.get_pair_intelligence(pair.upper())
        if "error" in intel:
            return f"⚠️ Couldn't fetch intelligence for {pair}. Try again."
        return news_module.format_pair_intelligence_message(intel)
    else:
        articles = await news_module.fetch_news(limit=8)
        summary = await news_module.summarize_with_groq(articles)
        return news_module.format_news_message(articles, summary)


async def handle_weekly_summary(data: dict) -> str:
    summary = journal.get_weekly_summary()
    return journal.format_weekly_summary(summary)


async def handle_view_trades(data: dict) -> str:
    filter_by = data.get("filter", "open")
    if filter_by == "open":
        trades = journal.get_open_trades()
    else:
        trades = journal.get_all_trades(limit=10)

    if not trades:
        return "No trades found."

    cards = [journal.format_trade_card(t) for t in trades[:5]]
    result = "\n\n---\n\n".join(cards)
    if len(trades) > 5:
        result += f"\n\n... and {len(trades) - 5} more"
    return result


async def handle_settings(data: dict) -> str:
    key = data.get("key", "")
    value = str(data.get("value", ""))
    if key not in ("default_balance", "default_risk_percent"):
        return "I can only update default_balance or default_risk_percent."
    result = journal.update_setting(key, value)
    if "error" in result:
        return f"❌ {result['error']}"
    return f"✅ Updated! {key} is now {value}"


async def handle_general(data: dict, original_message: str) -> str:
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: _groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": _GENERAL_SYSTEM},
                    {"role": "user", "content": original_message},
                ],
            ),
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "I didn't quite get that. Try asking me about prices, your trades, or the calendar! 😊"


# ---------------------------------------------------------------------------
# Main router
# ---------------------------------------------------------------------------

async def process_message(message: str) -> str:
    try:
        intent_result = await detect_intent(message)
        intent = intent_result.get("intent", "GENERAL")
        data = intent_result.get("extracted_data", {})

        if intent == "LOG_TRADE":
            return await handle_log_trade(data)
        elif intent == "CLOSE_TRADE":
            return await handle_close_trade(data)
        elif intent == "CHECK_PRICE":
            return await handle_check_price(data)
        elif intent == "POSITION_SIZE":
            return await handle_position_size(data)
        elif intent == "CALENDAR":
            return await handle_calendar(data)
        elif intent == "NEWS":
            return await handle_news(data)
        elif intent == "WEEKLY_SUMMARY":
            return await handle_weekly_summary(data)
        elif intent == "VIEW_TRADES":
            return await handle_view_trades(data)
        elif intent == "SETTINGS":
            return await handle_settings(data)
        else:
            return await handle_general(data, message)

    except Exception:
        return "⚠️ Something went wrong on my end. Try again in a moment!"
