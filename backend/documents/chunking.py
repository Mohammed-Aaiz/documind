"""Phase 3D — structure-aware, token-budgeted document chunking.

This module is **additive**.  The legacy chunker
(``documents/processing.py::chunk_text``, 1000 chars / 200 chars overlap)
is untouched and remains the production default until the candidate is
validated.  Both implementations are selectable at ingestion time.

Design contract (approved in Phase 3D)
--------------------------------------
Measurement
    Tokens are authoritative (see ``tokenization``); characters are a
    secondary guard.  The hard cap equals the *verified* embedding encoder
    sequence limit, because ``SentenceTransformer.encode()`` silently
    truncates anything longer and the truncated tail then becomes invisible
    to retrieval.

    Every fit decision measures the **actual concatenated chunk text**
    (heading prefix included), never a sum of per-part counts.  Token counts
    are not perfectly additive across a concatenation boundary, so summing
    could emit a chunk one or two tokens over the cap.

Grouping
    ```text
    ExtractedElement[] → group by (heading_path, page, merge_class)
                       → merge siblings within the group up to a token budget
                       → split only when a single element exceeds the budget
                       → Chunk[]
    ```

Boundaries, in precedence order:
  1. heading  — a heading always starts a new group (section boundary)
  2. page     — ``page`` is a hard boundary, so ``DocumentChunk.page`` stays
                exact for source attribution
  3. section  — merging requires identical ``heading_path``
  4. merge_class — tables never merge with anything; lists never merge with
                anything; only paragraph/text elements merge with each other
  5. sentence / list-item / table-row — split points for oversized elements
  6. hard cut — last resort, explicitly tagged

Overlap
    A bounded continuation overlap (last *complete* sentence, capped at
    ``CHUNK_OVERLAP_TOKENS``) is applied only when a single element is split,
    never across element, heading or page boundaries.  This removes the blind
    200-character duplicate windows the legacy chunker produced.

Determinism
    ``chunk_elements`` is a pure function of its inputs.  Ordering is stable
    (document order) and ``chunk_index`` is contiguous from 0.  Given the same
    ``ExtractedElement[]`` and the same counter, the output is byte-identical
    across runs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Callable, Iterable, Sequence

from documents.processing import ExtractedElement
from tokenization import count_tokens as _default_count_tokens
from tokenization import get_encoder_max_tokens, is_tokenizer_available

# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------

CHUNKER_VERSION_LEGACY = "chunk-v1-legacy-chars-1000-200"
CHUNKER_VERSION_STRUCTURE = "chunk-v2-structure-tokens"

_VERSION_ALIASES = {
    "legacy": CHUNKER_VERSION_LEGACY,
    "v1": CHUNKER_VERSION_LEGACY,
    CHUNKER_VERSION_LEGACY: CHUNKER_VERSION_LEGACY,
    "structure": CHUNKER_VERSION_STRUCTURE,
    "structure-v2": CHUNKER_VERSION_STRUCTURE,
    "v2": CHUNKER_VERSION_STRUCTURE,
    CHUNKER_VERSION_STRUCTURE: CHUNKER_VERSION_STRUCTURE,
}

# ---------------------------------------------------------------------------
# Budgets (tokens unless stated otherwise)
# ---------------------------------------------------------------------------

CHUNK_TARGET_TOKENS = 200     # aim for this when merging siblings
CHUNK_MIN_TOKENS = 40         # below this, prefer merging forward
CHUNK_MAX_TOKENS = 256        # hard cap == verified encoder sequence limit
CHUNK_OVERLAP_TOKENS = 64     # max carried sentence for split continuations
CHUNK_MAX_CHARS = 1400        # secondary guard when only chars are available

_MAX_PREFIX_FRACTION = 0.5    # heading prefix may not eat more than this share

MERGE_CLASS_TABLE = "table"
MERGE_CLASS_LIST = "list"
MERGE_CLASS_PROSE = "prose"

PARAGRAPH_JOINER = "\n\n"
LINE_JOINER = "\n"

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ChunkMeta:
    """Structure metadata carried by a chunk.

    ``source_indices``/``source_start``/``source_end`` are process-local
    provenance used for invariant testing and debugging; they are not
    persisted.  The fields that reach ``DocumentChunk`` are ``page``,
    ``heading_path``, ``section``, ``element_type``, ``chunker_version``
    and ``token_count``.
    """

    page: int | None
    heading_path: tuple[str, ...]
    section: str | None
    element_type: str
    chunker_version: str
    token_count: int
    char_count: int
    strategy: str = "merge"
    overlap_tokens: int = 0
    is_continuation: bool = False
    oversized: bool = False
    forced_cut: bool = False
    source_indices: tuple[int, ...] = ()
    source_start: int | None = None
    source_end: int | None = None
    overlap_text: str = ""

    @property
    def exact(self) -> bool:
        """True when the chunk maps to a single region of one element."""
        return len(self.source_indices) == 1 and self.source_start is not None


@dataclass(frozen=True)
class Chunk:
    """One chunk ready to be persisted as ``DocumentChunk``."""

    content: str
    meta: ChunkMeta


# ---------------------------------------------------------------------------
# Version / budget resolution
# ---------------------------------------------------------------------------

def resolve_chunker_version(value: str | None) -> str:
    """Map a configuration value onto a concrete chunker version.

    Unknown values deterministically fall back to the legacy version so a
    typo can never silently change production ingestion behaviour.
    """
    if not value:
        return CHUNKER_VERSION_LEGACY
    return _VERSION_ALIASES.get(str(value).strip().lower(), CHUNKER_VERSION_LEGACY)


def resolve_max_chunk_tokens() -> int:
    """Hard chunk cap, honouring the *verified* encoder limit when known."""
    limit = get_encoder_max_tokens()
    if isinstance(limit, int) and limit > 0:
        return min(CHUNK_MAX_TOKENS, limit)
    return CHUNK_MAX_TOKENS


def make_counter() -> Callable[[str], int]:
    """Default token counter (real tokenizer when available)."""
    return _default_count_tokens


# ---------------------------------------------------------------------------
# Segmentation (character spans, so provenance is exact)
# ---------------------------------------------------------------------------

# A boundary is a sentence terminator followed by whitespace, or a newline.
# Segment spans abut, so ''.join(text[a:b] for spans) == text exactly.
_BOUNDARY_RE = re.compile(r"(?:[.!?](?=\s))|(?:\n)")


def _segment_spans(text: str) -> list[tuple[int, int]]:
    """Character spans covering ``text`` exactly, split at soft boundaries."""
    if not text:
        return []
    bounds = [0]
    bounds.extend(m.end() for m in _BOUNDARY_RE.finditer(text))
    bounds.append(len(text))
    spans: list[tuple[int, int]] = []
    for a, b in zip(bounds, bounds[1:]):
        if b > a:
            spans.append((a, b))
    return spans


def _trim_span(text: str, a: int, b: int) -> tuple[int, int, str]:
    """Shrink ``[a, b)`` past surrounding whitespace."""
    while a < b and text[a].isspace():
        a += 1
    while b > a and text[b - 1].isspace():
        b -= 1
    return a, b, text[a:b]


# ---------------------------------------------------------------------------
# Heading prefix
# ---------------------------------------------------------------------------

def heading_prefix(heading_path: Sequence[str]) -> str:
    """Legacy-compatible heading context prefix: ``"A > B\\n\\nContent"``."""
    if not heading_path:
        return ""
    return " > ".join(heading_path) + "\n\n"


# ---------------------------------------------------------------------------
# Merge classification
# ---------------------------------------------------------------------------

def _merge_class(element_type: str) -> str:
    if element_type == "table":
        return MERGE_CLASS_TABLE
    if element_type == "list":
        return MERGE_CLASS_LIST
    return MERGE_CLASS_PROSE


def _chunk_element_type(element_types: Iterable[str]) -> str:
    """Single element type for a chunk, or ``"mixed"`` when merged across."""
    types = list(element_types)
    if not types:
        return "text"
    first = types[0]
    return first if all(t == first for t in types) else "mixed"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def chunk_elements(
    elements: list[ExtractedElement],
    *,
    version: str = CHUNKER_VERSION_STRUCTURE,
    count_tokens: Callable[[str], int] | None = None,
    max_tokens: int | None = None,
    target_tokens: int = CHUNK_TARGET_TOKENS,
    min_tokens: int = CHUNK_MIN_TOKENS,
    overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
) -> list[Chunk]:
    """Convert extracted elements into structure-aware chunks.

    Pure and deterministic: identical input and counter produce identical
    output, including ordering and ``chunker_version``.
    """
    resolved_version = resolve_chunker_version(version)
    if resolved_version != CHUNKER_VERSION_STRUCTURE:
        raise ValueError(
            "chunk_elements() implements "
            f"{CHUNKER_VERSION_STRUCTURE!r}, not {resolved_version!r}. "
            "Use documents.processing.chunk_text for the legacy strategy."
        )

    counter = count_tokens or _default_count_tokens
    cap = max_tokens or resolve_max_chunk_tokens()
    cap = max(cap, min_tokens + 1)

    builder = _Builder(
        version=resolved_version,
        counter=counter,
        max_tokens=cap,
        target_tokens=target_tokens,
        min_tokens=min_tokens,
        overlap_tokens=overlap_tokens,
    )
    return builder.build(elements)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

@dataclass
class _Builder:
    version: str
    counter: Callable[[str], int]
    max_tokens: int
    target_tokens: int
    min_tokens: int
    overlap_tokens: int
    chunks: list[Chunk] = field(default_factory=list)

    # -- fit helpers (always measure the concatenated chunk text) ---------

    def _text_of(self, prefix: str, joiner: str, parts: Sequence[str]) -> str:
        return prefix + joiner.join(parts)

    def fits(self, prefix: str, joiner: str, parts: Sequence[str]) -> bool:
        """True when ``prefix + joiner.join(parts)`` is within the hard cap."""
        if not parts:
            return True
        return self.counter(self._text_of(prefix, joiner, parts)) <= self.max_tokens

    def tokens(self, prefix: str, joiner: str, parts: Sequence[str]) -> int:
        if not parts:
            return 0
        return self.counter(self._text_of(prefix, joiner, parts))

    def _fit_prefix(self, heading_path: Sequence[str]) -> str:
        """Heading context that does not consume the whole chunk budget."""
        if not heading_path:
            return ""
        path = list(heading_path)
        limit = int(self.max_tokens * _MAX_PREFIX_FRACTION)
        while path:
            prefix = heading_prefix(path)
            if self.counter(prefix) <= limit:
                return prefix
            path = path[1:]
        return ""

    def _fit_end(self, text: str, a: int, b: int, prefix: str) -> int:
        """Largest ``end`` in ``(a, b]`` with ``counter(prefix + text[a:end])``
        within the cap.  Deterministic character binary search.
        """
        if b <= a:
            return a
        lo, hi = a + 1, b
        best = a
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.counter(prefix + text[a:mid]) <= self.max_tokens:
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1
        if best <= a:
            best = min(a + 1, b)
        while best > a + 1 and self.counter(prefix + text[a:best]) > self.max_tokens:
            best -= 1
        return best

    # -- entry ------------------------------------------------------------

    def build(self, elements: list[ExtractedElement]) -> list[Chunk]:
        group: list[tuple[int, ExtractedElement]] = []
        group_key: tuple | None = None
        pending_heading: tuple[int, ExtractedElement] | None = None

        def flush_group() -> None:
            nonlocal group, group_key
            if group:
                self._emit_group(group)
                group = []
            group_key = None

        for index, element in enumerate(elements):
            if element.element_type == "heading":
                flush_group()
                if pending_heading is not None:
                    self._emit_heading_only(pending_heading)
                pending_heading = (index, element)
                continue

            key = (
                tuple(element.heading_path or ()),
                element.page,
                _merge_class(element.element_type),
            )

            if group and key != group_key:
                flush_group()

            if not group:
                group_key = key
                if pending_heading is not None:
                    # The pending heading is this group's section context when
                    # it is the last component of the group's heading path;
                    # otherwise it headed a section with no content of its own
                    # and stays indexed as a standalone heading chunk.
                    if tuple(pending_heading[1].heading_path or ()) == key[0]:
                        pending_heading = None
                    else:
                        self._emit_heading_only(pending_heading)
                        pending_heading = None

            group.append((index, element))

        flush_group()
        if pending_heading is not None:
            self._emit_heading_only(pending_heading)

        return list(self.chunks)

    # -- group dispatch ---------------------------------------------------

    def _emit_group(self, group: list[tuple[int, ExtractedElement]]) -> None:
        merge_class = _merge_class(group[0][1].element_type)

        if merge_class == MERGE_CLASS_TABLE:
            # Tables are always atomic per element (never merged).
            for index, element in group:
                self._emit_table(index, element)
            return

        heading_path = tuple(group[0][1].heading_path or ())
        prefix = self._fit_prefix(heading_path)

        if merge_class == MERGE_CLASS_LIST:
            for index, element in group:
                self._emit_list(index, element, prefix)
            return

        self._emit_prose_group(group, prefix)

    # -- prose ------------------------------------------------------------

    def _emit_prose_group(
        self, group: list[tuple[int, ExtractedElement]], prefix: str
    ) -> None:
        pending: list[tuple[int, ExtractedElement]] = []

        def flush() -> None:
            nonlocal pending
            if pending:
                self._emit_merged(pending, prefix)
            pending = []

        for index, element in group:
            if not self.fits(prefix, PARAGRAPH_JOINER, [element.content]):
                if pending:
                    flush()
                self._split_prose(index, element, prefix)
                continue

            if not pending:
                pending = [(index, element)]
                continue

            candidate = [el.content for _, el in pending] + [element.content]
            cand_tokens = self.tokens(prefix, PARAGRAPH_JOINER, candidate)
            cur_tokens = self.tokens(
                prefix, PARAGRAPH_JOINER, [el.content for _, el in pending]
            )

            if cand_tokens <= self.target_tokens:
                pending.append((index, element))
            elif cur_tokens < self.min_tokens and cand_tokens <= self.max_tokens:
                pending.append((index, element))
            else:
                flush()
                pending = [(index, element)]

        flush()

    def _emit_merged(
        self, pending: list[tuple[int, ExtractedElement]], prefix: str
    ) -> None:
        if not pending:
            return
        contents = [el.content for _, el in pending]
        self._append(
            content=self._text_of(prefix, PARAGRAPH_JOINER, contents),
            page=pending[0][1].page,
            heading_path=tuple(pending[0][1].heading_path or ()),
            element_types=[el.element_type for _, el in pending],
            strategy="element" if len(pending) == 1 else "merge",
            source_indices=tuple(i for i, _ in pending),
            source_start=0 if len(pending) == 1 else None,
            source_end=len(contents[0]) if len(pending) == 1 else None,
        )

    def _split_prose(self, index: int, element: ExtractedElement, prefix: str) -> None:
        text = element.content
        queue = _segment_spans(text)
        if not queue:
            return

        first = True
        while queue:
            parts: list[str] = []
            used: list[tuple[int, int]] = []
            j = 0

            while j < len(queue):
                a, b = queue[j]
                _, _, piece = _trim_span(text, a, b)
                if not piece:
                    j += 1
                    continue
                if self.fits(prefix, PARAGRAPH_JOINER, parts + [piece]):
                    parts.append(piece)
                    used.append((a, b))
                    j += 1
                    continue
                if parts:
                    break
                # Single segment alone exceeds the cap: take it and hard cut.
                used.append((a, b))
                j += 1
                break

            if not used:
                break

            start, end, body = _trim_span(text, used[0][0], used[-1][1])
            forced = False

            if not self.fits(prefix, PARAGRAPH_JOINER, [body]):
                forced = True
                end = self._fit_end(text, start, end, prefix)
                body = text[start:end].strip()

            if not body:
                queue = queue[j:]
                continue

            self._append(
                content=prefix + body,
                page=element.page,
                heading_path=tuple(element.heading_path or ()),
                element_types=(element.element_type,),
                strategy="split_sentence",
                source_indices=(index,),
                source_start=start,
                source_end=end,
                forced_cut=forced,
                is_continuation=not first,
            )
            first = False

            remaining = queue[j:]

            if forced:
                # Resume exactly at the cut point so nothing is skipped.
                tail_end = used[-1][1]
                if end < tail_end:
                    remaining = [(end, tail_end)] + remaining
                queue = [span for span in remaining if span[1] > span[0]]
                continue

            if remaining and len(parts) >= 2:
                carry = parts[-1]
                carry_tokens = self.counter(carry)
                if 0 < carry_tokens <= self.overlap_tokens:
                    self.chunks[-1] = replace(
                        self.chunks[-1],
                        meta=replace(
                            self.chunks[-1].meta,
                            overlap_tokens=carry_tokens,
                            overlap_text=carry,
                        ),
                    )
                    queue = [used[-1]] + remaining
                    continue

            queue = remaining

    # -- lists ------------------------------------------------------------

    def _emit_list(self, index: int, element: ExtractedElement, prefix: str) -> None:
        """Emit one list element.

        Distinct lists are never concatenated with each other or with prose,
        so item relationships can never be broken by a merge.  Ordering and
        item integrity are preserved; an item is only cut when it alone
        exceeds the cap.
        """
        items = _list_items(element)
        if not items:
            return

        if self.fits(prefix, LINE_JOINER, [element.content]):
            self._append(
                content=prefix + element.content,
                page=element.page,
                heading_path=tuple(element.heading_path or ()),
                element_types=(element.element_type,),
                strategy="element",
                source_indices=(index,),
                source_start=0,
                source_end=len(element.content),
            )
            return

        remaining = list(items)
        first = True
        while remaining:
            parts: list[str] = []
            taken = 0

            for position, item in enumerate(remaining):
                if self.fits(prefix, LINE_JOINER, parts + [item]):
                    parts.append(item)
                    taken = position + 1
                    continue
                break

            if not parts:
                # A single item exceeds the cap: hard cut it.
                item = remaining[0]
                cut = self._fit_end(item, 0, len(item), prefix)
                self._append(
                    content=prefix + item[:cut].strip(),
                    page=element.page,
                    heading_path=tuple(element.heading_path or ()),
                    element_types=(element.element_type,),
                    strategy="split_list",
                    source_indices=(index,),
                    forced_cut=True,
                    is_continuation=not first,
                )
                first = False
                tail = item[cut:]
                remaining = ([tail] if tail.strip() else []) + remaining[1:]
                continue

            self._append(
                content=self._text_of(prefix, LINE_JOINER, parts),
                page=element.page,
                heading_path=tuple(element.heading_path or ()),
                element_types=(element.element_type,),
                strategy="split_list" if len(remaining) > taken else "element",
                source_indices=(index,),
                is_continuation=not first,
            )
            first = False
            remaining = remaining[taken:]

    # -- tables -----------------------------------------------------------

    def _emit_table(self, index: int, element: ExtractedElement) -> None:
        """Emit a table: atomic when it fits, otherwise row-stratified with the
        header row repeated in every sub-chunk.

        Header repetition is a correctness requirement, not a convenience: an
        extractive QA span such as ``92%`` is ungroundable without the column
        names, and a dense embedding of a headerless row fragment does not
        match table questions.
        """
        heading_path = tuple(element.heading_path or ())
        prefix = self._fit_prefix(heading_path)
        rows = _table_rows(element)
        if not rows:
            return

        serialized = _serialize_rows(rows)

        if self.fits(prefix, LINE_JOINER, [serialized]):
            self._append(
                content=prefix + serialized,
                page=element.page,
                heading_path=heading_path,
                element_types=(element.element_type,),
                strategy="table_atomic",
                source_indices=(index,),
                source_start=0,
                source_end=len(element.content),
            )
            return

        header = rows[0] if len(rows) > 1 else None
        body = rows[1:] if header is not None else rows
        header_row = _serialize_row(header) if header else None
        # The header is repeated, so it participates in every fit decision.
        base = [header_row] if header_row else []

        remaining = list(body)
        first = True
        oversized_emitted = False

        while remaining:
            parts: list[str] = list(base)
            taken = 0

            for position, row in enumerate(remaining):
                serialized_row = _serialize_row(row)
                if self.fits(prefix, LINE_JOINER, parts + [serialized_row]):
                    parts.append(serialized_row)
                    taken = position + 1
                    continue
                break

            if taken == 0:
                # A single row (plus the repeated header) exceeds the cap.
                # Keep the row whole and tag it: a split row is worse than an
                # oversized one because cells lose their column alignment.
                parts = list(base) + [_serialize_row(remaining[0])]
                taken = 1
                oversized_emitted = True

            self._append(
                content=self._text_of(prefix, LINE_JOINER, parts),
                page=element.page,
                heading_path=heading_path,
                element_types=(element.element_type,),
                strategy="table_rows",
                source_indices=(index,),
                oversized=oversized_emitted,
                is_continuation=not first,
            )
            first = False
            oversized_emitted = False
            remaining = remaining[taken:]

    # -- headings ---------------------------------------------------------

    def _emit_heading_only(self, item: tuple[int, ExtractedElement]) -> None:
        index, element = item
        self._append(
            content=element.content,
            page=element.page,
            heading_path=tuple(element.heading_path or ()),
            element_types=("heading",),
            strategy="heading",
            source_indices=(index,),
            source_start=0,
            source_end=len(element.content),
        )

    # -- emission ---------------------------------------------------------

    def _append(
        self,
        *,
        content: str,
        page: int | None,
        heading_path: tuple[str, ...],
        element_types: Sequence[str],
        strategy: str,
        source_indices: tuple[int, ...] = (),
        source_start: int | None = None,
        source_end: int | None = None,
        is_continuation: bool = False,
        oversized: bool = False,
        forced_cut: bool = False,
    ) -> None:
        if not content.strip():
            return

        meta = ChunkMeta(
            page=page,
            heading_path=heading_path,
            section=heading_path[-1] if heading_path else None,
            element_type=_chunk_element_type(element_types),
            chunker_version=self.version,
            token_count=self.counter(content),
            char_count=len(content),
            strategy=strategy,
            is_continuation=is_continuation,
            oversized=oversized,
            forced_cut=forced_cut,
            source_indices=source_indices,
            source_start=source_start,
            source_end=source_end,
        )
        self.chunks.append(Chunk(content=content, meta=meta))


# ---------------------------------------------------------------------------
# Element helpers
# ---------------------------------------------------------------------------

def _list_items(element: ExtractedElement) -> list[str]:
    """List items in document order.

    Marks (``-``, ``1.``) are not retained by extraction (DOCX detection is
    style-based), so items are raw text.  Items are never reordered and are
    never interleaved with another list.
    """
    if element.list_items:
        return [item for item in element.list_items if item and item.strip()]
    return [line.strip() for line in element.content.split("\n") if line.strip()]


def _table_rows(element: ExtractedElement) -> list[list[str]]:
    if element.table_data:
        return [list(row) for row in element.table_data]
    return [line.split(" | ") for line in element.content.split("\n")]


def _serialize_row(row: Sequence[str]) -> str:
    return " | ".join(row)


def _serialize_rows(rows: Sequence[Sequence[str]]) -> str:
    return "\n".join(_serialize_row(row) for row in rows)


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def chunks_to_pairs(chunks: Sequence[Chunk]) -> list[tuple[int | None, str]]:
    """Legacy ``(page, content)`` view, for baseline-comparable comparisons."""
    return [(chunk.meta.page, chunk.content) for chunk in chunks]


def chunk_contract_info() -> dict:
    """Report the active budgets and token-accounting provenance.

    Used by tests, the evaluation harness and the final report so no budget
    value is ever restated from memory.
    """
    return {
        "chunker_version": CHUNKER_VERSION_STRUCTURE,
        "legacy_version": CHUNKER_VERSION_LEGACY,
        "target_tokens": CHUNK_TARGET_TOKENS,
        "min_tokens": CHUNK_MIN_TOKENS,
        "max_tokens": resolve_max_chunk_tokens(),
        "declared_max_tokens": CHUNK_MAX_TOKENS,
        "overlap_tokens": CHUNK_OVERLAP_TOKENS,
        "max_chars": CHUNK_MAX_CHARS,
        "token_counter": "embedding-tokenizer" if is_tokenizer_available() else "char-estimate",
    }
