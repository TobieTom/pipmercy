import asyncio
from journal import get_all_trades
from coach import generate_trade_review

SEP = "-" * 55

async def main():
    trades = get_all_trades(limit=20)
    closed = [t for t in trades if t["outcome"] != "OPEN"]

    if not closed:
        print("No closed trades found. Run test_journal.py first.")
        return

    print(f"Found {len(closed)} closed trade(s).")
    wins  = [t for t in closed if t["outcome"] == "WIN"]
    losses = [t for t in closed if t["outcome"] == "LOSS"]
    print(f"  WINs: {len(wins)}  |  LOSSes: {len(losses)}")
    print()

    # Most recent closed trade
    print("TEST 1 — Most recent closed trade")
    print(SEP)
    review = await generate_trade_review(closed[0]["id"])
    print(review or "(empty — review generation failed)")
    print()

    # WIN trade (if distinct from first)
    if wins and wins[0]["id"] != closed[0]["id"]:
        print(f"TEST 2 — WIN trade #{wins[0]['id']} ({wins[0]['pair']})")
        print(SEP)
        review = await generate_trade_review(wins[0]["id"])
        print(review or "(empty)")
        print()

    # LOSS trade (if distinct)
    if losses and losses[0]["id"] != closed[0]["id"]:
        print(f"TEST 3 — LOSS trade #{losses[0]['id']} ({losses[0]['pair']})")
        print(SEP)
        review = await generate_trade_review(losses[0]["id"])
        print(review or "(empty)")
        print()

asyncio.run(main())
