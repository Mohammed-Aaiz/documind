"""Tests for the structure-discriminating v1 corpus and its validator.

The corpus exists to make the structure hypothesis falsifiable, so its contract
is pinned here: structure must be schema-valid, every structural gold reference
must exist and stay inside its document, unanswerable questions must carry no
gold, and the anti-leakage discrimination labels must be well formed.  The
validator is also exercised on deliberately malformed corpora so it fails
loudly rather than passing a broken dataset.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from evaluation.datasets import structure_discriminating_v1 as sd


@pytest.fixture(scope="module")
def corpus():
    return sd.build_corpus()


class TestCorpusLoads:
    def test_builds_without_error(self, corpus):
        assert corpus.version == sd.CORPUS_VERSION
        assert len(corpus.documents) >= 4
        assert len(corpus.questions) >= 60

    def test_documents_are_pdf(self, corpus):
        assert all(doc.file_type == "pdf" for doc in corpus.documents)

    def test_validates(self, corpus):
        result = sd.validate_corpus(corpus)
        assert result.ok, result.errors

    def test_vocabulary_matches_production_schema(self):
        from graph.models import ELEMENT_TYPES as PROD_TYPES
        from graph.models import STRUCTURE_RELATIONS as PROD_RELATIONS

        assert tuple(PROD_TYPES) == sd.ELEMENT_TYPES
        assert tuple(PROD_RELATIONS) == sd.STRUCTURE_RELATIONS


class TestQuestionAnnotations:
    def test_every_answerable_question_has_answer_and_gold(self, corpus):
        for q in corpus.questions:
            if not q.answerable:
                continue
            assert q.expected_answer, q.qid
            assert q.acceptable_answers, q.qid
            assert q.evidence, q.qid
            assert q.gold_element_ids or q.gold_table_cells, q.qid

    def test_every_structural_question_has_structural_gold(self, corpus):
        structural = {
            sd.CAT_TABLE, sd.CAT_SECTION, sd.CAT_PAGE, sd.CAT_MULTIHOP, sd.CAT_DISTRACTOR,
        }
        for q in corpus.questions:
            if q.answerable and q.category in structural:
                assert q.gold_element_ids, q.qid
                assert q.expected_structural_path, q.qid
                assert q.expected_evidence_type, q.qid

    def test_table_questions_reference_a_table_cell(self, corpus):
        for q in corpus.questions:
            if q.answerable and q.category == sd.CAT_TABLE:
                assert q.gold_table_cells, q.qid
                assert sd.ELEMENT_TYPE_TABLE in q.expected_structural_path

    def test_unanswerable_questions_carry_no_gold(self, corpus):
        for q in corpus.questions:
            if q.answerable:
                continue
            assert not q.gold_element_ids
            assert not q.gold_table_cells
            assert not q.evidence
            assert q.expected_answer is None
            assert q.discrimination is None

    def test_discrimination_labels_are_valid(self, corpus):
        for q in corpus.questions:
            if not q.answerable:
                continue
            assert q.discrimination in sd.DISCRIMINATION_LEVELS, q.qid
            if q.discrimination != sd.NOT_DISCRIMINATING:
                assert q.discrimination_rationale, q.qid


class TestStructuralIntegrity:
    def test_every_gold_reference_exists(self, corpus):
        index = {e.element_id for e in corpus.elements}
        for q in corpus.questions:
            for gid in q.gold_element_ids:
                assert gid in index, q.qid
            for cid in q.gold_table_cells:
                assert cid in index, q.qid

    def test_parent_chains_are_valid(self, corpus):
        index = {e.element_id: e for e in corpus.elements}
        for element in corpus.elements:
            if element.parent_id is None:
                continue
            parent = index[element.parent_id]
            assert parent.document_id == element.document_id
        for q in corpus.questions:
            for gid in q.gold_element_ids:
                element = index[gid]
                assert element.document_id == q.document_id

    def test_table_cells_nest_under_rows_under_tables(self, corpus):
        index = {e.element_id: e for e in corpus.elements}
        for element in corpus.elements:
            if element.element_type != sd.ELEMENT_TYPE_TABLE_CELL:
                continue
            row = index[element.parent_id]
            assert row.element_type == sd.ELEMENT_TYPE_TABLE_ROW
            table = index[row.parent_id]
            assert table.element_type == sd.ELEMENT_TYPE_TABLE

    def test_page_crossing_questions_actually_cross_a_page(self, corpus):
        index = {e.element_id: e for e in corpus.elements}
        crossings = [q for q in corpus.questions if q.category == sd.CAT_PAGE]
        assert crossings
        for q in crossings:
            pages = [index[g].page_number for g in q.gold_element_ids]
            assert max(pages) > min(pages), q.qid


class TestCountsAndOrdering:
    def test_category_counts(self, corpus):
        expected = {
            sd.CAT_TABLE: 20, sd.CAT_SECTION: 12, sd.CAT_PAGE: 8,
            sd.CAT_MULTIHOP: 8, sd.CAT_DISTRACTOR: 8, sd.CAT_SEMANTIC: 8,
            sd.CAT_UNANSWERABLE: 8,
        }
        summary = sd.validate_corpus(corpus).summary
        assert summary["categories"] == expected
        assert summary["questions"] == 72
        assert summary["answerable"] == 64
        assert summary["unanswerable"] == 8
        assert summary["discriminating"] == 32

    def test_ordering_is_deterministic(self):
        a, b = sd.build_corpus(), sd.build_corpus()
        assert [q.qid for q in a.questions] == [q.qid for q in b.questions]
        assert [e.element_id for e in a.elements] == [e.element_id for e in b.elements]

    def test_documents_build_parseable_pdfs(self, tmp_path):
        from documents.parser import parse_pdf

        doc = sd.build_corpus().document("atlas")
        path = doc.write(tmp_path)
        parsed = parse_pdf(path)
        assert parsed.page_count >= 3
        assert any(e.element_type == "table" for e in parsed.elements)
        assert any(e.element_type == "section" for e in parsed.elements)


class TestValidatorRejectsMalformedCorpora:
    def _validate(self, corpus):
        return sd.validate_corpus(corpus)

    def test_duplicate_question_ids_rejected(self, corpus):
        bad = replace(corpus.questions[1], qid=corpus.questions[0].qid)
        mutated = replace(
            corpus,
            questions=(corpus.questions[0], bad, *corpus.questions[2:]),
        )
        result = self._validate(mutated)
        assert not result.ok
        assert any("duplicate question id" in e for e in result.errors)

    def test_duplicate_question_text_rejected(self, corpus):
        bad = replace(corpus.questions[1], text=corpus.questions[0].text)
        mutated = replace(
            corpus,
            questions=(corpus.questions[0], bad, *corpus.questions[2:]),
        )
        result = self._validate(mutated)
        assert any("duplicate question text" in e for e in result.errors)

    def test_cross_document_gold_reference_rejected(self, corpus):
        q = next(q for q in corpus.questions if q.document_id == "atlas" and q.answerable)
        foreign = next(e for e in corpus.elements if e.document_id != q.document_id)
        mutated = replace(
            corpus,
            questions=tuple(
                replace(item, gold_element_ids=(foreign.element_id,)) if item is q else item
                for item in corpus.questions
            ),
        )
        result = self._validate(mutated)
        assert any("cross-document gold reference" in e for e in result.errors)

    def test_missing_gold_element_rejected(self, corpus):
        q = next(q for q in corpus.questions if q.answerable)
        mutated = replace(
            corpus,
            questions=tuple(
                replace(item, gold_element_ids=("does-not-exist",)) if item is q else item
                for item in corpus.questions
            ),
        )
        result = self._validate(mutated)
        assert any("does not exist" in e for e in result.errors)

    def test_malformed_element_type_rejected(self, corpus):
        bad = replace(corpus.elements[0], element_type="bogus_type")
        mutated = replace(corpus, elements=(bad, *corpus.elements[1:]))
        result = self._validate(mutated)
        assert any("unknown type" in e for e in result.errors)

    def test_table_cell_with_wrong_parent_rejected(self, corpus):
        section = next(e for e in corpus.elements if e.element_type == sd.ELEMENT_TYPE_SECTION)
        bad_cell = sd.StructuralElement(
            element_id="bad:cell", document_id=section.document_id,
            element_type=sd.ELEMENT_TYPE_TABLE_CELL, parent_id=section.element_id,
            page_number=section.page_number, sequence_index=99999,
        )
        mutated = replace(corpus, elements=(*corpus.elements, bad_cell))
        result = self._validate(mutated)
        assert any("parent is not a table_row" in e for e in result.errors)

    def test_fabricated_evidence_rejected(self, corpus):
        q = next(q for q in corpus.questions if q.answerable)
        mutated = replace(
            corpus,
            questions=tuple(
                replace(item, evidence=("not-in-any-document-xyz",)) if item is q else item
                for item in corpus.questions
            ),
        )
        result = self._validate(mutated)
        assert any("not present in document text" in e for e in result.errors)

    def test_ungrounded_answer_rejected(self, corpus):
        q = next(q for q in corpus.questions if q.answerable)
        mutated = replace(
            corpus,
            questions=tuple(
                replace(item, expected_answer="fabricated", acceptable_answers=("fabricated",))
                if item is q else item
                for item in corpus.questions
            ),
        )
        result = self._validate(mutated)
        assert any("not grounded in document text" in e for e in result.errors)

    def test_unanswerable_with_gold_rejected(self, corpus):
        q = next(q for q in corpus.questions if not q.answerable)
        mutated = replace(
            corpus,
            questions=tuple(
                replace(item, gold_element_ids=("atlas:section:0",)) if item is q else item
                for item in corpus.questions
            ),
        )
        result = self._validate(mutated)
        assert any("unanswerable must carry no gold" in e for e in result.errors)
