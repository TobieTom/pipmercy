from database import init_db
from journal import save_trade, get_open_exposure, format_exposure_message
from checklist import check_currency_exposure

SEP = "-" * 55

init_db()

# Insert 3 open trades all involving USD
print("Inserting test trades...")
for trade in [
    {"pair": "EURUSD", "direction": "BUY",  "entry_price": 1.0850, "stop_loss": 1.0800,
     "take_profit": 1.0950, "lot_size": 1.0, "risk_amount": 0.50, "risk_reward": 2.0},
    {"pair": "USDJPY", "direction": "BUY",  "entry_price": 149.50, "stop_loss": 149.00,
     "take_profit": 150.50, "lot_size": 1.0, "risk_amount": 0.50, "risk_reward": 2.0},
    {"pair": "XAUUSD", "direction": "BUY",  "entry_price": 2000.0, "stop_loss": 1990.0,
     "take_profit": 2020.0, "lot_size": 1.0, "risk_amount": 0.50, "risk_reward": 2.0},
]:
    r = save_trade(trade)
    print(f"  #{r.get('trade_id')} — {trade['pair']}")
print()

# 1. Raw exposure dict
print("TEST 1 — get_open_exposure() raw dict")
print(SEP)
exp = get_open_exposure()
print(f"open_trades:          {exp['open_trades']}")
print(f"total_risk:           ${exp['total_risk']:.2f}")
print(f"max_single_currency:  {exp['max_single_currency']} ({exp['max_count']} trades)")
print("currency_exposure:")
for currency, data in exp["currency_exposure"].items():
    print(f"  {currency}: {data['trade_count']} trades, ${data['risk_amount']:.2f}, pairs={data['pairs']}")
print(f"overexposed: {[o['currency'] for o in exp['overexposed']]}")
print()

# 2. Formatted message
print("TEST 2 — format_exposure_message()")
print(SEP)
print(format_exposure_message(exp))
print()

# 3. check_currency_exposure — USDCAD (USD already in 3 trades → should warn)
print("TEST 3 — check_currency_exposure('USDCAD')")
print(SEP)
result = check_currency_exposure("USDCAD")
print(f"passed: {result['passed']}")
print(f"message: {result['message']}")
print()

# 4. check_currency_exposure — EURGBP (EUR in 1 trade, GBP in 0 → should pass)
print("TEST 4 — check_currency_exposure('EURGBP')")
print(SEP)
result = check_currency_exposure("EURGBP")
print(f"passed: {result['passed']}")
print(f"message: {result['message'] or '(none — all clear)'}")
