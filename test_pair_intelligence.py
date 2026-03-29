import asyncio
from news import get_pair_intelligence, format_pair_intelligence_message

SEP = "-" * 55

async def main():
    for pair in ["EURUSD", "XAUUSD", "GBPUSD"]:
        print(f"TEST — get_pair_intelligence('{pair}')")
        print(SEP)
        intel = await get_pair_intelligence(pair)
        if "error" in intel:
            print(f"ERROR: {intel['error']}")
        else:
            print(f"pair:                  {intel['pair']}")
            print(f"base_currency:         {intel['base_currency']}")
            print(f"quote_currency:        {intel['quote_currency']}")
            print(f"pair_article_count:    {intel['pair_article_count']}")
            print(f"base_pressure:         {intel['base_pressure']}")
            print(f"quote_pressure:        {intel['quote_pressure']}")
            print(f"total_articles_scanned:{intel['total_articles_scanned']}")
            print(f"has_specific_articles: {intel['has_specific_articles']}")
            print(f"groq_analysis (first 100 chars): {intel['groq_analysis'][:100]}...")
        print()

    print("FORMATTED MESSAGE — XAUUSD")
    print(SEP)
    intel = await get_pair_intelligence("XAUUSD")
    if "error" in intel:
        print(f"ERROR: {intel['error']}")
    else:
        print(format_pair_intelligence_message(intel))

asyncio.run(main())
