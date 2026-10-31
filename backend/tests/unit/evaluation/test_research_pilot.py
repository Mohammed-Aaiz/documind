"""Research measurement/wiring regressions; no neural, DB or quality claims."""
from dataclasses import dataclass
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path

import pytest

from evaluation import research_scoring as scoring
from evaluation import research_retrieval as retrieval


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.fixture
def annotated():
    text = "Ada links A to B. B links to C. Repeat. Repeat."
    doc = {"id": "source", "raw_file_sha256": digest(text), "bundle_id": "bundle",
           "split": "development", "topic_ids": ["link"], "pages": [
               {"page": n, "canonical_text": text, "canonical_text_sha256": digest(text)}
               for n in (1, 2)]}
    def span(start, end, page=1):
        return {"document_id": "source", "page": page, "start_char": start,
                "end_char": end, "quote": text[start:end], "topic_id": "link"}
    question = {"id": "q", "question": "Explain the link.", "designated_marks": 5,
                "bundle_id": "bundle", "split": "development", "category": "relational_multihop",
                "answerability": "answerable", "required_evidence_units": [
                    {"id": "u", "alternatives": [{"all_of": [span(0, 16), span(17, 30)]}]}],
                "rubrics": {"5": {"max_marks": 5, "criteria": [{"max_marks": 3}, {"max_marks": 2}]}},
                "independent_annotation_reviews": []}
    dataset = {"status": "draft_unreviewed", "documents": [doc], "questions": [question]}
    record = {"question_id": "q", "system_id": "hidden-system", "context_text": "[1] source page 1\n" + text,
              "excerpts": [{"document_id": "source", "page": 1, "start_char": 0,
                            "end_char": len(text), "text": text}], "answer": "Ada connects A to C [1]."}
    return dataset, {"records": [record]}, span


def test_required_units_use_and_bundles_or_alternatives_without_page_leakage(annotated):
    dataset, _, span = annotated
    question = dataset["questions"][0]
    assert scoring.evidence_metrics(question, {("source", 1): [(0, 16)]})["rer"] == 0
    assert scoring.evidence_metrics(question, {("source", 2): [(0, 30)]})["rer"] == 0
    assert scoring.evidence_metrics(question, {("wrong", 1): [(0, 30)]})["rer"] == 0
    question["required_evidence_units"][0]["alternatives"].append({"all_of": [span(0, 16)]})
    assert scoring.evidence_metrics(question, {("source", 1): [(0, 16)]})["rer"] == 1


@pytest.mark.parametrize("intervals,expected", [
    ([(0, 8), (8, 30)], 1), ([(0, 20), (10, 30)], 1),
    ([(0, 7), (8, 30)], 0), ([(0, 30), (0, 30)], 1),
])
def test_source_interval_union_keeps_uncovered_gaps(annotated, intervals, expected):
    dataset, run, _ = annotated
    text = dataset["documents"][0]["pages"][0]["canonical_text"]
    record = run["records"][0]
    record["excerpts"] = [{"document_id": "source", "page": 1, "start_char": lo,
                            "end_char": hi, "text": text[lo:hi]} for lo, hi in intervals]
    assert scoring.score_run(dataset, run)["rows"][0]["rer"] == expected


def test_ambiguous_or_changed_source_mapping_is_rejected(annotated):
    dataset, run, _ = annotated
    excerpt = run["records"][0]["excerpts"][0]
    excerpt.clear()
    excerpt.update(document_id="source", page=1, text="Repeat.")
    with pytest.raises(ValueError, match="ambiguous"):
        scoring.score_run(dataset, run)
    start = dataset["documents"][0]["pages"][0]["canonical_text"].index("Repeat.")
    excerpt.update(start_char=start, end_char=start + len("Repeat."), source_sha256="0" * 64)
    with pytest.raises(ValueError, match="revision"):
        scoring.score_run(dataset, run)


@pytest.mark.parametrize("identity", [None, {"exact": True},
    {"exact": True, "generation_compatible": True, "compatibility_verified": False}])
def test_unverified_or_estimated_counter_never_produces_primary_ect(annotated, identity):
    dataset, run, _ = annotated
    calls = []
    result = scoring.score_run(dataset, run, lambda text: calls.append(text) or 1, identity)
    assert result["rows"][0]["rer"] == 1
    assert result["rows"][0]["ect1000"] is None and calls == []
    assert result["status"] == "draft_annotation_diagnostic_not_confirmatory"


def test_exact_denominator_keeps_serialized_headers_and_duplicate_text(annotated):
    dataset, run, _ = annotated
    record = run["records"][0]
    record["context_text"] *= 2
    record["excerpts"] *= 2
    calls = []
    identity = {"exact": True, "generation_compatible": True, "compatibility_verified": True,
                "status": "test_counter_only"}
    result = scoring.score_run(dataset, run, lambda text: calls.append(text) or 40, identity)
    assert calls == [record["context_text"]]
    assert result["rows"][0]["covered_units"] == 1
    assert result["rows"][0]["ect1000"] == 25


def test_empty_context_and_unanswerable_have_no_infinite_efficiency(annotated):
    dataset, run, _ = annotated
    run["records"][0].update(context_text="", excerpts=[])
    row = scoring.score_run(dataset, run)["rows"][0]
    assert row["rer"] == 0 and row["ect1000"] is None
    dataset["questions"][0].update(answerability="unanswerable", required_evidence_units=[])
    row = scoring.score_run(dataset, run)["rows"][0]
    assert row["rer"] is None and row["ect1000"] is None


@pytest.mark.asyncio
async def test_jsonl_serialization_preserves_real_prompt_evidence_and_counts_headers(annotated, wiring):
    from generation.provider_prompt import prepare_prompt
    from generation.types import AnswerFormat

    dataset, run, _ = annotated
    source = 'Calibration uses a "reference rig" for Δ alignment.\nThe source path C:\\notes preserves the original PDF line break.'
    assert "\n" in source and "\\" in source
    doc = dataset["documents"][0]
    doc.update(raw_file_sha256=digest(source), pages=[{
        "page": 1, "canonical_text": source, "canonical_text_sha256": digest(source)}])
    dataset["questions"][0]["required_evidence_units"] = [{"id": "u", "alternatives": [{"all_of": [{
        "document_id": "source", "page": 1, "start_char": 0, "end_char": len(source),
        "quote": source, "topic_id": "link"}]}]}]
    chunk = Chunk("chunk", source)
    # The real production assembler emits escaped JSONL; substring matching
    # against the raw JSON bytes cannot establish evidence coverage.
    prepared = prepare_prompt("Explain calibration", [chunk], [], workspace="student", task="answer",
                              answer_format=AnswerFormat.FIVE, context_tokens=8192)
    context = prepared.messages[-1]["content"].split("\nSource data (JSON):\n", 1)[1]
    fitted = retrieval.fit_prompt("Explain calibration", [chunk], 5, 8192)
    assert fitted["context_text"] == context and fitted["context_format"] == "jsonl_evidence"
    assert source not in context and json.loads(context)["text"] == source
    functions, _ = wiring
    async def retrieve_fixture(*args): return [chunk]
    record = await retrieval.compare(None, "owner", "Explain calibration", 5, "dense",
        functions={**functions, "dense": retrieve_fixture, "fit": retrieval.fit_prompt})
    record["question_id"] = "q"
    assert record["context_text"] == context
    assert record["excerpts"][0]["context_source"] == 1
    record["excerpts"][0].update(start_char=0, end_char=len(source))
    run["records"] = [record]
    counted = []
    identity = {"exact": True, "generation_compatible": True, "compatibility_verified": True,
                "status": "fixture_counter_not_research_tokenizer"}
    result = scoring.score_run(dataset, run, lambda text: counted.append(text) or 25, identity)
    assert result["rows"][0]["rer"] == 1 and result["rows"][0]["ect1000"] == 40
    assert counted == [context]  # Includes labels and JSON escapes, not just source prose.
    run["records"][0]["context_text"] = json.dumps({"source": 1, "page": 1,
        "document": source, "text": "Unrelated text; the quote occurs only in metadata."})
    with pytest.raises(ValueError, match="metadata is not evidence"):
        scoring.score_run(dataset, run)


def test_duplicate_jsonl_labels_cannot_supply_an_ambiguous_origin(annotated):
    dataset, run, _ = annotated
    record = run["records"][0]
    text = record["excerpts"][0]["text"]
    row = json.dumps({"source": 1, "page": 1, "text": text})
    record.update(context_text=row + "\n" + row, context_format="jsonl_evidence")
    record["excerpts"][0]["context_source"] = 1
    with pytest.raises(ValueError, match="ambiguous"):
        scoring.score_run(dataset, run)


@pytest.mark.parametrize("maximum", [float("nan"), float("inf"), -1])
def test_invalid_rubric_maxima_are_rejected_even_if_other_marks_compensate(annotated, maximum):
    dataset, _, _ = annotated
    criteria = dataset["questions"][0]["rubrics"]["5"]["criteria"]
    criteria[0]["max_marks"] = maximum
    criteria[1]["max_marks"] = 5 - maximum
    with pytest.raises(ValueError):
        scoring.validate_dataset(dataset)


def review_rows(annotated):
    dataset, run, _ = annotated
    payload, mapping = scoring.review_pack(dataset, run)
    assert "hidden-system" not in payload and "system_id" not in payload
    assert "question_id" not in payload and "reliability" not in payload
    return list(csv.DictReader(io.StringIO(payload))), mapping


def write_csv(path, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(stream.getvalue(), encoding="utf-8")


def test_blinded_reviews_need_two_real_distinct_ratings(annotated, tmp_path):
    rows, mapping = review_rows(annotated)
    path = tmp_path / "ratings.csv"
    write_csv(path, rows)
    result = scoring.summarize_reviews([path], mapping)
    assert result["status"] == "not_measured" and result["rows"][0]["nhrs"] is None
    rows[0].update(reviewer="reviewer A", score="4")
    write_csv(path, rows)
    assert scoring.summarize_reviews([path], mapping)["rows"][0]["nhrs"] is None
    rows.append({**rows[0], "reviewer": "reviewer B", "score": "3"})
    write_csv(path, rows)
    result = scoring.summarize_reviews([path], mapping)
    assert result["rows"][0]["nhrs"] == .7
    assert result["answerable_nhrs"] == [{"system_id": "hidden-system", "marks": 5,
                                          "questions": 1, "nhrs_mean": .7}]


@pytest.mark.parametrize("field", ["question", "answer", "rubric", "evidence", "marks"])
def test_review_import_rejects_changed_graded_content(annotated, tmp_path, field):
    rows, mapping = review_rows(annotated)
    rows[0][field] += " changed"
    rows[0].update(reviewer="A", score="4")
    path = tmp_path / "ratings.csv"
    write_csv(path, rows)
    with pytest.raises(ValueError, match="altered"):
        scoring.summarize_reviews([path], mapping)


@pytest.mark.parametrize("score", ["nan", "inf", "-1", "6"])
def test_grades_are_finite_and_within_designated_marks(annotated, tmp_path, score):
    rows, mapping = review_rows(annotated)
    rows[0].update(reviewer="A", score=score)
    path = tmp_path / "ratings.csv"
    write_csv(path, rows)
    with pytest.raises(ValueError):
        scoring.summarize_reviews([path], mapping)


def test_same_reviewer_cannot_count_twice_under_different_case(annotated, tmp_path):
    rows, mapping = review_rows(annotated)
    rows[0].update(reviewer="Reviewer A", score="4")
    rows.append({**rows[0], "reviewer": "reviewer a"})
    path = tmp_path / "ratings.csv"
    write_csv(path, rows)
    with pytest.raises(ValueError, match="duplicate"):
        scoring.summarize_reviews([path], mapping)


@dataclass
class Chunk:
    chunk_id: str
    content: str
    document_id: str = "source"
    document_name: str = "notes.pdf"
    page: int = 1
    score: float = .8
    heading_path: tuple | None = None
    section: str | None = None
    fusion_score: float = 0.
    knowledge_graph_path: str | None = None
    knowledge_graph_hops: int | None = None
    knowledge_graph_predicate: str | None = None
    knowledge_graph_quote: str | None = None


@pytest.fixture
def wiring():
    calls = []
    chunks = {name: Chunk(name, name + " evidence.") for name in ("base", "structure", "graph", "topic", "parent")}
    async def readonly(db): calls.append(("readonly",))
    async def dense(db, owner, question, depth): calls.append(("dense", owner, question, depth)); return [chunks["base"]]
    async def hybrid(db, owner, question, depth): calls.append(("hybrid", owner, question, depth)); return [chunks["base"]]
    async def structure(db, owner, question, values, depth): calls.append(("structure",)); return values + [chunks["structure"]]
    async def status(db, owner): calls.append(("graph_status",)); return "ready"
    async def graph(db, owner, question, depth, hops): calls.append(("graph", depth, hops)); return [chunks["graph"]]
    async def route(question): calls.append(("route", question)); return {"path": "both", "source": "fixture"}
    async def rerank(question, values, seeds): calls.append(("rerank", seeds)); return values[:seeds], {"status": "ready"}
    async def topic(db, owner, values): calls.append(("topic",)); return values + [chunks["topic"]], {"status": "complete"}
    async def parent(db, owner, values, target): calls.append(("parent", target)); return values + [chunks["parent"]], {"status": "ready"}
    def fit(question, values, marks, cap):
        calls.append(("fit", question, marks, cap, tuple(c.chunk_id for c in values)))
        return {"sources": values, "context_text": "\n".join(c.content for c in values), "messages": []}
    functions = dict(readonly=readonly, dense=dense, hybrid=hybrid, structure=structure,
                     graph_status=status, graph=graph, route=route, rerank=rerank, topic=topic, parent=parent, fit=fit)
    return functions, calls


@pytest.mark.asyncio
async def test_seven_configurations_have_isolated_component_ablations(wiring):
    functions, calls = wiring
    rows, stages = {}, {}
    assert len(retrieval.VARIANTS) == 7
    for system in retrieval.VARIANTS:
        calls.clear()
        rows[system] = await retrieval.compare(None, "owner", "Public query?", 10, system, functions=functions)
        stages[system] = [call[0] for call in calls]
        assert rows[system]["status"] == "measured_retrieval_only"
        assert rows[system]["production_equivalent"] is False
        assert ("rerank", 8) in calls
        assert calls[0] == ("readonly",)
    full = stages["documind_full"]
    assert stages["documind_no_topic"] == [stage for stage in full if stage != "topic"]
    assert stages["documind_no_graph"] == [stage for stage in full if stage not in ("graph_status", "graph")]
    assert "parent" in stages["parent"] and "topic" not in stages["parent"]
    assert "dense" in stages["dense"] and "hybrid" not in stages["dense"]
    assert "graph" in stages["graph"] and "structure" not in stages["graph"]


@pytest.mark.asyncio
@pytest.mark.parametrize("marks,cap", [(5, 8192), (10, 12288), (15, 16384)])
async def test_common_fit_uses_requested_marks_not_fifteen_for_all(wiring, marks, cap):
    functions, calls = wiring
    row = await retrieval.compare(None, "owner", "Public query?", marks, "dense", functions=functions)
    assert calls[-1][0:4] == ("fit", "Public query?", marks, cap)
    assert row["token_count_status"] == "not_measured"


@pytest.mark.asyncio
async def test_partial_graph_or_unavailable_reranker_blocks_controlled_comparison(wiring):
    functions, calls = wiring
    async def partial(*args): return "partial"
    row = await retrieval.compare(None, "owner", "Q", 5, "graph", functions={**functions, "graph_status": partial})
    assert row["status"] == "blocked" and row["reason"] == "complete_graph_snapshot_required"
    assert not any(call[0] == "graph" for call in calls)
    async def unavailable(*args): return [], {"status": "unavailable"}
    row = await retrieval.compare(None, "owner", "Q", 5, "dense", functions={**functions, "rerank": unavailable})
    assert row["status"] == "blocked" and row["reason"] == "common_reranker_not_ready"


@pytest.mark.asyncio
async def test_nonreadonly_session_is_rejected_before_any_search(wiring):
    functions, calls = wiring
    async def refuse(db): raise retrieval.BenchmarkUnavailable("caller_session_must_be_read_only")
    row = await retrieval.compare(None, "owner", "Q", 5, "dense", functions={**functions, "readonly": refuse})
    assert row["status"] == "blocked" and row["reason"] == "caller_session_must_be_read_only"
    assert calls == []


@pytest.mark.asyncio
async def test_exact_context_bound_removes_whole_excerpts_and_refits(wiring):
    functions, calls = wiring
    def count(text): return 100 if "topic evidence." not in text else 20000
    row = await retrieval.compare(None, "owner", "Q", 5, "documind_full", functions=functions,
                                  token_counter=count, tokenizer_identity="fixture-counter-only")
    assert row["status"] == "measured_retrieval_only"
    assert row["context_tokens"] == 100
    assert "topic evidence." not in row["context_text"]
    assert len([call for call in calls if call[0] == "fit"]) == 2
    assert "gold" not in retrieval.compare.__annotations__


@pytest.mark.asyncio
async def test_large_question_overhead_does_not_fit_just_because_evidence_is_short(wiring):
    functions, _ = wiring
    def counter(text):
        parsed = json.loads(text) if text.startswith("[") else None
        return 9000 if isinstance(parsed, list) else 10
    row = await retrieval.compare(None, "owner", "Question overhead", 5, "dense", functions=functions,
                                  token_counter=counter, tokenizer_identity="fixture-counter-only")
    assert row["status"] == "blocked" and row["reason"] == "no_source_fits_exact_context_budget"


@pytest.mark.asyncio
async def test_nonprogressing_fitter_is_blocked_instead_of_retried_forever(wiring):
    functions, _ = wiring
    fixed = [Chunk("a", "A"), Chunk("b", "B")]
    def sticky_fit(*args):
        return {"sources": fixed, "context_text": "A\nB", "messages": []}
    row = await retrieval.compare(None, "owner", "Q", 5, "dense", functions={**functions, "fit": sticky_fit},
                                  token_counter=lambda _: 20000, tokenizer_identity="fixture-counter-only")
    assert row["status"] == "blocked" and row["reason"] == "prompt_fitter_did_not_reduce_sources"


def test_real_source_pilot_has_twenty_valid_unreviewed_drafts():
    path = Path(__file__).resolve().parents[3] / "evaluation" / "pilot_v1" / "dataset.json"
    dataset = json.loads(path.read_text(encoding="utf-8"))
    documents, questions = scoring.validate_dataset(dataset)
    assert documents and len(questions) == 20
    assert Counter(q["category"] for q in questions.values()) == {
        "localized_single_topic": 4, "distributed_single_topic": 4,
        "multi_topic_synthesis": 4, "relational_multihop": 4, "unanswerable": 4}
    assert Counter(q["designated_marks"] for q in questions.values()) == {5: 7, 10: 7, 15: 6}
    assert not any(scoring._reviewed(q) for q in questions.values())
    assert all(len(q["independent_annotation_reviews"]) == 2 for q in questions.values())


@pytest.mark.parametrize("released,reviewer_ids,expected", [
    (False, ["reviewer A", "reviewer B"], "draft_annotation_diagnostic_not_confirmatory"),
    (True, [], "draft_annotation_diagnostic_not_confirmatory"),
    (True, ["reviewer A", "reviewer B"], "reviewed_annotation_measurement"),
    (True, ["reviewer A", " REVIEWER a "], "draft_annotation_diagnostic_not_confirmatory"),
])
def test_approved_slots_do_not_promote_an_unreleased_dataset(annotated, released, reviewer_ids, expected):
    dataset, run, _ = annotated
    if released:
        dataset["status"] = "reviewed_frozen_benchmark"
    dataset["questions"][0]["independent_annotation_reviews"] = [
        {"reviewer_id": name, "approved": True, "independent": True} for name in reviewer_ids]
    assert scoring.score_run(dataset, run)["status"] == expected


@pytest.mark.asyncio
async def test_one_immutable_router_snapshot_is_shared_across_documind_ablations(wiring):
    functions, _ = wiring
    queries = []
    async def changing_router(question):
        queries.append(question)
        return {"path": "both" if len(queries) == 1 else "semantic", "source": "test-router",
                "details": {"notes": ["original"]}}
    frozen = retrieval.freeze_router(changing_router)
    initial = await frozen("same question")
    expected_hash = initial["routing_snapshot_sha256"]
    initial["path"] = "semantic"
    initial["details"]["notes"].append("changed by caller")
    rows = []
    for system in ("documind_full", "documind_no_topic", "documind_no_graph"):
        rows.append(await retrieval.compare(None, "owner", "same question", 10, system,
                                           functions={**functions, "route": frozen}))
    assert queries == ["same question"]
    assert {row["routing_snapshot_sha256"] for row in rows} == {expected_hash}
    for row in rows:
        route = next(stage for stage in row["trace"] if stage["stage"] == "route")
        assert route["path"] == "both" and route["details"]["notes"] == ["original"]
        assert route["routing_control"] == "immutable_per_run_question_snapshot"
    assert (await frozen("different question"))["path"] == "semantic"
    assert queries == ["same question", "different question"]
