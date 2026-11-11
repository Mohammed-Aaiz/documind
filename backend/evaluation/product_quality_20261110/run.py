"""Private course-note quality pilot; source reads and inference, no DB writes.

Draft rubrics are frozen before capture. Two independent AI reviews are a
development diagnostic; qualified human NHRS remains a separate review gate.
The existing research CSV integrity and dataset validators are reused.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import html
import json
import random
import re
import statistics
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from evaluation.research_scoring import (
    _csv_payload, _csv_safe, _display_hash, summarize_reviews, validate_dataset,
)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_new(path: Path, value: str | dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as output:
        output.write(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def human_html(packets: list[dict], reference_material: str) -> str:
    """Self-contained offline review; source/answer text never becomes HTML."""
    cards = []
    for row in packets:
        criteria = json.loads(row["rubric"])["criteria"]
        inputs = "".join(
            f'<label>{html.escape(criterion["requirements"])} '
            f'<input type="number" min="0" max="{criterion["max_marks"]}" step="0.01" '
            f'data-criterion="{html.escape(criterion["id"], quote=True)}" aria-label="Score for {html.escape(criterion["id"], quote=True)}"> '
            f'/ {criterion["max_marks"]}</label>' for criterion in criteria)
        cards.append(f'''<article data-answer="{row['answer_id']}">
<h2>{html.escape(row['question'])} <small>{row['marks']} marks</small></h2>
<pre>{html.escape(row['answer'])}</pre>
<details><summary>Retrieved source passages</summary><pre>{html.escape(row['evidence'])}</pre></details>
<fieldset><legend>Apply the marking rubric</legend>{inputs}</fieldset>
<label>Accuracy notes<textarea data-notes="accuracy_notes"></textarea></label>
<label>Missing coverage, diagram and rubric notes<textarea data-notes="rubric_notes"></textarea></label>
</article>''')
    # The JSON literal is data, with script delimiters escaped even if a source
    # or model response contains adversarial markup. No external assets/network.
    serialized = json.dumps(packets, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DocuMind independent answer review</title><style>
body{font:16px/1.6 system-ui,sans-serif;background:#f6f5ef;color:#172f28;max-width:980px;margin:auto;padding:28px}
h1,h2{line-height:1.3}article,header,details{background:white;border:1px solid #d8dfd1;border-radius:12px;padding:22px;margin:20px 0}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.6 ui-monospace,monospace;background:#f5f6f0;padding:16px;border-radius:8px}
label{display:block;margin:14px 0}input,textarea,button{font:inherit;border:1px solid #b4c4b7;border-radius:6px;padding:9px}
input[type=number]{width:85px}textarea{display:block;width:95%;min-height:65px}button{background:#173f34;color:white;cursor:pointer;margin:8px 12px 8px 0}
fieldset{border:1px solid #d8dfd1}small{display:block;color:#547265}#status{font-weight:600}
</style><header><h1>Independent answer review</h1>
<p>Work independently from the original notes and this rubric. Do not consult another review or infer a grade from answer length or citation count. These draft rubrics need subject review. Leave uncertain scores blank and explain why.</p>
<label>Your reviewer ID <input id="reviewer" autocomplete="off"></label>
<label>Private qualification/reference <input id="qualification" autocomplete="off"></label>
<label><input id="independent" type="checkbox"> I am a human reviewer with suitable subject knowledge, and I have graded independently.</label>
<button id="csv">Download ratings CSV</button><button id="json">Download ratings and attestation JSON</button>
<p id="status" aria-live="polite">Scores begin blank. Downloads preserve incomplete rows as pending.</p>
<p>This file works offline. Download your work before closing it; scores are not sent or stored automatically.</p></header>
<details><summary>Original reference notes (PDF pages 10–13)</summary><pre>''' + html.escape(reference_material) + '</pre></details>' + "".join(cards) + '''<script>
const packet = ''' + serialized + r''';
function collect(){
 const reviewer=document.querySelector('#reviewer').value.trim();
 return packet.map(original=>{
  const card=document.querySelector('[data-answer="'+original.answer_id+'"]');
  const fields=[...card.querySelectorAll('[data-criterion]')];
  const complete=fields.every(field=>field.value!==''&&field.checkValidity());
  const criteria=Object.fromEntries(fields.map(field=>[field.dataset.criterion,field.value===''?null:Number(field.value)]));
  return {...original,reviewer,score:complete?fields.reduce((total,field)=>total+Number(field.value),0):'',
   accuracy_notes:card.querySelector('[data-notes="accuracy_notes"]').value,
   rubric_notes:card.querySelector('[data-notes="rubric_notes"]').value,criterion_scores:criteria};
 });
}
function download(name,type,text){const link=document.createElement('a');const url=URL.createObjectURL(new Blob([text],{type}));link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function csvsafe(value){const text=String(value);return /^[\ufeff \t\r\n]*[=+@-]/.test(text)||/^[\t\r\n]/.test(text)?"'"+text:text;}
function quote(value){return '"'+csvsafe(value).replaceAll('"','""')+'"';}
function attestation(){return {reviewer_id:document.querySelector('#reviewer').value.trim(),reviewer_kind:'human',qualification_reference_private:document.querySelector('#qualification').value.trim(),independent_self_attestation:document.querySelector('#independent').checked};}
document.querySelector('#csv').onclick=()=>{
 const rows=collect();const keys=Object.keys(packet[0]);
 download('documind-human-ratings.csv','text/csv;charset=utf-8',[keys.map(quote).join(','),...rows.map(row=>keys.map(key=>quote(row[key])).join(','))].join('\r\n'));
 document.querySelector('#status').textContent=rows.filter(row=>row.score!=='').length+' of '+rows.length+' answers scored. Qualification and independence still require verification.';
};
document.querySelector('#json').onclick=()=>download('documind-human-ratings.json','application/json',JSON.stringify({attestation:attestation(),rows:collect()},null,2));
</script></html>'''


def prepare(pdf: Path, output: Path, annotation_spec: Path) -> None:
    """Verify a source against separately supplied, private annotations.

    The public tool contains no course-note quotations or reference answers.
    Annotators supply a versioned JSON dataset specification with pinned source
    and page hashes; canonical text is recovered only from their original PDF.
    """
    import pymupdf

    data = load(annotation_spec)
    if len(data.get("documents", [])) != 1:
        raise ValueError("This development pilot requires one annotated source")
    document = data["documents"][0]
    if digest(pdf.read_bytes()) != document.get("raw_file_sha256"):
        raise ValueError("Source PDF differs from the annotation specification")
    with pymupdf.open(pdf) as source:
        pages = [{"page": i + 1, "canonical_text": re.sub(r"\s+", " ", page.get_text(sort=True)).strip()}
                 for i, page in enumerate(source)]
    for page in pages:
        page["canonical_text_sha256"] = digest(page["canonical_text"].encode())
    expected = {page["page"]: page["canonical_text_sha256"] for page in document["pages"]}
    if expected != {page["page"]: page["canonical_text_sha256"] for page in pages}:
        raise ValueError("Canonical PDF extraction differs from the annotation specification")
    document["pages"] = pages
    data["source_location_private"] = str(pdf.resolve())
    validate_dataset(data)
    write_new(output, data)
    print(json.dumps({"prepared_questions": len(data["questions"]), "dataset_sha256": digest(output.read_bytes())}))


async def capture(args) -> None:
    """Invoke the real product retrieval/generation without storing chat turns."""
    import main  # register the same ORM models as product startup
    from sqlalchemy import text
    from config import get_settings
    from generation.service import run_generation
    from generation.planning import text_diagram_blocks, validate_text_diagram
    from generation.types import GenerationUnavailableError
    from generation.verification import verify_with_mode
    from storage.database import async_session

    data = load(args.dataset)
    validate_dataset(data)
    settings = get_settings()
    source_hash = data["documents"][0]["raw_file_sha256"]
    chosen = [q for q in data["questions"] if not args.question or q["id"] in args.question]
    if not chosen or args.question and len(chosen) != len(set(args.question)):
        raise ValueError("Unknown or duplicate question selection")
    rows = []
    manifest = {"schema_version": "documind-private-product-quality-run-v1", "status": "in_progress",
                "product_path": "generation.service.run_generation (stateless, no SQL conversation persistence)",
                "dataset_sha256": digest(args.dataset.read_bytes()), "code_commit": args.code_commit,
                "started_at": datetime.now(timezone.utc).isoformat(), "provider": "groq", "model": settings.groq_model,
                "groq_context_tokens": settings.groq_context_tokens, "pause_seconds": args.pause,
                "production_sources_sha256": {path: digest(Path(path).read_bytes()) for path in (
                    "generation/planning.py", "generation/provider_prompt.py", "generation/providers.py",
                    "generation/service.py", "generation/topic_context.py", "generation/diagrams.py",
                    "generation/types.py", "orchestration/service.py")},
                "records": rows, "human_grading": "not_measured", "rer": "not_measured", "ect1000": "not_measured"}
    if args.output.exists():
        raise FileExistsError(args.output)
    for index, question in enumerate(chosen):
        started = time.perf_counter()
        async with async_session() as db:
            await db.execute(text("SET TRANSACTION READ ONLY"))
            matches = (await db.execute(text("SELECT id,user_id,name FROM documents WHERE content_hash=:hash AND status='ready'"),
                                        {"hash": source_hash})).mappings().all()
            if len(matches) != 1:
                raise ValueError("Expected one ready indexed document matching the pinned private source hash")
            row = {"question_id": question["id"], "marks": question["designated_marks"], "status": "failed"}
            try:
                sources, result = await run_generation(db, str(matches[0]["user_id"]), question["question"], 5,
                                                        str(question["designated_marks"]))
                diagrams = text_diagram_blocks(result.answer) or []
                row.update(status="completed", answer=result.answer, abstained=result.abstained,
                           latency_ms=result.latency_ms, model=result.model, warnings=result.warnings,
                           verification=result.verification, sources=[asdict(source) for source in sources],
                           diagram_count=len(diagrams),
                           rechecked_diagram_support=(validate_text_diagram(
                               result.answer, result.blocks, question=question["question"]
                           ) if diagrams else None),
                           rechecked_verification=verify_with_mode(
                               result.answer, result.blocks, question=question["question"]
                           ).summary())
            except GenerationUnavailableError as error:
                row.update(error=str(error), status_code=getattr(error, "status_code", None))
            await db.rollback()
        row["total_ms"] = round((time.perf_counter() - started) * 1000)
        rows.append(row)
        # New output identity; incremental checkpoints retain failures, never
        # overwrite a previous release. No raw provider request/key is recorded.
        checkpoint = args.output.with_suffix(args.output.suffix + f".checkpoint-{index + 1}")
        write_new(checkpoint, manifest)
        print(json.dumps({"question_id": row["question_id"], "status": row["status"],
                          "abstained": row.get("abstained"), "latency_ms": row["total_ms"]}), flush=True)
        if index + 1 < len(chosen):
            await asyncio.sleep(args.pause)
    manifest["status"] = "completed" if all(row["status"] == "completed" for row in rows) else "partial_provider_failures"
    write_new(args.output, manifest)


def export(data_path: Path, run_path: Path, output: Path) -> None:
    data, run = load(data_path), load(run_path)
    validate_dataset(data)
    if run["dataset_sha256"] != digest(data_path.read_bytes()):
        raise ValueError("Run/dataset identity mismatch")
    questions = {q["id"]: q for q in data["questions"]}
    packets, mapping = [], []
    for record in run["records"]:
        if record["status"] != "completed":
            continue
        q = questions[record["question_id"]]
        answer = record["answer"] or "[No answer text was returned.]"
        source_text = "\n\n".join(f"[{i}] {source['document_name']}, page {source['page']}\n{source['content']}"
                                   for i, source in enumerate(record["sources"], 1))
        blind_id = uuid.uuid4().hex
        packet = {"answer_id": blind_id, "question": q["question"], "marks": q["designated_marks"],
                  "answer": answer, "rubric": json.dumps(q["rubrics"][str(q["designated_marks"])]),
                  "evidence": source_text, "reviewer": "", "score": "", "accuracy_notes": "", "rubric_notes": ""}
        packets.append(packet)
        mapping.append({"answer_id": blind_id, "question_id": q["id"], "system_id": "current_product",
                        "marks": q["designated_marks"], "answerability": q["answerability"],
                        "review_fields_sha256": {name: _display_hash(_csv_safe(packet[name])) for name in
                                                 ("question", "marks", "answer", "rubric", "evidence")}})
    if not packets:
        raise ValueError("No completed outputs are available to grade")
    random.SystemRandom().shuffle(packets)
    payload = _csv_payload(packets)
    private_map = {"answers": mapping, "private_keep_from_reviewers": True, "expected_independent_reviewers": 2}
    write_new(output / "private_mapping.json", private_map)
    write_new(output / "human_reviewer_1.csv", payload)
    write_new(output / "human_reviewer_2.csv", payload)
    reference_pages = [page for page in data["documents"][0]["pages"] if page["page"] in (10, 11, 12, 13)]
    reference_material = "\n\n".join(f"module 4.pdf, PDF page {page['page']}\n{page['canonical_text']}" for page in reference_pages)
    public = {"instructions": "Grade independently using only the rubric and supplied original notes. Do not consult another review or private_mapping. Return a JSON object with reviewer_id, reviewer_kind='ai', and rows containing answer_id, criterion_scores, total_marks, factual_errors, missing_content, diagram_assessment, rationale. AI scores are diagnostic and must not be called NHRS. Award no content credit for unsupported claims; assess diagram order/labels and separate subtopics. A blank/withheld answer is not a completed explanation. The bracketed text '[No answer text was returned.]' is a reviewer display placeholder for an empty stateless API answer, not a model-generated response or a browser conversation turn. Never count length as a quality criterion.",
              "reference_material": reference_material,
              "answers": [{key: value for key, value in row.items() if key not in ("reviewer", "score", "accuracy_notes", "rubric_notes")}
                          for row in packets]}
    write_new(output / "blind_ai_packet.json", public)
    write_new(output / "human_reviewer_1.html", human_html(packets, reference_material))
    write_new(output / "human_reviewer_2.html", human_html(list(reversed(packets)), reference_material))
    human_summary = summarize_reviews([output / "human_reviewer_1.csv", output / "human_reviewer_2.csv"], private_map)
    write_new(output / "human_status.json", human_summary)
    print(json.dumps({"exported_answers": len(packets), "human_grading": human_summary["status"]}))


def summarize_ai(packet_path: Path, review_paths: list[Path], output: Path) -> None:
    """AI reviews use a distinct metric name and cannot populate human CSVs."""
    packet = load(packet_path)
    answers = {row["answer_id"]: row for row in packet["answers"]}
    mapping = {row["answer_id"]: row for row in load(packet_path.with_name("private_mapping.json"))["answers"]}
    if set(mapping) != set(answers):
        raise ValueError("Packet and private answerability mapping differ")
    if len(review_paths) != 2:
        raise ValueError("Two independent AI review files are required")
    graders, by_answer = set(), {key: [] for key in answers}
    for path in review_paths:
        review = load(path)
        raw_grader = review.get("reviewer_id", "")
        grader = raw_grader.strip().casefold() if isinstance(raw_grader, str) else ""
        if review.get("reviewer_kind") != "ai" or not grader or grader in graders:
            raise ValueError("AI review identity must be distinct and explicitly labelled")
        graders.add(grader)
        rows = review.get("rows", [])
        if {row.get("answer_id") for row in rows} != set(answers) or len(rows) != len(answers):
            raise ValueError("Every completed answer needs exactly one rating from each AI grader")
        for row in rows:
            item = answers[row["answer_id"]]
            rubric = json.loads(item["rubric"])
            maxima = {criterion["id"]: criterion["max_marks"] for criterion in rubric["criteria"]}
            scores = row["criterion_scores"]
            if set(scores) != set(maxima) or any(type(value) not in (int, float) or not 0 <= value <= maxima[key]
                                               for key, value in scores.items()):
                raise ValueError("AI criterion scores exceed the fixed rubric")
            total = sum(scores.values())
            if type(row["total_marks"]) not in (int, float) or not 0 <= row["total_marks"] <= item["marks"] or abs(total - row["total_marks"]) > 1e-6:
                raise ValueError("AI total does not equal criterion scores")
            if any(not isinstance(row.get(key), list) or any(not isinstance(note, str) for note in row[key])
                   for key in ("factual_errors", "missing_content")) or any(
                    not isinstance(row.get(key), str) or not row[key].strip() for key in ("diagram_assessment", "rationale")):
                raise ValueError("Independent review must record factual, coverage and diagram assessments")
            by_answer[row["answer_id"]].append(total / item["marks"])
    rows = [{"answer_id": key, "marks": answers[key]["marks"], "answerability": mapping[key]["answerability"],
             "mean_ai_normalized_rubric_score": statistics.mean(values),
             "absolute_ai_disagreement": abs(values[0] - values[1]), "requires_adjudication": abs(values[0] - values[1]) > .2}
            for key, values in by_answer.items()]
    def by_marks(answerability: str) -> dict:
        return {str(marks): {"answers": len(chosen), "mean_ai_normalized_rubric_score": statistics.mean(
            row["mean_ai_normalized_rubric_score"] for row in chosen)} for marks in (5, 10, 15)
            if (chosen := [row for row in rows if row["marks"] == marks and row["answerability"] == answerability])}
    write_new(output, {"status": "independent_ai_diagnostic_only", "metric": "AI normalized rubric score, not NHRS",
                       "reviewers": sorted(graders), "review_files_sha256": {path.name: digest(path.read_bytes()) for path in review_paths},
                       "packet_sha256": digest(packet_path.read_bytes()), "rows": rows,
                       "answerable_by_marks": by_marks("answerable"), "unanswerable_safe_abstention_by_marks": by_marks("unanswerable"),
                       "human_nhrs": None, "limitations": ["Same model family and AI-authored rubrics can produce correlated errors.",
                           "Small unreviewed development slice; no qualified human grade, confidence interval or improvement claim."]})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare"); p.add_argument("--source-pdf", type=Path, required=True); p.add_argument("--annotation-spec", type=Path, required=True); p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("capture"); p.add_argument("--dataset", type=Path, required=True); p.add_argument("--output", type=Path, required=True)
    p.add_argument("--question", action="append"); p.add_argument("--pause", type=float, default=30); p.add_argument("--code-commit", required=True)
    p = sub.add_parser("export"); p.add_argument("--dataset", type=Path, required=True); p.add_argument("--run", type=Path, required=True); p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("ai-summary"); p.add_argument("--packet", type=Path, required=True); p.add_argument("--reviews", nargs=2, type=Path, required=True); p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare": prepare(args.source_pdf, args.output, args.annotation_spec)
    elif args.command == "capture":
        if not 0 <= args.pause <= 60: raise ValueError("Pause must be between 0 and 60 seconds")
        asyncio.run(capture(args))
    elif args.command == "export": export(args.dataset, args.run, args.output)
    else: summarize_ai(args.packet, args.reviews, args.output)


if __name__ == "__main__":
    main()
