"""The 1-hop hierarchy expansion used by the 15-mark answer path.

Everything here runs against real persisted rows: documents, chunks and the
structural graph are created by the test, then ``expand_evidence_via_graph``
walks them.  The assertions are about which rows a traversal can reach and what
provenance it reports — never about a mock's return value.
"""

from __future__ import annotations

from graph.service import (
    GRAPH_EXPANSION_MAX_NEIGHBOURS,
    expand_evidence_via_graph,
    parent_heading,
    replace_document_graph,
)
from tests.fixtures.graph_data import create_document_with_chunks, views_for


def manual_chunks() -> list[dict]:
    """One document, two sections, in reading order."""
    return [
        {
            "index": 0,
            "content": "Reference manual introduction.",
            "page": 1,
            "heading_path": ["Reference Manual", "Overview"],
            "section": "Overview",
        },
        {
            "index": 1,
            "content": "The lidar array requires calibration every 30 days.",
            "page": 2,
            "heading_path": ["Reference Manual", "Calibration"],
            "section": "Calibration",
        },
        {
            "index": 2,
            "content": "Calibration is performed by a certified technician.",
            "page": 2,
            "heading_path": ["Reference Manual", "Calibration"],
            "section": "Calibration",
        },
        {
            "index": 3,
            "content": "The sensor array requires recalibration every 90 days.",
            "page": 3,
            "heading_path": ["Reference Manual", "Sensors"],
            "section": "Sensors",
        },
    ]


class TestParentHeading:
    def test_the_heading_above_the_own_section_is_reported(self):
        assert parent_heading(["Reference Manual", "Calibration"]) == "Reference Manual"

    def test_a_top_level_section_has_no_parent(self):
        assert parent_heading(["Reference Manual"]) is None

    def test_a_legacy_chunk_has_no_parent(self):
        assert parent_heading(None) is None

    def test_a_string_path_is_parsed(self):
        assert parent_heading("Reference Manual > Calibration > Torque") == "Calibration"


class TestExpansion:
    async def test_seed_is_expanded_to_its_one_hop_neighbours(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="expand-a@test.com")
        doc, rows = await create_document_with_chunks(
            db_session, user.id, chunks=manual_chunks()
        )
        await replace_document_graph(db_session, doc.id, views_for(rows))
        await db_session.flush()

        neighbours = await expand_evidence_via_graph(
            db_session, str(user.id), [str(rows[1].id)]
        )

        ids = [neighbour.chunk_id for neighbour in neighbours]
        assert str(rows[1].id) not in ids, "the seed must not be its own neighbour"
        assert str(rows[2].id) in ids, "the adjacent chunk in the same section"
        assert str(rows[0].id) in ids, "the previous chunk in reading order"
        assert all(neighbour.hops == 1 for neighbour in neighbours)

    async def test_neighbours_carry_the_parent_heading(self, db_session, create_test_user):
        user = await create_test_user(email="expand-b@test.com")
        doc, rows = await create_document_with_chunks(
            db_session, user.id, chunks=manual_chunks()
        )
        await replace_document_graph(db_session, doc.id, views_for(rows))
        await db_session.flush()

        neighbours = await expand_evidence_via_graph(
            db_session, str(user.id), [str(rows[1].id)]
        )
        calibration = next(n for n in neighbours if n.chunk_id == str(rows[2].id))

        assert calibration.heading_path == ("Reference Manual", "Calibration")
        assert calibration.parent_heading == "Reference Manual"
        assert calibration.document_name == "graph-doc.pdf"
        assert calibration.page == 2

    async def test_a_foreign_seed_reaches_nothing(self, db_session, create_test_user):
        owner = await create_test_user(email="expand-owner@test.com")
        stranger = await create_test_user(email="expand-stranger@test.com")
        doc, rows = await create_document_with_chunks(
            db_session, owner.id, chunks=manual_chunks()
        )
        await replace_document_graph(db_session, doc.id, views_for(rows))
        await db_session.flush()

        neighbours = await expand_evidence_via_graph(
            db_session, str(stranger.id), [str(rows[1].id)]
        )

        assert neighbours == []

    async def test_non_uuid_seeds_are_ignored(self, db_session, create_test_user):
        user = await create_test_user(email="expand-c@test.com")
        neighbours = await expand_evidence_via_graph(
            db_session, str(user.id), ["structure:not-a-chunk-id", ""]
        )
        assert neighbours == []

    async def test_expansion_is_bounded_and_deterministic(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="expand-d@test.com")
        chunks = [
            {
                "index": index,
                "content": f"Paragraph {index} about calibration.",
                "page": 1 + index,
                "heading_path": ["Reference Manual", f"Section {index}"],
                "section": f"Section {index}",
            }
            for index in range(20)
        ]
        doc, rows = await create_document_with_chunks(db_session, user.id, chunks=chunks)
        await replace_document_graph(db_session, doc.id, views_for(rows))
        await db_session.flush()

        first = await expand_evidence_via_graph(db_session, str(user.id), [str(rows[5].id)])
        second = await expand_evidence_via_graph(db_session, str(user.id), [str(rows[5].id)])

        assert len(first) <= GRAPH_EXPANSION_MAX_NEIGHBOURS
        assert [n.chunk_id for n in first] == [n.chunk_id for n in second]
        # Nearest reading-order neighbours first, then the rest by relation.
        assert first[0].chunk_id in (str(rows[4].id), str(rows[6].id))
