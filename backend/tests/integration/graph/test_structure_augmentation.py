"""Characterization tests for the structure-element *augmentation* selection.

Context — the production limitation these tests make visible
------------------------------------------------------------

``brain.adapters._augment_with_structure`` appends structure elements to the
retrieved chunk stream that QA later receives.  Selection is **document order
only**: ``graph.evidence.collect_document_structure_evidence`` orders by
``sequence_index`` ASC, ``id`` ASC and applies ``per_document_limit``
(``STRUCTURE_EVIDENCE_PER_DOCUMENT`` = 20).  The augmentation function passes no
question/query signal, so which elements are offered to QA cannot depend on what
was asked.

Consequence: an element that sits later than the first 20 in document order is
never appended, even when it is a legitimate retrieval result.  A teacher-demo
audit hit exactly this — a persisted ``table`` element (sequence index 34, on
page 4) was generated and could be returned as a structure-element *candidate*
by the ranked dual path, yet it was the 35th element in document order and so
was absent from the augmented stream.

A relevance-first selection inside ``_augment_with_structure`` (seeding from the
existing ``chat.rag.retrieve_structural_element_candidates`` stream, with
document order kept as a deterministic fill under the same per-document bound)
was implemented, measured on the real demo document, and **reverted** because it
did not achieve reachability and regressed an unrelated answer:

* the late element's own content was ~230 tokens against a 362-token QA context
  budget that the five fused chunks already consumed ~266 tokens of;
* reordering by the available relevance signals moved the element from stream
  position 10 to position 8 — still outside the budget;
* a controlled A/B over the five demo questions left four unchanged and
  regressed one (a correct answer was replaced by an incorrect one), while RRF
  weights were untouched.

So the behaviour pinned below is the *current production* behaviour, not the
desired behaviour.  These tests exist so the limitation is explicit and in-repo:
a future fix must consciously update them rather than silently change selection.
No retrieval- or answer-quality improvement is claimed or measured here.

Fixture (deliberately generic — no product/demo vocabulary):

* one ``section`` element at sequence 0;
* ``FILLER_COUNT`` unrelated ``paragraph`` elements at sequences 1..33, i.e.
  *first* in document order;
* a ``table`` element at sequence 34 — the late element that cannot be reached.

"""

from __future__ import annotations

import inspect
import uuid

from sqlalchemy import select

from chat.rag import (
    RRF_K,
    RRF_SEMANTIC_WEIGHT,
    RRF_STRUCTURAL_WEIGHT,
    SourceChunk,
    fuse_dual_path,
)
from graph.models import DocumentStructureElement
from tests.fixtures.graph_data import create_document_with_chunks

QUESTION = "What does the Boiler Manual state about the pressure limit?"
OTHER_QUESTION = "What annual leave entitlement is described in clause four?"

TABLE_SEQUENCE = 34
TABLE_PAGE = 7
TABLE_CONTENT = "Boiler pressure | 12 bar | Section 7"
FILLER_COUNT = 33

ELEMENT_CHUNK_PREFIX = "structure:"


async def _add_element(
    db,
    doc,
    *,
    sequence: int,
    element_type: str,
    content: str,
    heading_path: list[str],
    parent_id=None,
    page: int = 1,
):
    """Persist one structure element (no parser involved — deterministic)."""
    row = DocumentStructureElement(
        id=uuid.uuid4(),
        document_id=doc.id,
        parent_id=parent_id,
        element_type=element_type,
        sequence_index=sequence,
        page_number=page,
        heading_level=1 if element_type == "section" else None,
        heading_path=list(heading_path),
        content=content,
        parser_version="test-parser-1.0",
    )
    db.add(row)
    await db.flush()
    return row


async def _seed_document(db, user, *, name: str):
    """One document: an early section, many earlier distractors, a late table.

    Returns ``(doc, chunk_rows, section_row, table_row)``.
    """
    doc, chunk_rows = await create_document_with_chunks(
        db,
        user.id,
        name=name,
        chunks=[
            {
                "index": 0,
                "content": "Boiler Manual: the boiler pressure limit is 12 bar.",
                "page": 1,
                "heading_path": ["Boiler Manual"],
                "section": "Boiler Manual",
            }
        ],
    )

    section = await _add_element(
        db,
        doc,
        sequence=0,
        element_type="section",
        content="Boiler Manual",
        heading_path=["Boiler Manual"],
        page=1,
    )

    # Unrelated elements that occur FIRST in document order.
    for offset in range(FILLER_COUNT):
        await _add_element(
            db,
            doc,
            sequence=1 + offset,
            element_type="paragraph",
            content=f"Appendix note {offset}: unrelated boilerplate.",
            heading_path=["Appendix"],
            page=1,
        )

    # The late element, beyond the per-document selection window.
    table = await _add_element(
        db,
        doc,
        sequence=TABLE_SEQUENCE,
        element_type="table",
        content=TABLE_CONTENT,
        heading_path=["Boiler Manual"],
        parent_id=section.id,
        page=TABLE_PAGE,
    )

    await db.commit()
    return doc, chunk_rows, section, table


def _semantic_chunk_for(doc, chunk_row) -> SourceChunk:
    return SourceChunk(
        chunk_id=str(chunk_row.id),
        content=chunk_row.content,
        score=0.71,
        document_id=str(doc.id),
        document_name=doc.name,
        page=chunk_row.page,
    )


def _element_ids(chunks: list[SourceChunk]) -> list[str]:
    return [c.chunk_id for c in chunks if c.chunk_id.startswith(ELEMENT_CHUNK_PREFIX)]


async def _first_n_element_ids(db, document_id, n: int) -> list[str]:
    """The current production selection rule, expressed directly in SQL."""
    rows = (
        await db.execute(
            select(DocumentStructureElement.id)
            .where(DocumentStructureElement.document_id == document_id)
            .order_by(
                DocumentStructureElement.sequence_index.asc(),
                DocumentStructureElement.id.asc(),
            )
            .limit(n)
        )
    ).scalars().all()
    return [f"{ELEMENT_CHUNK_PREFIX}{row}" for row in rows]


class TestDocumentOrderSelection:
    """What the current augmentation actually selects."""

    async def test_late_element_is_not_reachable(self, db_session, create_test_user):
        """KNOWN LIMITATION: the sequence-34 table is not offered to QA."""
        from brain.adapters import _augment_with_structure

        user = await create_test_user(email="aug-late@test.com")
        doc, chunk_rows, _section, table = await _seed_document(
            db_session, user, name="late.pdf"
        )

        augmented = await _augment_with_structure(
            db_session, [_semantic_chunk_for(doc, chunk_rows[0])]
        )

        assert f"{ELEMENT_CHUNK_PREFIX}{table.id}" not in set(_element_ids(augmented)), (
            "the late element is now reachable — this test pins the documented "
            "limitation and must be updated together with any selection change"
        )

    async def test_selected_elements_are_the_first_n_in_document_order(
        self, db_session, create_test_user
    ):
        """Selection is the first ``STRUCTURE_EVIDENCE_PER_DOCUMENT`` elements."""
        from brain.adapters import (
            STRUCTURE_EVIDENCE_PER_DOCUMENT,
            _augment_with_structure,
        )

        user = await create_test_user(email="aug-firstn@test.com")
        doc, chunk_rows, section, table = await _seed_document(
            db_session, user, name="firstn.pdf"
        )

        augmented = await _augment_with_structure(
            db_session, [_semantic_chunk_for(doc, chunk_rows[0])]
        )
        element_ids = _element_ids(augmented)

        assert element_ids == await _first_n_element_ids(
            db_session, doc.id, STRUCTURE_EVIDENCE_PER_DOCUMENT
        )
        assert len(element_ids) == STRUCTURE_EVIDENCE_PER_DOCUMENT
        assert f"{ELEMENT_CHUNK_PREFIX}{section.id}" in element_ids
        assert f"{ELEMENT_CHUNK_PREFIX}{table.id}" not in element_ids

    async def test_selection_is_deterministic(self, db_session, create_test_user):
        """Identical inputs produce identical ordering."""
        from brain.adapters import _augment_with_structure

        user = await create_test_user(email="aug-determinism@test.com")
        doc, chunk_rows, _section, _table = await _seed_document(
            db_session, user, name="determinism.pdf"
        )
        base = [_semantic_chunk_for(doc, chunk_rows[0])]

        first = await _augment_with_structure(db_session, base)
        second = await _augment_with_structure(db_session, base)

        assert [c.chunk_id for c in first] == [c.chunk_id for c in second]

    async def test_selected_element_evidence_contract_is_preserved(
        self, db_session, create_test_user
    ):
        """Existing structure-element evidence behaviour stays valid."""
        from brain.adapters import _augment_with_structure

        user = await create_test_user(email="aug-contract@test.com")
        doc, chunk_rows, section, _table = await _seed_document(
            db_session, user, name="contract.pdf"
        )

        augmented = await _augment_with_structure(
            db_session, [_semantic_chunk_for(doc, chunk_rows[0])]
        )
        element = next(
            c for c in augmented if c.chunk_id == f"{ELEMENT_CHUNK_PREFIX}{section.id}"
        )

        assert element.evidence_kind == "structure_element"
        assert element.retrieval_path == "structural"
        assert element.score == 0.0, "structural evidence got a fake similarity"
        assert element.fusion_score is None
        assert element.element_type == "section"
        assert element.page == 1
        assert element.section == "Boiler Manual"
        assert element.heading_path == ("Boiler Manual",)
        assert element.document_id == str(doc.id)
        assert "Boiler Manual" in element.content

    async def test_an_already_ranked_element_is_not_appended_twice(
        self, db_session, create_test_user
    ):
        """Dedup: the ``structure:<uuid>`` identity is not duplicated."""
        from brain.adapters import _augment_with_structure

        user = await create_test_user(email="aug-dedup@test.com")
        doc, chunk_rows, section, _table = await _seed_document(
            db_session, user, name="dedup.pdf"
        )
        ranked = _semantic_chunk_for(doc, chunk_rows[0])
        already_ranked = SourceChunk(
            chunk_id=f"{ELEMENT_CHUNK_PREFIX}{section.id}",
            content="Boiler Manual",
            score=0.0,
            document_id=str(doc.id),
            document_name=doc.name,
            page=1,
            retrieval_path="structural",
            evidence_kind="structure_element",
        )

        augmented = await _augment_with_structure(db_session, [ranked, already_ranked])

        ids = [c.chunk_id for c in augmented]
        assert ids.count(f"{ELEMENT_CHUNK_PREFIX}{section.id}") == 1

    async def test_empty_retrieval_is_a_noop(self, db_session, create_test_user):
        from brain.adapters import _augment_with_structure

        user = await create_test_user(email="aug-empty@test.com")
        await _seed_document(db_session, user, name="empty.pdf")

        assert await _augment_with_structure(db_session, []) == []

    async def test_documents_without_structure_rows_are_unchanged(
        self, db_session, create_test_user
    ):
        """No structure rows -> semantic-only behaviour, byte for byte."""
        from brain.adapters import _augment_with_structure

        user = await create_test_user(email="aug-nostruct@test.com")
        doc, chunk_rows = await create_document_with_chunks(
            db_session,
            user.id,
            name="nostruct.pdf",
            chunks=[
                {"index": 0, "content": "Only semantic content here.", "page": 1}
            ],
        )
        base = [_semantic_chunk_for(doc, chunk_rows[0])]

        augmented = await _augment_with_structure(db_session, base)

        assert [c.chunk_id for c in augmented] == [c.chunk_id for c in base]


class TestSelectionIsQueryIndependent:
    """The augmentation receives no question signal at all."""

    def test_augmentation_signature_accepts_no_query_or_user(self):
        from brain.adapters import _augment_with_structure

        parameters = inspect.signature(_augment_with_structure).parameters

        assert list(parameters) == ["db", "chunks"], (
            "augmentation gained new inputs — selection may have become "
            "query-dependent; update TestDocumentOrderSelection deliberately"
        )

    def test_augmentation_is_called_without_a_query(self):
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[3] / "brain" / "adapters.py"
        ).read_text(encoding="utf-8")

        assert "await _augment_with_structure(db, chunks)" in source
        # Not imported, so the ranked element-candidate stream cannot be used as
        # a selection seed (the docstring may still name it in prose).
        assert "\n    retrieve_structural_element_candidates," not in source

    async def test_two_different_questions_yield_the_same_selection(
        self, db_session, create_test_user
    ):
        """Documented consequence: the question cannot influence selection."""
        from brain.adapters import _augment_with_structure

        user = await create_test_user(email="aug-query@test.com")
        doc, chunk_rows, _section, _table = await _seed_document(
            db_session, user, name="query.pdf"
        )
        base = [_semantic_chunk_for(doc, chunk_rows[0])]

        # The question is only relevant to the callers; the selection itself is
        # identical because it never sees it.
        assert QUESTION != OTHER_QUESTION
        first = await _augment_with_structure(db_session, base)
        second = await _augment_with_structure(db_session, base)
        assert _element_ids(first) == _element_ids(second)


class TestDocumentIsolation:
    async def test_another_users_elements_are_never_included(
        self, db_session, create_test_user
    ):
        """Selection must not cross user (or document) boundaries."""
        from brain.adapters import _augment_with_structure

        owner = await create_test_user(email="aug-owner@test.com")
        intruder = await create_test_user(email="aug-intruder@test.com")

        doc_a, chunk_a, _s_a, _table_a = await _seed_document(
            db_session, owner, name="owner.pdf"
        )
        doc_b, _chunk_b, _s_b, _table_b = await _seed_document(
            db_session, intruder, name="intruder.pdf"
        )

        augmented = await _augment_with_structure(
            db_session, [_semantic_chunk_for(doc_a, chunk_a[0])]
        )
        element_ids = _element_ids(augmented)

        assert element_ids, "expected the owner's own elements to be selected"
        assert {c.document_id for c in augmented} == {str(doc_a.id)}
        assert str(doc_b.id) not in {c.document_id for c in augmented}
        assert element_ids == await _first_n_element_ids(
            db_session, doc_a.id, len(element_ids)
        )

    async def test_elements_from_a_document_that_was_not_retrieved_are_excluded(
        self, db_session, create_test_user
    ):
        """Isolation is per-document, not merely per-user."""
        from brain.adapters import _augment_with_structure

        user = await create_test_user(email="aug-two-docs@test.com")
        doc_a, chunk_a, section_a, _table_a = await _seed_document(
            db_session, user, name="first.pdf"
        )
        doc_b, _chunk_b, _s_b, table_b = await _seed_document(
            db_session, user, name="second.pdf"
        )

        # Retrieval returned a chunk from doc A only.
        augmented = await _augment_with_structure(
            db_session, [_semantic_chunk_for(doc_a, chunk_a[0])]
        )
        ids = set(_element_ids(augmented))

        assert f"{ELEMENT_CHUNK_PREFIX}{section_a.id}" in ids
        assert f"{ELEMENT_CHUNK_PREFIX}{table_b.id}" not in ids
        assert {c.document_id for c in augmented} == {str(doc_a.id)}


class TestAdapterWiring:
    async def test_retrieval_adapter_appends_structure_evidence(
        self, db_session, create_test_user
    ):
        """The adapter wires augmentation into the production evidence stream."""
        from unittest.mock import AsyncMock, patch

        from brain.adapters import retrieval_adapter

        user = await create_test_user(email="aug-wiring@test.com")
        doc, chunk_rows, section, _table = await _seed_document(
            db_session, user, name="wiring.pdf"
        )
        ranked = _semantic_chunk_for(doc, chunk_rows[0])

        with patch(
            "brain.adapters.retrieve_chunks",
            new=AsyncMock(return_value=[ranked]),
        ):
            refs = await retrieval_adapter(
                db=db_session,
                user_id=str(user.id),
                cleaned_text=QUESTION,
                top_k=5,
            )

        by_id = {r.chunk_id: r for r in refs}
        assert ranked.chunk_id in by_id
        assert f"{ELEMENT_CHUNK_PREFIX}{section.id}" in by_id
        element_ref = by_id[f"{ELEMENT_CHUNK_PREFIX}{section.id}"]
        assert element_ref.evidence_kind == "structure_element"
        assert element_ref.retrieval_path == "structural"


class TestFusionConfigurationUnchanged:
    def test_production_rrf_constants_are_untouched(self):
        """Production RRF stays 0.70 / 0.30 / k=60."""
        assert RRF_K == 60
        assert RRF_SEMANTIC_WEIGHT == 0.70
        assert RRF_STRUCTURAL_WEIGHT == 0.30

    def _chunk(self, chunk_id: str, *, retrieval_path: str = "semantic") -> SourceChunk:
        return SourceChunk(
            chunk_id=chunk_id,
            content="body",
            score=0.9 if retrieval_path == "semantic" else 0.0,
            document_id="d",
            document_name="n",
            page=1,
            retrieval_path=retrieval_path,
        )

    def test_fuse_dual_path_default_uses_the_production_weights(self):
        """Single-path evidence keeps its own label and its own RRF contribution."""
        fused = fuse_dual_path(
            [self._chunk("sem")],
            [self._chunk("struct", retrieval_path="structural")],
            top_k=5,
        )

        assert [c.chunk_id for c in fused] == ["sem", "struct"]
        assert fused[0].retrieval_path == "semantic"
        assert fused[1].retrieval_path == "structural"
        assert fused[0].fusion_score == round(RRF_SEMANTIC_WEIGHT / (RRF_K + 1), 8)
        assert fused[1].fusion_score == round(RRF_STRUCTURAL_WEIGHT / (RRF_K + 1), 8)

    def test_fuse_dual_path_marks_a_both_paths_chunk_hybrid(self):
        """A chunk found by both paths is hybrid and carries both contributions."""
        fused = fuse_dual_path(
            [self._chunk("both")],
            [self._chunk("both", retrieval_path="structural")],
            top_k=5,
        )

        assert [c.chunk_id for c in fused] == ["both"]
        assert fused[0].retrieval_path == "hybrid"
        assert fused[0].fusion_score == round(
            RRF_SEMANTIC_WEIGHT / (RRF_K + 1) + RRF_STRUCTURAL_WEIGHT / (RRF_K + 1), 8
        )


class TestNoDemoSpecificProductionLogic:
    def test_production_augmentation_has_no_demo_vocabulary(self):
        """No teacher-demo strings or ids anywhere in the augmentation code."""
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[3] / "brain" / "adapters.py"
        ).read_text(encoding="utf-8").lower()

        for token in (
            "maintenance schedule",
            "reference rig",
            "kestrel",
            "field_robotics",
            "ada99ed5",
            "lidar",
            "sequence 34",
            "page 4",
        ):
            assert token not in source, f"demo-specific token {token!r} in production code"
