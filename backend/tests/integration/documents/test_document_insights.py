"""Regression/integration tests for ``GET /api/documents/{document_id}/insights``.

These tests exercise the *actual HTTP endpoint* through the real FastAPI app,
authentication boundary and database session — not the service function in
isolation.

Determinism strategy
--------------------
The owner's main document is built from the explicit ``MAIN_CHUNKS`` /
``MAIN_EDGES`` fixtures below, and every expected metric is *derived* from
those exact values (content lengths, token counts, element types, page
numbers, graph endpoints) rather than hard-coded.  Changing a fixture value
therefore changes the computed expectation and the test would fail if the
endpoint did not reflect the change — the assertions are non-vacuous.

No network access, no external LLM, and no Whisper/TTS/embedding model is
loaded: chunk embeddings are set directly as stored vectors, and the graph is
populated with deterministic rows.  The suite runs on the repository's
existing SQLite test harness.

Cross-database note — COUNT(DISTINCT) and NULL
----------------------------------------------
The documented contract for ``headingPathsRepresented`` is the count of
*distinct non-null* heading paths.  ``insights.py`` computes it as
``COUNT(DISTINCT CAST(heading_path AS TEXT))``.  PostgreSQL ignores NULLs in
``COUNT(DISTINCT ...)`` (so a NULL heading path is excluded, matching the
contract), but the SQLite test harness counts NULL as a distinct value.  To
keep these assertions cross-database correct and non-vacuous, the deterministic
main document has no NULL heading path; NULL handling for ``section``,
``element_type`` and ``token_count`` is still exercised.  The SQLite/PostgreSQL
divergence for a NULL heading path is recorded in the task report as a
follow-up for BACKEND_AGENT rather than being encoded as a passing assertion
here.
"""

from __future__ import annotations

import uuid
from collections import Counter

import pytest
from httpx import AsyncClient

from graph.models import DocumentGraphEdge
from tests.fixtures.graph_data import create_document_with_chunks

LOGIN_URL = "/api/auth/login"
INSIGHTS_URL = "/api/documents/{document_id}/insights"

EMBEDDING_DIM = 384

# ---------------------------------------------------------------------------
# Deterministic fixture data
# ---------------------------------------------------------------------------

# index, content, page, section, heading_path, element_type, token_count
# The final chunk is a *legacy* chunk: no structure metadata at all
# (section / heading_path / element_type / token_count all NULL), which must
# not be assigned a fabricated category.
MAIN_CHUNKS: list[dict] = [
    {"content": "a" * 5, "page": 1, "section": "Alpha", "heading_path": ["Alpha"],
     "element_type": "heading", "token_count": 2},
    {"content": "b" * 10, "page": 1, "section": "Alpha", "heading_path": ["Alpha"],
     "element_type": "paragraph", "token_count": 4},
    {"content": "c" * 15, "page": 2, "section": "Alpha", "heading_path": ["Alpha"],
     "element_type": "paragraph", "token_count": 6},
    {"content": "d" * 20, "page": 2, "section": "Beta", "heading_path": ["Beta"],
     "element_type": "table", "token_count": 8},
    {"content": "e" * 25, "page": 3, "section": "Beta", "heading_path": ["Beta"],
     "element_type": "list", "token_count": 10},
    # Legacy chunk: no section, no element type, no token count.  It keeps a
    # heading_path so that the heading-path DISTINCT count is cross-database
    # stable (see the module note on COUNT(DISTINCT) and NULL below).
    {"content": "f" * 30, "page": 3, "section": None, "heading_path": ["Gamma"],
     "element_type": None, "token_count": None},
]

# (source_index, target_index, relation) — two relation types, endpoints chosen
# so that the distinct union of sources ∪ targets is every chunk.
MAIN_EDGES: list[tuple[int, int, str]] = [
    (0, 1, "NEXT"),
    (1, 2, "NEXT"),
    (2, 3, "NEXT"),
    (3, 4, "SAME_SECTION"),
    (4, 5, "SAME_SECTION"),
]

# Chunks 0..2 carry an embedding; 3..5 do not.
EMBEDDED_INDICES = (0, 1, 2)

MAIN_PROVENANCE = {
    "parser_version": "pymupdf-1.28.2",
    "chunker_version": "chunk-v2-structure-tokens",
    "embedding_model": "all-MiniLM-L6-v2",
}

_LEAK_MARKERS = (
    "psycopg",
    "asyncpg",
    "sqlalchemy",
    "postgresql",
    "invalid input syntax",
    "dataerror",
    "traceback",
    "stored_path",
    "select document",
)

BAD_IDS = [
    "not-a-uuid",
    "12345",
    "'; DROP TABLE documents; --",
    "9f8a7b6c-5d4e-4f3a-8b2c-1d0e9f8a7b6",  # 35 chars
    "9f8a7b6c-5d4e-4f3a-8b2c-1d0e9f8a7bzz",  # non-hex chars
]


# ---------------------------------------------------------------------------
# Derived expectations (from the fixture, never hard-coded)
# ---------------------------------------------------------------------------

def _expected_structure() -> dict:
    lengths = [len(c["content"]) for c in MAIN_CHUNKS]
    tokens = [c["token_count"] for c in MAIN_CHUNKS if c["token_count"] is not None]
    pages = {c["page"] for c in MAIN_CHUNKS if c["page"] is not None}
    sections = {c["section"] for c in MAIN_CHUNKS if c["section"] is not None}
    heading_paths = {
        tuple(c["heading_path"]) for c in MAIN_CHUNKS if c["heading_path"] is not None
    }
    element_counts = Counter(
        c["element_type"] for c in MAIN_CHUNKS if c["element_type"] is not None
    )
    return {
        "totalChunks": len(MAIN_CHUNKS),
        "pagesRepresented": len(pages),
        "pageCount": max(pages),
        "sectionsRepresented": len(sections),
        "headingPathsRepresented": len(heading_paths),
        "elementTypeCounts": dict(element_counts),
        "avgChunkLength": round(sum(lengths) / len(lengths), 2),
        "avgTokenCount": round(sum(tokens) / len(tokens), 2),
        "totalTokenCount": sum(c["token_count"] or 0 for c in MAIN_CHUNKS),
    }


def _expected_graph() -> dict:
    relations = Counter(rel for _, _, rel in MAIN_EDGES)
    nodes = {i for s, t, _ in MAIN_EDGES for i in (s, t)}
    total = len(MAIN_CHUNKS)
    return {
        "edgeCount": len(MAIN_EDGES),
        "relationCounts": dict(relations),
        "nodeCount": len(nodes),
        "coverage": round(len(nodes) / total, 4),
    }


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client: AsyncClient, email: str) -> str:
    resp = await client.post(LOGIN_URL, json={"email": email, "password": "Pass123!"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
async def seeded(client: AsyncClient, db_session, create_test_user):
    """Owner with several documents plus an unrelated user.

    Unique e-mail addresses per test: the shared SQLite database is not
    truncated between tests, so fixed addresses would violate the UNIQUE
    constraint from the second test onwards.
    """
    tag = uuid.uuid4().hex[:10]
    owner_email = f"ins-owner-{tag}@test.com"
    other_email = f"ins-other-{tag}@test.com"

    owner = await create_test_user(email=owner_email, password="Pass123!")
    await create_test_user(email=other_email, password="Pass123!")

    # --- main PDF document: full structure, graph, embeddings, provenance ---
    main_doc, rows = await create_document_with_chunks(
        db_session, owner.id, name="insights-main.pdf", chunks=MAIN_CHUNKS
    )
    main_doc.parser_version = MAIN_PROVENANCE["parser_version"]
    main_doc.chunker_version = MAIN_PROVENANCE["chunker_version"]
    main_doc.embedding_model = MAIN_PROVENANCE["embedding_model"]

    for idx in EMBEDDED_INDICES:
        rows[idx].embedding = [0.0] * EMBEDDING_DIM

    for src, dst, relation in MAIN_EDGES:
        db_session.add(
            DocumentGraphEdge(
                id=uuid.uuid4(),
                document_id=main_doc.id,
                source_chunk_id=rows[src].id,
                target_chunk_id=rows[dst].id,
                relation=relation,
                weight=1.0,
            )
        )

    # --- non-paged document (TXT): all chunk pages are NULL ---
    txt_doc, _ = await create_document_with_chunks(
        db_session,
        owner.id,
        name="insights-notes.txt",
        chunks=[
            {"content": "first note", "page": None},
            {"content": "second note", "page": None},
        ],
    )
    txt_doc.file_type = "txt"

    # --- empty document: zero chunks ---
    empty_doc, _ = await create_document_with_chunks(
        db_session, owner.id, name="insights-empty.pdf", chunks=[]
    )

    # --- chunks but no graph edges ---
    nog_doc, _ = await create_document_with_chunks(
        db_session,
        owner.id,
        name="insights-nograph.pdf",
        chunks=[
            {"content": "x", "page": 1, "element_type": "paragraph", "token_count": 1},
            {"content": "y", "page": 1, "element_type": "paragraph", "token_count": 1},
        ],
    )

    await db_session.commit()

    return {
        "token": await _login(client, owner_email),
        "other_token": await _login(client, other_email),
        "main_id": str(main_doc.id),
        "txt_id": str(txt_doc.id),
        "empty_id": str(empty_doc.id),
        "nograph_id": str(nog_doc.id),
    }


async def _get_insights(client: AsyncClient, token: str, doc_id: str):
    return await client.get(
        f"/api/documents/{doc_id}/insights", headers=_auth_header(token)
    )


# ===========================================================================
# 1. Authentication
# ===========================================================================


@pytest.mark.asyncio
async def test_insights_authenticated_owner_returns_200(client: AsyncClient, seeded):
    resp = await _get_insights(client, seeded["token"], seeded["main_id"])
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_insights_unauthenticated_returns_401(client: AsyncClient, seeded):
    resp = await client.get(INSIGHTS_URL.format(document_id=seeded["main_id"]))
    assert resp.status_code == 401


# ===========================================================================
# 2. Ownership
# ===========================================================================


@pytest.mark.asyncio
async def test_insights_unknown_uuid_returns_404(client: AsyncClient, seeded):
    resp = await _get_insights(client, seeded["token"], str(uuid.uuid4()))
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Document not found"


@pytest.mark.asyncio
async def test_insights_cross_user_returns_404(client: AsyncClient, seeded):
    resp = await _get_insights(client, seeded["other_token"], seeded["main_id"])
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Document not found"
    # No insight data is disclosed for a document the caller does not own.
    assert "structure" not in resp.json()


@pytest.mark.asyncio
async def test_insights_cross_user_is_indistinguishable_from_unknown(
    client: AsyncClient, seeded
):
    """Another user's document must not be distinguishable from a random id."""
    other = await _get_insights(client, seeded["other_token"], seeded["main_id"])
    unknown = await _get_insights(client, seeded["token"], str(uuid.uuid4()))
    assert other.status_code == unknown.status_code == 404
    assert other.json() == unknown.json()


# ===========================================================================
# 3. UUID validation
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_id", BAD_IDS)
async def test_insights_malformed_id_returns_422_not_500(
    client: AsyncClient, seeded, bad_id
):
    resp = await _get_insights(client, seeded["token"], bad_id)
    assert resp.status_code == 422, f"{bad_id} -> {resp.status_code}: {resp.text}"
    assert resp.status_code != 500
    text = resp.text.lower()
    for marker in _LEAK_MARKERS:
        assert marker not in text, f"internal detail leaked: {resp.text}"


# ===========================================================================
# 4. Response contract
# ===========================================================================


@pytest.mark.asyncio
async def test_insights_response_contract(client: AsyncClient, seeded):
    resp = await _get_insights(client, seeded["token"], seeded["main_id"])
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert set(body) == {
        "documentId",
        "name",
        "fileType",
        "fileSize",
        "status",
        "embeddingStatus",
        "createdAt",
        "chunkCount",
        "structure",
        "embedding",
        "graph",
        "pages",
        "provenance",
    }
    assert set(body["structure"]) == {
        "totalChunks",
        "pagesRepresented",
        "pageCount",
        "sectionsRepresented",
        "headingPathsRepresented",
        "elementTypeCounts",
        "avgChunkLength",
        "avgTokenCount",
        "totalTokenCount",
    }
    assert set(body["embedding"]) == {"embeddedChunkCount", "coverage"}
    assert set(body["graph"]) == {"nodeCount", "edgeCount", "relationCounts", "coverage"}
    assert set(body["pages"]) == {
        "recorded",
        "pagesTotal",
        "nativePageCount",
        "ocrPageCount",
        "unaccountedPageCount",
        "ocrPages",
        "unaccountedPages",
        "spatialLayouts",
    }
    assert set(body["provenance"]) == {
        "parserVersion",
        "chunkerVersion",
        "embeddingModel",
    }

    # Identity fields mirror the stored document.
    assert body["documentId"] == seeded["main_id"]
    assert body["name"] == "insights-main.pdf"
    assert body["fileType"] == "pdf"
    assert body["chunkCount"] == len(MAIN_CHUNKS)
    # stored_path is never part of the contract.
    assert "stored_path" not in resp.text


# ===========================================================================
# 5. Structure metrics (values derived from the fixture)
# ===========================================================================


@pytest.mark.asyncio
async def test_structure_metrics_match_fixture(client: AsyncClient, seeded):
    body = (await _get_insights(client, seeded["token"], seeded["main_id"])).json()
    assert body["structure"] == _expected_structure()


@pytest.mark.asyncio
async def test_structure_averages_are_derived_not_defaulted(
    client: AsyncClient, seeded
):
    """The averages must equal the arithmetic mean of the exact fixture data."""
    body = (await _get_insights(client, seeded["token"], seeded["main_id"])).json()
    structure = body["structure"]

    lengths = [len(c["content"]) for c in MAIN_CHUNKS]
    assert structure["avgChunkLength"] == round(sum(lengths) / len(lengths), 2)

    tokens = [c["token_count"] for c in MAIN_CHUNKS if c["token_count"] is not None]
    assert structure["avgTokenCount"] == round(sum(tokens) / len(tokens), 2)
    assert structure["totalTokenCount"] == sum(tokens)


# ===========================================================================
# 6. Page-count semantics
# ===========================================================================


@pytest.mark.asyncio
async def test_pdf_page_count_is_max_page(client: AsyncClient, seeded):
    body = (await _get_insights(client, seeded["token"], seeded["main_id"])).json()
    structure = body["structure"]
    assert structure["pageCount"] == max(c["page"] for c in MAIN_CHUNKS)
    assert structure["pagesRepresented"] == len({c["page"] for c in MAIN_CHUNKS})


@pytest.mark.asyncio
async def test_non_paged_document_has_null_page_count(client: AsyncClient, seeded):
    body = (await _get_insights(client, seeded["token"], seeded["txt_id"])).json()
    assert body["fileType"] == "txt"
    assert body["structure"]["pageCount"] is None
    assert body["structure"]["pagesRepresented"] == 0


# ===========================================================================
# 7. Element type behavior
# ===========================================================================


@pytest.mark.asyncio
async def test_element_type_counts_exclude_legacy_null(client: AsyncClient, seeded):
    body = (await _get_insights(client, seeded["token"], seeded["main_id"])).json()
    counts = body["structure"]["elementTypeCounts"]

    expected = Counter(
        c["element_type"] for c in MAIN_CHUNKS if c["element_type"] is not None
    )
    assert counts == dict(expected)
    # The legacy NULL chunk is not assigned a fabricated category, so the
    # categorised total is strictly smaller than the chunk total.
    assert sum(counts.values()) == len(MAIN_CHUNKS) - 1
    assert None not in counts


# ===========================================================================
# 8. Embedding metrics
# ===========================================================================


@pytest.mark.asyncio
async def test_embedding_metrics_mixed(client: AsyncClient, seeded):
    body = (await _get_insights(client, seeded["token"], seeded["main_id"])).json()
    emb = body["embedding"]
    assert emb["embeddedChunkCount"] == len(EMBEDDED_INDICES)
    assert emb["coverage"] == round(len(EMBEDDED_INDICES) / len(MAIN_CHUNKS), 4)


@pytest.mark.asyncio
async def test_embedding_metrics_zero_chunks(client: AsyncClient, seeded):
    body = (await _get_insights(client, seeded["token"], seeded["empty_id"])).json()
    assert body["embedding"]["embeddedChunkCount"] == 0
    assert body["embedding"]["coverage"] == 0.0


# ===========================================================================
# 9. Graph metrics
# ===========================================================================


@pytest.mark.asyncio
async def test_graph_metrics_match_fixture(client: AsyncClient, seeded):
    body = (await _get_insights(client, seeded["token"], seeded["main_id"])).json()
    assert body["graph"] == _expected_graph()
    # At least two relation types are represented.
    assert len(body["graph"]["relationCounts"]) >= 2


@pytest.mark.asyncio
async def test_graph_metrics_without_edges(client: AsyncClient, seeded):
    body = (await _get_insights(client, seeded["token"], seeded["nograph_id"])).json()
    graph = body["graph"]
    assert graph["edgeCount"] == 0
    assert graph["relationCounts"] == {}
    assert graph["nodeCount"] == 0
    assert graph["coverage"] == 0.0


# ===========================================================================
# 10. Provenance
# ===========================================================================


@pytest.mark.asyncio
async def test_provenance_exposes_stored_values(client: AsyncClient, seeded):
    body = (await _get_insights(client, seeded["token"], seeded["main_id"])).json()
    assert body["provenance"] == {
        "parserVersion": MAIN_PROVENANCE["parser_version"],
        "chunkerVersion": MAIN_PROVENANCE["chunker_version"],
        "embeddingModel": MAIN_PROVENANCE["embedding_model"],
    }


@pytest.mark.asyncio
async def test_provenance_is_null_not_invented_for_unset_document(
    client: AsyncClient, seeded
):
    """The TXT doc has no recorded provenance; the endpoint must not invent it."""
    body = (await _get_insights(client, seeded["token"], seeded["txt_id"])).json()
    assert body["provenance"] == {
        "parserVersion": None,
        "chunkerVersion": None,
        "embeddingModel": None,
    }


# ===========================================================================
# 10b. Per-page extraction provenance
# ===========================================================================


@pytest.mark.asyncio
async def test_page_extraction_is_not_recorded_for_a_legacy_document(
    client: AsyncClient, seeded
):
    """A document with no page rows reports ``recorded: false``, not zero pages.

    The fixture's documents are created directly in the database, so they never
    went through the extraction pipeline and carry no per-page rows.  The
    endpoint must say so instead of presenting 0 pages as a measured fact.
    """
    body = (await _get_insights(client, seeded["token"], seeded["main_id"])).json()
    assert body["pages"] == {
        "recorded": False,
        "pagesTotal": 0,
        "nativePageCount": 0,
        "ocrPageCount": 0,
        "unaccountedPageCount": 0,
        "ocrPages": [],
        "unaccountedPages": [],
        "spatialLayouts": [],
    }


@pytest.mark.asyncio
async def test_page_extraction_reports_recorded_pages(
    client: AsyncClient, seeded, db_session
):
    """Recorded rows are reported per page: how it was read and how confidently."""
    from documents.models import DocumentPageExtraction

    for row in (
        DocumentPageExtraction(
            id=uuid.uuid4(),
            document_id=uuid.UUID(seeded["main_id"]),
            page_number=1,
            method="native",
            text_chars=120,
        ),
        DocumentPageExtraction(
            id=uuid.uuid4(),
            document_id=uuid.UUID(seeded["main_id"]),
            page_number=2,
            method="ocr",
            text_chars=95,
            ocr_engine="rapidocr",
            ocr_engine_version="3.10.0",
            ocr_confidence=0.98765,
            ocr_rotation=180,
            ocr_seconds=2.5,
        ),
        DocumentPageExtraction(
            id=uuid.uuid4(),
            document_id=uuid.UUID(seeded["main_id"]),
            page_number=3,
            method="none",
            text_chars=0,
            failure_reason="ocr_failed",
        ),
    ):
        db_session.add(row)
    await db_session.commit()

    pages = (await _get_insights(client, seeded["token"], seeded["main_id"])).json()[
        "pages"
    ]

    assert pages["recorded"] is True
    assert pages["pagesTotal"] == 3
    assert pages["nativePageCount"] == 1
    assert pages["ocrPageCount"] == 1
    assert pages["unaccountedPageCount"] == 1
    assert pages["ocrPages"] == [
        {
            "pageNumber": 2,
            "textChars": 95,
            "ocrEngine": "rapidocr",
            "ocrEngineVersion": "3.10.0",
            "ocrConfidence": 0.9877,
            "ocrRotation": 180,
            "ocrSeconds": 2.5,
        }
    ]
    assert pages["unaccountedPages"] == [
        {"pageNumber": 3, "failureReason": "ocr_failed"}
    ]


# ===========================================================================
# 11. Empty document
# ===========================================================================


@pytest.mark.asyncio
async def test_empty_document_returns_zeroed_metrics(client: AsyncClient, seeded):
    resp = await _get_insights(client, seeded["token"], seeded["empty_id"])
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["chunkCount"] == 0
    structure = body["structure"]
    assert structure["totalChunks"] == 0
    assert structure["pagesRepresented"] == 0
    assert structure["pageCount"] is None
    assert structure["sectionsRepresented"] == 0
    assert structure["headingPathsRepresented"] == 0
    assert structure["elementTypeCounts"] == {}
    assert structure["avgChunkLength"] is None
    assert structure["avgTokenCount"] is None
    assert structure["totalTokenCount"] == 0

    assert body["embedding"] == {"embeddedChunkCount": 0, "coverage": 0.0}
    assert body["graph"] == {
        "nodeCount": 0,
        "edgeCount": 0,
        "relationCounts": {},
        "coverage": 0.0,
    }


# ===========================================================================
# 12. Determinism
# ===========================================================================


@pytest.mark.asyncio
async def test_insights_are_deterministic(client: AsyncClient, seeded):
    first = (await _get_insights(client, seeded["token"], seeded["main_id"])).json()
    second = (await _get_insights(client, seeded["token"], seeded["main_id"])).json()
    assert first == second


# ===========================================================================
# 13. Content is aggregated, not returned
# ===========================================================================


@pytest.mark.asyncio
async def test_insights_do_not_return_chunk_content(client: AsyncClient, seeded):
    """The payload is aggregate statistics only — no chunk content is exposed."""
    body = (await _get_insights(client, seeded["token"], seeded["main_id"])).json()
    assert "chunks" not in body
    assert "content" not in body["structure"]
    # None of the fixture's raw chunk content appears anywhere in the response.
    for chunk in MAIN_CHUNKS:
        assert chunk["content"] not in str(body)
