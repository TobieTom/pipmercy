import datetime

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import agent
from agent import process_message
from calendar_alerts import fetch_today_events, format_calendar_message, check_upcoming_and_alert
from config import TELEGRAM_TOKEN, CHAT_ID
from database import init_db
from journal import get_weekly_summary, format_weekly_summary
from news import fetch_news, summarize_with_groq, format_news_message

_MAX_MSG = 4096


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
        await update.message.reply_text(chunk)


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


# ---------------------------------------------------------------------------
# Message handler
# ---------------------------------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != CHAT_ID:
        return

    try:
        await context.bot.send_chat_action(
            chat_id=update.message.chat_id, action=ChatAction.TYPING
        )
        response = await process_message(update.message.text)
        for chunk in _split(response):
            await update.message.reply_text(chunk)
    except Exception:
        await update.message.reply_text("⚠️ Something went wrong. Try again!")


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
    await _send(context.bot, CHAT_ID, msg)


async def calendar_check(context: ContextTypes.DEFAULT_TYPE):
    await check_upcoming_and_alert(context.bot, CHAT_ID)


async def news_digest(context: ContextTypes.DEFAULT_TYPE):
    articles = await fetch_news(limit=8)
    if not articles:
        return
    news_summary = await summarize_with_groq(articles)
    result = "📰 *Market Update*\n\n" + format_news_message(articles, news_summary)
    await _send(context.bot, CHAT_ID, result)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    init_db()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",    start))
    app.add_handler(CommandHandler("summary",  summary))
    app.add_handler(CommandHandler("trades",   trades))
    app.add_handler(CommandHandler("news",     news_command))
    app.add_handler(CommandHandler("calendar", calendar_command))
    app.add_handler(CommandHandler("help",     help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    jq = app.job_queue

    # Morning briefing: 06:00 UTC daily
    jq.run_daily(
        morning_briefing,
        time=datetime.time(6, 0, 0, tzinfo=datetime.timezone.utc),
        name="morning_briefing",
    )

    # Calendar alert: every 30 minutes
    jq.run_repeating(
        calendar_check,
        interval=1800,
        first=60,
        name="calendar_check",
    )

    # News digest: every 4 hours
    jq.run_repeating(
        news_digest,
        interval=14400,
        first=300,
        name="news_digest",
    )

    print("PipMercy is running... 🚀")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
