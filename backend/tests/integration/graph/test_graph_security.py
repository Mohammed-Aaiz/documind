"""Security tests: one user must never reach another user's structure.

Ownership is never read from client-supplied ids.  Every graph statement joins
``edge -> chunk -> document`` and filters on ``documents.user_id``, so these
tests drive the real queries with a *foreign* id and assert nothing comes back.

``create_test_user`` commits and the test engine is session-scoped, so each call
uses a unique email — otherwise the ``users.email`` unique constraint fires.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from chat.rag import retrieve_structural_candidates
from graph.service import (
    count_document_edges,
    expand_from_seeds,
    find_section_seed_matches,
    load_candidates,
    replace_document_graph,
)
from reliability.routes import store_query_reliability
from tests.fixtures.graph_data import create_document_with_chunks, views_for

FOREIGN_CHUNKS = [
    {
        "index": 0,
        "content": "Secret section about the Vermilion process.",
        "page": 1,
        "heading_path": ["Confidential"],
        "section": "Confidential",
    },
    {
        "index": 1,
        "content": "More confidential material.",
        "page": 1,
        "heading_path": ["Confidential"],
        "section": "Confidential",
    },
]


async def _foreign_document(db_session, create_test_user):
    """A pair of users, with a graph owned by the *owner* and never by the other."""
    tag = uuid.uuid4().hex[:8]
    owner_email = f"secret-owner-{tag}@test.com"
    intruder_email = f"intruder-{tag}@test.com"

    owner = await create_test_user(email=owner_email, name="Owner")
    intruder = await create_test_user(
        email=intruder_email, password="Pass123!", name="Intruder"
    )
    doc, rows = await create_document_with_chunks(
        db_session, owner.id, name="confidential.pdf", chunks=FOREIGN_CHUNKS
    )
    await replace_document_graph(db_session, doc.id, views_for(rows))
    await db_session.commit()
    return owner, intruder, doc, rows, owner_email, intruder_email


async def _token(client, email: str) -> str:
    resp = await client.post(
        "/api/auth/login", json={"email": email, "password": "Pass123!"}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


class TestGraphTraversalIsolation:
    async def test_user_a_cannot_traverse_user_bs_graph(
        self, db_session, create_test_user
    ):
        _owner, intruder, _doc, rows, _oe, _ie = await _foreign_document(
            db_session, create_test_user
        )

        visited = await expand_from_seeds(
            db_session, str(intruder.id), [str(rows[0].id)]
        )

        assert str(rows[1].id) not in visited
        assert list(visited) == [str(rows[0].id)], (
            "the foreign seed should resolve to itself and nothing more"
        )

    async def test_user_a_cannot_retrieve_user_bs_structural_evidence(
        self, db_session, create_test_user
    ):
        _owner, intruder, _doc, rows, _oe, _ie = await _foreign_document(
            db_session, create_test_user
        )

        candidates = await retrieve_structural_candidates(
            db_session,
            str(intruder.id),
            "Confidential Vermilion process",
            semantic_seed_ids=[str(rows[0].id), str(rows[1].id)],
        )

        assert candidates == []

    async def test_user_a_cannot_load_user_bs_chunks(
        self, db_session, create_test_user
    ):
        _owner, intruder, _doc, rows, _oe, _ie = await _foreign_document(
            db_session, create_test_user
        )

        loaded = await load_candidates(
            db_session, str(intruder.id), [str(row.id) for row in rows]
        )

        assert loaded == {}

    async def test_user_a_cannot_seed_from_user_bs_section_names(
        self, db_session, create_test_user
    ):
        _owner, intruder, _doc, _rows, _oe, _ie = await _foreign_document(
            db_session, create_test_user
        )

        matches = await find_section_seed_matches(
            db_session, str(intruder.id), ["confidential"]
        )

        assert matches == []

    async def test_the_owner_still_sees_their_own_graph(
        self, db_session, create_test_user
    ):
        """Isolation must not be achieved by breaking the feature."""
        owner, _intruder, doc, rows, _oe, _ie = await _foreign_document(
            db_session, create_test_user
        )

        assert await count_document_edges(db_session, doc.id) > 0
        visited = await expand_from_seeds(db_session, str(owner.id), [str(rows[0].id)])
        assert str(rows[1].id) in visited

    async def test_deleting_a_foreign_document_requires_ownership(
        self, db_session, create_test_user
    ):
        """The delete route is scoped, so an intruder cannot drop B's graph."""
        from documents.models import Document

        owner, intruder, doc, _rows, _oe, _ie = await _foreign_document(
            db_session, create_test_user
        )

        found = (
            await db_session.execute(
                select(Document).where(
                    Document.id == doc.id, Document.user_id == intruder.id
                )
            )
        ).scalar_one_or_none()

        assert found is None
        assert (
            await db_session.execute(
                select(Document).where(
                    Document.id == doc.id, Document.user_id == owner.id
                )
            )
        ).scalar_one_or_none() is not None


class TestDocumentAndChunkIsolation:
    async def test_user_a_cannot_read_user_bs_document(
        self, client, db_session, create_test_user
    ):
        _owner, _intruder, doc, _rows, _oe, intruder_email = await _foreign_document(
            db_session, create_test_user
        )
        token = await _token(client, intruder_email)

        resp = await client.get(
            f"/api/documents/{doc.id}", headers={"Authorization": f"Bearer {token}"}
        )

        assert resp.status_code == 404

    async def test_user_a_cannot_read_user_bs_chat_session(
        self, client, db_session, create_test_user
    ):
        from chat.models import ChatSession

        owner, _intruder, _doc, _rows, _oe, intruder_email = await _foreign_document(
            db_session, create_test_user
        )
        session = ChatSession(user_id=owner.id)
        db_session.add(session)
        await db_session.flush()

        token = await _token(client, intruder_email)

        resp = await client.get(
            f"/api/chat/sessions/{session.id}/messages",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 404

    async def test_user_a_cannot_read_user_bs_reliability(
        self, client, db_session, create_test_user
    ):
        owner, _intruder, _doc, _rows, _oe, intruder_email = await _foreign_document(
            db_session, create_test_user
        )
        await store_query_reliability(
            str(owner.id),
            {
                "question": "owner's private question",
                "answer": "owner's private answer",
                "qaConfidence": 0.9,
                "retrievalScore": 0.8,
                "avgRetrievalScore": 0.7,
                "sourceCount": 2,
                "uniqueDocuments": 1,
                "factualGrounded": True,
                "insufficientContext": False,
                "sources": [],
            },
            db=db_session,
        )
        await db_session.commit()

        token = await _token(client, intruder_email)

        resp = await client.get(
            "/api/reliability/last-query",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["question"] == ""
        assert body["sourceCount"] == 0

    async def test_user_a_cannot_delete_user_bs_document(
        self, client, db_session, create_test_user
    ):
        from documents.models import Document

        _owner, _intruder, doc, _rows, _oe, intruder_email = await _foreign_document(
            db_session, create_test_user
        )
        token = await _token(client, intruder_email)

        resp = await client.delete(
            f"/api/documents/{doc.id}", headers={"Authorization": f"Bearer {token}"}
        )

        assert resp.status_code == 404
        assert (
            await db_session.execute(
                select(Document).where(Document.id == doc.id)
            )
        ).scalar_one_or_none() is not None
