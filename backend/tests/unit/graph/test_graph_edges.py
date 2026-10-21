"""Unit tests for structural edge planning.

``plan_edges`` is pure, so every invariant is checked without a database: no
self edges, no duplicate triples, correct reading order, page adjacency only
between consecutive chunks that really share a page, and section adjacency that
links a section without turning it into a clique.
"""

from __future__ import annotations

import pytest

from graph.service import (
    RELATION_NEXT,
    RELATION_PREV,
    RELATION_SAME_PAGE,
    RELATION_SAME_SECTION,
    SECTION_NEIGHBOURHOOD,
    ChunkView,
    plan_edges,
)


def _edges(chunks):
    return [(e.source_chunk_id, e.target_chunk_id, e.relation) for e in plan_edges(chunks)]


def _specs(chunks):
    return plan_edges(chunks)


# ---------------------------------------------------------------------------
# Reading order
# ---------------------------------------------------------------------------


class TestReadingOrder:
    def test_consecutive_chunks_are_linked_in_both_directions(self):
        chunks = [ChunkView("a", 0, 1, None), ChunkView("b", 1, 1, None)]

        edges = _edges(chunks)

        assert ("a", "b", RELATION_NEXT) in edges
        assert ("b", "a", RELATION_PREV) in edges

    def test_last_chunk_has_no_next_and_first_has_no_prev(self):
        edges = _edges([ChunkView("a", 0, 1, None), ChunkView("b", 1, 1, None)])

        assert not any(src == "b" and rel == RELATION_NEXT for src, _, rel in edges)
        assert not any(src == "a" and rel == RELATION_PREV for src, _, rel in edges)

    def test_single_chunk_produces_no_edges(self):
        assert _specs([ChunkView("only", 0, 1, ("S",))]) == []

    def test_empty_document_produces_no_edges(self):
        assert _specs([]) == []


# ---------------------------------------------------------------------------
# Invariants: no self edges, no duplicate relations
# ---------------------------------------------------------------------------


class TestInvariants:
    def test_no_self_edges(self):
        chunks = [
            ChunkView("a", 0, 1, ("S",)),
            ChunkView("b", 1, 1, ("S",)),
            ChunkView("c", 2, 1, ("S",)),
            ChunkView("d", 3, 1, ("S",)),
        ]

        for source, target, _relation in _edges(chunks):
            assert source != target, "planner emitted a self edge"

    def test_relation_triples_are_unique(self):
        chunks = [ChunkView(f"c{i}", i, 1, ("S",)) for i in range(5)]

        edges = _edges(chunks)

        assert len(edges) == len(set(edges)), "planner emitted a duplicate triple"

    def test_every_edge_carries_a_positive_weight(self):
        chunks = [
            ChunkView("a", 0, 1, ("S",)),
            ChunkView("b", 1, 1, ("S",)),
            ChunkView("c", 2, 1, ("S",)),
        ]

        for spec in _specs(chunks):
            assert spec.weight > 0

    def test_weights_follow_relation_strength(self):
        chunks = [
            ChunkView("a", 0, 1, ("S",)),
            ChunkView("b", 1, 1, ("S",)),
        ]
        weights = {spec.relation: spec.weight for spec in _specs(chunks)}

        assert weights[RELATION_NEXT] == weights[RELATION_PREV]
        assert weights[RELATION_NEXT] > weights[RELATION_SAME_PAGE]
        assert weights[RELATION_SAME_PAGE] > weights[RELATION_SAME_SECTION]


# ---------------------------------------------------------------------------
# Page adjacency
# ---------------------------------------------------------------------------


class TestPageAdjacency:
    def test_same_page_neighbours_are_linked_both_ways(self):
        edges = _edges([ChunkView("a", 0, 3, None), ChunkView("b", 1, 3, None)])

        assert ("a", "b", RELATION_SAME_PAGE) in edges
        assert ("b", "a", RELATION_SAME_PAGE) in edges

    def test_different_pages_are_not_linked_by_page(self):
        edges = _edges([ChunkView("a", 0, 1, None), ChunkView("b", 1, 2, None)])

        assert not any(rel == RELATION_SAME_PAGE for _, _, rel in edges)

    def test_missing_page_never_creates_page_edges(self):
        """DOCX/TXT chunks have no page; None must not match None."""
        edges = _edges([ChunkView("a", 0, None, None), ChunkView("b", 1, None, None)])

        assert not any(rel == RELATION_SAME_PAGE for _, _, rel in edges)

    def test_page_adjacency_is_not_a_clique(self):
        """Only consecutive chunks share a page edge, not every pair."""
        chunks = [ChunkView(f"c{i}", i, 1, None) for i in range(4)]

        page_edges = [e for e in _edges(chunks) if e[2] == RELATION_SAME_PAGE]

        # 3 consecutive pairs, 2 directions each = 6 edges, not 4*3 = 12.
        assert len(page_edges) == 6


# ---------------------------------------------------------------------------
# Section adjacency
# ---------------------------------------------------------------------------


class TestSectionAdjacency:
    def test_same_heading_path_neighbours_are_linked_both_ways(self):
        chunks = [
            ChunkView("a", 0, 1, ("Handbook", "Tools")),
            ChunkView("b", 1, 1, ("Handbook", "Tools")),
        ]

        edges = _edges(chunks)

        assert ("a", "b", RELATION_SAME_SECTION) in edges
        assert ("b", "a", RELATION_SAME_SECTION) in edges

    def test_different_headings_are_not_linked(self):
        chunks = [
            ChunkView("a", 0, 1, ("Handbook", "Tools")),
            ChunkView("b", 1, 1, ("Handbook", "Safety")),
        ]

        assert not any(rel == RELATION_SAME_SECTION for _, _, rel in _edges(chunks))

    def test_chunks_without_a_heading_are_not_linked(self):
        chunks = [ChunkView("a", 0, 1, None), ChunkView("b", 1, 1, None)]

        assert not any(rel == RELATION_SAME_SECTION for _, _, rel in _edges(chunks))

    def test_nearby_chunks_in_the_same_section_are_linked(self):
        """A section must be navigable beyond its immediate neighbours."""
        chunks = [ChunkView(f"c{i}", i, 1, ("S",)) for i in range(3)]

        edges = _edges(chunks)

        assert ("c0", "c2", RELATION_SAME_SECTION) in edges
        assert ("c2", "c0", RELATION_SAME_SECTION) in edges

    def test_section_window_is_bounded_and_not_a_clique(self):
        """Beyond SECTION_NEIGHBOURHOOD there must be no direct edge."""
        size = SECTION_NEIGHBOURHOOD + 3
        chunks = [ChunkView(f"c{i}", i, 1, ("S",)) for i in range(size)]

        linked = {
            (src, dst)
            for src, dst, rel in _edges(chunks)
            if rel == RELATION_SAME_SECTION
        }

        far = SECTION_NEIGHBOURHOOD + 1
        assert ("c0", f"c{far}") not in linked
        # A dense clique would link every pair; the window must not.
        assert len(linked) < size * (size - 1)

    def test_section_window_does_not_cross_a_heading_boundary(self):
        chunks = [
            ChunkView("c0", 0, 1, ("Book", "One")),
            ChunkView("c1", 1, 1, ("Book", "One")),
            ChunkView("c2", 2, 1, ("Book", "Two")),
        ]

        edges = _edges(chunks)

        assert ("c0", "c2", RELATION_SAME_SECTION) not in edges
        assert ("c2", "c0", RELATION_SAME_SECTION) not in edges
