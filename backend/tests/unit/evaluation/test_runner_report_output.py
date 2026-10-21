"""Runner report contract: per-question diagnostics, legacy compatibility, and
append-only output directories.

The aggregate metrics are means over per-question measurements, so a report is
only traceable if the questions behind it are recorded.  These tests pin:

* the diagnostics the runner records (evidence ranks, outcome, failure
  attribution) and the attribution rule they follow;
* that the historical report format is unchanged when no output directory is
  given — the recorded research reports keep working with existing consumers;
* that a caller-supplied directory is used instead, is never overwritten, and
  is never a silent alias for ``evaluation/reports/``.
"""

from __future__ import annotations

import json

import pytest

from evaluation import runner
from evaluation.artifacts import ArtifactExistsError, RunOutput
from evaluation.experiments import run_dual_path_ablation
from evaluation.schemas import Baseline, EvalQuestion, QuestionCategory


def _question(*, answerable=True, gold=("c1",), gold_answers=("six hours",)):
    return EvalQuestion(
        question_id="q1",
        question="How long is the reference manual curing time?",
        category=QuestionCategory.SECTION_DEPENDENT,
        document_id="doc-1",
        gold_answers=gold_answers,
        gold_chunk_ids=gold,
        answerable=answerable,
    )


async def _measure(
    *,
    answer="six hours",
    retrieved=("c1", "c2"),
    supplied=("c1",),
    insufficient=False,
    question=None,
):
    async def retrieve(_question):
        return list(retrieved)

    async def answer_fn(_question, _ids):
        return {
            "answer": answer,
            "confidence": 0.9,
            "insufficient_context": insufficient,
            "factual_grounded": bool(answer),
            "supplied_chunk_ids": list(supplied),
            "retrieval_paths": ["hybrid"],
            "structural_hops": [0],
        }

    return await runner.run_baseline(
        Baseline.B4_DUAL_PATH, [question or _question()], retrieve, answer_fn
    )


# ---------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------


class TestOutcomeAttribution:
    def _classify(self, **overrides):
        kwargs = dict(
            answerable=True,
            predicted="six hours",
            expected=("six hours",),
            insufficient_context=False,
            has_gold_evidence=True,
            gold_evidence_supplied=True,
        )
        kwargs.update(overrides)
        return runner.classify_question_outcome(**kwargs)

    def test_correct_answer(self):
        assert self._classify() == ("correct", runner.FAILURE_NONE)

    def test_wrong_answer_with_the_gold_evidence_present_is_an_answer_stage_failure(self):
        assert self._classify(predicted="seven hours") == (
            "incorrect",
            runner.FAILURE_ANSWER_STAGE,
        )

    def test_wrong_answer_without_the_gold_evidence_is_a_retrieval_miss(self):
        assert self._classify(
            predicted="seven hours", gold_evidence_supplied=False
        ) == ("incorrect", runner.FAILURE_RETRIEVAL_MISS)

    def test_wrong_answer_without_gold_labels_is_not_attributed(self):
        assert self._classify(
            predicted="seven hours",
            has_gold_evidence=False,
            gold_evidence_supplied=False,
        ) == ("incorrect", runner.FAILURE_UNLABELLED)

    def test_abstention_on_an_answerable_question(self):
        assert self._classify(predicted="") == ("abstained", runner.FAILURE_ABSTAINED)

    def test_answered_unanswerable_question(self):
        assert self._classify(
            answerable=False, predicted="anything"
        ) == ("unsupported_answer", runner.FAILURE_UNSUPPORTED)

    def test_correct_abstention_on_an_unanswerable_question(self):
        assert self._classify(
            answerable=False, predicted="", insufficient_context=True, has_gold_evidence=False
        ) == ("correct_abstention", runner.FAILURE_NONE)


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


class TestPerQuestionDiagnostics:
    async def test_evidence_ranks_and_attribution_are_recorded(self):
        report = await _measure()
        detail = report.results[0].detail

        assert detail["retrieved_ranks"] == {"c1": 1, "c2": 2}
        assert detail["supplied_ranks"] == {"c1": 1}
        assert detail["gold_retrieved"] is True
        assert detail["gold_supplied"] is True
        assert detail["outcome"] == "correct"
        assert detail["failure_category"] == runner.FAILURE_NONE

    async def test_wrong_answer_names_the_stage_that_failed(self):
        report = await _measure(answer="seven hours")
        detail = report.results[0].detail

        assert detail["predicted"] == "seven hours"
        assert detail["failure_category"] == runner.FAILURE_ANSWER_STAGE

    async def test_ranks_come_from_the_measured_ranking_not_from_gold(self):
        report = await _measure(
            answer="seven hours", retrieved=("c9", "c1"), supplied=("c9",)
        )
        detail = report.results[0].detail

        # c1 is gold but arrived second; c9 was what the answer stage actually got.
        assert detail["retrieved_ranks"] == {"c9": 1, "c1": 2}
        assert detail["supplied_ranks"] == {"c9": 1}
        assert detail["gold_retrieved"] is True
        assert detail["gold_supplied"] is False
        assert detail["failure_category"] == runner.FAILURE_RETRIEVAL_MISS

    async def test_duplicate_evidence_does_not_invent_extra_ranks(self):
        report = await _measure(
            answer="seven hours", retrieved=("c1", "c1", "c2"), supplied=("c1", "c1")
        )
        detail = report.results[0].detail

        assert detail["retrieved_ranks"] == {"c1": 1, "c2": 2}
        assert detail["supplied_ranks"] == {"c1": 1}


# ---------------------------------------------------------------------------
# Legacy report format (unchanged)
# ---------------------------------------------------------------------------


class TestLegacyReportFormatIsUnchanged:
    async def test_default_write_keeps_the_historical_shape(self, tmp_path, monkeypatch):
        monkeypatch.setattr(runner, "REPORTS_DIR", tmp_path / "reports")
        report = await _measure()

        path = runner.write_report(report, "ablation_A")

        assert path == tmp_path / "reports" / "ablation_A.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["baseline"] == Baseline.B4_DUAL_PATH.value
        assert payload["includes_per_question_detail"] is False
        assert set(payload["results"][0]) == {
            "question_id",
            "category",
            "answerable",
            "retrieval",
            "qa",
            "evidence",
            "latency_ms",
        }, "existing consumers read exactly these keys"

        markdown = (tmp_path / "reports" / "ablation_A.md").read_text(encoding="utf-8")
        assert markdown.startswith("# Evaluation report — ")
        assert "| metric | value |" in markdown

    async def test_default_write_refuses_to_replace_a_same_named_report(
        self, tmp_path, monkeypatch
    ):
        # STEP 1.6Y: the recorded research directory is append-only by default.
        # The append-only rule used to belong only to a caller-supplied output
        # directory, so a re-run of this default path silently replaced recorded
        # evidence.  It now refuses, and a deliberate re-publication has to ask.
        monkeypatch.setattr(runner, "REPORTS_DIR", tmp_path / "reports")
        path = runner.write_report(await _measure(answer="six hours"), "ablation_A")
        first = json.loads(path.read_text(encoding="utf-8"))
        json_before = path.read_bytes()
        md = tmp_path / "reports" / "ablation_A.md"
        markdown_before = md.read_bytes()

        with pytest.raises(ArtifactExistsError):
            runner.write_report(await _measure(answer="seven hours"), "ablation_A")

        # The recorded evidence is byte-identical after the refusal — neither
        # file was replaced, and no partial pair was written.
        assert path.read_bytes() == json_before
        assert md.read_bytes() == markdown_before

        runner.write_report(
            await _measure(answer="seven hours"), "ablation_A", replace=True
        )
        second = json.loads(path.read_text(encoding="utf-8"))

        assert first["metrics"]["exact_match"] == pytest.approx(1.0)
        assert second["metrics"]["exact_match"] == pytest.approx(0.0), (
            "replace=True is an explicit, opt-in re-publication of the recorded "
            "report; it is never implied by a collision"
        )


# ---------------------------------------------------------------------------
# Caller-supplied output directory (append-only)
# ---------------------------------------------------------------------------


class TestRunnerCliContract:
    """The safety contract, seen from the interface an operator actually uses."""

    def test_out_is_required(self):
        with pytest.raises(SystemExit):
            run_dual_path_ablation.parse_args([])

    def test_database_url_is_optional_but_recognised(self):
        args = run_dual_path_ablation.parse_args(
            ["--out", "somewhere", "--database-url", "postgresql+asyncpg://h:55433/other"]
        )
        assert args.database_url == "postgresql+asyncpg://h:55433/other"
        assert args.out == "somewhere"

    def test_no_hard_coded_database_target_in_the_runner_source(self):
        # The previous revision imported the application's engine at module
        # import time, which froze the target. The DSN must be resolved from the
        # caller's configuration instead.
        import inspect

        source = inspect.getsource(run_dual_path_ablation)
        assert "assert_safe_evaluation_target" in source
        assert "from storage.database import async_session, engine  # noqa: E402" not in source


class TestOutDirReportOutput:
    async def test_requested_directory_is_used_and_reports_dir_is_untouched(
        self, tmp_path, monkeypatch
    ):
        sentinel = tmp_path / "reports"
        monkeypatch.setattr(runner, "REPORTS_DIR", sentinel)
        output = RunOutput(tmp_path / "run-1")
        output.reserve("ablation_A.json", "ablation_A.md")
        report = await _measure()

        path = runner.write_report(
            report, "ablation_A", out_dir=output, include_detail=True
        )

        assert path == tmp_path / "run-1" / "ablation_A.json"
        assert (tmp_path / "run-1" / "ablation_A.md").exists()
        assert not sentinel.exists(), "a caller-supplied directory is never mixed with the archive"

    async def test_detail_is_included_when_requested(self, tmp_path):
        output = RunOutput(tmp_path)
        report = await _measure()

        path = runner.write_report(report, "ablation_A", out_dir=output, include_detail=True)

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["includes_per_question_detail"] is True
        detail = payload["results"][0]["detail"]
        assert detail["outcome"] == "correct"
        assert detail["failure_category"] == runner.FAILURE_NONE
        assert detail["retrieved_ranks"] == {"c1": 1, "c2": 2}
        assert detail["expected"] == ["six hours"]

    async def test_existing_report_in_the_output_directory_is_not_replaced(self, tmp_path):
        output = RunOutput(tmp_path)
        report = await _measure()
        runner.write_report(report, "ablation_A", out_dir=output)
        before = (tmp_path / "ablation_A.json").read_bytes()

        with pytest.raises(ArtifactExistsError):
            runner.write_report(report, "ablation_A", out_dir=output)

        assert (tmp_path / "ablation_A.json").read_bytes() == before

    async def test_a_plain_path_is_accepted_as_the_output_directory(self, tmp_path):
        report = await _measure()

        path = runner.write_report(report, "ablation_A", out_dir=tmp_path / "run-9")

        assert path == tmp_path / "run-9" / "ablation_A.json"
        assert path.exists()
