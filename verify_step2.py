"""End-to-end verification for step 2 (registration)."""
import sys

import requests

BASE = "http://localhost:5001"
SESSION = requests.Session()


def assert_eq(label, got, want):
    ok = got == want
    print(f"  {'OK ' if ok else 'FAIL'}  {label}: got={got!r} want={want!r}")
    if not ok:
        sys.exit(1)


def assert_contains(label, haystack, needle):
    ok = needle in haystack
    print(f"  {'OK ' if ok else 'FAIL'}  {label}: needle={needle!r}")
    if not ok:
        # find the navbar
        import re
        m = re.search(r'<div class="nav-links">(.*?)</div>', haystack, re.S)
        print("--- navbar:", repr(m.group(1)) if m else "NOT FOUND")
        sys.exit(1)


def assert_not_contains(label, haystack, needle):
    ok = needle not in haystack
    print(f"  {'OK ' if ok else 'FAIL'}  {label}: must not contain {needle!r}")
    if not ok:
        sys.exit(1)


def reset():
    SESSION.cookies.clear()


def main():
    # --- 1. GET /register renders the form ---
    print("\n[1] GET /register")
    reset()
    r = SESSION.get(BASE + "/register")
    assert_eq("status", r.status_code, 200)
    assert_contains("has name input", r.text, 'name="name"')
    assert_contains("has email input", r.text, 'name="email"')
    assert_contains("has password input", r.text, 'name="password"')
    assert_contains("Sign in link", r.text, 'href="/login"')
    assert_contains("Get started link", r.text, 'href="/register"')

    # --- 2. Happy path: valid form ---
    print("\n[2] POST /register happy path")
    reset()
    r = SESSION.post(BASE + "/register",
                     data={"name": "Demo Five", "email": "demo5@spendly.com",
                           "password": "password123"},
                     allow_redirects=False)
    assert_eq("redirect status", r.status_code, 302)
    assert_contains("redirect target", r.headers.get("Location", ""), "/")
    assert_contains("session cookie set", r.headers.get("Set-Cookie", ""), "session=")
    assert_eq("session cookie stored", bool(SESSION.cookies.get("session")), True)

    # --- 3. Logged-in navbar ---
    print("\n[3] navbar after login")
    r = SESSION.get(BASE + "/")
    assert_eq("status", r.status_code, 200)
    assert_contains("Log out link shown", r.text, 'href="/logout"')
    assert_not_contains("Sign in hidden", r.text, 'class="nav-cta">Get started')

    # --- 4. Logout ---
    print("\n[4] GET /logout")
    r = SESSION.get(BASE + "/logout", allow_redirects=False)
    assert_eq("redirect status", r.status_code, 302)
    assert_contains("redirect to /", r.headers.get("Location", ""), "/")
    assert_contains("session cookie cleared", r.headers.get("Set-Cookie", ""),
                    "Max-Age=0")
    r = SESSION.get(BASE + "/")
    assert_contains("navbar back to logged-out", r.text, 'href="/login"')
    assert_contains("Get started visible again", r.text, 'href="/register"')
    assert_not_contains("Log out hidden", r.text, 'href="/logout"')

    # --- 5. Validation: empty name ---
    print("\n[5] empty name")
    reset()
    r = SESSION.post(BASE + "/register",
                     data={"name": "   ", "email": "valid@example.com",
                           "password": "password123"})
    assert_eq("status (re-render)", r.status_code, 200)
    assert_contains("error shown", r.text, "Name is required.")
    assert_contains("email sticky", r.text, 'value="valid@example.com"')

    # --- 6. Validation: invalid email ---
    print("\n[6] invalid email")
    reset()
    r = SESSION.post(BASE + "/register",
                     data={"name": "Some One", "email": "foo@bar",
                           "password": "password123"})
    assert_eq("status", r.status_code, 200)
    assert_contains("error shown", r.text, "Enter a valid email address.")
    assert_contains("name sticky", r.text, 'value="Some One"')

    # --- 7. Validation: short password ---
    print("\n[7] short password")
    reset()
    r = SESSION.post(BASE + "/register",
                     data={"name": "Some One", "email": "another@example.com",
                           "password": "7chars7"})
    assert_eq("status", r.status_code, 200)
    assert_contains("error shown", r.text,
                    "Password must be at least 8 characters.")

    # --- 8. Duplicate email ---
    print("\n[8] duplicate email (demo@spendly.com)")
    reset()
    r = SESSION.post(BASE + "/register",
                     data={"name": "Imposter", "email": "demo@spendly.com",
                           "password": "password123"})
    assert_eq("status (re-render, no 500)", r.status_code, 200)
    assert_contains("error shown", r.text,
                    "An account with that email already exists.")
    assert_contains("name sticky", r.text, 'value="Imposter"')

    # --- 9. Wrong method (PUT) ---
    print("\n[9] unsupported method on /register")
    r = requests.put(BASE + "/register",
                     data={"name": "x", "email": "x@x.com",
                           "password": "password123"})
    assert_eq("status (405)", r.status_code, 405)

    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    main()
