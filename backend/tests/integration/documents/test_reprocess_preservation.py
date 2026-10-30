"""Reprocessing must never destroy the last successfully indexed version.

**The defect these tests exist for.**  The reprocess route deleted the
document's chunks and structure rows up front and then committed
unconditionally, so a run that failed *after* the deletion destroyed the
previous version:

* failing before chunking  -> the embedded rows were gone and nothing replaced
  them (``chunkCount`` 0);
* failing after chunking   -> the embedded rows were replaced by rows with
  ``embedding IS NULL``, and the document reported ``chunkCount`` 2 while
  ``embeddingStatus`` said ``error``.

**What is asserted here.**  Every test drives the real HTTP route, the real
processing pipeline and the real database, and checks *persisted* rows and
*retrieval* behaviour — not mocked return values and not just a status code:

* the previous rows survive a failed attempt with their ids and content intact;
* they are still eligible for the semantic path (its two filters —
  ``embedding IS NOT NULL`` and ``d.embedding_status = 'ready'`` — still hold;
  that path's SQL itself needs pgvector, so it cannot be executed on the SQLite
  test database);
* the existing **structural** retrieval path really does return them;
* a successful attempt replaces them and leaves no active duplicates;
* a first-time failure reports failure honestly with nothing searchable.

Embedding inference and optional graph LLM extraction are stubbed; this suite
checks index replacement and rollback, not external model availability.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from chat.rag import retrieve_structural_candidates
from documents.models import Document, DocumentChunk
from graph.models import DocumentGraphEdge, DocumentStructureElement
from tests.fixtures.pdf_layout import add_text, new_page, new_pdf


UPLOAD_URL = "/api/documents/upload"
LOGIN_URL = "/api/auth/login"
PASSWORD = "Pass123!"

#: A real embedding vector (the project's 384 dimensions), so the "indexed"
#: state under test is genuinely searchable rather than None-stubbed.
_VECTOR = [0.01] * 384

#: Long enough that the default (legacy) chunker produces more than one chunk,
#: which is what makes the structural path's NEXT/PREV edges exist.
_DOCUMENT_TEXT = " ".join(
    f"Sentence {index} of the preservation fixture describes indexed content "
    f"number {index} with enough words to be chunked and embedded."
    for index in range(40)
)

#: A word that exists in the fixture and nowhere else, for retrieval questions.
_UNIQUE_TERM = "preservationfixtureword"


def _fake_embed(texts: list[str]) -> list[list[float]]:
    return [list(_VECTOR) for _ in texts]


def _explode(_texts: list[str]) -> list[list[float]]:
    raise RuntimeError("embedding model unavailable")


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client: AsyncClient, create_test_user, tag: str) -> tuple[str, str]:
    email = f"{tag}-{uuid.uuid4().hex[:8]}@test.com"
    await create_test_user(email=email, password=PASSWORD, name=tag)
    resp = await client.post(LOGIN_URL, json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return email, resp.json()["access_token"]


async def _upload(client: AsyncClient, token: str, text: str, name: str = "preservation.txt"):
    return await client.post(
        UPLOAD_URL,
        headers=_auth(token),
        files={"file": (name, text.encode("utf-8"), "text/plain")},
    )


async def _chunk_rows(db, document_id) -> list[DocumentChunk]:
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    )
    return list(result.scalars())


async def _doc_row(db, document_id) -> Document:
    result = await db.execute(select(Document).where(Document.id == document_id))
    return result.scalar_one()


async def _graph_edge_count(db, document_id) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(DocumentGraphEdge)
        .where(DocumentGraphEdge.document_id == document_id)
    )
    return int(result.scalar_one())


def _snapshot(rows: list[DocumentChunk]) -> list[tuple[str, str, bool]]:
    """Identity + content + searchability of each persisted row."""
    return [(str(r.id), r.content, r.embedding is not None) for r in rows]


# ---------------------------------------------------------------------------
# A. A failed replacement preserves the previously indexed version
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_reprocess_at_embedding_keeps_previous_version(
    client: AsyncClient, db_session, create_test_user, monkeypatch
):
    """**The demonstrated defect.**  Embedding fails: the old version must live.

    Asserts persisted rows, the semantic path's eligibility filters and real
    structural retrieval — not the HTTP status alone.
    """
    from documents import routes as documents_routes

    _email, token = await _login(client, create_test_user, "preserve-embed")

    monkeypatch.setattr(documents_routes, "embed_texts", _fake_embed)
    upload = await _upload(client, token, _DOCUMENT_TEXT)
    assert upload.status_code == 201, upload.text
    doc_id = upload.json()["id"]
    assert upload.json()["status"] == "ready", upload.text

    before_rows = await _chunk_rows(db_session, doc_id)
    before_doc = await _doc_row(db_session, doc_id)
    before = _snapshot(before_rows)
    before_edges = await _graph_edge_count(db_session, doc_id)
    assert len(before_rows) >= 2, "fixture must produce several chunks"
    assert all(embedded for _id, _content, embedded in before)

    # The replacement attempt fails at the embedding step.
    monkeypatch.setattr(documents_routes, "embed_texts", _explode)
    resp = await client.post(f"/api/documents/{doc_id}/reprocess", headers=_auth(token))

    assert resp.status_code == 500, resp.text
    assert "unchanged" in resp.json()["detail"].lower()

    # 1. The persisted rows are the previous version, unchanged.
    after_rows = await _chunk_rows(db_session, doc_id)
    assert _snapshot(after_rows) == before, "previous chunk rows were not preserved"

    # 2. The document still describes that version truthfully.
    after_doc = await _doc_row(db_session, doc_id)
    assert after_doc.status == before_doc.status == "ready"
    assert after_doc.embedding_status == "ready"
    assert after_doc.chunk_count == before_doc.chunk_count == len(before_rows)

    # 3. The graph the retrieval path traverses is untouched.
    assert await _graph_edge_count(db_session, doc_id) == before_edges

    # 4. The preserved rows still satisfy the semantic path's own filters.
    assert after_doc.embedding_status == "ready"
    assert all(row.embedding is not None for row in after_rows)

    # 5. The structural retrieval path really returns the preserved chunk.
    seed_id = before[0][0]
    retrieved = await retrieve_structural_candidates(
        db_session,
        str(after_doc.user_id),
        f"{_UNIQUE_TERM} retrieval",
        semantic_seed_ids=[seed_id],
        limit=10,
    )
    assert retrieved, "the preserved version is not reachable through retrieval"
    assert any(c.chunk_id == seed_id for c in retrieved)
    preserved_content = {content for _id, content, _e in before}
    assert any(c.content in preserved_content for c in retrieved)


# ---------------------------------------------------------------------------
# A2-A4. The same invariant at the other failure boundaries
# ---------------------------------------------------------------------------


async def _indexed_document(client, db_session, create_test_user, monkeypatch, tag: str):
    """Upload one document and return ``(token, doc_id, snapshot)``."""
    from documents import routes as documents_routes

    _email, token = await _login(client, create_test_user, tag)
    monkeypatch.setattr(documents_routes, "embed_texts", _fake_embed)
    upload = await _upload(client, token, _DOCUMENT_TEXT, name=f"{tag}.txt")
    assert upload.status_code == 201, upload.text
    doc_id = upload.json()["id"]
    rows = await _chunk_rows(db_session, doc_id)
    assert rows and all(row.embedding is not None for row in rows)
    return token, doc_id, _snapshot(rows)


@pytest.mark.asyncio
async def test_failed_reprocess_at_extraction_keeps_previous_version(
    client: AsyncClient, db_session, create_test_user, monkeypatch
):
    """Extraction raises: the previous version must survive."""
    from documents import routes as documents_routes

    token, doc_id, before = await _indexed_document(
        client, db_session, create_test_user, monkeypatch, "preserve-extract"
    )

    def _fail(*_args, **_kwargs):
        raise RuntimeError("extraction failed")

    monkeypatch.setattr(documents_routes, "extract_document", _fail)
    resp = await client.post(f"/api/documents/{doc_id}/reprocess", headers=_auth(token))

    assert resp.status_code == 500, resp.text
    assert _snapshot(await _chunk_rows(db_session, doc_id)) == before
    doc = await _doc_row(db_session, doc_id)
    assert doc.status == "ready"
    assert doc.embedding_status == "ready"


@pytest.mark.asyncio
async def test_failed_reprocess_at_chunk_creation_keeps_previous_version(
    client: AsyncClient, db_session, create_test_user, monkeypatch
):
    """Chunk creation raises: the previous version must survive."""
    from documents import routes as documents_routes

    token, doc_id, before = await _indexed_document(
        client, db_session, create_test_user, monkeypatch, "preserve-chunks"
    )

    def _fail(*_args, **_kwargs):
        raise RuntimeError("chunk creation failed")

    monkeypatch.setattr(documents_routes, "_build_chunk_objects", _fail)
    resp = await client.post(f"/api/documents/{doc_id}/reprocess", headers=_auth(token))

    assert resp.status_code == 500, resp.text
    assert _snapshot(await _chunk_rows(db_session, doc_id)) == before
    doc = await _doc_row(db_session, doc_id)
    assert doc.status == "ready"
    assert doc.embedding_status == "ready"


@pytest.mark.asyncio
async def test_failed_reprocess_at_graph_keeps_previous_version(
    client: AsyncClient, db_session, create_test_user, monkeypatch
):
    """The latest persistence boundary fails after new rows exist.

    Extraction, chunking, embedding and the structure/chunk writes have already
    happened when the graph step raises, so this is the strongest form of the
    invariant: everything the attempt wrote must be discarded, including rows
    that already carried embeddings.
    """
    from documents import routes as documents_routes

    token, doc_id, before = await _indexed_document(
        client, db_session, create_test_user, monkeypatch, "preserve-graph"
    )
    edges_before = await _graph_edge_count(db_session, doc_id)

    async def _fail(*_args, **_kwargs):
        raise RuntimeError("graph construction failed")

    monkeypatch.setattr(documents_routes, "replace_document_graph", _fail)
    resp = await client.post(f"/api/documents/{doc_id}/reprocess", headers=_auth(token))

    assert resp.status_code == 500, resp.text
    assert _snapshot(await _chunk_rows(db_session, doc_id)) == before
    assert await _graph_edge_count(db_session, doc_id) == edges_before
    doc = await _doc_row(db_session, doc_id)
    assert doc.status == "ready"
    assert doc.embedding_status == "ready"
    assert doc.chunk_count == len(before)


# ---------------------------------------------------------------------------
# B. A successful replacement really replaces
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_reprocess_replaces_and_leaves_no_duplicates(
    client: AsyncClient, db_session, create_test_user, monkeypatch
):
    """A successful run commits the new version and nothing stale survives."""
    token, doc_id, before = await _indexed_document(
        client, db_session, create_test_user, monkeypatch, "replace-ok"
    )
    before_ids = {row_id for row_id, _content, _embedded in before}

    resp = await client.post(f"/api/documents/{doc_id}/reprocess", headers=_auth(token))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ready"
    assert body["embeddingStatus"] == "ready"

    after_rows = await _chunk_rows(db_session, doc_id)
    after_ids = {str(row.id) for row in after_rows}
    doc = await _doc_row(db_session, doc_id)

    # New rows exist, are embedded, and the reported count matches the rows.
    assert after_rows, "successful reprocess produced no chunks"
    assert all(row.embedding is not None for row in after_rows)
    assert doc.chunk_count == len(after_rows) == body["chunkCount"]
    # The previous version is gone rather than duplicated.
    assert after_ids.isdisjoint(before_ids), "stale rows survived the replacement"
    # ...and the replacement is what retrieval returns.
    retrieved = await retrieve_structural_candidates(
        db_session,
        str(doc.user_id),
        f"{_UNIQUE_TERM} retrieval",
        semantic_seed_ids=[sorted(after_ids)[0]],
        limit=10,
    )
    assert retrieved
    assert all(c.chunk_id in after_ids for c in retrieved)


# ---------------------------------------------------------------------------
# C. A first-time failure reports failure honestly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_time_ingestion_failure_reports_no_searchable_content(
    client: AsyncClient, db_session, create_test_user, monkeypatch
):
    """No previous version exists: the failure must not look like content."""
    from documents import routes as documents_routes

    _email, token = await _login(client, create_test_user, "first-time-fail")

    monkeypatch.setattr(documents_routes, "embed_texts", _explode)
    upload = await _upload(client, token, _DOCUMENT_TEXT, name="first-time.txt")

    assert upload.status_code == 201, upload.text
    body = upload.json()
    doc_id = body["id"]

    assert body["status"] == "error"
    assert body["embeddingStatus"] == "error"
    assert body["chunkCount"] == 0, "a failed ingestion must not report chunks"

    doc = await _doc_row(db_session, doc_id)
    assert doc.status == "error" and doc.chunk_count == 0
    # The semantic path excludes this document: it filters on
    # ``d.embedding_status = 'ready'``, which is not satisfied.
    assert doc.embedding_status != "ready"

    # Whatever rows the failed attempt left behind carry no vectors, so the
    # semantic path's ``embedding IS NOT NULL`` filter excludes them too.
    rows = await _chunk_rows(db_session, doc_id)
    assert all(row.embedding is None for row in rows)


@pytest.mark.asyncio
async def test_failed_reprocess_without_previous_version_reports_failure(
    client: AsyncClient, db_session, create_test_user, monkeypatch
):
    """A document with nothing indexed stays honest when the retry fails too."""
    from documents import routes as documents_routes

    _email, token = await _login(client, create_test_user, "nothing-to-preserve")

    monkeypatch.setattr(documents_routes, "embed_texts", _explode)
    upload = await _upload(client, token, _DOCUMENT_TEXT, name="nothing.txt")
    assert upload.status_code == 201, upload.text
    doc_id = upload.json()["id"]

    resp = await client.post(f"/api/documents/{doc_id}/reprocess", headers=_auth(token))

    assert resp.status_code == 500, resp.text
    assert "no searchable content" in resp.json()["detail"].lower()

    doc = await _doc_row(db_session, doc_id)
    assert doc.status == "error"
    assert doc.embedding_status == "error"
    assert doc.chunk_count == 0
    rows = await _chunk_rows(db_session, doc_id)
    assert all(row.embedding is None for row in rows)


# ---------------------------------------------------------------------------
# C2-C4. The remaining boundaries: the final verdict, the structure stage and
#        the structure rows themselves
# ---------------------------------------------------------------------------

#: One line of real text placed on every generated PDF page.  Long enough, over
#: several pages, that extraction, chunking and the structural graph all
#: produce several rows and edges — so a failure test has real persisted state
#: to preserve rather than an empty fixture.
_PDF_SENTENCE = (
    "Sentence {index} of the preservation PDF fixture records indexed content "
    "that the structural graph and the retrieval paths can both reach."
)


def _pdf_bytes(*, page_count: int = 3, lines_per_page: int = 14) -> bytes:
    """Build a real text-layer PDF (every page carries usable text).

    Uses the shared deterministic layout builders, so the extractor and the
    parser see genuine PyMuPDF content rather than bytes we invented.
    """
    doc = new_pdf()
    for page_number in range(page_count):
        page = new_page(doc)
        for line in range(lines_per_page):
            index = page_number * lines_per_page + line
            add_text(
                page,
                40,
                60 + line * 16,
                _PDF_SENTENCE.format(index=index),
                size=10,
            )
    data = doc.tobytes()
    doc.close()
    return data


async def _upload_pdf(client: AsyncClient, token: str, data: bytes, name: str):
    return await client.post(
        UPLOAD_URL,
        headers=_auth(token),
        files={"file": (name, data, "application/pdf")},
    )


async def _structure_rows(db, document_id) -> list[DocumentStructureElement]:
    result = await db.execute(
        select(DocumentStructureElement)
        .where(DocumentStructureElement.document_id == document_id)
        .order_by(DocumentStructureElement.sequence_index)
    )
    return list(result.scalars().all())


def _structure_snapshot(rows: list[DocumentStructureElement]) -> list[tuple]:
    """Identity, type, order, page, content and parent link of each row."""
    return [
        (
            str(row.id),
            row.element_type,
            row.sequence_index,
            row.page_number,
            row.content,
            str(row.parent_id) if row.parent_id is not None else None,
        )
        for row in rows
    ]


async def _indexed_pdf(client, db_session, create_test_user, monkeypatch, tag: str):
    """Upload one real PDF and return the previously committed state.

    Returns ``(token, doc_id, chunk_snapshot, structure_snapshot)``.  The PDF is
    required because the structure stage only runs for ``file_type == "pdf"``.
    """
    from documents import routes as documents_routes

    _email, token = await _login(client, create_test_user, tag)
    monkeypatch.setattr(documents_routes, "embed_texts", _fake_embed)
    upload = await _upload_pdf(client, token, _pdf_bytes(), name=f"{tag}.pdf")
    assert upload.status_code == 201, upload.text
    doc_id = upload.json()["id"]
    assert upload.json()["status"] == "ready", upload.text

    rows = await _chunk_rows(db_session, doc_id)
    structure = await _structure_rows(db_session, doc_id)
    assert len(rows) >= 2, "fixture must produce several chunks"
    assert all(row.embedding is not None for row in rows)
    assert structure, "the PDF fixture must persist structure rows"
    return token, doc_id, _snapshot(rows), _structure_snapshot(structure)


@pytest.mark.asyncio
async def test_failed_reprocess_at_final_verdict_keeps_previous_version(
    client: AsyncClient, db_session, create_test_user, monkeypatch
):
    """The **final verdict evaluation** fails, after every step has persisted.

    ``_document_verdict`` is evaluated twice per run: once on the extraction
    coverage result and once at the very end, after chunking, embedding, the
    structure stage and the graph have all written their rows.  Only that last
    evaluation is failed, and the test proves the injection landed there — the
    graph really was rebuilt and the verdict really was evaluated twice — so
    the previous version has to survive the latest boundary of all.
    """
    from documents import routes as documents_routes

    token, doc_id, before, structure_before = await _indexed_pdf(
        client, db_session, create_test_user, monkeypatch, "preserve-verdict"
    )
    edges_before = await _graph_edge_count(db_session, doc_id)

    real_verdict = documents_routes._document_verdict
    real_graph = documents_routes.replace_document_graph
    verdict_calls: list[int] = []
    graph_calls: list[int] = []

    def _verdict_failing_on_the_final_call(coverage):
        verdict_calls.append(1)
        if len(verdict_calls) == 2:
            raise RuntimeError("verdict evaluation failed")
        return real_verdict(coverage)

    async def _counting_graph(db, document_id, chunks):
        graph_calls.append(len(chunks))
        return await real_graph(db, document_id, chunks)

    monkeypatch.setattr(
        documents_routes, "_document_verdict", _verdict_failing_on_the_final_call
    )
    monkeypatch.setattr(documents_routes, "replace_document_graph", _counting_graph)

    resp = await client.post(f"/api/documents/{doc_id}/reprocess", headers=_auth(token))

    # The injection reached the intended boundary: every persistence step ran
    # (the graph was rebuilt from the new chunks) and the verdict was reached
    # a second time, where it raised.
    assert graph_calls, "the graph step never ran: the failure was not at the final verdict"
    assert verdict_calls == [1, 1], verdict_calls

    assert resp.status_code == 500, resp.text
    assert "unchanged" in resp.json()["detail"].lower()

    assert _snapshot(await _chunk_rows(db_session, doc_id)) == before
    assert _structure_snapshot(await _structure_rows(db_session, doc_id)) == structure_before
    assert await _graph_edge_count(db_session, doc_id) == edges_before
    doc = await _doc_row(db_session, doc_id)
    assert doc.status == "ready"
    assert doc.embedding_status == "ready"
    assert doc.chunk_count == len(before)


@pytest.mark.asyncio
async def test_failed_reprocess_at_structure_keeps_previous_version(
    client: AsyncClient, db_session, create_test_user, monkeypatch
):
    """The **structure stage** fails with the old rows already deleted.

    ``documents.structure.table_rows_by_source_id`` is the last step inside
    ``replace_document_structure``'s SAVEPOINT: by the time it runs, the
    document's previous structure elements have been deleted and the new ones
    inserted.  Failing there is therefore a structure failure with the previous
    rows already gone from the attempt — and the previous version (chunks,
    embeddings, structure rows and graph) must still be what remains.
    """
    from documents import routes as documents_routes
    from documents import structure as documents_structure

    token, doc_id, before, structure_before = await _indexed_pdf(
        client, db_session, create_test_user, monkeypatch, "preserve-structure"
    )
    edges_before = await _graph_edge_count(db_session, doc_id)

    calls: list[int] = []

    def _fail_after_elements_were_inserted(parsed):
        calls.append(len(parsed.elements))
        raise RuntimeError("structure row evidence failed")

    monkeypatch.setattr(
        documents_structure,
        "table_rows_by_source_id",
        _fail_after_elements_were_inserted,
    )

    resp = await client.post(f"/api/documents/{doc_id}/reprocess", headers=_auth(token))

    # Reached the savepoint tail exactly once, with real parsed elements.
    assert len(calls) == 1, calls
    assert calls[0] > 0, "the parser produced no elements to persist"

    assert resp.status_code == 500, resp.text
    assert "unchanged" in resp.json()["detail"].lower()

    assert _snapshot(await _chunk_rows(db_session, doc_id)) == before
    assert _structure_snapshot(await _structure_rows(db_session, doc_id)) == structure_before
    assert await _graph_edge_count(db_session, doc_id) == edges_before
    doc = await _doc_row(db_session, doc_id)
    assert doc.status == "ready"
    assert doc.embedding_status == "ready"
    assert doc.chunk_count == len(before)


@pytest.mark.asyncio
async def test_failed_reprocess_at_graph_keeps_previous_structure_rows(
    client: AsyncClient, db_session, create_test_user, monkeypatch
):
    """**The previously committed structure rows themselves survive.**

    The graph step fails *after* the structure stage has already replaced the
    document's elements inside its savepoint, so this is the strongest form of
    the structure-row assertion: identity, element type, reading order, page,
    content and parent links of the rows that remain are exactly those of the
    rows committed by the previous run.
    """
    from documents import routes as documents_routes

    token, doc_id, before, structure_before = await _indexed_pdf(
        client, db_session, create_test_user, monkeypatch, "preserve-structure-rows"
    )
    edges_before = await _graph_edge_count(db_session, doc_id)
    assert structure_before, "the fixture must have structure rows to preserve"
    assert edges_before > 0, "the fixture must have graph edges to preserve"

    async def _fail(*_args, **_kwargs):
        raise RuntimeError("graph construction failed")

    monkeypatch.setattr(documents_routes, "replace_document_graph", _fail)
    resp = await client.post(f"/api/documents/{doc_id}/reprocess", headers=_auth(token))

    assert resp.status_code == 500, resp.text
    assert "unchanged" in resp.json()["detail"].lower()

    # The structure rows are the previous run's rows, not the failed attempt's.
    assert _structure_snapshot(await _structure_rows(db_session, doc_id)) == structure_before
    assert _snapshot(await _chunk_rows(db_session, doc_id)) == before
    assert await _graph_edge_count(db_session, doc_id) == edges_before
    doc = await _doc_row(db_session, doc_id)
    assert doc.status == "ready"
    assert doc.embedding_status == "ready"
    assert doc.chunk_count == len(before)
