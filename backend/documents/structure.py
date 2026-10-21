"""Persist the structure-aware parser output into ``document_structure_elements``.

This is the **integration layer** between the database-independent parser
(:mod:`documents.parser`) and the ORM.  The parser itself stays free of
persistence; everything that touches the database lives here.

Mapping
-------
One ``ParsedElement`` becomes one ``DocumentStructureElement``:

====================== =========================
``ParsedElement``      ``DocumentStructureElement``
====================== =========================
``element_type``       ``element_type``
``sequence_index``     ``sequence_index``  (exact, never regenerated)
``page_number``        ``page_number``
``heading_level``      ``heading_level``
``heading_path``       ``heading_path``
``content``            ``content``
``bbox_x0/y0/x1/y1``   ``bbox_x0/y0/x1/y1``
``parent_source_id``   ``parent_id``  (resolved, see below)
(none)                 ``parser_version``  (from ``ParsedDocument``)
====================== =========================

``document_id`` is set from the caller-supplied document and the UUID primary
key is database-generated (``uuid.uuid4``), never derived from parser ordering.
The parser's ``source_id`` has no column in the schema, so it is used **only**
as an ingestion-local key for parent resolution and is discarded afterwards —
no schema change is made for it.

Parent resolution
-----------------
``ParsedElement.parent_source_id`` is a parser-local reference, not a database
UUID.  Elements are inserted with ``parent_id = NULL``, the parser
``source_id -> ORM element`` map is built in memory, and then each
``parent_id`` is set from that map.  A parent reference that does not resolve
is rejected with :class:`ParserValidationError` rather than silently dropped.

Atomicity
---------
The whole replace runs inside a ``SAVEPOINT`` (``db.begin_nested()``): the old
structure rows for the document are deleted and the new ones inserted in one
nested transaction.  If anything fails, the savepoint rolls back, so a failed
processing run can never leave partially persisted structure elements — and the
outer processing transaction is not disturbed.

Row evidence (``document_table_rows``)
--------------------------------------
The same savepoint also replaces the document's compact table-row evidence,
projected by :mod:`documents.tables` from the parser's ``table_data``.  This is
purely additive: the element stream above is unchanged (one aggregate ``table``
element, same ``sequence_index`` values, same ordering), and rows point at the
element that was just inserted for each table's ``source_id``.  Deleting the
old elements already cascades the old rows away; the explicit delete keeps the
replace deterministic even on a database that does not enforce the cascade, and
``(document_id, table_element_id, row_index)`` being unique makes duplicate rows
impossible.  A document with no tables simply persists no rows.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from documents.models import DocumentTableRow
from documents.parser import ParsedDocument, ParserValidationError
from documents.tables import table_rows_by_source_id
from graph.models import DocumentStructureElement


def _as_uuid(value: object) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


async def replace_document_structure(
    db: AsyncSession,
    document_id: uuid.UUID | str,
    parsed: ParsedDocument,
) -> dict[str, DocumentStructureElement]:
    """Replace a document's persisted structural elements with ``parsed``.

    Deletes the document's existing ``document_structure_elements`` (cascade
    removes any edges that referenced them) and inserts the parser result, then
    replaces the document's compact table-row evidence (``document_table_rows``)
    for every table element.  Returns the ``source_id -> ORM element`` map used
    for parent resolution, so a caller can (later) derive graph edges without
    re-querying.

    The caller owns the transaction; this function only flushes, so the
    structure rows commit or roll back together with the rest of the document's
    processing.  On any failure the nested transaction rolls back and no
    partial structure rows remain.

    Raises :class:`ParserValidationError` if a parent reference does not resolve
    to another element in the same parsed document.
    """
    doc_uuid = _as_uuid(document_id)

    async with db.begin_nested():
        # 1. Remove stale structure rows for this document only.  The FK
        #    cascade also clears document_structure_edges and
        #    document_table_rows that referenced them.  Row evidence is deleted
        #    explicitly too, so a reprocess cannot retain stale rows even on a
        #    database that does not enforce the cascade.
        await db.execute(
            delete(DocumentTableRow).where(DocumentTableRow.document_id == doc_uuid)
        )
        await db.execute(
            delete(DocumentStructureElement).where(
                DocumentStructureElement.document_id == doc_uuid
            )
        )
        await db.flush()

        # 2. Insert every element first, without parent links, so each ORM
        #    object has its own primary key before hierarchy is resolved.
        by_source: dict[str, DocumentStructureElement] = {}
        elements: list[DocumentStructureElement] = []
        for parsed_element in parsed.elements:
            obj = DocumentStructureElement(
                id=uuid.uuid4(),
                document_id=doc_uuid,
                parent_id=None,
                element_type=parsed_element.element_type,
                sequence_index=parsed_element.sequence_index,
                page_number=parsed_element.page_number,
                heading_level=parsed_element.heading_level,
                heading_path=(
                    list(parsed_element.heading_path)
                    if parsed_element.heading_path
                    else None
                ),
                content=parsed_element.content,
                bbox_x0=parsed_element.bbox_x0,
                bbox_y0=parsed_element.bbox_y0,
                bbox_x1=parsed_element.bbox_x1,
                bbox_y1=parsed_element.bbox_y1,
                parser_version=parsed.parser_version,
            )
            db.add(obj)
            by_source[parsed_element.source_id] = obj
            elements.append(obj)
        await db.flush()

        # 3. Resolve parser-local parent references to database ids.
        for parsed_element, obj in zip(parsed.elements, elements):
            parent_source_id = parsed_element.parent_source_id
            if parent_source_id is None:
                continue
            parent = by_source.get(parent_source_id)
            if parent is None:
                # The parser guarantees resolution, so this is a defensive
                # guard against a contract violation rather than expected flow.
                raise ParserValidationError(
                    f"unresolved parent_source_id {parent_source_id!r} for "
                    f"element {parsed_element.source_id!r}"
                )
            obj.parent_id = parent.id
        await db.flush()

        # 4. Persist compact row evidence for every table element.  Cells come
        #    verbatim from the parser's ``table_data``; nothing is derived here
        #    (see documents/tables.py).  Elements with no usable rows are
        #    skipped, so a table the extractor could not decompose simply
        #    contributes no row evidence.
        for source_id, records in table_rows_by_source_id(parsed).items():
            element = by_source.get(source_id)
            if element is None:
                # Unreachable: every element was inserted in step 2.  Guarded
                # rather than assumed so a contract violation can never attach
                # evidence to the wrong row.
                raise ParserValidationError(
                    f"cannot persist table rows: source_id {source_id!r} has no "
                    "persisted element"
                )
            for record in records:
                db.add(
                    DocumentTableRow(
                        id=uuid.uuid4(),
                        document_id=doc_uuid,
                        table_element_id=element.id,
                        row_index=record.row_index,
                        is_header=record.is_header,
                        header_repeated=record.header_repeated,
                        cells=list(record.cells),
                        content=record.content,
                        page_number=element.page_number,
                        heading_path=(
                            list(element.heading_path)
                            if element.heading_path
                            else None
                        ),
                        section=(
                            element.heading_path[-1] if element.heading_path else None
                        ),
                        token_count=record.token_count,
                        parser_version=parsed.parser_version,
                    )
                )
        await db.flush()

    return by_source


__all__ = ["replace_document_structure"]
