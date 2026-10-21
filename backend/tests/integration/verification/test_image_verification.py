"""Integration tests for the implemented image Media Verification contract.

Covers the real endpoint (POST /api/verification/analyze):

* the successful path runs the *actual* provisioned local model (no mock)
* the response conforms exactly to the documented contract
* input-validation failures map to honest HTTP statuses
* the endpoint persists no media
* model-unavailable / inference-failure / timeout paths return generic errors
  that never leak internal paths or exception detail
"""

import asyncio
import io
import json
import math
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from PIL import Image

from tests.fixtures.paths import BACKEND_DIR
from verification.service import (
    InferenceError,
    ModelUnavailableError,
)

# ---------------------------------------------------------------------------
# Provisioned model metadata (must match the artifact actually on disk)
# ---------------------------------------------------------------------------

_MODEL_DIR = BACKEND_DIR / "models" / "media-verification"
_MANIFEST = json.loads((_MODEL_DIR / "MANIFEST.json").read_text(encoding="utf-8"))
_MODEL_LABELS = set(_MANIFEST["labels"].values())
_UPLOADS_DIR = BACKEND_DIR / "uploads"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tiny_image(fmt: str = "PNG", size=(64, 48)) -> bytes:
    """Deterministic tiny RGB image generated in memory (no committed files)."""
    buf = io.BytesIO()
    Image.new("RGB", size, (120, 30, 200)).save(buf, format=fmt)
    return buf.getvalue()


async def _auth_headers(
    client: AsyncClient, create_test_user, email: str
) -> dict[str, str]:
    await create_test_user(email=email, password="Pass123!", name="ImgVerify")
    login = await client.post(
        "/api/auth/login", json={"email": email, "password": "Pass123!"}
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Successful path — real local model, no mocking
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fmt,filename,mime",
    [("PNG", "sample.png", "image/png"), ("JPEG", "sample.jpg", "image/jpeg")],
)
async def test_valid_image_returns_model_derived_result(
    client: AsyncClient, create_test_user, fmt, filename, mime
):
    headers = await _auth_headers(client, create_test_user, f"valid_{fmt.lower()}@test.com")
    data = _tiny_image(fmt)

    resp = await client.post(
        "/api/verification/analyze",
        headers=headers,
        files={"file": (filename, data, mime)},
    )
    assert resp.status_code == 200, resp.text

    body = resp.json()

    # --- exact contract shape ---
    assert set(body.keys()) == {"available", "verdict", "score", "model", "processing"}
    assert set(body["model"].keys()) == {"name", "version"}
    assert set(body["processing"].keys()) == {"bytes", "width", "height", "elapsedMs"}

    # --- real, model-derived values ---
    assert body["available"] is True
    assert body["verdict"] in _MODEL_LABELS, (
        f"{body['verdict']!r} is not one of the provisioned model labels {_MODEL_LABELS}"
    )

    score = body["score"]
    assert isinstance(score, (int, float))
    assert math.isfinite(score)
    assert 0.0 <= score <= 1.0

    assert body["model"]["name"] == _MANIFEST["model_name"]
    assert body["model"]["version"] == _MANIFEST["revision"]

    proc = body["processing"]
    assert proc["bytes"] == len(data)
    assert proc["width"] == 64
    assert proc["height"] == 48
    assert isinstance(proc["elapsedMs"], int) and proc["elapsedMs"] >= 0

    # --- the response must not leak internals or invent metrics ---
    for forbidden in (
        "models/media-verification",
        "stored_path",
        "Traceback",
        "risk",
        "confidence",
        "manipulation",
        "authenticity",
    ):
        assert forbidden not in resp.text


@pytest.mark.asyncio
async def test_valid_image_persists_no_media(client: AsyncClient, create_test_user):
    headers = await _auth_headers(client, create_test_user, "nopersist@test.com")
    before = {str(p) for p in _UPLOADS_DIR.rglob("*")} if _UPLOADS_DIR.exists() else set()

    resp = await client.post(
        "/api/verification/analyze",
        headers=headers,
        files={"file": ("nopersist.png", _tiny_image("PNG"), "image/png")},
    )
    assert resp.status_code == 200, resp.text

    after = {str(p) for p in _UPLOADS_DIR.rglob("*")} if _UPLOADS_DIR.exists() else set()
    assert after == before, "media verification must not persist uploaded media"


# ---------------------------------------------------------------------------
# Input validation — success path not reached
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_returns_401(client: AsyncClient):
    resp = await client.post(
        "/api/verification/analyze",
        files={"file": ("x.png", _tiny_image(), "image/png")},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unsupported_extension_returns_415(client: AsyncClient, create_test_user):
    headers = await _auth_headers(client, create_test_user, "ext415@test.com")
    resp = await client.post(
        "/api/verification/analyze",
        headers=headers,
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 415
    assert "Unsupported file type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_unsupported_mime_returns_415(client: AsyncClient, create_test_user):
    headers = await _auth_headers(client, create_test_user, "mime415@test.com")
    resp = await client.post(
        "/api/verification/analyze",
        headers=headers,
        files={"file": ("notes.png", _tiny_image(), "text/plain")},
    )
    assert resp.status_code == 415
    assert resp.json()["detail"] == "Unsupported media type"


@pytest.mark.asyncio
async def test_non_image_content_returns_400(client: AsyncClient, create_test_user):
    headers = await _auth_headers(client, create_test_user, "badcontent@test.com")
    resp = await client.post(
        "/api/verification/analyze",
        headers=headers,
        files={"file": ("fake.png", b"this is not an image", "image/png")},
    )
    assert resp.status_code == 400
    assert "not a valid supported image" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_malformed_image_returns_400(client: AsyncClient, create_test_user):
    headers = await _auth_headers(client, create_test_user, "malformed@test.com")
    # Correct PNG magic bytes but an undecodable body.
    malformed = b"\x89PNG\r\n\x1a\n" + b"this is not real png data"
    resp = await client.post(
        "/api/verification/analyze",
        headers=headers,
        files={"file": ("broken.png", malformed, "image/png")},
    )
    assert resp.status_code == 400
    assert "not a valid image" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_mime_content_mismatch_returns_400(client: AsyncClient, create_test_user):
    headers = await _auth_headers(client, create_test_user, "mismatch@test.com")
    resp = await client.post(
        "/api/verification/analyze",
        headers=headers,
        files={"file": ("really_png.png", _tiny_image("PNG"), "image/gif")},
    )
    assert resp.status_code == 400
    assert "does not match its declared type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_oversized_upload_returns_413(client: AsyncClient, create_test_user):
    headers = await _auth_headers(client, create_test_user, "oversize@test.com")
    import verification.routes as routes

    # Shrink the configured limit so the 413 branch is exercised without
    # allocating a 50 MB payload.
    with patch.object(routes.settings, "max_upload_size_mb", 0):
        resp = await client.post(
            "/api/verification/analyze",
            headers=headers,
            files={"file": ("big.png", _tiny_image("PNG"), "image/png")},
        )
    assert resp.status_code == 413
    assert "exceeds maximum size" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Failure paths — mocks used only here
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_model_unavailable_returns_503_without_internal_details(
    client: AsyncClient, create_test_user
):
    headers = await _auth_headers(client, create_test_user, "unavailable@test.com")
    leak = r"C:\internal\models\media-verification secret"

    with patch(
        "verification.routes.analyze_image_bytes",
        new=AsyncMock(side_effect=ModelUnavailableError(leak)),
    ):
        resp = await client.post(
            "/api/verification/analyze",
            headers=headers,
            files={"file": ("x.png", _tiny_image(), "image/png")},
        )

    assert resp.status_code == 503
    assert resp.json()["detail"] == "Media verification model is unavailable"
    assert "internal" not in resp.text
    assert "secret" not in resp.text
    assert "media-verification" not in resp.text


@pytest.mark.asyncio
async def test_inference_failure_returns_generic_500(client: AsyncClient, create_test_user):
    headers = await _auth_headers(client, create_test_user, "inferfail@test.com")
    leak = "RuntimeError: boom at C:\\internal\\secret.py"

    with patch(
        "verification.routes.analyze_image_bytes",
        new=AsyncMock(side_effect=RuntimeError(leak)),
    ):
        resp = await client.post(
            "/api/verification/analyze",
            headers=headers,
            files={"file": ("x.png", _tiny_image(), "image/png")},
        )

    assert resp.status_code == 500
    assert resp.json()["detail"] == "Media verification failed"
    assert "RuntimeError" not in resp.text
    assert "internal" not in resp.text
    assert "secret.py" not in resp.text


@pytest.mark.asyncio
async def test_inference_error_returns_generic_500(client: AsyncClient, create_test_user):
    headers = await _auth_headers(client, create_test_user, "infererror@test.com")

    with patch(
        "verification.routes.analyze_image_bytes",
        new=AsyncMock(side_effect=InferenceError("label mapping failure at /srv/x")),
    ):
        resp = await client.post(
            "/api/verification/analyze",
            headers=headers,
            files={"file": ("x.png", _tiny_image(), "image/png")},
        )

    assert resp.status_code == 500
    assert resp.json()["detail"] == "Media verification failed"
    assert "/srv/x" not in resp.text


@pytest.mark.asyncio
async def test_inference_timeout_returns_504(client: AsyncClient, create_test_user):
    headers = await _auth_headers(client, create_test_user, "timeout@test.com")

    with patch(
        "verification.routes.analyze_image_bytes",
        new=AsyncMock(side_effect=asyncio.TimeoutError()),
    ):
        resp = await client.post(
            "/api/verification/analyze",
            headers=headers,
            files={"file": ("x.png", _tiny_image(), "image/png")},
        )

    assert resp.status_code == 504
    assert resp.json()["detail"] == "Media verification timed out"
