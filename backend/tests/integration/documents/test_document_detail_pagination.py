"""Tests for GET /api/documents/{document_id} hardening.

Covers the two defects from the document API audit:

1. A malformed ``document_id`` used to reach PostgreSQL and surface as a 500.
2. The endpoint used to return *every* chunk with full content, unbounded.

The contract under test is
``GET /api/documents/{document_id}?limit=<n>&offset=<n>`` with a DB-level
``LIMIT``/``OFFSET`` ordered by ``chunk_index``.
"""

import uuid

import pytest
from httpx import AsyncClient

from documents.routes import DEFAULT_CHUNK_LIMIT, MAX_CHUNK_LIMIT
from tests.fixtures.graph_data import create_document_with_chunks


LOGIN_URL = "/api/auth/login"

# More chunks than DEFAULT_CHUNK_LIMIT so the default bound is observable,
# while each row stays tiny.
CHUNK_COUNT = DEFAULT_CHUNK_LIMIT + 10


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client: AsyncClient, email: str) -> str:
    resp = await client.post(
        LOGIN_URL, json={"email": email, "password": "Pass123!"}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
async def seeded(client: AsyncClient, db_session, create_test_user):
    """Owner with a many-chunk document, plus a second unrelated user.

    E-mail addresses are unique per test: the shared SQLite database is not
    truncated between tests, so a fixed address would violate the UNIQUE
    constraint on the second test onwards.
    """
    tag = uuid.uuid4().hex[:10]
    owner_email = f"detail-owner-{tag}@test.com"
    other_email = f"detail-other-{tag}@test.com"

    owner = await create_test_user(email=owner_email, password="Pass123!")
    await create_test_user(email=other_email, password="Pass123!")

    doc, _rows = await create_document_with_chunks(
        db_session,
        owner.id,
        name="pagination-doc.pdf",
        chunks=[
            {"content": f"chunk-number-{i:03d}", "page": i + 1}
            for i in range(CHUNK_COUNT)
        ],
    )
    await db_session.commit()

    return {
        "token": await _login(client, owner_email),
        "other_token": await _login(client, other_email),
        "doc_id": str(doc.id),
    }


# ---------------------------------------------------------------------------
# 1. Happy path — metadata preserved
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detail_returns_document_with_default_window(
    client: AsyncClient, seeded
):
    resp = await client.get(
        f"/api/documents/{seeded['doc_id']}", headers=_auth_header(seeded["token"])
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Document metadata is unchanged from the pre-hardening contract.
    assert body["id"] == seeded["doc_id"]
    assert body["name"] == "pagination-doc.pdf"
    assert body["fileType"] == "pdf"
    assert body["fileSize"] == 1024
    assert body["chunkCount"] == CHUNK_COUNT
    assert body["status"] == "ready"
    assert body["embeddingStatus"] == "ready"
    assert body["createdAt"]

    # Default window is bounded, not "everything".
    assert body["limit"] == DEFAULT_CHUNK_LIMIT
    assert body["offset"] == 0
    assert len(body["chunks"]) == DEFAULT_CHUNK_LIMIT


@pytest.mark.asyncio
async def test_detail_default_page_has_no_chunk_outside_window(
    client: AsyncClient, seeded
):
    """The default window must not leak chunks beyond the limit."""
    resp = await client.get(
        f"/api/documents/{seeded['doc_id']}", headers=_auth_header(seeded["token"])
    )
    body = resp.json()
    assert [c["chunkIndex"] for c in body["chunks"]] == list(
        range(DEFAULT_CHUNK_LIMIT)
    )


@pytest.mark.asyncio
async def test_total_is_full_chunk_count_not_page_size(
    client: AsyncClient, seeded
):
    resp = await client.get(
        f"/api/documents/{seeded['doc_id']}", headers=_auth_header(seeded["token"])
    )
    body = resp.json()
    assert body["total"] == CHUNK_COUNT
    assert body["total"] > body["limit"] > 0


# ---------------------------------------------------------------------------
# 2. UUID validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_id",
    [
        "not-a-uuid",
        "12345",
        "'; DROP TABLE documents; --",
        "9f8a7b6c-5d4e-4f3a-8b2c-1d0e9f8a7b6",  # 35 chars
        "9f8a7b6c5d4e4f3a8b2c1d0e9f8a7b6c",  # missing dashes
    ],
)
async def test_malformed_document_id_returns_4xx_not_500(
    client: AsyncClient, seeded, bad_id
):
    resp = await client.get(
        f"/api/documents/{bad_id}", headers=_auth_header(seeded["token"])
    )
    assert 400 <= resp.status_code < 500, resp.text
    assert resp.status_code != 500
    # No database/driver internals may leak.  Pydantic's own
    # "input should be a valid uuid" is a client-facing validation message
    # and is expected; PostgreSQL/driver strings are not.
    text = resp.text.lower()
    for leak in (
        "psycopg",
        "asyncpg",
        "sqlalchemy",
        "postgresql",
        "invalid input syntax",
        "dataerror",
        "traceback",
        "select document",
    ):
        assert leak not in text, f"internal detail leaked: {resp.text}"


@pytest.mark.asyncio
async def test_valid_uuid_unknown_document_returns_404(
    client: AsyncClient, seeded
):
    resp = await client.get(
        f"/api/documents/{uuid.uuid4()}", headers=_auth_header(seeded["token"])
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Document not found"


@pytest.mark.asyncio
async def test_detail_unauthenticated_rejected(client: AsyncClient, seeded):
    resp = await client.get(f"/api/documents/{seeded['doc_id']}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 3. Pagination parameters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_custom_limit_returns_exact_window(client: AsyncClient, seeded):
    resp = await client.get(
        f"/api/documents/{seeded['doc_id']}?limit=5",
        headers=_auth_header(seeded["token"]),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["limit"] == 5
    assert body["offset"] == 0
    assert body["total"] == CHUNK_COUNT
    assert [c["chunkIndex"] for c in body["chunks"]] == [0, 1, 2, 3, 4]
    assert body["chunks"][0]["content"] == "chunk-number-000"
    assert body["chunks"][0]["page"] == 1


@pytest.mark.asyncio
async def test_custom_offset_skips_earlier_chunks(client: AsyncClient, seeded):
    resp = await client.get(
        f"/api/documents/{seeded['doc_id']}?limit=3&offset=10",
        headers=_auth_header(seeded["token"]),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["limit"] == 3
    assert body["offset"] == 10
    assert body["total"] == CHUNK_COUNT
    assert [c["chunkIndex"] for c in body["chunks"]] == [10, 11, 12]
    assert body["chunks"][0]["content"] == "chunk-number-010"


@pytest.mark.asyncio
async def test_offset_zero_is_explicitly_accepted(client: AsyncClient, seeded):
    resp = await client.get(
        f"/api/documents/{seeded['doc_id']}?limit=2&offset=0",
        headers=_auth_header(seeded["token"]),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["offset"] == 0
    assert [c["chunkIndex"] for c in body["chunks"]] == [0, 1]


@pytest.mark.asyncio
async def test_pagination_windows_are_disjoint_and_ordered(
    client: AsyncClient, seeded
):
    """Walking pages covers every chunk exactly once, in chunk_index order."""
    seen: list[int] = []
    offset = 0
    while True:
        resp = await client.get(
            f"/api/documents/{seeded['doc_id']}?limit=17&offset={offset}",
            headers=_auth_header(seeded["token"]),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        indexes = [c["chunkIndex"] for c in body["chunks"]]
        assert indexes == sorted(indexes)
        if not indexes:
            break
        assert not set(indexes) & set(seen), "pages must be disjoint"
        seen.extend(indexes)
        offset += 17

    assert seen == list(range(CHUNK_COUNT))


@pytest.mark.asyncio
async def test_offset_past_end_returns_empty_window_with_total(
    client: AsyncClient, seeded
):
    resp = await client.get(
        f"/api/documents/{seeded['doc_id']}?offset={CHUNK_COUNT + 25}",
        headers=_auth_header(seeded["token"]),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chunks"] == []
    assert body["total"] == CHUNK_COUNT


@pytest.mark.asyncio
async def test_limit_at_maximum_is_accepted(client: AsyncClient, seeded):
    resp = await client.get(
        f"/api/documents/{seeded['doc_id']}?limit={MAX_CHUNK_LIMIT}",
        headers=_auth_header(seeded["token"]),
    )
    assert resp.status_code == 200
    assert resp.json()["limit"] == MAX_CHUNK_LIMIT


# ---------------------------------------------------------------------------
# 4. Invalid pagination parameters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        f"limit={MAX_CHUNK_LIMIT + 1}",
        f"limit={MAX_CHUNK_LIMIT * 10}",
        "limit=0",
        "limit=-1",
        "limit=abc",
        "offset=-1",
        "offset=-100",
        "offset=1.5",
        "limit=abc&offset=-3",
    ],
)
async def test_invalid_pagination_params_rejected(client: AsyncClient, seeded, query):
    resp = await client.get(
        f"/api/documents/{seeded['doc_id']}?{query}",
        headers=_auth_header(seeded["token"]),
    )
    assert resp.status_code == 422, f"{query} -> {resp.status_code}: {resp.text}"
    assert "detail" in resp.json()


# ---------------------------------------------------------------------------
# 5. Ownership isolation is unchanged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_user_detail_still_rejected(client: AsyncClient, seeded):
    resp = await client.get(
        f"/api/documents/{seeded['doc_id']}",
        headers=_auth_header(seeded["other_token"]),
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Document not found"


@pytest.mark.asyncio
async def test_cross_user_detail_rejected_with_pagination_params(
    client: AsyncClient, seeded
):
    resp = await client.get(
        f"/api/documents/{seeded['doc_id']}?limit=5&offset=0",
        headers=_auth_header(seeded["other_token"]),
    )
    assert resp.status_code == 404
    # Ownership is checked before any chunk data is read.
    assert "chunks" not in resp.json()
