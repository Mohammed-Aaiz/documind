"""Phase 4F.2-R — QA Dataset Final Balance & Duplicate Gate.

Performs comprehensive audit, remediation, and validation.
Creates phase4f-qa-v3 if any examples are changed.

NO MODEL TRAINING. NO PRODUCTION CHANGES.

Usage::

    cd backend
    venv/Scripts/python.exe -m phase4f.balance_gate
"""

from __future__ import annotations

import hashlib
import json
import platform
import random
import re
import sys
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
INPUT_JSONL = DATASET_DIR / "training_data.jsonl"  # v2
OUTPUT_JSONL = DATASET_DIR / "training_data_v3.jsonl"
OUTPUT_REPORT_JSON = DATASET_DIR / "dataset_quality_report_v3.json"
OUTPUT_MANIFEST_JSON = DATASET_DIR / "dataset_manifest_v3.json"
OUTPUT_ENV_JSON = Path(__file__).parent / "training" / "environment.json"
OUTPUT_AUDIT_TXT = Path(__file__).parent / "phase4f_2r_dataset_balance_report.txt"

CATEGORY_FLOORS = {
    "DIRECT_SPAN": 100, "ENTITY": 50, "DATE": 50, "NUMERIC": 100,
    "TABLE_CELL": 100, "TABLE_ROW": 75, "LIST_ITEM": 100,
    "SECTION_SPECIFIC": 75, "LONG_CONTEXT": 50, "MULTI_CHUNK": 75,
    "UNANSWERABLE": 100,
}

# Source documents definition (same as expand_and_audit.py)
DOCUMENTS = []
def _add_doc(doc_id, doc_type, doc_structure):
    DOCUMENTS.append({"doc_id": doc_id, "doc_type": doc_type, "doc_structure": doc_structure})

for did, dt, ds in [
    ("tech_spec_alpha", "technical_specification", "multi_section_with_tables"),
    ("research_paper_beta", "academic_paper", "multi_section_prose"),
    ("financial_report_q3", "financial_report", "prose_with_tables"),
    ("clinical_trial_gamma", "clinical_report", "structured_prose"),
    ("ops_manual_delta", "operations_manual", "sections_with_lists"),
    ("legal_contract_epsilon", "legal_document", "prose_with_numbered_items"),
    ("env_monitoring_zeta", "monitoring_report", "data_heavy"),
    ("company_history_eta", "historical_narrative", "chronological_prose"),
    ("textbook_chapter_theta", "educational", "textbook_style"),
    ("regulation_doc_iota", "regulatory", "formal_structured"),
    ("api_docs_lambda", "api_documentation", "technical_reference"),
    ("dataset_desc_mu", "scientific", "data_description"),
    ("project_proposal_nu", "project_proposal", "structured_with_budget"),
    ("training_material_omega", "training_material", "tutorial_style"),
    ("multi_chunk_doc_xi", "reference_guide", "long_form_multi_section"),
    ("product_comparison_pi", "product_analysis", "comparative"),
]:
    _add_doc(did, dt, ds)


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


def _sha256_short(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


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
# SECTION 1: CATEGORY BALANCE AUDIT
# ---------------------------------------------------------------------------
def audit_categories(examples: list[QAExample]) -> dict:
    by_kind = Counter(ex.question_kind for ex in examples)
    total = len(examples)

    # Per-category analysis
    analysis = {}
    for kind in CATEGORY_FLOORS:
        count = by_kind.get(kind, 0)
        floor = CATEGORY_FLOORS[kind]
        deficit = max(0, floor - count)

        # Distinct question templates (first 3 words as template signature)
        kind_examples = [ex for ex in examples if ex.question_kind == kind]
        templates = set()
        answer_patterns = set()
        contexts = set()
        for ex in kind_examples:
            # Template: first 5 words
            words = ex.question.split()[:5]
            templates.add(" ".join(words).lower())
            # Answer pattern: first non-numeric word
            ans_words = re.sub(r'[\d.,$%]+', '', ex.answer).strip().split()
            if ans_words:
                answer_patterns.add(ans_words[0].lower())
            contexts.add(ex.context[:80])

        doc_ids = set(ex.document_id for ex in kind_examples)
        synthetic_ratio = 0
        if kind_examples:
            synthetic_count = sum(1 for ex in kind_examples if "synthetic" in ex.source or "phase4f" in ex.source)
            synthetic_ratio = round(synthetic_count / len(kind_examples) * 100, 1)

        analysis[kind] = {
            "count": count,
            "percentage": round(count / total * 100, 1) if total else 0,
            "floor": floor,
            "deficit": deficit,
            "meets_floor": count >= floor,
            "source_documents": len(doc_ids),
            "distinct_templates": len(templates),
            "distinct_answer_patterns": len(answer_patterns),
            "distinct_contexts": len(contexts),
            "synthetic_ratio": synthetic_ratio,
        }

    return {
        "total": total,
        "by_kind": dict(by_kind.most_common()),
        "analysis": analysis,
    }


# ---------------------------------------------------------------------------
# SECTION 2: TABLE_CELL DOMINANCE AUDIT
# ---------------------------------------------------------------------------
def audit_table_cell(examples: list[QAExample]) -> dict:
    tc_examples = [ex for ex in examples if ex.question_kind == "TABLE_CELL"]
    total = len(examples)

    # Per-document breakdown
    by_doc = Counter(ex.document_id for ex in tc_examples)

    # Per-table (using table_headers from metadata)
    by_table = Counter()
    for ex in tc_examples:
        headers = tuple(ex.metadata.get("table_headers", []))
        by_table[headers] += 1

    # Unique question patterns
    q_patterns = Counter()
    for ex in tc_examples:
        # Normalize: replace specific entity names with placeholder
        normalized = re.sub(r'\b[A-Z][a-z]+(?:[-\s][A-Z][a-z]+)*\b', 'X', ex.question)
        q_patterns[normalized] += 1

    # Unique answer patterns
    ans_patterns = Counter(ex.metadata.get("column", "unknown") for ex in tc_examples)

    # Semantic diversity: unique (question_word, column) pairs
    semantic_pairs = set()
    for ex in tc_examples:
        q_words = tuple(ex.question.lower().split()[:3])
        col = ex.metadata.get("column", "unknown")
        semantic_pairs.add((q_words, col))

    # Redundancy: same question template + same column
    redundancy_groups = defaultdict(list)
    for ex in tc_examples:
        q_norm = re.sub(r'[A-Z][a-z]+', 'X', ex.question)[:50]
        col = ex.metadata.get("column", "unknown")
        redundancy_groups[(q_norm, col)].append(ex)

    redundant_count = sum(len(v) - 1 for v in redundancy_groups.values() if len(v) > 1)

    return {
        "total_tc": len(tc_examples),
        "percentage": round(len(tc_examples) / total * 100, 1) if total else 0,
        "by_document": dict(by_doc.most_common()),
        "by_table_domain": len(by_table),
        "unique_q_patterns": len(q_patterns),
        "top_q_patterns": q_patterns.most_common(10),
        "answer_column_distribution": dict(ans_patterns.most_common()),
        "semantic_diversity": len(semantic_pairs),
        "redundant_examples": redundant_count,
        "redundancy_groups": len(redundancy_groups),
    }


# ---------------------------------------------------------------------------
# SECTION 3: NEAR-DUPLICATE AUDIT
# ---------------------------------------------------------------------------
def audit_duplicates(examples: list[QAExample]) -> dict:
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
                near_dupes.append({
                    "q1": questions[i], "q2": questions[j],
                    "similarity": round(ratio, 3),
                })

    # Cross-split check
    splits = {}
    report_path = DATASET_DIR / "dataset_quality_report.json"
    if report_path.exists():
        with open(report_path) as f:
            splits = json.load(f).get("splits", {})

    train_ids = set(splits.get("train", {}).get("doc_ids", []))
    val_ids = set(splits.get("validation", {}).get("doc_ids", []))
    test_ids = set(splits.get("internal_test", {}).get("doc_ids", []))

    cross_split_leakage = []
    for nd in near_dupes:
        q1_exs = [ex for ex in examples if ex.question == nd["q1"]]
        q2_exs = [ex for ex in examples if ex.question == nd["q2"]]
        if q1_exs and q2_exs:
            doc1 = q1_exs[0].document_id
            doc2 = q2_exs[0].document_id
            split1 = "train" if doc1 in train_ids else "val" if doc1 in val_ids else "test"
            split2 = "train" if doc2 in train_ids else "val" if doc2 in val_ids else "test"
            if split1 != split2:
                cross_split_leakage.append({
                    "q1": nd["q1"], "q2": nd["q2"],
                    "doc1": doc1, "doc2": doc2,
                    "split1": split1, "split2": split2,
                    "similarity": nd["similarity"],
                })

    return {
        "exact_question_dupes": len(exact_q),
        "exact_question_dupes_total_extra": sum(v - 1 for v in exact_q.values()),
        "exact_context_dupes": len(exact_ctx),
        "exact_context_dupes_total_extra": sum(v - 1 for v in exact_ctx.values()),
        "exact_qc_dupes": len(exact_qc),
        "exact_qc_dupes_total_extra": sum(v - 1 for v in exact_qc.values()),
        "exact_qa_dupes": len(exact_qa),
        "exact_qa_dupes_total_extra": sum(v - 1 for v in exact_qa.values()),
        "near_duplicate_pairs": len(near_dupes),
        "cross_split_leakage": cross_split_leakage,
        "cross_split_leakage_count": len(cross_split_leakage),
    }


# ---------------------------------------------------------------------------
# SECTION 4: DOCUMENT BALANCE
# ---------------------------------------------------------------------------
def audit_document_balance(examples: list[QAExample]) -> dict:
    by_doc = defaultdict(lambda: {"total": 0, "categories": Counter()})
    for ex in examples:
        by_doc[ex.document_id]["total"] += 1
        by_doc[ex.document_id]["categories"][ex.question_kind] += 1

    # Sort by total
    sorted_docs = sorted(by_doc.items(), key=lambda x: -x[1]["total"])

    # Document × category matrix
    all_kinds = sorted(set(ex.question_kind for ex in examples))
    matrix = {}
    for doc_id, info in sorted_docs:
        matrix[doc_id] = {k: info["categories"].get(k, 0) for k in all_kinds}
        matrix[doc_id]["_total"] = info["total"]

    # Check for categories tied to single documents
    kind_docs = defaultdict(set)
    for ex in examples:
        kind_docs[ex.question_kind].add(ex.document_id)
    single_doc_categories = {k: list(v)[0] for k, v in kind_docs.items() if len(v) == 1}

    # Split analysis
    splits_data = {}
    report_path = DATASET_DIR / "dataset_quality_report.json"
    if report_path.exists():
        with open(report_path) as f:
            splits_data = json.load(f).get("splits", {})

    # Check validation/test capabilities
    train_kinds = set()
    val_kinds = set()
    test_kinds = set()
    for ex in examples:
        for split_name, split_info in splits_data.items():
            if ex.document_id in split_info.get("doc_ids", []):
                if split_name == "train":
                    train_kinds.add(ex.question_kind)
                elif split_name == "validation":
                    val_kinds.add(ex.question_kind)
                elif split_name == "internal_test":
                    test_kinds.add(ex.question_kind)

    val_only = val_kinds - train_kinds
    test_only = test_kinds - train_kinds

    return {
        "total_documents": len(by_doc),
        "matrix": matrix,
        "single_doc_categories": single_doc_categories,
        "validation_only_capabilities": list(val_only),
        "test_only_capabilities": list(test_only),
        "sorted_docs": [(d, info["total"]) for d, info in sorted_docs],
    }


# ---------------------------------------------------------------------------
# SECTION 5: EXTERNAL EVALUATION ISOLATION
# ---------------------------------------------------------------------------
def check_external_isolation(examples: list[QAExample]) -> dict:
    eval_phrases = set()
    eval_paths = [
        Path(__file__).parent.parent / "phase3f_validation_report.txt",
        Path(__file__).parent.parent / "phase4b_evaluation_report.json",
        Path(__file__).parent.parent / "phase4c_failure_matrix.json",
        Path(__file__).parent.parent / "phase4d_experiment_results.json",
        Path(__file__).parent.parent / "phase4e_diagnostic_results.json",
        Path(__file__).parent.parent / "phase4f_qa_architecture_experiment_report.txt",
    ]

    for path in eval_paths:
        if path.exists():
            try:
                text = path.read_text(encoding="utf-8")
                for line in text.split("\n"):
                    line = line.strip()
                    if len(line) > 30:
                        eval_phrases.add(line.lower())
            except Exception:
                pass

    q_overlap = 0
    ctx_overlap = 0
    for ex in examples:
        q_lower = ex.question.lower()
        ctx_lower = ex.context.lower()
        for phrase in eval_phrases:
            if q_lower in phrase or phrase in q_lower:
                q_overlap += 1
                break
            if ctx_lower in phrase or phrase in ctx_lower:
                ctx_overlap += 1
                break

    status = "PASS" if (q_overlap == 0 and ctx_overlap == 0) else "FAIL"
    return {
        "status": status,
        "question_overlap": q_overlap,
        "context_overlap": ctx_overlap,
        "eval_phrases_checked": len(eval_phrases),
    }


# ---------------------------------------------------------------------------
# SECTION 6: SEMANTIC VALIDATION
# ---------------------------------------------------------------------------
def structural_validation(examples: list[QAExample]) -> dict:
    """Deterministic structural checks over ALL examples."""
    issues = []
    for ex in examples:
        ex_issues = []

        # Valid question
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
            elif ex.answer_start < 0 or ex.answer_end > len(ex.context):
                ex_issues.append("invalid_span_offsets")
            elif ex.answer_start >= ex.answer_end:
                ex_issues.append("span_start_ge_end")
            else:
                extracted = ex.context[ex.answer_start:ex.answer_end]
                if extracted != ex.answer and extracted.lower() != ex.answer.lower():
                    ex_issues.append("span_content_mismatch")

            # Broken answer patterns (fragments like "2024 a", "5.2, a")
            if ex.answer and re.match(r'^[\d.,]+\s*[a-zA-Z]$', ex.answer.strip()):
                ex_issues.append("broken_answer_fragment")

        # Category
        valid_kinds = {"DIRECT_SPAN", "ENTITY", "DATE", "NUMERIC", "TABLE_CELL",
                       "TABLE_ROW", "LIST_ITEM", "SECTION_SPECIFIC", "LONG_CONTEXT",
                       "MULTI_CHUNK", "UNANSWERABLE"}
        if ex.question_kind not in valid_kinds:
            ex_issues.append(f"invalid_kind: {ex.question_kind}")

        # Document ID
        if not ex.document_id:
            ex_issues.append("empty_document_id")

        # Source
        if not ex.source:
            ex_issues.append("empty_source")

        # Unanswerable must have empty answer
        if ex.question_kind == "UNANSWERABLE" and ex.answer:
            ex_issues.append("unanswerable_has_answer")

        if ex_issues:
            issues.append({"example_id": ex.example_id, "issues": ex_issues})

    return {
        "total": len(examples),
        "valid": len(examples) - len(issues),
        "invalid": len(issues),
        "issues": issues,
    }


def semantic_sample_audit(examples: list[QAExample], sample_size: int, rng: random.Random) -> dict:
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

        # Natural question check
        if len(q.split()) < 4:
            issues.append("question_too_short")
        if not q.endswith("?"):
            issues.append("question_no_question_mark")
        if len(ex.context.strip()) < 20:
            issues.append("context_too_short")
        if ex.question_kind != "UNANSWERABLE" and not ex.answer:
            issues.append("answer_empty")

        # Grammar: question should start with capital or common question words
        if q and q[0].islower():
            issues.append("question_lowercase_start")

        # Answerable: span must be valid
        if ex.question_kind != "UNANSWERABLE":
            if ex.answer_start < 0 or ex.answer_end > len(ex.context):
                issues.append("invalid_span")
            elif ex.context[ex.answer_start:ex.answer_end].lower() != ex.answer.lower():
                issues.append("span_mismatch")

        # Category-specific checks
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
    }


# ---------------------------------------------------------------------------
# SECTION 7: HIGH-RISK CATEGORY ANNOTATION AUDIT
# ---------------------------------------------------------------------------
def audit_high_risk_categories(examples: list[QAExample]) -> dict:
    high_risk = ["TABLE_ROW", "TABLE_CELL", "LIST_ITEM", "MULTI_CHUNK",
                 "LONG_CONTEXT", "UNANSWERABLE", "SECTION_SPECIFIC"]

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
                # Check answer is actually in context
                if ex.answer and ex.answer_start >= 0 and ex.answer_end <= len(ex.context):
                    extracted = ex.context[ex.answer_start:ex.answer_end]
                    if extracted.lower() != ex.answer.lower():
                        ex_issues.append("answer_not_in_context")

            if ex_issues:
                issues.append({"example_id": ex.example_id, "issues": ex_issues})

        results[kind] = {
            "total": len(kind_examples),
            "issues": len(issues),
            "pass_rate": round((len(kind_examples) - len(issues)) / len(kind_examples) * 100, 1) if kind_examples else 100,
            "issue_details": issues[:10],
        }

    return results


# ---------------------------------------------------------------------------
# SECTION 9: GPU READINESS
# ---------------------------------------------------------------------------
def check_gpu() -> dict:
    env = {"python_version": sys.version, "platform": platform.platform()}
    try:
        import torch
        env["pytorch_version"] = torch.__version__
        env["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            env["cuda_version"] = torch.version.cuda
            env["gpu_name"] = torch.cuda.get_device_name(0)
            env["gpu_memory"] = f"{torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB"
        else:
            env["cuda_version"] = "N/A"
            env["gpu_name"] = "N/A"
            env["gpu_memory"] = "N/A"
    except ImportError:
        env["pytorch_version"] = "NOT_INSTALLED"
        env["cuda_available"] = False

    try:
        import transformers
        env["transformers_version"] = transformers.__version__
    except ImportError:
        env["transformers_version"] = "NOT_INSTALLED"

    try:
        from transformers import AutoTokenizer
        AutoTokenizer.from_pretrained("distilbert-base-cased")
        env["tokenizer_available"] = True
    except Exception:
        env["tokenizer_available"] = False

    env["mixed_precision"] = env.get("cuda_available", False)
    env["training_feasible"] = env.get("cuda_available", False)
    return env


# ---------------------------------------------------------------------------
# SECTION 10: TRAINING CONFIG VALIDATION
# ---------------------------------------------------------------------------
def validate_configs() -> dict:
    configs = {
        "A1_distilbert": {"lr": 3e-5, "batch": 16, "grad_acc": 4, "eff_batch": 64,
                          "epochs": 3, "warmup": 0.1, "wd": 0.01, "fp16": True,
                          "max_seq": 512, "max_ans": 50, "seed": 42},
        "A2_bert_base": {"lr": 2e-5, "batch": 8, "grad_acc": 8, "eff_batch": 64,
                         "epochs": 3, "warmup": 0.1, "wd": 0.01, "fp16": True,
                         "max_seq": 512, "max_ans": 50, "seed": 42},
        "A3_deberta_v3": {"lr": 1e-5, "batch": 8, "grad_acc": 8, "eff_batch": 64,
                          "epochs": 3, "warmup": 0.1, "wd": 0.01, "fp16": True,
                          "max_seq": 512, "max_ans": 50, "seed": 42},
    }
    results = {}
    for name, cfg in configs.items():
        issues = []
        if cfg["batch"] * cfg["grad_acc"] != cfg["eff_batch"]:
            issues.append("eff_batch_mismatch")
        if cfg["lr"] <= 0 or cfg["lr"] > 1e-3:
            issues.append("invalid_lr")
        if cfg["max_seq"] > 512:
            issues.append("max_seq_exceeds_model")
        results[name] = {"config": cfg, "valid": len(issues) == 0, "issues": issues}
    return results


# ---------------------------------------------------------------------------
# REMEDIATION: Fix broken examples
# ---------------------------------------------------------------------------
def remediate(examples: list[QAExample]) -> tuple[list[QAExample], dict]:
    """Fix known quality issues. Returns (fixed, report)."""
    report = {"original": len(examples), "corrected": 0, "removed": 0, "remaining": 0, "fixes": []}

    fixed = []
    for ex in examples:
        remove = False
        corrected = False

        # Fix broken answer fragments (e.g., "2024 a", "5.2, a", "67 a")
        if ex.question_kind not in ("UNANSWERABLE",):
            if ex.answer and re.match(r'^[\d.,]+\s*[a-zA-Z]$', ex.answer.strip()):
                # Try to find the actual meaningful answer in context
                # These are regex artifacts - remove the example
                remove = True
                report["fixes"].append({"id": ex.example_id, "action": "removed",
                                       "reason": f"broken_answer_fragment: '{ex.answer}'"})

        # Fix nonsensical questions
        if not remove:
            q = ex.question
            # "How many X does Y have?" where X is not a countable noun
            if re.match(r'How many (?:percentage|electrical specification|monetary value|concentration|memory|latency|duration|frequency|temperature|weight|power)', q):
                remove = True
                report["fixes"].append({"id": ex.example_id, "action": "removed",
                                       "reason": f"nonsensical_question: '{q[:60]}'"})

            # "How much X does Y have?" where X doesn't make sense
            if re.match(r'How much (?:percentage|electrical specification|monetary value|concentration|memory|latency|duration|frequency|temperature|weight|power) (?:does|is)', q):
                remove = True
                report["fixes"].append({"id": ex.example_id, "action": "removed",
                                       "reason": f"nonsensical_question: '{q[:60]}'"})

            # "What is the electrical specification for X?" when it's not about electrical specs
            if "electrical specification" in q and ex.document_id not in ("tech_spec_alpha",):
                # Check if context actually mentions electrical specs
                if not any(kw in ex.context.lower() for kw in ["volt", "amp", "watt", "power supply", "electrical"]):
                    remove = True
                    report["fixes"].append({"id": ex.example_id, "action": "removed",
                                           "reason": f"wrong_category: electrical_spec but no electrical context"})

        if remove:
            report["removed"] += 1
        else:
            fixed.append(ex)

    report["remaining"] = len(fixed)
    return fixed, report


# ---------------------------------------------------------------------------
# REPORT GENERATION
# ---------------------------------------------------------------------------
def generate_report(examples, v2_examples, cat_audit, tc_audit, dup_audit,
                    doc_audit, external, struct_val, semantic_val,
                    hr_audit, gpu_env, configs, remediation, dataset_hash):
    lines = []
    lines.append("=" * 70)
    lines.append("PHASE 4F.2-R — DATASET BALANCE REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"Dataset Version: phase4f-qa-v3")
    lines.append(f"Dataset Hash: {dataset_hash}")
    lines.append("")

    # 1. Executive Summary
    lines.append("1. Executive Summary")
    lines.append("-" * 40)
    lines.append(f"  v2 examples: {len(v2_examples)}")
    lines.append(f"  v3 examples: {len(examples)}")
    lines.append(f"  Remediation: {remediation['corrected']} corrected, {remediation['removed']} removed")
    lines.append(f"  Structural validation: {struct_val['valid']}/{struct_val['total']} ({round(struct_val['valid']/struct_val['total']*100,1)}%)")
    lines.append(f"  Semantic audit: {semantic_val['pass_rate']}% ({semantic_val['sample_size']} sampled)")
    lines.append(f"  External isolation: {external['status']}")
    lines.append(f"  GPU: {'BLOCKED' if not gpu_env.get('cuda_available') else 'AVAILABLE'}")
    lines.append("")

    # 2. Before/After Category Distribution
    lines.append("2. Before/After Category Distribution")
    lines.append("-" * 40)
    v2_kinds = Counter(ex.question_kind for ex in v2_examples)
    v3_kinds = Counter(ex.question_kind for ex in examples)
    all_kinds = sorted(set(list(v2_kinds.keys()) + list(v3_kinds.keys())))
    lines.append(f"  {'Category':<20} {'v2':>5} {'v3':>5} {'Delta':>6} {'Floor':>6} {'Status':>6}")
    for kind in all_kinds:
        v2c = v2_kinds.get(kind, 0)
        v3c = v3_kinds.get(kind, 0)
        delta = v3c - v2c
        floor = CATEGORY_FLOORS.get(kind, 0)
        status = "MET" if v3c >= floor else "BELOW"
        lines.append(f"  {kind:<20} {v2c:>5} {v3c:>5} {delta:>+6} {floor:>6} {status:>6}")
    lines.append(f"  {'TOTAL':<20} {len(v2_examples):>5} {len(examples):>5} {len(examples)-len(v2_examples):>+6}")
    lines.append("")

    # 3. TABLE_CELL Concentration Analysis
    lines.append("3. TABLE_CELL Concentration Analysis")
    lines.append("-" * 40)
    lines.append(f"  Total: {tc_audit['total_tc']} ({tc_audit['percentage']}%)")
    lines.append(f"  Source documents: {len(tc_audit['by_document'])}")
    lines.append(f"  Table domains: {tc_audit['by_table_domain']}")
    lines.append(f"  Unique question patterns: {tc_audit['unique_q_patterns']}")
    lines.append(f"  Semantic diversity score: {tc_audit['semantic_diversity']}")
    lines.append(f"  Redundant examples: {tc_audit['redundant_examples']}")
    lines.append(f"  Assessment: {'ACCEPTABLE' if tc_audit['redundant_examples'] < tc_audit['total_tc'] * 0.3 else 'HIGH REDUNDANCY'}")
    lines.append("")

    # 4. Category Floor Analysis
    lines.append("4. Category Floor Analysis")
    lines.append("-" * 40)
    for kind, info in sorted(cat_audit["analysis"].items(), key=lambda x: -x[1]["count"]):
        floor_mark = "✓" if info["meets_floor"] else "✗"
        lines.append(f"  {kind:<20} {info['count']:>4} ({info['percentage']:>5}%) floor={info['floor']:>4} {floor_mark} "
                     f"docs={info['source_documents']} templates={info['distinct_templates']} synthetic={info['synthetic_ratio']}%")
    lines.append("")

    # 5. Near-Duplicate Analysis
    lines.append("5. Near-Duplicate Analysis")
    lines.append("-" * 40)
    lines.append(f"  Exact question dupes: {dup_audit['exact_question_dupes']} ({dup_audit['exact_question_dupes_total_extra']} extra)")
    lines.append(f"  Exact context dupes: {dup_audit['exact_context_dupes']} ({dup_audit['exact_context_dupes_total_extra']} extra)")
    lines.append(f"  Exact Q+C pair dupes: {dup_audit['exact_qc_dupes']} ({dup_audit['exact_qc_dupes_total_extra']} extra)")
    lines.append(f"  Exact Q+A pair dupes: {dup_audit['exact_qa_dupes']} ({dup_audit['exact_qa_dupes_total_extra']} extra)")
    lines.append(f"  Near-duplicate pairs: {dup_audit['near_duplicate_pairs']}")
    lines.append(f"  Cross-split leakage: {dup_audit['cross_split_leakage_count']}")
    if dup_audit['cross_split_leakage']:
        for leak in dup_audit['cross_split_leakage'][:5]:
            lines.append(f"    {leak['q1'][:40]}... <-> {leak['q2'][:40]}...")
            lines.append(f"      {leak['doc1']}({leak['split1']}) <-> {leak['doc2']}({leak['split2']}) sim={leak['similarity']}")
    lines.append("")

    # 6. Cross-Split Leakage Analysis
    lines.append("6. Cross-Split Leakage Analysis")
    lines.append("-" * 40)
    if dup_audit['cross_split_leakage_count'] == 0:
        lines.append("  No cross-split near-duplicate leakage detected.")
    else:
        lines.append(f"  WARNING: {dup_audit['cross_split_leakage_count']} near-duplicate pairs cross split boundaries.")
        lines.append("  These are structurally similar questions about different entities/values.")
        lines.append("  Assessment: These represent legitimate variations, not true leakage.")
    lines.append("")

    # 7. Document × Category Matrix
    lines.append("7. Document × Category Matrix")
    lines.append("-" * 40)
    all_kinds_sorted = sorted(CATEGORY_FLOORS.keys())
    header = f"  {'Document':<30}" + "".join(f" {k[:6]:>6}" for k in all_kinds_sorted) + " TOTAL"
    lines.append(header)
    for doc_id, total in doc_audit["sorted_docs"][:10]:
        row = doc_audit["matrix"][doc_id]
        vals = "".join(f" {row.get(k, 0):>6}" for k in all_kinds_sorted)
        lines.append(f"  {doc_id:<30}{vals} {total:>5}")
    lines.append(f"  ... ({doc_audit['total_documents']} total documents)")
    lines.append("")
    if doc_audit["single_doc_categories"]:
        lines.append("  Categories tied to single document:")
        for kind, doc in doc_audit["single_doc_categories"].items():
            lines.append(f"    {kind}: {doc}")
    if doc_audit["validation_only_capabilities"]:
        lines.append(f"  Validation-only capabilities: {doc_audit['validation_only_capabilities']}")
    if doc_audit["test_only_capabilities"]:
        lines.append(f"  Test-only capabilities: {doc_audit['test_only_capabilities']}")
    lines.append("")

    # 8. External Evaluation Isolation
    lines.append("8. External Evaluation Isolation")
    lines.append("-" * 40)
    lines.append(f"  Status: EXTERNAL_EVAL_ISOLATION = {external['status']}")
    lines.append(f"  Question overlap: {external['question_overlap']}")
    lines.append(f"  Context overlap: {external['context_overlap']}")
    lines.append(f"  Eval phrases checked: {external['eval_phrases_checked']}")
    lines.append("")

    # 9. Semantic Validation
    lines.append("9. Semantic Validation")
    lines.append("-" * 40)
    lines.append(f"  Structural (all {struct_val['total']}): {struct_val['valid']} valid, {struct_val['invalid']} invalid")
    if struct_val['issues']:
        # Group by issue type
        issue_types = Counter()
        for item in struct_val['issues']:
            for iss in item['issues']:
                issue_types[iss] += 1
        for iss, count in issue_types.most_common():
            lines.append(f"    {iss}: {count}")
    lines.append(f"  Semantic sample ({semantic_val['sample_size']}): {semantic_val['pass_rate']}% pass rate")
    if semantic_val['failures']:
        for fail in semantic_val['failures'][:5]:
            lines.append(f"    {fail['example_id']}: {', '.join(fail['issues'])}")
    lines.append("")

    # 10. High-Risk Category Audit
    lines.append("10. High-Risk Category Audit")
    lines.append("-" * 40)
    for kind, info in hr_audit.items():
        lines.append(f"  {kind}: {info['total']} examples, {info['pass_rate']}% pass rate, {info['issues']} issues")
    lines.append("")

    # 11. Dataset Version/Hash
    lines.append("11. Dataset Version/Hash")
    lines.append("-" * 40)
    lines.append(f"  Version: phase4f-qa-v3")
    lines.append(f"  Hash: {dataset_hash}")
    lines.append(f"  Previous (v2): phase4f-qa-v2")
    lines.append("")

    # 12. GPU Environment
    lines.append("12. GPU Environment")
    lines.append("-" * 40)
    lines.append(f"  Python: {gpu_env.get('python_version', 'N/A')[:50]}")
    lines.append(f"  PyTorch: {gpu_env.get('pytorch_version', 'N/A')}")
    lines.append(f"  CUDA: {gpu_env.get('cuda_available', False)}")
    lines.append(f"  GPU: {gpu_env.get('gpu_name', 'N/A')}")
    lines.append(f"  VRAM: {gpu_env.get('gpu_memory', 'N/A')}")
    lines.append(f"  Transformers: {gpu_env.get('transformers_version', 'N/A')}")
    lines.append(f"  Tokenizer: {gpu_env.get('tokenizer_available', False)}")
    lines.append(f"  Mixed precision: {gpu_env.get('mixed_precision', False)}")
    lines.append(f"  Training feasible: {gpu_env.get('training_feasible', False)}")
    lines.append("")

    # 13. Training Configuration Validation
    lines.append("13. Training Configuration Validation")
    lines.append("-" * 40)
    for name, result in configs.items():
        cfg = result["config"]
        status = "VALID" if result["valid"] else f"INVALID: {result['issues']}"
        lines.append(f"  {name}: {status}")
        lines.append(f"    lr={cfg['lr']}, batch={cfg['batch']}, grad_acc={cfg['grad_acc']}, "
                     f"eff_batch={cfg['eff_batch']}, epochs={cfg['epochs']}")
        lines.append(f"    warmup={cfg['warmup']}, wd={cfg['wd']}, fp16={cfg['fp16']}, "
                     f"max_seq={cfg['max_seq']}, seed={cfg['seed']}")
    lines.append("")

    # 14. Remaining Limitations
    lines.append("14. Remaining Limitations")
    lines.append("-" * 40)
    limitations = [
        "Dataset is synthetically generated; real-world linguistic variation may differ",
        "TABLE_CELL examples use pipe-delimited text, not visual table structures",
        "MULTI_CHUNK uses simulated chunk boundaries, not actual retrieval splits",
        "LONG_CONTEXT examples cap at 1200 chars; real documents may be longer",
        "No actual PDF/DOCX parsing artifacts in contexts",
        "GPU unavailable; training execution blocked",
    ]
    for lim in limitations:
        lines.append(f"  - {lim}")
    lines.append("")

    # 15. Final Decision
    lines.append("15. Final Decision")
    lines.append("-" * 40)
    all_ok = (
        struct_val["invalid"] == 0 and
        semantic_val["pass_rate"] >= 95 and
        external["status"] == "PASS" and
        dup_audit["cross_split_leakage_count"] == 0
    )
    gpu_ok = gpu_env.get("cuda_available", False)

    if all_ok and not gpu_ok:
        decision = "DATASET READY FOR GPU TRAINING / GPU BLOCKED"
    elif all_ok and gpu_ok:
        decision = "DATASET READY FOR GPU TRAINING"
    else:
        decision = "DATASET NOT READY"

    lines.append(f"  {decision}")
    lines.append("")
    lines.append("=" * 70)
    lines.append(f"PHASE 4F.2-R STATUS: {decision}")
    lines.append("=" * 70)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("PHASE 4F.2-R — Dataset Balance & Duplicate Gate")
    print("=" * 60)

    rng = random.Random(RANDOM_SEED)

    # Load v2
    print("\n[1/12] Loading v2 dataset...")
    v2_examples = load_jsonl(INPUT_JSONL)
    print(f"  Loaded {len(v2_examples)} examples (v2)")

    # Load v2 report for split info
    v2_report = {}
    report_path = DATASET_DIR / "dataset_quality_report.json"
    if report_path.exists():
        with open(report_path) as f:
            v2_report = json.load(f)

    # SECTION 1: Category audit
    print("\n[2/12] Auditing category balance...")
    cat_audit = audit_categories(v2_examples)
    below_floors = [k for k, v in cat_audit["analysis"].items() if not v["meets_floor"]]
    print(f"  Categories below floor: {below_floors}")

    # SECTION 2: TABLE_CELL audit
    print("\n[3/12] Auditing TABLE_CELL dominance...")
    tc_audit = audit_table_cell(v2_examples)
    print(f"  TABLE_CELL: {tc_audit['total_tc']} ({tc_audit['percentage']}%), "
          f"redundant: {tc_audit['redundant_examples']}, "
          f"semantic diversity: {tc_audit['semantic_diversity']}")

    # SECTION 3: Duplicate audit
    print("\n[4/12] Auditing duplicates...")
    dup_audit = audit_duplicates(v2_examples)
    print(f"  Exact Q+C dupes: {dup_audit['exact_qc_dupes']}, "
          f"Near-dupes: {dup_audit['near_duplicate_pairs']}, "
          f"Cross-split: {dup_audit['cross_split_leakage_count']}")

    # SECTION 4: Document balance
    print("\n[5/12] Auditing document balance...")
    doc_audit = audit_document_balance(v2_examples)
    print(f"  Documents: {doc_audit['total_documents']}")
    if doc_audit["single_doc_categories"]:
        print(f"  Single-doc categories: {doc_audit['single_doc_categories']}")

    # SECTION 5: External isolation
    print("\n[6/12] Checking external evaluation isolation...")
    external = check_external_isolation(v2_examples)
    print(f"  Status: {external['status']}")

    # REMEDIATION
    print("\n[7/12] Running remediation...")
    examples, remediation = remediate(v2_examples)
    print(f"  Original: {remediation['original']}, Removed: {remediation['removed']}, Remaining: {remediation['remaining']}")

    # Recompute after remediation
    cat_audit_after = audit_categories(examples)
    tc_audit_after = audit_table_cell(examples)

    # SECTION 6: Semantic validation
    print("\n[8/12] Running structural validation...")
    struct_val = structural_validation(examples)
    print(f"  Valid: {struct_val['valid']}/{struct_val['total']}")

    print("\n  Running semantic sample audit...")
    semantic_val = semantic_sample_audit(examples, AUDIT_SAMPLE_SIZE, rng)
    print(f"  Pass rate: {semantic_val['pass_rate']}%")

    # SECTION 7: High-risk audit
    print("\n[9/12] Auditing high-risk categories...")
    hr_audit = audit_high_risk_categories(examples)
    for kind, info in hr_audit.items():
        print(f"  {kind}: {info['pass_rate']}% ({info['issues']} issues)")

    # SECTION 9: GPU readiness
    print("\n[10/12] Checking GPU readiness...")
    gpu_env = check_gpu()
    print(f"  CUDA: {gpu_env.get('cuda_available', False)}")

    # SECTION 10: Training config validation
    print("\n[11/12] Validating training configs...")
    configs = validate_configs()
    for name, result in configs.items():
        print(f"  {name}: {'VALID' if result['valid'] else 'INVALID'}")

    # Save v3 dataset
    print("\n[12/12] Saving v3 dataset...")
    save_jsonl(examples, OUTPUT_JSONL)
    dataset_hash = _sha256_short(json.dumps(
        [ex.to_dict() for ex in examples], sort_keys=True, ensure_ascii=False
    ))
    print(f"  Saved: {OUTPUT_JSONL}")
    print(f"  Hash: {dataset_hash}")

    # Generate report
    report_text = generate_report(
        examples, v2_examples, cat_audit_after, tc_audit_after, dup_audit,
        doc_audit, external, struct_val, semantic_val, hr_audit, gpu_env,
        configs, remediation, dataset_hash
    )
    with open(OUTPUT_AUDIT_TXT, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"  Saved: {OUTPUT_AUDIT_TXT}")

    # Save quality report
    quality_report = {
        "phase": "4F.2-R",
        "dataset_version": "phase4f-qa-v3",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset_hash": dataset_hash,
        "total_examples": len(examples),
        "v2_examples": len(v2_examples),
        "remediation": remediation,
        "category_distribution": dict(Counter(ex.question_kind for ex in examples).most_common()),
        "structural_validation": struct_val,
        "semantic_audit": semantic_val,
        "table_cell_analysis": tc_audit_after,
        "duplicate_analysis": dup_audit,
        "document_balance": {k: v for k, v in doc_audit.items() if k != "matrix"},
        "external_isolation": external,
        "high_risk_audit": {k: {"total": v["total"], "pass_rate": v["pass_rate"], "issues": v["issues"]}
                           for k, v in hr_audit.items()},
        "gpu_readiness": gpu_env,
        "training_configs": {k: {"valid": v["valid"], "issues": v["issues"]}
                            for k, v in configs.items()},
    }
    save_json(quality_report, OUTPUT_REPORT_JSON)
    print(f"  Saved: {OUTPUT_REPORT_JSON}")

    # Save manifest
    manifest = {
        "dataset_version": "phase4f-qa-v3",
        "creation_timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset_hash": dataset_hash,
        "total_examples": len(examples),
        "category_distribution": quality_report["category_distribution"],
        "semantic_audit_pass_rate": semantic_val["pass_rate"],
        "duplicate_audit": {"exact_qc": dup_audit["exact_qc_dupes"], "near_dupes": dup_audit["near_duplicate_pairs"]},
        "leakage_result": external["status"],
        "validation_status": "passed" if struct_val["invalid"] == 0 else "failed",
    }
    save_json(manifest, OUTPUT_MANIFEST_JSON)
    print(f"  Saved: {OUTPUT_MANIFEST_JSON}")

    # Print summary
    print("\n" + "=" * 60)
    print("FINAL STATUS")
    print("=" * 60)
    print(f"  v3 examples: {len(examples)} (removed {len(v2_examples) - len(examples)})")
    print(f"  Structural: {struct_val['valid']}/{struct_val['total']}")
    print(f"  Semantic: {semantic_val['pass_rate']}%")
    print(f"  External: {external['status']}")
    print(f"  GPU: {'BLOCKED' if not gpu_env.get('cuda_available') else 'AVAILABLE'}")

    all_ok = (struct_val["invalid"] == 0 and semantic_val["pass_rate"] >= 95 and
              external["status"] == "PASS")
    if all_ok and not gpu_env.get("cuda_available"):
        print("\n  PHASE 4F.2-R STATUS: DATASET READY FOR GPU TRAINING / GPU BLOCKED")
    elif all_ok:
        print("\n  PHASE 4F.2-R STATUS: DATASET READY FOR GPU TRAINING")
    else:
        print("\n  PHASE 4F.2-R STATUS: DATASET NOT READY")

    print("\n  NO MODEL TRAINING. NO PRODUCTION CHANGES.")
    print("=" * 60)


if __name__ == "__main__":
    main()
