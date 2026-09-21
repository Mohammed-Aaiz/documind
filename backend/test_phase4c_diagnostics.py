#!/usr/bin/env python3
"""Phase 4C — QA Failure Isolation Diagnostics.

OFFLINE diagnostic experiments.  NO production code changes.

Experiments:
  1. Table control experiment (4 representations x table questions)
  2. List control experiment (3 representations x list questions)
  3. Oracle evidence experiment (exact gold evidence only)
  4. RET_MISS replay (15 failures)
  5. EVID_OMIT replay (10 failures)
  6. CTX_TRUNC replay (5 failures)
  7. Extractive architecture limitation test
  8. Confidence analysis

Usage::

    cd backend
    python test_phase4c_diagnostics.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("DOCUMIND_DEV", "1")
os.environ.setdefault("QA_MODEL_NAME", "./models/documind-qa")


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

_WS = re.compile(r"\s+")


def norm(text: str) -> str:
    return _WS.sub(" ", (text or "")).strip().lower()


def tokenise(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", norm(text))


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


def exact_match(predicted: str, expected: str) -> bool:
    if not expected:
        return False
    p = norm(predicted).rstrip(".")
    e = norm(expected).rstrip(".")
    return p == e and p != ""


# ---------------------------------------------------------------------------
# QA model (direct call, no production pipeline)
# ---------------------------------------------------------------------------

_model = None
_tokenizer = None


def _load_qa_model():
    global _model, _tokenizer
    if _model is not None:
        return
    import torch
    from transformers import AutoModelForQuestionAnswering, AutoTokenizer
    model_path = os.getenv("QA_MODEL_NAME", "./models/documind-qa")
    _tokenizer = AutoTokenizer.from_pretrained(model_path)
    _model = AutoModelForQuestionAnswering.from_pretrained(model_path)
    _model.eval()
    print("  QA model loaded")


def ask(question: str, context: str) -> dict:
    """Direct QA model call.  Returns {answer, score, start, end}."""
    import torch
    _load_qa_model()

    if not context.strip():
        return {"answer": "", "score": 0.0, "start": 0, "end": 0}

    inputs = _tokenizer(
        question, context, return_tensors="pt",
        max_length=384, truncation=True, padding=True,
    )

    with torch.no_grad():
        outputs = _model(**inputs)

    start_logits = outputs.start_logits
    end_logits = outputs.end_logits

    start_probs = torch.softmax(start_logits, dim=1)[0]
    end_probs = torch.softmax(end_logits, dim=1)[0]

    start_top = torch.topk(start_probs, min(20, len(start_probs))).indices
    end_top = torch.topk(end_probs, min(20, len(end_probs))).indices

    best_answer = ""
    best_score = 0.0
    best_start = 0
    best_end = 0

    input_ids_0 = inputs["input_ids"][0]
    for s_idx in start_top:
        s = int(s_idx)
        for e_idx in end_top:
            e = int(e_idx)
            if e < s or (e - s + 1) > 100:
                continue
            tok_s = _tokenizer.convert_ids_to_tokens(int(input_ids_0[s]))
            tok_e = _tokenizer.convert_ids_to_tokens(int(input_ids_0[e]))
            if tok_s in ("[CLS]", "[PAD]", "[SEP]") or tok_e in ("[SEP]", "[PAD]"):
                continue
            score = float(start_probs[s] * end_probs[e])
            if score > best_score:
                best_score = score
                best_start = s
                best_end = e + 1
                answer_tokens = input_ids_0[s:e + 1]
                best_answer = _tokenizer.decode(answer_tokens, skip_special_tokens=True).strip()

    if not best_answer:
        s = torch.argmax(start_logits)
        e = torch.argmax(end_logits) + 1
        answer_tokens = inputs["input_ids"][0][s:e]
        best_answer = _tokenizer.decode(answer_tokens, skip_special_tokens=True).strip()
        best_score = float(torch.softmax(start_probs, dim=0)[s] * torch.softmax(end_probs, dim=0)[e - 1])

    return {
        "answer": best_answer,
        "score": round(max(0.0, min(1.0, best_score)), 4),
        "start": best_start,
        "end": best_end,
    }


# ---------------------------------------------------------------------------
# Table control experiment
# ---------------------------------------------------------------------------

def build_table_representations(table_data: list[list[str]], target_qid: str) -> dict[str, str]:
    """Build 4 representations of a table for controlled experiment."""
    if not table_data:
        return {}

    headers = table_data[0]
    rows = table_data[1:]

    # R1: Current pipe-delimited (as in production)
    r1_lines = [" | ".join(row) for row in table_data]
    r1 = "\n".join(r1_lines)

    # R2: Explicit row/column with headers
    r2_parts = []
    for row in rows:
        row_str = "; ".join(f"{h}: {v}" for h, v in zip(headers, row))
        r2_parts.append(row_str)
    r2 = "Table rows:\n" + "\n".join(r2_parts)

    # R3: Cell-focused (headers + all rows with explicit structure)
    r3_parts = ["Headers: " + ", ".join(headers)]
    for i, row in enumerate(rows):
        cells = "; ".join(f"{headers[j]}={row[j]}" for j in range(min(len(headers), len(row))))
        r3_parts.append(f"Row {i+1}: {cells}")
    r3 = "\n".join(r3_parts)

    # R4: Minimal (headers + all rows, very clean)
    r4_lines = ["Headers: " + " | ".join(headers)]
    for row in rows:
        r4_lines.append(" | ".join(row))
    r4 = "\n".join(r4_lines)

    return {"R1_pipe": r1, "R2_explicit": r2, "R3_cell": r3, "R4_minimal": r4}


def run_table_experiment(qid: str, question: str, expected: str, table_data: list[list[str]], acceptable: list[str]) -> dict:
    """Run table control experiment for one question."""
    reps = build_table_representations(table_data, qid)
    results = {}

    for rep_name, rep_text in reps.items():
        qa_result = ask(question, rep_text)
        pred = qa_result["answer"]
        em = exact_match(pred, expected)
        acc = any(exact_match(pred, a) for a in acceptable) if acceptable else False
        f1 = token_f1(pred, expected)

        results[rep_name] = {
            "prediction": pred,
            "exact_match": em,
            "acceptable_match": acc,
            "token_f1": round(f1, 4),
            "confidence": qa_result["score"],
        }

    return results


# ---------------------------------------------------------------------------
# List control experiment
# ---------------------------------------------------------------------------

def build_list_representations(list_items: list[str]) -> dict[str, str]:
    """Build 3 representations of a list for controlled experiment."""
    # R1: Current (newline-delimited, as in production)
    r1 = "\n".join(list_items)

    # R2: Explicit numbered
    r2 = "\n".join(f"{i+1}. {item}" for i, item in enumerate(list_items))

    # R3: Minimal (just the items with clear boundaries)
    r3 = "List items:\n" + "\n".join(f"- {item}" for item in list_items)

    return {"R1_newline": r1, "R2_numbered": r2, "R3_minimal": r3}


# ---------------------------------------------------------------------------
# Oracle experiment
# ---------------------------------------------------------------------------

def run_oracle_experiment(qid: str, question: str, evidence_text: str, expected: str, acceptable: list[str]) -> dict:
    """Run oracle experiment: QA model with ONLY the exact gold evidence."""
    qa_result = ask(question, evidence_text)
    pred = qa_result["answer"]
    em = exact_match(pred, expected)
    acc = any(exact_match(pred, a) for a in acceptable) if acceptable else False
    f1 = token_f1(pred, expected)

    return {
        "prediction": pred,
        "exact_match": em,
        "acceptable_match": acc,
        "token_f1": round(f1, 4),
        "confidence": qa_result["score"],
        "evidence_used": evidence_text[:200],
    }


# ---------------------------------------------------------------------------
# Main diagnostic runner
# ---------------------------------------------------------------------------

def main():
    print("=" * 78)
    print("PHASE 4C — QA FAILURE ISOLATION DIAGNOSTICS")
    print("=" * 78)

    # Load Phase 4B results
    with open("phase4b_evaluation_report.json") as f:
        report = json.load(f)

    c_questions = report["per_question"]["C"]
    answerable = [q for q in c_questions if q["answerable"]]
    failures = [q for q in answerable if q["failure_primary"] not in ("CORRECT", "CORRECT_ABSTAIN")]
    correct = [q for q in answerable if q["failure_primary"] in ("CORRECT",)]

    print(f"\nPhase 4B Arm C: {len(answerable)} answerable, {len(correct)} correct, {len(failures)} failures")

    # Load corpus for document builders
    from tests.phase4b_corpus import build_phase4b_corpus
    corpus = build_phase4b_corpus()

    # Build document→questions map
    doc_questions = {}
    for doc in corpus:
        doc_questions[doc.name] = doc

    # Build acceptable answers map
    from tests.phase4b_corpus import Question
    acceptable_map = {}
    # Import from Phase 3F
    from evaluation.harness.corpus import ACCEPTABLE_ANSWERS
    acceptable_map = ACCEPTABLE_ANSWERS

    results = {
        "table_experiment": {},
        "list_experiment": {},
        "oracle_experiment": {},
        "retmiss_replay": {},
        "evidomit_replay": {},
        "ctxtrunc_replay": {},
        "architecture_analysis": {},
        "confidence_analysis": {},
    }

    # ===================================================================
    # 1. TABLE CONTROL EXPERIMENT
    # ===================================================================
    print("\n" + "=" * 78)
    print("1. TABLE CONTROL EXPERIMENT")
    print("=" * 78)

    table_failures = [q for q in failures if q["kind"] == "table"]
    print(f"  Table failures: {len(table_failures)}")

    table_experiment_results = {}
    for q in table_failures:
        doc = doc_questions.get(q["document"])
        if not doc:
            continue

        # Find the table in the document
        # We need to build the document and extract the table
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / doc.name
            doc.builder(path)

            if doc.file_type == "docx":
                import docx
                d = docx.Document(str(path))
                for table in d.tables:
                    table_data = [[cell.text for cell in row.cells] for row in table.rows]
                    if len(table_data) > 1:
                        # Check if this table contains relevant content
                        flat = " ".join(" ".join(row) for row in table_data).lower()
                        evidence_words = [e.lower() for e in (doc.questions[0].evidence if doc.questions else [])]
                        if any(w in flat for w in ["method", "result", "accuracy", "config", "station",
                                                     "temperature", "region", "season", "revenue", "model"]):
                            acc = acceptable_map.get(q["qid"], [])
                            exp = q.get("answer", "")
                            # Find the actual expected answer from corpus
                            for cq in doc.questions:
                                if cq.qid == q["qid"]:
                                    exp = cq.expected_answer or ""
                                    acc = acceptable_map.get(q["qid"], [])
                                    break

                            exp_result = run_table_experiment(
                                q["qid"], q["document"], exp, table_data, acc
                            )
                            table_experiment_results[q["qid"]] = {
                                "question": q.get("answer", ""),
                                "expected": exp,
                                "table_rows": len(table_data),
                                "table_cols": len(table_data[0]) if table_data else 0,
                                "results": exp_result,
                            }
                            # Print summary
                            r1 = exp_result.get("R1_pipe", {})
                            r4 = exp_result.get("R4_minimal", {})
                            print(f"  {q['qid']:12s} R1: EM={r1.get('exact_match', False)} F1={r1.get('token_f1', 0):.3f} pred={r1.get('prediction', '')[:30]}")
                            print(f"             R4: EM={r4.get('exact_match', False)} F1={r4.get('token_f1', 0):.3f} pred={r4.get('prediction', '')[:30]}")
                            break

    results["table_experiment"] = table_experiment_results

    # ===================================================================
    # 2. LIST CONTROL EXPERIMENT
    # ===================================================================
    print("\n" + "=" * 78)
    print("2. LIST CONTROL EXPERIMENT")
    print("=" * 78)

    list_failures = [q for q in failures if q["kind"] == "list"]
    print(f"  List failures: {len(list_failures)}")

    list_experiment_results = {}
    for q in list_failures:
        doc = doc_questions.get(q["document"])
        if not doc:
            continue

        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / doc.name
            doc.builder(path)

            if doc.file_type == "docx":
                import docx
                d = docx.Document(str(path))
                # Find list items
                list_items = []
                for para in d.paragraphs:
                    if para.style and para.style.name.startswith("List"):
                        list_items.append(para.text.strip())

                if list_items:
                    reps = build_list_representations(list_items)
                    exp = ""
                    acc = []
                    for cq in doc.questions:
                        if cq.qid == q["qid"]:
                            exp = cq.expected_answer or ""
                            acc = acceptable_map.get(q["qid"], [])
                            break

                    list_results = {}
                    for rep_name, rep_text in reps.items():
                        qa_result = ask(q.get("answer", ""), rep_text)
                        pred = qa_result["answer"]
                        em = exact_match(pred, exp)
                        acc_match = any(exact_match(pred, a) for a in acc) if acc else False
                        f1 = token_f1(pred, exp)
                        list_results[rep_name] = {
                            "prediction": pred,
                            "exact_match": em,
                            "acceptable_match": acc_match,
                            "token_f1": round(f1, 4),
                            "confidence": qa_result["score"],
                        }

                    list_experiment_results[q["qid"]] = {
                        "question": q.get("answer", ""),
                        "expected": exp,
                        "item_count": len(list_items),
                        "results": list_results,
                    }
                    r1 = list_results.get("R1_newline", {})
                    r3 = list_results.get("R3_minimal", {})
                    print(f"  {q['qid']:12s} R1: EM={r1.get('exact_match', False)} F1={r1.get('token_f1', 0):.3f} pred={r1.get('prediction', '')[:30]}")
                    print(f"             R3: EM={r3.get('exact_match', False)} F1={r3.get('token_f1', 0):.3f} pred={r3.get('prediction', '')[:30]}")

    results["list_experiment"] = list_experiment_results

    # ===================================================================
    # 3. ORACLE EVIDENCE EXPERIMENT
    # ===================================================================
    print("\n" + "=" * 78)
    print("3. ORACLE EVIDENCE EXPERIMENT")
    print("=" * 78)

    # Run oracle on ALL failures (not just table/list)
    oracle_results = {}
    for q in failures:
        # For oracle, we need the exact gold evidence text
        # Use the question's expected answer as a proxy for what the context should contain
        exp = ""
        acc = []
        evidence_texts = []
        for doc in corpus:
            for cq in doc.questions:
                if cq.qid == q["qid"]:
                    exp = cq.expected_answer or ""
                    acc = acceptable_map.get(q["qid"], [])
                    # Build minimal context containing the expected answer
                    if exp:
                        evidence_texts.append(exp)
                    break

        if not evidence_texts:
            continue

        # Oracle: provide ONLY the evidence that contains the expected answer
        oracle_ctx = " ".join(evidence_texts)
        oracle_result = run_oracle_experiment(
            q["qid"], q.get("answer", ""), oracle_ctx, exp, acc
        )
        oracle_results[q["qid"]] = oracle_result

        em = oracle_result["exact_match"]
        f1 = oracle_result["token_f1"]
        pred = oracle_result["prediction"]
        status = "PASS" if em else "FAIL"
        print(f"  {q['qid']:12s} {status} EM={em} F1={f1:.3f} conf={oracle_result['confidence']:.4f} pred={pred[:40]}")

    results["oracle_experiment"] = oracle_results

    # ===================================================================
    # 4. RET_MISS REPLAY
    # ===================================================================
    print("\n" + "=" * 78)
    print("4. RET_MISS REPLAY (15 failures)")
    print("=" * 78)

    ret_miss = [q for q in failures if q["failure_primary"] == "RET_MISS"]
    for q in ret_miss:
        print(f"  {q['qid']:12s} {q['kind']:20s} {q['document']:30s} conf={q['qa_confidence']:.4f} answer='{q['answer'][:40]}'")

    # ===================================================================
    # 5. EVID_OMIT REPLAY
    # ===================================================================
    print("\n" + "=" * 78)
    print("5. EVID_OMIT REPLAY (10 failures)")
    print("=" * 78)

    evid_omit = [q for q in failures if q["failure_primary"] == "EVID_OMIT"]
    for q in evid_omit:
        print(f"  {q['qid']:12s} {q['kind']:20s} {q['document']:30s} ctx={q['context_tokens']}/{q['context_budget']} cov={q['coverage']:.1f} answer='{q['answer'][:40]}'")

    # ===================================================================
    # 6. CTX_TRUNC REPLAY
    # ===================================================================
    print("\n" + "=" * 78)
    print("6. CTX_TRUNC REPLAY (5 failures)")
    print("=" * 78)

    ctx_trunc = [q for q in failures if q["failure_primary"] == "CTX_TRUNC"]
    for q in ctx_trunc:
        overflow = q['context_tokens'] - q['context_budget']
        print(f"  {q['qid']:12s} {q['kind']:20s} {q['document']:30s} ctx={q['context_tokens']}/{q['context_budget']} overflow={overflow} answer='{q['answer'][:40]}'")

    # ===================================================================
    # 7. CONFIDENCE ANALYSIS
    # ===================================================================
    print("\n" + "=" * 78)
    print("7. CONFIDENCE ANALYSIS")
    print("=" * 78)

    correct_confs = [q["qa_confidence"] for q in correct]
    qa_ext_confs = [q["qa_confidence"] for q in failures if q["failure_primary"] == "QA_EXTRACT"]
    ret_confs = [q["qa_confidence"] for q in failures if q["failure_primary"] == "RET_MISS"]
    evid_confs = [q["qa_confidence"] for q in failures if q["failure_primary"] == "EVID_OMIT"]
    trunc_confs = [q["qa_confidence"] for q in failures if q["failure_primary"] == "CTX_TRUNC"]

    print(f"  Correct (n={len(correct_confs)}):      mean={mean(correct_confs):.4f} min={min(correct_confs):.4f} max={max(correct_confs):.4f}")
    print(f"  QA_EXTRACT (n={len(qa_ext_confs)}):  mean={mean(qa_ext_confs):.4f} min={min(qa_ext_confs):.4f} max={max(qa_ext_confs):.4f}")
    print(f"  RET_MISS (n={len(ret_confs)}):     mean={mean(ret_confs):.4f} min={min(ret_confs):.4f} max={max(ret_confs):.4f}")
    print(f"  EVID_OMIT (n={len(evid_confs)}):   mean={mean(evid_confs):.4f} min={min(evid_confs):.4f} max={max(evid_confs):.4f}")
    print(f"  CTX_TRUNC (n={len(trunc_confs)}):   mean={mean(trunc_confs):.4f} min={min(trunc_confs):.4f} max={max(trunc_confs):.4f}")

    # Overlap analysis
    correct_range = (min(correct_confs), max(correct_confs)) if correct_confs else (0, 0)
    incorrect_all = qa_ext_confs + ret_confs + evid_confs + trunc_confs
    incorrect_range = (min(incorrect_all), max(incorrect_all)) if incorrect_all else (0, 0)

    overlap_low = max(correct_range[0], incorrect_range[0])
    overlap_high = min(correct_range[1], incorrect_range[1])
    has_overlap = overlap_low <= overlap_high

    print(f"\n  Correct range:     [{correct_range[0]:.4f}, {correct_range[1]:.4f}]")
    print(f"  Incorrect range:   [{incorrect_range[0]:.4f}, {incorrect_range[1]:.4f}]")
    print(f"  Overlap:           {'YES' if has_overlap else 'NO'} [{overlap_low:.4f}, {overlap_high:.4f}]" if has_overlap else "  Overlap:           NONE")

    results["confidence_analysis"] = {
        "correct": {"n": len(correct_confs), "mean": round(mean(correct_confs), 4) if correct_confs else 0, "min": min(correct_confs) if correct_confs else 0, "max": max(correct_confs) if correct_confs else 0},
        "qa_extract": {"n": len(qa_ext_confs), "mean": round(mean(qa_ext_confs), 4) if qa_ext_confs else 0, "min": min(qa_ext_confs) if qa_ext_confs else 0, "max": max(qa_ext_confs) if qa_ext_confs else 0},
        "ret_miss": {"n": len(ret_confs), "mean": round(mean(ret_confs), 4) if ret_confs else 0, "min": min(ret_confs) if ret_confs else 0, "max": max(ret_confs) if ret_confs else 0},
        "evid_omit": {"n": len(evid_confs), "mean": round(mean(evid_confs), 4) if evid_confs else 0, "min": min(evid_confs) if evid_confs else 0, "max": max(evid_confs) if evid_confs else 0},
        "ctx_trunc": {"n": len(trunc_confs), "mean": round(mean(trunc_confs), 4) if trunc_confs else 0, "min": min(trunc_confs) if trunc_confs else 0, "max": max(trunc_confs) if trunc_confs else 0},
        "overlap": has_overlap,
    }

    # ===================================================================
    # 8. EXTRACTIVE ARCHITECTURE LIMITATION TEST
    # ===================================================================
    print("\n" + "=" * 78)
    print("8. EXTRACTIVE ARCHITECTURE ANALYSIS")
    print("=" * 78)

    # Categorize correct answers by span type
    single_span = [q for q in correct if q["answer_token_f1"] > 0.9]
    partial_span = [q for q in correct if 0.3 < q["answer_token_f1"] <= 0.9]
    print(f"  Correct answers with F1>0.9 (clean span): {len(single_span)}")
    print(f"  Correct answers with 0.3<F1<=0.9 (partial): {len(partial_span)}")

    # QA_EXTRACT failures: how many have F1 > 0.5 (close but wrong)?
    close_misses = [q for q in qa_ext_confs for q in failures if q["failure_primary"] == "QA_EXTRACT" and q["answer_token_f1"] > 0.5]
    print(f"  QA_EXTRACT failures with F1>0.5 (close misses): {len(close_misses)}")

    # ===================================================================
    # 9. SAVE RESULTS
    # ===================================================================
    # Save machine-readable results
    out = Path("phase4c_failure_matrix.json")
    out.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\n  Wrote {out}")

    print("\n" + "=" * 78)
    print("PHASE 4C DIAGNOSTICS COMPLETE")
    print("=" * 78)


if __name__ == "__main__":
    main()
