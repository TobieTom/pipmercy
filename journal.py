import random
from datetime import datetime, timezone, timedelta

from database import get_db

_REQUIRED_FIELDS = ["pair", "direction", "entry_price", "stop_loss", "lot_size", "risk_amount"]

_MOTIVATIONAL = [
    "Keep going Mercy, you're building good habits! 💪",
    "Consistency beats perfection. Stay the course! 🎯",
    "Every trade is a lesson. Keep journaling! 📝",
    "Discipline today, profits tomorrow. You've got this! 🚀",
    "Small gains compound into big results. Stay focused! 🔥",
]


def _row_to_dict(row) -> dict:
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def save_trade(trade: dict) -> dict:
    for field in _REQUIRED_FIELDS:
        if field not in trade or trade[field] is None:
            return {"error": f"Missing required field: {field}"}

    direction = str(trade["direction"]).upper()
    if direction not in ("BUY", "SELL"):
        return {"error": "Direction must be BUY or SELL"}

    pair = str(trade["pair"]).upper().strip()
    if " " in pair:
        return {"error": "Pair must not contain spaces"}

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO trades
                (pair, direction, entry_price, stop_loss, take_profit,
                 lot_size, risk_amount, risk_reward, notes, outcome)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
            """,
            (
                pair,
                direction,
                trade["entry_price"],
                trade["stop_loss"],
                trade.get("take_profit"),
                trade["lot_size"],
                trade["risk_amount"],
                trade.get("risk_reward"),
                trade.get("notes"),
            ),
        )
        conn.commit()
        trade_id = cur.lastrowid
        conn.close()
        return {"success": True, "trade_id": trade_id, "message": f"Trade saved! ID: #{trade_id}"}
    except Exception as e:
        return {"error": str(e)}


def close_trade(trade_id: int, outcome: str, pnl: float = None) -> dict:
    outcome = outcome.upper()
    if outcome not in ("WIN", "LOSS"):
        return {"error": "Outcome must be WIN or LOSS"}

    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
        if row is None:
            return {"error": f"Trade #{trade_id} not found"}
        if row["outcome"] != "OPEN":
            return {"error": f"Trade #{trade_id} is already closed"}

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE trades SET outcome = ?, pnl = ?, closed_at = ? WHERE id = ?",
            (outcome, pnl, now, trade_id),
        )
        conn.commit()
        return {"success": True, "message": f"Trade #{trade_id} closed as {outcome}"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


def get_open_trades() -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM trades WHERE outcome = 'OPEN' ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_trade_by_id(trade_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def get_all_trades(limit: int = 50) -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM trades ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def get_weekly_summary() -> dict:
    now = datetime.now(timezone.utc)
    monday = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    monday_str = monday.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()

    closed = conn.execute(
        """
        SELECT * FROM trades
        WHERE outcome IN ('WIN', 'LOSS')
          AND created_at >= ?
        ORDER BY created_at DESC
        """,
        (monday_str,),
    ).fetchall()
    closed = [dict(r) for r in closed]

    open_count = conn.execute(
        "SELECT COUNT(*) FROM trades WHERE outcome = 'OPEN'"
    ).fetchone()[0]
    conn.close()

    total = len(closed)
    wins = sum(1 for t in closed if t["outcome"] == "WIN")
    losses = total - wins
    win_rate = round((wins / total) * 100, 1) if total else 0.0
    pnl_values = [t["pnl"] for t in closed if t["pnl"] is not None]
    total_pnl = round(sum(pnl_values), 2) if pnl_values else 0.0
    rr_values = [t["risk_reward"] for t in closed if t["risk_reward"] is not None]
    avg_rr = round(sum(rr_values) / len(rr_values), 2) if rr_values else 0.0

    best = max(closed, key=lambda t: (t["pnl"] or 0), default=None)
    worst = min(closed, key=lambda t: (t["pnl"] or 0), default=None)

    return {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "avg_rr": avg_rr,
        "open_trades": open_count,
        "best_trade": best,
        "worst_trade": worst,
    }


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _fmt_dt(ts_str: str | None) -> str:
    if not ts_str:
        return "—"
    try:
        dt = datetime.strptime(ts_str[:19], "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%-d %b %Y, %H:%M")
    except Exception:
        return ts_str


def format_trade_card(trade: dict) -> str:
    tid = trade["id"]
    pair = trade["pair"]
    direction = trade["direction"]
    entry = trade["entry_price"]
    sl = trade["stop_loss"]
    tp = trade.get("take_profit")
    lot = trade.get("lot_size")
    rr = trade.get("risk_reward")
    risk = trade.get("risk_amount")
    outcome = trade.get("outcome", "OPEN")
    pnl = trade.get("pnl")
    created = _fmt_dt(trade.get("created_at"))
    closed = _fmt_dt(trade.get("closed_at"))

    lines = [f"📋 Trade #{tid} — {pair} {direction}"]

    tp_part = f" | 🎯 TP: {tp:.5f}" if tp is not None else ""
    lines.append(f"📍 Entry: {entry:.5f} | 🛑 SL: {sl:.5f}{tp_part}")

    if lot is not None and rr is not None:
        lines.append(f"📦 Size: {lot:.2f} micro | ⚖️ R:R: 1:{rr:.2f}")
    elif lot is not None:
        lines.append(f"📦 Size: {lot:.2f} micro")

    if risk is not None:
        lines.append(f"💰 Risk: ${risk:.2f}")

    if outcome == "OPEN":
        lines.append(f"📅 Opened: {created}")
        lines.append("🔵 Status: OPEN")
    else:
        lines.append(f"📅 Opened: {created} | Closed: {closed}")
        icon = "🟢" if outcome == "WIN" else "🔴"
        pnl_str = f"+${pnl:.2f}" if pnl and pnl >= 0 else f"-${abs(pnl):.2f}" if pnl else "N/A"
        lines.append(f"{icon} {outcome} — P&L: {pnl_str}")

    return "\n".join(lines)


def format_weekly_summary(summary: dict) -> str:
    if summary["total_trades"] == 0:
        return (
            "📊 No closed trades this week yet.\n"
            "Open a trade and start building your journal! 📝"
        )

    w = summary["wins"]
    l = summary["losses"]
    wr = summary["win_rate"]
    pnl = summary["total_pnl"]
    pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
    avg_rr = summary["avg_rr"]

    best = summary["best_trade"]
    worst = summary["worst_trade"]
    best_str = f"{best['pair']} {best['direction']} +${best['pnl']:.2f}" if best and best["pnl"] is not None else "—"
    worst_pnl = worst["pnl"] if worst and worst["pnl"] is not None else None
    worst_str = (
        f"{worst['pair']} {worst['direction']} -${abs(worst_pnl):.2f}"
        if worst_pnl is not None else "—"
    )

    lines = [
        "📊 This Week's Performance",
        f"🏆 Record: {w}W — {l}L ({wr}% win rate)",
        f"💰 Net P&L: {pnl_str}",
        f"⚖️ Avg R:R: 1:{avg_rr:.2f}",
        f"📂 Open trades: {summary['open_trades']}",
        f"🥇 Best trade: {best_str}",
        f"💀 Worst trade: {worst_str}",
        random.choice(_MOTIVATIONAL),
    ]

    try:
        from streaks import get_discipline_score
        sd = get_discipline_score(7)
        lines.append(
            f"\n📊 Discipline Score: {sd['score']}/100 — {sd['grade']}\n{sd['feedback']}"
        )
    except Exception:
        pass

    return "\n".join(lines)


_DAILY_MOTIVATIONAL = [
    "🌙 Rest well. Tomorrow's opportunities will come.",
    "🌙 Good session. Reset and come back sharper tomorrow.",
    "💤 Every day is a new edge. See you tomorrow.",
    "🌟 Small steps every day. You're building something real.",
    "🛌 Log off, recharge. The market will be here tomorrow.",
]

_NO_TRADES_MOTIVATIONAL = [
    "💡 Consistency beats intensity — show up tomorrow.",
    "📆 No trades is sometimes the right trade. See you tomorrow.",
    "⏳ Patience is a strategy. Tomorrow brings new setups.",
    "🧘 Rest days matter too. Come back fresh.",
    "💡 Protecting capital on slow days is a skill. Well done.",
]


def get_today_summary() -> dict:
    """Return trade stats for today (opened or closed today)."""
    conn = get_db()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    opened_today = conn.execute(
        "SELECT * FROM trades WHERE created_at LIKE ?", (f"{today}%",)
    ).fetchall()
    opened_today = [dict(r) for r in opened_today]

    closed_today = conn.execute(
        "SELECT * FROM trades WHERE closed_at LIKE ? AND outcome IN ('WIN','LOSS')",
        (f"{today}%",),
    ).fetchall()
    closed_today = [dict(r) for r in closed_today]

    open_trades_all = conn.execute(
        "SELECT * FROM trades WHERE outcome = 'OPEN'"
    ).fetchall()
    open_trades_all = [dict(r) for r in open_trades_all]

    # Weekly P&L (Mon 00:00 UTC to now)
    now = datetime.now(timezone.utc)
    monday = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    monday_str = monday.strftime("%Y-%m-%d %H:%M:%S")
    weekly_closed = conn.execute(
        "SELECT * FROM trades WHERE outcome IN ('WIN','LOSS') AND created_at >= ?",
        (monday_str,),
    ).fetchall()
    weekly_closed = [dict(r) for r in weekly_closed]
    conn.close()

    wins_today   = sum(1 for t in closed_today if t["outcome"] == "WIN")
    losses_today = len(closed_today) - wins_today
    pnl_today    = round(sum(t["pnl"] for t in closed_today if t["pnl"] is not None), 2)
    open_exposure = round(
        sum(t["risk_amount"] for t in open_trades_all if t["risk_amount"] is not None), 2
    )
    weekly_pnl = round(
        sum(t["pnl"] for t in weekly_closed if t["pnl"] is not None), 2
    )

    best_today = (
        max(closed_today, key=lambda t: (t["pnl"] or 0))
        if closed_today else None
    )
    worst_today = (
        min(closed_today, key=lambda t: (t["pnl"] or 0))
        if closed_today else None
    )

    return {
        "date":           now.strftime("%-d %b %Y"),
        "trades_opened":  len(opened_today),
        "trades_closed":  len(closed_today),
        "wins_today":     wins_today,
        "losses_today":   losses_today,
        "pnl_today":      pnl_today,
        "open_trades":    len(open_trades_all),
        "open_exposure":  open_exposure,
        "weekly_pnl":     weekly_pnl,
        "weekly_trades":  len(weekly_closed),
        "best_today":     best_today,
        "worst_today":    worst_today,
    }


def _pnl_str(pnl: float) -> str:
    if pnl > 0:
        return f"+${pnl:.2f}"
    if pnl < 0:
        return f"-${abs(pnl):.2f}"
    return "±$0.00"


def format_daily_summary(summary: dict) -> str:
    """Format today's P&L report for Telegram."""
    date = summary.get("date", "Today")
    open_n = summary.get("open_trades", 0)
    weekly_pnl = summary.get("weekly_pnl", 0.0)
    weekly_n = summary.get("weekly_trades", 0)

    if summary.get("trades_closed", 0) == 0 and summary.get("trades_opened", 0) == 0:
        weekly_str = _pnl_str(weekly_pnl)
        return (
            f"📊 *Daily Report — {date}*\n\n"
            f"No trades logged today.\n\n"
            f"📂 Open positions: {open_n}\n"
            f"📅 This week so far: {weekly_str} ({weekly_n} trades)\n\n"
            f"─────────────────\n"
            f"{random.choice(_NO_TRADES_MOTIVATIONAL)}"
        )

    pnl = summary["pnl_today"]
    wins = summary["wins_today"]
    losses = summary["losses_today"]
    closed = summary["trades_closed"]
    exposure = summary["open_exposure"]
    weekly_str = _pnl_str(weekly_pnl)

    best = summary.get("best_today")
    worst = summary.get("worst_today")
    best_str = (
        f"{best['pair']} {best['direction']} {_pnl_str(best['pnl'])}"
        if best and best.get("pnl") is not None else "—"
    )
    worst_str = (
        f"{worst['pair']} {worst['direction']} {_pnl_str(worst['pnl'])}"
        if worst and worst.get("pnl") is not None else "—"
    )

    return (
        f"📊 *Daily Trading Report — {date}*\n\n"
        f"💰 *Today's P&L: {_pnl_str(pnl)}*\n"
        f"✅ {wins} win{'s' if wins != 1 else ''}  |  "
        f"❌ {losses} loss{'es' if losses != 1 else ''}  |  "
        f"{closed} trade{'s' if closed != 1 else ''} closed\n\n"
        f"📈 Best trade: {best_str}\n"
        f"📉 Worst trade: {worst_str}\n\n"
        f"📂 *Open positions: {open_n}*\n"
        f"⚠️ At-risk capital: ${exposure:.2f}\n\n"
        f"📅 *This week so far: {weekly_str}* ({weekly_n} trades)\n\n"
        f"─────────────────\n"
        f"{random.choice(_DAILY_MOTIVATIONAL)}"
    )


# ---------------------------------------------------------------------------
# Settings
def get_trade_context(trade_id: int) -> dict:
    """Return a closed trade plus lifetime and pair-level performance stats."""
    conn = get_db()

    trade_row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    trade = dict(trade_row) if trade_row else None

    closed = conn.execute(
        "SELECT * FROM trades WHERE outcome IN ('WIN','LOSS')"
    ).fetchall()
    closed = [dict(r) for r in closed]

    wins = sum(1 for t in closed if t["outcome"] == "WIN")
    losses = len(closed) - wins
    win_rate = round((wins / len(closed)) * 100, 1) if closed else 0.0
    rr_values = [t["risk_reward"] for t in closed if t["risk_reward"] is not None]
    avg_rr = round(sum(rr_values) / len(rr_values), 2) if rr_values else 0.0

    pair = trade["pair"] if trade else None
    same_pair = [t for t in closed if t["pair"] == pair] if pair else []
    same_pair_wins = sum(1 for t in same_pair if t["outcome"] == "WIN")
    same_pair_win_rate = round((same_pair_wins / len(same_pair)) * 100, 1) if same_pair else 0.0

    conn.close()
    return {
        "trade":               trade,
        "total_closed_trades": len(closed),
        "wins":                wins,
        "losses":              losses,
        "win_rate":            win_rate,
        "avg_rr":              avg_rr,
        "same_pair_trades":    len(same_pair),
        "same_pair_wins":      same_pair_wins,
        "same_pair_win_rate":  same_pair_win_rate,
    }


# ---------------------------------------------------------------------------

def get_settings() -> dict:
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    result = {}
    for row in rows:
        k, v = row["key"], row["value"]
        if k == "default_balance":
            result[k] = float(v)
        elif k == "default_risk_percent":
            result[k] = float(v)
        else:
            result[k] = v
    return result


def update_setting(key: str, value: str) -> dict:
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}
