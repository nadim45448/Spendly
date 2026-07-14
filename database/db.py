import sqlite3
from flask import g
from werkzeug.security import generate_password_hash

DATABASE = "expense_tracker.db"


# ------------------------------------------------------------------ #
# Connection helpers                                                  #
# ------------------------------------------------------------------ #

def get_db():
    """Return a SQLite connection scoped to the current request.

    - Reuses the connection stored on ``flask.g`` within a single request.
    - Sets ``row_factory`` to ``sqlite3.Row`` so rows behave like dicts.
    - Enables foreign-key enforcement (off by default in SQLite).
    """
    if "db" not in g:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def close_db(exception=None):
    """Close the request-scoped connection, if one is open."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ------------------------------------------------------------------ #
# Schema                                                              #
# ------------------------------------------------------------------ #

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    amount      REAL    NOT NULL,
    category    TEXT    NOT NULL,
    date        TEXT    NOT NULL,
    description TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_expenses_user_id ON expenses(user_id);
CREATE INDEX IF NOT EXISTS idx_expenses_date    ON expenses(date);
"""


def init_db():
    """Create all tables and indexes if they do not already exist."""
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()


# ------------------------------------------------------------------ #
# Seed data                                                           #
# ------------------------------------------------------------------ #

def seed_db():
    """Insert the demo user and 8 sample expenses.

    Idempotent: returns early if the ``users`` table is already populated,
    so repeated calls (or repeated app starts) never duplicate data.
    """
    db = get_db()
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
        return

    db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
    )
    demo_user_id = db.execute(
        "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
    ).fetchone()["id"]

    # 8 expenses spanning the current month (July 2026) across all 7
    # fixed categories defined by the spec — "Other" appears twice.
    sample_expenses = [
        (12.50, "Food",          "2026-07-01", "Lunch at the corner cafe"),
        (45.00, "Transport",     "2026-07-03", "Rideshare to airport"),
        (89.99, "Bills",         "2026-07-05", "Internet — July"),
        (23.75, "Food",          "2026-07-07", "Weekly groceries"),
        (32.40, "Health",        "2026-07-09", "Pharmacy refill"),
        (15.00, "Entertainment", "2026-07-10", "Movie ticket"),
        (54.20, "Shopping",      "2026-07-11", "New running shoes"),
        ( 8.00, "Other",         "2026-07-12", "Donation"),
    ]
    for amount, category, date, description in sample_expenses:
        db.execute(
            """INSERT INTO expenses
                   (user_id, amount, category, date, description)
               VALUES (?, ?, ?, ?, ?)""",
            (demo_user_id, amount, category, date, description),
        )

    db.commit()


def get_user_by_email(email: str):
    """Return the user row for the given email, or None if not found.

    Uses a parameterised query and returns a sqlite3.Row (dict-like) when
    a match exists so callers can index by column name.
    """
    db = get_db()
    return db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def get_user_by_id(user_id: int):
    """Return the user row for the given id, or None if not found.

    Uses a parameterised query and returns a sqlite3.Row (dict-like) when
    a match exists so callers can index by column name. Mirrors
    ``get_user_by_email`` so routes that authenticate by id (e.g. the
    profile view) can fetch the full user record.
    """
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_expense_stats(user_id: int) -> dict:
    """Return aggregate expense statistics for the given user.

    The returned dict has three keys:

    - ``total_count``:  int — total number of expenses recorded by the user
    - ``total_amount``: float — sum of all expense amounts (0.0 when none)
    - ``by_category``: list of ``(category, count, total)`` tuples, ordered
      by ``total`` descending so the template's "top categories" list is
      already sorted.

    All queries are parameterised. ``COALESCE`` keeps the aggregate
    ``SUM`` returning 0 instead of ``None`` when the user has no rows.
    """
    db = get_db()

    totals_row = db.execute(
        """SELECT COUNT(*)            AS count,
                  COALESCE(SUM(amount), 0) AS total
             FROM expenses
            WHERE user_id = ?""",
        (user_id,),
    ).fetchone()

    by_category_rows = db.execute(
        """SELECT category,
                  COUNT(*)                 AS count,
                  COALESCE(SUM(amount), 0) AS total
             FROM expenses
            WHERE user_id = ?
         GROUP BY category
         ORDER BY total DESC""",
        (user_id,),
    ).fetchall()

    return {
        "total_count":  int(totals_row["count"]),
        "total_amount": float(totals_row["total"]),
        "by_category":  [(row["category"], int(row["count"]), float(row["total"]))
                         for row in by_category_rows],
    }
