"""Seed a single realistic random Bangladeshi user into the database.

Usage:  python seed_user.py
"""

import random
import re
from datetime import datetime

from app import app
from database.db import get_db
from werkzeug.security import generate_password_hash

# ---- Bangladeshi name pools (representative across regions) ---- #
FIRST_NAMES_M = [
    "Nadim", "Rahim", "Karim", "Shakib", "Tamim", "Mushfiq", "Mahmudullah",
    "Mashrafe", "Rubel", "Taskin", "Mustafizur", "Sabbir", "Liton", "Soumya",
    "Imrul", "Mominul", "Mushfiqur", "Shakib", "Anamul", "Nasir", "Faruq",
    "Rashed", "Jasim", "Babul", "Selim", "Jalal", "Ibrahim", "Yusuf",
    "Hasan", "Hossain", "Kamal", "Jamal", "Rakib", "Sabbir", "Tareq",
    "Rumi", "Faisal", "Arif", "Asif", "Saif", "Riyad", "Mehedi", "Sanjid",
]
FIRST_NAMES_F = [
    "Ayesha", "Fatema", "Nusrat", "Tasnim", "Sumaiya", "Laboni", "Mim",
    "Tisha", "Mahi", "Ritu", "Priya", "Anika", "Sadia", "Maria", "Sanjida",
    "Tania", "Nadia", "Jui", "Mousumi", "Rima", "Shila", "Rekha", "Mitu",
    "Sharmin", "Shamim", "Salma", "Rina", "Lucky", "Popy", "Bithi",
    "Khadija", "Rabeya", "Sumi", "Mst.", "Nazia", "Sumiya",
]
LAST_NAMES = [
    "Hossain", "Rahman", "Khan", "Islam", "Ahmed", "Uddin", "Akter",
    "Begum", "Chowdhury", "Sheikh", "Siddique", "Sarkar", "Miah", "Bhuiyan",
    "Talukder", "Mondal", "Das", "Dewan", "Majumder", "Saha", "Roy",
    "Haque", "Jamil", "Molla", "Howlader", "Faruq", "Habib", "Karim",
    "Mahmud", "Matin", "Rashid", "Saber", "Sattar", "Zaman", "Mannan",
]

DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"]


def slugify(text: str) -> str:
    """Lowercase, strip diacritics-free, keep ASCII letters/digits only."""
    text = text.lower()
    text = re.sub(r"[^a-z]", "", text)
    return text


def random_name() -> tuple[str, str]:
    """Return (first, last) with realistic gendered pairings."""
    if random.random() < 0.5:
        first = random.choice(FIRST_NAMES_M)
    else:
        first = random.choice(FIRST_NAMES_F)
    last = random.choice(LAST_NAMES)
    return first, last


def make_email(first: str, last: str) -> str:
    """Build first.last##@domain.com — strip Ms./Mst. prefixes."""
    first_slug = slugify(first)
    last_slug = slugify(last)
    suffix = random.randint(10, 999)
    domain = random.choice(DOMAINS)
    return f"{first_slug}.{last_slug}{suffix}@{domain}"


def email_exists(db, email: str) -> bool:
    return (
        db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
        is not None
    )


def insert_user(db, name: str, email: str) -> int:
    cur = db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, generate_password_hash("password123")),
    )
    db.commit()
    return cur.lastrowid


def main() -> None:
    with app.app_context():
        db = get_db()

        # Make sure schema exists in case app.py wasn't run first.
        from database.db import init_db, seed_db

        init_db()
        seed_db()

        # Generate until unique.
        for _ in range(200):
            first, last = random_name()
            name = f"{first} {last}"
            email = make_email(first, last)
            if not email_exists(db, email):
                break
        else:
            raise RuntimeError("Could not generate a unique email after 200 tries")

        user_id = insert_user(db, name, email)
        print(f"id:    {user_id}")
        print(f"name:  {name}")
        print(f"email: {email}")


if __name__ == "__main__":
    main()
