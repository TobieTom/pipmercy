import asyncio
from prices import get_price, get_multiple_prices, format_price_message, format_multiple_prices_message

SEP = "-" * 40

async def main():
    print("TEST 1 — EURUSD")
    print(SEP)
    data = await get_price("EURUSD")
    print(format_price_message(data))
    print()

    print("TEST 2 — USDJPY")
    print(SEP)
    data = await get_price("USDJPY")
    print(format_price_message(data))
    print()

    print("TEST 3 — XAUUSD (Gold)")
    print(SEP)
    data = await get_price("XAUUSD")
    print(format_price_message(data))
    print()

    print("TEST 4 — Multiple prices (EURUSD, GBPUSD, USDJPY)")
    print(SEP)
    prices = await get_multiple_prices(["EURUSD", "GBPUSD", "USDJPY"])
    print(format_multiple_prices_message(prices))
    print()

    print("TEST 5 — Invalid pair")
    print(SEP)
    data = await get_price("INVALID")
    print(format_price_message(data))

asyncio.run(main())
