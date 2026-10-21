"""Regression tests for the denominator sensitivity analysis.

The analysis re-aggregates frozen production-aligned per-question results under
the repository-established populations (retrieval → gold-bearing, answer →
answerable, unsupported → unanswerable).  These tests pin the filtering rules,
the empty-population ``null`` rule, the excluded-question count, deterministic
output, and — critically — that the production-aligned reports are never
modified.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from evaluation import denominator_sensitivity as ds
from evaluation.artifacts import ArtifactExistsError


def _q(
    qid: str,
    answerable: bool,
    *,
    recall: float = 1.0,
    em: float = 1.0,
    f1: float = 1.0,
    ec: float = 1.0,
    unsupported: float = 0.0,
) -> dict:
    return {
        "question_id": qid,
        "answerable": answerable,
        "retrieval": {"recall@5": recall, "precision@5": recall, "mrr": recall, "ndcg@5": recall},
        "qa": {"exact_match": em, "token_f1": f1},
        "evidence": {
            "evidence_coverage": ec,
            "factual_grounded": 1.0,
            "path_agreement": 0.0,
            "unsupported_answer": unsupported,
        },
    }


def _write_report(directory: Path, prefix: str, variant: str, results: list[dict]) -> Path:
    metrics: dict[str, float | None] = {}
    for group in ("retrieval", "qa", "evidence"):
        keys = {k for r in results for k in r[group]}
        for key in keys:
            metrics[key] = sum(r[group][key] for r in results) / len(results) if results else 0.0
    # Mirror the corrected runner: unsupported_answer uses the unanswerable
    # population (``None`` when there are none).
    unanswerable = [r for r in results if not r["answerable"]]
    metrics["unsupported_answer"] = (
        sum(r["evidence"]["unsupported_answer"] for r in unanswerable) / len(unanswerable)
        if unanswerable
        else None
    )
    path = directory / f"{prefix}_{variant}.json"
    path.write_text(json.dumps({"metrics": metrics, "results": results}), encoding="utf-8")
    return path


def _analyze_one(tmp_path: Path, results: list[dict]) -> dict:
    _write_report(tmp_path, "ablation", "A", results)
    return ds.analyze_corpus(tmp_path, "phase3d", "ablation", variants=("A",))


def _metric(corpus: dict, metric: str) -> dict:
    return corpus["variants"]["A"]["metrics"][metric]


class TestPopulationFiltering:
    def test_retrieval_uses_gold_bearing_population(self, tmp_path: Path):
        # 3 gold-bearing questions score 1.0; 1 unanswerable scores 0.0.
        results = [_q(f"a{i}", True, recall=1.0) for i in range(3)]
        results.append(_q("u0", False, recall=0.0))
        corpus = _analyze_one(tmp_path, results)

        rec = _metric(corpus, "recall@5")
        assert rec["current"]["value"] == pytest.approx(0.75)      # mean over all 4
        assert rec["current"]["n"] == 4
        assert rec["sensitivity"]["value"] == pytest.approx(1.0)   # mean over 3 gold-bearing
        assert rec["sensitivity"]["n"] == 3
        assert rec["sensitivity"]["population"] == ds.POPULATION_GOLD

    def test_answer_metrics_use_answerable_population(self, tmp_path: Path):
        results = [_q(f"a{i}", True, em=1.0) for i in range(3)]
        results.append(_q("u0", False, em=0.0))
        corpus = _analyze_one(tmp_path, results)

        rec = _metric(corpus, "exact_match")
        assert rec["current"]["value"] == pytest.approx(0.75)
        assert rec["sensitivity"]["value"] == pytest.approx(1.0)
        assert rec["sensitivity"]["population"] == ds.POPULATION_ANSWERABLE

    def test_evidence_coverage_uses_answerable_population(self, tmp_path: Path):
        results = [_q(f"a{i}", True, ec=0.8) for i in range(2)]
        results.append(_q("u0", False, ec=1.0))
        corpus = _analyze_one(tmp_path, results)

        rec = _metric(corpus, "evidence_coverage")
        assert rec["current"]["value"] == pytest.approx((0.8 + 0.8 + 1.0) / 3)
        assert rec["sensitivity"]["value"] == pytest.approx(0.8)

    def test_excluded_question_count(self, tmp_path: Path):
        results = [_q("a0", True)] + [_q("u0", False), _q("u1", False)]
        corpus = _analyze_one(tmp_path, results)
        rec = _metric(corpus, "recall@5")
        assert rec["excluded_questions"] == 2
        assert rec["current"]["n"] - rec["sensitivity"]["n"] == 2


class TestEmptyPopulation:
    def test_no_answerable_questions_yields_null(self, tmp_path: Path):
        results = [_q("u0", False), _q("u1", False)]
        corpus = _analyze_one(tmp_path, results)

        for metric in ("recall@5", "exact_match", "evidence_coverage"):
            rec = _metric(corpus, metric)
            assert rec["sensitivity"]["value"] is None, metric
            assert rec["sensitivity"]["n"] == 0

    def test_matches_runner_aggregate_when_population_is_full(self, tmp_path: Path):
        results = [_q(f"a{i}", True) for i in range(3)]
        corpus = _analyze_one(tmp_path, results)
        rec = _metric(corpus, "recall@5")
        assert rec["current"]["value"] == rec["sensitivity"]["value"] == pytest.approx(1.0)
        assert rec["excluded_questions"] == 0


class TestGroundingAndEvidence:
    def test_factual_grounded_is_not_applicable(self, tmp_path: Path):
        corpus = _analyze_one(tmp_path, [_q("a0", True)])
        statuses = {r["metric"]: r["status"] for r in corpus["notApplicable"]}
        assert statuses["factual_grounded"] == "not_applicable"
        assert "factual_grounded" not in corpus["variants"]["A"]["metrics"]

    def test_path_agreement_is_not_applicable(self, tmp_path: Path):
        corpus = _analyze_one(tmp_path, [_q("a0", True)])
        statuses = {r["metric"]: r["status"] for r in corpus["notApplicable"]}
        assert statuses["path_agreement"] == "not_applicable"


class TestUnsupportedConfirmation:
    def test_confirms_unanswerable_denominator(self, tmp_path: Path):
        results = [_q("a0", True)] + [
            _q("u0", False, unsupported=1.0),
            _q("u1", False, unsupported=0.0),
        ]
        corpus = _analyze_one(tmp_path, results)
        rec = corpus["unsupportedAnswerConfirmation"][0]
        assert rec["failures"] == 1
        assert rec["population"] == 2
        assert rec["human_readable"] == "1/2"
        assert rec["denominator_correct"] is True


class TestDeterminismAndSourceIntegrity:
    def test_output_is_deterministic(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(ds, "REPORTS_DIR", tmp_path)
        results = [_q(f"a{i}", True) for i in range(2)] + [_q("u0", False, recall=0.0)]
        for variant in ds.VARIANTS:
            _write_report(tmp_path, "ablation", variant, results)
        payload = ds.analyze(tmp_path, ["phase3d"])

        ds.write_report(payload, "out")
        first = (tmp_path / "out.json").read_bytes(), (tmp_path / "out.md").read_bytes()

        # The determinism comparison republishes the same name on purpose, so it
        # must ask for it explicitly: the default now refuses and leaves the
        # recorded bytes exactly as they were.
        with pytest.raises(ArtifactExistsError):
            ds.write_report(payload, "out")
        assert (
            (tmp_path / "out.json").read_bytes(),
            (tmp_path / "out.md").read_bytes(),
        ) == first

        ds.write_report(payload, "out", replace=True)
        second = (tmp_path / "out.json").read_bytes(), (tmp_path / "out.md").read_bytes()
        assert first == second

    def test_production_aligned_reports_are_not_modified(self, tmp_path: Path, monkeypatch):
        source = ds.REPORTS_DIR
        ablations = sorted(source.glob("ablation*.json"))
        if not ablations:
            pytest.skip("no production-aligned reports present to check")

        # Copy the frozen reports into a sandbox and point the module at it.
        for path in ablations:
            shutil.copy(path, tmp_path / path.name)
        monkeypatch.setattr(ds, "REPORTS_DIR", tmp_path)

        before = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in tmp_path.glob("ablation*.json")
        }
        payload = ds.analyze(tmp_path)
        ds.write_report(payload, "denominator_sensitivity")
        after = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in tmp_path.glob("ablation*.json")
        }

        assert before == after, "production-aligned reports must not be modified"
        assert (tmp_path / "denominator_sensitivity.json").exists()
        assert (tmp_path / "denominator_sensitivity.md").exists()
        # The sensitivity output is a distinct artifact, never an ablation report.
        assert "denominator_sensitivity" not in {p.name for p in ablations}
