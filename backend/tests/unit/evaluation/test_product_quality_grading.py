"""New product pilot scores remain bounded diagnostics, never invented NHRS."""
from copy import deepcopy
import json

import pytest

from evaluation.product_quality_20261110.run import summarize_ai
from evaluation.research_scoring import _csv_payload, _csv_safe, _display_hash, summarize_reviews


@pytest.fixture
def review_files(tmp_path):
    answer = {
        "answer_id": "blind-answer-a", "question": "Explain the energy conversion.", "marks": 5,
        "answer": "The generator converts mechanical energy into electrical energy.",
        "evidence": "[1] notes.pdf, page 1: The generator converts mechanical energy into electrical energy.",
        "rubric": json.dumps({"criteria": [{"id": "explanation", "max_marks": 5,
                                             "requirements": "Explain the supported conversion."}]}),
    }
    packet = tmp_path / "blind_ai_packet.json"
    packet.write_text(json.dumps({"answers": [answer]}), encoding="utf-8")
    mapping = {"answers": [{
        "answer_id": answer["answer_id"], "question_id": "question-a", "system_id": "current_product",
        "marks": 5, "answerability": "answerable",
        "review_fields_sha256": {key: _display_hash(_csv_safe(answer[key])) for key in
                                 ("question", "marks", "answer", "rubric", "evidence")},
    }]}
    packet.with_name("private_mapping.json").write_text(json.dumps(mapping), encoding="utf-8")
    reviews = [{"reviewer_id": name, "reviewer_kind": "ai", "rows": [{
        "answer_id": answer["answer_id"], "criterion_scores": {"explanation": score}, "total_marks": score,
        "factual_errors": [], "missing_content": [], "diagram_assessment": "No diagram requested.",
        "rationale": "The answer states the supported conversion.",
    }]} for name, score in (("independent-ai-a", 4), ("independent-ai-b", 3))]
    paths = [tmp_path / f"review-{index}.json" for index in range(2)]

    def run(values=None):
        for path, review in zip(paths, values or reviews):
            path.write_text(json.dumps(review), encoding="utf-8")
        output = tmp_path / "summary.json"
        summarize_ai(packet, paths, output)
        return json.loads(output.read_text(encoding="utf-8"))

    return answer, mapping, reviews, run, tmp_path


def test_two_ai_reviews_produce_a_diagnostic_but_no_human_grade(review_files):
    _, _, _, run, _ = review_files
    summary = run()
    assert summary["status"] == "independent_ai_diagnostic_only"
    assert summary["human_nhrs"] is None
    assert summary["answerable_by_marks"]["5"]["mean_ai_normalized_rubric_score"] == pytest.approx(.7)
    assert "not NHRS" in summary["metric"]


@pytest.mark.parametrize("value", [-.01, 5.01, float("nan"), float("inf"), True])
def test_invalid_criterion_score_cannot_enter_a_report(review_files, value):
    _, _, reviews, run, _ = review_files
    changed = deepcopy(reviews)
    changed[0]["rows"][0]["criterion_scores"]["explanation"] = value
    changed[0]["rows"][0]["total_marks"] = value
    with pytest.raises(ValueError):
        run(changed)


def test_grade_total_must_equal_its_criterion_scores(review_files):
    _, _, reviews, run, _ = review_files
    changed = deepcopy(reviews)
    changed[0]["rows"][0]["total_marks"] = 2
    with pytest.raises(ValueError):
        run(changed)


def test_duplicate_answer_cannot_count_as_another_reviewed_answer(review_files):
    _, _, reviews, run, _ = review_files
    changed = deepcopy(reviews)
    changed[0]["rows"].append(deepcopy(changed[0]["rows"][0]))
    with pytest.raises(ValueError):
        run(changed)


@pytest.mark.parametrize("second_id", ["independent-ai-a", " INDEPENDENT-AI-A "])
def test_one_reviewer_cannot_be_counted_as_two_independent_reviewers(review_files, second_id):
    _, _, reviews, run, _ = review_files
    changed = deepcopy(reviews)
    changed[1]["reviewer_id"] = second_id
    with pytest.raises(ValueError):
        run(changed)


@pytest.mark.parametrize("kind", [None, "", "human"])
def test_reviewer_kind_cannot_be_implicitly_upgraded_to_ai_or_human(review_files, kind):
    _, _, reviews, run, _ = review_files
    changed = deepcopy(reviews)
    changed[0]["reviewer_kind"] = kind
    with pytest.raises(ValueError):
        run(changed)


def test_blank_human_sheets_remain_pending_without_nhrs(review_files):
    answer, mapping, _, _, directory = review_files
    row = {**answer, "reviewer": "", "score": "", "accuracy_notes": "", "rubric_notes": ""}
    paths = [directory / f"human-{index}.csv" for index in range(2)]
    for path in paths:
        path.write_text(_csv_payload([row]), encoding="utf-8")
    summary = summarize_reviews(paths, mapping)
    assert summary["status"] == "not_measured"
    assert summary["pending_rows"] == 2
    assert summary["answerable_nhrs"] == []
    assert summary["rows"][0]["nhrs"] is None
