import asyncio
import re
import time
from datetime import datetime

import feedparser
from groq import Groq

from config import GROQ_API_KEY

FEEDS = [
    {
        "name": "ForexLive",
        "url": "https://www.forexlive.com/feed/news",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    },
    {
        "name": "DailyFX",
        "url": "https://www.dailyfx.com/feeds/all",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    },
    {
        "name": "MyFXBook",
        "url": "https://www.myfxbook.com/rss/latest-forex-news",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    },
]

PAIR_KEYWORDS = {
    "EURUSD": ["EUR", "Euro", "EURUSD", "ECB", "European"],
    "GBPUSD": ["GBP", "Pound", "Sterling", "GBPUSD", "BOE", "Bank of England"],
    "USDJPY": ["JPY", "Yen", "USDJPY", "BOJ", "Bank of Japan"],
    "AUDUSD": ["AUD", "Aussie", "AUDUSD", "RBA"],
    "USDCAD": ["CAD", "Loonie", "USDCAD", "BOC"],
    "XAUUSD": ["Gold", "XAU", "XAUUSD"],
    "USD":    ["USD", "Dollar", "Fed", "Federal Reserve", "FOMC", "NFP", "CPI", "inflation"],
}

_groq_client = Groq(api_key=GROQ_API_KEY)


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "")


def _format_date(parsed: time.struct_time | None) -> str:
    if parsed is None:
        return "Date unknown"
    try:
        dt = datetime(*parsed[:6])
        return dt.strftime("%-d %b %Y, %H:%M UTC")
    except Exception:
        return "Date unknown"


def _parse_feed(feed_config: dict) -> list:
    """Synchronous RSS feed parser. Returns a list of article dicts."""
    try:
        feed = feedparser.parse(
            feed_config["url"],
            request_headers={"User-Agent": feed_config["user_agent"]},
        )
        if feed.bozo and not feed.entries:
            return []

        articles = []
        for entry in feed.entries:
            raw_summary = entry.get("summary") or entry.get("description") or ""
            summary = _strip_html(raw_summary)[:300]
            articles.append({
                "title":     entry.get("title", "").strip(),
                "summary":   summary,
                "link":      entry.get("link", ""),
                "published": _format_date(entry.get("published_parsed")),
                "source":    feed_config["name"],
                "_parsed":   entry.get("published_parsed"),  # kept for sorting
            })
        return articles

    except Exception:
        return []


async def fetch_news(limit: int = 15) -> list:
    """Fetch and merge articles from all feeds concurrently."""
    loop = asyncio.get_event_loop()
    results = await asyncio.gather(
        *[loop.run_in_executor(None, _parse_feed, feed) for feed in FEEDS]
    )

    combined = [article for feed_articles in results for article in feed_articles]

    # Deduplicate by title (case-insensitive), keeping first occurrence
    seen = set()
    unique = []
    for article in combined:
        key = article["title"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(article)

    # Sort: known dates first (descending), unknowns at end
    def sort_key(a):
        p = a.get("_parsed")
        if p is None:
            return (1, 0)
        return (0, -time.mktime(p))

    unique.sort(key=sort_key)

    # Drop the internal sort key before returning
    for a in unique:
        a.pop("_parsed", None)

    return unique[:limit]


async def get_news_for_pair(pair: str) -> list:
    """Return up to 8 articles matching the given pair's keywords."""
    articles = await fetch_news(limit=50)
    keywords = PAIR_KEYWORDS.get(pair.upper(), [pair])

    matches = []
    for article in articles:
        haystack = (article["title"] + " " + article["summary"]).lower()
        if any(kw.lower() in haystack for kw in keywords):
            matches.append(article)
        if len(matches) == 8:
            break

    return matches


async def summarize_with_groq(articles: list) -> str:
    """Use Groq to produce a 3-bullet summary of the provided articles."""
    if not articles:
        return "📰 No recent forex news found."

    content = "\n\n".join(
        f"Title: {a['title']}\nSummary: {a['summary']}"
        for a in articles[:10]
    )

    try:
        response = _groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are PipMercy, a forex trading assistant. Summarize the following "
                        "forex news into exactly 3 bullet points. Each bullet point should: state "
                        "what happened, which currency pairs are affected, and what it means for "
                        "traders. Be concise, direct, and use simple language for a beginner "
                        "trader. Start each bullet with an emoji relevant to the direction "
                        "(📈 bullish, 📉 bearish, ⚠️ uncertain)."
                    ),
                },
                {"role": "user", "content": content},
            ],
        )
        return response.choices[0].message.content.strip()

    except Exception:
        headlines = "\n".join(f"• {a['title']}" for a in articles[:10])
        return f"⚠️ Could not summarize news right now. Here are the headlines:\n{headlines}"


def format_news_message(articles: list, summary: str) -> str:
    """Combine Groq summary + top 5 source links into one message."""
    sources = "\n".join(
        f"[{a['source']}] {a['title']} → {a['link']}"
        for a in articles[:5]
    )
    return (
        f"📰 Forex Market Update\n"
        f"{summary}\n"
        f"─────────────────\n"
        f"📎 Sources:\n\n"
        f"{sources}"
    )
