"""Add owner-scoped entity/relation evidence and extraction status.

Revision ID: 013
Revises: 012
Create Date: 2026-10-27

All structures are additive. Existing documents, chunks, and messages remain
unchanged. Composite foreign keys keep graph nodes and evidence within one
authenticated owner's documents.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_documents_owner_id", "documents", ["user_id", "id"]
    )
    op.create_unique_constraint(
        "uq_document_chunks_document_id", "document_chunks", ["document_id", "id"]
    )

    op.create_table(
        "kg_entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("normalized_name", sa.String(length=512), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "normalized_name", "entity_type",
            name="uq_kg_entities_owner_name_type",
        ),
        sa.UniqueConstraint("user_id", "id", name="uq_kg_entities_owner_id"),
    )
    op.create_index(
        "ix_kg_entities_owner_normalized", "kg_entities", ["user_id", "normalized_name"]
    )

    op.create_table(
        "kg_entity_mentions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mention_text", sa.String(length=512), nullable=False),
        sa.Column("extractor_model", sa.String(length=128), nullable=False),
        sa.Column("extractor_version", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "entity_id"],
            ["kg_entities.user_id", "kg_entities.id"],
            ondelete="CASCADE",
            name="fk_kg_mentions_entity_owner",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "document_id"],
            ["documents.user_id", "documents.id"],
            ondelete="CASCADE",
            name="fk_kg_mentions_document_owner",
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "source_chunk_id"],
            ["document_chunks.document_id", "document_chunks.id"],
            ondelete="CASCADE",
            name="fk_kg_mentions_source_chunk_document",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "document_id", "source_chunk_id", "id",
            name="uq_kg_mentions_scoped_id",
        ),
        sa.UniqueConstraint(
            "document_id", "source_chunk_id", "entity_id", "mention_text",
            name="uq_kg_mentions_chunk_entity_text",
        ),
    )
    op.create_index(
        "ix_kg_mentions_owner_entity", "kg_entity_mentions", ["user_id", "entity_id"]
    )
    op.create_index(
        "ix_kg_mentions_document_chunk",
        "kg_entity_mentions",
        ["document_id", "source_chunk_id"],
    )

    op.create_table(
        "kg_relations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_mention_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_mention_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("predicate", sa.String(length=128), nullable=False),
        sa.Column("normalized_predicate", sa.String(length=128), nullable=False),
        sa.Column("evidence_quote", sa.Text(), nullable=False),
        sa.Column("extractor_model", sa.String(length=128), nullable=False),
        sa.Column("extractor_version", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "document_id"],
            ["documents.user_id", "documents.id"],
            ondelete="CASCADE",
            name="fk_kg_relations_document_owner",
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "source_chunk_id"],
            ["document_chunks.document_id", "document_chunks.id"],
            ondelete="CASCADE",
            name="fk_kg_relations_source_chunk_document",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "document_id", "source_chunk_id", "subject_mention_id"],
            [
                "kg_entity_mentions.user_id",
                "kg_entity_mentions.document_id",
                "kg_entity_mentions.source_chunk_id",
                "kg_entity_mentions.id",
            ],
            ondelete="CASCADE",
            name="fk_kg_relations_subject_mention_scope",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "document_id", "source_chunk_id", "object_mention_id"],
            [
                "kg_entity_mentions.user_id",
                "kg_entity_mentions.document_id",
                "kg_entity_mentions.source_chunk_id",
                "kg_entity_mentions.id",
            ],
            ondelete="CASCADE",
            name="fk_kg_relations_object_mention_scope",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "source_chunk_id",
            "subject_mention_id",
            "object_mention_id",
            "normalized_predicate",
            name="uq_kg_relations_chunk_triple",
        ),
    )
    op.create_index(
        "ix_kg_relations_owner_subject", "kg_relations", ["user_id", "subject_mention_id"]
    )
    op.create_index(
        "ix_kg_relations_owner_object", "kg_relations", ["user_id", "object_mention_id"]
    )
    op.create_index(
        "ix_kg_relations_document_chunk", "kg_relations", ["document_id", "source_chunk_id"]
    )

    op.create_table(
        "kg_extraction_status",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("extractor_model", sa.String(length=128), nullable=True),
        sa.Column("extractor_version", sa.String(length=64), nullable=True),
        sa.Column("processed_chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "document_id"],
            ["documents.user_id", "documents.id"],
            ondelete="CASCADE",
            name="fk_kg_extraction_document_owner",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", name="uq_kg_extraction_document"),
        sa.CheckConstraint(
            "status IN ('pending', 'ready', 'partial', 'unavailable')",
            name="ck_kg_extraction_status",
        ),
        sa.CheckConstraint(
            "processed_chunk_count >= 0", name="ck_kg_extraction_chunk_count"
        ),
    )
    op.create_index(
        "ix_kg_extraction_owner_status",
        "kg_extraction_status",
        ["user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_kg_extraction_owner_status", table_name="kg_extraction_status")
    op.drop_table("kg_extraction_status")
    op.drop_index("ix_kg_relations_document_chunk", table_name="kg_relations")
    op.drop_index("ix_kg_relations_owner_object", table_name="kg_relations")
    op.drop_index("ix_kg_relations_owner_subject", table_name="kg_relations")
    op.drop_table("kg_relations")
    op.drop_index("ix_kg_mentions_document_chunk", table_name="kg_entity_mentions")
    op.drop_index("ix_kg_mentions_owner_entity", table_name="kg_entity_mentions")
    op.drop_table("kg_entity_mentions")
    op.drop_index("ix_kg_entities_owner_normalized", table_name="kg_entities")
    op.drop_table("kg_entities")
    op.drop_constraint(
        "uq_document_chunks_document_id", "document_chunks", type_="unique"
    )
    op.drop_constraint("uq_documents_owner_id", "documents", type_="unique")
