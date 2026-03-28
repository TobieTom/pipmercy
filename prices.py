import asyncio
from datetime import datetime

import aiohttp

from config import TWELVE_DATA_KEY

PAIR_SYMBOLS = {
    "EURUSD":  "EUR/USD",
    "GBPUSD":  "GBP/USD",
    "USDJPY":  "USD/JPY",
    "AUDUSD":  "AUD/USD",
    "USDCAD":  "USD/CAD",
    "USDCHF":  "USD/CHF",
    "NZDUSD":  "NZD/USD",
    "XAUUSD":  "XAU/USD",
    "GBPJPY":  "GBP/JPY",
    "EURJPY":  "EUR/JPY",
    "EURGBP":  "EUR/GBP",
}

_BASE_URL = "https://api.twelvedata.com/price"
_TIMEOUT = aiohttp.ClientTimeout(total=10)


def _normalize(pair: str) -> str:
    """Return uppercase pair key without slash, e.g. 'EUR/USD' → 'EURUSD'."""
    return pair.strip().upper().replace("/", "")


async def get_price(pair: str) -> dict:
    """Fetch the current price for a single forex pair from Twelve Data."""
    normalized = _normalize(pair)

    if normalized not in PAIR_SYMBOLS:
        return {"error": f"Pair {pair} not supported"}

    symbol = PAIR_SYMBOLS[normalized]

    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(
                _BASE_URL, params={"symbol": symbol, "apikey": TWELVE_DATA_KEY}
            ) as resp:
                data = await resp.json()

        if data.get("status") == "error":
            return {"error": data.get("message", f"API error for {normalized}")}

        return {
            "pair":      normalized,
            "price":     float(data["price"]),
            "symbol":    symbol,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        }

    except Exception:
        return {"error": f"Could not fetch price for {normalized}. Try again."}


async def get_multiple_prices(pairs: list) -> dict:
    """Fetch prices for multiple pairs concurrently."""
    results = await asyncio.gather(*[get_price(p) for p in pairs])
    return {_normalize(p): r for p, r in zip(pairs, results)}


def format_price_message(price_data: dict) -> str:
    """Return a multi-line formatted message for a single price result."""
    if "error" in price_data:
        return f"❌ {price_data['error']}"

    pair   = price_data["pair"]
    symbol = price_data["symbol"]
    price  = price_data["price"]
    ts     = datetime.strptime(price_data["timestamp"], "%Y-%m-%d %H:%M:%S")
    ts_str = ts.strftime("%-d %b %Y, %H:%M UTC")

    if pair == "XAUUSD":
        return (
            f"🥇 {symbol} (Gold)\n"
            f"💰 Price: ${price:,.2f}\n"
            f"🕐 Updated: {ts_str}"
        )

    return (
        f"💱 {symbol}\n"
        f"💰 Price: {price:.5f}\n"
        f"🕐 Updated: {ts_str}"
    )


def format_multiple_prices_message(prices_dict: dict) -> str:
    """Return a compact single-line-per-pair summary."""
    lines = []
    for pair, data in prices_dict.items():
        if "error" in data:
            lines.append(f"❌ {pair}: {data['error']}")
        elif pair == "XAUUSD":
            lines.append(f"🥇 {data['symbol']}: ${data['price']:,.2f}")
        else:
            lines.append(f"💱 {data['symbol']}: {data['price']:.5f}")
    return "\n".join(lines)
