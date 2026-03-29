import datetime
import logging
import time

from telegram import BotCommand, Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import agent
import checklist
import coach
import journal as journal_module
import prices
import sessions
import streaks
from agent import process_message
from calendar_alerts import fetch_today_events, format_calendar_message, check_upcoming_and_alert
from config import TELEGRAM_TOKEN, CHAT_ID
from database import init_db
from config import DEFAULT_BALANCE, DEFAULT_RISK_PERCENT
from journal import get_weekly_summary, format_weekly_summary, get_today_summary, format_daily_summary
import calculator
import news as news_module
from news import fetch_news, summarize_with_groq, format_news_message, analyze_market_pressure, format_heatmap_message

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("pipmercy.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

_MAX_MSG = 4096
_last_message_time: dict = {}
COOLDOWN_SECONDS = 3


def _split(text: str) -> list[str]:
    """Split a long message into <=4096-char chunks, breaking at newlines."""
    if len(text) <= _MAX_MSG:
        return [text]
    chunks, current = [], []
    current_len = 0
    for line in text.splitlines(keepends=True):
        if current_len + len(line) > _MAX_MSG and current:
            chunks.append("".join(current))
            current, current_len = [], 0
        current.append(line)
        current_len += len(line)
    if current:
        chunks.append("".join(current))
    return chunks


async def _send(bot_or_obj, chat_id: int, text: str, **kwargs):
    """Send text, splitting into chunks if needed."""
    for chunk in _split(text):
        await bot_or_obj.send_message(chat_id=chat_id, text=chunk, **kwargs)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 Hey Mercy! I'm PipMercy, your personal forex assistant.\n"
        "Here's what I can do:\n\n"
        "📈 Log your trades — just tell me naturally\n"
        "💱 Check live prices — \"price of EURUSD\"\n"
        "📦 Calculate position size — \"how much to trade GBPUSD?\"\n"
        "📅 Economic calendar — high-impact events for today\n"
        "📰 Market news — summarized by AI\n"
        "📊 Weekly summary — your P&L and win rate\n"
        "⚙️ Update settings — \"change my balance to 100\"\n\n"
        "Just talk to me naturally — no commands needed! 🎯"
    )
    await update.message.reply_text(msg)


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = format_weekly_summary(get_weekly_summary())
    await update.message.reply_text(result)


async def trades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await agent.handle_view_trades({"filter": "open"})
    await update.message.reply_text(result)


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📰 Fetching latest forex news...")
    articles = await fetch_news(limit=8)
    news_summary = await summarize_with_groq(articles)
    result = format_news_message(articles, news_summary)
    for chunk in _split(result):
        await update.message.reply_text(chunk, disable_web_page_preview=True)


async def calendar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    events = await fetch_today_events()
    result = format_calendar_message(events, title="📅 Today's High-Impact Events")
    await update.message.reply_text(result)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 PipMercy Help\n\n"
        "Just talk to me naturally! Examples:\n\n"
        "📈 Logging a trade:\n"
        "\"I bought EURUSD at 1.0850, sl 1.0800, tp 1.0950\"\n\n"
        "💱 Checking prices:\n"
        "\"What's gold at?\" / \"Price of GBPUSD\"\n\n"
        "📦 Position sizing:\n"
        "\"How many lots for USDJPY entry 149.50 sl 149.00?\"\n\n"
        "✅ Closing a trade:\n"
        "\"Close trade 2 as a win, made $1.20\"\n\n"
        "📊 Your stats:\n"
        "\"How did I do this week?\"\n\n"
        "⚙️ Settings:\n"
        "\"Change my risk to 2%\" / \"Update balance to 100\""
    )
    await update.message.reply_text(msg)


async def close_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: /close <trade_id> <win|loss> [pnl]\nExample: /close 3 win 1.20"
        )
        return
    msg = f"close trade {' '.join(args)}"
    response = await agent.process_message(msg)
    await update.message.reply_text(response)


async def heatmap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != CHAT_ID:
        return
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    articles = await fetch_news(limit=20)
    if not articles:
        await update.message.reply_text("📊 No articles available for analysis right now.")
        return
    pressure = analyze_market_pressure(articles)
    message = format_heatmap_message(pressure)
    await update.message.reply_text(message, disable_web_page_preview=True)


async def pair_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != CHAT_ID:
        return
    if not context.args:
        await update.message.reply_text(
            "Usage: /pair <symbol>\n\nExamples:\n/pair EURUSD\n/pair XAUUSD\n/pair GBPUSD\n/pair USDJPY",
            disable_web_page_preview=True,
        )
        return
    pair = context.args[0].upper().replace("/", "")
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    loading = await update.message.reply_text(
        f"🔍 Analysing {pair}... fetching news and running AI analysis...",
        disable_web_page_preview=True,
    )
    intel = await news_module.get_pair_intelligence(pair)
    if "error" in intel:
        await loading.edit_text(f"⚠️ Couldn't fetch intelligence for {pair}. Try again.")
        return
    message = news_module.format_pair_intelligence_message(intel)
    await loading.edit_text(message, disable_web_page_preview=True)


async def session_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != CHAT_ID:
        return
    if context.args:
        pair = context.args[0].upper().replace("/", "")
        pair_info = sessions.get_session_for_pair(pair)
        msg = sessions.format_session_message()
        msg += f"\n\n{pair_info.get('message', '')}"
    else:
        msg = sessions.format_session_message()
    await update.message.reply_text(msg, disable_web_page_preview=True)


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != CHAT_ID:
        return
    summary = get_today_summary()
    message = format_daily_summary(summary)
    await update.message.reply_text(
        message,
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


async def checklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != CHAT_ID:
        return
    if len(context.args) < 4:
        await update.message.reply_text(
            "Usage: /checklist PAIR DIRECTION ENTRY SL [TP]\n\nExample:\n"
            "/checklist EURUSD BUY 1.0850 1.0800 1.0950\n"
            "/checklist XAUUSD BUY 4500 4480",
            disable_web_page_preview=True,
        )
        return
    try:
        pair   = context.args[0].upper()
        entry  = float(context.args[2])
        sl     = float(context.args[3])
        tp     = float(context.args[4]) if len(context.args) > 4 else None

        settings    = journal_module.get_settings()
        balance     = settings.get("default_balance", DEFAULT_BALANCE)
        risk_pct    = settings.get("default_risk_percent", DEFAULT_RISK_PERCENT)

        pos = calculator.calculate_position_size(balance, risk_pct, entry, sl, pair)
        lot_size = pos.get("lot_size_micro", 0) if "error" not in pos else 0

        await context.bot.send_chat_action(
            chat_id=update.message.chat_id, action=ChatAction.TYPING
        )
        warnings = await checklist.run_pretrade_checklist(pair, entry, sl, tp, lot_size, balance)

        if not warnings:
            await update.message.reply_text(
                "✅ Pre-Trade Checklist Passed\n\nAll checks clear — this trade looks clean from a risk management perspective.",
                disable_web_page_preview=True,
            )
        else:
            await update.message.reply_text(warnings, disable_web_page_preview=True)
    except (ValueError, IndexError):
        await update.message.reply_text(
            "Invalid format. Example: /checklist EURUSD BUY 1.0850 1.0800 1.0950"
        )


async def streak_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != CHAT_ID:
        return
    message = streaks.format_streak_message()
    await update.message.reply_text(message, disable_web_page_preview=True)


async def review_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != CHAT_ID:
        return
    if not context.args:
        trades = journal_module.get_all_trades(limit=10)
        closed = [t for t in trades if t["outcome"] != "OPEN"]
        if not closed:
            await update.message.reply_text("No closed trades to review yet.")
            return
        trade_id = closed[0]["id"]
    else:
        try:
            trade_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Usage: /review or /review <trade_id>")
            return
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    review = await coach.generate_trade_review(trade_id)
    if not review:
        await update.message.reply_text("⚠️ Could not generate review right now.")
        return
    await update.message.reply_text(review, disable_web_page_preview=True)


async def exposure_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != CHAT_ID:
        return
    exposure = journal_module.get_open_exposure()
    message = journal_module.format_exposure_message(exposure)
    await update.message.reply_text(
        message,
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /price EURUSD\nExample: /price XAUUSD")
        return
    pair = context.args[0].upper()
    price_data = await prices.get_price(pair)
    await update.message.reply_text(prices.format_price_message(price_data))


# ---------------------------------------------------------------------------
# Message handler
# ---------------------------------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != CHAT_ID:
        return

    user_id = update.message.from_user.id
    now = time.time()
    if now - _last_message_time.get(user_id, 0) < COOLDOWN_SECONDS:
        await update.message.reply_text("⏳ Give me a second to think... send that again!")
        return
    _last_message_time[user_id] = now

    try:
        await context.bot.send_chat_action(
            chat_id=update.message.chat_id, action=ChatAction.TYPING
        )
        response = await process_message(update.message.text)
        for chunk in _split(response):
            await update.message.reply_text(chunk, disable_web_page_preview=True)
    except Exception:
        await update.message.reply_text("⚠️ Something went wrong. Try again!")


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception while handling update: {context.error}")
    if update and hasattr(update, "message") and update.message:
        await update.message.reply_text(
            "⚠️ Something went wrong on my end. Try again in a moment!"
        )


# ---------------------------------------------------------------------------
# Scheduled jobs
# ---------------------------------------------------------------------------

async def morning_briefing(context: ContextTypes.DEFAULT_TYPE):
    events = await fetch_today_events()
    calendar_msg = format_calendar_message(events, title="📅 High-Impact Events")
    articles = await fetch_news(limit=8)
    news_summary = await summarize_with_groq(articles)
    msg = (
        "🌅 Good morning Mercy!\n"
        "Here's your market briefing for today:\n\n"
        f"{calendar_msg}\n\n"
        "📰 Market Summary\n\n"
        f"{news_summary}\n\n"
        "Trade safe and stick to your plan! 💪"
    )

    try:
        exposure = journal_module.get_open_exposure()
        if exposure["overexposed"]:
            overexposed_msg = journal_module.format_exposure_message(exposure)
            msg += f"\n\n⚠️ *Exposure Alert*\n{overexposed_msg}"
    except Exception:
        pass

    await _send(context.bot, CHAT_ID, msg, disable_web_page_preview=True)


async def calendar_check(context: ContextTypes.DEFAULT_TYPE):
    await check_upcoming_and_alert(context.bot, CHAT_ID)


async def news_digest(context: ContextTypes.DEFAULT_TYPE):
    articles = await fetch_news(limit=8)
    if not articles:
        return
    news_summary = await summarize_with_groq(articles)
    result = "📰 *Market Update*\n\n" + format_news_message(articles, news_summary)
    await _send(context.bot, CHAT_ID, result, disable_web_page_preview=True)


async def daily_pnl_push(context: ContextTypes.DEFAULT_TYPE):
    try:
        summary = get_today_summary()
        message = format_daily_summary(summary)
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(f"Daily P&L push failed: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def post_init(application):
    await application.bot.set_my_commands([
        BotCommand("start",    "Welcome message and feature overview"),
        BotCommand("summary",  "This week's trading performance"),
        BotCommand("trades",   "View your open trades"),
        BotCommand("news",     "Latest forex market news"),
        BotCommand("calendar", "Today's high-impact economic events"),
        BotCommand("price",    "Get live price: /price EURUSD"),
        BotCommand("close",    "Close a trade: /close 3 win 1.20"),
        BotCommand("heatmap",  "Market pressure — which pairs are most active"),
        BotCommand("pair",     "Pair intelligence: /pair EURUSD"),
        BotCommand("exposure",  "Currency exposure across open trades"),
        BotCommand("session",   "Current market session and best pairs to trade"),
        BotCommand("today",     "Today's P&L and open positions summary"),
        BotCommand("checklist", "Pre-trade risk check: /checklist EURUSD BUY 1.08 1.075"),
        BotCommand("streak",   "Your discipline streak and score"),
        BotCommand("review",   "AI trade review: /review or /review 3"),
        BotCommand("help",     "How to use PipMercy"),
    ])


def main():
    init_db()

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start",    start))
    app.add_handler(CommandHandler("summary",  summary))
    app.add_handler(CommandHandler("trades",   trades))
    app.add_handler(CommandHandler("news",     news_command))
    app.add_handler(CommandHandler("calendar", calendar_command))
    app.add_handler(CommandHandler("heatmap",  heatmap_command))
    app.add_handler(CommandHandler("pair",     pair_command))
    app.add_handler(CommandHandler("exposure",  exposure_command))
    app.add_handler(CommandHandler("price",    price_command))
    app.add_handler(CommandHandler("session",   session_command))
    app.add_handler(CommandHandler("today",     today_command))
    app.add_handler(CommandHandler("checklist", checklist_command))
    app.add_handler(CommandHandler("streak",   streak_command))
    app.add_handler(CommandHandler("review",   review_command))
    app.add_handler(CommandHandler("close",    close_command))
    app.add_handler(CommandHandler("help",     help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    jq = app.job_queue

    jq.run_daily(
        morning_briefing,
        time=datetime.time(6, 0, 0, tzinfo=datetime.timezone.utc),
        name="morning_briefing",
    )
    jq.run_repeating(
        calendar_check,
        interval=1800,
        first=60,
        name="calendar_check",
    )
    jq.run_repeating(
        news_digest,
        interval=14400,
        first=300,
        name="news_digest",
    )
    jq.run_daily(
        daily_pnl_push,
        time=datetime.time(19, 0, 0, tzinfo=datetime.timezone.utc),
        name="daily_pnl_push",
    )

    print("PipMercy is running... 🚀")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
