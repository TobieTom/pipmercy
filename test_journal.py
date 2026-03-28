from journal import (
    save_trade, close_trade, get_open_trades,
    get_trade_by_id, get_weekly_summary,
    format_trade_card, format_weekly_summary,
    get_settings, update_setting,
)
from database import init_db

init_db()

SEP = "-" * 50

# 1. Save 3 trades
print("STEP 1 — Save 3 trades")
print(SEP)
r1 = save_trade({"pair": "EURUSD", "direction": "BUY",  "entry_price": 1.0850, "stop_loss": 1.0800, "take_profit": 1.0950, "lot_size": 0.10, "risk_amount": 0.50, "risk_reward": 2.0})
r2 = save_trade({"pair": "GBPUSD", "direction": "SELL", "entry_price": 1.2700, "stop_loss": 1.2750, "take_profit": 1.2600, "lot_size": 0.25, "risk_amount": 0.50, "risk_reward": 2.0})
r3 = save_trade({"pair": "USDJPY", "direction": "BUY",  "entry_price": 149.50, "stop_loss": 149.00, "take_profit": 150.50, "lot_size": 0.10, "risk_amount": 0.50, "risk_reward": 2.0})
print(r1)
print(r2)
print(r3)
t1_id = r1["trade_id"]
t2_id = r2["trade_id"]
t3_id = r3["trade_id"]
print()

# 2. Open trades
print("STEP 2 — Open trades (expect 3)")
print(SEP)
open_trades = get_open_trades()
print(f"Open trades: {len(open_trades)}")
for t in open_trades:
    print(f"  #{t['id']} {t['pair']} {t['direction']}")
print()

# 3 & 4. Close trades
print("STEP 3 & 4 — Close Trade 1 WIN, Trade 2 LOSS")
print(SEP)
print(close_trade(t1_id, "WIN",  pnl=1.00))
print(close_trade(t2_id, "LOSS", pnl=-0.50))
print()

# 5. Trade card for Trade 1 (closed WIN)
print("STEP 5 — Trade card: Trade 1 (WIN)")
print(SEP)
print(format_trade_card(get_trade_by_id(t1_id)))
print()

# 6. Trade card for Trade 3 (still open)
print("STEP 6 — Trade card: Trade 3 (OPEN)")
print(SEP)
print(format_trade_card(get_trade_by_id(t3_id)))
print()

# 7. Weekly summary
print("STEP 7 — Weekly summary")
print(SEP)
summary = get_weekly_summary()
print(format_weekly_summary(summary))
print()

# 8. Double-close Trade 1 (should error)
print("STEP 8 — Double-close Trade 1 (expect error)")
print(SEP)
print(close_trade(t1_id, "WIN"))
print()

# 9 & 10. Update and print settings
print("STEP 9 & 10 — Update balance to 75, print settings")
print(SEP)
print(update_setting("default_balance", "75"))
settings = get_settings()
print(f"Settings: {settings}")
assert settings["default_balance"] == 75.0, "Balance update failed"
print("✅ Balance confirmed as 75.0")
