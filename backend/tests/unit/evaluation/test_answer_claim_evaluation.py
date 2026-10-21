"""Regression tests for the actual-answer claim evaluation (2026-10-18).

The evaluation itself needs the local embedder and the recorded benchmark runs,
so the runner is exercised separately (its output is the recorded report).  What
is pinned here is the part that must never drift silently:

* the frozen annotation set exists, is well formed, and describes claims that
  really occur in the recorded answers;
* the frozen benchmark hash still matches the constant the runner enforces;
* the integrity check fails closed on tampered provenance or on an unanswerable
  row, rather than scoring a claim against evidence that was never used;
* the metric code treats partially-supported claims and zero denominators
  honestly, and the confidence interval is a real Wilson interval.
"""

from __future__ import annotations

import dataclasses

import pytest

from evaluation.datasets import answer_claims_v1, answer_claims_v2
from evaluation.experiments import run_answer_claim_evaluation as runner


@pytest.fixture(scope="module")
def claims():
    return answer_claims_v1.load()


@pytest.fixture(scope="module")
def benchmark():
    rows = runner.load_benchmark(runner.BENCHMARK_PATH)
    return {str(row["example_id"]): row for row in rows}


@pytest.fixture(scope="module")
def runs():
    return {mode: runner._load_run(run_id) for mode, run_id in runner.RUN_DIRS.items()}


class TestFrozenDataset:
    def test_counts(self, claims):
        stats = answer_claims_v1.statistics(claims)
        assert stats["total"] == 104
        assert stats["examples"] == 86
        assert stats["propositional"] == 75
        assert stats["non_claims"] == 29
        assert stats["labels"] == {
            "SUPPORTED": 66,
            "CONTRADICTED": 5,
            "INSUFFICIENT_EVIDENCE": 2,
            "PARTIALLY_SUPPORTED": 2,
            "NOT_A_CLAIM": 29,
        }

    def test_claim_ids_are_unique(self, claims):
        ids = [claim.claim_id for claim in claims]
        assert len(ids) == len(set(ids))

    def test_provenance_is_known(self, claims):
        for claim in claims:
            assert set(claim.produced_by) <= {"lexical", "relations"}
            assert claim.produced_by

    def test_non_claims_are_separated_from_propositions(self, claims):
        for claim in claims:
            if claim.label == answer_claims_v1.NOT_A_CLAIM:
                assert claim.is_propositional is False
                assert claim.answers_question is None
            else:
                assert claim.is_propositional is True
                assert claim.answers_question is not None

    def test_partial_support_is_not_full_support(self, claims):
        for claim in claims:
            if claim.label == answer_claims_v1.PARTIAL:
                assert claim.fully_supported is False

    def test_every_claim_has_a_rationale(self, claims):
        for claim in claims:
            assert claim.rationale.strip()


class TestIntegrityContract:
    def test_frozen_benchmark_hash_matches_the_enforced_constant(self):
        assert runner.sha256_of(runner.BENCHMARK_PATH) == runner.EXPECTED_SHA256

    def test_dataset_matches_the_recorded_answers(self, claims, benchmark, runs):
        # Fails (not skips) if the recorded runs are missing: the dataset is only
        # meaningful next to the answers it was drawn from.
        assert set(runs) == {"lexical", "relations"}
        integrity = runner.validate_inputs(
            claims, benchmark, runs, answer_claims_v1.split_claims
        )
        assert integrity["claims"] == 104
        assert integrity["answerable_rows"] == 140

    def test_tampered_provenance_fails_closed(self, claims, benchmark, runs):
        original = next(claim for claim in claims if claim.produced_by == ("lexical",))
        tampered = [
            dataclasses.replace(original, produced_by=("relations",))
            if claim.claim_id == original.claim_id
            else claim
            for claim in claims
        ]
        with pytest.raises(SystemExit, match="integrity failed"):
            runner.validate_inputs(
                tampered, benchmark, runs, answer_claims_v1.split_claims
            )

    def test_unanswerable_row_fails_closed(self, claims, benchmark, runs):
        unanswerable = next(
            example_id
            for example_id, row in benchmark.items()
            if row.get("question_kind") == "UNANSWERABLE"
        )
        original = claims[0]
        tampered = [
            dataclasses.replace(original, example_id=unanswerable)
            if claim.claim_id == original.claim_id
            else claim
            for claim in claims
        ]
        with pytest.raises(SystemExit, match="integrity failed"):
            runner.validate_inputs(
                tampered, benchmark, runs, answer_claims_v1.split_claims
            )


class TestVersionedDatasets:
    """v1 and v2 differ only in the re-extracted claim boundary."""

    @pytest.fixture(scope="class")
    def v2_claims(self):
        return answer_claims_v2.load()

    def test_v1_is_unchanged(self, claims):
        assert len(claims) == 104
        assert {"Dr.", "Sarah Chen"} <= {claim.claim for claim in claims}

    def test_v2_counts(self, v2_claims):
        stats = answer_claims_v2.statistics(v2_claims)
        assert stats["total"] == 103
        assert stats["examples"] == 86
        assert stats["propositional"] == 75
        assert stats["non_claims"] == 28
        assert stats["labels"] == {
            "SUPPORTED": 66,
            "CONTRADICTED": 5,
            "INSUFFICIENT_EVIDENCE": 2,
            "PARTIALLY_SUPPORTED": 2,
            "NOT_A_CLAIM": 28,
        }

    def test_v2_contains_the_merged_reannotation(self, v2_claims):
        merged = [c for c in v2_claims if c.claim_id == "ac_c411173a36"]
        assert len(merged) == 1
        claim = merged[0]
        assert claim.claim == "Dr. Sarah Chen"
        assert claim.example_id == "li_ab55f3c4"
        assert claim.label == answer_claims_v2.SUPPORTED
        assert claim.answers_question is True

    def test_v2_mapping_matches_the_records(self, v2_claims):
        ids = {claim.claim_id for claim in v2_claims}
        for removed in answer_claims_v2.CHANGES["removed"]:
            assert removed["claim_id"] not in ids
        for added in answer_claims_v2.CHANGES["added"]:
            assert added["claim_id"] in ids

    def test_v2_ids_are_unique(self, v2_claims):
        ids = [claim.claim_id for claim in v2_claims]
        assert len(ids) == len(set(ids))

    def test_v2_keeps_every_unchanged_v1_id(self, claims, v2_claims):
        """Only the two merged records lose their ids; nothing else is re-keyed."""
        removed = {record["claim_id"] for record in answer_claims_v2.CHANGES["removed"]}
        added = {record["claim_id"] for record in answer_claims_v2.CHANGES["added"]}
        assert {claim.claim_id for claim in claims} - removed == {
            claim.claim_id for claim in v2_claims
        } - added

    def test_v2_matches_the_corrected_extractor(self, v2_claims, benchmark, runs):
        """Every v2 claim is what the production splitter now emits, and vice versa."""
        expected = set()
        for rows in runs.values():
            for row in rows.values():
                example_id = str(row["example_id"])
                if benchmark[example_id].get("question_kind") == "UNANSWERABLE":
                    continue  # the dataset annotates answerable rows only
                for claim in answer_claims_v2.split_claims(
                    str(row.get("generative_answer") or "")
                ):
                    expected.add((example_id, claim))
        actual = {(claim.example_id, claim.claim) for claim in v2_claims}
        assert actual == expected

    def test_v2_passes_the_integrity_check(self, v2_claims, benchmark, runs):
        integrity = runner.validate_inputs(
            v2_claims, benchmark, runs, answer_claims_v2.split_claims
        )
        assert integrity["claims"] == 103
        assert integrity["answerable_rows"] == 140

    def test_v1_pins_the_frozen_extractor(self):
        assert answer_claims_v1.split_claims("Dr. Sarah Chen") == ["Dr.", "Sarah Chen"]
        assert answer_claims_v2.split_claims("Dr. Sarah Chen") == ["Dr. Sarah Chen"]


class TestVerifierInvocationContract:
    def test_relations_call_passes_the_question(self, monkeypatch):
        """Production passes the question; omitting it changes the verifier under test.

        An independent audit caught this omission in the first version of the
        runner: every value-only claim is attributed through the question, so the
        call must carry it even when a particular claim's verdict does not move.
        """
        from types import SimpleNamespace

        import generation.verification_relations as relations

        captured = {}

        def fake_verify(claim, blocks, stated_citations=(), question=None):
            captured["claim"] = claim
            captured["question"] = question
            captured["blocks"] = blocks
            return SimpleNamespace(
                label="SUPPORTED",
                explanation="stub",
                supporting_blocks=[1],
                contradicting_blocks=[],
                citation_ok=True,
                best_support_score=1.0,
            )

        monkeypatch.setattr(relations, "verify_claim", fake_verify)
        result = runner._relations("30 days", "calibration every 30 days", "What is the interval?")
        assert captured["question"] == "What is the interval?"
        assert captured["claim"] == "30 days"
        assert len(captured["blocks"]) == 1
        assert result["label"] == "SUPPORTED"

    def test_both_verifiers_receive_the_same_inputs(self, monkeypatch):
        """One evidence list, one claim, one question — no drift between calls."""
        from types import SimpleNamespace

        import generation.verification as lexical
        import generation.verification_relations as relations

        captured = {}

        def fake_check(claim, blocks, question=None):
            captured["lexical"] = (claim, blocks, question)
            return SimpleNamespace(supported=True, reason="", citation_indices=[1])

        def fake_verify(claim, blocks, stated_citations=(), question=None):
            captured["relations"] = (claim, blocks, question)
            return SimpleNamespace(
                label="SUPPORTED",
                explanation="stub",
                supporting_blocks=[1],
                contradicting_blocks=[],
                citation_ok=True,
                best_support_score=1.0,
            )

        monkeypatch.setattr(lexical, "check_claim", fake_check)
        monkeypatch.setattr(relations, "verify_claim", fake_verify)
        lexical_out, relations_out, _, _ = runner.verify_both(
            "30 days", "calibration every 30 days", "What is the interval?"
        )

        assert captured["lexical"][0] == captured["relations"][0] == "30 days"
        assert captured["lexical"][2] == captured["relations"][2] == "What is the interval?"
        assert captured["lexical"][1] is captured["relations"][1]
        assert [(block.index, block.content) for block in captured["lexical"][1]] == [
            (1, "calibration every 30 days")
        ]
        assert lexical_out["label"] == relations_out["label"] == "SUPPORTED"

    def test_lexical_entity_conflict_is_not_reported_as_contradiction(self, monkeypatch):
        from types import SimpleNamespace

        import generation.verification as lexical

        monkeypatch.setattr(
            lexical,
            "check_claim",
            lambda *args, **kwargs: SimpleNamespace(
                supported=False,
                reason="value appears in the evidence but belongs to a different entity",
                citation_indices=[],
            ),
        )
        result = runner._lexical("Elena Vasquez", "CFO: Robert Tanaka", "Who is CFO?")
        assert result["label"] == "UNSUPPORTED"
        assert result["entity_conflict"] is True


def _row(gold: str, lexical: str, relations: str, answers_question=True) -> dict:
    return {
        "gold": gold,
        "lexical_label": lexical,
        "relations_label": relations,
        "answers_question": answers_question,
    }


class TestMetrics:
    def test_perfect_decisions(self):
        rows = [
            _row("SUPPORTED", "SUPPORTED", "SUPPORTED"),
            _row("CONTRADICTED", "UNSUPPORTED", "CONTRADICTED"),
            _row("INSUFFICIENT_EVIDENCE", "UNSUPPORTED", "INSUFFICIENT_EVIDENCE"),
        ]
        metrics = runner._metrics(rows, "relations")
        assert metrics["support_precision"] == 1.0
        assert metrics["support_recall"] == 1.0
        assert metrics["false_accept_count"] == 0
        assert metrics["false_reject_count"] == 0
        assert metrics["contradiction_recall"] == 1.0
        assert metrics["insufficient_correct"] == 1

    def test_partial_accepted_is_a_false_accept_but_reported_separately(self):
        rows = [_row("PARTIALLY_SUPPORTED", "SUPPORTED", "SUPPORTED")]
        metrics = runner._metrics(rows, "lexical")
        assert metrics["false_accept_count"] == 1
        assert metrics["partial_accepted"] == 1
        assert metrics["false_accept_rate"] == 1.0

    def test_zero_denominators_are_none_not_zero(self):
        rows = [_row("SUPPORTED", "SUPPORTED", "SUPPORTED")]
        metrics = runner._metrics(rows, "lexical")
        assert metrics["false_accept_rate"] is None
        assert metrics["contradiction_precision"] is None
        assert metrics["contradiction_recall"] is None
        assert metrics["contradiction_f1"] is None

    def test_contradiction_f1_is_undefined_without_positive_predictions(self):
        # Lexical makes no contradiction prediction at all.
        rows = [_row("CONTRADICTED", "UNSUPPORTED", "CONTRADICTED")]
        metrics = runner._metrics(rows, "lexical")
        assert metrics["contradiction_precision"] is None
        assert metrics["contradiction_recall"] == 0.0
        assert metrics["contradiction_f1"] is None

    def test_support_f1_is_undefined_without_positive_reference_claims(self):
        rows = [_row("CONTRADICTED", "UNSUPPORTED", "UNSUPPORTED")]
        metrics = runner._metrics(rows, "lexical")
        assert metrics["support_recall"] is None
        assert metrics["support_f1"] is None

    def test_support_metrics_do_not_treat_rejection_as_contradiction(self):
        rows = [_row("CONTRADICTED", "UNSUPPORTED", "SUPPORTED")]
        metrics = runner._metrics(rows, "lexical")
        assert metrics["contradiction_false_positives"] == 0
        assert metrics["contradiction_false_negatives"] == 1
        assert metrics["false_accept_count"] == 0
        assert metrics["binary_decision_accuracy"] == 1.0

    def test_answer_relevance_counts_only_supported_off_target_claims(self):
        rows = [
            _row("SUPPORTED", "SUPPORTED", "SUPPORTED", answers_question=False),
            _row("CONTRADICTED", "UNSUPPORTED", "SUPPORTED", answers_question=False),
            _row("SUPPORTED", "SUPPORTED", "SUPPORTED", answers_question=True),
        ]
        relevance = runner._answer_relevance(rows)
        assert relevance["off_target_claims"] == 2
        assert relevance["supported_off_target"] == 1
        assert relevance["supported_off_target_lexical_accepted"] == 1
        assert relevance["supported_off_target_relations_accepted"] == 1


class TestWilsonInterval:
    def test_empty_sample_has_no_interval(self):
        assert runner.wilson_interval(0, 0) is None

    def test_half_sample_is_symmetric_around_one_half(self):
        low, high = runner.wilson_interval(5, 10)
        assert low == pytest.approx(0.2366, abs=1e-4)
        assert high == pytest.approx(0.7634, abs=1e-4)

    def test_bounds_stay_inside_the_unit_interval(self):
        assert runner.wilson_interval(0, 10)[0] == 0.0
        assert runner.wilson_interval(10, 10)[1] == 1.0
        assert 0.0 < runner.wilson_interval(0, 10)[1] < 1.0
        assert 0.0 < runner.wilson_interval(10, 10)[0] < 1.0

    def test_interval_widens_with_smaller_samples(self):
        small = runner.wilson_interval(1, 4)
        large = runner.wilson_interval(25, 100)
        assert (small[1] - small[0]) > (large[1] - large[0])
