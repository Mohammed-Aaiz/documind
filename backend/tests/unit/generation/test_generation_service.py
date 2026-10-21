"""Generation service policy — no model download required."""

from types import SimpleNamespace

import pytest

from generation import service
from generation.types import GenerationResult, VerificationReport


def _chunk(chunk_id="c1", content="The lidar array requires calibration every 30 days.", **kw):
    base = dict(
        chunk_id=chunk_id,
        content=content,
        score=0.77,
        document_id="d1",
        document_name="sample.txt",
        page=3,
        heading_path=("Calibration",),
        section="Calibration",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _result(answer, *, supported=1, total=1, verified=True):
    return GenerationResult(
        answer=answer,
        abstained=False,
        verification=VerificationReport(
            claims=[],
            citation_accuracy=supported / total if total else 0.0,
            supported_claims=supported,
            unsupported_claims=[] if verified else [answer],
            uncited_claims=0 if verified else 1,
            verified=verified,
        ),
        model="google/flan-t5-base",
        marks=10,
        latency_ms=5,
    )


class TestEvidenceBlocks:
    def test_provenance_is_preserved(self):
        blocks = service.build_evidence_blocks([_chunk()])
        assert len(blocks) == 1
        block = blocks[0]
        assert block.index == 1
        assert block.document_name == "sample.txt"
        assert block.page == 3
        assert block.section == "Calibration"

    def test_duplicate_chunk_ids_are_not_cited_twice(self):
        blocks = service.build_evidence_blocks([_chunk(), _chunk()])
        assert len(blocks) == 1

    def test_empty_evidence_yields_no_blocks(self):
        assert service.build_evidence_blocks([_chunk(content="   ")]) == []


class TestGroundingPolicy:
    def test_no_evidence_abstains_without_calling_the_model(self, monkeypatch):
        calls = []
        monkeypatch.setattr(service, "generate", lambda *a, **k: calls.append(1))
        result = service.answer_generatively("How often?", [])
        assert result.abstained is True
        assert result.insufficient_context is True
        assert result.answer == ""
        assert calls == []

    def test_supported_answer_is_returned_verified(self, monkeypatch):
        # 5-mark format: this test is about grounding, not depth.  Longer formats
        # legitimately warn when the evidence cannot support more points.
        fake = _result("every 30 days")
        fake.marks = 5
        monkeypatch.setattr(service, "generate", lambda *a, **k: fake)
        result = service.answer_generatively("How often?", [_chunk()], answer_format="5")
        assert result.answer == "every 30 days"
        assert result.abstained is False
        assert result.verification["verified"] is True
        assert result.warnings == []

    def test_unattributable_answer_is_withheld(self, monkeypatch):
        # The question's terms ARE in the evidence (so the answerability gate
        # passes); the generated text is not attributable to it.
        monkeypatch.setattr(
            service, "generate", lambda *a, **k: _result("lithium battery", supported=0, verified=False)
        )
        result = service.answer_generatively(
            "What is the calibration interval for the lidar array?", [_chunk()]
        )
        assert result.answer == ""
        assert result.abstained is True
        assert result.insufficient_context is True
        assert result.verification["status"] == "INSUFFICIENT_EVIDENCE"
        assert any("withheld" in warning for warning in result.warnings)

    def test_question_terms_absent_from_evidence_abstain_without_generating(self, monkeypatch):
        calls = []
        monkeypatch.setattr(service, "generate", lambda *a, **k: calls.append(1))
        result = service.answer_generatively("What is the battery chemistry?", [_chunk()])
        assert calls == []
        assert result.abstained is True
        assert result.verification["status"] == "INSUFFICIENT_EVIDENCE"
        assert any("does not cover" in warning for warning in result.warnings)

    def test_partially_supported_answer_is_returned_with_a_warning(self, monkeypatch):
        monkeypatch.setattr(
            service, "generate", lambda *a, **k: _result("a. b.", supported=1, total=2, verified=False)
        )
        result = service.answer_generatively("How often?", [_chunk()])
        assert result.answer
        assert result.abstained is False
        assert any("not supported" in warning for warning in result.warnings)

    def test_model_reported_abstention_is_surfaced(self, monkeypatch):
        result = _result("")
        result.abstained = True
        monkeypatch.setattr(service, "generate", lambda *a, **k: result)
        out = service.answer_generatively("How often?", [_chunk()])
        assert out.abstained is True
        assert any("does not answer" in warning for warning in out.warnings)
