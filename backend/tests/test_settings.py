"""Tests for the real Settings API.

Covers:
  • GET /api/settings — authenticated, unauthenticated, defaults
  • PATCH /api/settings — authenticated, partial update, invalid field/value
  • Persistence after update
  • User isolation (two users see different settings)
  • Cannot update another user's settings
"""

import uuid

import pytest
from httpx import AsyncClient


LOGIN_URL = "/api/auth/login"
SETTINGS_URL = "/api/settings"


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. GET /api/settings — authenticated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_settings_authenticated(client: AsyncClient, create_test_user):
    """Authenticated GET returns the user's settings (with defaults)."""
    await create_test_user(email="settings1@test.com", password="Pass123!", name="Settings User")
    login_resp = await client.post(LOGIN_URL, json={
        "email": "settings1@test.com", "password": "Pass123!",
    })
    token = login_resp.json()["access_token"]

    resp = await client.get(SETTINGS_URL, headers=_auth_header(token))
    assert resp.status_code == 200
    body = resp.json()
    assert "processingDepth" in body
    assert "contextWindow" in body
    assert "theme" in body
    assert "density" in body
    assert "glassIntensity" in body
    assert isinstance(body["processingDepth"], int)
    assert isinstance(body["glassIntensity"], int)


# ---------------------------------------------------------------------------
# 2. GET /api/settings — unauthenticated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_settings_unauthenticated(client: AsyncClient):
    """Unauthenticated GET returns 401."""
    resp = await client.get(SETTINGS_URL)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 3. GET default settings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_settings_returns_defaults(client: AsyncClient, create_test_user):
    """First access returns sensible defaults."""
    await create_test_user(email="defaults@test.com", password="Pass123!", name="Defaults")
    login_resp = await client.post(LOGIN_URL, json={
        "email": "defaults@test.com", "password": "Pass123!",
    })
    token = login_resp.json()["access_token"]

    resp = await client.get(SETTINGS_URL, headers=_auth_header(token))
    body = resp.json()
    # Check default values match the model defaults
    assert body["processingDepth"] == 3
    assert body["contextWindow"] == "persistent"
    assert body["theme"] == "dark-cyber"
    assert body["density"] == "high"
    assert body["glassIntensity"] == 70


# ---------------------------------------------------------------------------
# 4. PATCH /api/settings — authenticated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_settings_authenticated(client: AsyncClient, create_test_user):
    """Authenticated PATCH updates the specified fields."""
    await create_test_user(email="patch1@test.com", password="Pass123!", name="Patcher")
    login_resp = await client.post(LOGIN_URL, json={
        "email": "patch1@test.com", "password": "Pass123!",
    })
    token = login_resp.json()["access_token"]

    resp = await client.patch(
        SETTINGS_URL,
        json={"processingDepth": 5, "density": "standard"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["processingDepth"] == 5
    assert body["density"] == "standard"
    # Other fields remain unchanged
    assert body["contextWindow"] == "persistent"
    assert body["theme"] == "dark-cyber"


# ---------------------------------------------------------------------------
# 5. PATCH partial update
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_partial_update(client: AsyncClient, create_test_user):
    """Only supplied fields are updated; others remain."""
    await create_test_user(email="partial2@test.com", password="Pass123!", name="Partial")
    login_resp = await client.post(LOGIN_URL, json={
        "email": "partial2@test.com", "password": "Pass123!",
    })
    token = login_resp.json()["access_token"]

    # First update
    await client.patch(SETTINGS_URL, json={"theme": "light"}, headers=_auth_header(token))

    # Second update — only density
    resp = await client.patch(SETTINGS_URL, json={"density": "high"}, headers=_auth_header(token))
    body = resp.json()
    assert body["theme"] == "light"  # preserved from first update
    assert body["density"] == "high"


# ---------------------------------------------------------------------------
# 6. PATCH invalid contextWindow value
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_invalid_context_window(client: AsyncClient, create_test_user):
    """Invalid contextWindow returns 422."""
    await create_test_user(email="invalid2@test.com", password="Pass123!", name="Invalid")
    login_resp = await client.post(LOGIN_URL, json={
        "email": "invalid2@test.com", "password": "Pass123!",
    })
    token = login_resp.json()["access_token"]

    resp = await client.patch(
        SETTINGS_URL,
        json={"contextWindow": "invalid-value"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 7. PATCH invalid theme value
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_invalid_theme(client: AsyncClient, create_test_user):
    """Invalid theme returns 422."""
    await create_test_user(email="invalidtheme2@test.com", password="Pass123!", name="Theme")
    login_resp = await client.post(LOGIN_URL, json={
        "email": "invalidtheme2@test.com", "password": "Pass123!",
    })
    token = login_resp.json()["access_token"]

    resp = await client.patch(
        SETTINGS_URL,
        json={"theme": "neon-pink"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 8. PATCH invalid density value
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_invalid_density(client: AsyncClient, create_test_user):
    """Invalid density returns 422."""
    await create_test_user(email="invdensity2@test.com", password="Pass123!", name="Density")
    login_resp = await client.post(LOGIN_URL, json={
        "email": "invdensity2@test.com", "password": "Pass123!",
    })
    token = login_resp.json()["access_token"]

    resp = await client.patch(
        SETTINGS_URL,
        json={"density": "ultra"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 9. PATCH out-of-range processingDepth
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_out_of_range_depth(client: AsyncClient, create_test_user):
    """processingDepth outside 1–5 returns 422."""
    await create_test_user(email="oor2@test.com", password="Pass123!", name="OOR")
    login_resp = await client.post(LOGIN_URL, json={
        "email": "oor2@test.com", "password": "Pass123!",
    })
    token = login_resp.json()["access_token"]

    resp = await client.patch(
        SETTINGS_URL,
        json={"processingDepth": 10},
        headers=_auth_header(token),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 10. Persistence after update
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_settings_persist_after_update(client: AsyncClient, create_test_user):
    """Settings survive a new request cycle."""
    await create_test_user(email="persist2@test.com", password="Pass123!", name="Persist")
    login_resp = await client.post(LOGIN_URL, json={
        "email": "persist2@test.com", "password": "Pass123!",
    })
    token = login_resp.json()["access_token"]

    # Update
    resp = await client.patch(
        SETTINGS_URL,
        json={"processingDepth": 2, "glassIntensity": 30},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200

    # Re-read in a new request
    resp2 = await client.get(SETTINGS_URL, headers=_auth_header(token))
    body = resp2.json()
    assert body["processingDepth"] == 2
    assert body["glassIntensity"] == 30


# ---------------------------------------------------------------------------
# 11. User isolation — two users see different settings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_isolation(client: AsyncClient, create_test_user):
    """User A settings are never returned to User B."""
    # User A
    await create_test_user(email="iso_a2@test.com", password="Pass123!", name="User A")
    login_a = await client.post(LOGIN_URL, json={
        "email": "iso_a2@test.com", "password": "Pass123!",
    })
    token_a = login_a.json()["access_token"]

    # User B
    await create_test_user(email="iso_b2@test.com", password="Pass123!", name="User B")
    login_b = await client.post(LOGIN_URL, json={
        "email": "iso_b2@test.com", "password": "Pass123!",
    })
    token_b = login_b.json()["access_token"]

    # User A sets depth=1, theme=light
    await client.patch(
        SETTINGS_URL,
        json={"processingDepth": 1, "theme": "light"},
        headers=_auth_header(token_a),
    )

    # User A reads — should see their settings
    resp_a = await client.get(SETTINGS_URL, headers=_auth_header(token_a))
    body_a = resp_a.json()
    assert body_a["processingDepth"] == 1
    assert body_a["theme"] == "light"

    # User B reads — should see defaults, NOT User A's settings
    resp_b = await client.get(SETTINGS_URL, headers=_auth_header(token_b))
    body_b = resp_b.json()
    assert body_b["processingDepth"] == 3  # default
    assert body_b["theme"] == "dark-cyber"  # default


# ---------------------------------------------------------------------------
# 12. Cannot update another user's settings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cannot_update_other_user(client: AsyncClient, create_test_user):
    """PATCH only affects the authenticated user."""
    await create_test_user(email="other1b@test.com", password="Pass123!", name="Other1")
    await create_test_user(email="other2b@test.com", password="Pass123!", name="Other2")

    login1 = await client.post(LOGIN_URL, json={
        "email": "other1b@test.com", "password": "Pass123!",
    })
    login2 = await client.post(LOGIN_URL, json={
        "email": "other2b@test.com", "password": "Pass123!",
    })
    token1 = login1.json()["access_token"]
    token2 = login2.json()["access_token"]

    # User 1 updates
    await client.patch(SETTINGS_URL, json={"processingDepth": 1}, headers=_auth_header(token1))

    # User 2 reads — should NOT see User 1's value
    resp = await client.get(SETTINGS_URL, headers=_auth_header(token2))
    body = resp.json()
    assert body["processingDepth"] == 3  # default, not User 1's value
