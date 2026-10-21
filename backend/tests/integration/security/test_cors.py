"""Regression tests for CORS configuration and preflight handling.

Covers the local login blocker where the browser reached the Vite dev server
through ``127.0.0.1`` (or the preview server on port 4173) while the backend
only allowlisted ``http://localhost:3000``.  CORS preflight succeeds only for
an exact ``Origin`` match, so ``OPTIONS /api/auth/login`` returned
``400 Disallowed CORS origin`` and the browser never sent the POST.
"""

import pytest
from httpx import AsyncClient

from config import Settings, get_settings

PREFLIGHT_HEADERS = {
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "content-type,authorization",
}


class TestCorsOriginDefaults:
    """The configured allowlist must cover the local dev + preview origins."""

    def test_defaults_include_dev_and_preview_loopback_origins(self):
        # _env_file=None ignores the local .env so the class default is tested.
        origins = set(Settings(_env_file=None).cors_origin_list)
        for origin in (
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ):
            assert origin in origins

    def test_loopback_counterpart_is_added(self):
        origins = Settings(cors_origins="http://localhost:3000").cors_origin_list
        assert "http://localhost:3000" in origins
        assert "http://127.0.0.1:3000" in origins

    def test_non_loopback_origin_is_not_expanded(self):
        origins = Settings(cors_origins="https://documind.vercel.app").cors_origin_list
        assert origins == ["https://documind.vercel.app"]

    def test_trailing_slash_and_duplicates_are_normalised(self):
        origins = Settings(
            cors_origins=" http://localhost:3000/ , http://localhost:3000 "
        ).cors_origin_list
        assert origins.count("http://localhost:3000") == 1
        assert "http://localhost:3000/" not in origins

    def test_partial_loopback_allowlist_fills_local_dev_set(self):
        # Mirrors the stale `.env` value that omitted the preview server: a
        # partial loopback allowlist must still permit the local Vite origins.
        origins = Settings(
            cors_origins="http://localhost:3000,http://localhost:5173"
        ).cors_origin_list
        for origin in (
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ):
            assert origin in origins

    def test_production_allowlist_adds_no_loopback_origin(self):
        origins = Settings(
            cors_origins="https://documind.vercel.app,https://www.documind.app"
        ).cors_origin_list
        assert origins == ["https://documind.vercel.app", "https://www.documind.app"]
        assert not any("localhost" in o or "127.0.0.1" in o for o in origins)


class TestCorsPreflight:
    """The wired-up middleware must answer preflight correctly."""

    @pytest.mark.asyncio
    async def test_preflight_allowed_origin_succeeds(self, client: AsyncClient):
        origin = get_settings().cors_origin_list[0]
        resp = await client.options(
            "/api/auth/login", headers={"Origin": origin, **PREFLIGHT_HEADERS}
        )
        assert resp.status_code == 200
        assert resp.headers["access-control-allow-origin"] == origin
        assert resp.headers.get("access-control-allow-credentials") == "true"
        assert "authorization" in resp.headers["access-control-allow-headers"].lower()

    @pytest.mark.asyncio
    async def test_preflight_disallowed_origin_rejected(self, client: AsyncClient):
        resp = await client.options(
            "/api/auth/login",
            headers={"Origin": "https://evil.example", **PREFLIGHT_HEADERS},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_loopback_origins_in_allowlist_pass(self, client: AsyncClient):
        allowed = set(get_settings().cors_origin_list)
        for origin in (
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ):
            assert origin in allowed, origin
            resp = await client.options(
                "/api/auth/login", headers={"Origin": origin, **PREFLIGHT_HEADERS}
            )
            assert resp.status_code == 200, origin
