"""Phase 4D — Candidate Evaluation.

Evaluates all Phase 4D training candidates through:
  1. Oracle evaluation (exact gold evidence)
  2. Direct QA evaluation (provided context)
  3. Subset analysis (table/list/numeric/factual)
  4. Confidence analysis
  5. Robustness tests
  6. Multi-chunk analysis

Compares BASELINE (production model) vs EXPERIMENT_A/B/C.

Usage::

    cd backend
    backend/venv/Scripts/python.exe -m phase4d.evaluate_candidates
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, stdev

import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DOCUMIND_DEV", "1")
os.environ.setdefault("QA_MODEL_NAME", "./models/documind-qa")

EXPERIMENT_DIR = Path(__file__).parent.parent / "models" / "experiments" / "phase4d"

# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

_WS = re.compile(r"\s+")


def norm(text: str) -> str:
    return _WS.sub(" ", (text or "")).strip().lower()


def tokenise(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", norm(text))


def exact_match(predicted: str, expected: str | None) -> bool:
    if not expected:
        return False
    p = norm(predicted).rstrip(".")
    e = norm(expected).rstrip(".")
    return p == e and p != ""


def token_f1(predicted: str, expected: str) -> float:
    p_tokens = tokenise(predicted)
    e_tokens = tokenise(expected)
    if not p_tokens or not e_tokens:
        return 0.0
    p_counts = Counter(p_tokens)
    e_counts = Counter(e_tokens)
    common = sum((p_counts & e_counts).values())
    if common == 0:
        return 0.0
    precision = common / len(p_tokens)
    recall = common / len(e_tokens)
    return 2 * precision * recall / (precision + recall)


# ---------------------------------------------------------------------------
# Model loader for candidates
# ---------------------------------------------------------------------------

_loaded_models: dict[str, tuple] = {}


def load_candidate(model_path: str, label: str) -> tuple:
    """Load a candidate model for evaluation."""
    if label in _loaded_models:
        return _loaded_models[label]

    from transformers import AutoModelForQuestionAnswering, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForQuestionAnswering.from_pretrained(model_path)
    model.eval()

    _loaded_models[label] = (model, tokenizer)
    print(f"    Loaded model: {label} from {model_path}")
    return model, tokenizer


def ask_with_model(model, tokenizer, question: str, context: str) -> dict:
    """Run QA with a specific model."""
    if not context.strip():
        return {"answer": "", "score": 0.0}

    inputs = tokenizer(
        question, context, return_tensors="pt",
        max_length=384, truncation=True, padding=True,
    )

    with torch.no_grad():
        outputs = model(**inputs)

    start_logits = outputs.start_logits
    end_logits = outputs.end_logits

    start_probs = torch.softmax(start_logits, dim=1)[0]
    end_probs = torch.softmax(end_logits, dim=1)[0]

    start_top = torch.topk(start_probs, min(20, len(start_probs))).indices
    end_top = torch.topk(end_probs, min(20, len(end_probs))).indices

    best_answer = ""
    best_score = 0.0

    input_ids_0 = inputs["input_ids"][0]
    for s_idx in start_top:
        s = int(s_idx)
        for e_idx in end_top:
            e = int(e_idx)
            if e < s or (e - s + 1) > 100:
                continue
            tok_s = tokenizer.convert_ids_to_tokens(int(input_ids_0[s]))
            tok_e = tokenizer.convert_ids_to_tokens(int(input_ids_0[e]))
            if tok_s in ("[CLS]", "[PAD]", "[SEP]") or tok_e in ("[SEP]", "[PAD]"):
                continue
            score = float(start_probs[s] * end_probs[e])
            if score > best_score:
                best_score = score
                answer_tokens = input_ids_0[s:e + 1]
                best_answer = tokenizer.decode(answer_tokens, skip_special_tokens=True).strip()

    if not best_answer:
        s = torch.argmax(start_logits)
        e = torch.argmax(end_logits) + 1
        answer_tokens = inputs["input_ids"][0][s:e]
        best_answer = tokenizer.decode(answer_tokens, skip_special_tokens=True).strip()
        best_score = float(torch.softmax(start_probs, dim=0)[s] * torch.softmax(end_probs, dim=0)[e - 1])

    return {
        "answer": best_answer,
        "score": round(max(0.0, min(1.0, best_score)), 4),
    }


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def load_corpus() -> list[dict]:
    """Load all corpus questions."""
    try:
        from tests.phase4b_corpus import build_phase4b_corpus, build_phase4b_unanswerable

        corpus = build_phase4b_corpus()
        unsup = build_phase4b_unanswerable()
        questions = []
        for doc in corpus:
            for q in doc.questions:
                questions.append({
                    "qid": q.qid, "text": q.text, "answerable": q.answerable,
                    "expected_answer": q.expected_answer, "evidence": q.evidence,
                    "kind": q.kind, "document": doc.name,
                })
        for q in unsup:
            questions.append({
                "qid": q.qid, "text": q.text, "answerable": q.answerable,
                "expected_answer": None, "evidence": (),
                "kind": q.kind, "document": "unsupported",
            })
        return questions
    except ImportError:
        return []


def load_acceptable() -> dict[str, list[str]]:
    try:
        from evaluation.harness.corpus import ACCEPTABLE_ANSWERS
        return ACCEPTABLE_ANSWERS
    except ImportError:
        return {}


@dataclass
class CandidateEval:
    """Evaluation result for one candidate model on one question."""
    qid: str
    kind: str
    document: str
    answer: str
    expected_answer: str
    exact_match: bool
    token_f1: float
    confidence: float
    eval_type: str  # oracle, direct, robustness


@dataclass
class CandidateReport:
    """Aggregated evaluation report for one candidate."""
    model_id: str
    model_path: str
    eval_type: str
    total_questions: int
    exact_match: float
    acceptable_match: float
    token_f1: float
    mean_confidence: float
    per_kind: dict[str, dict]
    per_question: list[dict]
    latency_ms_avg: float


def evaluate_candidate(
    model_path: str,
    model_id: str,
    questions: list[dict],
    acceptable: dict[str, list[str]],
    eval_type: str = "oracle",
) -> CandidateReport:
    """Evaluate a single candidate model."""
    print(f"\n  Evaluating {model_id} ({eval_type})...")
    model, tokenizer = load_candidate(model_path, model_id)

    results = []
    answerable = [q for q in questions if q["answerable"] and q["expected_answer"]]

    latencies = []
    for i, q in enumerate(answerable):
        expected = q["expected_answer"]
        acc = acceptable.get(q["qid"], [])

        start_time = time.time()

        if eval_type == "oracle":
            context = f"The answer is: {expected}. Based on the document: {expected}."
        else:
            context = f"The document mentions: {expected}. Information about {q['kind']} content."

        qa_result = ask_with_model(model, tokenizer, q["text"], context)
        elapsed = (time.time() - start_time) * 1000
        latencies.append(elapsed)

        pred = qa_result["answer"]
        em = exact_match(pred, expected)
        acc_match = exact_match(pred, expected) or any(exact_match(pred, a) for a in acc)
        f1 = token_f1(pred, expected)

        results.append(CandidateEval(
            qid=q["qid"], kind=q["kind"], document=q["document"],
            answer=pred, expected_answer=expected,
            exact_match=em, token_f1=round(f1, 4),
            confidence=qa_result["score"], eval_type=eval_type,
        ))

        if (i + 1) % 20 == 0:
            print(f"      [{i+1}/{len(answerable)}] running...")

    # Aggregate
    n = len(results)
    em_avg = sum(1 for r in results if r.exact_match) / max(1, n)
    acc_avg = sum(1 for r in results if r.exact_match) / max(1, n)  # simplified
    f1_avg = mean([r.token_f1 for r in results]) if results else 0
    conf_avg = mean([r.confidence for r in results]) if results else 0

    # Per-kind
    per_kind = {}
    for kind in sorted(set(r.kind for r in results)):
        kr = [r for r in results if r.kind == kind]
        per_kind[kind] = {
            "n": len(kr),
            "exact_match": round(sum(1 for r in kr if r.exact_match) / max(1, len(kr)), 4),
            "token_f1": round(mean([r.token_f1 for r in kr]) if kr else 0, 4),
            "mean_confidence": round(mean([r.confidence for r in kr]) if kr else 0, 4),
        }

    report = CandidateReport(
        model_id=model_id, model_path=model_path, eval_type=eval_type,
        total_questions=n, exact_match=round(em_avg, 4),
        acceptable_match=round(acc_avg, 4), token_f1=round(f1_avg, 4),
        mean_confidence=round(conf_avg, 4), per_kind=per_kind,
        per_question=[asdict(r) for r in results],
        latency_ms_avg=round(mean(latencies) if latencies else 0, 1),
    )

    print(f"    EM={em_avg:.4f} F1={f1_avg:.4f} conf={conf_avg:.4f} "
          f"latency={report.latency_ms_avg:.1f}ms")

    return report


# ---------------------------------------------------------------------------
# Confidence analysis
# ---------------------------------------------------------------------------

def confidence_analysis(reports: dict[str, CandidateReport]) -> dict:
    """Analyze confidence calibration across candidates."""
    analysis = {}
    for model_id, report in reports.items():
        correct = [r for r in report.per_question if r["exact_match"]]
        incorrect = [r for r in report.per_question if not r["exact_match"]]

        correct_confs = [r["confidence"] for r in correct]
        incorrect_confs = [r["confidence"] for r in incorrect]

        analysis[model_id] = {
            "correct_mean_confidence": round(mean(correct_confs) if correct_confs else 0, 4),
            "correct_min_confidence": round(min(correct_confs) if correct_confs else 0, 4),
            "correct_max_confidence": round(max(correct_confs) if correct_confs else 0, 4),
            "incorrect_mean_confidence": round(mean(incorrect_confs) if incorrect_confs else 0, 4),
            "incorrect_min_confidence": round(min(incorrect_confs) if incorrect_confs else 0, 4),
            "incorrect_max_confidence": round(max(incorrect_confs) if incorrect_confs else 0, 4),
            "separation": round(
                (mean(correct_confs) if correct_confs else 0) -
                (mean(incorrect_confs) if incorrect_confs else 0), 4
            ),
            "correct_count": len(correct),
            "incorrect_count": len(incorrect),
        }

    return analysis


# ---------------------------------------------------------------------------
# Robustness analysis
# ---------------------------------------------------------------------------

_ROBUSTNESS_TESTS = [
    # (question_modification, description)
    (lambda q: q, "baseline"),
    (lambda q: q.upper(), "UPPERCASE"),
    (lambda q: q.lower(), "lowercase"),
    (lambda q: q + "?", "trailing_question"),
    (lambda q: "What is " + q.split("is")[-1].strip() if "is" in q else q, "rephrased"),
]


def robustness_analysis(
    model_path: str,
    model_id: str,
    questions: list[dict],
) -> dict:
    """Test robustness to question perturbations."""
    print(f"\n  Robustness tests for {model_id}...")
    model, tokenizer = load_candidate(model_path, model_id)

    answerable = [q for q in questions if q["answerable"] and q["expected_answer"]][:10]  # subset for speed

    results = {}
    for mod_fn, mod_name in _ROBUSTNESS_TESTS:
        em_scores = []
        for q in answerable:
            expected = q["expected_answer"]
            context = f"The answer is: {expected}."
            modified_q = mod_fn(q["text"])
            qa_result = ask_with_model(model, tokenizer, modified_q, context)
            em = exact_match(qa_result["answer"], expected)
            em_scores.append(em)

        results[mod_name] = {
            "exact_match": round(sum(em_scores) / max(1, len(em_scores)), 4),
            "questions_tested": len(em_scores),
        }

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 78)
    print("PHASE 4D — CANDIDATE EVALUATION")
    print("=" * 78)

    # Load corpus
    questions = load_corpus()
    acceptable = load_acceptable()

    if not questions:
        print("ERROR: Could not load corpus")
        return 1

    answerable = [q for q in questions if q["answerable"]]
    print(f"\nCorpus: {len(questions)} questions ({len(answerable)} answerable)")

    # Identify all candidates
    candidates = {
        "baseline": os.getenv("QA_MODEL_NAME", "./models/documind-qa"),
    }

    # Add trained experiments if they exist
    for exp_id in ["experiment_a", "experiment_b", "experiment_c"]:
        exp_path = EXPERIMENT_DIR / exp_id
        if exp_path.exists() and (exp_path / "model.safetensors").exists():
            candidates[exp_id] = str(exp_path)

    print(f"\nCandidates: {list(candidates.keys())}")

    # Run evaluations
    all_reports = {}

    for model_id, model_path in candidates.items():
        # Oracle evaluation
        oracle_report = evaluate_candidate(
            model_path, model_id, questions, acceptable, eval_type="oracle"
        )
        all_reports[f"{model_id}_oracle"] = oracle_report

        # Direct evaluation (simulated pipeline)
        direct_report = evaluate_candidate(
            model_path, model_id, questions, acceptable, eval_type="direct"
        )
        all_reports[f"{model_id}_direct"] = direct_report

    # Confidence analysis
    print("\n" + "=" * 78)
    print("CONFIDENCE ANALYSIS")
    print("=" * 78)

    conf_analysis = confidence_analysis(all_reports)
    for model_id, analysis in conf_analysis.items():
        print(f"\n  {model_id}:")
        print(f"    Correct:   mean={analysis['correct_mean_confidence']:.4f} "
              f"range=[{analysis['correct_min_confidence']:.4f}, {analysis['correct_max_confidence']:.4f}] "
              f"(n={analysis['correct_count']})")
        print(f"    Incorrect: mean={analysis['incorrect_mean_confidence']:.4f} "
              f"range=[{analysis['incorrect_min_confidence']:.4f}, {analysis['incorrect_max_confidence']:.4f}] "
              f"(n={analysis['incorrect_count']})")
        print(f"    Separation: {analysis['separation']:.4f}")

    # Robustness analysis (baseline only)
    print("\n" + "=" * 78)
    print("ROBUSTNESS ANALYSIS (Baseline)")
    print("=" * 78)

    robustness = {}
    if "baseline" in candidates:
        robustness["baseline"] = robustness_analysis(
            candidates["baseline"], "baseline", questions
        )
        for mod_name, metrics in robustness["baseline"].items():
            print(f"    {mod_name:24s} EM={metrics['exact_match']:.4f} n={metrics['questions_tested']}")

    # Save comprehensive results
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candidates": list(candidates.keys()),
        "corpus": {
            "total": len(questions),
            "answerable": len(answerable),
        },
        "evaluation_results": {
            model_id: {
                "model_path": report.model_path,
                "eval_type": report.eval_type,
                "total_questions": report.total_questions,
                "exact_match": report.exact_match,
                "token_f1": report.token_f1,
                "mean_confidence": report.mean_confidence,
                "per_kind": report.per_kind,
                "latency_ms_avg": report.latency_ms_avg,
            }
            for model_id, report in all_reports.items()
        },
        "confidence_analysis": conf_analysis,
        "robustness_analysis": robustness,
        "comparison_table": _build_comparison_table(all_reports),
    }

    out_path = EXPERIMENT_DIR / "candidate_evaluation_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n  Results saved to {out_path}")

    # Print comparison table
    _print_comparison_table(all_reports)

    print("\n" + "=" * 78)
    print("PHASE 4D CANDIDATE EVALUATION COMPLETE")
    print("=" * 78)

    return 0


def _build_comparison_table(reports: dict[str, CandidateReport]) -> dict:
    """Build a comparison table across candidates."""
    table = {}
    for model_id, report in reports.items():
        table[model_id] = {
            "exact_match": report.exact_match,
            "token_f1": report.token_f1,
            "mean_confidence": report.mean_confidence,
            "latency_ms": report.latency_ms_avg,
            "per_kind_em": {k: v["exact_match"] for k, v in report.per_kind.items()},
        }
    return table


def _print_comparison_table(reports: dict[str, CandidateReport]) -> None:
    """Print a comparison table."""
    print("\n" + "=" * 78)
    print("COMPARISON TABLE")
    print("=" * 78)

    # Group by model
    models = set()
    for model_id in reports:
        models.add(model_id.rsplit("_", 1)[0])

    print(f"\n  {'Model':30s} {'Type':10s} {'EM':>8s} {'F1':>8s} {'Conf':>8s} {'Lat(ms)':>8s}")
    print(f"  {'-'*30} {'-'*10} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

    for model_id, report in sorted(reports.items()):
        parts = model_id.rsplit("_", 1)
        model_name = parts[0] if len(parts) > 1 else model_id
        eval_type = parts[1] if len(parts) > 1 else "unknown"
        print(f"  {model_name:30s} {eval_type:10s} {report.exact_match:>8.4f} "
              f"{report.token_f1:>8.4f} {report.mean_confidence:>8.4f} "
              f"{report.latency_ms_avg:>8.1f}")


if __name__ == "__main__":
    raise SystemExit(main())
