"""Unit tests for the structure-element retrieval candidate path.

Runs against the SQLite test database with real persisted
``DocumentStructureElement`` rows (written through the production
``documents.structure.replace_document_structure`` persister).  Assertions are
about which persisted rows become candidates, how they rank, and what reaches
the fused top-k — never about mock return values.
"""

from __future__ import annotations

import pytest

from chat.rag import (
    RETRIEVAL_SEMANTIC,
    RETRIEVAL_STRUCTURAL,
    RRF_K,
    RRF_STRUCTURAL_WEIGHT,
    SourceChunk,
    retrieve_dual_path,
    retrieve_structural_element_candidates,
)
from documents.parser import ParsedDocument, ParsedElement
from documents.structure import replace_document_structure
from tests.fixtures.graph_data import create_document_with_chunks

QUERY = (
    "What is the Kestrel frame calibrated against in the Instrument "
    "Calibration section?"
)

# One document, three sections.  Only "Instrument Calibration" names a query
# term; "Rig Setup" is its child and the target paragraph is a grandchild, so
# the target is reachable only through the parent/child walk (2 hops).
CALIBRATION_TREE = [
    {
        "element_type": "section",
        "heading_level": 1,
        "heading_path": ["Manual", "Instrument Calibration"],
        "content": "Instrument Calibration",
    },
    {
        "element_type": "section",
        "heading_level": 2,
        "heading_path": ["Manual", "Instrument Calibration", "Rig Setup"],
        "content": "Rig Setup",
        "parent_source_id": "section:1:0",
    },
    {
        "element_type": "paragraph",
        "heading_path": ["Manual", "Instrument Calibration", "Rig Setup"],
        "content": "The Kestrel frame is calibrated against the reference rig.",
        "parent_source_id": "section:1:1",
    },
    {
        "element_type": "section",
        "heading_level": 2,
        "heading_path": ["Manual", "Field Supplies"],
        "content": "Field Supplies",
        "parent_source_id": None,
    },
    {
        "element_type": "paragraph",
        "heading_path": ["Manual", "Field Supplies"],
        "content": "The carrying case is made of nylon.",
        "parent_source_id": "section:1:3",
    },
]

TARGET_CONTENT = "The Kestrel frame is calibrated against the reference rig."


async def seed_structure(db, user_id, specs, *, name: str = "structure.pdf"):
    """Persist a structure tree through the production persister."""
    doc, _ = await create_document_with_chunks(db, user_id, name=name, chunks=[])
    elements = [
        ParsedElement(
            source_id=f"{spec['element_type']}:1:{index}",
            element_type=spec["element_type"],
            page_number=1,
            sequence_index=index,
            parent_source_id=spec.get("parent_source_id"),
            heading_level=spec.get("heading_level"),
            heading_path=spec.get("heading_path"),
            content=spec.get("content"),
        )
        for index, spec in enumerate(specs)
    ]
    parsed = ParsedDocument(
        parser_version="test-parser", source=name, page_count=1, elements=elements
    )
    by_source = await replace_document_structure(db, doc.id, parsed)
    return doc, by_source


# A canonical UUID that is never seeded into the structure: the declared
# semantic candidate is fed back into the graph expansion, so its chunk id must
# be a value the real database accepts (PostgreSQL rejects a non-UUID there).
SEMANTIC_ONLY_CHUNK_ID = "6f1e2c34-0000-4000-8000-000000000001"


def declared_semantic(document_id: str, *, score: float = 0.93) -> SourceChunk:
    """A declared semantic candidate (test double for the pgvector stream).

    Labeled as declared: it is an input to the ranking, not a measured
    retrieval result.
    """
    return SourceChunk(
        chunk_id=SEMANTIC_ONLY_CHUNK_ID,
        content="The vermilion coating cures in six hours.",
        score=score,
        document_id=document_id,
        document_name="fixture.pdf",
        page=1,
        retrieval_path=RETRIEVAL_SEMANTIC,
    )


# ---------------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------------


class TestCandidateGeneration:
    async def test_structural_element_candidates_are_generated(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="elem-gen@test.com")
        doc, by_source = await seed_structure(
            db_session, user.id, CALIBRATION_TREE
        )

        candidates = await retrieve_structural_element_candidates(
            db_session, str(user.id), QUERY
        )

        by_content = {c.content: c for c in candidates}
        target = by_content[TARGET_CONTENT]
        assert target.chunk_id == f"structure:{by_source['paragraph:1:2'].id}"
        assert target.document_id == str(doc.id)
        assert target.evidence_kind == "structure_element"
        assert target.retrieval_path == RETRIEVAL_STRUCTURAL
        assert target.score == 0.0, "an element has no similarity and must not get one"

    async def test_seeds_use_structure_names_never_content(
        self, db_session, create_test_user
    ):
        """A term that only occurs in body text cannot seed structure."""
        user = await create_test_user(email="elem-content@test.com")
        await seed_structure(db_session, user.id, CALIBRATION_TREE)

        candidates = await retrieve_structural_element_candidates(
            db_session, str(user.id), "What is the carrying case made of?"
        )

        assert candidates == []

    async def test_no_terms_no_candidates(self, db_session, create_test_user):
        user = await create_test_user(email="elem-terms@test.com")
        await seed_structure(db_session, user.id, CALIBRATION_TREE)

        assert (
            await retrieve_structural_element_candidates(
                db_session, str(user.id), "the of and"
            )
            == []
        )

    async def test_candidate_count_is_bounded(self, db_session, create_test_user):
        user = await create_test_user(email="elem-bound@test.com")
        specs = [
            {
                "element_type": "section",
                "heading_level": 1,
                "heading_path": ["Calibration"],
                "content": "Calibration",
            },
        ]
        for index in range(10):
            specs.append(
                {
                    "element_type": "paragraph",
                    "heading_path": ["Calibration"],
                    "content": f"Calibration notes {index}.",
                    "parent_source_id": "section:1:0",
                }
            )
        await seed_structure(db_session, user.id, specs)

        candidates = await retrieve_structural_element_candidates(
            db_session, str(user.id), "Calibration notes", limit=3
        )

        assert len(candidates) == 3


# ---------------------------------------------------------------------------
# Isolation and identity
# ---------------------------------------------------------------------------


class TestIsolationAndIdentity:
    async def test_candidates_never_cross_users(
        self, db_session, create_test_user
    ):
        user_a = await create_test_user(email="elem-owner-a@test.com")
        user_b = await create_test_user(email="elem-owner-b@test.com")
        await seed_structure(db_session, user_a.id, CALIBRATION_TREE, name="a.pdf")
        _, by_source_b = await seed_structure(
            db_session, user_b.id, CALIBRATION_TREE, name="b.pdf"
        )

        candidates = await retrieve_structural_element_candidates(
            db_session, str(user_a.id), QUERY
        )

        foreign_ids = {str(row.id) for row in by_source_b.values()}
        for candidate in candidates:
            element_id = candidate.chunk_id.split(":", 1)[1]
            assert element_id not in foreign_ids, (
                "user A retrieved user B's structure element"
            )

    async def test_unready_documents_are_ignored(self, db_session, create_test_user):
        user = await create_test_user(email="elem-unready@test.com")
        doc, _ = await create_document_with_chunks(
            db_session,
            user.id,
            name="broken.pdf",
            chunks=[],
            status="error",
            embedding_status="error",
        )
        specs = [
            {
                "element_type": "section",
                "heading_level": 1,
                "heading_path": ["Calibration"],
                "content": "Calibration",
            }
        ]
        elements = [
            ParsedElement(
                source_id="section:1:0",
                element_type="section",
                page_number=1,
                sequence_index=0,
                heading_level=1,
                heading_path=["Calibration"],
                content="Calibration",
            )
        ]
        await replace_document_structure(
            db_session,
            doc.id,
            ParsedDocument(
                parser_version="test-parser",
                source="broken.pdf",
                page_count=1,
                elements=elements,
            ),
        )

        candidates = await retrieve_structural_element_candidates(
            db_session, str(user.id), "Calibration"
        )

        assert candidates == []

    async def test_identity_is_stable_across_calls(self, db_session, create_test_user):
        user = await create_test_user(email="elem-id@test.com")
        _, by_source = await seed_structure(db_session, user.id, CALIBRATION_TREE)

        first = await retrieve_structural_element_candidates(
            db_session, str(user.id), QUERY
        )
        second = await retrieve_structural_element_candidates(
            db_session, str(user.id), QUERY
        )

        assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
        target_id = f"structure:{by_source['paragraph:1:2'].id}"
        assert target_id in {c.chunk_id for c in first}


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


class TestRanking:
    async def test_ordering_is_deterministic(self, db_session, create_test_user):
        user = await create_test_user(email="elem-order@test.com")
        await seed_structure(db_session, user.id, CALIBRATION_TREE)

        first = await retrieve_structural_element_candidates(
            db_session, str(user.id), QUERY
        )
        second = await retrieve_structural_element_candidates(
            db_session, str(user.id), QUERY
        )

        assert [(c.chunk_id, c.structural_hops) for c in first] == [
            (c.chunk_id, c.structural_hops) for c in second
        ]

    async def test_nearer_elements_rank_above_deeper_ones(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="elem-hops@test.com")
        _, by_source = await seed_structure(db_session, user.id, CALIBRATION_TREE)

        candidates = await retrieve_structural_element_candidates(
            db_session, str(user.id), QUERY
        )

        hops = {c.chunk_id: c.structural_hops for c in candidates}
        section_id = f"structure:{by_source['section:1:0'].id}"
        subsection_id = f"structure:{by_source['section:1:1'].id}"
        target_id = f"structure:{by_source['paragraph:1:2'].id}"

        assert hops[section_id] == 0
        assert hops[subsection_id] == 1
        assert hops[target_id] == 2
        assert [c.chunk_id for c in candidates] == [
            section_id,
            subsection_id,
            target_id,
        ]

    async def test_rank_contribution_is_the_declared_rrf_contribution(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="elem-rrf@test.com")
        doc, _ = await seed_structure(db_session, user.id, CALIBRATION_TREE)
        semantic = [declared_semantic(str(doc.id))]

        fused = await retrieve_dual_path(
            db_session, str(user.id), QUERY, top_k=5, semantic_chunks=semantic
        )
        again = await retrieve_dual_path(
            db_session, str(user.id), QUERY, top_k=5, semantic_chunks=semantic
        )

        assert [(c.chunk_id, c.fusion_score) for c in fused] == [
            (c.chunk_id, c.fusion_score) for c in again
        ]
        # Rank-based contribution only: 0.70/61 for the semantic rank-1
        # candidate, 0.30/(60+rank) for each structural candidate.
        assert fused[0].fusion_score == pytest.approx(0.70 / (RRF_K + 1), abs=1e-8)
        for rank, candidate in enumerate(fused[1:], start=1):
            assert candidate.fusion_score == pytest.approx(
                RRF_STRUCTURAL_WEIGHT / (RRF_K + rank), abs=1e-8
            )
            assert candidate.fusion_score != candidate.score, (
                "the rank contribution must never masquerade as a similarity"
            )


# ---------------------------------------------------------------------------
# Final top-k and ordering influence
# ---------------------------------------------------------------------------


class TestTopKInfluence:
    async def test_structural_evidence_enters_final_top_k(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="elem-topk@test.com")
        doc, by_source = await seed_structure(db_session, user.id, CALIBRATION_TREE)
        semantic = [declared_semantic(str(doc.id))]

        fused = await retrieve_dual_path(
            db_session, str(user.id), QUERY, top_k=5, semantic_chunks=semantic
        )

        target_id = f"structure:{by_source['paragraph:1:2'].id}"
        assert target_id in {c.chunk_id for c in fused}, (
            "the structure-derived candidate never reached the final top-k"
        )

    async def test_structural_evidence_changes_final_ordering(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="elem-rank-change@test.com")
        doc, by_source = await seed_structure(db_session, user.id, CALIBRATION_TREE)
        semantic = [declared_semantic(str(doc.id))]

        # Semantic-only baseline: one candidate, nothing else.
        from chat.rag import fuse_dual_path

        semantic_only = fuse_dual_path(semantic, [], top_k=5)
        assert [c.chunk_id for c in semantic_only] == [SEMANTIC_ONLY_CHUNK_ID]

        fused = await retrieve_dual_path(
            db_session, str(user.id), QUERY, top_k=5, semantic_chunks=semantic
        )

        section_id = f"structure:{by_source['section:1:0'].id}"
        subsection_id = f"structure:{by_source['section:1:1'].id}"
        target_id = f"structure:{by_source['paragraph:1:2'].id}"
        assert [c.chunk_id for c in fused] == [
            SEMANTIC_ONLY_CHUNK_ID,
            section_id,
            subsection_id,
            target_id,
        ], "structural candidates must enter the final ranking in graph order"

    async def test_ranked_elements_are_not_duplicated_by_augmentation(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="elem-dup@test.com")
        doc, by_source = await seed_structure(db_session, user.id, CALIBRATION_TREE)

        from unittest.mock import AsyncMock, patch

        from brain.adapters import retrieval_adapter

        semantic = [declared_semantic(str(doc.id))]
        with patch(
            "brain.adapters.retrieve_chunks",
            new=AsyncMock(return_value=semantic),
        ):
            refs = await retrieval_adapter(
                db=db_session,
                user_id=str(user.id),
                cleaned_text=QUERY,
                top_k=5,
            )

        ids = [ref.chunk_id for ref in refs]
        assert len(ids) == len(set(ids)), "an element was reported twice"

        target_id = f"structure:{by_source['paragraph:1:2'].id}"
        target = next(ref for ref in refs if ref.chunk_id == target_id)
        assert target.evidence_kind == "structure_element"
        assert target.score == 0.0
        assert target.fusion_score is not None
        assert target.structural_hops == 2


# ---------------------------------------------------------------------------
# No fabricated values
# ---------------------------------------------------------------------------


class TestNoFabricatedValues:
    async def test_elements_never_carry_a_similarity(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="elem-score@test.com")
        await seed_structure(db_session, user.id, CALIBRATION_TREE)

        candidates = await retrieve_structural_element_candidates(
            db_session, str(user.id), QUERY
        )

        for candidate in candidates:
            assert candidate.score == 0.0
            assert candidate.evidence_kind == "structure_element"
            # The graph-distance score is labelled structural and equals the
            # documented relation_weight / (1 + hops) with weight 1.0.
            assert candidate.structural_score == pytest.approx(
                1.0 / (1 + candidate.structural_hops), abs=1e-6
            )
