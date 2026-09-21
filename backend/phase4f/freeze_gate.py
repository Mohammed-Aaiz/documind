"""Phase 4F.3-R — Final QA Dataset Freeze & GPU Package Validation.

Creates immutable v3.1 dataset, validates all quality gates,
audits scripts, and produces the final GPU execution package.

NO TRAINING. NO PRODUCTION CHANGES.

Usage::

    cd backend
    venv/Scripts/python.exe -m phase4f.freeze_gate
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import random
import re
import shutil
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
RANDOM_SEED = 42
AUDIT_SAMPLE_SIZE = 150
NEAR_DUP_THRESHOLD = 0.85

DATASET_DIR = Path(__file__).parent / "dataset"
EXPERIMENTS_DIR = Path(__file__).parent / "experiments"
FINAL_PKG_DIR = EXPERIMENTS_DIR / "final_gpu_package"

V3_JSONL = DATASET_DIR / "training_data_v3.jsonl"
V3_1_JSONL = DATASET_DIR / "training_data_v3_1.jsonl"
V3_1_REPORT = DATASET_DIR / "dataset_quality_report_v3_1.json"
V3_1_MANIFEST = DATASET_DIR / "dataset_manifest_v3_1.json"
FINAL_REPORT = Path(__file__).parent / "phase4f_3r_freeze_report.txt"

PROD_MODEL_DIR = Path(__file__).parent.parent / "models" / "documind-qa"

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------
@dataclass
class QAExample:
    example_id: str
    source: str
    document_id: str
    question: str
    context: str
    answer: str
    answer_start: int
    answer_end: int
    question_kind: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _find_span(text: str, answer: str) -> tuple[int, int]:
    if not answer:
        return 0, 0
    idx = text.find(answer)
    if idx >= 0:
        return idx, idx + len(answer)
    idx = text.lower().find(answer.lower())
    if idx >= 0:
        return idx, idx + len(answer)
    return -1, -1


def _sha256_full(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_short(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def safe_print(text: str):
    """Print with Unicode safety."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'replace').decode('ascii'))


def _dir_hash(directory: str) -> str:
    hasher = hashlib.sha256()
    for root, dirs, files in os.walk(directory):
        for fn in sorted(files):
            fp = os.path.join(root, fn)
            with open(fp, "rb") as f:
                hasher.update(f.read())
    return hasher.hexdigest()


# ---------------------------------------------------------------------------
# Load/Save
# ---------------------------------------------------------------------------
def load_jsonl(path: Path) -> list[QAExample]:
    examples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                examples.append(QAExample(**data))
    return examples


def save_jsonl(examples: list[QAExample], path: Path):
    with open(path, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex.to_dict(), ensure_ascii=False) + "\n")


def save_json(data: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 1. Create v3.1 dataset
# ---------------------------------------------------------------------------
def create_v3_1(examples: list[QAExample]) -> tuple[list[QAExample], dict]:
    """Create v3.1 by copying v3 (repaired) dataset."""
    # v3.1 is identical to the current repaired v3
    v3_1 = [QAExample(**ex.to_dict()) for ex in examples]

    # Record the 12 repaired example IDs (from Phase 4F.3)
    repaired_ids = [
        "tc_20399d46", "tc_00f97d46", "tc_c2c51b89", "tc_4e522e45",
        "tc_3b383990", "tr_fc34fb8b", "li_89834a97", "li_7216dc7b",
        "li_ce7dfc4b", "li_8bc7889f", "li_4fa4a839", "li_8770780b",
    ]

    provenance = {
        "parent_version": "phase4f-qa-v3",
        "parent_hash": "ff293619e1a7b051",
        "child_version": "phase4f-qa-v3.1",
        "repaired_examples": len(repaired_ids),
        "repaired_ids": repaired_ids,
        "repair_reason": "Answer-span mismatches fixed (12 examples where context[start:end] did not match answer)",
        "total_examples": len(v3_1),
    }

    return v3_1, provenance


# ---------------------------------------------------------------------------
# 2. Full Structural Validation
# ---------------------------------------------------------------------------
def structural_validation(examples: list[QAExample]) -> dict:
    """Full structural validation over ALL examples."""
    issues = []
    valid_kinds = {"DIRECT_SPAN", "ENTITY", "DATE", "NUMERIC", "TABLE_CELL",
                   "TABLE_ROW", "LIST_ITEM", "SECTION_SPECIFIC", "LONG_CONTEXT",
                   "MULTI_CHUNK", "UNANSWERABLE"}

    for ex in examples:
        ex_issues = []

        # Valid JSON (already parsed, so this passes)
        # Required fields
        required = ["example_id", "source", "document_id", "question", "context",
                    "answer", "answer_start", "answer_end", "question_kind"]
        for field_name in required:
            if not hasattr(ex, field_name) or getattr(ex, field_name) is None:
                ex_issues.append(f"missing_field: {field_name}")

        # Valid category
        if ex.question_kind not in valid_kinds:
            ex_issues.append(f"invalid_category: {ex.question_kind}")

        # Valid document ID
        if not ex.document_id or not ex.document_id.strip():
            ex_issues.append("empty_document_id")

        # Question
        if not ex.question or not ex.question.strip():
            ex_issues.append("empty_question")
        elif not ex.question.rstrip().endswith("?"):
            ex_issues.append("question_no_question_mark")
        elif len(ex.question.split()) < 3:
            ex_issues.append("question_too_short")

        # Context
        if not ex.context or not ex.context.strip():
            ex_issues.append("empty_context")
        elif len(ex.context.strip()) < 20 and ex.question_kind != "UNANSWERABLE":
            ex_issues.append("context_too_short")

        # Answer (for answerable)
        if ex.question_kind != "UNANSWERABLE":
            if not ex.answer or not ex.answer.strip():
                ex_issues.append("empty_answer")
            elif ex.answer_start < 0:
                ex_issues.append("negative_start_offset")
            elif ex.answer_end > len(ex.context):
                ex_issues.append("end_offset_out_of_bounds")
            elif ex.answer_start >= ex.answer_end:
                ex_issues.append("start_ge_end")
            else:
                extracted = ex.context[ex.answer_start:ex.answer_end]
                if extracted != ex.answer:
                    if extracted.lower() != ex.answer.lower():
                        ex_issues.append(f"span_mismatch: extracted='{extracted}' answer='{ex.answer}'")

        # Unanswerable
        if ex.question_kind == "UNANSWERABLE":
            if ex.answer:
                ex_issues.append("unanswerable_has_answer")

        # Invalid Unicode check
        try:
            ex.question.encode("utf-8")
            ex.context.encode("utf-8")
            ex.answer.encode("utf-8")
        except UnicodeEncodeError:
            ex_issues.append("invalid_unicode")

        # Metadata check
        if not isinstance(ex.metadata, dict):
            ex_issues.append("invalid_metadata_type")

        if ex_issues:
            issues.append({"example_id": ex.example_id, "issues": ex_issues})

    return {
        "total": len(examples),
        "valid": len(examples) - len(issues),
        "invalid": len(issues),
        "issues": issues,
        "status": "PASS" if len(issues) == 0 else "FAIL",
    }


# ---------------------------------------------------------------------------
# 3. Semantic Quality Gate
# ---------------------------------------------------------------------------
def semantic_audit(examples: list[QAExample], sample_size: int, rng: random.Random) -> dict:
    """Stratified semantic audit."""
    by_kind = defaultdict(list)
    for ex in examples:
        by_kind[ex.question_kind].append(ex)

    sampled = []
    per_kind = max(1, sample_size // len(by_kind))
    for kind, kind_examples in by_kind.items():
        n = min(per_kind, len(kind_examples))
        sampled.extend(rng.sample(kind_examples, n))

    remaining = [ex for ex in examples if ex not in sampled]
    if len(sampled) < sample_size and remaining:
        extra = min(sample_size - len(sampled), len(remaining))
        sampled.extend(rng.sample(remaining, extra))

    failures = []
    for ex in sampled:
        issues = []
        q = ex.question.strip()

        if len(q.split()) < 4:
            issues.append("question_too_short")
        if not q.endswith("?"):
            issues.append("question_no_question_mark")
        if len(ex.context.strip()) < 20:
            issues.append("context_too_short")
        if ex.question_kind != "UNANSWERABLE" and not ex.answer:
            issues.append("answer_empty")
        if q and q[0].islower():
            issues.append("question_lowercase_start")

        if ex.question_kind != "UNANSWERABLE":
            if ex.answer_start < 0 or ex.answer_end > len(ex.context):
                issues.append("invalid_span")
            elif ex.context[ex.answer_start:ex.answer_end].lower() != ex.answer.lower():
                issues.append("span_mismatch")

        if ex.question_kind == "UNANSWERABLE" and ex.answer:
            issues.append("unanswerable_has_answer")

        if issues:
            failures.append({
                "example_id": ex.example_id,
                "question_kind": ex.question_kind,
                "issues": issues,
            })

    return {
        "sample_size": len(sampled),
        "failures": failures,
        "pass_rate": round((len(sampled) - len(failures)) / len(sampled) * 100, 1) if sampled else 0,
        "status": "PASS" if (len(sampled) - len(failures)) / max(len(sampled), 1) >= 0.95 else "FAIL",
    }


# ---------------------------------------------------------------------------
# 4. High-Risk Category Recheck
# ---------------------------------------------------------------------------
def audit_high_risk(examples: list[QAExample], repaired_ids: list[str]) -> dict:
    """Audit high-risk categories, especially the 12 repaired examples."""
    high_risk = ["TABLE_ROW", "TABLE_CELL", "LIST_ITEM", "MULTI_CHUNK",
                 "LONG_CONTEXT", "UNANSWERABLE", "DIRECT_SPAN"]

    results = {}
    for kind in high_risk:
        kind_examples = [ex for ex in examples if ex.question_kind == kind]
        issues = []
        for ex in kind_examples:
            ex_issues = []
            if kind == "UNANSWERABLE":
                if ex.answer:
                    ex_issues.append("unanswerable_has_answer")
            else:
                if ex.answer and ex.answer_start >= 0 and ex.answer_end <= len(ex.context):
                    extracted = ex.context[ex.answer_start:ex.answer_end]
                    if extracted.lower() != ex.answer.lower():
                        ex_issues.append("answer_not_in_context")
            if ex_issues:
                issues.append({"example_id": ex.example_id, "issues": ex_issues})

        results[kind] = {
            "total": len(kind_examples),
            "issues": len(issues),
            "pass_rate": round((len(kind_examples) - len(issues)) / max(len(kind_examples), 1) * 100, 1),
        }

    # Check repaired examples specifically
    repaired_results = []
    for ex in examples:
        if ex.example_id in repaired_ids:
            ex_issues = []
            if ex.question_kind != "UNANSWERABLE":
                if not ex.question.endswith("?"):
                    ex_issues.append("question_no_question_mark")
                if not ex.answer:
                    ex_issues.append("empty_answer")
                elif ex.answer_start >= 0 and ex.answer_end <= len(ex.context):
                    extracted = ex.context[ex.answer_start:ex.answer_end]
                    if extracted.lower() != ex.answer.lower():
                        ex_issues.append("span_still_mismatched")
            repaired_results.append({
                "example_id": ex.example_id,
                "category": ex.question_kind,
                "issues": ex_issues,
                "status": "PASS" if not ex_issues else "FAIL",
            })

    return {"categories": results, "repaired_examples": repaired_results}


# ---------------------------------------------------------------------------
# 5. Dataset Distribution
# ---------------------------------------------------------------------------
def distribution_report(examples: list[QAExample]) -> dict:
    total = len(examples)
    by_kind = Counter(ex.question_kind for ex in examples)
    by_doc = Counter(ex.document_id for ex in examples)

    # Question diversity per category
    q_diversity = {}
    for kind in by_kind:
        kind_examples = [ex for ex in examples if ex.question_kind == kind]
        templates = set()
        for ex in kind_examples:
            words = ex.question.split()[:5]
            templates.add(" ".join(words).lower())
        q_diversity[kind] = len(templates)

    # Answer diversity per category
    a_diversity = {}
    for kind in by_kind:
        kind_examples = [ex for ex in examples if ex.question_kind == kind]
        ans_lengths = [len(ex.answer) for ex in kind_examples if ex.answer]
        a_diversity[kind] = {
            "mean_length": round(sum(ans_lengths) / max(len(ans_lengths), 1), 1),
            "unique_answers": len(set(ex.answer for ex in kind_examples if ex.answer)),
        }

    return {
        "total": total,
        "by_kind": dict(by_kind.most_common()),
        "by_kind_pct": {k: round(v / total * 100, 1) for k, v in by_kind.items()},
        "source_documents": len(by_doc),
        "question_diversity": q_diversity,
        "answer_diversity": a_diversity,
    }


# ---------------------------------------------------------------------------
# 6. Duplicate / Leakage Recheck
# ---------------------------------------------------------------------------
def duplicate_leakage_check(examples: list[QAExample]) -> dict:
    # Exact duplicates
    q_counter = Counter(ex.question for ex in examples)
    exact_q = {q: c for q, c in q_counter.items() if c > 1}

    ctx_counter = Counter(ex.context for ex in examples)
    exact_ctx = {c: n for c, n in ctx_counter.items() if n > 1}

    qc_counter = Counter((ex.question, ex.context) for ex in examples)
    exact_qc = {k: v for k, v in qc_counter.items() if v > 1}

    qa_counter = Counter((ex.question, ex.answer) for ex in examples)
    exact_qa = {k: v for k, v in qa_counter.items() if v > 1}

    # Near-duplicates
    questions = list(set(ex.question for ex in examples))
    near_dupes = []
    for i in range(len(questions)):
        for j in range(i + 1, min(i + 100, len(questions))):
            ratio = SequenceMatcher(None, questions[i].lower(), questions[j].lower()).ratio()
            if NEAR_DUP_THRESHOLD <= ratio < 1.0:
                near_dupes.append({"q1": questions[i], "q2": questions[j], "sim": round(ratio, 3)})

    # Cross-split check
    report_path = DATASET_DIR / "dataset_quality_report.json"
    splits = {}
    if report_path.exists():
        with open(report_path) as f:
            splits = json.load(f).get("splits", {})

    train_ids = set(splits.get("train", {}).get("doc_ids", []))
    val_ids = set(splits.get("validation", {}).get("doc_ids", []))
    test_ids = set(splits.get("internal_test", {}).get("doc_ids", []))

    cross_split = []
    for nd in near_dupes:
        q1_exs = [ex for ex in examples if ex.question == nd["q1"]]
        q2_exs = [ex for ex in examples if ex.question == nd["q2"]]
        if q1_exs and q2_exs:
            doc1 = q1_exs[0].document_id
            doc2 = q2_exs[0].document_id
            split1 = "train" if doc1 in train_ids else "val" if doc1 in val_ids else "test"
            split2 = "train" if doc2 in train_ids else "val" if doc2 in val_ids else "test"
            if split1 != split2:
                cross_split.append({"q1": nd["q1"][:50], "q2": nd["q2"][:50],
                                   "split1": split1, "split2": split2})

    # External isolation
    eval_phrases = set()
    eval_paths = [
        Path(__file__).parent.parent / "phase3f_validation_report.txt",
        Path(__file__).parent.parent / "phase4b_evaluation_report.json",
        Path(__file__).parent.parent / "phase4c_failure_matrix.json",
        Path(__file__).parent.parent / "phase4d_experiment_results.json",
        Path(__file__).parent.parent / "phase4e_diagnostic_results.json",
    ]
    for path in eval_paths:
        if path.exists():
            try:
                text = path.read_text(encoding="utf-8")
                for line in text.split("\n"):
                    if len(line.strip()) > 30:
                        eval_phrases.add(line.strip().lower())
            except Exception:
                pass

    q_overlap = 0
    ctx_overlap = 0
    for ex in examples:
        for phrase in eval_phrases:
            if ex.question.lower() in phrase or phrase in ex.question.lower():
                q_overlap += 1
                break
            if ex.context.lower() in phrase or phrase in ex.context.lower():
                ctx_overlap += 1
                break

    return {
        "exact_question_dupes": len(exact_q),
        "exact_context_dupes": len(exact_ctx),
        "exact_qc_dupes": len(exact_qc),
        "exact_qa_dupes": len(exact_qa),
        "near_duplicate_pairs": len(near_dupes),
        "cross_split_leakage": len(cross_split),
        "cross_split_details": cross_split[:5],
        "external_isolation": "PASS" if (q_overlap == 0 and ctx_overlap == 0) else "FAIL",
        "external_q_overlap": q_overlap,
        "external_ctx_overlap": ctx_overlap,
    }


# ---------------------------------------------------------------------------
# 9. Training Script Audit
# ---------------------------------------------------------------------------
def audit_training_script() -> dict:
    script_path = EXPERIMENTS_DIR / "train.py"
    if not script_path.exists():
        return {"status": "NOT_FOUND", "issues": ["train.py not found"]}

    content = script_path.read_text(encoding="utf-8")
    checks = {
        "uses_distilbert": "distilbert-base-cased" in content,
        "uses_bert_base": "bert-base-cased" in content,
        "uses_deberta_v3": "deberta-v3" in content,
        "correct_lr_a1": "3e-5" in content or "3e5" in content,
        "correct_lr_a2": "2e-5" in content or "2e5" in content,
        "correct_lr_a3": "1e-5" in content or "1e5" in content,
        "effective_batch_64": "64" in content,
        "three_epochs": "\"epochs\": 3" in content or "epochs=3" in content,
        "max_length_384": "384" in content,
        "reproducible_seed": "seed" in content and "42" in content,
        "no_production_path": "backend/models/documind-qa" not in content,
        "no_hidden_llm": "openai" not in content.lower() and "anthropic" not in content.lower(),
        "dataset_loads_jsonl": "training_data_v3" in content or "jsonl" in content,
    }

    issues = [k for k, v in checks.items() if not v]
    return {
        "status": "PASS" if not issues else "ISSUES_FOUND",
        "checks": checks,
        "issues": issues,
    }


# ---------------------------------------------------------------------------
# 10. Evaluation Script Audit
# ---------------------------------------------------------------------------
def audit_evaluation_script() -> dict:
    script_path = EXPERIMENTS_DIR / "evaluate.py"
    if not script_path.exists():
        return {"status": "NOT_FOUND", "issues": ["evaluate.py not found"]}

    content = script_path.read_text(encoding="utf-8")
    checks = {
        "exact_match": "exact_match" in content or "compute_match" in content,
        "token_f1": "f1" in content.lower(),
        "answerability": "answerability" in content,
        "abstention": "abstention" in content,
        "spurious_rate": "spurious" in content,
        "category_metrics": "category" in content.lower(),
        "failure_taxonomy": "FAILURE_TYPES" in content or "failure_taxonomy" in content,
        "confidence": "confidence" in content,
    }

    # Check for NOT_IMPLEMENTED claims
    not_impl = []
    for metric in ["Phase 4B", "Phase 4E", "ECE", "Brier"]:
        if metric.lower() not in content.lower():
            not_impl.append(metric)

    issues = [k for k, v in checks.items() if not v]
    return {
        "status": "PASS" if not issues else "ISSUES_FOUND",
        "checks": checks,
        "issues": issues,
        "not_implemented": not_impl,
    }


# ---------------------------------------------------------------------------
# 11. Production Model Safety
# ---------------------------------------------------------------------------
def verify_production_safety() -> dict:
    result = {"model_dir": str(PROD_MODEL_DIR), "exists": PROD_MODEL_DIR.exists()}

    if PROD_MODEL_DIR.exists():
        # Full SHA-256
        full_hash = _dir_hash(str(PROD_MODEL_DIR))
        result["full_sha256"] = full_hash
        result["short_hash"] = full_hash[:16]

        # File listing
        files = []
        for fn in sorted(os.listdir(PROD_MODEL_DIR)):
            fp = PROD_MODEL_DIR / fn
            if fp.is_file():
                sz = fp.stat().st_size
                h = hashlib.md5(fp.read_bytes()).hexdigest()
                files.append({"name": fn, "size": sz, "md5": h})
        result["files"] = files
    else:
        result["full_sha256"] = "NOT_FOUND"
        result["short_hash"] = "NOT_FOUND"

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("PHASE 4F.3-R — Final Dataset Freeze & GPU Package")
    print("=" * 60)

    rng = random.Random(RANDOM_SEED)
    all_checks_pass = True

    # 1. Create v3.1
    print("\n[1/10] Creating v3.1 dataset...")
    v3_examples = load_jsonl(V3_JSONL)
    v3_1, provenance = create_v3_1(v3_examples)
    save_jsonl(v3_1, V3_1_JSONL)
    print(f"  v3.1: {len(v3_1)} examples")

    # 2. Full structural validation
    print("\n[2/10] Full structural validation...")
    struct = structural_validation(v3_1)
    print(f"  {struct['status']}: {struct['valid']}/{struct['total']} valid")
    if struct["issues"]:
        all_checks_pass = False
        for issue in struct["issues"][:5]:
            safe_print(f"    {issue['example_id']}: {', '.join(issue['issues'])}")

    # 3. Semantic audit
    print("\n[3/10] Semantic quality gate...")
    semantic = semantic_audit(v3_1, AUDIT_SAMPLE_SIZE, rng)
    print(f"  {semantic['status']}: {semantic['pass_rate']}% ({semantic['sample_size']} sampled)")
    if semantic["failures"]:
        all_checks_pass = False
        for fail in semantic["failures"][:5]:
            print(f"    {fail['example_id']}: {', '.join(fail['issues'])}")

    # 4. High-risk recheck
    print("\n[4/10] High-risk category recheck...")
    hr = audit_high_risk(v3_1, provenance["repaired_ids"])
    for kind, info in hr["categories"].items():
        status = "OK" if info["pass_rate"] >= 95 else "FAIL"
        print(f"  {kind}: {info['pass_rate']}% {status}")
    repaired_pass = sum(1 for r in hr["repaired_examples"] if r["status"] == "PASS")
    print(f"  Repaired examples: {repaired_pass}/{len(hr['repaired_examples'])} PASS")

    # 5. Distribution
    print("\n[5/10] Dataset distribution...")
    dist = distribution_report(v3_1)
    for kind, count in sorted(dist["by_kind"].items(), key=lambda x: -x[1]):
        print(f"  {kind}: {count} ({dist['by_kind_pct'][kind]}%)")

    # 6. Duplicate/leakage
    print("\n[6/10] Duplicate/leakage recheck...")
    dup = duplicate_leakage_check(v3_1)
    print(f"  Exact Q+C dupes: {dup['exact_qc_dupes']}")
    print(f"  Near-dupes: {dup['near_duplicate_pairs']}")
    print(f"  Cross-split leakage: {dup['cross_split_leakage']}")
    print(f"  External isolation: {dup['external_isolation']}")
    if dup["external_isolation"] != "PASS":
        all_checks_pass = False

    # 7. Compute hash
    print("\n[7/10] Computing canonical hash...")
    jsonl_bytes = V3_1_JSONL.read_bytes()
    full_hash = _sha256_full(jsonl_bytes)
    short_hash = _sha256_short(jsonl_bytes)
    file_size = len(jsonl_bytes)
    print(f"  Full SHA-256: {full_hash}")
    print(f"  Short: {short_hash}")
    print(f"  Size: {file_size} bytes")

    # 8. Script audits
    print("\n[8/10] Auditing scripts...")
    train_audit = audit_training_script()
    eval_audit = audit_evaluation_script()
    print(f"  train.py: {train_audit['status']}")
    print(f"  evaluate.py: {eval_audit['status']}")
    if eval_audit.get("not_implemented"):
        print(f"  Not implemented in eval: {eval_audit['not_implemented']}")

    # 9. Production safety
    print("\n[9/10] Production model safety...")
    prod = verify_production_safety()
    print(f"  Model exists: {prod['exists']}")
    print(f"  SHA-256: {prod.get('full_sha256', 'N/A')[:32]}...")

    # 10. Create final GPU package
    print("\n[10/10] Creating final GPU package...")
    pkg_dir = FINAL_PKG_DIR

    # Dataset
    (pkg_dir / "dataset").mkdir(parents=True, exist_ok=True)
    shutil.copy2(V3_1_JSONL, pkg_dir / "dataset" / "training_data_v3_1.jsonl")

    # Training
    (pkg_dir / "training").mkdir(parents=True, exist_ok=True)
    shutil.copy2(EXPERIMENTS_DIR / "train.py", pkg_dir / "training" / "train.py")

    # Evaluation
    (pkg_dir / "evaluation").mkdir(parents=True, exist_ok=True)
    shutil.copy2(EXPERIMENTS_DIR / "evaluate.py", pkg_dir / "evaluation" / "evaluate.py")

    # Requirements
    shutil.copy2(EXPERIMENTS_DIR / "requirements.txt", pkg_dir / "requirements.txt")

    # Checksums
    (pkg_dir / "dataset_checksum.txt").write_text(
        f"Full SHA-256: {full_hash}\nShort: {short_hash}\nExamples: {len(v3_1)}\n")
    (pkg_dir / "production_model_checksum.txt").write_text(
        f"Full SHA-256: {prod.get('full_sha256', 'N/A')}\nShort: {prod.get('short_hash', 'N/A')}\n")

    # README
    (pkg_dir / "README_GPU_EXECUTION.md").write_text(f"""# GPU Execution Package — Phase 4F.3

## Dataset
- Version: phase4f-qa-v3.1
- Examples: {len(v3_1)}
- SHA-256: {full_hash}

## Status
- **LOCAL GPU:** BLOCKED
- **EXTERNAL GPU:** REQUIRED
- **NO PRODUCTION MODEL REPLACEMENT:** YES

## Commands

```bash
pip install -r requirements.txt

# A1: DistilBERT
python training/train.py --experiment a1 --data_dir dataset --output_dir a1_distilbert

# A2: BERT-base
python training/train.py --experiment a2 --data_dir dataset --output_dir a2_bert_base

# A3: DeBERTa-v3
python training/train.py --experiment a3 --data_dir dataset --output_dir a3_deberta_v3

# Evaluate
python evaluation/evaluate.py --model_dir a1_distilbert --data_dir dataset
```

## Verify Before Training
```bash
python -c "import hashlib,json; d=json.load(open('dataset/training_data_v3_1.jsonl')); h=hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()[:16]; print(f'Hash: {{h}}'); assert h=='{short_hash}', 'HASH MISMATCH'"
```
""")

    # Expected output structure
    (pkg_dir / "expected_output_structure.txt").write_text("""Expected Output Structure:
final_gpu_package/
├── dataset/
│   ├── training_data_v3_1.jsonl
│   └── dataset_manifest_v3_1.json
├── training/
│   └── train.py
├── evaluation/
│   └── evaluate.py
├── requirements.txt
├── README_GPU_EXECUTION.md
├── production_model_checksum.txt
├── dataset_checksum.txt
├── expected_output_structure.txt
├── final_gpu_package_manifest.json
├── a1_distilbert/
│   ├── config.json
│   ├── model.safetensors
│   ├── tokenizer.json
│   └── training_metadata.json
├── a2_bert_base/
│   └── ...
└── a3_deberta_v3/
    └── ...
""")

    # Experiment config
    (pkg_dir / "training" / "experiment_config.json").write_text(json.dumps({
        "a1": {"model": "distilbert-base-cased", "lr": 3e-5, "batch": 16, "grad_acc": 4, "eff_batch": 64, "epochs": 3, "max_length": 384, "seed": 42},
        "a2": {"model": "bert-base-cased", "lr": 2e-5, "batch": 8, "grad_acc": 8, "eff_batch": 64, "epochs": 3, "max_length": 384, "seed": 42},
        "a3": {"model": "microsoft/deberta-v3-base", "lr": 1e-5, "batch": 8, "grad_acc": 8, "eff_batch": 64, "epochs": 3, "max_length": 384, "seed": 42},
    }, indent=2))

    # Manifest
    manifest = {
        "dataset_version": "phase4f-qa-v3.1",
        "dataset_full_sha256": full_hash,
        "dataset_short_hash": short_hash,
        "dataset_examples": len(v3_1),
        "dataset_file_size": file_size,
        "document_count": dist["source_documents"],
        "category_counts": dist["by_kind"],
        "production_model_full_checksum": prod.get("full_sha256", "N/A"),
        "production_model_short_checksum": prod.get("short_hash", "N/A"),
        "experiments": {
            "a1_distilbert": {"model": "distilbert-base-cased", "status": "PENDING_GPU"},
            "a2_bert_base": {"model": "bert-base-cased", "status": "PENDING_GPU"},
            "a3_deberta_v3": {"model": "microsoft/deberta-v3-base", "status": "PENDING_GPU"},
        },
        "software_requirements": "requirements.txt",
        "creation_timestamp": datetime.now(timezone.utc).isoformat(),
        "provenance": provenance,
    }
    save_json(manifest, pkg_dir / "final_gpu_package_manifest.json")

    # Also save v3.1 manifest and report in dataset dir
    save_json(provenance, V3_1_MANIFEST)
    quality_report = {
        "phase": "4F.3-R",
        "dataset_version": "phase4f-qa-v3.1",
        "dataset_hash_full": full_hash,
        "dataset_hash_short": short_hash,
        "total_examples": len(v3_1),
        "structural_validation": struct,
        "semantic_audit": semantic,
        "high_risk_audit": hr,
        "distribution": dist,
        "duplicate_leakage": dup,
        "training_script_audit": train_audit,
        "evaluation_script_audit": eval_audit,
        "production_safety": {k: v for k, v in prod.items() if k != "files"},
        "provenance": provenance,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    save_json(quality_report, V3_1_REPORT)

    print(f"  Package created: {pkg_dir}")

    # Generate final report
    report = []
    report.append("=" * 70)
    report.append("PHASE 4F.3-R — FREEZE REPORT")
    report.append("=" * 70)
    report.append("")
    report.append(f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    report.append(f"Dataset: phase4f-qa-v3.1")
    report.append(f"Hash: {full_hash}")
    report.append(f"Examples: {len(v3_1)}")
    report.append("")

    report.append("1. Structural Validation")
    report.append("-" * 40)
    report.append(f"  Status: {struct['status']}")
    report.append(f"  Valid: {struct['valid']}/{struct['total']}")
    report.append("")

    report.append("2. Semantic Audit")
    report.append("-" * 40)
    report.append(f"  Status: {semantic['status']}")
    report.append(f"  Pass rate: {semantic['pass_rate']}%")
    report.append("")

    report.append("3. High-Risk Categories")
    report.append("-" * 40)
    for kind, info in hr["categories"].items():
        report.append(f"  {kind}: {info['pass_rate']}% ({info['issues']} issues)")
    report.append(f"  Repaired: {repaired_pass}/{len(hr['repaired_examples'])} PASS")
    report.append("")

    report.append("4. Distribution")
    report.append("-" * 40)
    for kind, count in sorted(dist["by_kind"].items(), key=lambda x: -x[1]):
        report.append(f"  {kind}: {count} ({dist['by_kind_pct'][kind]}%)")
    report.append("")

    report.append("5. Duplicate/Leakage")
    report.append("-" * 40)
    report.append(f"  External isolation: {dup['external_isolation']}")
    report.append(f"  Cross-split leakage: {dup['cross_split_leakage']}")
    report.append("")

    report.append("6. Script Audits")
    report.append("-" * 40)
    report.append(f"  train.py: {train_audit['status']}")
    report.append(f"  evaluate.py: {eval_audit['status']}")
    report.append("")

    report.append("7. Production Safety")
    report.append("-" * 40)
    report.append(f"  Checksum: {prod.get('short_hash', 'N/A')}")
    report.append("")

    report.append("8. GPU Package")
    report.append("-" * 40)
    report.append(f"  Location: {pkg_dir}")
    report.append(f"  Dataset hash: {short_hash}")
    report.append("")

    report.append("=" * 70)
    if all_checks_pass:
        report.append("PHASE 4F.3-R — GPU PACKAGE FROZEN")
    else:
        report.append("PHASE 4F.3-R — NOT FROZEN")
        report.append("Blocking issues found.")
    report.append("=" * 70)

    with open(FINAL_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print(f"\n  Report: {FINAL_REPORT}")

    # Print summary
    print("\n" + "=" * 60)
    if all_checks_pass:
        print("PHASE 4F.3-R — GPU PACKAGE FROZEN")
    else:
        print("PHASE 4F.3-R — NOT FROZEN")
    print("=" * 60)
    print(f"  Dataset: phase4f-qa-v3.1 ({len(v3_1)} examples)")
    print(f"  Hash: {full_hash}")
    print(f"  Package: {pkg_dir}")


if __name__ == "__main__":
    main()
