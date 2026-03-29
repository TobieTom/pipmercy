from datetime import date, timedelta

from database import get_db

DISCIPLINE_WEIGHTS = {
    "respected_risk": 40,
    "journaled":      35,
    "traded":         25,
}


def update_today_streak(
    traded: bool = False,
    journaled: bool = False,
    respected_risk: bool = True,
) -> None:
    """Upsert today's streak row. Never downgrade an existing True field to False."""
    today = date.today().isoformat()
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM streaks WHERE date = ?", (today,)
        ).fetchone()

        if row:
            new_traded         = 1 if (row["traded"] or traded) else 0
            new_journaled      = 1 if (row["journaled"] or journaled) else 0
            new_respected_risk = 1 if (row["respected_risk"] and respected_risk) else 0
            conn.execute(
                """UPDATE streaks
                   SET traded = ?, journaled = ?, respected_risk = ?
                   WHERE date = ?""",
                (new_traded, new_journaled, new_respected_risk, today),
            )
        else:
            conn.execute(
                """INSERT INTO streaks (date, traded, journaled, respected_risk)
                   VALUES (?, ?, ?, ?)""",
                (today, int(traded), int(journaled), int(respected_risk)),
            )
        conn.commit()
    finally:
        conn.close()


def get_current_journaling_streak() -> int:
    """Count consecutive days ending today where journaled = 1."""
    conn = get_db()
    try:
        streak = 0
        check_date = date.today()
        while True:
            row = conn.execute(
                "SELECT journaled FROM streaks WHERE date = ?",
                (check_date.isoformat(),),
            ).fetchone()
            if row and row["journaled"] == 1:
                streak += 1
                check_date -= timedelta(days=1)
            else:
                break
        return streak
    finally:
        conn.close()


def get_current_win_streak() -> int:
    """Count consecutive WINs from the most recent closed trade backwards."""
    conn = get_db()
    try:
        trades = conn.execute(
            "SELECT outcome FROM trades WHERE outcome IN ('WIN','LOSS') ORDER BY closed_at DESC"
        ).fetchall()
    finally:
        conn.close()

    streak = 0
    for t in trades:
        if t["outcome"] == "WIN":
            streak += 1
        else:
            break
    return streak


def get_current_loss_streak() -> int:
    """Count consecutive LOSSes from the most recent closed trade backwards."""
    conn = get_db()
    try:
        trades = conn.execute(
            "SELECT outcome FROM trades WHERE outcome IN ('WIN','LOSS') ORDER BY closed_at DESC"
        ).fetchall()
    finally:
        conn.close()

    streak = 0
    for t in trades:
        if t["outcome"] == "LOSS":
            streak += 1
        else:
            break
    return streak


def get_discipline_score(days: int = 7) -> dict:
    """Calculate weighted discipline score over the last `days` days."""
    conn = get_db()
    today = date.today()
    start = (today - timedelta(days=days - 1)).isoformat()
    try:
        rows = conn.execute(
            "SELECT * FROM streaks WHERE date >= ? ORDER BY date DESC",
            (start,),
        ).fetchall()
        rows = [dict(r) for r in rows]
    finally:
        conn.close()

    total_days = days
    trading_days = sum(1 for r in rows if r["traded"])
    journaled_active = sum(1 for r in rows if r["traded"] and r["journaled"])
    risk_respected_days = sum(1 for r in rows if r["respected_risk"])
    # Count days that had data at all (to avoid penalising empty days as risk-violated)
    data_days = len(rows) if rows else 0

    respected_risk_rate = risk_respected_days / data_days if data_days else 1.0
    journaling_rate = journaled_active / trading_days if trading_days else 0.0

    # Weighted score
    risk_score      = respected_risk_rate * DISCIPLINE_WEIGHTS["respected_risk"]
    journal_score   = journaling_rate     * DISCIPLINE_WEIGHTS["journaled"]
    trading_score   = min(trading_days / max(total_days * 0.5, 1), 1.0) * DISCIPLINE_WEIGHTS["traded"]
    score = round(risk_score + journal_score + trading_score)

    if score >= 90:
        grade, grade_label = "A", "Elite discipline 🏆"
    elif score >= 75:
        grade, grade_label = "B", "Strong habits 💪"
    elif score >= 60:
        grade, grade_label = "C", "Room to improve 📈"
    elif score >= 40:
        grade, grade_label = "D", "Needs attention ⚠️"
    else:
        grade, grade_label = "F", "Let's reset and rebuild 🔄"

    if respected_risk_rate < 0.7:
        feedback = "You're exceeding your risk limit on some trades — tighten that stop loss."
    elif journaling_rate < 0.6:
        feedback = "You're missing trade reviews — close every trade with a note."
    elif trading_days < total_days * 0.3:
        feedback = "You haven't been showing up consistently this week."
    else:
        feedback = "Keep it up — consistency is your edge."

    return {
        "score":               score,
        "respected_risk_rate": round(respected_risk_rate, 2),
        "journaling_rate":     round(journaling_rate, 2),
        "trading_days":        trading_days,
        "total_days":          total_days,
        "grade":               grade,
        "grade_label":         grade_label,
        "feedback":            feedback,
    }


def format_streak_message() -> str:
    """Render the full discipline dashboard."""
    conn = get_db()
    try:
        has_data = conn.execute(
            "SELECT COUNT(*) FROM streaks WHERE traded = 1"
        ).fetchone()[0]
    finally:
        conn.close()

    if not has_data:
        return (
            "🔥 Discipline Dashboard\n"
            "No trading data yet — log your first trade to start tracking! 📝"
        )

    j_streak  = get_current_journaling_streak()
    win_streak  = get_current_win_streak()
    loss_streak = get_current_loss_streak()
    score_data  = get_discipline_score(7)

    return (
        f"🔥 Discipline Dashboard\n"
        f"📅 Journaling Streak: {j_streak} day{'s' if j_streak != 1 else ''} in a row\n"
        f"📈 Current Win Streak: {win_streak} win{'s' if win_streak != 1 else ''}\n"
        f"📉 Loss Streak: {loss_streak}\n"
        f"📊 7-Day Discipline Score: {score_data['score']}/100 — {score_data['grade']}\n"
        f"✅ Risk respected: {round(score_data['respected_risk_rate'] * 100)}% of days\n"
        f"📝 Trade reviews: {round(score_data['journaling_rate'] * 100)}% of days\n"
        f"📆 Active trading days: {score_data['trading_days']}/{score_data['total_days']}\n"
        f"💬 {score_data['feedback']}"
    )


def check_and_warn_loss_streak() -> str | None:
    """Return a warning message if loss streak is 3 or more, else None."""
    n = get_current_loss_streak()
    if n >= 3:
        return (
            f"⚠️ Heads up Mercy\n"
            f"You've had {n} losses in a row. This is normal — but it's also when most traders "
            f"make their worst decisions.\n"
            f"Take a breath. Review your last trades with /review. Only trade your A+ setups today."
        )
    return None
