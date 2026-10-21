"""Small deterministic reachability fixture for the structure-element path.

Purpose: prove **technical reachability** only — that a persisted structure
element can become a retrieval candidate, receive a legitimate rank
contribution, enter the final top-k, alter the final candidate ordering and
survive into the QA context.  This is NOT a research result: no retrieval or
answer-quality improvement is claimed or measured here.

Fixture (one document, three sections, one page):

* ``Instrument Calibration`` (H1) — the only section naming a query term
* ``Rig Setup`` (H2, child) — reachable only through the parent/child walk
* ruled table ``Kestrel frame | reference rig`` (child of ``Rig Setup``) —
  the target structural element whose content represents the answer
* ``Field Supplies`` (H1) + paragraph — structural distractors that must not
  become candidates

plus one **declared** irrelevant high-ranked semantic candidate (the same
test-double pattern as ``test_graph_rag_flow``): it is an input to ranking,
not a measured pgvector result.

The test records the full trace (semantic candidates → structural candidates →
fused candidates with rank contributions → final top-k → QA supplied evidence)
and asserts its exact deterministic values, so the evaluation report can quote
verified numbers.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from chat.rag import (
    RETRIEVAL_SEMANTIC,
    RRF_K,
    RRF_SEMANTIC_WEIGHT,
    RRF_STRUCTURAL_WEIGHT,
    SourceChunk,
    build_qa_context,
    fuse_dual_path,
    retrieve_dual_path,
    retrieve_structural_element_candidates,
)
from documents.parser import parse_pdf
from documents.structure import replace_document_structure
from sqlalchemy import select
from graph.models import DocumentStructureElement
from tests.fixtures.graph_data import create_document_with_chunks
from tests.fixtures.pdf_layout import add_text, draw_ruled_table, new_pdf, new_page

QUERY = (
    "What is the Kestrel frame calibrated against in the Instrument "
    "Calibration section?"
)

TABLE_CONTENT = "Kestrel frame | reference rig"
PARAGRAPH_CONTENT = "The carrying case is made of nylon."

# (y, kind, payload) — drawn top-to-bottom at fixed coordinates.
LAYOUT = [
    (60, "text", ("Instrument Calibration", 16)),
    (110, "text", ("Rig Setup", 13)),
    (155, "table", [["Kestrel frame", "reference rig"]]),
    (260, "text", ("Field Supplies", 16)),
    (305, "text", (PARAGRAPH_CONTENT, 10)),
]


def build_fixture_pdf() -> bytes:
    """One-page PDF with real headings and a real ruled table."""
    doc = new_pdf()
    page = new_page(doc)
    for y, kind, payload in LAYOUT:
        if kind == "text":
            text, size = payload
            add_text(page, 50, y, text, size=size)
        else:
            draw_ruled_table(page, 50, y, payload)
    data = doc.tobytes()
    doc.close()
    return data


async def persist_fixture(db, user, *, name: str = "reachability.pdf"):
    """Real PDF -> real parser -> real structure persister -> document row."""
    pdf_bytes = build_fixture_pdf()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
        handle.write(pdf_bytes)
        tmp = Path(handle.name)
    try:
        parsed = parse_pdf(tmp)
    finally:
        os.unlink(tmp)

    doc, _ = await create_document_with_chunks(db, user.id, name=name, chunks=[])
    await replace_document_structure(db, doc.id, parsed)

    rows = (
        (
            await db.execute(
                select(DocumentStructureElement)
                .where(DocumentStructureElement.document_id == doc.id)
                .order_by(
                    DocumentStructureElement.sequence_index.asc(),
                    DocumentStructureElement.id.asc(),
                )
            )
        )
        .scalars()
        .all()
    )
    return doc, parsed, rows


# A canonical UUID that is never seeded into the structure: the declared
# semantic candidate is fed back into the graph expansion, so its chunk id must
# be a value the real database accepts (PostgreSQL rejects a non-UUID there).
SEMANTIC_ONLY_CHUNK_ID = "6f1e2c34-0000-4000-8000-000000000001"


def declared_semantic(document_id: str) -> SourceChunk:
    """Declared irrelevant high-ranked semantic candidate (test double)."""
    return SourceChunk(
        chunk_id=SEMANTIC_ONLY_CHUNK_ID,
        content="The vermilion coating cures in six hours.",
        score=0.93,
        document_id=document_id,
        document_name="reachability.pdf",
        page=1,
        retrieval_path=RETRIEVAL_SEMANTIC,
    )


class TestStructuralReachabilityFixture:
    async def test_recorded_reachability_trace(self, db_session, create_test_user):
        user = await create_test_user(email="reachability@test.com")
        doc, _parsed, rows = await persist_fixture(db_session, user)

        # --- Parser correction is observable end-to-end --------------------
        tables = [row for row in rows if row.element_type == "table"]
        assert len(tables) == 1
        assert tables[0].heading_path == ["Instrument Calibration", "Rig Setup"], (
            "the table was attributed to the heading at its read position"
        )

        semantic = [declared_semantic(str(doc.id))]
        structural = await retrieve_structural_element_candidates(
            db_session, str(user.id), QUERY
        )
        fused = await retrieve_dual_path(
            db_session,
            str(user.id),
            QUERY,
            top_k=5,
            semantic_chunks=semantic,
        )
        context = build_qa_context(fused, QUERY)

        # --- Recorded trace -----------------------------------------------
        trace = {
            "semantic_candidates": [
                {"chunk_id": c.chunk_id, "score": c.score} for c in semantic
            ],
            "structural_candidates": [
                {
                    "chunk_id": c.chunk_id,
                    "element_type": c.element_type,
                    "structural_hops": c.structural_hops,
                    "structural_relation": c.structural_relation,
                    "structural_score": c.structural_score,
                    "evidence_kind": c.evidence_kind,
                    "score": c.score,
                }
                for c in structural
            ],
            "fused_candidates": [
                {
                    "rank": rank,
                    "chunk_id": c.chunk_id,
                    "fusion_score": c.fusion_score,
                    "retrieval_path": c.retrieval_path,
                }
                for rank, c in enumerate(fused, start=1)
            ],
            "rank_contributions": {
                "semantic_rank_1": round(RRF_SEMANTIC_WEIGHT / (RRF_K + 1), 8),
                "structural_rank_1": round(RRF_STRUCTURAL_WEIGHT / (RRF_K + 1), 8),
                "structural_rank_2": round(RRF_STRUCTURAL_WEIGHT / (RRF_K + 2), 8),
                "structural_rank_3": round(RRF_STRUCTURAL_WEIGHT / (RRF_K + 3), 8),
            },
            "final_top_k": [c.chunk_id for c in fused],
            "qa_supplied_evidence": list(context.included_ids),
        }
        print("\nREACHABILITY TRACE:", trace)

        # --- Structural candidates ---------------------------------------
        section = next(r for r in rows if r.content == "Instrument Calibration")
        subsection = next(r for r in rows if r.content == "Rig Setup")
        target = tables[0]

        assert [c.chunk_id for c in structural] == [
            f"structure:{section.id}",
            f"structure:{subsection.id}",
            f"structure:{target.id}",
        ]
        assert [c.structural_hops for c in structural] == [0, 1, 2]
        assert [c.structural_score for c in structural] == [1.0, 0.5, 0.333333]
        for candidate in structural:
            assert candidate.score == 0.0
            assert candidate.evidence_kind == "structure_element"
            assert candidate.retrieval_path == "structural"

        # --- Rank contributions are the declared RRF contributions --------
        assert fused[0].chunk_id == SEMANTIC_ONLY_CHUNK_ID
        assert fused[0].fusion_score == round(
            RRF_SEMANTIC_WEIGHT / (RRF_K + 1), 8
        )
        for rank, candidate in enumerate(fused[1:], start=1):
            assert candidate.fusion_score == round(
                RRF_STRUCTURAL_WEIGHT / (RRF_K + rank), 8
            )

        # --- Final top-k contains the structural target -------------------
        assert [c.chunk_id for c in fused] == [
            SEMANTIC_ONLY_CHUNK_ID,
            f"structure:{section.id}",
            f"structure:{subsection.id}",
            f"structure:{target.id}",
        ]

        # --- QA supplied evidence ----------------------------------------
        assert set(context.included_ids) == {c.chunk_id for c in fused}
        assert TABLE_CONTENT in str(context)
        assert PARAGRAPH_CONTENT not in str(context), (
            "an unmatched section's content must not enter the ranked context"
        )

    async def test_semantic_only_baseline_omits_the_structural_target(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="reachability-base@test.com")
        doc, _parsed, rows = await persist_fixture(db_session, user, name="base.pdf")
        semantic = [declared_semantic(str(doc.id))]

        semantic_only = fuse_dual_path(semantic, [], top_k=5)

        assert [c.chunk_id for c in semantic_only] == [SEMANTIC_ONLY_CHUNK_ID]
        target = next(r for r in rows if r.element_type == "table")
        assert f"structure:{target.id}" not in {c.chunk_id for c in semantic_only}

    async def test_trace_is_reproducible(self, db_session, create_test_user):
        user = await create_test_user(email="reachability-repeat@test.com")
        doc, _parsed, _rows = await persist_fixture(
            db_session, user, name="repeat.pdf"
        )
        semantic = [declared_semantic(str(doc.id))]

        first = await retrieve_dual_path(
            db_session, str(user.id), QUERY, top_k=5, semantic_chunks=semantic
        )
        second = await retrieve_dual_path(
            db_session, str(user.id), QUERY, top_k=5, semantic_chunks=semantic
        )

        assert [(c.chunk_id, c.fusion_score) for c in first] == [
            (c.chunk_id, c.fusion_score) for c in second
        ]
