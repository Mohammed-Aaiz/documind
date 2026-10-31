"""Research-only evidence metrics and blinded human review; never a model judge.

Input runs contain final, prompt-fitted evidence excerpts with canonical source
offsets and the full serialized evidence context. No app imports, DB or network.
Draft annotations remain diagnostic; exact context tokens are never estimated.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import random
import statistics
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _unique(rows: list[dict], key: str = "id") -> dict:
    if not isinstance(rows, list):
        raise ValueError("Expected a list of records")
    result = {}
    for row in rows:
        name = row.get(key)
        if not isinstance(name, str) or not name.strip() or name in result:
            raise ValueError("Record IDs must be nonempty and unique")
        result[name] = row
    return result


def _page(doc: dict, number: int) -> dict:
    if type(number) is not int or number < 1:
        raise ValueError("Page numbers must be positive integers")
    matches = [page for page in doc["pages"] if page["page"] == number]
    if len(matches) != 1:
        raise ValueError("Unknown or repeated canonical page")
    return matches[0]


def _span(span: dict, documents: dict, *, text_key: str = "quote") -> tuple[str, int, int, int, str]:
    document_id = span.get("document_id")
    if document_id not in documents:
        raise ValueError("Span refers to an unknown document")
    doc = documents[document_id]
    page = _page(doc, span.get("page"))
    text = page["canonical_text"]
    quote = span.get(text_key)
    if not isinstance(quote, str) or not quote:
        raise ValueError("Evidence span requires nonempty exact source text")
    if "start_char" not in span and "end_char" not in span:
        # No whitespace/paraphrase alignment: one exact occurrence on this page.
        start = text.find(quote)
        if start < 0 or text.find(quote, start + 1) >= 0:
            raise ValueError("Text-only evidence mapping is absent or ambiguous; supply canonical offsets")
        end = start + len(quote)
    else:
        start, end = span.get("start_char"), span.get("end_char")
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
        raise ValueError("Invalid half-open canonical character offsets")
    if text[start:end] != quote:
        raise ValueError("Evidence text does not match its canonical offsets")
    if span.get("quote_sha256", _sha(quote)) != _sha(quote):
        raise ValueError("Evidence quote hash mismatch")
    if span.get("source_sha256", doc["raw_file_sha256"]) != doc["raw_file_sha256"]:
        raise ValueError("Evidence belongs to another document revision")
    return document_id, page["page"], start, end, quote


def rubric_for(question: dict) -> dict:
    marks = question["designated_marks"]
    return question["rubrics"][str(marks)]


def validate_dataset(data: dict) -> tuple[dict, dict]:
    """Validate structure/provenance, not subject correctness or reviewer expertise."""
    documents, questions = _unique(data["documents"]), _unique(data["questions"])
    if not documents or not questions:
        raise ValueError("Dataset requires source documents and questions")
    for doc in documents.values():
        raw_hash = doc.get("raw_file_sha256", "")
        if not isinstance(raw_hash, str) or len(raw_hash) != 64 or any(c not in "0123456789abcdef" for c in raw_hash):
            raise ValueError("Source requires raw-file SHA256")
        numbers = [page["page"] for page in doc["pages"]]
        if not numbers or len(numbers) != len(set(numbers)):
            raise ValueError("Canonical pages must be nonempty and unique")
        for number in numbers:
            page = _page(doc, number)
            if not isinstance(page["canonical_text"], str) or _sha(page["canonical_text"]) != page["canonical_text_sha256"]:
                raise ValueError("Canonical source hash mismatch")
    for question in questions.values():
        marks = question.get("designated_marks")
        if type(marks) is not int or marks not in (5, 10, 15):
            raise ValueError("Designated marks must be 5, 10 or 15")
        if not isinstance(question.get("question"), str) or not question["question"].strip():
            raise ValueError("Question text is missing")
        answerability = question.get("answerability")
        if answerability not in ("answerable", "unanswerable"):
            raise ValueError("Unsupported answerability label")
        units = _unique(question["required_evidence_units"])
        if bool(units) != (answerability == "answerable"):
            raise ValueError("Required evidence and answerability disagree")
        for unit in units.values():
            if not unit.get("alternatives"):
                raise ValueError("An evidence unit needs at least one sufficient alternative")
            for alternative in unit["alternatives"]:
                if not alternative.get("all_of"):
                    raise ValueError("An alternative requires at least one span")
                for span in alternative["all_of"]:
                    if "start_char" not in span or "end_char" not in span:
                        raise ValueError("Annotated evidence requires explicit canonical offsets")
                    doc_id, _, _, _, _ = _span(span, documents)
                    doc = documents[doc_id]
                    if doc.get("bundle_id") != question.get("bundle_id") or doc.get("split") != question.get("split"):
                        raise ValueError("Evidence crosses its question's bundle or split")
                    if span.get("topic_id") not in doc.get("topic_ids", []):
                        raise ValueError("Evidence references an unknown source topic")
        if str(marks) not in question.get("rubrics", {}):
            raise ValueError("Missing designated-mark rubric")
        for mark, rubric in question["rubrics"].items():
            maxima = [criterion["max_marks"] for criterion in rubric["criteria"]]
            if mark not in ("5", "10", "15") or not maxima or any(
                    type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in maxima):
                raise ValueError("Rubric criteria require finite nonnegative maxima")
            if sum(maxima) != int(mark) or rubric.get("max_marks", int(mark)) != int(mark):
                raise ValueError("Rubric maxima must total the available marks")
    return documents, questions


def _merge(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def _mapped_context(record: dict, documents: dict) -> tuple[dict, list]:
    context = record.get("context_text")
    if not isinstance(context, str):
        raise ValueError("Run must preserve full serialized final evidence context_text")
    if not isinstance(record.get("excerpts"), list):
        raise ValueError("Run requires final fitted excerpts, even if empty")
    format_name = record.get("context_format", "plain")
    if format_name not in ("plain", "jsonl_evidence"):
        raise ValueError("Unsupported evidence serialization format")
    context_rows = []
    if format_name == "jsonl_evidence":
        for line in context.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or not isinstance(row.get("text"), str):
                raise ValueError("JSONL evidence needs a text field in each object")
            context_rows.append(row)
    intervals, spans = defaultdict(list), []
    for excerpt in record["excerpts"]:
        doc, page, start, end, text = _span(excerpt, documents, text_key="text")
        if format_name == "jsonl_evidence":
            candidates = [row for row in context_rows if (
                row.get("source") == excerpt["context_source"] if "context_source" in excerpt else text in row["text"])]
            if len(candidates) != 1 or text not in candidates[0]["text"] or candidates[0].get("page", page) != page:
                raise ValueError("Mapped excerpt is absent or ambiguous in JSONL evidence text; metadata is not evidence")
        elif text not in context:
            raise ValueError("Mapped source excerpt is absent from the serialized final context")
        intervals[(doc, page)].append((start, end))
        spans.append((doc, page, text))
    return {key: _merge(value) for key, value in intervals.items()}, spans


def evidence_metrics(question: dict, intervals: dict, context_tokens: int | None = None) -> dict:
    """Units are OR alternatives of ALL-required spans; overlap never adds credit."""
    covered = []
    for unit in question["required_evidence_units"]:
        if any(all(any(lo <= span["start_char"] and hi >= span["end_char"]
                       for lo, hi in intervals.get((span["document_id"], span["page"]), []))
                   for span in alternative["all_of"]) for alternative in unit["alternatives"]):
            covered.append(unit["id"])
    total = len(question["required_evidence_units"])
    return {"required_units": total, "covered_units": len(covered), "covered_unit_ids": covered,
            "rer": len(covered) / total if total else None,
            "context_tokens": context_tokens,
            "ect1000": 1000 * len(covered) / context_tokens if total and context_tokens else None}


def _reviewed(question: dict) -> bool:
    reviews = question.get("independent_annotation_reviews", [])
    ids = {review["reviewer_id"].strip().casefold() for review in reviews
           if review.get("approved") is True and review.get("independent") is True
           and isinstance(review.get("reviewer_id"), str) and review["reviewer_id"].strip()}
    return len(ids) >= 2


def score_run(dataset: dict, run: dict, token_counter: Callable[[str], int] | None = None,
              tokenizer_identity: dict | None = None) -> dict:
    documents, questions = validate_dataset(dataset)
    records = run.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("Run requires nonempty records")
    seen, rows = set(), []
    exact = bool(token_counter and tokenizer_identity and tokenizer_identity.get("exact") is True
                 and tokenizer_identity.get("generation_compatible") is True
                 and tokenizer_identity.get("compatibility_verified") is True)
    for record in records:
        qid, system = record.get("question_id"), record.get("system_id")
        key = (qid, system, record.get("replicate", 0))
        if qid not in questions or not isinstance(system, str) or not system.strip() or key in seen:
            raise ValueError("Unknown question, missing system or duplicate run record")
        seen.add(key)
        question = questions[qid]
        intervals, _ = _mapped_context(record, documents)
        tokens = token_counter(record["context_text"]) if exact else None
        if tokens is not None and (type(tokens) is not int or tokens < 0 or record["context_text"] and not tokens):
            raise ValueError("Exact tokenizer returned an invalid context count")
        row = {"question_id": qid, "system_id": system, "replicate": record.get("replicate", 0),
               "designated_marks": question["designated_marks"], "category": question.get("category"),
               "answerability": question["answerability"], "annotations_reviewed": _reviewed(question),
               **evidence_metrics(question, intervals, tokens)}
        row["ect_status"] = "measured" if row["ect1000"] is not None else "not_measured"
        rows.append(row)
    summaries = []
    for system in sorted({row["system_id"] for row in rows}):
        values = [row for row in rows if row["system_id"] == system]
        answerable = [row for row in values if row["rer"] is not None]
        ect = [row for row in answerable if row["ect1000"] is not None]
        summaries.append({"system_id": system, "records": len(values), "answerable_records": len(answerable),
            "rer_macro": statistics.mean(row["rer"] for row in answerable) if answerable else None,
            "complete_fraction": statistics.mean(row["rer"] == 1 for row in answerable) if answerable else None,
            "ect1000_macro": statistics.mean(row["ect1000"] for row in ect) if ect else None,
            "ect_measured_records": len(ect), "ect_missing_records": len(answerable) - len(ect)})
    return {"schema_version": "documind-evidence-score-v1", "dataset_status": dataset.get("status", "unverified"),
            "dataset_sha256": _sha(json.dumps(dataset, sort_keys=True, ensure_ascii=False, separators=(",", ":"))),
            "run_sha256": _sha(json.dumps(run, sort_keys=True, ensure_ascii=False, separators=(",", ":"))),
            "input_hash_method": "canonical_json_utf8", "scorer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "status": "reviewed_annotation_measurement" if dataset.get("status") == "reviewed_frozen_benchmark"
                      and all(row["annotations_reviewed"] for row in rows)
                      else "draft_annotation_diagnostic_not_confirmatory",
            "tokenizer": tokenizer_identity or {"status": "unavailable"}, "rows": rows, "summary": summaries,
            "limitations": ["Evidence coverage is exact source-interval coverage, not semantic entailment.",
                            "Draft labels are not independent gold; reviewer qualifications are not validated by software.",
                            "ECT is not measured without a verified exact generation-compatible counter.",
                            "Replicates are reported records, not independent questions for inferential statistics."]}


def load_local_tokenizer(path: Path, identity: str) -> tuple[Callable, dict]:
    """Count using the hash-verified official pinned research model tokenizer.

    Exact for this frozen tokenizer, not proof that a hosted alias never changes.
    Provisioning is a separate explicit command; loading cannot download files.
    """
    if not path.is_dir() or "@" not in identity or "minilm" in identity.lower():
        raise ValueError("Supply a local generation tokenizer and model@immutable-revision identity")
    model, revision = identity.rsplit("@", 1)
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise ValueError("Tokenizer identity needs a pinned 40-character repository revision")
    files = {name: hashlib.sha256((path / name).read_bytes()).hexdigest()
             for name in ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json") if (path / name).is_file()}
    if "tokenizer_config.json" not in files or "tokenizer.json" not in files:
        raise ValueError("Local tokenizer assets are incomplete")
    manifest_path = path / "documind_tokenizer_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (model != "openai/gpt-oss-20b" or manifest.get("repository") != model
            or manifest.get("revision") != revision or manifest.get("license") != "apache-2.0"):
        raise ValueError("Tokenizer identity does not match the pinned generation-model manifest")
    for name, digest in manifest["files_sha256"].items():
        if Path(name).name != name or hashlib.sha256((path / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Pinned tokenizer file hash mismatch")
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True, trust_remote_code=False)
    return (lambda text: len(tokenizer.encode(text, add_special_tokens=False, truncation=False))), {
        "status": "verified_official_pinned_model_tokenizer", "model": model, "revision": revision,
        "files_sha256": manifest["files_sha256"], "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "exact": True, "generation_compatible": True, "compatibility_verified": True,
        "hosted_alias_equivalence": "not_independently_verified",
        "note": "ECT uses the frozen official GPT-OSS tokenizer; hosted Groq alias/tokenizer drift remains an external reproducibility limitation."}


def _csv_safe(value: object) -> str:
    text = str(value)
    return "'" + text if text.lstrip("\ufeff \t\r\n").startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")) else text


def _csv_payload(rows: list[dict]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows({key: _csv_safe(value) for key, value in row.items()} for row in rows)
    return buffer.getvalue()


def _display_hash(value: str) -> str:
    # Spreadsheet software can rewrite display line endings without changing
    # what was graded. Source-interval scoring itself remains strictly exact.
    return _sha(value.replace("\r\n", "\n").replace("\r", "\n"))


def review_pack(dataset: dict, run: dict) -> tuple[str, dict]:
    """Public sheet never contains system/question IDs or reliability metrics."""
    documents, questions = validate_dataset(dataset)
    score_run(dataset, run)  # validate all source mappings and duplicate records first
    public, private = [], []
    for record in run["records"]:
        if "answer" not in record or not isinstance(record["answer"], str):
            continue  # retrieval-only or failed-provider records have no answer to grade
        question = questions[record["question_id"]]
        _, spans = _mapped_context(record, documents)
        blind_id = uuid.uuid4().hex
        row = {"answer_id": blind_id, "question": question["question"], "marks": question["designated_marks"],
               "answer": record["answer"], "rubric": json.dumps(rubric_for(question), ensure_ascii=False),
               "evidence": "\n\n".join(f"[{i}] {doc}, page {page}\n{text}" for i, (doc, page, text) in enumerate(spans, 1)),
               "reviewer": "", "score": "", "accuracy_notes": "", "rubric_notes": ""}
        public.append(row)
        private.append({"answer_id": blind_id, "question_id": record["question_id"], "system_id": record["system_id"],
                        "replicate": record.get("replicate", 0), "marks": question["designated_marks"],
                        "answerability": question["answerability"], "answer_sha256": _sha(record["answer"]),
                        "review_fields_sha256": {name: _display_hash(_csv_safe(row[name]))
                                                 for name in ("question", "marks", "answer", "rubric", "evidence")}})
    if not public:
        raise ValueError("No generated answers available to export; no review pack was fabricated")
    random.SystemRandom().shuffle(public)
    payload = _csv_payload(public)
    return payload, {"schema_version": "documind-private-review-map-v1", "private_keep_from_reviewers": True,
                     "review_sheet_sha256": _sha(payload), "answers": private,
                     "expected_independent_reviewers": 2,
                     "limitations": "Metadata is blinded; answer prose and evidence can still reveal method characteristics."}


def summarize_reviews(ratings_paths: list[Path], mapping: dict) -> dict:
    answers = _unique(mapping["answers"], "answer_id")
    scores, seen, pending_rows = defaultdict(list), set(), 0
    for path in ratings_paths:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                blind = row.get("answer_id")
                if blind not in answers or str(answers[blind]["marks"]) != row.get("marks"):
                    raise ValueError("Review contains an unknown answer ID or altered maximum marks")
                if any(_display_hash(row.get(name, "")) != digest for name, digest in answers[blind]["review_fields_sha256"].items()):
                    raise ValueError("Review answer, question, rubric or evidence was altered")
                reviewer = row.get("reviewer", "").strip()
                if not row.get("score", "").strip():
                    pending_rows += 1
                    continue
                if not reviewer or (blind, reviewer.casefold()) in seen:
                    raise ValueError("A scored row requires a distinct reviewer; duplicate ratings are forbidden")
                value = float(row["score"])
                if not math.isfinite(value) or not 0 <= value <= answers[blind]["marks"]:
                    raise ValueError("Human score must be finite and within the available marks")
                seen.add((blind, reviewer.casefold()))
                scores[blind].append((reviewer, value))
    rows = []
    for blind, info in answers.items():
        values = scores[blind]
        # The protocol specifies two fixed independent graders. Extra grades
        # need an explicit adjudication workflow, not an unlabelled third mean.
        if len(values) > 2:
            raise ValueError("More than two ratings require a separately labelled adjudication workflow")
        rows.append({**info, "reviewer_count": len(values), "ratings": values,
                     "nhrs": statistics.mean(value / info["marks"] for _, value in values) if len(values) == 2 else None})
    groups = defaultdict(list)
    negative = defaultdict(list)
    for row in rows:
        if row["nhrs"] is not None:
            target = groups if row["answerability"] == "answerable" else negative
            target[(row["system_id"], row["marks"])].append(row["nhrs"])
    def aggregates(values):
        return [{"system_id": system, "marks": marks, "questions": len(scores), "nhrs_mean": statistics.mean(scores)}
                for (system, marks), scores in sorted(values.items())]
    return {"schema_version": "documind-human-review-summary-v1", "status": "measured" if groups or negative else "not_measured",
            "ratings_sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in ratings_paths},
            "mapping_canonical_json_sha256": _sha(json.dumps(mapping, sort_keys=True, separators=(",", ":"))),
            "pending_rows": pending_rows, "answers_missing_two_reviews": sum(row["nhrs"] is None for row in rows),
            "rows": rows, "answerable_nhrs": aggregates(groups), "unanswerable_safe_abstention_scores": aggregates(negative),
            "limitations": ["Only answers with two distinct human-entered ratings contribute to NHRS.",
                            "Reviewer expertise and independence require external verification; no grades are inferred.",
                            "Agreement statistics and confidence intervals are not computed by this preparation tool."]}


def write_new(path: Path, value: str | dict) -> None:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    with path.open("x", encoding="utf-8", newline="") as stream:
        stream.write(text)


def self_check() -> None:
    import tempfile
    source = 'Ada links A to B.\nB links to C. 中文 "quoted" \\path'
    doc = {"id": "d", "raw_file_sha256": _sha(source), "pages": [{"page": 1, "canonical_text": source,
           "canonical_text_sha256": _sha(source)}], "bundle_id": "b", "split": "development", "topic_ids": ["t"]}
    span = {"document_id": "d", "page": 1, "start_char": 0, "end_char": 16, "quote": source[:16], "topic_id": "t"}
    question = {"id": "q", "question": "How does Ada link A to B?", "answerability": "answerable", "designated_marks": 5,
        "bundle_id": "b", "split": "development", "required_evidence_units": [{"id": "u", "alternatives": [{"all_of": [span]}]}],
        "rubrics": {"5": {"max_marks": 5, "criteria": [{"max_marks": 5}]}}, "independent_annotation_reviews": []}
    data = {"status": "synthetic_self_check_not_benchmark", "documents": [doc], "questions": [question]}
    excerpts = [{"document_id": "d", "page": 1, "start_char": lo, "end_char": hi, "text": source[lo:hi]} for lo, hi in ((0, 8), (8, 16))]
    record = {"question_id": "q", "system_id": "secret-system", "context_text": "\n".join(e["text"] for e in excerpts),
              "excerpts": excerpts, "answer": "Ada links A to B [1]."}
    run = {"records": [record]}
    result = score_run(data, run)
    assert result["rows"][0]["rer"] == 1 and result["rows"][0]["ect1000"] is None
    approved = {**question, "independent_annotation_reviews": [
        {"reviewer_id": name, "approved": True, "independent": True} for name in ("Alice", "Bob")]}
    approved_data = {**data, "questions": [approved]}
    assert score_run(approved_data, run)["status"] == "draft_annotation_diagnostic_not_confirmatory"
    assert score_run({**approved_data, "status": "reviewed_frozen_benchmark"}, run)["status"] == "reviewed_annotation_measurement"
    jsonl = {**record, "context_format": "jsonl_evidence",
             "context_text": json.dumps({"source": 1, "page": 1, "text": source}, ensure_ascii=False),
             "excerpts": [{"document_id": "d", "page": 1, "start_char": 0, "end_char": len(source),
                           "text": source, "context_source": 1}]}
    assert score_run(data, {"records": [jsonl]})["rows"][0]["rer"] == 1
    try:
        score_run(data, {"records": [{**jsonl, "context_text": json.dumps(
            {"source": 1, "page": 1, "text": "unrelated", "metadata": source})}]})
    except ValueError:
        pass
    else:
        raise AssertionError("Metadata was incorrectly counted as evidence")
    intervals, _ = _mapped_context(record, {"d": doc})
    assert intervals[("d", 1)] == [(0, 16)]
    assert evidence_metrics(question, {("d", 1): [(0, 7), (8, 16)]})["rer"] == 0
    extended = {**question, "required_evidence_units": [{"id": "u", "alternatives": [{"all_of": [span, {**span, "start_char": 17, "end_char": 30}]}]}]}
    assert evidence_metrics(extended, intervals)["rer"] == 0
    extended["required_evidence_units"][0]["alternatives"].append({"all_of": [span]})
    assert evidence_metrics(extended, intervals)["rer"] == 1
    identity = {"exact": True, "generation_compatible": True, "compatibility_verified": True, "status": "toy_self_check_only"}
    measured = score_run(data, run, lambda _: 10, identity)
    assert measured["rows"][0]["ect1000"] == 100
    assert evidence_metrics(question, {}, 0)["ect1000"] is None
    payload, mapping = review_pack(data, run)
    assert "secret-system" not in payload and "system_id" not in payload
    with tempfile.TemporaryDirectory() as directory:
        p = Path(directory) / "review.csv"
        write_new(p, payload)
        assert summarize_reviews([p], mapping)["status"] == "not_measured"
        rows = list(csv.DictReader(io.StringIO(payload)))
        rows[0].update(reviewer="reviewer-A", score="4")
        other = {**rows[0], "reviewer": "reviewer-B", "score": "3"}
        p.write_text(_csv_payload([rows[0], other]), encoding="utf-8")
        assert summarize_reviews([p], mapping)["rows"][0]["nhrs"] == .7
        for invalid in ("nan", "-1", "6"):
            p.write_text(_csv_payload([{**rows[0], "score": invalid}]), encoding="utf-8")
            try:
                summarize_reviews([p], mapping)
            except ValueError:
                pass
            else:
                raise AssertionError("Invalid human grade accepted")
        p.write_text(_csv_payload([{**rows[0], "answer": "Altered answer"}]), encoding="utf-8")
        try:
            summarize_reviews([p], mapping)
        except ValueError:
            pass
        else:
            raise AssertionError("Altered review answer accepted")
    print("research scoring self-check passed (toy assertions, not benchmark results)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--dataset", type=Path, required=True)
    for name in ("score", "review-export"):
        command = sub.add_parser(name)
        command.add_argument("--dataset", type=Path, required=True)
        command.add_argument("--run", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
    sub.choices["score"].add_argument("--tokenizer", type=Path)
    sub.choices["score"].add_argument("--tokenizer-id")
    sub.choices["review-export"].add_argument("--mapping", type=Path, required=True)
    review = sub.add_parser("review-summary")
    review.add_argument("--ratings", type=Path, nargs="+", required=True)
    review.add_argument("--mapping", type=Path, required=True)
    review.add_argument("--output", type=Path, required=True)
    sub.add_parser("self-check")
    args = parser.parse_args()
    if args.command == "self-check":
        self_check()
        return
    if getattr(args, "output", None) and args.output.exists():
        parser.error("Output already exists; choose a new path")
    if args.command == "review-summary":
        result = summarize_reviews(args.ratings, json.loads(args.mapping.read_text(encoding="utf-8")))
        result["mapping_file_sha256"] = hashlib.sha256(args.mapping.read_bytes()).hexdigest()
        write_new(args.output, result)
    else:
        dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
        docs, questions = validate_dataset(dataset)
        if args.command == "validate":
            print(json.dumps({"documents": len(docs), "questions": len(questions), "status": dataset.get("status"),
                              "categories": dict(Counter(q.get("category") for q in questions.values())),
                              "marks": dict(Counter(q["designated_marks"] for q in questions.values())),
                              "independently_reviewed": sum(_reviewed(q) for q in questions.values())}))
            return
        run = json.loads(args.run.read_text(encoding="utf-8"))
        if args.command == "score":
            if bool(args.tokenizer) != bool(args.tokenizer_id):
                parser.error("--tokenizer and --tokenizer-id must be supplied together")
            counter, identity = load_local_tokenizer(args.tokenizer, args.tokenizer_id) if args.tokenizer else (None, None)
            result = score_run(dataset, run, counter, identity)
            result.update(dataset_sha256=hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
                          run_sha256=hashlib.sha256(args.run.read_bytes()).hexdigest(), input_hash_method="input_file_bytes")
            write_new(args.output, result)
        else:
            if args.mapping.resolve() == args.output.resolve() or args.mapping.exists():
                parser.error("Mapping must be a separate new private path")
            payload, mapping = review_pack(dataset, run)
            # Open both new paths before writing either; existing files are never overwritten.
            with args.output.open("x", encoding="utf-8", newline="") as public:
                try:
                    private = args.mapping.open("x", encoding="utf-8")
                except Exception:
                    raise ValueError("Private mapping could not be created; public file is empty") from None
                with private:
                    public.write(payload)
                    json.dump(mapping, private, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({"output": str(args.output), "status": "written; review and annotation status remain explicit"}))


if __name__ == "__main__":
    main()
