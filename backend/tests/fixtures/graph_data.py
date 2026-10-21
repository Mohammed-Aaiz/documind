"""Shared builders for the structural-graph tests.

Owned by the test layer.  Not production code.
"""

from __future__ import annotations

import uuid
from typing import Sequence

from documents.models import Document, DocumentChunk
from graph.service import ChunkView


async def create_document_with_chunks(
    db,
    user_id,
    *,
    name: str = "graph-doc.pdf",
    chunks: Sequence[dict],
    status: str = "ready",
    embedding_status: str = "ready",
) -> tuple[Document, list[DocumentChunk]]:
    """Insert one document plus its chunks.

    ``chunks`` entries accept ``content`` (required), ``page``,
    ``heading_path``, ``section``, ``element_type``, ``index``,
    ``chunker_version`` and ``token_count``.  Embeddings are left NULL: the
    graph and the SQL-side retrieval logic never read them.
    """
    doc = Document(
        id=uuid.uuid4(),
        user_id=user_id,
        name=name,
        file_type="pdf",
        file_size=1024,
        stored_path=f"uploads/{user_id}/{name}",
        status=status,
        embedding_status=embedding_status,
        chunk_count=len(chunks),
    )
    db.add(doc)
    await db.flush()

    rows: list[DocumentChunk] = []
    for position, spec in enumerate(chunks):
        row = DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            chunk_index=int(spec.get("index", position)),
            content=spec["content"],
            page=spec.get("page"),
            heading_path=spec.get("heading_path"),
            section=spec.get("section"),
            element_type=spec.get("element_type", "paragraph"),
            chunker_version=spec.get("chunker_version", "chunk-v2-structure-tokens"),
            token_count=spec.get("token_count", 12),
        )
        db.add(row)
        rows.append(row)

    await db.flush()
    return doc, rows


def views_for(rows: Sequence[DocumentChunk]) -> list[ChunkView]:
    """Structural views of persisted chunks, in document order."""
    return [
        ChunkView(
            chunk_id=str(row.id),
            index=row.chunk_index,
            page=row.page,
            heading_path=tuple(row.heading_path) if row.heading_path else None,
        )
        for row in sorted(rows, key=lambda r: r.chunk_index)
    ]


async def create_test_user(db, email: str, *, name: str = "Graph User"):
    """Insert a user directly (the conftest factory is a fixture; this is not)."""
    import uuid as _uuid

    from auth.models import User
    from passlib.context import CryptContext

    user = User(
        id=_uuid.uuid4(),
        email=email,
        name=name,
        hashed_password=CryptContext(schemes=["bcrypt"], deprecated="auto").hash(
            "Pass123!"
        ),
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user
