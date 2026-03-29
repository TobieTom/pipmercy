from datetime import datetime, timezone

from database import init_db, get_db
from journal import save_trade, close_trade, get_monthly_summary, format_monthly_report

SEP = "-" * 55

init_db()

now = datetime.now(timezone.utc)
YEAR, MONTH = now.year, now.month

# ---------------------------------------------------------------------------
# 1. Insert 6 test trades (open then close within current month)
# ---------------------------------------------------------------------------
print("Inserting test trades...")

test_trades = [
    # EURUSD — 2W 1L
    {"pair": "EURUSD", "direction": "BUY",  "entry_price": 1.0850, "stop_loss": 1.0800,
     "take_profit": 1.0950, "lot_size": 1.0, "risk_amount": 0.50, "risk_reward": 2.0,
     "_outcome": "WIN",  "_pnl": 1.00},
    {"pair": "EURUSD", "direction": "SELL", "entry_price": 1.0920, "stop_loss": 1.0960,
     "take_profit": 1.0840, "lot_size": 1.0, "risk_amount": 0.50, "risk_reward": 2.0,
     "_outcome": "WIN",  "_pnl": 0.80},
    {"pair": "EURUSD", "direction": "BUY",  "entry_price": 1.0780, "stop_loss": 1.0730,
     "take_profit": 1.0880, "lot_size": 1.0, "risk_amount": 0.50, "risk_reward": 2.0,
     "_outcome": "LOSS", "_pnl": -0.50},
    # GBPUSD — 1W 1L
    {"pair": "GBPUSD", "direction": "BUY",  "entry_price": 1.2600, "stop_loss": 1.2550,
     "take_profit": 1.2700, "lot_size": 1.0, "risk_amount": 0.50, "risk_reward": 2.0,
     "_outcome": "WIN",  "_pnl": 0.60},
    {"pair": "GBPUSD", "direction": "SELL", "entry_price": 1.2720, "stop_loss": 1.2760,
     "take_profit": 1.2640, "lot_size": 1.0, "risk_amount": 0.50, "risk_reward": 2.0,
     "_outcome": "LOSS", "_pnl": -0.40},
    # XAUUSD — 1W
    {"pair": "XAUUSD", "direction": "BUY",  "entry_price": 2000.0, "stop_loss": 1990.0,
     "take_profit": 2020.0, "lot_size": 1.0, "risk_amount": 0.50, "risk_reward": 2.0,
     "_outcome": "WIN",  "_pnl": 1.20},
]

inserted_ids = []
for t in test_trades:
    outcome = t.pop("_outcome")
    pnl = t.pop("_pnl")
    r = save_trade(t)
    tid = r["trade_id"]
    close_trade(tid, outcome, pnl)
    inserted_ids.append(tid)
    print(f"  #{tid} {t['pair']} {t['direction']} → {outcome} {pnl:+.2f}")
print()

# ---------------------------------------------------------------------------
# 2. Raw summary dict
# ---------------------------------------------------------------------------
print("TEST 1 — get_monthly_summary() raw dict")
print(SEP)
summary = get_monthly_summary(YEAR, MONTH)
skip = {"best_trade", "worst_trade", "discipline_score"}
for k, v in summary.items():
    if k in skip:
        continue
    print(f"  {k}: {v}")
best = summary["best_trade"]
worst = summary["worst_trade"]
print(f"  best_trade:  {best['pair']} {best['direction']} pnl={best['pnl']}" if best else "  best_trade: None")
print(f"  worst_trade: {worst['pair']} {worst['direction']} pnl={worst['pnl']}" if worst else "  worst_trade: None")
ds = summary["discipline_score"]
print(f"  discipline_score: {ds['score']}/100 {ds['grade']}" if ds else "  discipline_score: None")
print()

# ---------------------------------------------------------------------------
# 3. Formatted report
# ---------------------------------------------------------------------------
print("TEST 2 — format_monthly_report()")
print(SEP)
print(format_monthly_report(summary))
print()

# ---------------------------------------------------------------------------
# 4. Cleanup — delete test trades
# ---------------------------------------------------------------------------
conn = get_db()
for tid in inserted_ids:
    conn.execute("DELETE FROM trades WHERE id = ?", (tid,))
conn.commit()
conn.close()
print(f"Cleaned up {len(inserted_ids)} test trades: {inserted_ids}")
