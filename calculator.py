import math

# Lot size constants
STANDARD_LOT = 100_000
MINI_LOT = 10_000
MICRO_LOT = 1_000

# Fixed pip value per micro lot for USD-quote pairs
MICRO_PIP_VALUE_USD = 0.10


def _pip_size(pair: str) -> float:
    pair = pair.upper()
    if "JPY" in pair or pair == "XAUUSD":
        return 0.01
    return 0.0001


def calculate_pips(entry: float, price: float, pair: str) -> float:
    """Return the number of pips between entry and price for the given pair."""
    return round(abs(entry - price) / _pip_size(pair), 1)


def calculate_pip_value(pair: str, lot_size_micro: float) -> float:
    """
    Return dollar value per pip for a given lot size in micro lots.

    For USD-quote pairs (EURUSD, GBPUSD, AUDUSD, NZDUSD, XAUUSD) this is exact.
    For USD-base pairs (USDJPY, USDCAD, USDCHF) and cross pairs (EURGBP, EURJPY,
    GBPJPY, etc.) this is an approximation — the true value depends on the current
    exchange rate, which is not available here.
    """
    return lot_size_micro * MICRO_PIP_VALUE_USD


def calculate_position_size(
    balance: float,
    risk_percent: float,
    entry: float,
    stop_loss: float,
    pair: str,
) -> dict:
    """
    Calculate position size so that hitting stop loss loses exactly risk_amount.

    Returns a dict with keys:
        lot_size_micro, lot_size_standard, risk_amount, sl_pips, pip_value_per_micro
    or {"error": <message>} on invalid input.
    """
    sl_pips = calculate_pips(entry, stop_loss, pair)

    if sl_pips == 0:
        return {"error": "Stop loss cannot equal entry price"}

    risk_amount = balance * (risk_percent / 100)

    # Raw micro lots required; floor to never exceed intended risk
    raw = risk_amount / (sl_pips * MICRO_PIP_VALUE_USD)
    lot_size_micro = math.floor(raw * 100) / 100

    if lot_size_micro < 0.01:
        return {"error": "Position too small for this account size and stop loss"}

    return {
        "lot_size_micro": round(lot_size_micro, 2),
        "lot_size_standard": round(lot_size_micro / 100, 4),
        "risk_amount": round(risk_amount, 2),
        "sl_pips": sl_pips,
        "pip_value_per_micro": MICRO_PIP_VALUE_USD,
    }


def calculate_rr(
    entry: float,
    stop_loss: float,
    take_profit: float,
    pair: str,
) -> dict:
    """Return sl_pips, tp_pips, rr_ratio, and rr_formatted for a trade."""
    sl_pips = calculate_pips(entry, stop_loss, pair)

    if sl_pips == 0:
        return {"error": "Invalid stop loss"}

    tp_pips = calculate_pips(entry, take_profit, pair)
    rr_ratio = round(tp_pips / sl_pips, 2)

    return {
        "sl_pips": sl_pips,
        "tp_pips": tp_pips,
        "rr_ratio": rr_ratio,
        "rr_formatted": f"1:{rr_ratio:.2f}",
    }


def format_position_message(
    pair: str,
    direction: str,
    entry: float,
    stop_loss: float,
    take_profit: float | None,
    balance: float,
    risk_percent: float,
) -> str:
    """
    Build a human-readable position sizing message.

    Returns the message string, or an error string if sizing fails.
    """
    pos = calculate_position_size(balance, risk_percent, entry, stop_loss, pair)
    if "error" in pos:
        return f"❌ Error: {pos['error']}"

    pip_sz = _pip_size(pair)
    sl_pips = pos["sl_pips"]

    lines = [
        f"📊 Position Size for {pair.upper()} {direction.upper()}",
        f"💰 Account: ${balance:.2f} | Risk: {risk_percent}% (${pos['risk_amount']:.2f})",
        f"📍 Entry: {entry:.5f}",
        f"🛑 Stop Loss: {stop_loss:.5f} ({sl_pips:.0f} pips)",
    ]

    if take_profit is not None:
        rr = calculate_rr(entry, stop_loss, take_profit, pair)
        if "error" not in rr:
            lines.append(
                f"🎯 Take Profit: {take_profit:.5f} ({rr['tp_pips']:.0f} pips)"
            )

    lines.append(
        f"📦 Lot Size: {pos['lot_size_micro']:.2f} micro lots "
        f"({pos['lot_size_standard']:.4f} standard)"
    )

    if take_profit is not None:
        rr = calculate_rr(entry, stop_loss, take_profit, pair)
        if "error" not in rr:
            lines.append(f"⚖️ Risk/Reward: {rr['rr_formatted']}")

    lines.append(f"⚠️ Max loss on this trade: ${pos['risk_amount']:.2f}")

    return "\n".join(lines)
