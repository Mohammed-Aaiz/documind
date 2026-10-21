"""STEP 1.6Y: the historical ``write_report`` path must not replace evidence.

``evaluation/runner.py`` wrote the recorded research reports into
``evaluation/reports/`` with ``Path.write_text``, so a re-run silently replaced a
same-named report and the previous run's evidence was gone.  The branch is now
append-only: it refuses an existing artifact with ``ArtifactExistsError`` before
writing either file, and a deliberate re-publication has to pass
``replace=True``.

These tests keep the ``reports/`` directory inside ``tmp_path``; nothing here
writes to the real ``evaluation/reports/``.
"""

from __future__ import annotations

import json

import pytest

from evaluation import runner
from evaluation.artifacts import ArtifactExistsError, RunOutput
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


async def _measure(*, answer="six hours", retrieved=("c1", "c2"), supplied=("c1",)):
    async def retrieve(_question):
        return list(retrieved)

    async def answer_fn(_question, _ids):
        return {
            "answer": answer,
            "confidence": 0.9,
            "insufficient_context": False,
            "factual_grounded": bool(answer),
            "supplied_chunk_ids": list(supplied),
            "retrieval_paths": ["hybrid"],
            "structural_hops": [0],
        }

    return await runner.run_baseline(
        Baseline.B4_DUAL_PATH, [_question()], retrieve, answer_fn
    )


@pytest.fixture
def reports_dir(tmp_path, monkeypatch):
    """Point the historical archive at a scratch directory."""
    directory = tmp_path / "reports"
    monkeypatch.setattr(runner, "REPORTS_DIR", directory)
    return directory


class TestHistoricalPathIsAppendOnly:
    async def test_first_write_succeeds_then_a_rerun_refuses(self, reports_dir):
        path = runner.write_report(await _measure(answer="six hours"), "ablation_A")
        assert path == reports_dir / "ablation_A.json"

        json_before = path.read_bytes()
        markdown = reports_dir / "ablation_A.md"
        assert markdown.exists()
        markdown_before = markdown.read_bytes()

        with pytest.raises(ArtifactExistsError):
            runner.write_report(await _measure(answer="seven hours"), "ablation_A")

        assert path.read_bytes() == json_before, "the JSON report was preserved"
        assert markdown.read_bytes() == markdown_before, "the markdown was preserved"

    async def test_refusal_names_the_path_and_the_explicit_opt_in(self, reports_dir):
        runner.write_report(await _measure(), "ablation_A")

        with pytest.raises(ArtifactExistsError) as error:
            runner.write_report(await _measure(answer="seven hours"), "ablation_A")

        message = str(error.value)
        assert "ablation_A.json" in message
        assert "replace=True" in message, (
            "the refusal has to tell the caller how to re-publish deliberately"
        )

    async def test_replace_true_republishes_on_purpose(self, reports_dir):
        path = runner.write_report(await _measure(answer="six hours"), "ablation_A")
        first = json.loads(path.read_text(encoding="utf-8"))

        runner.write_report(
            await _measure(answer="seven hours"), "ablation_A", replace=True
        )
        second = json.loads(path.read_text(encoding="utf-8"))

        assert first["metrics"]["exact_match"] == pytest.approx(1.0)
        assert second["metrics"]["exact_match"] == pytest.approx(0.0)

    async def test_colliding_json_leaves_no_partial_pair(self, reports_dir):
        # Only the JSON exists: the markdown from that earlier run is gone, so a
        # refusal that wrote the markdown first would leave a mismatched pair.
        path = runner.write_report(await _measure(), "ablation_A")
        (reports_dir / "ablation_A.md").unlink()
        json_before = path.read_bytes()

        with pytest.raises(ArtifactExistsError):
            runner.write_report(await _measure(answer="seven hours"), "ablation_A")

        assert sorted(p.name for p in reports_dir.iterdir()) == ["ablation_A.json"]
        assert path.read_bytes() == json_before

    async def test_colliding_markdown_does_not_create_a_json(self, reports_dir):
        runner.write_report(await _measure(), "ablation_A")
        json_path = reports_dir / "ablation_A.json"
        json_path.unlink()
        markdown_before = (reports_dir / "ablation_A.md").read_bytes()

        with pytest.raises(ArtifactExistsError):
            runner.write_report(await _measure(answer="seven hours"), "ablation_A")

        assert sorted(p.name for p in reports_dir.iterdir()) == ["ablation_A.md"]
        assert (reports_dir / "ablation_A.md").read_bytes() == markdown_before

    async def test_written_json_keeps_the_historical_serialization(self, reports_dir):
        path = runner.write_report(await _measure(), "ablation_A")
        text = path.read_text(encoding="utf-8")

        # The same json.dumps(payload, indent=2, sort_keys=True) contract as the
        # pre-1.6Y write: re-dumping the parsed payload reproduces the file.
        assert text == json.dumps(json.loads(text), indent=2, sort_keys=True)
        assert "\r" not in text, "RunOutput/write_evidence normalise newlines to LF"


class TestProvidedOutputDirectoryIsUnchanged:
    async def test_out_dir_still_uses_run_output_and_never_the_archive(
        self, tmp_path, monkeypatch, reports_dir
    ):
        output = RunOutput(tmp_path / "run-1")
        report = await _measure()

        path = runner.write_report(report, "ablation_A", out_dir=output)

        assert path == tmp_path / "run-1" / "ablation_A.json"
        assert (tmp_path / "run-1" / "ablation_A.md").exists()
        assert not reports_dir.exists(), (
            "a caller-supplied directory is never mixed with the recorded archive"
        )
        with pytest.raises(ArtifactExistsError):
            runner.write_report(report, "ablation_A", out_dir=output)

    async def test_plain_path_out_dir_is_also_append_only(self, tmp_path, reports_dir):
        report = await _measure()

        runner.write_report(report, "ablation_A", out_dir=tmp_path / "run-2")

        with pytest.raises(ArtifactExistsError):
            runner.write_report(report, "ablation_A", out_dir=tmp_path / "run-2")
