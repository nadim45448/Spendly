"""Seed N realistic Indian-style expenses for a given user.

Usage:  python seed_expenses.py <user_id> <count> <months>
"""

import random
import sqlite3
import sys
from datetime import date, timedelta

from app import app
from database.db import DATABASE, get_db

# ---- Category catalog: (category, amount_low, amount_high, descriptions, weight) ---- #
# Weights roughly mirror typical Indian household spend: Food dominates, then
# Transport + Shopping + Bills, then Health + Entertainment, with "Other" filling.
CATEGORIES = [
    (
        "Food",
        50, 800,
        [
            "Chai and samosa at the corner stall",
            "Veg thali at the office canteen",
            "Masala dosa and filter coffee",
            "Chicken biryani takeaway",
            "Pani puri from the roadside vendor",
            "Idli-vada sambar breakfast",
            "Pav bhaji plate",
            "Mutton roll for evening snack",
            "Cold coffee and sandwich",
            "Family dinner at a dhaba",
            "Weekly vegetable groceries",
            "Milk and bread from the kirana store",
            "Egg curry and rice lunch",
            "South Indian thali at Saravana Bhavan",
            "Chole bhature brunch",
        ],
        30,
    ),
    (
        "Transport",
        20, 500,
        [
            "Auto rickshaw to the metro station",
            "Ola cab to the airport",
            "Uber ride back home",
            "Monthly metro pass recharge",
            "Petrol refill for the bike",
            "Rapido bike taxi to office",
            "State bus ticket to hometown",
            "Prepaid taxi from the railway station",
            "Shared auto to the market",
            "Parking fee at the mall",
        ],
        18,
    ),
    (
        "Bills",
        200, 3000,
        [
            "Electricity bill — BESCOM",
            "Airtel postpaid mobile bill",
            "Jio Fiber broadband recharge",
            "LPG cylinder refill",
            "Municipal water bill",
            "DTH recharge for the month",
            "Gas pipeline bill — Adani Gas",
            "Home maintenance society charge",
            "Credit card statement payment",
            "Insurance premium — quarterly",
        ],
        15,
    ),
    (
        "Health",
        100, 2000,
        [
            "Pharmacy — paracetamol and vitamins",
            "Consultation fee at the family doctor",
            "Blood test at Thyrocare",
            "Dental cleaning appointment",
            "Eye checkup at the optician",
            "Ayurvedic oil and medicines",
            "Gym monthly membership",
            "Yoga class drop-in fee",
        ],
        8,
    ),
    (
        "Entertainment",
        100, 1500,
        [
            "Movie ticket — PVR IMAX",
            "Netflix monthly subscription",
            "Spotify Premium renewal",
            "Book purchase at Crossword",
            "Concert ticket — NH7 Weekender",
            "Cricket match ticket at Chinnaswamy",
            "Disney+ Hotstar annual plan",
            "Bowling night with friends",
        ],
        8,
    ),
    (
        "Shopping",
        200, 5000,
        [
            "New kurta from FabIndia",
            "Smartphone cover from Amazon",
            "Running shoes from Decathlon",
            "Kitchen utensils set",
            "Festival saree purchase",
            "Bluetooth earphones — Boat",
            "Bed sheet and pillow covers",
            "School bag for the kid",
            "Mixer grinder replacement",
            "Winter jacket from Myntra",
        ],
        14,
    ),
    (
        "Other",
        50, 1000,
        [
            "Temple donation",
            "Barber shop haircut",
            "Newspaper and magazine subscription",
            "Birthday gift for a friend",
            "Laundry and ironing",
            "Mobile recharge for parents",
            "Tailoring alterations",
            "Petrol for the neighbour's car",
            "Miscellaneous household item",
        ],
        7,
    ),
]


def parse_args(argv: list[str]) -> tuple[int, int, int]:
    if len(argv) != 4:
        raise SystemExit(
            "Usage: /seed-expenses <user_id> <count> <months>\n"
            "Example: /seed-expenses 1 50 6"
        )
    try:
        user_id = int(argv[1])
        count = int(argv[2])
        months = int(argv[3])
    except ValueError:
        raise SystemExit(
            "Usage: /seed-expenses <user_id> <count> <months>\n"
            "Example: /seed-expenses 1 50 6"
        )
    if count <= 0 or months <= 0:
        raise SystemExit("count and months must be positive integers.")
    return user_id, count, months


def user_exists(db, user_id: int) -> bool:
    return (
        db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone()
        is not None
    )


def random_amount(low: float, high: float) -> float:
    return round(random.uniform(low, high), 2)


def random_date_within(months: int) -> date:
    """Random date in the past `months` calendar months, ending today (2026-07-14)."""
    today = date(2026, 7, 14)
    # Subtract 1 day from `months` months back to keep distribution in the past.
    # Walk months back: if today is 2026-07-14 and months=6, span [2026-01-14, 2026-07-14].
    year = today.year
    month = today.month - months
    while month <= 0:
        month += 12
        year -= 1
    start = date(year, month, today.day)
    span_days = (today - start).days
    if span_days <= 0:
        return today
    return start + timedelta(days=random.randint(0, span_days))


def build_expenses(count: int, months: int) -> list[tuple]:
    """Build `count` (user_id, amount, category, date, description) tuples."""
    rows: list[tuple] = []
    for _ in range(count):
        catalog = random.choices(CATEGORIES, weights=[c[4] for c in CATEGORIES], k=1)[0]
        category, low, high, descs, _ = catalog
        amount = random_amount(low, high)
        description = random.choice(descs)
        d = random_date_within(months)
        rows.append((amount, category, d.isoformat(), description))
    return rows


def insert_expenses(db, user_id: int, rows: list[tuple]) -> list[int]:
    """Insert in a single transaction; rollback on any failure."""
    ids: list[int] = []
    try:
        for amount, category, date_str, description in rows:
            cur = db.execute(
                """INSERT INTO expenses
                       (user_id, amount, category, date, description)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, amount, category, date_str, description),
            )
            ids.append(cur.lastrowid)
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise
    return ids


def main() -> None:
    user_id, count, months = parse_args(sys.argv)

    with app.app_context():
        db = get_db()

        if not user_exists(db, user_id):
            raise SystemExit(f"No user found with id {user_id}.")

        # Build and insert
        rows = build_expenses(count, months)
        ids = insert_expenses(db, user_id, rows)

        # Fetch back the inserted rows for the confirmation printout.
        placeholders = ",".join("?" for _ in ids)
        sample = db.execute(
            f"""SELECT id, amount, category, date, description
                  FROM expenses
                 WHERE id IN ({placeholders})
                 ORDER BY id
                 LIMIT 5""",
            tuple(ids),
        ).fetchall()

        # Min/max date
        range_row = db.execute(
            """SELECT MIN(date) AS lo, MAX(date) AS hi
                 FROM expenses
                WHERE id IN ({})""".format(placeholders),
            tuple(ids),
        ).fetchone()

    print(f"Inserted {len(ids)} expenses for user_id={user_id} "
          f"spanning {months} months.")
    print(f"Date range: {range_row['lo']}  to  {range_row['hi']}")
    print("Sample of 5 inserted records:")
    for row in sample:
        print(f"  id={row['id']:>4}  {row['date']}  BDT {row['amount']:>7.2f}  "
              f"{row['category']:<14}  {row['description']}")


if __name__ == "__main__":
    main()
