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
        "name": "DailyFX News",
        "url": "https://www.dailyforex.com/rss/forexnews.xml",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    },
    {
        "name": "DailyFX Analysis",
        "url": "https://www.dailyforex.com/rss/fundamentalanalysis.xml",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    },
    {
        "name": "ForexCrunch",
        "url": "https://forexcrunch.com/feed",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    },
]

CURRENCY_KEYWORDS = {
    "USD": ["USD", "Dollar", "Fed", "Federal Reserve", "FOMC", "NFP", "CPI", "inflation", "Powell"],
    "EUR": ["EUR", "Euro", "ECB", "European Central Bank", "Eurozone"],
    "GBP": ["GBP", "Pound", "Sterling", "BOE", "Bank of England"],
    "JPY": ["JPY", "Yen", "BOJ", "Bank of Japan"],
    "CAD": ["CAD", "Loonie", "BOC", "Bank of Canada", "Oil"],
    "AUD": ["AUD", "Aussie", "RBA", "Reserve Bank of Australia"],
    "NZD": ["NZD", "Kiwi", "RBNZ"],
    "CHF": ["CHF", "Franc", "SNB"],
    "XAU": ["Gold", "XAU", "bullion"],
}

_HEATMAP_PAIR_KEYWORDS = {
    "EUR/USD": ["EURUSD", "EUR/USD", "Euro Dollar"],
    "GBP/USD": ["GBPUSD", "GBP/USD", "Cable", "Pound Dollar"],
    "USD/JPY": ["USDJPY", "USD/JPY", "Dollar Yen"],
    "USD/CAD": ["USDCAD", "USD/CAD", "Dollar Loonie"],
    "AUD/USD": ["AUDUSD", "AUD/USD", "Aussie Dollar"],
    "XAU/USD": ["XAUUSD", "XAU/USD", "Gold Dollar", "Gold price"],
    "GBP/JPY": ["GBPJPY", "GBP/JPY"],
    "EUR/JPY": ["EURJPY", "EUR/JPY"],
}

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
                        "(📈 bullish, 📉 bearish, ⚠️ uncertain). "
                        "Only discuss forex and currency markets. Ignore any content about stocks, "
                        "tech companies, or non-forex topics."
                    ),
                },
                {"role": "user", "content": content},
            ],
        )
        return response.choices[0].message.content.strip()

    except Exception:
        headlines = "\n".join(f"• {a['title']}" for a in articles[:10])
        return f"⚠️ Could not summarize news right now. Here are the headlines:\n{headlines}"


def analyze_market_pressure(articles: list) -> dict:
    """Count per-article currency and pair mentions across all articles."""
    total = len(articles)

    currency_counts = {c: 0 for c in CURRENCY_KEYWORDS}
    pair_counts = {p: 0 for p in _HEATMAP_PAIR_KEYWORDS}

    for article in articles:
        haystack = (article["title"] + " " + article["summary"]).lower()
        for currency, keywords in CURRENCY_KEYWORDS.items():
            if any(kw.lower() in haystack for kw in keywords):
                currency_counts[currency] += 1
        for pair, keywords in _HEATMAP_PAIR_KEYWORDS.items():
            if any(kw.lower() in haystack for kw in keywords):
                pair_counts[pair] += 1

    sorted_currencies = dict(sorted(currency_counts.items(), key=lambda x: x[1], reverse=True))
    sorted_pairs = dict(sorted(pair_counts.items(), key=lambda x: x[1], reverse=True))

    top_currencies = [(c, n) for c, n in sorted_currencies.items() if n > 0][:3]
    top_pairs = [(p, n) for p, n in sorted_pairs.items() if n > 0][:3]

    return {
        "currencies":     sorted_currencies,
        "pairs":          sorted_pairs,
        "total_articles": total,
        "top_currencies": top_currencies,
        "top_pairs":      top_pairs,
    }


def format_heatmap_message(pressure: dict) -> str:
    """Render market pressure as a block-bar heatmap string."""
    if pressure["total_articles"] == 0:
        return "📊 No articles available for analysis right now."

    def bar(count, max_count):
        if max_count == 0:
            return ""
        length = round((count / max_count) * 8)
        return "█" * length

    def dot(count, max_count):
        if max_count == 0 or count == 0:
            return "⚪"
        ratio = count / max_count
        if ratio >= 0.6:
            return "🔴"
        if ratio >= 0.3:
            return "🟡"
        return "🟢"

    top_c = pressure["top_currencies"]
    top_p = pressure["top_pairs"]
    total = pressure["total_articles"]

    max_c = top_c[0][1] if top_c else 1
    max_p = top_p[0][1] if top_p else 1

    lines = [
        f"📊 Market Pressure — Top 3",
        f"Based on {total} recent articles",
    ]

    if top_c:
        lines.append("💱 Currencies Under Pressure:")
        for currency, count in top_c:
            b = bar(count, max_c).ljust(8)
            d = dot(count, max_c)
            lines.append(f"{d} {currency:<4} {b}  {count} articles")

    if top_p:
        lines.append("🔗 Most Active Pairs:")
        for pair, count in top_p:
            b = bar(count, max_p).ljust(8)
            d = dot(count, max_p)
            lines.append(f"{d} {pair:<9} {b}  {count} articles")

    lines.append("⚡ Focus your analysis on the pairs with most activity.")
    return "\n".join(lines)


def format_news_message(articles: list, summary: str) -> str:
    """Combine Groq summary + heatmap + top 3 source links into one message."""
    sources = "\n".join(
        f"[{a['source']}] {a['title']} → {a['link']}"
        for a in articles[:3]
    )
    pressure = analyze_market_pressure(articles)
    heatmap = format_heatmap_message(pressure)
    return (
        f"📰 Forex Market Update\n"
        f"{summary}\n"
        f"─────────────────\n"
        f"{heatmap}\n"
        f"─────────────────\n"
        f"📎 Sources:\n\n"
        f"{sources}"
    )
