"""Unit tests for Reciprocal Rank Fusion of the two retrieval paths.

The properties that matter: a chunk's provenance is reported honestly
(semantic / structural / hybrid), a structural-only chunk never receives a fake
similarity, the ranking is deterministic, and the top-K bound is respected.
"""

from __future__ import annotations

import pytest

from chat.rag import (
    RETRIEVAL_HYBRID,
    RETRIEVAL_SEMANTIC,
    RETRIEVAL_STRUCTURAL,
    RRF_K,
    RRF_SEMANTIC_WEIGHT,
    RRF_STRUCTURAL_WEIGHT,
    SourceChunk,
    fuse_dual_path,
)


def semantic_chunk(chunk_id: str, score: float) -> SourceChunk:
    return SourceChunk(
        chunk_id=chunk_id,
        content=f"content-{chunk_id}",
        score=score,
        document_id="doc-1",
        document_name="doc.pdf",
        page=1,
        retrieval_path=RETRIEVAL_SEMANTIC,
    )


def structural_chunk(chunk_id: str, hops: int, relation: str, score: float) -> SourceChunk:
    return SourceChunk(
        chunk_id=chunk_id,
        content=f"content-{chunk_id}",
        score=0.0,  # structural hits are never scored by the embedding model
        document_id="doc-1",
        document_name="doc.pdf",
        page=1,
        retrieval_path=RETRIEVAL_STRUCTURAL,
        structural_hops=hops,
        structural_relation=relation,
        structural_score=score,
    )


def expected_contribution(weight: float, rank: int) -> float:
    return weight / (RRF_K + rank)


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


class TestProvenance:
    def test_semantic_only_candidate_is_labelled_semantic(self):
        fused = fuse_dual_path([semantic_chunk("s1", 0.9)], [], top_k=5)

        assert len(fused) == 1
        assert fused[0].retrieval_path == RETRIEVAL_SEMANTIC
        assert fused[0].score == 0.9
        assert fused[0].fusion_score == pytest.approx(
            expected_contribution(RRF_SEMANTIC_WEIGHT, 1)
        )

    def test_structural_only_candidate_is_labelled_structural(self):
        fused = fuse_dual_path([], [structural_chunk("g1", 1, "NEXT", 0.5)], top_k=5)

        assert len(fused) == 1
        assert fused[0].retrieval_path == RETRIEVAL_STRUCTURAL
        assert fused[0].fusion_score == pytest.approx(
            expected_contribution(RRF_STRUCTURAL_WEIGHT, 1)
        )

    def test_candidate_found_by_both_paths_is_labelled_hybrid(self):
        sem = [semantic_chunk("x", 0.8)]
        struct = [structural_chunk("x", 1, "SAME_SECTION", 0.25)]

        fused = fuse_dual_path(sem, struct, top_k=5)

        assert len(fused) == 1
        assert fused[0].retrieval_path == RETRIEVAL_HYBRID
        assert fused[0].fusion_score == pytest.approx(
            expected_contribution(RRF_SEMANTIC_WEIGHT, 1)
            + expected_contribution(RRF_STRUCTURAL_WEIGHT, 1)
        )

    def test_hybrid_chunk_keeps_its_cosine_score(self):
        sem = [semantic_chunk("x", 0.8)]
        struct = [structural_chunk("x", 2, "NEXT", 1 / 3)]

        fused = fuse_dual_path(sem, struct, top_k=5)

        assert fused[0].score == 0.8, "fusion must not overwrite the similarity"
        assert fused[0].structural_hops == 2
        assert fused[0].structural_relation == "NEXT"


# ---------------------------------------------------------------------------
# No fabricated similarity
# ---------------------------------------------------------------------------


class TestNoFakeSimilarity:
    def test_structural_only_chunk_has_zero_semantic_score(self):
        """The embedding model never scored it; scoring it here would be fake."""
        fused = fuse_dual_path([], [structural_chunk("g1", 1, "NEXT", 0.5)], top_k=5)

        assert fused[0].score == 0.0

    def test_fusion_score_is_not_a_cosine_similarity(self):
        fused = fuse_dual_path([], [structural_chunk("g1", 1, "NEXT", 0.5)], top_k=5)

        assert fused[0].fusion_score is not None
        assert fused[0].fusion_score != fused[0].score
        # RRF scores live in a completely different range from cosine similarity.
        assert fused[0].fusion_score < 0.01

    def test_undefined_similarity_stays_undefined_when_nothing_was_retrieved(self):
        assert fuse_dual_path([], [], top_k=5) == []


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


class TestRanking:
    def test_hybrid_outranks_semantic_only_at_the_same_rank(self):
        sem = [semantic_chunk("hybrid", 0.9), semantic_chunk("sem_only", 0.8)]
        struct = [structural_chunk("hybrid", 1, "NEXT", 0.5)]

        fused = fuse_dual_path(sem, struct, top_k=5)

        assert [c.chunk_id for c in fused] == ["hybrid", "sem_only"]

    def test_semantic_rank_order_is_preserved_without_structural_support(self):
        sem = [
            semantic_chunk("first", 0.9),
            semantic_chunk("second", 0.7),
            semantic_chunk("third", 0.5),
        ]

        fused = fuse_dual_path(sem, [], top_k=5)

        assert [c.chunk_id for c in fused] == ["first", "second", "third"]

    def test_semantic_weight_dominates_structural_weight(self):
        """The declared prior is 0.70 / 0.30 — asserted, not assumed."""
        assert RRF_SEMANTIC_WEIGHT > RRF_STRUCTURAL_WEIGHT

        fused = fuse_dual_path(
            [semantic_chunk("sem", 0.9)],
            [structural_chunk("struct", 1, "NEXT", 0.5)],
            top_k=5,
        )

        assert fused[0].chunk_id == "sem"

    def test_ranking_is_deterministic_across_runs(self):
        sem = [semantic_chunk("a", 0.5), semantic_chunk("b", 0.5)]
        struct = [structural_chunk("b", 1, "NEXT", 0.5), structural_chunk("a", 1, "NEXT", 0.5)]

        first = [(c.chunk_id, c.fusion_score) for c in fuse_dual_path(sem, struct, top_k=5)]
        second = [(c.chunk_id, c.fusion_score) for c in fuse_dual_path(sem, struct, top_k=5)]

        assert first == second

    def test_semantic_similarity_breaks_an_exact_fusion_tie(self):
        """Two chunks with identical fused scores are ordered by similarity.

        Equal fusion scores are constructed deliberately: with equal path
        weights, mirrored ranks produce identical contributions
        (0.5/(61) + 0.5/(62) == 0.5/(62) + 0.5/(61)).
        """
        sem = [semantic_chunk("better", 0.6), semantic_chunk("worse", 0.4)]
        struct = [
            structural_chunk("worse", 1, "NEXT", 0.5),
            structural_chunk("better", 1, "NEXT", 0.5),
        ]

        fused = fuse_dual_path(
            sem, struct, top_k=5, semantic_weight=0.5, structural_weight=0.5
        )

        assert fused[0].fusion_score == pytest.approx(fused[1].fusion_score)
        assert [c.chunk_id for c in fused] == ["better", "worse"]

    def test_chunk_id_breaks_a_tie_when_similarity_is_also_equal(self):
        # Mirrored ranks again, so the two fused scores are exactly equal and
        # the similarity is identical too — only the chunk id can break it.
        sem = [semantic_chunk("zzz", 0.4), semantic_chunk("aaa", 0.4)]
        struct = [
            structural_chunk("aaa", 1, "NEXT", 0.5),
            structural_chunk("zzz", 1, "NEXT", 0.5),
        ]

        fused = fuse_dual_path(
            sem, struct, top_k=5, semantic_weight=0.5, structural_weight=0.5
        )

        assert [c.chunk_id for c in fused] == ["aaa", "zzz"]


# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------


class TestTopKLimit:
    def test_returns_at_most_top_k(self):
        sem = [semantic_chunk(f"s{i}", 1.0 - i * 0.01) for i in range(10)]

        fused = fuse_dual_path(sem, [], top_k=3)

        assert len(fused) == 3
        assert [c.chunk_id for c in fused] == ["s0", "s1", "s2"]

    def test_top_k_larger_than_union_returns_everything(self):
        sem = [semantic_chunk("s0", 0.9)]
        struct = [structural_chunk("g0", 1, "NEXT", 0.5)]

        fused = fuse_dual_path(sem, struct, top_k=50)

        assert len(fused) == 2

    def test_top_k_zero_returns_nothing(self):
        assert fuse_dual_path([semantic_chunk("s0", 0.9)], [], top_k=0) == []

    def test_duplicate_ids_within_one_path_are_collapsed(self):
        sem = [semantic_chunk("dup", 0.9), semantic_chunk("dup", 0.8)]

        fused = fuse_dual_path(sem, [], top_k=5)

        assert len(fused) == 1
