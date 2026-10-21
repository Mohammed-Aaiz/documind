"""Tests for the authentication flow.

Covers:
  • Creating a test user
  • POST /api/auth/login  – valid & invalid credentials
  • GET  /api/auth/me      – authenticated & unauthenticated
  • POST /api/auth/logout  – authenticated
  • Inactive user handling
  • Missing / expired / malformed token handling
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from auth.models import User
from auth.routes import create_access_token

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LOGIN_URL = "/api/auth/login"
ME_URL = "/api/auth/me"
LOGOUT_URL = "/api/auth/logout"


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. User creation via fixture
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_test_user(create_test_user):
    """Verify the fixture creates a user in the database."""
    user = await create_test_user(
        email="alice@example.com",
        password="P@ssw0rd!",
        name="Alice",
    )
    assert user.email == "alice@example.com"
    assert user.name == "Alice"
    assert user.is_active is True
    assert user.id is not None


# ---------------------------------------------------------------------------
# 2. POST /api/auth/login
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, create_test_user):
    """Login with valid credentials returns a JWT + UserProfile."""
    await create_test_user(email="bob@test.com", password="Secret123!", name="Bob")

    resp = await client.post(LOGIN_URL, json={
        "email": "bob@test.com",
        "password": "Secret123!",
    })
    assert resp.status_code == 200
    body = resp.json()

    # Token fields
    assert "access_token" in body
    assert body["token_type"] == "bearer"

    # User profile matches the frontend shape
    user = body["user"]
    assert user["name"] == "Bob"
    assert user["email"] == "bob@test.com"
    assert "avatarUrl" in user  # may be null


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, create_test_user):
    """Wrong password → 401."""
    await create_test_user(email="carol@test.com", password="GoodPass1!")

    resp = await client.post(LOGIN_URL, json={
        "email": "carol@test.com",
        "password": "WrongPass!",
    })
    assert resp.status_code == 401
    assert "Invalid email or password" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_email(client: AsyncClient):
    """Unknown email → 401 (does not leak whether user exists)."""
    resp = await client.post(LOGIN_URL, json={
        "email": "nobody@example.com",
        "password": "irrelevant",
    })
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 3. GET /api/auth/me
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_me_authenticated(client: AsyncClient, create_test_user):
    """Authenticated /me returns the user profile."""
    await create_test_user(email="dave@test.com", password="Pa$$1234", name="Dave")

    login_resp = await client.post(LOGIN_URL, json={
        "email": "dave@test.com",
        "password": "Pa$$1234",
    })
    token = login_resp.json()["access_token"]

    me_resp = await client.get(ME_URL, headers=_auth_header(token))
    assert me_resp.status_code == 200
    profile = me_resp.json()
    assert profile["name"] == "Dave"
    assert profile["email"] == "dave@test.com"


@pytest.mark.asyncio
async def test_me_no_token(client: AsyncClient):
    """Unauthenticated /me → 401."""
    resp = await client.get(ME_URL)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_invalid_token(client: AsyncClient):
    """Bogus token → 401."""
    resp = await client.get(ME_URL, headers=_auth_header("totally.bogus.token"))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_expired_token(client: AsyncClient, create_test_user, db_session: AsyncSession):
    """Expired JWT → 401."""
    eve = await create_test_user(email="eve@test.com", password="XyZ789!!", name="Eve")

    # Generate a token that expired 1 hour ago
    from datetime import datetime, timezone, timedelta
    from jose import jwt
    from config import get_settings

    settings = get_settings()

    expired_token = jwt.encode(
        {"sub": str(eve.id), "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    resp = await client.get(ME_URL, headers=_auth_header(expired_token))
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 4. POST /api/auth/logout
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_logout_authenticated(client: AsyncClient, create_test_user):
    """Authenticated logout returns 200."""
    await create_test_user(email="frank@test.com", password="Logout1!!", name="Frank")

    login_resp = await client.post(LOGIN_URL, json={
        "email": "frank@test.com",
        "password": "Logout1!!",
    })
    token = login_resp.json()["access_token"]

    resp = await client.post(LOGOUT_URL, headers=_auth_header(token))
    assert resp.status_code == 200
    assert "Logged out" in resp.json()["message"]


@pytest.mark.asyncio
async def test_logout_unauthenticated(client: AsyncClient):
    """Logout without token → 401."""
    resp = await client.post(LOGOUT_URL)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 5. Inactive user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inactive_user_cannot_login(client: AsyncClient, create_test_user):
    """Inactive user → 403."""
    await create_test_user(
        email="inactive@test.com", password="Pass1234!", name="Ghost",
        is_active=False,
    )
    resp = await client.post(LOGIN_URL, json={
        "email": "inactive@test.com",
        "password": "Pass1234!",
    })
    assert resp.status_code == 403
    assert "inactive" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_inactive_user_token_rejected(client: AsyncClient, create_test_user):
    """Token for inactive user → 403 on /me."""
    user = await create_test_user(
        email="zombie@test.com", password="Dead1234!", name="Zombie",
        is_active=False,
    )
    token = f"bearer_{uuid.uuid4()}"  # won't be valid JWT, use real one

    # Login to get a valid token (login will fail for inactive)
    login_resp = await client.post(LOGIN_URL, json={
        "email": "zombie@test.com", "password": "Dead1234!",
    })
    assert login_resp.status_code == 403  # can't even login

    # Manually create a token for the inactive user
    from auth.routes import create_access_token
    real_token = create_access_token(str(user.id))

    me_resp = await client.get(ME_URL, headers=_auth_header(real_token))
    assert me_resp.status_code == 403
    assert "inactive" in me_resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 6. Login returns correct profile shape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_profile_shape(client: AsyncClient, create_test_user):
    """The user object in the login response matches UserProfile shape."""
    await create_test_user(
        email="shape@test.com", password="Shape123!!", name="Shapey",
    )
    resp = await client.post(LOGIN_URL, json={
        "email": "shape@test.com", "password": "Shape123!!",
    })
    user = resp.json()["user"]
    assert set(user.keys()) == {"name", "email", "avatarUrl"}
    assert isinstance(user["name"], str)
    assert isinstance(user["email"], str)
