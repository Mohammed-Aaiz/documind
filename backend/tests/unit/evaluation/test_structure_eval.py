"""Tests for the offline structure-aware evaluation harness (Feature #15).

These pin the properties the framework must never lose:

* the synthetic corpus is internally consistent and passes validation;
* a malformed corpus fails loudly *before* any metric is produced;
* runs are deterministic and the written JSON is byte-reproducible;
* a metric whose population is empty is reported as ``None`` (unavailable),
  never as ``0.0``;
* each variant actually exercises its own retrieval path (no variant is a
  silent copy of another);
* the offline harness makes no network / external-LLM call.

They deliberately do **not** assert that any variant is "better" — that is a
research claim that requires a real corpus, not a unit test.
"""

from __future__ import annotations

import inspect
import json
import re

import pytest

from evaluation import structure_eval as se
from evaluation.artifacts import ArtifactExistsError
from evaluation.datasets import structure_eval_corpus as fixture
from evaluation.schemas import QuestionCategory


# ---------------------------------------------------------------------------
# Fixture contract
# ---------------------------------------------------------------------------


class TestSyntheticCorpus:
    def test_corpus_passes_harness_validation(self):
        se.validate_corpus(fixture.build_corpus())

    def test_summary_is_deterministic_and_path_free(self):
        summary = fixture.corpus_summary()
        assert summary["version"] == fixture.CORPUS_VERSION
        assert summary["questionCount"] == len(fixture.build_corpus().questions)
        assert summary["answerableCount"] + summary["unanswerableCount"] == summary["questionCount"]
        assert not any("/" in str(value) or "\\" in str(value) for value in summary.values())

    def test_every_chunk_backs_an_element(self):
        corpus = fixture.build_corpus()
        for chunk in corpus.chunks:
            assert corpus.element_by_id(chunk.element_id) is not None

    def test_question_document_scope_is_consistent(self):
        corpus = fixture.build_corpus()
        for question in corpus.questions:
            if question.document_id is None:
                continue
            for element_id in question.gold_element_ids:
                element = corpus.element_by_id(element_id)
                assert element is not None
                assert element.document_id == question.document_id


class TestValidateCorpusFailsLoudly:
    def _base(self):
        element = fixture.EvalElement("e1", "doc", "paragraph", 0, 1, ("S",), "alpha")
        chunk = fixture.EvalChunk("c1", "doc", "e1", "alpha", 1)
        question = fixture.StructureQuestion(
            "q1", "alpha?", QuestionCategory.DIRECT, "doc",
            gold_element_ids=("e1",), gold_chunk_ids=("c1",), gold_answers=("alpha",),
        )
        return element, chunk, question

    def test_dangling_gold_element_is_rejected(self):
        element, chunk, question = self._base()
        bad = fixture.EvalCorpus(
            "t", (element,), (chunk,),
            (fixture.StructureQuestion(
                "q1", "alpha?", QuestionCategory.DIRECT, "doc", gold_element_ids=("ghost",)
            ),),
        )
        with pytest.raises(se.StructureCorpusError) as exc:
            se.validate_corpus(bad)
        assert "ghost" in str(exc.value)

    def test_duplicate_chunk_id_is_rejected(self):
        element, chunk, _ = self._base()
        bad = fixture.EvalCorpus("t", (element,), (chunk, chunk), ())
        with pytest.raises(se.StructureCorpusError, match="duplicate chunk id"):
            se.validate_corpus(bad)

    def test_answerable_question_without_gold_is_rejected(self):
        bad = fixture.EvalCorpus(
            "t", (), (),
            (fixture.StructureQuestion("q1", "?", QuestionCategory.DIRECT, None),),
        )
        with pytest.raises(se.StructureCorpusError, match="no gold evidence"):
            se.validate_corpus(bad)

    def test_evaluate_validates_before_measuring(self):
        # A malformed corpus must raise from evaluate() rather than silently
        # producing metrics over dangling labels.
        element, chunk, _ = self._base()
        bad = fixture.EvalCorpus(
            "t", (element,), (chunk,),
            (fixture.StructureQuestion("q1", "?", QuestionCategory.DIRECT, "doc",
                                       gold_element_ids=("ghost",)),),
        )
        with pytest.raises(se.StructureCorpusError):
            se.evaluate(bad)


# ---------------------------------------------------------------------------
# Variant behaviour
# ---------------------------------------------------------------------------


class TestVariantsExerciseTheirOwnPath:
    def test_semantic_only_returns_semantic_evidence(self):
        corpus = fixture.build_corpus()
        question = corpus.questions[0]
        items = se.retrieve_semantic_only(corpus, question, top_k=5)
        assert items
        assert all(item.source_type == "semantic" for item in items)
        assert all(item.chunk_id for item in items)

    def test_structure_aware_returns_structural_evidence(self):
        corpus = fixture.build_corpus()
        question = corpus.questions[1]
        items = se.retrieve_structure_aware(corpus, question, top_k=5)
        assert items
        assert all(item.source_type == "structure" for item in items)
        assert all(item.structure_element_id for item in items)
        assert all(item.score is None for item in items)

    def test_fused_path_uses_both_streams(self):
        corpus = fixture.build_corpus()
        question = corpus.questions[0]
        items = se.retrieve_fused_dual_path(corpus, question, top_k=5)
        assert items
        # fuse_evidence emits semantic evidence before structural evidence.
        assert items[0].source_type == "semantic"
        # Every structural item must carry no fabricated similarity score.
        assert all(item.score is None for item in items if item.source_type == "structure")

    def test_dual_path_chunk_differs_from_semantic_only(self):
        """A saturated semantic list must not starve the structural path."""
        corpus = fixture.build_corpus()
        question = next(q for q in corpus.questions if q.question_id == "q-crosspage")
        a = se.retrieve_semantic_only(corpus, question, top_k=5)
        b = se.retrieve_dual_path_chunk(corpus, question, top_k=5)
        assert [i.identity() for i in a] != [i.identity() for i in b]

    def test_all_four_variants_run(self):
        report = se.evaluate(fixture.build_corpus())
        assert [run.variant for run in report.runs] == [v.value for v in se.ALL_VARIANTS]
        for run in report.runs:
            assert run.question_count == len(fixture.build_corpus().questions)


# ---------------------------------------------------------------------------
# Honest metrics
# ---------------------------------------------------------------------------


def _corpus(questions, elements=(), chunks=()):
    return fixture.EvalCorpus("test-v1", tuple(elements), tuple(chunks), tuple(questions))


class TestHonestAvailability:
    def test_empty_ground_truth_population_is_null_not_zero(self):
        # Two unanswerable questions: there is no gold, so retrieval metrics have
        # an empty population and must be reported as unavailable.
        corpus = _corpus(
            [
                fixture.StructureQuestion("u1", "?", QuestionCategory.DIRECT, None, answerable=False),
                fixture.StructureQuestion("u2", "?", QuestionCategory.DIRECT, None, answerable=False),
            ]
        )
        report = se.evaluate(corpus, variants=[se.StructureVariant.A_SEMANTIC_ONLY])
        run = report.runs[0]
        assert run.metrics["recall@5"] is None
        assert run.metrics["recall@5"] != 0.0
        assert "recall@5" in run.unavailable
        assert run.metrics["exact_match"] is None
        assert "exact_match" in run.unavailable

    def test_retrieval_denominator_counts_only_gold_bearing_questions(self):
        elements = (
            fixture.EvalElement("e1", "doc", "paragraph", 0, 1, ("S",), "alpha beta"),
            fixture.EvalElement("e2", "doc", "paragraph", 1, 1, ("S",), "gamma delta"),
        )
        chunks = (
            fixture.EvalChunk("c1", "doc", "e1", "alpha beta", 1),
            fixture.EvalChunk("c2", "doc", "e2", "gamma delta", 1),
        )
        questions = (
            # recall 1.0 — the question terms match e1, which is gold.
            fixture.StructureQuestion(
                "qA", "alpha", QuestionCategory.DIRECT, "doc",
                gold_element_ids=("e1",), gold_chunk_ids=("c1",), gold_answers=("alpha",),
            ),
            # recall 0.0 — no overlap with the gold element e2.
            fixture.StructureQuestion(
                "qB", "zzzz", QuestionCategory.DIRECT, "doc",
                gold_element_ids=("e2",), gold_chunk_ids=("c2",), gold_answers=("gamma",),
            ),
            # no gold at all — must be excluded from the retrieval denominator.
            fixture.StructureQuestion("qU", "?", QuestionCategory.DIRECT, None, answerable=False),
        )
        report = se.evaluate(
            _corpus(questions, elements, chunks),
            variants=[se.StructureVariant.A_SEMANTIC_ONLY],
            top_k=1,
        )
        run = report.runs[0]
        assert run.metrics["recall@1"] == pytest.approx(0.5)


class TestExtractiveAnswer:
    def test_abstains_without_evidence(self):
        question = fixture.build_corpus().questions[0]
        outcome = se.extractive_answer(question, [])
        assert outcome["answer"] == ""
        assert outcome["insufficient_context"] is True
        assert outcome["factual_grounded"] is False

    def test_span_is_verbatim_from_evidence(self):
        corpus = fixture.build_corpus()
        question = next(q for q in corpus.questions if q.question_id == "q-firmware")
        evidence = se.retrieve_semantic_only(corpus, question, top_k=5)
        outcome = se.extractive_answer(question, evidence)
        assert outcome["answer"]
        assert outcome["factual_grounded"] is True


# ---------------------------------------------------------------------------
# Determinism / output hygiene
# ---------------------------------------------------------------------------


class TestDeterminismAndOutput:
    def test_repeated_runs_are_identical(self):
        corpus = fixture.build_corpus()
        first = se.evaluate(corpus).to_dict()
        second = se.evaluate(corpus).to_dict()
        assert first == second
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)

    def test_written_json_is_byte_reproducible(self, monkeypatch, tmp_path):
        monkeypatch.setattr(se, "REPORTS_DIR", tmp_path)
        report = se.evaluate(fixture.build_corpus())
        first = se.write_report(report, "run")
        first_bytes = first.read_bytes()

        # This is the byte-reproducibility check, which rewrites the same name on
        # purpose and therefore asks for it explicitly: the default refuses and
        # leaves the recorded artifact untouched.
        with pytest.raises(ArtifactExistsError):
            se.write_report(report, "run")
        assert first.read_bytes() == first_bytes

        second = se.write_report(report, "run", replace=True)
        assert first_bytes == second.read_bytes()
        payload = json.loads(first_bytes.decode("utf-8"))
        assert payload["offline"] is True
        assert payload["requires_database"] is False
        assert payload["requires_model"] is False

    def test_report_contains_no_absolute_paths_or_secrets(self):
        payload = json.dumps(se.evaluate(fixture.build_corpus()).to_dict())
        assert not re.search(r"[A-Za-z]:\\\\", payload)
        assert "/Users/" not in payload and "/home/" not in payload
        assert "traceback" not in payload.lower()

    def test_harness_makes_no_network_or_llm_calls(self):
        source = inspect.getsource(se)
        for forbidden in ("openai", "anthropic", "requests.", "httpx", "urllib.request", "socket."):
            assert forbidden not in source
