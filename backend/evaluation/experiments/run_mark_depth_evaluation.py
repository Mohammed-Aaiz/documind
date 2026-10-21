"""Mark-depth evaluation: is a 15-mark answer actually deeper than a 5-mark one?

The API accepting 5/10/15 is not evidence that the formats differ.  This script
runs the real generative service on a fixed set of questions at all three
formats and measures properties that can be checked without a human judge:

* **length** — characters and words;
* **coverage** — how many distinct key facts (hand-labelled per question, in
  this file) the answer contains; this is a correctness signal, not a style one;
* **evidence breadth** — distinct evidence blocks cited;
* **redundancy** — the largest word overlap between two sentences of the answer;
* **grounding** — the deterministic verifier's status and unsupported-claim rate;
* **latency**.

The fixture is a self-contained maintenance manual, so the run is reproducible
and needs no database: every section becomes one numbered evidence block, the
same shape the production retrieval pipeline produces.

Usage (from ``backend/``)::

    python -m evaluation.experiments.run_mark_depth_evaluation
"""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

REPORT_ROOT = Path("evaluation/reports")
RUN_ID = "mark_depth_2026-10-17"
FORMATS = ("5", "10", "15")

# ---------------------------------------------------------------------------
# Fixture evidence (one block per section, as retrieval would deliver it)
# ---------------------------------------------------------------------------

SECTIONS: dict[str, str] = {
    "Overview": (
        "The calibration programme keeps every field robot within its measurement "
        "tolerance. Calibration is the process of comparing an instrument's reading "
        "against a reference standard and correcting the difference. Each robot is "
        "assigned a calibration owner in the fleet register."
    ),
    "Intervals": (
        "The lidar array requires calibration every 30 days. The sensor array is "
        "recalibrated every 90 days. The power rail is verified annually. Intervals "
        "are shortened after a collision or a firmware update."
    ),
    "Procedure": (
        "Calibration follows four steps. First the robot is parked on a level pad and "
        "the reference target is mounted. Second the lidar sweep is recorded and "
        "compared with the reference distances. Third the offsets are written to the "
        "controller and the sweep is repeated. Finally the result is signed off in the "
        "maintenance log."
    ),
    "Manual versus automated": (
        "Manual calibration needs a technician and takes about two hours. Automated "
        "calibration uses the docking station and finishes in twelve minutes. Manual "
        "calibration is more accurate on damaged hardware, while automated calibration "
        "is cheaper for a large fleet."
    ),
    "Failure handling": (
        "A failed calibration check blocks the robot from dispatch until it is "
        "resolved. Repeated failures on the same axis indicate a worn bearing. "
        "Calibration cannot correct a physically damaged lidar unit."
    ),
    "Records": (
        "Calibration records are retained for five years. Each record stores the "
        "technician, the reference target identifier and the measured offsets."
    ),
}


def _blocks():
    from generation.types import EvidenceBlock

    return [
        EvidenceBlock(index=index, content=content, document_name="field-robotics-manual.pdf", section=name)
        for index, (name, content) in enumerate(SECTIONS.items(), start=1)
    ]


@dataclass(frozen=True)
class GradedQuestion:
    question: str
    kind: str
    key_facts: tuple[str, ...]


QUESTIONS: tuple[GradedQuestion, ...] = (
    GradedQuestion(
        question="What is calibration and why is it required?",
        kind="definition",
        key_facts=("reference standard", "tolerance"),
    ),
    GradedQuestion(
        question="How often is the lidar array calibrated?",
        kind="factual",
        key_facts=("30 days",),
    ),
    GradedQuestion(
        question="What are the steps of the calibration procedure?",
        kind="process",
        key_facts=("level pad", "reference target", "offsets", "sign"),
    ),
    GradedQuestion(
        question="Compare manual and automated calibration.",
        kind="comparison",
        key_facts=("two hours", "twelve minutes", "accurate", "cheaper"),
    ),
    GradedQuestion(
        question="What happens when a calibration check fails, and what are the limits of calibration?",
        kind="explanation",
        key_facts=("blocks the robot", "worn bearing", "damaged"),
    ),
)


# ---------------------------------------------------------------------------
# Measurements
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9.%/-]*")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _sentences(text: str) -> list[str]:
    return [piece.strip() for piece in _SENTENCE_RE.split(text) if piece.strip()]


def _key_fact_recall(answer: str, facts: Sequence[str]) -> float:
    lowered = " ".join(answer.lower().split())
    if not facts:
        return 0.0
    return sum(1 for fact in facts if fact.lower() in lowered) / len(facts)


def _redundancy(answer: str) -> float:
    sentences = [set(_words(s)) for s in _sentences(answer)]
    worst = 0.0
    for i, first in enumerate(sentences):
        for second in sentences[i + 1 :]:
            if not first or not second:
                continue
            worst = max(worst, len(first & second) / len(first | second))
    return round(worst, 3)


@dataclass
class DepthResult:
    question: str
    kind: str
    marks: str
    answer: str
    words: int
    sentences: int
    key_fact_recall: float
    distinct_blocks: int
    redundancy: float
    status: str
    unsupported_claims: int
    verified: bool
    latency_ms: int
    warnings: list[str] = field(default_factory=list)


def evaluate() -> dict:
    from generation.service import answer_generatively

    blocks = _blocks()
    results: list[DepthResult] = []
    for graded in QUESTIONS:
        for marks in FORMATS:
            result = answer_generatively(graded.question, blocks, answer_format=marks)
            verification = result.verification
            citations = {
                int(number)
                for number in re.findall(r"\[(\d{1,2})\]", result.answer)
            }
            results.append(
                DepthResult(
                    question=graded.question,
                    kind=graded.kind,
                    marks=marks,
                    answer=result.answer,
                    words=len(_words(result.answer)),
                    sentences=len(_sentences(result.answer)),
                    key_fact_recall=round(
                        _key_fact_recall(result.answer, graded.key_facts), 3
                    ),
                    distinct_blocks=len(citations),
                    redundancy=_redundancy(result.answer),
                    status=str(verification.get("status", "UNKNOWN")),
                    unsupported_claims=len(verification.get("unsupportedClaims", [])),
                    verified=bool(verification.get("verified")),
                    latency_ms=result.latency_ms,
                    warnings=list(result.warnings),
                )
            )
    return {
        "summary": _summarise(results),
        "results": [result.__dict__ for result in results],
    }


def _summarise(results: list[DepthResult]) -> dict:
    by_marks: dict[str, dict] = {}
    for marks in FORMATS:
        group = [r for r in results if r.marks == marks]
        by_marks[marks] = {
            "answers": len(group),
            "mean_words": round(statistics.mean(r.words for r in group), 1),
            "mean_sentences": round(statistics.mean(r.sentences for r in group), 1),
            "mean_key_fact_recall": round(
                statistics.mean(r.key_fact_recall for r in group), 3
            ),
            "mean_distinct_blocks": round(
                statistics.mean(r.distinct_blocks for r in group), 1
            ),
            "max_redundancy": max(r.redundancy for r in group),
            "supported_rate": round(
                sum(1 for r in group if r.status == "SUPPORTED") / len(group), 3
            ),
            "unsupported_claim_rate": round(
                sum(r.unsupported_claims for r in group)
                / max(1, sum(r.sentences for r in group)),
                3,
            ),
            "latency_p50_ms": statistics.median(r.latency_ms for r in group),
            "latency_p95_ms": max(r.latency_ms for r in group),
        }

    per_question: dict[str, dict[str, dict]] = {}
    for graded in QUESTIONS:
        entry: dict[str, dict] = {}
        for marks in FORMATS:
            row = next(
                r for r in results if r.question == graded.question and r.marks == marks
            )
            entry[marks] = {
                "words": row.words,
                "key_fact_recall": row.key_fact_recall,
                "distinct_blocks": row.distinct_blocks,
                "status": row.status,
            }
        per_question[graded.question] = entry

    return {
        "run_id": RUN_ID,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "model": _model_name(),
        "fixture": "field-robotics-manual.pdf (synthetic, 6 sections)",
        "questions": len(QUESTIONS),
        "formats": list(FORMATS),
        "by_marks": by_marks,
        "per_question": per_question,
        "monotonic_depth": {
            "words": by_marks["5"]["mean_words"]
            < by_marks["10"]["mean_words"]
            < by_marks["15"]["mean_words"],
            "key_fact_recall": by_marks["5"]["mean_key_fact_recall"]
            <= by_marks["10"]["mean_key_fact_recall"]
            <= by_marks["15"]["mean_key_fact_recall"],
        },
    }


def _model_name() -> str:
    try:
        from generation.engine import generator_model_name

        return generator_model_name()
    except Exception:  # pragma: no cover - metadata only
        return "unknown"


def render_markdown(summary: dict) -> str:
    lines = [
        "# Mark-depth evaluation — 5 vs 10 vs 15 marks",
        "",
        f"- Run: `{summary['run_id']}`",
        f"- Started: {summary['started_at']}",
        f"- Model: `{summary['model']}`",
        f"- Fixture: {summary['fixture']}",
        f"- Questions: {summary['questions']} (definition, factual, process, comparison, explanation)",
        "- Every question is asked at every format; key facts are hand-labelled in the "
        "evaluation script.",
        "",
        "## Aggregate by format",
        "",
        "| Format | Mean words | Mean sentences | Key-fact recall | Distinct sources | "
        "Max redundancy | SUPPORTED rate | Latency p50 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for marks in FORMATS:
        row = summary["by_marks"][marks]
        lines.append(
            f"| {marks} | {row['mean_words']} | {row['mean_sentences']} | "
            f"{row['mean_key_fact_recall']:.3f} | {row['mean_distinct_blocks']} | "
            f"{row['max_redundancy']:.3f} | {row['supported_rate']:.3f} | "
            f"{row['latency_p50_ms']:.0f} ms |"
        )
    lines += ["", "## Per question", "", "| Question | 5 marks | 10 marks | 15 marks |", "|---|---|---|---|"]
    for question, entry in summary["per_question"].items():
        cells = [
            f"{entry[m]['words']}w / facts {entry[m]['key_fact_recall']:.2f} / {entry[m]['status']}"
            for m in FORMATS
        ]
        lines.append(f"| {question} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Verdict",
        "",
        f"- Word counts strictly increase with marks: **{summary['monotonic_depth']['words']}**",
        f"- Key-fact recall does not decrease with marks: "
        f"**{summary['monotonic_depth']['key_fact_recall']}**",
        "",
        "Depth is produced by adding further evidence sentences with their own citations "
        "(see `generation/planning.py`), not by asking the model to write more. A point is "
        "only added when it is relevant to the question, does not restate the direct "
        "answer, and (for numeric points) mentions the question's own entity.",
        "",
    ]
    return "\n".join(lines)


def write_report(payload: dict, run_id: str = RUN_ID) -> Path:
    out_dir = REPORT_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "REPORT.md").write_text(render_markdown(payload["summary"]), encoding="utf-8")
    return out_dir


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate 5/10/15-mark answer depth.")
    parser.add_argument(
        "--run-id",
        default=RUN_ID,
        help="Report directory name; use a new value instead of overwriting a previous run.",
    )
    args = parser.parse_args()

    payload = evaluate()
    out_dir = write_report(payload, args.run_id)
    print(json.dumps({"out_dir": str(out_dir), "by_marks": payload["summary"]["by_marks"]}, indent=2))


if __name__ == "__main__":
    main()
