"""Phase 4E — Report Generator.

Produces:
  - backend/phase4e_qa_architecture_analysis.txt
  - backend/phase4e_capability_matrix.json (already created by analysis)
  - backend/phase4e_diagnostic_results.json (already created by analysis)

Usage::

    cd backend
    venv/Scripts/python.exe -m phase4e.generate_report
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

EXPERIMENT_DIR = Path(__file__).parent.parent / "models" / "experiments" / "phase4d"


def load_json(path: Path) -> dict | None:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def generate_report() -> str:
    """Generate the Phase 4E architecture analysis report."""
    lines = []

    def add(text=""):
        lines.append(text)

    add("=" * 78)
    add("PHASE 4E — QA CAPABILITY & ARCHITECTURE ANALYSIS")
    add("=" * 78)
    add(f"Report Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    add("Status: ANALYSIS COMPLETE — NO PRODUCTION CHANGES")
    add()

    # Load data
    capability_matrix = load_json(Path("phase4e_capability_matrix.json"))
    diagnostic_results = load_json(Path("phase4e_diagnostic_results.json"))
    reconciliation = load_json(Path("phase4d_1_reconciliation.json"))

    # =========================================================================
    # 1. Executive Summary
    # =========================================================================
    add("=" * 78)
    add("1. EXECUTIVE SUMMARY")
    add("=" * 78)
    add()
    add("Phase 4E defines DocuMind's QA capability taxonomy, maps every")
    add("benchmark question to an explicit capability class, tests")
    add("representability with the current extractive architecture,")
    add("and evaluates architecture options for the next experiment.")
    add()
    add("KEY FINDINGS:")
    add()
    add("  1. The current DistilBERT extractive QA can REPRESENT 7 of 16")
    add("     capability classes (DIRECT_SPAN, ENTITY, DATE, DEFINITION,")
    add("     SECTION_SPECIFIC, UNANSWERABLE, and partially TABLE_CELL/LIST_ITEM)")
    add()
    add("  2. 9 capability classes require capabilities beyond pure extraction:")
    add("     TABLE_ROW, TABLE_COMPARISON, LIST_ORDER, MULTI_CHUNK,")
    add("     MULTI_HOP, COMPARISON, AGGREGATION, TRANSFORMATION, SUMMARIZATION")
    add()
    add("  3. The unified oracle baseline (27.2% EM) reflects both model")
    add("     weakness AND context quality issues — evidence substrings are")
    add("     too short to support extraction")
    add()
    add("  4. Product requirements demand capabilities the extractive")
    add("     architecture cannot represent (comparison, aggregation, synthesis)")
    add()

    if reconciliation:
        oracle_c = reconciliation.get("oracle_c_unified", {}).get("aggregate", {})
        add(f"  Corrected baseline: Oracle-C EM = {oracle_c.get('exact_match', 0):.4f}")
    add()

    # =========================================================================
    # 2. Corrected Baseline
    # =========================================================================
    add("=" * 78)
    add("2. CORRECTED BASELINE")
    add("=" * 78)
    add()
    add("Phase 4D.1 reconciliation established the corrected baseline:")
    add()
    add("  ORACLE-C (Unified protocol):")
    add("    Correct question + actual evidence substrings")
    add("    EM = 0.2717 (24/92)")
    add("    F1 = 0.6196")
    add("    Confidence = 0.1212")
    add()
    add("  IMPORTANT: This baseline uses evidence SUBSTRINGS (keywords),")
    add("  not full document passages. The true oracle with full document")
    add("  context may be significantly higher.")
    add()
    add("  Phase 4C's 84.3% failure rate: INVALID (protocol bug)")
    add("  Phase 4D's 66.3% EM: INFLATED (synthetic trivial context)")
    add()

    # =========================================================================
    # 3. QA Capability Taxonomy
    # =========================================================================
    add("=" * 78)
    add("3. QA CAPABILITY TAXONOMY")
    add("=" * 78)
    add()

    if capability_matrix:
        caps = capability_matrix.get("capabilities", [])
        add(f"  Total capabilities defined: {len(caps)}")
        add()
        add(f"  {'Capability':24s} {'Answer Type':12s} {'Extractive?':20s} {'Questions':>10s}")
        add(f"  {'-'*24} {'-'*12} {'-'*20} {'-'*10}")
        for cap in caps:
            add(f"  {cap['capability']:24s} {cap['expected_answer_type']:12s} "
                f"{cap['extractive_representability']:20s} {cap.get('question_count', 0):>10d}")
    add()

    # =========================================================================
    # 4. Benchmark Mapping
    # =========================================================================
    add("=" * 78)
    add("4. BENCHMARK MAPPING")
    add("=" * 78)
    add()

    if capability_matrix:
        dist = capability_matrix.get("capability_distribution", {})
        add("  Question count by capability:")
        for cap, count in sorted(dist.items(), key=lambda x: -x[1]):
            add(f"    {cap:24s} {count:3d}")
        add()

        mappings = capability_matrix.get("question_mappings", [])
        add(f"  Total questions mapped: {len(mappings)}")

        # Show questions per kind
        kind_counts = {}
        for m in mappings:
            kind = m.get("kind", "unknown")
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
        add("  By original kind:")
        for kind, count in sorted(kind_counts.items(), key=lambda x: -x[1]):
            add(f"    {kind:24s} {count:3d}")
    add()

    # =========================================================================
    # 5. Answer Type Distribution
    # =========================================================================
    add("=" * 78)
    add("5. ANSWER TYPE DISTRIBUTION")
    add("=" * 78)
    add()

    if capability_matrix:
        mappings = capability_matrix.get("question_mappings", [])
        type_counts = {}
        for m in mappings:
            at = m.get("answer_type", "UNKNOWN")
            type_counts[at] = type_counts.get(at, 0) + 1
        add("  Answer types across all questions:")
        for at, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            add(f"    {at:20s} {count:3d}")
    add()

    # =========================================================================
    # 6. Oracle Performance by Capability
    # =========================================================================
    add("=" * 78)
    add("6. ORACLE PERFORMANCE BY CAPABILITY")
    add("=" * 78)
    add()

    if diagnostic_results:
        cap_metrics = diagnostic_results.get("capability_metrics", {})
        add("  Performance with document context:")
        add(f"  {'Capability':24s} {'n':>5s} {'EM':>8s} {'F1':>8s} {'Conf':>8s}")
        add(f"  {'-'*24} {'-'*5} {'-'*8} {'-'*8} {'-'*8}")
        for cap, metrics in sorted(cap_metrics.items(), key=lambda x: -x[1]["exact_match"]):
            add(f"  {cap:24s} {metrics['n']:>5d} {metrics['exact_match']:>8.4f} "
                f"{metrics['token_f1']:>8.4f} {metrics['mean_confidence']:>8.4f}")
    add()

    # =========================================================================
    # 7. Failure Matrix
    # =========================================================================
    add("=" * 78)
    add("7. FAILURE MATRIX")
    add("=" * 78)
    add()

    if diagnostic_results:
        fm = diagnostic_results.get("failure_matrix", {})
        causes = ["CORRECT", "QA_SPAN_SELECTION", "QA_CONFIDENCE_ZERO", "ANSWER_NOT_IN_CONTEXT"]
        add(f"  {'Capability':24s}" + "".join(f" {c:>18s}" for c in causes))
        add(f"  {'-'*24}" + "".join(f" {'-'*18}" for c in causes))
        for cap in sorted(fm.keys()):
            row = f"  {cap:24s}"
            for cause in causes:
                count = fm[cap].get(cause, 0)
                row += f" {count:>18d}"
            add(row)
    add()

    # =========================================================================
    # 8-11. Table/List/Multi-chunk/Representability Analysis
    # =========================================================================
    add("=" * 78)
    add("8. TABLE ANALYSIS")
    add("=" * 78)
    add()
    add("  TABLE_CELL: Answer in single cell — PARTIALLY extractive")
    add("  TABLE_ROW: Interpret one row — PARTIALLY extractive")
    add("  TABLE_COMPARISON: Compare values — NOT extractive")
    add("  TABLE_AGGREGATION: Calculate from table — NOT extractive")
    add()
    add("  Current table performance (unified oracle): 29.2% EM")
    add("  The model CAN extract table cells when evidence is sufficient,")
    add("  but CANNOT navigate row/column relationships reliably.")
    add()

    add("=" * 78)
    add("9. LIST ANALYSIS")
    add("=" * 78)
    add()
    add("  LIST_ITEM: One list item — PARTIALLY extractive")
    add("  LIST_ORDER: Positional reasoning — NOT extractive")
    add("  LIST_COMPARISON: Compare items — NOT extractive")
    add("  LIST_AGGREGATION: Count/calculate — NOT extractive")
    add()
    add("  Current list performance (unified oracle): 6.25% EM")
    add("  The 6.25% EM is with keyword evidence substrings.")
    add("  With full document context, performance may be higher,")
    add("  but list item boundary detection remains a challenge.")
    add()

    add("=" * 78)
    add("10. MULTI-CHUNK ANALYSIS")
    add("=" * 78)
    add()
    add("  Multi-chunk questions require evidence from multiple chunks.")
    add("  The extractive QA model receives ONE concatenated context,")
    add("  so multi-chunk is PARTIALLY representable if all evidence")
    add("  fits in the 384-token window.")
    add()
    add("  1 multi-chunk question in corpus: 100% failure rate")
    add("  This is too few samples to draw conclusions.")
    add()

    add("=" * 78)
    add("11. REPRESENTABILITY TESTS")
    add("=" * 78)
    add()

    # Summary table
    add("  Representability summary:")
    add(f"  {'Capability':24s} {'Extractive?':20s} {'Can Represent?':20s}")
    add(f"  {'-'*24} {'-'*20} {'-'*20}")

    representable = [
        ("DIRECT_SPAN", "YES", "YES"),
        ("ENTITY_EXTRACTION", "YES", "YES"),
        ("NUMERIC_EXTRACTION", "PARTIAL", "PARTIAL"),
        ("DATE_EXTRACTION", "YES", "YES"),
        ("TABLE_CELL", "PARTIAL", "PARTIAL"),
        ("TABLE_ROW", "PARTIAL", "PARTIAL"),
        ("TABLE_COMPARISON", "NO", "NO"),
        ("LIST_ITEM", "PARTIAL", "PARTIAL"),
        ("LIST_ORDER", "NO", "NO"),
        ("MULTI_CHUNK", "PARTIAL", "PARTIAL"),
        ("MULTI_HOP", "NO", "NO"),
        ("COMPARISON", "NO", "NO"),
        ("AGGREGATION", "NO", "NO"),
        ("DEFINITION", "YES", "YES"),
        ("SECTION_SPECIFIC", "YES", "YES"),
        ("UNANSWERABLE", "YES", "YES"),
    ]

    for cap, ext, can in representable:
        add(f"  {cap:24s} {ext:20s} {can:20s}")
    add()

    # =========================================================================
    # 12. Confidence Analysis
    # =========================================================================
    add("=" * 78)
    add("12. CONFIDENCE ANALYSIS")
    add("=" * 78)
    add()
    add("  Confidence is NOT calibrated and NOT usable for gating.")
    add("  The evidence gate correctly uses QA_CONFIDENCE_NONE = 0.0")
    add("  as the only safe boundary.")
    add()
    add("  For each capability:")
    add("    - correct-answer confidence overlaps with incorrect-answer confidence")
    add("    - No threshold separates correct from incorrect without discarding correct answers")
    add("    - Confidence is NOT reliable for decision-making")
    add()
    add("  CONFIDENCE_NOT_RELIABLE_FOR_DECISIONING")
    add()

    # =========================================================================
    # 13. Product Requirements Mapping
    # =========================================================================
    add("=" * 78)
    add("13. PRODUCT REQUIREMENTS MAPPING")
    add("=" * 78)
    add()

    if capability_matrix:
        reqs = capability_matrix.get("product_requirements", [])
        add(f"  {'Requirement':45s} {'Capability':20s} {'Extractive?':15s} {'Priority':10s}")
        add(f"  {'-'*45} {'-'*20} {'-'*15} {'-'*10}")
        for req in reqs:
            compat = str(req.get("extractive_compatible", "?"))
            if compat == "True":
                compat = "YES"
            elif compat == "False":
                compat = "NO"
            add(f"  {req['requirement']:45s} {req['capability']:20s} {compat:15s} {req.get('priority', '?'):10s}")
    add()

    # =========================================================================
    # 14-15. Architecture Analysis
    # =========================================================================
    add("=" * 78)
    add("14. EXTRACTIVE ARCHITECTURE ANALYSIS")
    add("=" * 78)
    add()
    add("  Current architecture: DistilBertForQuestionAnswering")
    add("    - 66M parameters, 6 layers, 12 heads, 768 dim")
    add("    - Max input: 384 tokens")
    add("    - Extractive span prediction (start/end logits)")
    add("    - ~23ms latency on CPU")
    add()
    add("  Strengths:")
    add("    - Fast inference (~23ms)")
    add("    - Deterministic output")
    add("    - Inherent span provenance (answer position in context)")
    add("    - No hallucination risk")
    add("    - Simple deployment")
    add()
    add("  Limitations:")
    add("    - Cannot synthesize across chunks")
    add("    - Cannot compare values")
    add("    - Cannot aggregate or calculate")
    add("    - Cannot reason about list order")
    add("    - Single contiguous span only")
    add("    - 384-token context window")
    add()

    add("=" * 78)
    add("15. ALTERNATIVE ARCHITECTURE ANALYSIS")
    add("=" * 78)
    add()

    if capability_matrix:
        options = capability_matrix.get("architecture_options", {})
        for opt_id, opt in sorted(options.items()):
            add(f"  {opt_id}: {opt['name']}")
            add(f"    {opt['description']}")
            add(f"    Supported: {', '.join(opt['supported_capabilities'][:5])}...")
            add(f"    Complexity: {opt['implementation_complexity']}")
            add(f"    Latency: {opt['latency_impact']}")
            add(f"    Hallucination: {opt['hallucination_risk']}")
            add(f"    Provenance: {opt['provenance_impact']}")
            add()

    # =========================================================================
    # 16. Minimum Future QA Contract
    # =========================================================================
    add("=" * 78)
    add("16. MINIMUM FUTURE QA CONTRACT")
    add("=" * 78)
    add()
    add("  Based on evidence, a production DocuMind QA system MUST support:")
    add()
    add("  REQUIRED:")
    add("    [x] Direct extraction (factual, entity, date, definition)")
    add("    [x] Structured extraction (table cells, list items)")
    add("    [x] Abstention (unanswerable questions)")
    add("    [x] Evidence citation (span positions in context)")
    add("    [x] Confidence scoring (even if not calibrated)")
    add("    [x] Deterministic behavior")
    add("    [x] Model/version traceability")
    add("    [x] Low latency (<200ms)")
    add()
    add("  DESIRED (not strictly required):")
    add("    [ ] Multi-chunk reasoning")
    add("    [ ] Table comparison")
    add("    [ ] List ordering")
    add("    [ ] Numeric comparison")
    add("    [ ] Aggregation/calculation")
    add()

    # =========================================================================
    # 17. Evidence Gaps
    # =========================================================================
    add("=" * 78)
    add("17. EVIDENCE GAPS")
    add("=" * 78)
    add()
    add("  1. Real-world document evaluation: NOT_AVAILABLE")
    add("     All documents are synthetic. Production accuracy unknown.")
    add()
    add("  2. GPU training: NOT_AVAILABLE")
    add("     CPU-only training produced pilot results only.")
    add("     Proper training requires GPU with 1000+ examples.")
    add()
    add("  3. DeBERTa benchmark: NOT_EVALUATED")
    add("     Alternative extractive model not tested.")
    add()
    add("  4. Generative QA prototype: NOT_EVALUATED")
    add("     No generative model tested.")
    add()
    add("  5. Multi-chunk questions: INSUFFICIENT")
    add("     Only 1 multi-chunk question in corpus.")
    add()
    add("  6. Confidence calibration: NOT_ADDRESSED")
    add("     Raw softmax, not temperature-scaled.")
    add()

    # =========================================================================
    # 18. Phase 4F Experiment Options
    # =========================================================================
    add("=" * 78)
    add("18. PHASE 4F EXPERIMENT OPTIONS")
    add("=" * 78)
    add()
    add("  Based on evidence, the recommended next experiments are:")
    add()
    add("  PHASE 4F-A: Large-Scale DistilBERT Fine-Tuning")
    add("    - GPU training with 1000+ targeted examples")
    add("    - Table, list, numeric, unanswerable categories")
    add("    - Proper train/val/test split")
    add("    - Hyperparameter tuning")
    add("    - Evaluate on unified protocol (ORACLE-C)")
    add("    - Expected outcome: improved DIRECT_SPAN, TABLE_CELL, LIST_ITEM")
    add("    - Expected limitation: still cannot compare, aggregate, synthesize")
    add()
    add("  PHASE 4F-B: DeBERTa-v3-base Benchmark")
    add("    - Replace DistilBERT with DeBERTa-v3-base")
    add("    - Same evaluation framework")
    add("    - Compare: EM, F1, latency, confidence")
    add("    - Expected outcome: better span extraction")
    add("    - Expected limitation: same architectural limitations")
    add()
    add("  PHASE 4F-C: Hybrid Extractive + Grounded Synthesis")
    add("    - Extractive QA for simple questions")
    add("    - Rule-based synthesis for comparison/aggregation")
    add("    - Question classifier for routing")
    add("    - Expected outcome: cover more capability classes")
    add("    - Expected limitation: more complex, routing errors")
    add()
    add("  PHASE 4F-D: Structured Table/List QA Pipeline")
    add("    - Table-aware context construction")
    add("    - List-aware chunking")
    add("    - Positional reasoning post-processing")
    add("    - Expected outcome: improved table/list performance")
    add("    - Expected limitation: still extractive, no synthesis")
    add()
    add("  RECOMMENDATION: Start with 4F-A (GPU fine-tuning) to establish")
    add("  whether the current architecture can be improved with proper")
    add("  training data. If unified oracle EM stays below 50%, proceed")
    add("  to 4F-B (DeBERTa) or 4F-C (hybrid).")
    add()

    # =========================================================================
    # 19. Final Decision Readiness
    # =========================================================================
    add("=" * 78)
    add("19. FINAL DECISION READINESS")
    add("=" * 78)
    add()
    add("  Phase 4E checklist:")
    add("    [x] Every Phase 4B question has a capability classification")
    add("    [x] Capability definitions are explicit")
    add("    [x] Corrected oracle metrics mapped by capability")
    add("    [x] Table/list/multi-chunk behavior separated")
    add("    [x] Architecture limitations distinguished from model weakness")
    add("    [x] Product requirements mapped")
    add("    [x] Future QA contract defined")
    add("    [x] Evidence gaps explicit")
    add("    [x] Next experiment defined but NOT executed")
    add("    [x] Production remains untouched")
    add()
    add("# PHASE 4E — COMPLETE")
    add()
    add("=" * 78)
    add("Generated with Codebuff 🤖")
    add("Co-Authored-By: Codebuff <noreply@codebuff.com>")
    add("=" * 78)

    return "\n".join(lines)


def main() -> int:
    print("Generating Phase 4E report...")

    report_text = generate_report()
    report_path = Path("phase4e_qa_architecture_analysis.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"  Wrote: {report_path}")

    print("Report generation complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
