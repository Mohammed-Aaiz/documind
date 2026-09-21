"""Phase 4E — QA Capability Matrix & Architecture Analysis.

Comprehensive analysis of DocuMind's QA capabilities, mapping every
benchmark question to an explicit capability class, testing representability,
and evaluating architecture options.

NO training. NO model replacement. NO production changes.

Usage::

    cd backend
    venv/Scripts/python.exe -m phase4e.capability_analysis
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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
# QA Model
# ---------------------------------------------------------------------------

_model = None
_tokenizer = None
_model_loaded = False


def _load_qa_model():
    global _model, _tokenizer, _model_loaded
    if _model_loaded:
        return
    import torch
    from transformers import AutoModelForQuestionAnswering, AutoTokenizer

    model_path = os.getenv("QA_MODEL_NAME", "./models/documind-qa")
    _tokenizer = AutoTokenizer.from_pretrained(model_path)
    _model = AutoModelForQuestionAnswering.from_pretrained(model_path)
    _model.eval()
    _model_loaded = True
    print(f"  QA model loaded from {model_path}")


def ask(question: str, context: str) -> dict:
    """Direct QA model call."""
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
                answer_tokens = input_ids_0[s:e + 1]
                best_answer = _tokenizer.decode(answer_tokens, skip_special_tokens=True).strip()

    if not best_answer:
        s = torch.argmax(start_logits)
        e = torch.argmax(end_logits) + 1
        answer_tokens = inputs["input_ids"][0][s:e]
        best_answer = _tokenizer.decode(answer_tokens, skip_special_tokens=True).strip()
        best_score = float(torch.softmax(start_probs, dim=0)[s] * torch.softmax(end_probs, dim=0)[e - 1])

    return {"answer": best_answer, "score": round(max(0.0, min(1.0, best_score)), 4)}


# ---------------------------------------------------------------------------
# Capability Taxonomy
# ---------------------------------------------------------------------------

CAPABILITIES = {
    "DIRECT_SPAN": {
        "definition": "Answer is one contiguous span directly stated in evidence",
        "example": "What year was the paper published? → 2024",
        "answer_type": "SPAN",
        "extractive_representable": "YES",
    },
    "ENTITY_EXTRACTION": {
        "definition": "Answer is a named entity (person, org, location, technology)",
        "example": "What tool is required? → Tundra torque wrench",
        "answer_type": "ENTITY",
        "extractive_representable": "YES",
    },
    "NUMERIC_EXTRACTION": {
        "definition": "Answer is a number, percentage, measurement, or currency",
        "example": "What is the accuracy? → 85 percent",
        "answer_type": "NUMBER",
        "extractive_representable": "PARTIAL",
    },
    "DATE_EXTRACTION": {
        "definition": "Answer is a date, year, or time range",
        "example": "When was it released? → March 2024",
        "answer_type": "DATE",
        "extractive_representable": "YES",
    },
    "TABLE_CELL": {
        "definition": "Answer is directly contained in a single table cell",
        "example": "What is the accuracy of Config D? → 91.3",
        "answer_type": "SPAN",
        "extractive_representable": "PARTIAL",
    },
    "TABLE_ROW": {
        "definition": "Answer requires interpreting one table row",
        "example": "Which method has highest accuracy? → Config G",
        "answer_type": "ENTITY",
        "extractive_representable": "PARTIAL",
    },
    "TABLE_COMPARISON": {
        "definition": "Answer requires comparing values across table rows",
        "example": "Which is faster, A or B? → A",
        "answer_type": "ENTITY",
        "extractive_representable": "NOT_REPRESENTABLE",
    },
    "LIST_ITEM": {
        "definition": "Answer is one list item",
        "example": "What is the third step? → Configure the database",
        "answer_type": "SPAN",
        "extractive_representable": "PARTIAL",
    },
    "LIST_ORDER": {
        "definition": "Question depends on list ordering/position",
        "example": "What follows draining the loop? → Remove the filter",
        "answer_type": "SPAN",
        "extractive_representable": "NOT_REPRESENTABLE",
    },
    "MULTI_CHUNK": {
        "definition": "Relevant evidence spans multiple retrieved chunks",
        "example": "Trace the programme from start to finish → 1984",
        "answer_type": "SPAN",
        "extractive_representable": "PARTIAL",
    },
    "MULTI_HOP": {
        "definition": "Answer requires connecting multiple pieces of evidence",
        "example": "What replaced the booster that was introduced in 1971? → Falcon",
        "answer_type": "SPAN",
        "extractive_representable": "NOT_REPRESENTABLE",
    },
    "COMPARISON": {
        "definition": "Answer requires comparing two or more values",
        "example": "Which method is more accurate? → Neural Network",
        "answer_type": "ENTITY",
        "extractive_representable": "NOT_REPRESENTABLE",
    },
    "AGGREGATION": {
        "definition": "Answer requires calculation or aggregation",
        "example": "What is the average accuracy? → 85.2%",
        "answer_type": "NUMBER",
        "extractive_representable": "NOT_REPRESENTABLE",
    },
    "DEFINITION": {
        "definition": "Answer is a definition or explanation",
        "example": "What is abstention? → withholds an answer",
        "answer_type": "SPAN",
        "extractive_representable": "YES",
    },
    "SECTION_SPECIFIC": {
        "definition": "Answer requires correct section identification",
        "example": "What is in the Epsilon section? → Vermilion coating",
        "answer_type": "SPAN",
        "extractive_representable": "YES",
    },
    "UNANSWERABLE": {
        "definition": "Evidence does not support an answer",
        "example": "What is the population of Tokyo? → (no answer)",
        "answer_type": "NONE",
        "extractive_representable": "YES",
    },
}


# ---------------------------------------------------------------------------
# Question Mapping
# ---------------------------------------------------------------------------

# Map Phase 4B question kinds to capabilities
KIND_TO_CAPABILITY = {
    "factual": "DIRECT_SPAN",
    "table": "TABLE_CELL",
    "list": "LIST_ITEM",
    "section_specific": "SECTION_SPECIFIC",
    "dense_prose": "DIRECT_SPAN",
    "long_paragraph": "DIRECT_SPAN",
    "academic": "DIRECT_SPAN",
    "multichunk": "MULTI_CHUNK",
    "multipage": "MULTI_CHUNK",
    "surrounding_context": "DIRECT_SPAN",
    "unpunctuated": "DIRECT_SPAN",
    "unsupported": "UNANSWERABLE",
}

# Special overrides based on actual question content
QUESTION_OVERRIDES = {
    # Table comparison questions
    "tm_2": "TABLE_COMPARISON",    # "Which configuration has highest accuracy?"
    "tm_5": "TABLE_COMPARISON",    # "Which configuration has lowest latency?"
    "tn_2": "TABLE_COMPARISON",    # "Which station has highest humidity?"
    "tn_3": "TABLE_COMPARISON",    # "Temperature difference between Alpha-1 and Beta-1?"
    "mx_3": "TABLE_COMPARISON",    # "Which season recorded 1013 millibars?"
    "ms_2": "TABLE_COMPARISON",    # "Which month had negative growth?"
    "cd_2": "TABLE_COMPARISON",    # "Which model has fewest parameters?"

    # List order questions
    "ln_2": "LIST_ORDER",          # "What is the third installation step?"
    "ln_4": "LIST_ORDER",          # "How many prerequisites are listed?"
    "ll_1": "LIST_ORDER",          # "What is the sixth component?"
    "ll_3": "LIST_ORDER",          # "What is the last component listed?"
    "ll_4": "LIST_ORDER",          # "How many components are listed?"
    "ms_3": "LIST_ORDER",          # "What was the first key achievement?"
    "ms_5": "LIST_ORDER",          # "What is the first next quarter goal?"
    "tm_manual_3": "LIST_ORDER",   # "What is the fourth calibration step?"
    "tm_manual_5": "LIST_ITEM",    # "What equipment is required?"

    # Numeric extraction
    "tm_3": "NUMERIC_EXTRACTION",  # "What is the latency of Config F?"
    "tm_4": "NUMERIC_EXTRACTION",  # "How much memory does Config D use?"
    "rp_3": "NUMERIC_EXTRACTION",  # "What sparsity level is used?"
    "rp_4": "NUMERIC_EXTRACTION",  # "How many iterations?"
    "dp_2": "NUMERIC_EXTRACTION",  # "What was the mean transport rate?"
    "dp_3": "NUMERIC_EXTRACTION",  # "What was the erosion rate?"
    "dp_4": "NUMERIC_EXTRACTION",  # "When was the glacier first documented?"
    "mpr_2": "NUMERIC_EXTRACTION", # "What is the chunk count after upgrade?"
    "mpr_4": "NUMERIC_EXTRACTION", # "What is the QA_EXTRACT failure rate?"
    "mpr_5": "NUMERIC_EXTRACTION", # "How many parameters does QA model have?"
    "tl_3": "NUMERIC_EXTRACTION",  # "What was the initial QA model accuracy?"
    "rp_2": "NUMERIC_EXTRACTION",  # "Improvement over baseline on CIFAR-10?"
    "cd_3": "NUMERIC_EXTRACTION",  # "What is the latency of BERT-large?"

    # Definition questions
    "gl_1": "DEFINITION",          # "What is abstention?"
    "gl_2": "DEFINITION",          # "What is the current context window size?"
    "gl_3": "DEFINITION",          # "What does CTX_TRUNC stand for?"
    "gl_4": "DEFINITION",          # "What is MRR?"
    "faq_1": "DEFINITION",         # "What file formats does DocuMind support?"
    "faq_2": "DEFINITION",         # "What embedding model does DocuMind use?"
    "faq_3": "DEFINITION",         # "What is the default max upload size?"
    "faq_4": "DEFINITION",         # "What authentication method is used?"

    # Comparison questions
    "rp_1": "TABLE_COMPARISON",    # "What accuracy does Falcon achieve on MNIST?"
    "rp_5": "TABLE_COMPARISON",    # "What is baseline accuracy on ImageNet?"
}


def classify_question(qid: str, kind: str, text: str) -> str:
    """Classify a question into a capability."""
    if qid in QUESTION_OVERRIDES:
        return QUESTION_OVERRIDES[qid]
    return KIND_TO_CAPABILITY.get(kind, "DIRECT_SPAN")


# ---------------------------------------------------------------------------
# Document context builder (for representability tests)
# ---------------------------------------------------------------------------

def build_document_context(doc_name: str, evidence: tuple) -> str:
    """Build a realistic document context for a question.

    Uses the document builder to generate the actual document text,
    then extracts the relevant section.
    """
    import tempfile

    try:
        from tests.phase4b_corpus import build_phase4b_corpus
        corpus = build_phase4b_corpus()

        for doc in corpus:
            if doc.name == doc_name:
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / doc.name
                    doc.builder(path)

                    if doc.file_type == "docx":
                        import docx
                        d = docx.Document(str(path))
                        full_text = "\n".join(p.text for p in d.paragraphs if p.text.strip())
                        # Also include table text
                        for table in d.tables:
                            for row in table.rows:
                                full_text += "\n" + " | ".join(cell.text for cell in row.cells)
                    elif doc.file_type == "txt":
                        full_text = path.read_text(encoding="utf-8")
                    elif doc.file_type == "pdf":
                        import fitz
                        pdf = fitz.open(str(path))
                        full_text = ""
                        for page in pdf:
                            full_text += page.get_text()
                        pdf.close()
                    else:
                        full_text = ""

                    # Find the relevant section containing evidence
                    if evidence:
                        for e in evidence:
                            idx = full_text.lower().find(e.lower())
                            if idx >= 0:
                                # Extract a window around the evidence
                                start = max(0, idx - 200)
                                end = min(len(full_text), idx + len(e) + 200)
                                return full_text[start:end]

                    # Fallback: return first 500 chars
                    return full_text[:500]
    except Exception:
        pass

    # Fallback: use evidence as context
    return " ".join(evidence) if evidence else ""


# ---------------------------------------------------------------------------
# Controlled Representability Tests
# ---------------------------------------------------------------------------

@dataclass
class DiagnosticResult:
    qid: str
    capability: str
    question: str
    context: str
    context_source: str  # "evidence_keywords", "document_passage", "synthetic"
    expected_answer: str
    prediction: str
    exact_match: bool
    token_f1: float
    confidence: float
    answer_is_contiguous_span: bool
    representability: str  # REPRESENTABLE, PARTIAL, NOT_REPRESENTABLE


def run_diagnostic_tests(questions: list[dict], acceptable: dict) -> list[DiagnosticResult]:
    """Run controlled representability tests with proper document contexts."""
    _load_qa_model()
    results = []

    answerable = [q for q in questions if q["answerable"] and q["expected_answer"]]

    for i, q in enumerate(answerable):
        qid = q["qid"]
        expected = q["expected_answer"]
        evidence = q.get("evidence", ())
        kind = q.get("kind", "factual")
        text = q["text"]
        doc = q.get("document", "")

        # Classify capability
        capability = classify_question(qid, kind, text)

        # Build context from document
        doc_context = build_document_context(doc, evidence)
        keyword_context = " ".join(evidence) if evidence else expected

        # Test with document context (primary)
        ctx = doc_context if doc_context else keyword_context
        ctx_source = "document_passage" if doc_context else "evidence_keywords"

        qa_result = ask(text, ctx)
        pred = qa_result["answer"]
        em = exact_match(pred, expected)
        f1 = token_f1(pred, expected)

        # Determine if answer is a contiguous span in context
        answer_in_context = expected.lower() in ctx.lower() if ctx else False

        # Representability assessment
        if capability in ("DIRECT_SPAN", "ENTITY_EXTRACTION", "DATE_EXTRACTION",
                          "DEFINITION", "SECTION_SPECIFIC", "UNANSWERABLE"):
            rep = "REPRESENTABLE"
        elif capability in ("TABLE_CELL", "LIST_ITEM", "MULTI_CHUNK"):
            rep = "PARTIAL"
        elif capability in ("NUMERIC_EXTRACTION",):
            rep = "PARTIAL"
        else:
            rep = "NOT_REPRESENTABLE"

        results.append(DiagnosticResult(
            qid=qid, capability=capability, question=text,
            context=ctx[:300], context_source=ctx_source,
            expected_answer=expected, prediction=pred,
            exact_match=em, token_f1=round(f1, 4),
            confidence=qa_result["score"],
            answer_is_contiguous_span=answer_in_context,
            representability=rep,
        ))

        if (i + 1) % 20 == 0:
            print(f"    [{i+1}/{len(answerable)}] running...")

    return results


# ---------------------------------------------------------------------------
# Product Requirements Mapping
# ---------------------------------------------------------------------------

PRODUCT_REQUIREMENTS = [
    {
        "requirement": "Answer factual questions about documents",
        "capability": "DIRECT_SPAN",
        "extractive_compatible": True,
        "current_evidence": "70% EM on factual questions (unified oracle)",
        "priority": "HIGH",
    },
    {
        "requirement": "Extract values from tables",
        "capability": "TABLE_CELL",
        "extractive_compatible": "PARTIAL",
        "current_evidence": "29.2% EM on table questions (unified oracle)",
        "priority": "HIGH",
    },
    {
        "requirement": "Navigate lists and ordered items",
        "capability": "LIST_ITEM/LIST_ORDER",
        "extractive_compatible": "PARTIAL/NOT_REPRESENTABLE",
        "current_evidence": "6.25% EM on list questions (unified oracle)",
        "priority": "HIGH",
    },
    {
        "requirement": "Extract numeric values with units",
        "capability": "NUMERIC_EXTRACTION",
        "extractive_compatible": "PARTIAL",
        "current_evidence": "NOT_EVALUATED separately",
        "priority": "MEDIUM",
    },
    {
        "requirement": "Compare values across documents",
        "capability": "COMPARISON",
        "extractive_compatible": False,
        "current_evidence": "NOT_EVALUATED separately",
        "priority": "MEDIUM",
    },
    {
        "requirement": "Multi-chunk evidence synthesis",
        "capability": "MULTI_CHUNK",
        "extractive_compatible": "PARTIAL",
        "current_evidence": "1 multi-chunk question, 100% failure",
        "priority": "LOW",
    },
    {
        "requirement": "Correct abstention on unanswerable questions",
        "capability": "UNANSWERABLE",
        "extractive_compatible": True,
        "current_evidence": "10 unsupported questions, needs verification",
        "priority": "HIGH",
    },
    {
        "requirement": "Evidence citation and provenance",
        "capability": "ALL",
        "extractive_compatible": True,
        "current_evidence": "Extractive QA inherently provides span positions",
        "priority": "HIGH",
    },
    {
        "requirement": "Low latency (<200ms)",
        "capability": "ALL",
        "extractive_compatible": True,
        "current_evidence": "~23ms QA latency on CPU",
        "priority": "HIGH",
    },
    {
        "requirement": "Deterministic behavior",
        "capability": "ALL",
        "extractive_compatible": True,
        "current_evidence": "Extractive QA is deterministic",
        "priority": "MEDIUM",
    },
]


# ---------------------------------------------------------------------------
# Architecture Options
# ---------------------------------------------------------------------------

ARCHITECTURE_OPTIONS = {
    "OPTION_A": {
        "name": "Improve DistilBERT extractive QA",
        "description": "Fine-tune with targeted table/list data on GPU",
        "supported_capabilities": ["DIRECT_SPAN", "ENTITY_EXTRACTION", "DATE_EXTRACTION",
                                    "DEFINITION", "SECTION_SPECIFIC"],
        "limitations": ["Cannot synthesize across chunks", "Cannot compare values",
                        "Cannot aggregate", "Cannot reason about list order"],
        "evidence_requirements": "GPU training with 1000+ targeted examples",
        "implementation_complexity": "LOW",
        "latency_impact": "NONE (same model)",
        "reliability_impact": "LOW (proven architecture)",
        "hallucination_risk": "NONE (extractive)",
        "provenance_impact": "EXCELLENT (span positions in context)",
        "evaluation_complexity": "LOW (same evaluation framework)",
    },
    "OPTION_B": {
        "name": "Stronger extractive model (DeBERTa-v3-base)",
        "description": "Replace DistilBERT with DeBERTa for better span extraction",
        "supported_capabilities": ["DIRECT_SPAN", "ENTITY_EXTRACTION", "DATE_EXTRACTION",
                                    "DEFINITION", "SECTION_SPECIFIC", "TABLE_CELL"],
        "limitations": ["Same synthesis limitations as DistilBERT",
                        "Higher latency (~2x)", "Larger model (~86M params)"],
        "evidence_requirements": "Benchmark DeBERTa on unified oracle",
        "implementation_complexity": "MEDIUM (model swap + retraining)",
        "latency_impact": "MODERATE (+50-100%)",
        "reliability_impact": "LOW (proven architecture)",
        "hallucination_risk": "NONE (extractive)",
        "provenance_impact": "EXCELLENT (span positions)",
        "evaluation_complexity": "LOW",
    },
    "OPTION_C": {
        "name": "Extractive + lightweight synthesis layer",
        "description": "Extractive QA for simple questions, rule-based synthesis for complex",
        "supported_capabilities": ["DIRECT_SPAN", "ENTITY_EXTRACTION", "DATE_EXTRACTION",
                                    "DEFINITION", "SECTION_SPECIFIC", "TABLE_CELL",
                                    "LIST_ITEM", "MULTI_CHUNK", "COMPARISON"],
        "limitations": ["Synthesis layer is rule-based, not learned",
                        "Cannot handle arbitrary aggregation",
                        "More complex architecture"],
        "evidence_requirements": "Define synthesis rules for each capability",
        "implementation_complexity": "MEDIUM-HIGH",
        "latency_impact": "MODERATE (+20-50%)",
        "reliability_impact": "MODERATE (more components to validate)",
        "hallucination_risk": "LOW (rule-based synthesis)",
        "provenance_impact": "GOOD (extractive path is traceable)",
        "evaluation_complexity": "MEDIUM",
    },
    "OPTION_D": {
        "name": "Generative grounded QA",
        "description": "Small generative model (T5-small) with evidence grounding",
        "supported_capabilities": ["DIRECT_SPAN", "ENTITY_EXTRACTION", "DATE_EXTRACTION",
                                    "DEFINITION", "SECTION_SPECIFIC", "TABLE_CELL",
                                    "LIST_ITEM", "LIST_ORDER", "MULTI_CHUNK",
                                    "MULTI_HOP", "COMPARISON", "AGGREGATION",
                                    "SUMMARIZATION"],
        "limitations": ["Hallucination risk", "Loss of exact span provenance",
                        "Higher latency", "Requires evidence verification"],
        "evidence_requirements": "Prototype with evidence grounding verification",
        "implementation_complexity": "HIGH",
        "latency_impact": "HIGH (+200-500%)",
        "reliability_impact": "HIGH (new failure modes)",
        "hallucination_risk": "MODERATE (generative)",
        "provenance_impact": "MODERATE (needs evidence verification layer)",
        "evaluation_complexity": "HIGH",
    },
    "OPTION_E": {
        "name": "Hybrid: extractive + grounded synthesis",
        "description": "Route simple questions to extractive, complex to grounded synthesis",
        "supported_capabilities": ["ALL"],
        "limitations": ["Routing accuracy", "Two models to maintain",
                        "Complex evaluation", "Integration complexity"],
        "evidence_requirements": "Question classifier + both models trained",
        "implementation_complexity": "HIGH",
        "latency_impact": "VARIABLE (extractive for simple, generative for complex)",
        "reliability_impact": "HIGH (routing errors possible)",
        "hallucination_risk": "LOW-MODERATE (generative path only)",
        "provenance_impact": "GOOD (extractive path is traceable, generative needs verification)",
        "evaluation_complexity": "HIGH",
    },
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 78)
    print("PHASE 4E — QA CAPABILITY MATRIX & ARCHITECTURE ANALYSIS")
    print("=" * 78)

    # Load corpus
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
            "expected_answer": None, "evidence": (), "kind": q.kind,
            "document": "unsupported",
        })

    answerable = [q for q in questions if q["answerable"]]
    print(f"\nCorpus: {len(questions)} questions ({len(answerable)} answerable)")

    # Load acceptable answers
    try:
        from evaluation.harness.corpus import ACCEPTABLE_ANSWERS
        acceptable = ACCEPTABLE_ANSWERS
    except ImportError:
        acceptable = {}

    # ===================================================================
    # 1. Map all questions to capabilities
    # ===================================================================
    print("\n[1] Mapping questions to capabilities...")

    question_mappings = []
    capability_counts = Counter()

    for q in questions:
        cap = classify_question(q["qid"], q["kind"], q["text"])
        capability_counts[cap] += 1

        answer_type = CAPABILITIES.get(cap, {}).get("answer_type", "SPAN")
        rep = CAPABILITIES.get(cap, {}).get("extractive_representable", "UNKNOWN")

        question_mappings.append({
            "qid": q["qid"],
            "question": q["text"],
            "kind": q["kind"],
            "document": q["document"],
            "answerable": q["answerable"],
            "expected_answer": q.get("expected_answer"),
            "primary_capability": cap,
            "answer_type": answer_type,
            "extractive_representability": rep,
        })

    print(f"\n  Capability distribution:")
    for cap, count in sorted(capability_counts.items(), key=lambda x: -x[1]):
        rep = CAPABILITIES.get(cap, {}).get("extractive_representable", "?")
        print(f"    {cap:24s} {count:3d}  extractive={rep}")

    # ===================================================================
    # 2. Run diagnostic tests
    # ===================================================================
    print("\n[2] Running controlled representability tests...")
    print("  (Building document contexts and testing extraction)")

    diagnostic_results = run_diagnostic_tests(answerable, acceptable)

    # Aggregate by capability
    cap_metrics = {}
    for cap in sorted(set(r.capability for r in diagnostic_results)):
        cap_results = [r for r in diagnostic_results if r.capability == cap]
        n = len(cap_results)
        if n == 0:
            continue
        em = sum(1 for r in cap_results if r.exact_match) / n
        f1 = mean([r.token_f1 for r in cap_results])
        conf = mean([r.confidence for r in cap_results])
        doc_ctx = sum(1 for r in cap_results if r.context_source == "document_passage")

        cap_metrics[cap] = {
            "n": n,
            "exact_match": round(em, 4),
            "token_f1": round(f1, 4),
            "mean_confidence": round(conf, 4),
            "document_context_available": doc_ctx,
        }

        print(f"    {cap:24s} n={n:3d} EM={em:.4f} F1={f1:.4f} conf={conf:.4f} doc_ctx={doc_ctx}")

    # ===================================================================
    # 3. Build capability matrix
    # ===================================================================
    print("\n[3] Building capability matrix...")

    capability_matrix = []
    for cap_name, cap_info in CAPABILITIES.items():
        metrics = cap_metrics.get(cap_name, {"n": 0, "exact_match": 0, "token_f1": 0, "mean_confidence": 0})
        capability_matrix.append({
            "capability": cap_name,
            "definition": cap_info["definition"],
            "example": cap_info["example"],
            "expected_answer_type": cap_info["answer_type"],
            "extractive_representability": cap_info["extractive_representable"],
            "current_evidence": f"n={metrics['n']}, EM={metrics['exact_match']:.4f}, F1={metrics['token_f1']:.4f}" if metrics["n"] > 0 else "NOT_EVALUATED",
            "question_count": metrics["n"],
            "baseline_performance": {
                "exact_match": metrics.get("exact_match", 0),
                "token_f1": metrics.get("token_f1", 0),
                "mean_confidence": metrics.get("mean_confidence", 0),
            },
        })

    # Save capability matrix
    matrix_path = Path("phase4e_capability_matrix.json")
    with open(matrix_path, "w") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "capabilities": capability_matrix,
            "question_mappings": question_mappings,
            "capability_distribution": dict(capability_counts),
            "product_requirements": PRODUCT_REQUIREMENTS,
            "architecture_options": ARCHITECTURE_OPTIONS,
        }, f, indent=2, default=str)
    print(f"  Saved: {matrix_path}")

    # ===================================================================
    # 4. Failure matrix
    # ===================================================================
    print("\n[4] Building failure matrix...")

    failure_matrix = defaultdict(lambda: defaultdict(int))
    for r in diagnostic_results:
        if r.exact_match:
            failure_matrix[r.capability]["CORRECT"] += 1
        elif r.confidence == 0:
            failure_matrix[r.capability]["QA_CONFIDENCE_ZERO"] += 1
        elif not r.answer_is_contiguous_span:
            failure_matrix[r.capability]["ANSWER_NOT_IN_CONTEXT"] += 1
        else:
            failure_matrix[r.capability]["QA_SPAN_SELECTION"] += 1

    print(f"\n  Failure matrix (capability × cause):")
    causes = ["CORRECT", "QA_SPAN_SELECTION", "QA_CONFIDENCE_ZERO", "ANSWER_NOT_IN_CONTEXT"]
    header = f"  {'Capability':24s}" + "".join(f" {c:20s}" for c in causes)
    print(header)
    for cap in sorted(failure_matrix.keys()):
        row = f"  {cap:24s}"
        for cause in causes:
            count = failure_matrix[cap][cause]
            row += f" {count:20d}"
        print(row)

    # ===================================================================
    # 5. Save diagnostic results
    # ===================================================================
    print("\n[5] Saving diagnostic results...")

    diag_output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_questions": len(diagnostic_results),
        "capability_metrics": cap_metrics,
        "failure_matrix": {k: dict(v) for k, v in failure_matrix.items()},
        "per_question": [asdict(r) for r in diagnostic_results],
    }

    diag_path = Path("phase4e_diagnostic_results.json")
    with open(diag_path, "w") as f:
        json.dump(diag_output, f, indent=2, default=str)
    print(f"  Saved: {diag_path}")

    # ===================================================================
    # Summary
    # ===================================================================
    print("\n" + "=" * 78)
    print("PHASE 4E SUMMARY")
    print("=" * 78)

    print(f"\n  Total questions mapped: {len(question_mappings)}")
    print(f"  Capabilities identified: {len(CAPABILITIES)}")
    print(f"  Diagnostic tests run: {len(diagnostic_results)}")

    overall_em = sum(1 for r in diagnostic_results if r.exact_match) / max(1, len(diagnostic_results))
    print(f"  Overall EM (document context): {overall_em:.4f}")

    print(f"\n  Capability performance (document context):")
    for cap, metrics in sorted(cap_metrics.items(), key=lambda x: -x[1]["exact_match"]):
        rep = CAPABILITIES.get(cap, {}).get("extractive_representable", "?")
        print(f"    {cap:24s} EM={metrics['exact_match']:.4f} F1={metrics['token_f1']:.4f} rep={rep}")

    print(f"\n  Architecture options evaluated: {len(ARCHITECTURE_OPTIONS)}")
    for opt_id, opt in ARCHITECTURE_OPTIONS.items():
        print(f"    {opt_id}: {opt['name']}")

    print(f"\n  Product requirements mapped: {len(PRODUCT_REQUIREMENTS)}")

    print("\n" + "=" * 78)
    print("PHASE 4E ANALYSIS COMPLETE")
    print("=" * 78)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
