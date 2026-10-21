"""Phase 3 at the HTTP boundary: table-row evidence in ``/api/chat/ask``.

The evidence-band tests (``test_table_evidence_bands.py``) prove the selection and
the context order through the adapters.  These tests prove the same facts through
the interface the product actually exposes: a real ``POST /api/chat/ask`` over the
real Brain chain, with only the embedding model and the QA model stubbed (the
project's existing convention — pgvector's ``<=>`` does not exist on SQLite and the
QA weights are not needed to inspect provenance).

Asserted here:

* the response carries a source with ``evidenceKind = "table_row"`` and truthful
  ``tableElementId`` / ``rowIndex`` / ``headerRepeated`` / ``page`` / ``section``;
* that source carries no similarity and no fusion score (it never entered RRF);
* the row sits after every chunk-level source and before the element tail;
* the text handed to the QA model contains the row's fact;
* with ``DOCUMIND_TABLE_EVIDENCE`` unset (the default) none of that happens.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from brain.types import QaResult
from chat.rag import EVIDENCE_KIND_TABLE_ROW, TABLE_EVIDENCE_ENV, SourceChunk
from documents.parser import parse_pdf
from documents.structure import replace_document_structure
from tests.fixtures.graph_data import create_document_with_chunks
from tests.fixtures.pdf_layout import add_text, draw_ruled_table, new_page, new_pdf

ASK_URL = "/api/chat/ask"
PASSWORD = "Pass123!"

#: Names a table dimension ("service interval") and a row label ("gyro unit").
QUESTION = "What service interval does the maintenance schedule give for the gyro unit?"

HEADER = ["Module", "Service Interval", "Operating Range"]
BODY_ROWS = [
    ["Gyro Unit", "250 h", "0-80 m"],
    ["Spare Rail", "1000 h", "19.5-26.0 V"],
]
SECTION = "Maintenance Schedule"


def _pdf_bytes() -> bytes:
    doc = new_pdf()
    page = new_page(doc)
    add_text(page, 50, 60, SECTION, size=16)
    draw_ruled_table(page, 50, 110, [HEADER, *BODY_ROWS])
    data = doc.tobytes()
    doc.close()
    return data


async def _seed(db_session, user, *, name: str = "table-api.pdf"):
    """A document whose chunk section answers the question and whose rows exist."""
    doc, chunks = await create_document_with_chunks(
        db_session,
        user.id,
        name=name,
        chunks=[
            {
                "index": 0,
                "content": "The maintenance schedule records each interval.",
                "page": 1,
                "heading_path": [SECTION],
                "section": SECTION,
            }
        ],
    )
    await replace_document_structure(db_session, doc.id, parse_pdf(_pdf_bytes()))
    await db_session.commit()
    return doc, chunks


def _declared_hit(doc, chunk) -> SourceChunk:
    return SourceChunk(
        chunk_id=str(chunk.id),
        content=chunk.content,
        score=0.81,
        document_id=str(doc.id),
        document_name=doc.name,
        page=chunk.page,
        heading_path=(SECTION,),
        section=SECTION,
        retrieval_path="semantic",
    )


async def _token(client, email: str) -> dict:
    login = await client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _ask(client, headers, *, question: str = QUESTION, qa_mock):
    # The semantic path is declared, not executed: pgvector's ``<=>`` operator does
    # not exist on the SQLite test database (the established convention in this
    # suite).  Everything else — structural retrieval, the element tail, the gated
    # table band, the context builder and the route — is the real production code.
    with patch(
        "brain.adapters.retrieve_chunks", new=AsyncMock(return_value=[qa_mock.hit])
    ), patch("brain.adapters.qa_adapter", new=qa_mock.adapter):
        return await client.post(
            ASK_URL, json={"question": question, "topK": 5}, headers=headers
        )


class _QaSpy:
    """Stub QA model that records the exact text it was asked about."""

    def __init__(self, hit: SourceChunk, answer: str = "250 h"):
        self.hit = hit
        self.answer = answer
        self.calls: list[dict] = []

    async def adapter(self, **kwargs):
        self.calls.append(kwargs)
        return QaResult(
            answer=self.answer,
            score=0.9,
            start=0,
            end=len(self.answer),
        )


class TestTableEvidenceInAskResponse:
    async def test_enabled_band_is_reported_with_true_provenance(
        self, client, db_session, create_test_user, monkeypatch
    ):
        monkeypatch.setenv(TABLE_EVIDENCE_ENV, "1")
        email = "table-api-on@test.com"
        user = await create_test_user(email=email, password=PASSWORD)
        doc, chunks = await _seed(db_session, user)
        headers = await _token(client, email)
        spy = _QaSpy(_declared_hit(doc, chunks[0]))

        resp = await _ask(client, headers, qa_mock=spy)

        assert resp.status_code == 200, resp.text
        body = resp.json()
        sources = body["sources"]
        assert sources, "fixture assumption: evidence was returned"

        rows = [s for s in sources if s.get("evidenceKind") == EVIDENCE_KIND_TABLE_ROW]
        assert len(rows) == 1, f"expected exactly one row source, got {len(rows)}"
        row = rows[0]

        # Identity and provenance point back at the persisted row.
        assert row["tableElementId"]
        assert row["rowIndex"] == 1  # header row is 0
        assert row["headerRepeated"] is True
        assert row["page"] == 1
        assert row["section"] == SECTION
        assert row["documentId"] == str(doc.id)
        assert row["documentName"] == doc.name
        # A row is structural evidence: no similarity, and never an RRF score.
        assert row["retrievalPath"] == "structural"
        assert row["score"] == 0.0
        assert row["fusionScore"] is None
        # Faithful content: the persisted cells, header repeated, nothing invented.
        assert "Gyro Unit" in row["content"]
        assert "250 h" in row["content"]
        assert f"{HEADER[0]} | {HEADER[1]} | {HEADER[2]}" in row["content"]

        # Band order: after every chunk-level source, before the element tail.
        kinds = [s.get("evidenceKind") for s in sources]
        chunk_positions = [i for i, kind in enumerate(kinds) if kind == "chunk"]
        table_position = kinds.index(EVIDENCE_KIND_TABLE_ROW)
        assert chunk_positions, "fixture assumption: chunk evidence is present"
        assert table_position > max(chunk_positions), "the row displaced ranked chunks"

        # The ranked chunk evidence is untouched and still reported first.  (It is
        # also a structural seed here, so the fused path reports it hybrid — an
        # honest label, not a semantic-only claim.)
        assert sources[0]["evidenceKind"] == "chunk"
        assert sources[0]["score"] == pytest.approx(0.81)
        reliability = body["reliability"]
        assert reliability["sourceCount"] == len(sources), (
            "reliability must report every source it received"
        )
        assert (
            reliability["semanticSourceCount"]
            + reliability["structuralSourceCount"]
            + reliability["hybridSourceCount"]
        ) == reliability["sourceCount"]

        # The QA model's input actually carried the row: that is what makes the
        # band meaningful rather than decorative.
        assert spy.calls, "the QA model was never reached"
        assert "250 h" in spy.calls[0]["context"]

        # Reliability Center agrees with the response, source for source.
        last = await client.get("/api/reliability/last-query", headers=headers)
        assert last.status_code == 200, last.text
        last_body = last.json()
        assert {s["id"] for s in last_body["sources"]} == {
            s["chunkId"] for s in sources
        }
        reported = [
            s for s in last_body["sources"] if s.get("evidenceKind") == EVIDENCE_KIND_TABLE_ROW
        ]
        assert len(reported) == 1
        assert reported[0]["id"] == row["chunkId"]
        # Phase 5: the exact table-row provenance must survive persistence and
        # the reliability endpoint, value for value — never re-derived.
        assert reported[0]["tableElementId"] == row["tableElementId"]
        assert reported[0]["rowIndex"] == row["rowIndex"] == 1
        assert reported[0]["headerRepeated"] is True
        assert reported[0]["page"] == row["page"] == 1
        assert reported[0]["section"] == row["section"] == SECTION
        assert reported[0]["retrievalPath"] == "structural"
        assert last_body["tableRowSourceCount"] == 1
        # The row is structural by path and counted separately, so the
        # element + table-row evidence fits inside the structural bucket.
        assert (
            last_body["structuralSourceCount"]
            >= last_body["structuralElementSourceCount"]
            + last_body["tableRowSourceCount"]
        )

    async def test_default_switch_off_adds_nothing_and_the_band_is_additive(
        self, client, db_session, create_test_user, monkeypatch
    ):
        """Off is the default; turning it on adds the row and changes nothing else.

        The comparison is made on the reported sources, not on the raw context text:
        the document's aggregate ``table`` element is still part of the unranked
        element tail (unchanged Phase 2 behaviour), so its text legitimately contains
        the same table words either way.  What must not change is the evidence set.
        """
        monkeypatch.delenv(TABLE_EVIDENCE_ENV, raising=False)
        email = "table-api-off@test.com"
        user = await create_test_user(email=email, password=PASSWORD)
        doc, chunks = await _seed(db_session, user, name="table-api-off.pdf")
        headers = await _token(client, email)

        spy_off = _QaSpy(_declared_hit(doc, chunks[0]))
        off = await _ask(client, headers, qa_mock=spy_off)

        assert off.status_code == 200, off.text
        off_sources = off.json()["sources"]
        assert off_sources, "fixture assumption: evidence was returned"
        assert not [
            s for s in off_sources if s.get("evidenceKind") == EVIDENCE_KIND_TABLE_ROW
        ]

        monkeypatch.setenv(TABLE_EVIDENCE_ENV, "1")
        spy_on = _QaSpy(_declared_hit(doc, chunks[0]))
        on = await _ask(client, headers, qa_mock=spy_on)

        assert on.status_code == 200, on.text
        on_sources = on.json()["sources"]
        rows = [
            s for s in on_sources if s.get("evidenceKind") == EVIDENCE_KIND_TABLE_ROW
        ]

        assert len(rows) == 1
        assert [
            s for s in on_sources if s.get("evidenceKind") != EVIDENCE_KIND_TABLE_ROW
        ] == off_sources, "the table band was not purely additive"
        assert spy_off.calls and spy_on.calls, "the QA model was never reached"
        # The row's fact reaches the model's input only when the feature is on.
        assert rows[0]["content"] in spy_on.calls[0]["context"]
        assert spy_on.calls[0]["context"] != spy_off.calls[0]["context"]

    async def test_feature_can_be_switched_off_explicitly(
        self, client, db_session, create_test_user, monkeypatch
    ):
        monkeypatch.setenv(TABLE_EVIDENCE_ENV, "0")
        email = "table-api-explicit-off@test.com"
        user = await create_test_user(email=email, password=PASSWORD)
        doc, chunks = await _seed(db_session, user, name="table-api-explicit-off.pdf")
        headers = await _token(client, email)
        spy = _QaSpy(_declared_hit(doc, chunks[0]))

        resp = await _ask(client, headers, qa_mock=spy)

        assert resp.status_code == 200, resp.text
        assert not [
            s
            for s in resp.json()["sources"]
            if s.get("evidenceKind") == EVIDENCE_KIND_TABLE_ROW
        ]
