"""Malformed-id hardening tests for the document mutation endpoints.

Covers the remaining half of the document API audit's G2 finding, after
``GET /api/documents/{document_id}`` was hardened:

    DELETE /api/documents/{document_id}
    POST   /api/documents/{document_id}/reprocess

Both used to take ``document_id: str`` and compare it against a
``postgresql.UUID(as_uuid=True)`` column, so a malformed id reached PostgreSQL
and surfaced as a 500/DataError (invisible under the SQLite test harness, which
maps UUID to String).  They now take ``uuid.UUID``, so FastAPI rejects a bad id
with a 422 before any database bind happens.

These tests assert the *response* contract.  On SQLite a malformed id would
never have raised a driver error anyway, so the real guarantee under test is
that validation happens in the framework layer: a 422 (never a 500) with a
body free of database/driver detail.
"""

import uuid

import pytest
from httpx import AsyncClient


LOGIN_URL = "/api/auth/login"
UPLOAD_URL = "/api/documents/upload"

# Genuinely malformed: rejected by Pydantic before any DB bind -> 422.
BAD_IDS = [
    "not-a-uuid",
    "12345",
    "'; DROP TABLE documents; --",
    "9f8a7b6c-5d4e-4f3a-8b2c-1d0e9f8a7b6",  # 35 chars
    "not-a-uuid-but-long-enough-to-look-plausible",
    "9f8a7b6c-5d4e-4f3a-8b2c-1d0e9f8a7bzz",  # non-hex chars
]

# Pydantic's lax UUID parser accepts a bare 32-char hex string, so this is a
# *valid* (if unusual) UUID rather than a malformed one -- it must 404, not 422.
UNDASHED_HEX_UUID = "9f8a7b6c5d4e4f3a8b2c1d0e9f8a7b6c"

# Substrings that would indicate an internal failure reaching the client.
# Pydantic's own "input should be a valid uuid" is a client-facing validation
# message and is expected; database/driver/storage internals are not.
_LEAK_MARKERS = (
    "psycopg",
    "asyncpg",
    "sqlalchemy",
    "postgresql",
    "invalid input syntax",
    "dataerror",
    "traceback",
    "select document",
    "stored_path",
    "traceback (most recent call last)",
)


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client: AsyncClient, email: str) -> str:
    resp = await client.post(
        LOGIN_URL, json={"email": email, "password": "Pass123!"}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _register_and_login(client: AsyncClient, create_test_user, tag: str) -> str:
    email = f"mut-{tag}-{uuid.uuid4().hex[:8]}@test.com"
    await create_test_user(email=email, password="Pass123!")
    return await _login(client, email)


async def _upload_txt(client: AsyncClient, token: str) -> str:
    """Upload a real TXT so the document has a stored file on disk."""
    content = f"mutation endpoint test payload {uuid.uuid4().hex}".encode()
    resp = await client.post(
        UPLOAD_URL,
        files={"file": ("mut.txt", content, "text/plain")},
        headers=_auth_header(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _assert_no_internal_leak(resp) -> None:
    text = resp.text.lower()
    for marker in _LEAK_MARKERS:
        assert marker not in text, f"internal detail leaked: {resp.text}"


# ===========================================================================
# 1. Malformed UUID -> 422, never 500
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_id", BAD_IDS)
async def test_delete_malformed_document_id_returns_422(
    client: AsyncClient, create_test_user, bad_id
):
    token = await _register_and_login(client, create_test_user, "del")
    resp = await client.delete(
        f"/api/documents/{bad_id}", headers=_auth_header(token)
    )
    assert resp.status_code == 422, f"{bad_id} -> {resp.status_code}: {resp.text}"
    assert resp.status_code != 500
    _assert_no_internal_leak(resp)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_id", BAD_IDS)
async def test_reprocess_malformed_document_id_returns_422(
    client: AsyncClient, create_test_user, bad_id
):
    token = await _register_and_login(client, create_test_user, "rep")
    resp = await client.post(
        f"/api/documents/{bad_id}/reprocess", headers=_auth_header(token)
    )
    assert resp.status_code == 422, f"{bad_id} -> {resp.status_code}: {resp.text}"
    assert resp.status_code != 500
    _assert_no_internal_leak(resp)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_id", [UNDASHED_HEX_UUID, "../../etc/passwd", "a/b"])
async def test_non_uuid_shaped_paths_still_return_clean_4xx(
    client: AsyncClient, create_test_user, bad_id
):
    """Undashed hex (valid to Pydantic) and non-route-matching paths must still
    produce a clean 4xx rather than a 500."""
    token = await _register_and_login(client, create_test_user, "shape")
    resp = await client.delete(
        f"/api/documents/{bad_id}", headers=_auth_header(token)
    )
    assert 400 <= resp.status_code < 500, f"{bad_id} -> {resp.status_code}: {resp.text}"
    assert resp.status_code != 500
    _assert_no_internal_leak(resp)

    resp = await client.post(
        f"/api/documents/{bad_id}/reprocess", headers=_auth_header(token)
    )
    assert 400 <= resp.status_code < 500, f"{bad_id} -> {resp.status_code}: {resp.text}"
    assert resp.status_code != 500
    _assert_no_internal_leak(resp)


@pytest.mark.asyncio
async def test_malformed_id_validation_body_is_structural(
    client: AsyncClient, create_test_user
):
    """The 422 body is FastAPI's normal validation envelope, with no internals."""
    token = await _register_and_login(client, create_test_user, "body")
    resp = await client.delete(
        "/api/documents/definitely-not-a-uuid", headers=_auth_header(token)
    )
    assert resp.status_code == 422
    body = resp.json()
    assert "detail" in body
    entries = body["detail"]
    assert isinstance(entries, list) and entries
    loc = entries[0]["loc"]
    assert "document_id" in loc
    _assert_no_internal_leak(resp)


# ===========================================================================
# 2. Valid UUID -> behavior unchanged
# ===========================================================================


@pytest.mark.asyncio
async def test_delete_valid_unknown_uuid_returns_404(
    client: AsyncClient, create_test_user
):
    token = await _register_and_login(client, create_test_user, "unk-del")
    resp = await client.delete(
        f"/api/documents/{uuid.uuid4()}", headers=_auth_header(token)
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Document not found"


@pytest.mark.asyncio
async def test_reprocess_valid_unknown_uuid_returns_404(
    client: AsyncClient, create_test_user
):
    token = await _register_and_login(client, create_test_user, "unk-rep")
    resp = await client.post(
        f"/api/documents/{uuid.uuid4()}/reprocess", headers=_auth_header(token)
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Document not found"


@pytest.mark.asyncio
async def test_delete_valid_document_still_succeeds(
    client: AsyncClient, create_test_user
):
    token = await _register_and_login(client, create_test_user, "ok-del")
    doc_id = await _upload_txt(client, token)

    resp = await client.delete(f"/api/documents/{doc_id}", headers=_auth_header(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["message"] == "Document deleted successfully"

    # The document is really gone for its owner.
    gone = await client.get(f"/api/documents/{doc_id}", headers=_auth_header(token))
    assert gone.status_code == 404


@pytest.mark.asyncio
async def test_reprocess_valid_document_response_contract_unchanged(
    client: AsyncClient, create_test_user
):
    token = await _register_and_login(client, create_test_user, "ok-rep")
    doc_id = await _upload_txt(client, token)

    resp = await client.post(
        f"/api/documents/{doc_id}/reprocess", headers=_auth_header(token)
    )
    # A freshly uploaded TXT is READY and its file exists on disk, so reprocess
    # re-runs the pipeline and returns the DocumentOut contract.
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == doc_id
    assert body["fileType"] == "txt"
    assert set(body) == {
        "id",
        "name",
        "fileType",
        "fileSize",
        "chunkCount",
        "status",
        "embeddingStatus",
        "createdAt",
    }
    assert body["status"] in ("ready", "processing", "error")


@pytest.mark.asyncio
async def test_reprocess_missing_source_file_still_409(
    client: AsyncClient, db_session, create_test_user
):
    """The pre-existing 409 for a missing stored file is preserved (no leak)."""
    from tests.fixtures.graph_data import create_document_with_chunks

    user_email = f"mut-nofile-{uuid.uuid4().hex[:8]}@test.com"
    user = await create_test_user(email=user_email, password="Pass123!")
    doc, _rows = await create_document_with_chunks(
        db_session,
        user.id,
        name="absent.pdf",
        chunks=[{"content": "x"}],
    )
    await db_session.commit()
    token = await _login(client, user_email)

    resp = await client.post(
        f"/api/documents/{doc.id}/reprocess", headers=_auth_header(token)
    )
    assert resp.status_code == 409
    assert "no longer exists" in resp.json()["detail"].lower()
    _assert_no_internal_leak(resp)


# ===========================================================================
# 3. Authentication unchanged
# ===========================================================================


@pytest.mark.asyncio
async def test_delete_unauthenticated_rejected(client: AsyncClient, create_test_user):
    token = await _register_and_login(client, create_test_user, "unauth-del")
    doc_id = await _upload_txt(client, token)

    resp = await client.delete(f"/api/documents/{doc_id}")
    assert resp.status_code == 401

    # And the document survived the rejected request.
    still_there = await client.get(
        f"/api/documents/{doc_id}", headers=_auth_header(token)
    )
    assert still_there.status_code == 200


@pytest.mark.asyncio
async def test_reprocess_unauthenticated_rejected(
    client: AsyncClient, create_test_user
):
    token = await _register_and_login(client, create_test_user, "unauth-rep")
    doc_id = await _upload_txt(client, token)

    resp = await client.post(f"/api/documents/{doc_id}/reprocess")
    assert resp.status_code == 401


# ===========================================================================
# 4. Ownership isolation unchanged
# ===========================================================================


@pytest.mark.asyncio
async def test_cross_user_delete_returns_404_and_does_not_delete(
    client: AsyncClient, create_test_user
):
    owner_token = await _register_and_login(client, create_test_user, "own-del-a")
    other_token = await _register_and_login(client, create_test_user, "own-del-b")
    doc_id = await _upload_txt(client, owner_token)

    resp = await client.delete(
        f"/api/documents/{doc_id}", headers=_auth_header(other_token)
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Document not found"

    # The owner's document must be untouched by the rejected delete.
    still_there = await client.get(
        f"/api/documents/{doc_id}", headers=_auth_header(owner_token)
    )
    assert still_there.status_code == 200


@pytest.mark.asyncio
async def test_cross_user_reprocess_returns_404(
    client: AsyncClient, create_test_user
):
    owner_token = await _register_and_login(client, create_test_user, "own-rep-a")
    other_token = await _register_and_login(client, create_test_user, "own-rep-b")
    doc_id = await _upload_txt(client, owner_token)

    resp = await client.post(
        f"/api/documents/{doc_id}/reprocess", headers=_auth_header(other_token)
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Document not found"


@pytest.mark.asyncio
async def test_cross_user_malformed_id_does_not_reveal_ownership(
    client: AsyncClient, create_test_user
):
    """Malformed ids are rejected by validation regardless of the caller."""
    other_token = await _register_and_login(client, create_test_user, "own-mal")
    resp = await client.delete(
        "/api/documents/not-a-uuid", headers=_auth_header(other_token)
    )
    assert resp.status_code == 422
