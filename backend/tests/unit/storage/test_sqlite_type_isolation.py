"""Regression tests for SQLite type compatibility.

The test suite used to monkey-patch the shared production SQLAlchemy column
types (``postgresql.UUID`` -> a String shim, ``postgresql.JSONB`` -> ``JSON``)
in ``tests/conftest.py``.  Because those ``Column`` objects live on
``storage.database.Base.metadata``, the mutation leaked into every later test
in the same pytest process, so a real PostgreSQL test saw altered metadata and
the suite became import/collection-order dependent.

These tests pin the replacement contract:

* SQLite type compatibility comes from a dialect-scoped DDL rule, not from
  rewriting the production metadata.
* The production metadata still exposes genuine PostgreSQL types after SQLite
  DDL has been executed.
* UUID primary keys, UUID foreign keys (including the self-referential
  ``document_structure_elements.parent_id``) and JSONB values round-trip
  through the SQLite fixtures as real Python objects.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import DatabaseError, StatementError
from sqlalchemy.schema import CreateTable

from auth.models import User
from graph.models import DocumentStructureElement
from reliability.models import ReliabilityLog
from storage.database import Base


def _pg_typed_columns():
    """Return the production columns that still carry PG-only types."""
    uuids, jsonbs = set(), set()
    for table in Base.metadata.sorted_tables:
        for col in table.columns:
            if isinstance(col.type, postgresql.UUID):
                uuids.add(f"{table.name}.{col.name}")
            elif isinstance(col.type, postgresql.JSONB):
                jsonbs.add(f"{table.name}.{col.name}")
    return uuids, jsonbs


def test_sqlite_ddl_does_not_mutate_production_metadata(_create_tables):
    """Running SQLite DDL must leave ``Base.metadata`` on the production types."""
    uuids, jsonbs = _pg_typed_columns()

    # Exact set, deliberately: a new PG-only JSONB column must be a conscious
    # change here, not a silent one.  ``generation_json`` was added by migration
    # 008 for the additive generative answer path (nullable; extractive rows
    # leave it NULL).
    assert jsonbs == {
        "reliability_logs.sources_json",
        "reliability_logs.generation_json",
        "chat_messages.evidence_metadata",
    }
    # 32 before per-page extraction provenance; migration 009 added its two
    # UUID columns, and migration 013 added sixteen owner-scoped KG columns
    # across entities, mentions, relations and extraction status.
    assert len(uuids) == 50
    assert "users.id" in uuids
    assert "documents.user_id" in uuids
    assert "document_structure_elements.parent_id" in uuids
    assert "document_page_extractions.id" in uuids
    assert "document_page_extractions.document_id" in uuids
    assert "kg_entities.user_id" in uuids
    assert "kg_entity_mentions.source_chunk_id" in uuids
    assert "kg_relations.subject_mention_id" in uuids
    assert "kg_extraction_status.document_id" in uuids


def test_jsonb_renders_as_json_only_for_sqlite():
    """The JSONB DDL rule is dialect-scoped: PostgreSQL keeps ``JSONB``."""
    table = Base.metadata.tables["reliability_logs"]

    sqlite_ddl = str(
        CreateTable(table).compile(dialect=sqlite.dialect())
    ).replace("\n", " ")
    pg_ddl = str(
        CreateTable(table).compile(dialect=postgresql.dialect())
    ).replace("\n", " ")

    assert "sources_json JSON" in sqlite_ddl
    assert "JSONB" not in sqlite_ddl
    assert "sources_json JSONB" in pg_ddl


def test_uuid_columns_render_natively_on_postgres_only():
    """UUID stays native on PostgreSQL and is emulated as CHAR(32) on SQLite."""
    table = Base.metadata.tables["users"]

    sqlite_ddl = str(
        CreateTable(table).compile(dialect=sqlite.dialect())
    ).replace("\n", " ")
    pg_ddl = str(
        CreateTable(table).compile(dialect=postgresql.dialect())
    ).replace("\n", " ")

    assert "id CHAR(32) NOT NULL" in sqlite_ddl
    assert "id UUID NOT NULL" in pg_ddl


async def test_canonical_uuid_string_binds_like_postgresql(db_session, create_test_user):
    """Production passes ``str(id)`` into UUID comparisons; SQLite must too.

    PostgreSQL accepts a canonical UUID string for a ``uuid`` column, and
    ``reliability/routes.py`` and ``chat/routes.py`` rely on that.  A malformed
    string must still be rejected, exactly as PostgreSQL rejects it.
    """
    from sqlalchemy import select

    from auth.models import User

    user = await create_test_user(email="string-bind@example.com")

    found = (
        await db_session.execute(
            select(User).where(User.id == str(user.id))
        )
    ).scalar_one_or_none()
    assert found is not None and found.id == user.id

    with pytest.raises(StatementError):
        await db_session.execute(
            select(User).where(User.id == "semantic-irrelevant")
        )
    await db_session.rollback()


async def test_uuid_and_jsonb_round_trip_through_sqlite(db_session):
    """UUID PK/FK identity and JSONB values survive a real SQLite round-trip."""
    user_id, document_id = uuid.uuid4(), uuid.uuid4()

    from documents.models import Document

    db_session.add(
        User(
            id=user_id,
            email="isolation@example.com",
            name="Isolation",
            hashed_password="x",
            is_active=True,
        )
    )
    db_session.add(
        Document(
            id=document_id,
            user_id=user_id,
            name="isolation.pdf",
            file_type="pdf",
            file_size=1,
            stored_path="uploads/isolation.pdf",
            status="uploaded",
        )
    )
    await db_session.commit()

    # UUID primary key read back by uuid.UUID, plus ORM identity/refresh.
    user = await db_session.get(User, user_id)
    assert user is not None
    assert isinstance(user.id, uuid.UUID) and user.id == user_id
    await db_session.refresh(user)

    document = await db_session.get(Document, document_id)
    assert isinstance(document.user_id, uuid.UUID) and document.user_id == user_id

    # Self-referential UUID foreign key.
    root = DocumentStructureElement(
        id=uuid.uuid4(),
        document_id=document_id,
        element_type="section",
        sequence_index=0,
        content="root",
    )
    db_session.add(root)
    await db_session.commit()

    child = DocumentStructureElement(
        id=uuid.uuid4(),
        document_id=document_id,
        parent_id=root.id,
        element_type="section",
        sequence_index=1,
        content="child",
    )
    db_session.add(child)
    await db_session.commit()

    loaded = await db_session.get(DocumentStructureElement, child.id)
    assert loaded.parent_id == root.id

    # JSONB column round-trips as a Python structure, not a raw string.
    payload = {"sources": [{"document_id": str(document_id), "score": 0.5}]}
    db_session.add(
        ReliabilityLog(id=uuid.uuid4(), user_id=user_id, sources_json=payload)
    )
    await db_session.commit()

    row = (
        await db_session.execute(
            ReliabilityLog.__table__.select().where(
                ReliabilityLog.__table__.c.user_id == user_id
            )
        )
    ).one()
    assert row.sources_json == payload

    # The default primary key is a real UUID, not a string blob.
    assert isinstance(root.id, uuid.UUID)

    # The created SQLite schema declares the emulated CHAR(32) UUID type, and
    # ``ON DELETE CASCADE`` / FK enforcement is active (the removed patch used
    # to rewrite ``col._user_defined_foreign_key`` to keep this working).
    info = await db_session.execute(
        text("PRAGMA table_info(document_structure_elements)")
    )
    declared = {row[1]: row[2] for row in info}
    assert declared["id"] == "CHAR(32)"
    assert declared["parent_id"] == "CHAR(32)"

    with pytest.raises(DatabaseError) as excinfo:
        db_session.add(
            DocumentStructureElement(
                id=uuid.uuid4(),
                document_id=document_id,
                parent_id=uuid.uuid4(),  # no such element
                element_type="section",
                sequence_index=2,
                content="orphan",
            )
        )
        await db_session.commit()
    assert "FOREIGN KEY constraint failed" in str(excinfo.value)
    await db_session.rollback()
