"""Standalone query helpers for the profile page.

Each function opens its own SQLite connection, executes parameterised
queries, and closes the connection before returning.  No Flask imports
— this module is usable in any context (CLI scripts, tests, etc.).
"""

import datetime
import sqlite3

DATABASE = "expense_tracker.db"


# ------------------------------------------------------------------ #
# Private connection helper                                           #
# ------------------------------------------------------------------ #

def _get_connection():
    """Return a fresh SQLite connection with row_factory and FK pragma."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ------------------------------------------------------------------ #
# Public query functions                                              #
# ------------------------------------------------------------------ #

def get_user_by_id(user_id: int):
    """Return a dict with ``name``, ``email``, ``member_since`` or ``None``.

    ``member_since`` is formatted as "Month YYYY" (e.g. "July 2026")
    derived from the ``created_at`` column.
    """
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None

        # Format created_at → "Month YYYY"
        raw = row["created_at"]
        member_since = raw  # fallback
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.datetime.strptime(raw, fmt)
                member_since = f"{dt.strftime('%B')} {dt.year}"
                break
            except ValueError:
                continue

        return {
            "name": row["name"],
            "email": row["email"],
            "member_since": member_since,
        }
    finally:
        conn.close()


def get_summary_stats(user_id: int) -> dict:
    """Return summary statistics for the given user.

    Returns a dict with:
    - ``total_spent``: float (0.0 when no expenses)
    - ``transaction_count``: int (0 when no expenses)
    - ``top_category``: str — the category with the highest total spend,
      or ``"—"`` when the user has no expenses
    """
    conn = _get_connection()
    try:
        totals = conn.execute(
            """SELECT COUNT(*)            AS count,
                      COALESCE(SUM(amount), 0) AS total
                 FROM expenses
                WHERE user_id = ?""",
            (user_id,),
        ).fetchone()

        transaction_count = int(totals["count"])
        total_spent = float(totals["total"])

        if transaction_count == 0:
            return {
                "total_spent": 0,
                "transaction_count": 0,
                "top_category": "—",
            }

        top_row = conn.execute(
            """SELECT category
                 FROM expenses
                WHERE user_id = ?
             GROUP BY category
             ORDER BY SUM(amount) DESC
                LIMIT 1""",
            (user_id,),
        ).fetchone()

        return {
            "total_spent": total_spent,
            "transaction_count": transaction_count,
            "top_category": top_row["category"],
        }
    finally:
        conn.close()


def get_recent_transactions(user_id: int, limit: int = 10) -> list:
    """Return the most recent transactions for the given user.

    Each item is a dict with ``date``, ``description``, ``category``,
    and ``amount``.  Results are ordered newest-first by ``date``.
    Returns an empty list when the user has no expenses.
    """
    conn = _get_connection()
    try:
        rows = conn.execute(
            """SELECT date, description, category, amount
                 FROM expenses
                WHERE user_id = ?
             ORDER BY date DESC
                LIMIT ?""",
            (user_id, limit),
        ).fetchall()

        return [
            {
                "date": row["date"],
                "description": row["description"],
                "category": row["category"],
                "amount": float(row["amount"]),
            }
            for row in rows
        ]
    finally:
        conn.close()


def get_category_breakdown(user_id: int) -> list:
    """Return per-category spending breakdown for the given user.

    Each item is a dict with ``name``, ``amount``, and ``pct``
    (integer percentage of total spend).  Results are ordered by
    ``amount`` descending.  Returns an empty list when the user has
    no expenses.

    Percentages are integers that sum to exactly 100.  The largest-
    remainder method is used: floor every percentage, then distribute
    the remaining points one-at-a-time to the categories whose
    fractional parts are largest.
    """
    conn = _get_connection()
    try:
        rows = conn.execute(
            """SELECT category,
                      COALESCE(SUM(amount), 0) AS total
                 FROM expenses
                WHERE user_id = ?
             GROUP BY category
             ORDER BY total DESC""",
            (user_id,),
        ).fetchall()

        if not rows:
            return []

        grand_total = sum(float(r["total"]) for r in rows)
        if grand_total == 0:
            return []

        # Largest-remainder method for integer percentages summing to 100
        raw = []
        for r in rows:
            exact = (float(r["total"]) / grand_total) * 100
            raw.append({
                "name": r["category"],
                "amount": float(r["total"]),
                "floor": int(exact),
                "remainder": exact - int(exact),
            })

        floor_sum = sum(item["floor"] for item in raw)
        shortfall = 100 - floor_sum

        # Sort by remainder descending to decide who gets the extra points
        indices = sorted(range(len(raw)), key=lambda i: raw[i]["remainder"], reverse=True)
        for i in indices[:shortfall]:
            raw[i]["floor"] += 1

        return [
            {
                "name": item["name"],
                "amount": item["amount"],
                "pct": item["floor"],
            }
            for item in raw
        ]
    finally:
        conn.close()
