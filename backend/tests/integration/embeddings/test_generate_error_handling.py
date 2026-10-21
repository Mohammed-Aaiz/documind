"""Regression tests: POST /api/embeddings/generate must never disclose internals.

Invariant under test:

    Internal embedding/model/database exception details may appear in server
    logs, but must never appear in the client-facing API response.

Background: the handler used to return

    detail=f"Embedding generation failed: {str(e)}"

and its ``try`` block spans BOTH model inference (``embed_texts``) and
``await db.commit()``, so the interpolated string could carry third-party ML,
filesystem, network or database-driver detail.  It now logs the full exception
via ``logger.exception(...)`` and returns the fixed message
``"Embedding generation failed"``.

These tests are written against the *observable contract*, and every leak
assertion scans the raw response body — not just the parsed ``detail`` field —
so a future regression that leaks the text through any field is caught.

No real embedding model is loaded and no network call is made: ``embed_texts``
is monkeypatched at ``embeddings.routes.embed_texts`` (the route imports the
function into its module namespace, so that is the correct patch target).
"""

import logging
import uuid

import pytest
from httpx import AsyncClient

import embeddings.routes as embeddings_routes
from tests.fixtures.graph_data import create_document_with_chunks


LOGIN_URL = "/api/auth/login"
GENERATE_URL = "/api/embeddings/generate"

# ---------------------------------------------------------------------------
# Unmistakable fake sensitive data.  If any of these appear in a response body,
# the endpoint is disclosing internals.
# ---------------------------------------------------------------------------

# A fake PostgreSQL DSN complete with credentials and an internal hostname.
SECRET_DSN = "postgresql://leakuser:LEAKED-PASSWORD-9f3a@leak-host.internal:5432/leakdb"
# A fake absolute filesystem path resembling a HuggingFace cache directory.
SECRET_PATH = "C:/Users/leakuser/.cache/huggingface/hub/models--secret-model"
# A short recognizable sentinel that is easy to scan for.
SENTINEL = "LEAK-SENTINEL-9f3a2b"

# Generic markers that indicate internal machinery reached the client.
# NB: "RuntimeError" is checked as a *type name* leak, distinct from SENTINEL.
_LEAK_MARKERS = (
    SENTINEL,
    SECRET_DSN,
    SECRET_PATH,
    "Traceback",
    "RuntimeError",
    "psycopg",
    "sqlalchemy",
    "SELECT ",
)

EMBEDDING_DIMENSIONS = 384

CHUNK_COUNT = 3


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client: AsyncClient, email: str) -> str:
    resp = await client.post(LOGIN_URL, json={"email": email, "password": "Pass123!"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _assert_body_is_clean(resp, context: str) -> None:
    """The raw response body must contain no internal detail whatsoever.

    Scans the serialized body rather than ``resp.json()["detail"]`` so that a
    leak through any other field is also caught.
    """
    body = resp.text
    for marker in _LEAK_MARKERS:
        assert marker not in body, (
            f"{context}: response body leaked internal detail {marker!r}. "
            f"Body was: {body}"
        )


class _RecordingLeakyEmbedder:
    """Callable that raises a leaky exception and remembers what it raised.

    Remembering the exception object is what makes the leak test non-vacuous:
    the test asserts the sentinels really ARE inside the raised exception
    (``str(exc)``) while being ABSENT from the response.  Without that, a test
    could pass simply because the exception never contained the sentinels.
    """

    def __init__(self) -> None:
        self.raised: BaseException | None = None
        self.call_count = 0
        self.received_texts: list[str] | None = None

    def __call__(self, texts):
        self.call_count += 1
        self.received_texts = list(texts)
        exc = RuntimeError(
            f"model load failed: path={SECRET_PATH} dsn={SECRET_DSN} {SENTINEL}"
        )
        self.raised = exc
        raise exc


def _fake_embed_texts(texts):
    """Deterministic vectors of the correct dimension — never the real model."""
    return [[0.5] * EMBEDDING_DIMENSIONS for _ in texts]


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
async def seeded(client: AsyncClient, db_session, create_test_user):
    """Owner + an unrelated user; owner has a chunked doc and an empty doc.

    E-mail addresses are unique per test: the shared test database is not
    truncated between tests, so fixed addresses would violate the UNIQUE
    constraint from the second test onwards.
    """
    tag = uuid.uuid4().hex[:10]
    owner_email = f"emb-owner-{tag}@test.com"
    other_email = f"emb-other-{tag}@test.com"

    owner = await create_test_user(email=owner_email, password="Pass123!")
    await create_test_user(email=other_email, password="Pass123!")

    doc, rows = await create_document_with_chunks(
        db_session,
        owner.id,
        name="embeddings-doc.pdf",
        chunks=[
            {"content": f"chunk content number {i}", "page": i + 1}
            for i in range(CHUNK_COUNT)
        ],
    )
    empty_doc, _ = await create_document_with_chunks(
        db_session,
        owner.id,
        name="empty-doc.pdf",
        chunks=[],
    )
    await db_session.commit()

    return {
        "owner_token": await _login(client, owner_email),
        "other_token": await _login(client, other_email),
        "doc_id": str(doc.id),
        "doc": doc,
        "chunks": rows,
        "empty_doc_id": str(empty_doc.id),
    }


async def _embedding_status(db_session, document_id):
    """Re-read the persisted embedding_status from the database."""
    from sqlalchemy import select

    from documents.models import Document

    db_session.expire_all()
    row = (
        await db_session.execute(
            select(Document).where(Document.id == uuid.UUID(str(document_id)))
        )
    ).scalar_one()
    return row.embedding_status


# ===========================================================================
# 1. embed_texts failure does not leak exception details
# ===========================================================================


@pytest.mark.asyncio
async def test_embed_texts_failure_does_not_leak_exception_details(
    client: AsyncClient, seeded, db_session, monkeypatch
):
    """A leaky exception from model inference must not reach the client."""
    leaky = _RecordingLeakyEmbedder()
    monkeypatch.setattr(embeddings_routes, "embed_texts", leaky)

    resp = await client.post(
        GENERATE_URL,
        json={"documentId": seeded["doc_id"]},
        headers=_auth_header(seeded["owner_token"]),
    )

    # The patched callable was actually exercised (guards against a vacuous test).
    assert leaky.call_count == 1, "embed_texts was not invoked by the endpoint"

    # The sentinels really were inside the raised exception ...
    assert leaky.raised is not None
    raised_text = str(leaky.raised)
    assert SENTINEL in raised_text
    assert SECRET_DSN in raised_text
    assert SECRET_PATH in raised_text

    # ... and are absent from the response.
    assert resp.status_code == 500, resp.text
    assert resp.json()["detail"] == "Embedding generation failed"
    _assert_body_is_clean(resp, "embed_texts failure")

    # The endpoint also received the real chunk contents.
    assert leaky.received_texts == [f"chunk content number {i}" for i in range(CHUNK_COUNT)]


class _DatabaseTopologyError(RuntimeError):
    """Custom exception whose *name* is itself sensitive-looking.

    A regression that returned ``type(e).__name__`` (instead of ``str(e)``)
    would pass a body scan for the sentinel but fail this test.
    """


@pytest.mark.asyncio
async def test_exception_type_name_is_not_disclosed(
    client: AsyncClient, seeded, monkeypatch
):
    """No exception class name and no traceback may appear in the body."""
    raised: dict = {}

    def custom_named_failure(texts):
        exc = _DatabaseTopologyError(f"internal detail {SENTINEL}")
        raised["exc"] = exc
        raise exc

    monkeypatch.setattr(embeddings_routes, "embed_texts", custom_named_failure)

    resp = await client.post(
        GENERATE_URL,
        json={"documentId": seeded["doc_id"]},
        headers=_auth_header(seeded["owner_token"]),
    )

    assert resp.status_code == 500
    # The custom type name really was available to leak.
    assert type(raised["exc"]).__name__ == "_DatabaseTopologyError"

    body = resp.text
    assert "_DatabaseTopologyError" not in body
    assert "RuntimeError" not in body
    assert "Traceback" not in body
    assert SENTINEL not in body
    assert resp.json()["detail"] == "Embedding generation failed"


# ===========================================================================
# 2. Server-side logging is preserved
# ===========================================================================


@pytest.mark.asyncio
async def test_failure_is_logged_server_side_with_traceback(
    client: AsyncClient, seeded, monkeypatch, caplog
):
    """Diagnostics are moved to the log, not deleted."""
    leaky = _RecordingLeakyEmbedder()
    monkeypatch.setattr(embeddings_routes, "embed_texts", leaky)

    with caplog.at_level(logging.ERROR, logger="embeddings.routes"):
        resp = await client.post(
            GENERATE_URL,
            json={"documentId": seeded["doc_id"]},
            headers=_auth_header(seeded["owner_token"]),
        )

    assert resp.status_code == 500

    log_text = caplog.text
    # The sentinel and the fake secrets ARE in the log — detail was preserved.
    assert SENTINEL in log_text, f"sentinel missing from server log: {log_text!r}"
    assert SECRET_DSN in log_text
    assert SECRET_PATH in log_text
    # And a real traceback was emitted (logger.exception, not logger.error).
    assert "Traceback (most recent call last)" in log_text
    assert "RuntimeError" in log_text

    # The log message identifies the document.
    assert seeded["doc_id"] in log_text

    # Cross-check the invariant in one place: present in the log, absent in the body.
    assert SENTINEL not in resp.text


# ===========================================================================
# 3. Error status is persisted
# ===========================================================================


@pytest.mark.asyncio
async def test_embedding_status_is_persisted_as_error(
    client: AsyncClient, seeded, db_session, monkeypatch
):
    """The pre-existing error-state transition is protected."""
    monkeypatch.setattr(embeddings_routes, "embed_texts", _RecordingLeakyEmbedder())

    resp = await client.post(
        GENERATE_URL,
        json={"documentId": seeded["doc_id"]},
        headers=_auth_header(seeded["owner_token"]),
    )
    assert resp.status_code == 500

    assert await _embedding_status(db_session, seeded["doc_id"]) == "error"


# ===========================================================================
# 4. Unknown document remains 404
# ===========================================================================


@pytest.mark.asyncio
async def test_unknown_document_returns_404(client: AsyncClient, seeded, monkeypatch):
    monkeypatch.setattr(embeddings_routes, "embed_texts", _fake_embed_texts)

    resp = await client.post(
        GENERATE_URL,
        json={"documentId": str(uuid.uuid4())},
        headers=_auth_header(seeded["owner_token"]),
    )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Document not found"
    _assert_body_is_clean(resp, "unknown document")


@pytest.mark.asyncio
async def test_generate_unauthenticated_rejected(
    client: AsyncClient, seeded, monkeypatch
):
    monkeypatch.setattr(embeddings_routes, "embed_texts", _fake_embed_texts)

    resp = await client.post(GENERATE_URL, json={"documentId": seeded["doc_id"]})
    assert resp.status_code == 401


# ===========================================================================
# 5. Cross-user document remains isolated
# ===========================================================================


@pytest.mark.asyncio
async def test_cross_user_document_is_isolated(
    client: AsyncClient, seeded, db_session, monkeypatch
):
    """User B cannot embed User A's document, and A's document is intact."""
    leaky = _RecordingLeakyEmbedder()
    monkeypatch.setattr(embeddings_routes, "embed_texts", leaky)

    resp = await client.post(
        GENERATE_URL,
        json={"documentId": seeded["doc_id"]},
        headers=_auth_header(seeded["other_token"]),
    )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Document not found"
    _assert_body_is_clean(resp, "cross-user document")

    # Ownership is checked first: the model must never have been called.
    assert leaky.call_count == 0, "embed_texts was invoked for another user's document"

    # User A's document is untouched.
    owner_view = await client.get(
        f"/api/documents/{seeded['doc_id']}",
        headers=_auth_header(seeded["owner_token"]),
    )
    assert owner_view.status_code == 200
    assert owner_view.json()["id"] == seeded["doc_id"]

    assert await _embedding_status(db_session, seeded["doc_id"]) != "error"


# ===========================================================================
# 6. Document with no chunks remains 400
# ===========================================================================


@pytest.mark.asyncio
async def test_document_without_chunks_returns_400(
    client: AsyncClient, seeded, monkeypatch
):
    leaky = _RecordingLeakyEmbedder()
    monkeypatch.setattr(embeddings_routes, "embed_texts", leaky)

    resp = await client.post(
        GENERATE_URL,
        json={"documentId": seeded["empty_doc_id"]},
        headers=_auth_header(seeded["owner_token"]),
    )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Document has no chunks"
    _assert_body_is_clean(resp, "document without chunks")
    assert leaky.call_count == 0


# ===========================================================================
# 7. Successful embedding contract remains unchanged
# ===========================================================================


@pytest.mark.asyncio
async def test_successful_generation_contract_unchanged(
    client: AsyncClient, seeded, db_session, monkeypatch
):
    monkeypatch.setattr(embeddings_routes, "embed_texts", _fake_embed_texts)

    resp = await client.post(
        GENERATE_URL,
        json={"documentId": seeded["doc_id"]},
        headers=_auth_header(seeded["owner_token"]),
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Existing response keys are preserved.
    assert set(body) == {"message", "documentId", "chunksEmbedded"}
    assert body["message"] == "Embeddings generated successfully"
    assert body["documentId"] == seeded["doc_id"]
    assert body["chunksEmbedded"] == CHUNK_COUNT

    # Status transitions to ready once embeddings are stored.
    assert await _embedding_status(db_session, seeded["doc_id"]) == "ready"

    # The stored vectors are real values of the correct dimension, not NULL.
    # Re-query rather than reading the fixture's identities, whose state is
    # from before the endpoint's own commit.
    from sqlalchemy import select, func

    from documents.models import DocumentChunk

    db_session.expire_all()
    stored = (
        await db_session.execute(
            select(DocumentChunk).where(
                DocumentChunk.document_id == uuid.UUID(seeded["doc_id"])
            )
        )
    ).scalars().all()
    assert len(stored) == CHUNK_COUNT
    for row in stored:
        assert row.embedding is not None
        assert len(list(row.embedding)) == EMBEDDING_DIMENSIONS

    embedded_count = (
        await db_session.execute(
            select(func.count())
            .select_from(DocumentChunk)
            .where(
                DocumentChunk.document_id == uuid.UUID(seeded["doc_id"]),
                DocumentChunk.embedding.is_not(None),
            )
        )
    ).scalar_one()
    assert embedded_count == CHUNK_COUNT


@pytest.mark.asyncio
async def test_successful_generation_does_not_log_an_error(
    client: AsyncClient, seeded, monkeypatch, caplog
):
    """The success path must not emit the failure log."""
    monkeypatch.setattr(embeddings_routes, "embed_texts", _fake_embed_texts)

    with caplog.at_level(logging.ERROR, logger="embeddings.routes"):
        resp = await client.post(
            GENERATE_URL,
            json={"documentId": seeded["doc_id"]},
            headers=_auth_header(seeded["owner_token"]),
        )

    assert resp.status_code == 200
    assert "Embedding generation failed" not in caplog.text
    assert "Traceback" not in caplog.text


# ===========================================================================
# 8. Database-commit failure leak regression
# ===========================================================================


@pytest.mark.asyncio
async def test_database_commit_failure_does_not_leak(
    client: AsyncClient, seeded, monkeypatch
):
    """The same generic-error protection must cover a commit failure.

    The audit established that the route's ``try`` block spans both
    ``embed_texts(...)`` and ``await db.commit()``, so a database failure is
    caught by the same handler and must produce the same non-disclosing
    response.

    The failure is induced by wrapping ``AsyncSession.commit`` so the FIRST
    commit performed after patching raises a leaky ``OperationalError`` whose
    message embeds SQL plus the fake DSN.  The first commit inside the request
    is the handler's ``await db.commit()`` — the document lookup, the chunk
    query and the earlier ``flush()`` do not commit.  The wrapper raises
    *before* delegating to the real commit, so the session transaction is not
    invalidated and the handler's error-path commit can still run.

    The wrapper records what it raised so the test can prove the sentinel really
    was inside the exception rather than assuming it.
    """
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.exc import OperationalError

    monkeypatch.setattr(embeddings_routes, "embed_texts", _fake_embed_texts)

    faulty_sql = (
        f"SELECT * FROM document_chunks WHERE dsn='{SECRET_DSN}' {SENTINEL}"
    )

    state = {"raised": None, "calls": 0}
    real_commit = AsyncSession.commit

    async def failing_commit(self):
        state["calls"] += 1
        if state["calls"] == 1:
            exc = OperationalError(faulty_sql, None, Exception(f"db down {SENTINEL}"))
            state["raised"] = exc
            raise exc
        return await real_commit(self)

    monkeypatch.setattr(AsyncSession, "commit", failing_commit)

    resp = await client.post(
        GENERATE_URL,
        json={"documentId": seeded["doc_id"]},
        headers=_auth_header(seeded["owner_token"]),
    )

    # The induced exception really did carry the internals.
    assert state["raised"] is not None, "no commit failure was induced"
    raised_text = str(state["raised"])
    assert SENTINEL in raised_text or SECRET_DSN in raised_text

    # The client receives a generic failure, not the database exception.
    assert resp.status_code == 500, resp.text
    assert resp.json()["detail"] == "Embedding generation failed"
    _assert_body_is_clean(resp, "database commit failure")

    # And no raw database exception type is surfaced.
    body = resp.text
    assert "OperationalError" not in body
    assert "IntegrityError" not in body
    assert "document_chunks" not in body
