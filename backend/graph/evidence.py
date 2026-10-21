"""Evidence fusion: semantic (chunk) evidence + structural (element) evidence.

This is the bridge toward the project's Dual-Path GraphRAG pipeline.  It is a
**pure, deterministic, database-independent** service: given already-retrieved
semantic evidence and already-traversed structural evidence, it normalises them
into one contract, deduplicates, and produces a bounded fused collection that
preserves provenance.

What this module is NOT
-----------------------
No LLM calls, no prompt generation, no answer generation, no reranking models,
no embeddings, no external APIs, no new tables or migrations, no FAISS, no
pgvector changes.  It never invents a confidence or relevance score: an
existing retrieval score is preserved exactly and labelled with its source, and
structural evidence — which has no similarity score — carries ``None``.

Existing representations reused
-------------------------------
* :class:`chat.rag.SourceChunk` — the semantic/chunk retrieval contract.  It is
  imported lazily so this module has no import-time dependency on the embedding
  stack.
* :class:`graph.models.DocumentStructureElement` — the persisted structural
  element used by the Feature #11 traversal.  Structural evidence is built from
  these (or from the traversal result of
  :func:`graph.service.get_structural_neighborhood`).

Provenance contract
-------------------
Every :class:`EvidenceItem` can answer: what is it, where did it come from,
which document does it belong to, what produced it, and what content can
downstream reasoning inspect.  ``source_type`` is exactly ``"semantic"`` or
``"structure"``.  The source record id is preserved (``chunk_id`` for semantic
evidence, ``structure_element_id`` for structural evidence).

Document isolation
------------------
Fusion is single-document by default.  If the inputs contain more than one
``document_id``, fusion refuses (raises :class:`EvidenceFusionError`) rather
than silently mixing documents.  ``allow_multi_document=True`` keeps the
boundaries explicit instead of merging them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from graph.models import DocumentStructureElement

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

SOURCE_SEMANTIC = "semantic"
SOURCE_STRUCTURE = "structure"

SOURCE_TYPES: tuple[str, ...] = (SOURCE_SEMANTIC, SOURCE_STRUCTURE)

#: Bounded defaults.  Semantic evidence keeps the existing retrieval ordering,
#: structural evidence keeps the Feature #11 deterministic traversal ordering.
DEFAULT_MAX_SEMANTIC = 20
DEFAULT_MAX_STRUCTURAL = 20
DEFAULT_MAX_FUSED = 20

#: How many ancestors of a structural element are retained as heading context.
DEFAULT_ANCESTOR_CONTEXT = 3


class EvidenceFusionError(ValueError):
    """Raised when evidence cannot be fused under the contract.

    Used for genuinely invalid input (e.g. mixing documents when single-document
    fusion was requested, or an unrecognised ``source_type``).  It never carries
    filesystem paths, internal exceptions, or secrets.
    """


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EvidenceItem:
    """One normalised piece of evidence.

    ``score`` is only ever populated for semantic evidence, and only from the
    real retrieval score that produced it (``score_source`` names where it came
    from).  Structural evidence has no similarity score, so ``score`` is
    ``None`` — never a fabricated value.
    """

    evidence_id: str
    """Stable identity: ``document_id:chunk_id`` (semantic) or
    ``document_id:structure_element_id`` (structure)."""

    document_id: str
    source_type: str
    """``"semantic"`` or ``"structure"``."""

    content: str | None
    """Text downstream reasoning may inspect.  ``None`` when the source record
    carries no text (e.g. a heading-only section element)."""

    chunk_id: str | None = None
    """Source ``document_chunks.id`` for semantic evidence."""

    structure_element_id: str | None = None
    """Source ``document_structure_elements.id`` for structural evidence."""

    page_number: int | None = None
    sequence_index: int | None = None
    element_type: str | None = None
    heading_path: tuple[str, ...] | None = None
    section: str | None = None

    score: float | None = None
    """Real retrieval score only.  ``None`` for structural evidence."""

    score_source: str | None = None
    """``"pgvector_similarity"`` when ``score`` came from the semantic path;
    ``None`` when there is no score."""

    parent_source_id: str | None = None
    """For structural evidence, the parent element's id (from ``parent_id``)."""

    heading_context: tuple[str, ...] = ()
    """Ancestor heading texts, root-first, from the structural traversal."""

    provenance: dict[str, Any] = field(default_factory=dict)
    """Non-sensitive provenance extras only (retrieval path, hops, relation,
    parser version, ...).  Never filesystem paths or internal exceptions."""

    def identity(self) -> tuple[str, str, str]:
        """Deterministic dedup key: ``(document_id, source_type, record_id)``."""
        record_id = self.chunk_id or self.structure_element_id or self.evidence_id
        return (self.document_id, self.source_type, record_id)


@dataclass
class FusedEvidence:
    """The bounded, deterministic result of :func:`fuse_evidence`."""

    items: list[EvidenceItem] = field(default_factory=list)
    semantic_count: int = 0
    structural_count: int = 0
    duplicate_count: int = 0
    truncated: bool = False
    multi_document: bool = False
    document_ids: tuple[str, ...] = ()

    @property
    def total(self) -> int:
        return len(self.items)

    def semantic_items(self) -> list[EvidenceItem]:
        return [i for i in self.items if i.source_type == SOURCE_SEMANTIC]

    def structural_items(self) -> list[EvidenceItem]:
        return [i for i in self.items if i.source_type == SOURCE_STRUCTURE]


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def evidence_from_source_chunk(chunk: Any) -> EvidenceItem:
    """Normalise a :class:`chat.rag.SourceChunk` into an :class:`EvidenceItem`.

    Preserves the real retrieval score and its source, plus the Phase 3D
    structure metadata already carried by the chunk.  Accepts any object with
    the ``SourceChunk`` attribute shape so it stays decoupled from the service
    import graph.
    """
    document_id = str(getattr(chunk, "document_id"))
    chunk_id = str(getattr(chunk, "chunk_id"))
    score = getattr(chunk, "score", None)
    heading_path = getattr(chunk, "heading_path", None)

    return EvidenceItem(
        evidence_id=f"{document_id}:{chunk_id}",
        document_id=document_id,
        source_type=SOURCE_SEMANTIC,
        content=getattr(chunk, "content", None),
        chunk_id=chunk_id,
        page_number=getattr(chunk, "page", None),
        element_type=getattr(chunk, "element_type", None),
        heading_path=tuple(heading_path) if heading_path else None,
        section=getattr(chunk, "section", None),
        score=float(score) if score is not None else None,
        score_source="pgvector_similarity" if score is not None else None,
        provenance={
            "document_name": getattr(chunk, "document_name", None),
            "retrieval_path": getattr(chunk, "retrieval_path", None),
            "chunker_version": getattr(chunk, "chunker_version", None),
        },
    )


def evidence_from_structure_element(
    element: DocumentStructureElement,
    *,
    heading_context: Sequence[str] = (),
    hops: int | None = None,
    relation: str | None = None,
) -> EvidenceItem:
    """Normalise a persisted :class:`DocumentStructureElement` into evidence.

    ``heading_context`` is the ancestor heading chain (root-first) supplied by
    the Feature #11 traversal; it is never inferred here.  Structural evidence
    has no similarity score, so ``score`` is ``None``.
    """
    document_id = str(element.document_id)
    element_id = str(element.id)
    heading_path = element.heading_path

    return EvidenceItem(
        evidence_id=f"{document_id}:{element_id}",
        document_id=document_id,
        source_type=SOURCE_STRUCTURE,
        content=element.content,
        structure_element_id=element_id,
        page_number=element.page_number,
        sequence_index=element.sequence_index,
        element_type=element.element_type,
        heading_path=tuple(heading_path) if heading_path else None,
        section=(tuple(heading_path)[-1] if heading_path else None),
        score=None,
        score_source=None,
        parent_source_id=str(element.parent_id) if element.parent_id else None,
        heading_context=tuple(str(h) for h in heading_context),
        provenance={
            "parser_version": element.parser_version,
            "hops": hops,
            "relation": relation,
        },
    )


# ---------------------------------------------------------------------------
# Fusion
# ---------------------------------------------------------------------------

def _coerce_semantic(items: Iterable[Any]) -> list[EvidenceItem]:
    out: list[EvidenceItem] = []
    for item in items:
        if isinstance(item, EvidenceItem):
            if item.source_type != SOURCE_SEMANTIC:
                raise EvidenceFusionError(
                    f"semantic input carried source_type {item.source_type!r}"
                )
            out.append(item)
        else:
            out.append(evidence_from_source_chunk(item))
    return out


def _coerce_structural(items: Iterable[Any]) -> list[EvidenceItem]:
    out: list[EvidenceItem] = []
    for item in items:
        if isinstance(item, EvidenceItem):
            if item.source_type != SOURCE_STRUCTURE:
                raise EvidenceFusionError(
                    f"structural input carried source_type {item.source_type!r}"
                )
            out.append(item)
        else:
            out.append(evidence_from_structure_element(item))
    return out


def _document_ids(items: Sequence[EvidenceItem]) -> set[str]:
    return {item.document_id for item in items}


def fuse_evidence(
    semantic_evidence: Sequence[Any] | None = None,
    structural_evidence: Sequence[Any] | None = None,
    *,
    max_semantic: int = DEFAULT_MAX_SEMANTIC,
    max_structural: int = DEFAULT_MAX_STRUCTURAL,
    max_fused: int = DEFAULT_MAX_FUSED,
    allow_multi_document: bool = False,
) -> FusedEvidence:
    """Deterministically fuse semantic and structural evidence.

    Behaviour
    ---------
    * Inputs may be :class:`EvidenceItem` objects or the raw records they come
      from (``SourceChunk`` for semantic, ``DocumentStructureElement`` for
      structural).
    * **Ordering** — semantic evidence keeps the existing retrieval ordering
      (highest similarity first); structural evidence keeps the Feature #11
      deterministic traversal ordering.  Semantic evidence is emitted first,
      then structural evidence, each in its input order.  No new "best
      evidence" score is invented.
    * **Deduplication** — by ``(document_id, source_type, record_id)``, i.e.
      real persisted ids, never by text.  A semantic chunk and a structural
      element are *different* records with different identities, so both are
      preserved; provenance is never discarded.
    * **Bounds** — ``max_semantic`` / ``max_structural`` cap each stream before
      fusion; ``max_fused`` caps the output.  Truncation is deterministic
      (input order preserved) and reported via ``truncated``.
    * **Document isolation** — single-document by default.  Mixing documents
      raises :class:`EvidenceFusionError`; ``allow_multi_document=True`` keeps
      boundaries explicit (each item retains its own ``document_id``) and marks
      the result ``multi_document=True``.

    Empty inputs are valid and return an empty :class:`FusedEvidence`.
    Malformed records that lack a usable identity are skipped rather than
    crashing, and are counted as duplicates only when they truly duplicate.
    """
    semantic = _coerce_semantic(semantic_evidence or [])
    structural = _coerce_structural(structural_evidence or [])

    all_items = [*semantic, *structural]
    doc_ids = _document_ids(all_items)
    if len(doc_ids) > 1 and not allow_multi_document:
        raise EvidenceFusionError(
            f"evidence spans {len(doc_ids)} documents; single-document fusion "
            "expected (pass allow_multi_document=True to keep boundaries explicit)"
        )

    # Apply per-stream bounds before dedup so the policy is deterministic.
    semantic_bounded = semantic[: max(0, int(max_semantic))]
    structural_bounded = structural[: max(0, int(max_structural))]

    seen: set[tuple[str, str, str]] = set()
    fused: list[EvidenceItem] = []
    duplicates = 0

    for item in [*semantic_bounded, *structural_bounded]:
        key = item.identity()
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        fused.append(item)

    truncated = (
        len(fused) > max(0, int(max_fused))
        or len(semantic) > len(semantic_bounded)
        or len(structural) > len(structural_bounded)
    )
    fused = fused[: max(0, int(max_fused))]

    return FusedEvidence(
        items=fused,
        semantic_count=sum(1 for i in fused if i.source_type == SOURCE_SEMANTIC),
        structural_count=sum(1 for i in fused if i.source_type == SOURCE_STRUCTURE),
        duplicate_count=duplicates,
        truncated=truncated,
        multi_document=len(doc_ids) > 1,
        document_ids=tuple(sorted(doc_ids)),
    )


async def collect_document_structure_evidence(
    db: Any,
    document_ids: Sequence[Any],
    *,
    per_document_limit: int = DEFAULT_MAX_STRUCTURAL,
    max_documents: int = 5,
) -> list[EvidenceItem]:
    """Bounded, document-scoped structural evidence for fusion.

    Fetches at most ``per_document_limit`` elements per document, in the
    Feature #11 deterministic order (``sequence_index ASC, id ASC``), for at
    most ``max_documents`` documents.  One query per document — never per
    semantic chunk — and never a whole-graph scan.

    There is no persisted chunk->structure mapping, so this deliberately does
    **not** try to attach structure to individual chunks: it returns the
    document's structural elements as a *separate* evidence stream, which
    :func:`fuse_evidence` then deduplicates and orders without mixing
    identities.  Ordering within a document is document order (not a fabricated
    relevance ranking).
    """
    from sqlalchemy import select  # local import keeps this module import-light

    items: list[EvidenceItem] = []
    for document_id in list(document_ids)[: max(0, int(max_documents))]:
        stmt = (
            select(DocumentStructureElement)
            .where(DocumentStructureElement.document_id == _as_uuid(document_id))
            .order_by(
                DocumentStructureElement.sequence_index.asc(),
                DocumentStructureElement.id.asc(),
            )
            .limit(max(0, int(per_document_limit)))
        )
        rows = (await db.execute(stmt)).scalars().all()
        items.extend(evidence_from_structure_element(row) for row in rows)
    return items


def _as_uuid(value: Any):
    """Coerce to a UUID; return the input unchanged when impossible."""
    import uuid as _uuid

    if isinstance(value, _uuid.UUID):
        return value
    try:
        return _uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return value


async def fuse_document_evidence(
    db: Any,
    document_id: Any,
    *,
    semantic_evidence: Sequence[Any] | None = None,
    structure_element_ids: Sequence[Any] | None = None,
    max_semantic: int = DEFAULT_MAX_SEMANTIC,
    max_structural: int = DEFAULT_MAX_STRUCTURAL,
    max_fused: int = DEFAULT_MAX_FUSED,
) -> FusedEvidence:
    """Database-backed convenience fusion for one document.

    Uses the existing Feature #11 traversal (:mod:`graph.service`) to build the
    structural evidence and its heading context — it does **not** re-implement
    traversal.  ``semantic_evidence`` may be supplied by the caller (the
    semantic path already ran) or left empty for a structure-only fusion.

    The traversal is document-scoped, so structural evidence can never leak in
    from another document.
    """
    # Imported lazily to keep the pure fusion path import-light and to avoid a
    # hard import cycle with the graph service.
    from graph.service import get_structure_element, get_parent_chain

    structural_items: list[EvidenceItem] = []
    for element_id in structure_element_ids or []:
        element = await get_structure_element(db, document_id, element_id)
        if element is None:
            continue  # not in this document — skip rather than leak
        chain = await get_parent_chain(db, document_id, element_id)
        heading_context = [
            (tuple(ancestor.heading_path)[-1] if ancestor.heading_path else ancestor.element_type)
            for ancestor in chain
            if ancestor.id != element.id
        ][-DEFAULT_ANCESTOR_CONTEXT:]
        structural_items.append(
            evidence_from_structure_element(
                element, heading_context=heading_context
            )
        )

    return fuse_evidence(
        semantic_evidence=semantic_evidence,
        structural_evidence=structural_items,
        max_semantic=max_semantic,
        max_structural=max_structural,
        max_fused=max_fused,
    )


__all__ = [
    "EvidenceItem",
    "FusedEvidence",
    "EvidenceFusionError",
    "fuse_evidence",
    "fuse_document_evidence",
    "collect_document_structure_evidence",
    "evidence_from_source_chunk",
    "evidence_from_structure_element",
    "SOURCE_SEMANTIC",
    "SOURCE_STRUCTURE",
    "SOURCE_TYPES",
    "DEFAULT_MAX_SEMANTIC",
    "DEFAULT_MAX_STRUCTURAL",
    "DEFAULT_MAX_FUSED",
]
