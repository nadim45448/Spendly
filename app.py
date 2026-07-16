import datetime
import os
import re
import sqlite3

from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import generate_password_hash, check_password_hash

from database.db import (
    close_db,
    get_db,
    init_db,
    seed_db,
    get_user_by_email,
    get_user_by_id,
    get_expense_stats,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")


# ------------------------------------------------------------------ #
# Database — initialize schema and seed sample data on startup       #
# ------------------------------------------------------------------ #
with app.app_context():
    init_db()
    seed_db()

app.teardown_appcontext(close_db)


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _create_user(name: str, email: str, password: str) -> int:
    """Insert a new user row and return the new id.

    Caller is expected to have already validated ``name``/``email``/``password``.
    Raises ``sqlite3.IntegrityError`` if the email is already taken (UNIQUE).
    """
    db = get_db()
    cur = db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, generate_password_hash(password)),
    )
    db.commit()
    return cur.lastrowid


def _format_joined_date(raw: str) -> str:
    """Format a stored ``created_at`` value as "Month D, YYYY".

    SQLite's ``datetime('now')`` stores an ISO-8601 string like
    ``2026-07-14 09:30:00``. We try a couple of common shapes so the
    fallback never crashes the page render — at worst we return the
    raw string from the database. The day-of-month is stripped of its
    leading zero explicitly (strftime's ``%-d`` is POSIX-only, so we
    can't rely on it on Windows).
    """
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.datetime.strptime(raw, fmt)
        except ValueError:
            continue
        return f"{dt.strftime('%B')} {dt.day}, {dt.year}"
    return raw


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    # Redirect signed-in users away from registration
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html", name="", email="", error=None)

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    # Validation — first failure wins, keeps error messages user-friendly.
    if not name:
        return render_template("register.html", name=name, email=email,
                               error="Name is required.")
    if len(name) > 80:
        return render_template("register.html", name=name, email=email,
                               error="Name is too long (max 80 characters).")
    if not email:
        return render_template("register.html", name=name, email=email,
                               error="Email is required.")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return render_template("register.html", name=name, email=email,
                               error="Enter a valid email address.")
    if len(email) > 120:
        return render_template("register.html", name=name, email=email,
                               error="Email is too long (max 120 characters).")
    if len(password) < 8:
        return render_template("register.html", name=name, email=email,
                               error="Password must be at least 8 characters.")

    try:
        user_id = _create_user(name, email, password)
    except sqlite3.IntegrityError:
        return render_template("register.html", name=name, email=email,
                               error="An account with that email already exists.")

    session.clear()
    session["user_id"] = user_id
    return redirect(url_for("profile"))


@app.route("/login", methods=["GET", "POST"])
def login():
    # Redirect signed-in users away from the login page
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html", error=None)

    # POST — authenticate
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not email:
        return render_template("login.html", error="Email is required.")
    if not password:
        return render_template("login.html", error="Password is required.")

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.")

    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    """Render the profile page for the currently logged-in user.

    Guards in order:

    1. No ``user_id`` in the session → redirect to the login page (the
       friendlier landing flow, not a 401).
    2. ``user_id`` set but the row no longer exists → stale session.
       Clear the session and redirect to login so the user re-authenticates.
    3. Otherwise render the page with hardcoded demo data (Step 4 is UI/design only;
       real database integration happens in Step 5).
    """
    user_id = session.get("user_id")
    if user_id is None:
       return redirect(url_for("login"))

    user = get_user_by_id(user_id)
    if user is None:
       session.clear()
       return redirect(url_for("login"))

    # Hardcoded demo data for Step 4 (UI design). Step 5 will wire up real database queries.
    demo_stats = {
       "total_count": 8,
       "total_amount": 280.84,
       "by_category": [
           ("Food", 2, 109.25),
           ("Bills", 1, 89.99),
           ("Shopping", 1, 54.20),
           ("Transport", 1, 45.00),
           ("Entertainment", 1, 15.00),
           ("Health", 1, 32.40),
           ("Other", 1, 8.00),
       ],
    }

    # Pre-compute display values here so the template stays logic-free.
    joined_date = _format_joined_date(user["created_at"])
    formatted_total = f"৳ {demo_stats['total_amount']:,.2f}"
    distinct_categories = len(demo_stats["by_category"])

    return render_template(
       "profile.html",
       user=user,
       stats=demo_stats,
       joined_date=joined_date,
       formatted_total=formatted_total,
       distinct_categories=distinct_categories,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
