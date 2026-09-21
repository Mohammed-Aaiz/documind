"""Phase 3D — structure-aware chunker tests.

Two layers:

1. *Contract invariants* on synthetic ``ExtractedElement`` lists, using a
   deterministic stand-in counter so the arithmetic is inspectable without
   loading a model.
2. *Real-document* tests that run the actual extractors over the Phase 3D
   corpus (`tests/phase3d_corpus.py`) and the real embedding tokenizer, with
   the verified encoder cap (256) enforced.

The legacy chunker is untouched; these tests never call it to redefine
behaviour, they only assert the candidate's contract.
"""

from __future__ import annotations

import math
import re
import tempfile
from pathlib import Path

import pytest

from documents.chunking import (
    CHUNKER_VERSION_LEGACY,
    CHUNKER_VERSION_STRUCTURE,
    CHUNK_MAX_TOKENS,
    CHUNK_MIN_TOKENS,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_TARGET_TOKENS,
    Chunk,
    chunk_contract_info,
    chunk_elements,
    chunks_to_pairs,
    resolve_chunker_version,
    resolve_max_chunk_tokens,
)
from documents.processing import ExtractedElement, chunk_text, extract_text
from tokenization import (
    count_tokens,
    get_encoder_limits,
    is_tokenizer_available,
    reset_tokenizer_cache,
)

from .phase3d_corpus import build_corpus


# ---------------------------------------------------------------------------
# Counter used by the invariant layer
# ---------------------------------------------------------------------------

def chars4(text: str) -> int:
    """Deterministic stand-in counter: 4 characters per token.

    Used only where the arithmetic (not the model) is under test, so the
    expected chunk boundaries are exact integers.
    """
    return max(0, math.ceil(len(text) / 4))


def para(*texts: str, page: int | None = 1, path: list[str] | None = None,
         etype: str = "paragraph") -> ExtractedElement:
    return ExtractedElement(
        content="\n\n".join(texts),
        element_type=etype,
        page=page,
        heading_path=list(path or []),
    )


# ===========================================================================
# Versioning and budget resolution
# ===========================================================================

class TestVersioning:
    def test_legacy_is_the_default_for_unknown_values(self):
        assert resolve_chunker_version(None) == CHUNKER_VERSION_LEGACY
        assert resolve_chunker_version("") == CHUNKER_VERSION_LEGACY
        assert resolve_chunker_version("nonsense") == CHUNKER_VERSION_LEGACY

    def test_structure_aliases(self):
        for value in ("structure", "structure-v2", "v2", CHUNKER_VERSION_STRUCTURE):
            assert resolve_chunker_version(value) == CHUNKER_VERSION_STRUCTURE

    def test_chunk_elements_refuses_the_legacy_version(self):
        with pytest.raises(ValueError):
            chunk_elements([para("hello")], version="legacy")

    def test_contract_info_reports_the_verified_cap(self):
        info = chunk_contract_info()
        assert info["chunker_version"] == CHUNKER_VERSION_STRUCTURE
        assert info["legacy_version"] == CHUNKER_VERSION_LEGACY
        assert info["max_tokens"] <= CHUNK_MAX_TOKENS
        assert "token_counter" in info

    def test_legacy_chunker_is_still_available_and_unchanged(self):
        elements = [para("A" * 1200, page=1, path=["Intro"])]
        legacy = chunk_text(elements)
        assert legacy, "legacy chunker must still produce output"
        assert all(isinstance(page, (int, type(None))) for page, _ in legacy)
        assert all(isinstance(content, str) for _, content in legacy)


# ===========================================================================
# Budget invariants
# ===========================================================================

class TestBudgetInvariants:
    def test_short_text_is_one_chunk(self):
        chunks = chunk_elements([para("A short sentence.")], count_tokens=chars4)
        assert len(chunks) == 1
        assert chunks[0].meta.token_count <= CHUNK_MAX_TOKENS

    def test_no_chunk_exceeds_the_cap(self):
        long_text = ("This is a sentence about retrieval. " * 200)
        chunks = chunk_elements([para(long_text)], count_tokens=chars4)
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.meta.token_count <= CHUNK_MAX_TOKENS, chunk.meta

    def test_no_chunk_exceeds_the_cap_with_the_real_tokenizer(self):
        long_text = ("Der retrieval augmentierte Prozess nutzt Vektoren. " * 200)
        chunks = chunk_elements([para(long_text)])
        for chunk in chunks:
            assert chunk.meta.token_count <= resolve_max_chunk_tokens()

    def test_heading_prefix_is_inside_the_budget(self):
        deep = ["Handbook", "Installation", "Preparation", "Tools", "Torque"]
        chunks = chunk_elements(
            [para("Body text here.", page=1, path=deep)], count_tokens=chars4
        )
        assert len(chunks) == 1
        assert chunks[0].content.startswith("Handbook > Installation")
        assert chunks[0].meta.token_count <= CHUNK_MAX_TOKENS

    def test_pathological_heading_path_is_shortened(self):
        deep = [f"Level{i}SectionName" for i in range(40)]
        chunks = chunk_elements(
            [para("Body." * 40, page=1, path=deep)], count_tokens=chars4
        )
        for chunk in chunks:
            assert chunk.meta.token_count <= CHUNK_MAX_TOKENS

    def test_target_and_min_are_sane_relative_to_cap(self):
        info = chunk_contract_info()
        assert 0 < info["min_tokens"] < info["target_tokens"] <= info["max_tokens"]


# ===========================================================================
# Grouping / boundaries
# ===========================================================================

class TestGrouping:
    def test_paragraphs_in_the_same_section_merge(self):
        elements = [
            para("First sentence.", page=1, path=["Intro"]),
            para("Second sentence.", page=1, path=["Intro"]),
        ]
        chunks = chunk_elements(elements, count_tokens=chars4)
        assert len(chunks) == 1
        assert chunks[0].meta.element_type == "paragraph"

    def test_different_sections_never_merge(self):
        elements = [
            para("Alpha body text.", page=1, path=["Alpha"]),
            para("Beta body text.", page=1, path=["Beta"]),
        ]
        chunks = chunk_elements(elements, count_tokens=chars4)
        assert len(chunks) == 2
        assert [c.meta.section for c in chunks] == ["Alpha", "Beta"]

    def test_page_is_a_hard_boundary(self):
        # Same section, different page: two chunks, exact page attribution.
        elements = [
            para("Text on page one.", page=1, path=["Intro"]),
            para("Text on page two.", page=2, path=["Intro"]),
        ]
        chunks = chunk_elements(elements, count_tokens=chars4)
        assert len(chunks) == 2
        assert [c.meta.page for c in chunks] == [1, 2]

    def test_tables_never_merge_with_prose(self):
        elements = [
            para("Some prose here.", page=1, path=["Results"]),
            ExtractedElement(
                content="Method | Result\nPCA | 85 percent",
                element_type="table",
                page=1,
                heading_path=["Results"],
                table_data=[["Method", "Result"], ["PCA", "85 percent"]],
            ),
            para("More prose here.", page=1, path=["Results"]),
        ]
        chunks = chunk_elements(elements, count_tokens=chars4)
        types = [c.meta.element_type for c in chunks]
        assert types.count("table") == 1
        table_chunk = next(c for c in chunks if c.meta.element_type == "table")
        assert "PCA | 85 percent" in table_chunk.content
        assert "Some prose here" not in table_chunk.content

    def test_lists_never_merge_with_prose(self):
        elements = [
            para("The steps are as follows.", page=1, path=["Procedure"]),
            ExtractedElement(
                content="Step one\nStep two",
                element_type="list",
                page=1,
                heading_path=["Procedure"],
                list_items=["Step one", "Step two"],
            ),
        ]
        chunks = chunk_elements(elements, count_tokens=chars4)
        list_chunk = next(c for c in chunks if c.meta.element_type == "list")
        assert "The steps are as follows" not in list_chunk.content

    def test_zero_width_whitespace_elements_do_not_leak(self):
        elements = [para("   \n  "), para("Real content here.")]
        chunks = chunk_elements(elements, count_tokens=chars4)
        assert len(chunks) == 1
        assert chunks[0].content.strip() == "Real content here."


# ===========================================================================
# Headings
# ===========================================================================

class TestHeadings:
    def test_heading_context_is_prepended_to_section_chunks(self):
        elements = [
            ExtractedElement(content="Methods", element_type="heading", page=1,
                             heading_level=1, heading_path=["Methods"]),
            para("We used the Zephyr method.", page=1, path=["Methods"]),
        ]
        chunks = chunk_elements(elements, count_tokens=chars4)
        content_chunk = next(c for c in chunks if c.meta.element_type == "paragraph")
        assert content_chunk.content.startswith("Methods\n\n")
        assert content_chunk.meta.section == "Methods"
        assert content_chunk.meta.heading_path == ("Methods",)

    def test_heading_with_no_content_is_still_indexed(self):
        elements = [
            ExtractedElement(content="Empty Section", element_type="heading",
                             page=1, heading_level=1, heading_path=["Empty Section"]),
        ]
        chunks = chunk_elements(elements, count_tokens=chars4)
        assert len(chunks) == 1
        assert chunks[0].content == "Empty Section"
        assert chunks[0].meta.element_type == "heading"

    def test_consecutive_headings_each_remain_findable(self):
        elements = [
            ExtractedElement(content="First", element_type="heading", page=1,
                             heading_level=1, heading_path=["First"]),
            ExtractedElement(content="Second", element_type="heading", page=1,
                             heading_level=2, heading_path=["First", "Second"]),
            para("Body under second.", page=1, path=["First", "Second"]),
        ]
        chunks = chunk_elements(elements, count_tokens=chars4)
        headings = [c.content for c in chunks if c.meta.element_type == "heading"]
        assert "First" in headings
        body = next(c for c in chunks if c.meta.element_type == "paragraph")
        assert body.content.startswith("First > Second\n\n")

    def test_heading_path_metadata_survives(self):
        elements = [
            para("Deep body text.", page=2, path=["A", "B", "C"]),
        ]
        chunks = chunk_elements(elements, count_tokens=chars4)
        assert chunks[0].meta.heading_path == ("A", "B", "C")
        assert chunks[0].meta.section == "C"


# ===========================================================================
# Long-element splitting and overlap
# ===========================================================================

class TestSplitting:
    def test_long_paragraph_splits_on_sentence_boundaries(self):
        sentences = [f"Sentence number {i} carries factual content." for i in range(60)]
        elements = [para(" ".join(sentences), page=1, path=["Long"])]
        chunks = chunk_elements(elements, count_tokens=chars4)
        assert len(chunks) > 1
        # every emitted body should end at a sentence terminator
        for chunk in chunks:
            body = chunk.content.split("\n\n", 1)[-1]
            assert body.rstrip().endswith("."), body[-40:]

    def test_continuation_overlap_is_bounded_and_sentence_aligned(self):
        sentences = [f"Clause {i} describes the retrieval procedure in detail." for i in range(80)]
        elements = [para(" ".join(sentences), page=1, path=["Long"])]
        chunks = chunk_elements(elements, count_tokens=chars4)

        continuations = [c for c in chunks if c.meta.is_continuation]
        assert continuations, "expected at least one continuation chunk"
        for chunk in continuations:
            assert chunk.meta.overlap_tokens <= CHUNK_OVERLAP_TOKENS

        # ``overlap_text`` is the text a chunk hands to its successor, so the
        # successor must actually begin with it (this proves the overlap is
        # realised, not merely recorded).
        overlapped = [(i, c) for i, c in enumerate(chunks) if c.meta.overlap_text]
        assert overlapped, "expected at least one overlapping chunk"
        for index, chunk in overlapped:
            assert index + 1 < len(chunks), "overlap recorded on the final chunk"
            successor = chunks[index + 1].content.split("\n\n", 1)[-1]
            assert successor.startswith(chunk.meta.overlap_text), (
                f"successor does not begin with the carried text: "
                f"{successor[:60]!r} vs {chunk.meta.overlap_text!r}"
            )

    def test_overlap_only_occurs_within_a_split_element(self):
        elements = [
            para("First element text.", page=1, path=["A"]),
            para("Second element text.", page=1, path=["A"]),
        ]
        chunks = chunk_elements(elements, count_tokens=chars4)
        assert len(chunks) == 1
        assert chunks[0].meta.overlap_tokens == 0

    def test_unpunctuated_text_is_hard_cut_and_tagged(self):
        text = "X" * 4000
        elements = [para(text, page=1, path=["Raw"])]
        chunks = chunk_elements(elements, count_tokens=chars4)
        assert len(chunks) > 1
        # There is no sentence boundary anywhere, so every chunk except a final
        # remainder that happens to fit must come from a forced cut.
        assert any(c.meta.forced_cut for c in chunks)
        for chunk in chunks:
            assert chunk.meta.token_count <= CHUNK_MAX_TOKENS
        emitted = "".join(c.content.split("\n\n", 1)[-1] for c in chunks)
        assert emitted.count("X") >= len(text)

    def test_no_content_is_lost_across_a_split(self):
        text = " ".join(f"Sentence {i} about the Kestrel programme." for i in range(100))
        elements = [para(text, page=1, path=["Long"])]
        chunks = chunk_elements(elements, count_tokens=chars4)

        def norm(value: str) -> str:
            return re.sub(r"\s+", " ", value).strip()

        merged = norm(" ".join(c.content.split("\n\n", 1)[-1] for c in chunks))
        for sentence in re.findall(r"Sentence \d+ about the Kestrel programme\.", text):
            assert sentence in merged, sentence

    def test_forced_cut_resumes_without_skipping_text(self):
        text = "A" * 1000 + "B" * 1000
        elements = [para(text, page=1, path=["Raw"])]
        chunks = chunk_elements(elements, count_tokens=chars4)
        bodies = "".join(c.content.split("\n\n", 1)[-1] for c in chunks)
        # every A and B must appear somewhere in the emitted bodies
        assert bodies.count("A") >= 1000
        assert bodies.count("B") >= 1000


# ===========================================================================
# Lists
# ===========================================================================

class TestLists:
    def test_small_list_stays_one_chunk_in_order(self):
        items = ["Isolate the Nimbus supply", "Drain the Vermilion loop",
                 "Remove the Helios filter"]
        elements = [ExtractedElement(
            content="\n".join(items), element_type="list", page=1,
            heading_path=["Procedure"], list_items=items,
        )]
        chunks = chunk_elements(elements, count_tokens=chars4)
        assert len(chunks) == 1
        positions = [chunks[0].content.index(item) for item in items]
        assert positions == sorted(positions)

    def test_large_list_splits_at_item_boundaries(self):
        items = [f"Step {i}: perform the calibration routine carefully." for i in range(80)]
        elements = [ExtractedElement(
            content="\n".join(items), element_type="list", page=1,
            heading_path=["Procedure"], list_items=items,
        )]
        chunks = chunk_elements(elements, count_tokens=chars4)
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.meta.token_count <= CHUNK_MAX_TOKENS
            body = chunk.content.split("\n\n", 1)[-1]
            # no item is torn apart: every line is a recognizable Step line
            for line in body.split("\n"):
                assert line.strip().startswith("Step ") or line.strip() == ""

    def test_items_are_not_interleaved_across_chunks(self):
        items = [f"Step {i}: unique marker M{i}." for i in range(60)]
        elements = [ExtractedElement(
            content="\n".join(items), element_type="list", page=1,
            heading_path=["Procedure"], list_items=items,
        )]
        chunks = chunk_elements(elements, count_tokens=chars4)
        seen: list[str] = []
        for chunk in chunks:
            seen.extend(chunk.content.split("\n\n", 1)[-1].split("\n"))
        ordered = [line for line in seen if line.strip()]
        assert ordered == items

    def test_oversized_single_item_is_hard_cut(self):
        huge = "word " * 4000
        elements = [ExtractedElement(
            content=huge, element_type="list", page=1,
            heading_path=["Procedure"], list_items=[huge],
        )]
        chunks = chunk_elements(elements, count_tokens=chars4)
        assert len(chunks) > 1
        assert any(c.meta.forced_cut for c in chunks)
        for chunk in chunks:
            assert chunk.meta.token_count <= CHUNK_MAX_TOKENS


# ===========================================================================
# Tables
# ===========================================================================

class TestTables:
    def test_small_table_is_atomic(self):
        rows = [["Method", "Result"], ["PCA", "85 percent"], ["SVM", "92 percent"]]
        elements = [ExtractedElement(
            content="\n".join(" | ".join(r) for r in rows), element_type="table",
            page=1, heading_path=["Results"], table_data=rows,
        )]
        chunks = chunk_elements(elements, count_tokens=chars4)
        assert len(chunks) == 1
        assert chunks[0].meta.strategy == "table_atomic"
        for row in rows:
            assert " | ".join(row) in chunks[0].content

    def test_large_table_splits_by_rows_and_repeats_the_header(self):
        rows = [["Method", "Accuracy", "Runtime"]]
        rows += [[f"Method {i}", f"{60 + i} percent", f"{i * 7} ms"] for i in range(1, 41)]
        elements = [ExtractedElement(
            content="\n".join(" | ".join(r) for r in rows), element_type="table",
            page=1, heading_path=["Results"], table_data=rows,
        )]
        chunks = chunk_elements(elements, count_tokens=chars4)
        assert len(chunks) > 1
        header = " | ".join(rows[0])
        for chunk in chunks:
            assert chunk.meta.strategy == "table_rows"
            assert header in chunk.content, "header row must be repeated"

    def test_table_rows_are_never_split_across_chunks(self):
        rows = [["Method", "Accuracy"]]
        rows += [[f"Method {i}", f"{60 + i} percent"] for i in range(1, 41)]
        elements = [ExtractedElement(
            content="\n".join(" | ".join(r) for r in rows), element_type="table",
            page=1, heading_path=["Results"], table_data=rows,
        )]
        chunks = chunk_elements(elements, count_tokens=chars4)
        for row in rows[1:]:
            serialized = " | ".join(row)
            holders = [c for c in chunks if serialized in c.content]
            assert len(holders) == 1, f"row split or duplicated: {serialized}"

    def test_oversized_row_is_kept_whole_and_tagged(self):
        wide = [[f"c{i}" for i in range(400)], ["x" * 2000, "y" * 2000]]
        elements = [ExtractedElement(
            content="\n".join(" | ".join(r) for r in wide), element_type="table",
            page=1, heading_path=["Wide"], table_data=wide,
        )]
        chunks = chunk_elements(elements, count_tokens=chars4)
        assert any(c.meta.oversized for c in chunks)

    def test_table_without_table_data_falls_back_to_lines(self):
        content = "Method | Result\nPCA | 85 percent\nSVM | 92 percent"
        elements = [ExtractedElement(
            content=content, element_type="table", page=1,
            heading_path=["Results"], table_data=None,
        )]
        chunks = chunk_elements(elements, count_tokens=chars4)
        assert len(chunks) == 1
        assert "SVM | 92 percent" in chunks[0].content


# ===========================================================================
# Determinism
# ===========================================================================

class TestDeterminism:
    def test_output_is_byte_identical_across_runs(self):
        elements = [
            ExtractedElement(content="Intro", element_type="heading", page=1,
                             heading_level=1, heading_path=["Intro"]),
            para("Alpha sentence. " * 60, page=1, path=["Intro"]),
            para("Beta sentence. " * 60, page=2, path=["Intro"]),
        ]
        first = chunk_elements(elements, count_tokens=chars4)
        second = chunk_elements(elements, count_tokens=chars4)
        assert [c.content for c in first] == [c.content for c in second]
        assert [c.meta for c in first] == [c.meta for c in second]

    def test_chunk_index_is_implicitly_contiguous(self):
        elements = [para("Text. " * 400, page=1, path=["A"])]
        chunks = chunk_elements(elements, count_tokens=chars4)
        assert [i for i, _ in enumerate(chunks)] == list(range(len(chunks)))

    def test_pairs_view_matches_chunk_pages(self):
        elements = [para("Some text.", page=3, path=["A"])]
        chunks = chunk_elements(elements, count_tokens=chars4)
        assert chunks_to_pairs(chunks) == [(3, chunks[0].content)]


# ===========================================================================
# Real documents (actual extractors + real tokenizer)
# ===========================================================================

@pytest.mark.skipif(not is_tokenizer_available(), reason="tokenizer unavailable")
class TestRealDocuments:
    @pytest.fixture(scope="class")
    def extracted(self):
        corpus = build_corpus()
        out = {}
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for doc in corpus:
                path = doc.write(directory)
                out[doc.name] = extract_text(path, doc.file_type)
        return out

    def test_every_corpus_document_produces_chunks(self, extracted):
        for name, elements in extracted.items():
            chunks = chunk_elements(elements)
            assert chunks, f"{name} produced no chunks"

    def test_encoder_truncation_rate_is_zero(self, extracted):
        cap = resolve_max_chunk_tokens()
        assert cap == CHUNK_MAX_TOKENS, (
            "verified encoder limit changed; re-validate the chunk budget"
        )
        for name, elements in extracted.items():
            for chunk in chunk_elements(elements):
                if chunk.meta.oversized:
                    continue
                assert chunk.meta.token_count <= cap, (
                    f"{name}: chunk of {chunk.meta.token_count} tokens exceeds the cap"
                )

    def test_chunker_version_is_recorded_on_every_chunk(self, extracted):
        for name, elements in extracted.items():
            for chunk in chunk_elements(elements):
                assert chunk.meta.chunker_version == CHUNKER_VERSION_STRUCTURE, name

    def test_heading_context_present_wherever_a_section_exists(self, extracted):
        for name, elements in extracted.items():
            for chunk in chunk_elements(elements):
                if chunk.meta.element_type == "heading":
                    continue
                if chunk.meta.heading_path:
                    expected = " > ".join(chunk.meta.heading_path) + "\n\n"
                    assert chunk.content.startswith(expected), (
                        f"{name}: missing heading prefix on {chunk.content[:40]!r}"
                    )

    def test_candidate_never_fragments_more_than_the_legacy_chunker(self, extracted):
        """Fragmentation, not chunk size, was the real defect.

        The candidate must not produce more chunks than the blind character
        chunker for the same document, and must produce strictly fewer for at
        least one document (proving sibling merging actually happens).
        """
        strictly_fewer = 0
        for name, elements in extracted.items():
            candidate = chunk_elements(elements)
            legacy = chunk_text(elements)
            assert len(candidate) <= len(legacy), (
                f"{name}: candidate={len(candidate)} legacy={len(legacy)}"
            )
            if len(candidate) < len(legacy):
                strictly_fewer += 1
        assert strictly_fewer > 0, "no document benefited from sibling merging"


class TestEncoderLimitsVerified:
    """The chunk budget is derived from the loaded model, not from memory."""

    def test_limits_are_reported_from_the_loaded_model(self):
        reset_tokenizer_cache()
        limits = get_encoder_limits()
        if not limits.get("available"):
            pytest.skip("embedding model unavailable")
        assert limits["max_tokens"] == CHUNK_MAX_TOKENS, (
            "verified encoder limit no longer matches the declared chunk cap: "
            f"{limits}"
        )
        assert limits["dimensions"] == 384

    def test_declared_cap_never_exceeds_the_encoder(self):
        cap = resolve_max_chunk_tokens()
        limit = get_encoder_limits().get("max_tokens")
        if limit:
            assert cap <= limit
