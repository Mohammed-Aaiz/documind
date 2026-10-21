"""Integration tests for structural graph construction during ingestion.

Exercises the real persistence path against the test database: graph build,
delete-then-rebuild (which is what makes reprocessing correct), uniqueness of
relation triples on a rebuild, and cascade deletion of edges when a document is
removed.
"""

from __future__ import annotations

from sqlalchemy import func, select

from documents.models import Document, DocumentChunk
from graph.models import DocumentGraphEdge
from graph.service import (
    RELATION_NEXT,
    count_document_edges,
    replace_document_graph,
)
from tests.fixtures.graph_data import create_document_with_chunks, views_for


async def _edge_rows(db, document_id):
    result = await db.execute(
        select(DocumentGraphEdge).where(DocumentGraphEdge.document_id == document_id)
    )
    return list(result.scalars().all())


CHAPTERS = [
    {
        "index": 0,
        "content": "Introduction to the handbook.",
        "page": 1,
        "heading_path": ["Handbook", "Introduction"],
        "section": "Introduction",
    },
    {
        "index": 1,
        "content": "Tools list.",
        "page": 1,
        "heading_path": ["Handbook", "Tools"],
        "section": "Tools",
    },
    {
        "index": 2,
        "content": "Safety notes.",
        "page": 2,
        "heading_path": ["Handbook", "Safety"],
        "section": "Safety",
    },
]


class TestGraphBuild:
    async def test_edges_are_created_for_an_ordered_document(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="ingest-a@test.com")
        doc, rows = await create_document_with_chunks(
            db_session, user.id, chunks=CHAPTERS
        )

        created = await replace_document_graph(db_session, doc.id, views_for(rows))

        assert created > 0
        assert await count_document_edges(db_session, doc.id) == created

    async def test_reading_order_edges_are_present(self, db_session, create_test_user):
        user = await create_test_user(email="ingest-b@test.com")
        doc, rows = await create_document_with_chunks(
            db_session, user.id, chunks=CHAPTERS
        )
        await replace_document_graph(db_session, doc.id, views_for(rows))

        edges = {(str(e.source_chunk_id), str(e.target_chunk_id), e.relation) for e in await _edge_rows(db_session, doc.id)}

        assert (str(rows[0].id), str(rows[1].id), RELATION_NEXT) in edges
        assert (str(rows[1].id), str(rows[2].id), RELATION_NEXT) in edges

    async def test_every_edge_points_at_a_real_chunk_of_the_same_document(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="ingest-c@test.com")
        doc, rows = await create_document_with_chunks(
            db_session, user.id, chunks=CHAPTERS
        )
        await replace_document_graph(db_session, doc.id, views_for(rows))

        chunk_ids = {str(row.id) for row in rows}
        for edge in await _edge_rows(db_session, doc.id):
            assert str(edge.document_id) == str(doc.id)
            assert str(edge.source_chunk_id) in chunk_ids
            assert str(edge.target_chunk_id) in chunk_ids


class TestRebuild:
    async def test_rebuild_replaces_rather_than_appends(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="rebuild-a@test.com")
        doc, rows = await create_document_with_chunks(
            db_session, user.id, chunks=CHAPTERS
        )

        first = await replace_document_graph(db_session, doc.id, views_for(rows))
        second = await replace_document_graph(db_session, doc.id, views_for(rows))

        assert first == second, "rebuild changed the edge count"
        assert await count_document_edges(db_session, doc.id) == first, (
            "rebuild appended edges instead of replacing them"
        )

    async def test_rebuild_does_not_duplicate_relation_triples(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="rebuild-b@test.com")
        doc, rows = await create_document_with_chunks(
            db_session, user.id, chunks=CHAPTERS
        )
        await replace_document_graph(db_session, doc.id, views_for(rows))
        await replace_document_graph(db_session, doc.id, views_for(rows))

        edges = await _edge_rows(db_session, doc.id)
        triples = [
            (str(e.source_chunk_id), str(e.target_chunk_id), e.relation) for e in edges
        ]

        assert len(triples) == len(set(triples))

    async def test_reprocessing_with_new_chunks_leaves_no_stale_edges(
        self, db_session, create_test_user
    ):
        """Old chunk ids must not survive a rebuild with a different chunking."""
        user = await create_test_user(email="rebuild-c@test.com")
        doc, old_rows = await create_document_with_chunks(
            db_session, user.id, chunks=CHAPTERS
        )
        await replace_document_graph(db_session, doc.id, views_for(old_rows))
        old_ids = {str(row.id) for row in old_rows}

        # Reprocessing deletes the old chunks (which cascades their edges) and
        # creates new ones; the graph is then rebuilt from the new chunks only.
        for chunk in old_rows:
            await db_session.delete(chunk)
        await db_session.flush()

        assert await count_document_edges(db_session, doc.id) == 0, (
            "edges survived the deletion of their chunks"
        )

        doc2, new_rows = await create_document_with_chunks(
            db_session, user.id, name="reprocessed.pdf", chunks=CHAPTERS
        )
        await replace_document_graph(db_session, doc2.id, views_for(new_rows))

        new_edges = await _edge_rows(db_session, doc2.id)
        for edge in new_edges:
            assert str(edge.source_chunk_id) not in old_ids
            assert str(edge.target_chunk_id) not in old_ids


class TestCascade:
    async def test_deleting_a_document_removes_its_edges(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="cascade-a@test.com")
        doc, rows = await create_document_with_chunks(
            db_session, user.id, chunks=CHAPTERS
        )
        await replace_document_graph(db_session, doc.id, views_for(rows))
        assert await count_document_edges(db_session, doc.id) > 0

        await db_session.delete(doc)
        await db_session.flush()

        remaining = await db_session.execute(
            select(func.count())
            .select_from(DocumentGraphEdge)
            .where(DocumentGraphEdge.document_id == doc.id)
        )
        assert int(remaining.scalar_one()) == 0

    async def test_deleting_a_chunk_removes_its_edges(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="cascade-b@test.com")
        doc, rows = await create_document_with_chunks(
            db_session, user.id, chunks=CHAPTERS
        )
        await replace_document_graph(db_session, doc.id, views_for(rows))

        await db_session.delete(rows[1])
        await db_session.flush()

        edges = await _edge_rows(db_session, doc.id)
        assert all(
            str(edge.source_chunk_id) != str(rows[1].id)
            and str(edge.target_chunk_id) != str(rows[1].id)
            for edge in edges
        )

    async def test_deleting_a_document_removes_its_chunks(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="cascade-c@test.com")
        doc, _ = await create_document_with_chunks(db_session, user.id, chunks=CHAPTERS)

        await db_session.delete(doc)
        await db_session.flush()

        remaining = await db_session.execute(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == doc.id)
        )
        assert int(remaining.scalar_one()) == 0
        assert (await db_session.execute(
            select(func.count()).select_from(Document).where(Document.id == doc.id)
        )).scalar_one() == 0
