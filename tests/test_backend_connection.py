"""Tests for Step 5 — Profile Page Backend Connection.

Unit tests for each query function in database/queries.py, plus route
tests for GET /profile with and without authentication.
"""

import pytest
from app import app
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _login_seed_user(client):
    """Log in as the seed demo user and return the response."""
    return client.post(
        "/login",
        data={"email": "demo@spendly.com", "password": "demo123"},
        follow_redirects=False,
    )


def _get_seed_user_id(client):
    """Return the user_id of the seed user after logging in."""
    _login_seed_user(client)
    with client.session_transaction() as sess:
        return sess["user_id"]


# ------------------------------------------------------------------ #
# Unit tests — get_user_by_id                                         #
# ------------------------------------------------------------------ #

def test_get_user_by_id_valid():
    with app.app_context():
        client = app.test_client()
        user_id = _get_seed_user_id(client)

        result = get_user_by_id(user_id)
        assert result is not None
        assert result["name"] == "Demo User"
        assert result["email"] == "demo@spendly.com"
        assert "member_since" in result
        # member_since should be "Month YYYY" format
        parts = result["member_since"].split()
        assert len(parts) == 2
        assert parts[1].isdigit()


def test_get_user_by_id_missing():
    with app.app_context():
        result = get_user_by_id(999999)
        assert result is None


# ------------------------------------------------------------------ #
# Unit tests — get_summary_stats                                      #
# ------------------------------------------------------------------ #

def test_get_summary_stats_with_expenses():
    with app.app_context():
        client = app.test_client()
        user_id = _get_seed_user_id(client)

        result = get_summary_stats(user_id)
        assert result["transaction_count"] == 8
        # Sum of seed expenses: 12.50+45.00+89.99+23.75+32.40+15.00+54.20+8.00 = 280.84
        assert abs(result["total_spent"] - 280.84) < 0.01
        assert result["top_category"] == "Bills"


def test_get_summary_stats_no_expenses():
    with app.app_context():
        result = get_summary_stats(999999)
        assert result == {
            "total_spent": 0,
            "transaction_count": 0,
            "top_category": "—",
        }


# ------------------------------------------------------------------ #
# Unit tests — get_recent_transactions                                #
# ------------------------------------------------------------------ #

def test_get_recent_transactions_with_expenses():
    with app.app_context():
        client = app.test_client()
        user_id = _get_seed_user_id(client)

        result = get_recent_transactions(user_id)
        assert len(result) == 8
        # Verify newest-first ordering
        dates = [txn["date"] for txn in result]
        assert dates == sorted(dates, reverse=True)
        # Verify each item has required keys
        for txn in result:
            assert "date" in txn
            assert "description" in txn
            assert "category" in txn
            assert "amount" in txn


def test_get_recent_transactions_no_expenses():
    with app.app_context():
        result = get_recent_transactions(999999)
        assert result == []


# ------------------------------------------------------------------ #
# Unit tests — get_category_breakdown                                 #
# ------------------------------------------------------------------ #

def test_get_category_breakdown_with_expenses():
    with app.app_context():
        client = app.test_client()
        user_id = _get_seed_user_id(client)

        result = get_category_breakdown(user_id)
        # 7 distinct categories in seed data
        assert len(result) == 7
        # Ordered by amount descending
        amounts = [cat["amount"] for cat in result]
        assert amounts == sorted(amounts, reverse=True)
        # pct values are integers summing to 100
        pcts = [cat["pct"] for cat in result]
        assert all(isinstance(p, int) for p in pcts)
        assert sum(pcts) == 100
        # Each item has required keys
        for cat in result:
            assert "name" in cat
            assert "amount" in cat
            assert "pct" in cat


def test_get_category_breakdown_no_expenses():
    with app.app_context():
        result = get_category_breakdown(999999)
        assert result == []


# ------------------------------------------------------------------ #
# Route tests — GET /profile                                          #
# ------------------------------------------------------------------ #

def test_profile_unauthenticated():
    client = app.test_client()
    res = client.get("/profile", follow_redirects=False)
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_profile_authenticated_seed_user():
    client = app.test_client()
    _login_seed_user(client)

    res = client.get("/profile")
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    # User info
    assert "Demo User" in html
    assert "demo@spendly.com" in html

    # Currency symbol
    assert "৳" in html

    # Summary stats — total_spent matches seed sum
    assert "280.84" in html

    # Transaction count
    assert "8" in html

    # Top category
    assert "Bills" in html

    # Verify all 7 categories appear in the breakdown
    for category in ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]:
        assert category in html
