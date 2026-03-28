import asyncio
from news import fetch_news, get_news_for_pair, summarize_with_groq, format_news_message

SEP = "-" * 50

async def main():
    # 1. Fetch top 10 articles
    print("TEST 1 — fetch_news(limit=10)")
    print(SEP)
    articles = await fetch_news(limit=10)
    print(f"Fetched {len(articles)} articles:")
    for a in articles:
        print(f"  [{a['source']}] {a['title']}")
    print()

    # 2. Filter for XAUUSD
    print("TEST 2 — get_news_for_pair('XAUUSD')")
    print(SEP)
    gold_articles = await get_news_for_pair("XAUUSD")
    print(f"Matched {len(gold_articles)} articles for XAUUSD:")
    for a in gold_articles:
        print(f"  [{a['source']}] {a['title']}")
    print()

    # 3. Groq summary of top 5 articles
    print("TEST 3 — summarize_with_groq (top 5 articles)")
    print(SEP)
    summary = await summarize_with_groq(articles[:5])
    print(summary)
    print()

    # 4. Full formatted message
    print("TEST 4 — format_news_message")
    print(SEP)
    print(format_news_message(articles, summary))

asyncio.run(main())
