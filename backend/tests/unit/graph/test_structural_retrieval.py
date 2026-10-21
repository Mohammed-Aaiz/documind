"""Unit tests for structural seed matching and graph expansion.

Runs against the SQLite test database.  Every seed and every returned chunk is a
real persisted row — the assertions are about which rows the structural path can
reach, never about a mock's return value.
"""

from __future__ import annotations

import pytest

from chat.rag import retrieve_structural_candidates
from graph.service import (
    MAX_HOPS,
    expand_from_seeds,
    find_section_seed_matches,
    load_candidates,
    replace_document_graph,
    terms_from_question,
)
from tests.fixtures.graph_data import create_document_with_chunks, views_for


def chain_document(name: str, count: int) -> list[dict]:
    """A document whose chunks share no page or heading.

    That removes every SAME_PAGE / SAME_SECTION shortcut, so the only way from
    one chunk to the next is the reading-order chain — which is what makes hop
    distance observable.
    """
    return [
        {
            "index": i,
            "content": f"{name} body paragraph {i}",
            "page": i + 1,
            "heading_path": [f"Section {i}"],
            "section": f"Section {i}",
        }
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# Term extraction
# ---------------------------------------------------------------------------


class TestQuestionTerms:
    def test_terms_drop_stop_words_and_short_tokens(self):
        terms = terms_from_question("What is the of a an in?")
        assert terms == []

    def test_terms_keep_meaningful_words_in_order(self):
        terms = terms_from_question("Reference Manual coating cure time")
        assert terms == ["reference", "manual", "coating", "cure", "time"]

    def test_terms_are_deduplicated(self):
        assert terms_from_question("coating coating coating") == ["coating"]

    def test_empty_question_yields_no_terms(self):
        assert terms_from_question("") == []


# ---------------------------------------------------------------------------
# Heading / section seed matching
# ---------------------------------------------------------------------------


class TestSeedMatching:
    async def test_section_term_match_selects_the_chunk(self, db_session, create_test_user):
        user = await create_test_user(email="seed-a@test.com")
        doc, rows = await create_document_with_chunks(
            db_session,
            user.id,
            chunks=[
                {
                    "index": 0,
                    "content": "intro",
                    "page": 1,
                    "heading_path": ["Reference Manual"],
                    "section": "Reference Manual",
                },
                {
                    "index": 1,
                    "content": "unrelated",
                    "page": 2,
                    "heading_path": ["Appendix"],
                    "section": "Appendix",
                },
            ],
        )

        matches = await find_section_seed_matches(
            db_session, str(user.id), terms_from_question("What does the Reference Manual say?")
        )

        assert matches, "no seed matched the section name"
        assert matches[0][0] == str(rows[0].id)
        assert "reference" in matches[0][1]

    async def test_heading_path_is_also_searched(
        self, db_session, create_test_user
    ):
        """A term may appear only in an ancestor heading, not the leaf section."""
        user = await create_test_user(email="seed-b@test.com")
        _, rows = await create_document_with_chunks(
            db_session,
            user.id,
            chunks=[
                {
                    "index": 0,
                    "content": "body",
                    "page": 1,
                    "heading_path": ["Installation", "Requirements"],
                    "section": "Requirements",
                }
            ],
        )

        matches = await find_section_seed_matches(
            db_session, str(user.id), ["installation"]
        )

        assert [m[0] for m in matches] == [str(rows[0].id)]

    async def test_content_only_terms_are_not_treated_as_seeds(
        self, db_session, create_test_user
    ):
        """Seed matching reads structure, never chunk text.

        This is the boundary that keeps the structural path honest: a term that
        only occurs in body text is not evidence that the *section* is relevant.
        """
        user = await create_test_user(email="seed-c@test.com")
        await create_document_with_chunks(
            db_session,
            user.id,
            chunks=[
                {
                    "index": 0,
                    "content": "The vermilion coating cures in six hours.",
                    "page": 1,
                    "heading_path": ["Appendix"],
                    "section": "Appendix",
                }
            ],
        )

        matches = await find_section_seed_matches(db_session, str(user.id), ["vermilion"])

        assert matches == []

    async def test_seed_matching_ignores_unready_documents(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="seed-d@test.com")
        await create_document_with_chunks(
            db_session,
            user.id,
            status="error",
            embedding_status="error",
            chunks=[
                {
                    "index": 0,
                    "content": "body",
                    "page": 1,
                    "heading_path": ["Reference Manual"],
                    "section": "Reference Manual",
                }
            ],
        )

        matches = await find_section_seed_matches(
            db_session, str(user.id), ["reference"]
        )

        assert matches == []


# ---------------------------------------------------------------------------
# Expansion
# ---------------------------------------------------------------------------


class TestExpansion:
    async def test_one_hop_expansion(self, db_session, create_test_user):
        user = await create_test_user(email="hop-1@test.com")
        doc, rows = await create_document_with_chunks(
            db_session, user.id, chunks=chain_document("one", 5)
        )
        await replace_document_graph(db_session, doc.id, views_for(rows))

        visited = await expand_from_seeds(db_session, str(user.id), [str(rows[0].id)])

        assert visited[str(rows[1].id)][0] == 1
        assert visited[str(rows[1].id)][1] == "NEXT"

    async def test_two_hop_expansion(self, db_session, create_test_user):
        user = await create_test_user(email="hop-2@test.com")
        doc, rows = await create_document_with_chunks(
            db_session, user.id, chunks=chain_document("two", 5)
        )
        await replace_document_graph(db_session, doc.id, views_for(rows))

        visited = await expand_from_seeds(db_session, str(user.id), [str(rows[0].id)])

        assert visited[str(rows[2].id)][0] == 2

    async def test_expansion_stops_at_max_hops(self, db_session, create_test_user):
        user = await create_test_user(email="hop-max@test.com")
        doc, rows = await create_document_with_chunks(
            db_session, user.id, chunks=chain_document("max", 6)
        )
        await replace_document_graph(db_session, doc.id, views_for(rows))

        visited = await expand_from_seeds(
            db_session, str(user.id), [str(rows[0].id)], max_hops=MAX_HOPS
        )

        assert str(rows[MAX_HOPS].id) in visited
        assert str(rows[MAX_HOPS + 1].id) not in visited, "expansion exceeded max hops"

    async def test_seed_itself_is_hop_zero(self, db_session, create_test_user):
        user = await create_test_user(email="hop-0@test.com")
        doc, rows = await create_document_with_chunks(
            db_session, user.id, chunks=chain_document("zero", 3)
        )
        await replace_document_graph(db_session, doc.id, views_for(rows))

        visited = await expand_from_seeds(db_session, str(user.id), [str(rows[0].id)])

        assert visited[str(rows[0].id)][0] == 0
        assert visited[str(rows[0].id)][1] is None

    async def test_expansion_never_crosses_documents(self, db_session, create_test_user):
        """Edges are per-document, so a seed cannot reach a sibling document."""
        user = await create_test_user(email="cross-doc@test.com")
        doc_a, rows_a = await create_document_with_chunks(
            db_session, user.id, name="a.pdf", chunks=chain_document("a", 3)
        )
        doc_b, rows_b = await create_document_with_chunks(
            db_session, user.id, name="b.pdf", chunks=chain_document("b", 3)
        )
        await replace_document_graph(db_session, doc_a.id, views_for(rows_a))
        await replace_document_graph(db_session, doc_b.id, views_for(rows_b))

        visited = await expand_from_seeds(db_session, str(user.id), [str(rows_a[0].id)])

        assert not any(str(row.id) in visited for row in rows_b), (
            "structural expansion leaked into another document"
        )

    async def test_expansion_never_crosses_users(self, db_session, create_test_user):
        """User B's chunk ids are unusable seeds for user A."""
        user_a = await create_test_user(email="owner-a@test.com")
        user_b = await create_test_user(email="owner-b@test.com")
        doc_b, rows_b = await create_document_with_chunks(
            db_session, user_b.id, name="b.pdf", chunks=chain_document("b", 3)
        )
        await replace_document_graph(db_session, doc_b.id, views_for(rows_b))

        visited = await expand_from_seeds(db_session, str(user_a.id), [str(rows_b[0].id)])

        assert str(rows_b[1].id) not in visited, "user A traversed user B's graph"

    async def test_load_candidates_hides_other_users_chunks(
        self, db_session, create_test_user
    ):
        user_a = await create_test_user(email="load-a@test.com")
        user_b = await create_test_user(email="load-b@test.com")
        _, rows_b = await create_document_with_chunks(
            db_session, user_b.id, name="b.pdf", chunks=chain_document("b", 2)
        )

        loaded = await load_candidates(
            db_session, str(user_a.id), [str(row.id) for row in rows_b]
        )

        assert loaded == {}


# ---------------------------------------------------------------------------
# retrieve_structural_candidates (the rag-level entry point)
# ---------------------------------------------------------------------------


class TestRetrieveStructuralCandidates:
    async def test_returns_real_persisted_chunks(self, db_session, create_test_user):
        user = await create_test_user(email="rsc-a@test.com")
        doc, rows = await create_document_with_chunks(
            db_session,
            user.id,
            chunks=[
                {
                    "index": 0,
                    "content": "Reference Manual introduction",
                    "page": 1,
                    "heading_path": ["Reference Manual"],
                    "section": "Reference Manual",
                },
                {
                    "index": 1,
                    "content": "Reference Manual details",
                    "page": 1,
                    "heading_path": ["Reference Manual"],
                    "section": "Reference Manual",
                },
            ],
        )
        await replace_document_graph(db_session, doc.id, views_for(rows))

        candidates = await retrieve_structural_candidates(
            db_session, str(user.id), "What does the Reference Manual describe?"
        )

        ids = {c.chunk_id for c in candidates}
        assert ids == {str(rows[0].id), str(rows[1].id)}
        assert {c.content for c in candidates} == {
            "Reference Manual introduction",
            "Reference Manual details",
        }

    async def test_structural_candidates_carry_no_fake_similarity(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="rsc-b@test.com")
        doc, rows = await create_document_with_chunks(
            db_session, user.id, chunks=chain_document("noise", 2), name="noise.pdf"
        )
        await replace_document_graph(db_session, doc.id, views_for(rows))

        candidates = await retrieve_structural_candidates(
            db_session, str(user.id), "anything", semantic_seed_ids=[str(rows[0].id)]
        )

        assert candidates, "semantic seeds should anchor an expansion"
        for candidate in candidates:
            assert candidate.score == 0.0
            assert candidate.retrieval_path == "structural"
            assert candidate.structural_score is not None

    async def test_semantic_seeds_anchor_the_expansion(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="rsc-c@test.com")
        doc, rows = await create_document_with_chunks(
            db_session, user.id, chunks=chain_document("anchor", 4)
        )
        await replace_document_graph(db_session, doc.id, views_for(rows))

        candidates = await retrieve_structural_candidates(
            db_session,
            str(user.id),
            "no structural terms here at all",
            semantic_seed_ids=[str(rows[0].id)],
        )

        hops = {c.chunk_id: c.structural_hops for c in candidates}
        assert hops[str(rows[0].id)] == 0
        assert hops[str(rows[1].id)] == 1

    async def test_no_seeds_and_no_terms_returns_nothing(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="rsc-d@test.com")

        candidates = await retrieve_structural_candidates(
            db_session, str(user.id), "the of and", semantic_seed_ids=[]
        )

        assert candidates == []

    async def test_other_users_seed_cannot_retrieve_anything(
        self, db_session, create_test_user
    ):
        user_a = await create_test_user(email="rsc-owner-a@test.com")
        user_b = await create_test_user(email="rsc-owner-b@test.com")
        doc_b, rows_b = await create_document_with_chunks(
            db_session, user_b.id, name="b.pdf", chunks=chain_document("b", 3)
        )
        await replace_document_graph(db_session, doc_b.id, views_for(rows_b))

        candidates = await retrieve_structural_candidates(
            db_session,
            str(user_a.id),
            "unrelated query text",
            semantic_seed_ids=[str(rows_b[0].id)],
        )

        assert candidates == [], "user A retrieved user B's structural evidence"

    async def test_results_are_deterministic(self, db_session, create_test_user):
        user = await create_test_user(email="rsc-e@test.com")
        doc, rows = await create_document_with_chunks(
            db_session, user.id, chunks=chain_document("det", 4)
        )
        await replace_document_graph(db_session, doc.id, views_for(rows))

        first = await retrieve_structural_candidates(
            db_session, str(user.id), "query", semantic_seed_ids=[str(rows[0].id)]
        )
        second = await retrieve_structural_candidates(
            db_session, str(user.id), "query", semantic_seed_ids=[str(rows[0].id)]
        )

        assert [c.chunk_id for c in first] == [c.chunk_id for c in second]

    async def test_limit_is_respected(self, db_session, create_test_user):
        user = await create_test_user(email="rsc-f@test.com")
        doc, rows = await create_document_with_chunks(
            db_session, user.id, chunks=chain_document("limit", 6)
        )
        await replace_document_graph(db_session, doc.id, views_for(rows))

        candidates = await retrieve_structural_candidates(
            db_session,
            str(user.id),
            "query",
            semantic_seed_ids=[str(rows[0].id)],
            limit=2,
        )

        assert len(candidates) == 2
