from calculator import format_position_message, calculate_position_size, calculate_rr

SEP = "-" * 50

# Test 1 — Standard case
print("TEST 1 — EURUSD standard (50 SL pips, 1:2 RR)")
print(SEP)
msg = format_position_message(
    pair="EURUSD", direction="BUY",
    entry=1.08500, stop_loss=1.08000, take_profit=1.09500,
    balance=50, risk_percent=1,
)
print(msg)
pos = calculate_position_size(50, 1, 1.08500, 1.08000, "EURUSD")
assert pos["sl_pips"] == 50, f"Expected 50 sl_pips, got {pos['sl_pips']}"
assert pos["lot_size_micro"] == 0.10, f"Expected 0.10 micro lots, got {pos['lot_size_micro']}"
assert pos["risk_amount"] == 0.50
rr = calculate_rr(1.08500, 1.08000, 1.09500, "EURUSD")
assert rr["rr_ratio"] == 2.0, f"Expected RR 2.0, got {rr['rr_ratio']}"
print("✅ All assertions passed\n")

# Test 2 — JPY pair
print("TEST 2 — USDJPY (50 SL pips)")
print(SEP)
msg = format_position_message(
    pair="USDJPY", direction="BUY",
    entry=149.500, stop_loss=149.000, take_profit=150.500,
    balance=50, risk_percent=1,
)
print(msg)
pos = calculate_position_size(50, 1, 149.500, 149.000, "USDJPY")
assert pos["sl_pips"] == 50, f"Expected 50 sl_pips, got {pos['sl_pips']}"
assert "error" not in pos, f"Unexpected error: {pos}"
print("✅ All assertions passed\n")

# Test 3 — Tight stop loss
print("TEST 3 — GBPUSD SELL (20 SL pips)")
print(SEP)
msg = format_position_message(
    pair="GBPUSD", direction="SELL",
    entry=1.27000, stop_loss=1.27200, take_profit=1.26600,
    balance=50, risk_percent=1,
)
print(msg)
pos = calculate_position_size(50, 1, 1.27000, 1.27200, "GBPUSD")
assert pos["sl_pips"] == 20, f"Expected 20 sl_pips, got {pos['sl_pips']}"
print("✅ All assertions passed\n")

# Test 4 — No take profit
print("TEST 4 — EURUSD BUY (no TP)")
print(SEP)
msg = format_position_message(
    pair="EURUSD", direction="BUY",
    entry=1.08500, stop_loss=1.08000, take_profit=None,
    balance=50, risk_percent=1,
)
print(msg)
assert "Take Profit" not in msg, "TP line should not appear when tp=None"
assert "Risk/Reward" not in msg, "RR line should not appear when tp=None"
print("✅ All assertions passed\n")
