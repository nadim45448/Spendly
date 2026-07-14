import pytest
from app import app


def test_get_login():
    client = app.test_client()
    res = client.get("/login")
    assert res.status_code == 200


def test_logged_in_cannot_access_auth_pages():
    client = app.test_client()
    # login first
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    # GET /login should redirect
    res = client.get("/login", follow_redirects=False)
    assert res.status_code in (301, 302)
    # GET /register should also redirect
    res = client.get("/register", follow_redirects=False)
    assert res.status_code in (301, 302)


def test_post_login_success():
    client = app.test_client()
    res = client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"}, follow_redirects=False)
    assert res.status_code in (301, 302)
    # session is stored in client cookie; verify server-side session value
    with client.session_transaction() as sess:
        assert sess.get("user_id") is not None


def test_post_login_failure():
    client = app.test_client()
    res = client.post("/login", data={"email": "demo@spendly.com", "password": "wrong"}, follow_redirects=True)
    assert b"Invalid email or password" in res.data


def test_logout_clears_session():
    client = app.test_client()
    # login first
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    with client.session_transaction() as sess:
        assert sess.get("user_id") is not None

    res = client.get("/logout", follow_redirects=False)
    assert res.status_code in (301, 302)
    with client.session_transaction() as sess:
        assert sess.get("user_id") is None
