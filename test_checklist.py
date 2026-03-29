import asyncio
import sqlite3
from database import init_db, get_db
from checklist import run_pretrade_checklist

SEP = "-" * 55

init_db()


def _insert_loss(pair="EURUSD"):
    """Insert a closed LOSS trade directly for testing."""
    conn = get_db()
    conn.execute(
        """INSERT INTO trades
           (pair, direction, entry_price, stop_loss, lot_size, risk_amount, outcome, pnl, closed_at)
           VALUES (?, 'SELL', 1.0900, 1.0950, 0.10, 0.75, 'LOSS', -0.75,
                   datetime('now'))""",
        (pair,),
    )
    conn.commit()
    conn.close()


async def main():
    # Test 1 — clean trade, expect all pass
    print("TEST 1 — Clean trade (EURUSD, good R:R, normal size)")
    print(SEP)
    result = await run_pretrade_checklist(
        pair="EURUSD", entry=1.0850, stop_loss=1.0800, take_profit=1.0950,
        lot_size_micro=0.10, balance=75.0,
    )
    print(repr(result) if not result else result)
    print("→ Expected: empty string (all pass)")
    print()

    # Test 2 — bad R:R (0.5:1)
    print("TEST 2 — Bad R:R (GBPUSD SELL: 20 pip SL, 10 pip TP = 0.5 RR)")
    print(SEP)
    result = await run_pretrade_checklist(
        pair="GBPUSD", entry=1.2700, stop_loss=1.2720, take_profit=1.2690,
        lot_size_micro=0.25, balance=75.0,
    )
    print(result if result else "(empty — unexpected)")
    print()

    # Test 3 — oversize position
    print("TEST 3 — Oversize position (15 micro lots on $75)")
    print(SEP)
    result = await run_pretrade_checklist(
        pair="EURUSD", entry=1.0850, stop_loss=1.0800, take_profit=1.0950,
        lot_size_micro=15.0, balance=75.0,
    )
    print(result if result else "(empty — unexpected)")
    print()

    # Test 4 — loss streak (insert 3 losses then check)
    print("TEST 4 — Loss streak (inserting 3 consecutive losses)")
    print(SEP)
    for _ in range(3):
        _insert_loss()
    result = await run_pretrade_checklist(
        pair="EURUSD", entry=1.0850, stop_loss=1.0800, take_profit=1.0950,
        lot_size_micro=0.10, balance=75.0,
    )
    print(result if result else "(empty — unexpected)")
    print()

    # Test 5 — multiple failures at once
    print("TEST 5 — Multiple failures (bad R:R + oversize + loss streak)")
    print(SEP)
    result = await run_pretrade_checklist(
        pair="GBPUSD", entry=1.2700, stop_loss=1.2720, take_profit=1.2690,
        lot_size_micro=15.0, balance=75.0,
    )
    print(result if result else "(empty — unexpected)")

asyncio.run(main())
