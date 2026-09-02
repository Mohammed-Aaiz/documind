"""
Simulates the exact same HTTP flow the React browser app performs.

This is NOT a mock -- every request hits the real FastAPI backend through
the real Vite dev-server proxy (port 3000 -> port 8000) and the real
PostgreSQL database.
"""

import json
import sys
import urllib.request

BASE = "http://localhost:3000"  # Vite dev server (proxies /api -> 8000)


def api_call(method, path, token=None, body=None):
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def main():
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        status = "PASS" if condition else "FAIL"
        if condition:
            passed += 1
        else:
            failed += 1
        suffix = f" -- {detail}" if detail else ""
        print(f"  [{status}] {name}{suffix}")

    print()
    print("=" * 60)
    print("  BROWSER FLOW INTEGRATION TEST")
    print("  (React app -> Vite proxy -> FastAPI -> PostgreSQL)")
    print("=" * 60)

    # 1. Valid login
    print()
    print("1. POST /api/auth/login (valid credentials)")
    code, body = api_call("POST", "/api/auth/login", body={
        "email": "test@documind.io",
        "password": "TestPass123!",
    })
    check("Status 200", code == 200, f"got {code}")
    check("Has access_token", "access_token" in body)
    check("token_type is bearer", body.get("token_type") == "bearer")
    check("user.name is 'Test User'", body.get("user", {}).get("name") == "Test User")
    check("user.email is 'test@documind.io'", body.get("user", {}).get("email") == "test@documind.io")
    check("user.avatarUrl is null", body.get("user", {}).get("avatarUrl") is None)

    token = body.get("access_token", "")

    # 2. GET /api/auth/me with token
    print()
    print("2. GET /api/auth/me (authenticated)")
    code, body = api_call("GET", "/api/auth/me", token=token)
    check("Status 200", code == 200, f"got {code}")
    check("name matches", body.get("name") == "Test User")
    check("email matches", body.get("email") == "test@documind.io")

    # 3. GET /api/auth/me WITHOUT token
    print()
    print("3. GET /api/auth/me (no token -> should fail)")
    code, body = api_call("GET", "/api/auth/me")
    check("Status 401", code == 401, f"got {code}")
    check("Detail says 'Not authenticated'", "Not authenticated" in body.get("detail", ""))

    # 4. GET /api/auth/me with INVALID token
    print()
    print("4. GET /api/auth/me (bogus token -> should fail)")
    code, body = api_call("GET", "/api/auth/me", token="not.a.real.jwt")
    check("Status 401", code == 401, f"got {code}")
    check("Detail says 'Invalid token'", "Invalid token" in body.get("detail", ""))

    # 5. Login with WRONG password
    print()
    print("5. POST /api/auth/login (wrong password -> should fail)")
    code, body = api_call("POST", "/api/auth/login", body={
        "email": "test@documind.io",
        "password": "WrongPassword!",
    })
    check("Status 401", code == 401, f"got {code}")
    check("Detail says 'Invalid email or password'", "Invalid email or password" in body.get("detail", ""))

    # 6. Login with NONEXISTENT email
    print()
    print("6. POST /api/auth/login (unknown email -> should fail)")
    code, body = api_call("POST", "/api/auth/login", body={
        "email": "ghost@nowhere.com",
        "password": "irrelevant",
    })
    check("Status 401", code == 401, f"got {code}")
    check("Same error as wrong password (no user enumeration)", "Invalid email or password" in body.get("detail", ""))

    # 7. Logout
    print()
    print("7. POST /api/auth/logout (authenticated -> should succeed)")
    code, body = api_call("POST", "/api/auth/logout", token=token)
    check("Status 200", code == 200, f"got {code}")
    check("Message contains 'Logged out'", "Logged out" in body.get("message", ""))

    # 8. Logout WITHOUT token
    print()
    print("8. POST /api/auth/logout (no token -> should fail)")
    code, body = api_call("POST", "/api/auth/logout")
    check("Status 401", code == 401, f"got {code}")

    # Summary
    total = passed + failed
    print()
    print("=" * 60)
    print(f"  RESULTS: {passed}/{total} passed, {failed} failed")
    print("=" * 60)
    print()

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
