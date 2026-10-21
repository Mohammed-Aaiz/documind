"""Regression tests for the removal of the obsolete `/api/user/*` contract.

`backend/user/routes.py` used to declare four routes — `GET/PUT /api/user/profile`
and `GET/PUT /api/user/preferences` — that took no authentication dependency and
raised an unhandled ``NotImplementedError``.  Both halves of their intended
responsibility were already served elsewhere: identity by ``GET /api/auth/me``
(``auth.schemas.UserProfile`` = ``{name, email, avatarUrl}``) and persisted
settings by ``GET/PATCH /api/settings``.  No frontend or backend caller existed.

The module and its router registration were removed, so these tests pin the
resulting contract against the application's REAL routing setup (the ``app``
fixture imports the real ``main.app``):

  • no ``/api/user*`` route is registered at all
  • the four paths answer 404, authenticated or not — not 500, not a stale stub
  • the replacement endpoints are still authenticated and still correct
    (an unauthenticated request to either replacement still 401s)
"""

import pytest
from httpx import AsyncClient

from auth.schemas import UserProfile

LOGIN_URL = "/api/auth/login"
ME_URL = "/api/auth/me"
SETTINGS_URL = "/api/settings"

REMOVED_PATHS = ("/api/user/profile", "/api/user/preferences")
METHODS = ("get", "put")

PASSWORD = "Pass123!"


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _case_email(method: str, path: str) -> str:
    """A distinct account per case: the test database persists rows."""
    return f"removed-{method}-{path.strip('/').replace('/', '-')}@test.com"


async def _create_and_login(
    client: AsyncClient, create_test_user, *, email: str, name: str
) -> str:
    await create_test_user(email=email, password=PASSWORD, name=name)
    login_resp = await client.post(
        LOGIN_URL, json={"email": email, "password": PASSWORD}
    )
    assert login_resp.status_code == 200
    return login_resp.json()["access_token"]


# ---------------------------------------------------------------------------
# 1. The obsolete contract is no longer registered
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_user_router_remains_registered(app):
    """The real application mounts no route under /api/user."""
    mounted = [getattr(route, "path", "") for route in app.routes]
    assert [path for path in mounted if path.startswith("/api/user")] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("path", REMOVED_PATHS)
async def test_removed_paths_return_404_when_unauthenticated(
    client: AsyncClient, path: str, method: str
):
    """The paths no longer exist for anonymous callers (they used to 500/401)."""
    resp = await getattr(client, method)(path)
    assert resp.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("path", REMOVED_PATHS)
async def test_removed_paths_return_404_when_authenticated(
    client: AsyncClient, create_test_user, path: str, method: str
):
    """A valid token does not resurrect them either."""
    token = await _create_and_login(
        client,
        create_test_user,
        email=_case_email(method, path),
        name="Removed Route User",
    )
    resp = await getattr(client, method)(path, headers=_auth_header(token))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 2. The replacement endpoint for identity — still protected, still correct
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auth_me_is_still_protected(client: AsyncClient):
    """GET /api/auth/me without a token is still 401."""
    resp = await client.get(ME_URL)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_returns_the_authenticated_users_identity(
    client: AsyncClient, create_test_user
):
    """GET /api/auth/me covers the identity the removed profile route returned."""
    token = await _create_and_login(
        client, create_test_user, email="me-replacement@test.com", name="Me User"
    )

    resp = await client.get(ME_URL, headers=_auth_header(token))
    assert resp.status_code == 200
    body = resp.json()

    # The same three fields the removed ProfileResponse exposed.
    assert set(body) == set(UserProfile.model_fields) == {"name", "email", "avatarUrl"}
    assert body["email"] == "me-replacement@test.com"
    assert body["name"] == "Me User"
    assert body["avatarUrl"] is None


# ---------------------------------------------------------------------------
# 3. The replacement endpoint for settings — still protected, still persisting
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_settings_get_and_patch_without_a_token_are_rejected(
    client: AsyncClient,
):
    """GET/PATCH /api/settings remain authenticated-only."""
    assert (await client.get(SETTINGS_URL)).status_code == 401
    assert (
        await client.patch(SETTINGS_URL, json={"theme": "light"})
    ).status_code == 401


@pytest.mark.asyncio
async def test_settings_still_supports_its_authenticated_contract(
    client: AsyncClient, create_test_user
):
    """PATCH persists, and a later GET returns the stored value."""
    token = await _create_and_login(
        client,
        create_test_user,
        email="settings-unchanged@test.com",
        name="Settings User",
    )
    headers = _auth_header(token)

    initial = await client.get(SETTINGS_URL, headers=headers)
    assert initial.status_code == 200
    for field in (
        "processingDepth",
        "contextWindow",
        "theme",
        "density",
        "glassIntensity",
    ):
        assert field in initial.json()

    patched = await client.patch(
        SETTINGS_URL, headers=headers, json={"theme": "light"}
    )
    assert patched.status_code == 200
    assert patched.json()["theme"] == "light"

    reread = await client.get(SETTINGS_URL, headers=headers)
    assert reread.status_code == 200
    assert reread.json()["theme"] == "light"
