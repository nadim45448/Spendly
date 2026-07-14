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

from database.db import close_db, get_db, init_db, seed_db, get_user_by_email

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
        return redirect(url_for("landing"))

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
    return redirect(url_for("landing"))


@app.route("/login", methods=["GET", "POST"])
def login():
    # Redirect signed-in users away from the login page
    if session.get("user_id"):
        return redirect(url_for("landing"))

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
    return redirect(url_for("landing"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    return "Profile page — coming in Step 4"


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
