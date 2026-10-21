#!/usr/bin/env python3
"""Held-out confirmation experiment for the calibrated structural RRF prior.

Research code.  Run explicitly from ``backend/``:

    ./venv/Scripts/python.exe evaluation/experiments/run_structure_confirmation.py

What it tests
-------------
The RRF calibration selected ``semantic=0.50 / structural=0.50`` (k=60,
top_k=5) as the smallest structural prior with non-zero structure-element
admission and classified it ``PROMISING`` on the primary DISCRIMINATING subset
(Recall@5 +0.070313, nDCG@5 +0.034369, EM +0.03125, token-F1 +0.008671, 0
harmful).  That is promising evidence, NOT proof.

This experiment tests whether that structural benefit survives on a genuinely
held-out question set.  It compares exactly:

CONTROL    structural-element candidate stream disabled; semantic +
           existing chunk-structural retrieval; RRF 0.50/0.50.
TREATMENT  production structural-element candidate retrieval enabled;
           semantic + chunk-structural + structure-element retrieval; RRF
           0.50/0.50.

Everything else is frozen (corpus, questions, gold, parser, chunker,
embeddings, QA model, DB, k=60, top_k=5, weights, candidate generation,
evidence fusion, metrics).  Weights are injected strictly inside the harness by
wrapping ``chat.rag.fuse_dual_path`` — production is never modified.

Held-out split
--------------
The corpus is fully authored; no new questions are generated.  A deterministic,
**outcome-blind**, stratified split is created from the existing question IDs:
within each ``(discrimination_label, category)`` stratum, question IDs are
sorted ascending and even sorted positions are assigned to the confirmation
(held-out) set, odd positions to the development set.  The rule depends only on
question IDs and strata — never on any measured result — so no question is
cherry-picked into confirmation.

Honesty note (recorded in the report): the earlier calibration *execution*
measured all 72 questions (that is how the 0.50/0.50 prior was selected, via
admission geometry, and how the PROMISING label was assigned).  The split is
therefore held-out from the *designated development population*, not
never-before-seen data.  This confirmation tests effect consistency on a
designated, outcome-blind held-out subset — not generalisation to unseen data —
and the report says so.

Determinism
-----------
The complete confirmation is executed twice (independent user/ingest/measure/
teardown cycles, identical deterministic-id seed) and the machine-readable
payload must be byte-identical.  The existing normalisations are preserved:
model warm-up outside the deterministic-id region, and the semantic stream
re-sorted by ``(-similarity, chunk_id)``.

Publication
-----------
The two published artifacts (``evaluation/reports/structure_confirmation.json``
and ``..._report.md``) are evaluation evidence and are written append-only:
they go through ``evaluation.artifacts.write_evidence``, which refuses to replace
an existing artifact rather than silently overwriting a recorded result.  Both
names are pre-flighted before the first byte is written, and ``--replace`` is the
explicit, operator-supplied opt-in for a deliberate re-publication.  ``--smoke``
output stays in a fresh temporary directory and is not evidence.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

_BACKEND_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from sqlalchemy import delete, select  # noqa: E402

from evaluation.artifacts import ArtifactExistsError, write_evidence  # noqa: E402

import evaluation.experiments.run_structure_element_measurement as base  # noqa: E402
import evaluation.experiments.run_structure_rrf_calibration as calib  # noqa: E402

# Database-dependent names.  Bound by bind_database_runtime() only after the
# central isolation guard has approved the target; nothing here imports storage
# or chat at module scope.
async_session = None
engine = None
rag = None

REPORTS_DIR = Path(_BACKEND_DIR) / "evaluation" / "reports"

TOP_K = base.TOP_K
RUNS = 2
EVAL_EMAIL = base.EVAL_EMAIL
RRF_K = None  # bound with rag by bind_database_runtime()
SEMANTIC_WEIGHT = 0.50
STRUCTURAL_WEIGHT = 0.50

POPULATIONS = base.POPULATIONS
canonical = base.canonical
_r = base._r


# ---------------------------------------------------------------------------
# Deterministic, outcome-blind, stratified held-out split
# ---------------------------------------------------------------------------

def split_questions(meta: dict) -> dict:
    """Split question IDs into confirmation (held-out) and development.

    Stratum = ``(str(discrimination_label), category)``.  Within a stratum the
    question IDs are sorted ascending and assigned alternately: even sorted
    position -> confirmation (held-out), odd -> development.  The rule uses
    only question IDs and stratum labels — never any measured result — so it
    is deterministic and outcome-blind, and it preserves category and
    answerable/unanswerable representation in both sides.
    """
    strata: dict[tuple, list[str]] = defaultdict(list)
    for qid, q in meta.items():
        strata[(str(q.discrimination), q.category)].append(qid)

    confirmation: set[str] = set()
    development: set[str] = set()
    per_stratum: dict[str, dict] = {}
    for key in sorted(strata):
        sids = sorted(strata[key])
        conf = [qid for i, qid in enumerate(sids) if i % 2 == 0]
        dev = [qid for i, qid in enumerate(sids) if i % 2 == 1]
        confirmation.update(conf)
        development.update(dev)
        per_stratum[f"{key[0]}|{key[1]}"] = {
            "discrimination_label": key[0],
            "category": key[1],
            "n": len(sids),
            "question_ids": sids,
            "confirmation": conf,
            "development": dev,
        }

    all_qids = set(meta)
    return {
        "rule": (
            "stratum = (str(discrimination_label), category); within each "
            "stratum sort question IDs ascending and assign even sorted "
            "positions to confirmation (held-out), odd to development. "
            "Outcome-blind: depends only on question IDs and stratum labels, "
            "never on measured results."
        ),
        "confirmation_qids": sorted(confirmation),
        "development_qids": sorted(development),
        "counts": {
            "confirmation": len(confirmation),
            "development": len(development),
            "total": len(all_qids),
        },
        "no_overlap": not (confirmation & development),
        "covers_all_questions": (confirmation | development) == all_qids,
        "overlap_qids": sorted(confirmation & development),
        "per_stratum": per_stratum,
    }


# ---------------------------------------------------------------------------
# Split-aware subset metrics
# ---------------------------------------------------------------------------

def subset_metrics(control: list[dict], treatment: list[dict], qids: set[str]) -> dict:
    c_sub = sorted(
        [t for t in control if t["question_id"] in qids], key=lambda x: x["question_id"]
    )
    t_sub = sorted(
        [t for t in treatment if t["question_id"] in qids], key=lambda x: x["question_id"]
    )
    retr_c = base.retrieval_aggregates(c_sub)
    retr_t = base.retrieval_aggregates(t_sub)
    ans_c = base.answer_aggregates(c_sub)
    ans_t = base.answer_aggregates(t_sub)
    return {
        "n": len(t_sub),
        "question_ids": [t["question_id"] for t in t_sub],
        "element_admission_count": sum(
            1 for t in t_sub if t["structure_element_count_in_top_k"] > 0
        ),
        "retrieval": {
            "CONTROL": retr_c,
            "TREATMENT": retr_t,
            "DELTA": {
                view: base.metric_delta(
                    retr_c.get(view) if isinstance(retr_c.get(view), dict) else {},
                    retr_t.get(view) if isinstance(retr_t.get(view), dict) else {},
                )
                for view in ("evidence_unit", "chunk_only", "authored_gold")
            },
            "evidence_coverage_DELTA": base.metric_delta(
                {"evidence_coverage": retr_c.get("evidence_coverage")},
                {"evidence_coverage": retr_t.get("evidence_coverage")},
            ),
        },
        "answers": {
            "CONTROL": ans_c,
            "TREATMENT": ans_t,
            "DELTA": base.metric_delta(ans_c, ans_t),
        },
        "transitions": base.answer_transitions(c_sub, t_sub),
        "ranking_influence": calib.ranking_influence(c_sub, t_sub),
        "funnel_treatment": base.funnel_for(t_sub),
        "funnel_control": base.funnel_for(c_sub),
    }


# ---------------------------------------------------------------------------
# Confirmation criteria + decision
# ---------------------------------------------------------------------------

def evaluate_confirmation(subsets: dict, isolation: dict) -> dict:
    conf = subsets["confirmation_DISCRIMINATING"]
    dev = subsets["development_DISCRIMINATING"]
    d_retr = conf["retrieval"]["DELTA"]["evidence_unit"]
    d_ans = conf["answers"]["DELTA"]
    trans = conf["transitions"]["counts"]

    admission = conf["element_admission_count"] > 0
    retr_pos = any((d_retr.get(m) or 0.0) > 0.0 for m in ("recall@5", "precision@5", "mrr", "ndcg@5"))
    ans_pos = any(
        (d_ans.get(m) or 0.0) > 0.0
        for m in ("exact_match_rate", "token_f1", "answer_accuracy")
    )
    retr_regress = any((d_retr.get(m) or 0.0) < 0.0 for m in ("recall@5", "mrr", "ndcg@5"))
    ans_regress = any(
        (d_ans.get(m) or 0.0) < 0.0
        for m in ("exact_match_rate", "token_f1", "answer_accuracy")
    )
    harmful = trans.get("correct_to_wrong", 0)
    isolation_ok = isolation.get("arms_differ_only_in_element_stream", False)

    # Criterion 6: effect survives outside the development questions.  Compare
    # the confirmation-subset effect direction with the development-subset one.
    d_retr_dev = dev["retrieval"]["DELTA"]["evidence_unit"]
    d_ans_dev = dev["answers"]["DELTA"]
    dev_pos = any((d_retr_dev.get(m) or 0.0) > 0.0 for m in ("recall@5", "mrr", "ndcg@5")) or any(
        (d_ans_dev.get(m) or 0.0) > 0.0 for m in ("exact_match_rate", "token_f1", "answer_accuracy")
    )
    survives = (retr_pos or ans_pos)  # positive effect on the held-out subset

    criteria = {
        "1_structural_elements_enter_top_k": admission,
        "2_retrieval_improves_or_non_inferior": not retr_regress,
        "3_answer_quality_improves_or_non_inferior": not ans_regress,
        "4_no_harmful_answer_transitions": harmful == 0,
        "5_effect_attributable_to_element_stream": isolation_ok,
        "6_effect_survives_outside_development_questions": bool(survives),
        "positive_movement_on_confirmation": bool(retr_pos or ans_pos),
        "development_subset_also_positive": bool(dev_pos),
    }

    evidence = {
        "confirmation_delta_evidence_unit": d_retr,
        "confirmation_delta_answer": d_ans,
        "confirmation_harmful_transitions": harmful,
        "confirmation_element_admission_count": conf["element_admission_count"],
        "retrieval_regression": retr_regress,
        "answer_regression": ans_regress,
    }

    if not isolation_ok:
        status = "BLOCKED"
        classification = "BLOCKED"
    elif admission and (retr_regress or ans_regress or harmful > 0):
        classification = "NOT_CONFIRMED"
        status = "CONFIRMATION COMPLETE — EFFECT NOT CONFIRMED"
    elif admission and (retr_pos or ans_pos):
        classification = "POSITIVE"
        status = "CONFIRMATION COMPLETE — POSITIVE EFFECT REPLICATED"
    elif admission:
        classification = "NEUTRAL"
        status = "CONFIRMATION COMPLETE — EFFECT NEUTRAL"
    else:
        # no admission on held-out -> the mechanism did not fire; effect not replicated
        classification = "NOT_CONFIRMED"
        status = "CONFIRMATION COMPLETE — EFFECT NOT CONFIRMED"

    return {
        "criteria": criteria,
        "evidence": evidence,
        "classification": classification,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def _f(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def render_report(payload: dict) -> str:
    split = payload["split"]
    subsets = payload["subsets"]
    iso = payload["isolation"]
    det = payload.get("determinism", {})
    decision = payload["confirmation"]
    comparison = payload["comparison_with_calibration"]
    L: list[str] = []

    def w(line: str = "") -> None:
        L.append(line)

    def retr_rows(name, block):
        for arm in ("CONTROL", "TREATMENT"):
            ev = block["retrieval"][arm]["evidence_unit"]
            cov = block["retrieval"][arm]["evidence_coverage"]
            w(f"| {name} | {arm} | {block['n']} | {_f(ev['recall@5'])} | "
              f"{_f(ev['precision@5'])} | {_f(ev['mrr'])} | {_f(ev['ndcg@5'])} | {_f(cov)} |")

    w("# Structure Held-Out Confirmation Experiment")
    w()
    w("**Experiment:** `structure_confirmation`  ")
    w("**Corpus:** `structure_discriminating_v1` (unchanged, no new questions)  ")
    w("**Configuration:** semantic 0.50 / structural 0.50, k=60, top_k=5  ")
    w("**Runner:** `backend/evaluation/experiments/run_structure_confirmation.py`  ")
    w("**Machine-readable artifact:** `structure_confirmation.json`")
    w()
    w("---")
    w()

    # 1
    w("## 1. Objective")
    w()
    w("Test whether the structural benefit observed at the calibrated prior "
      "(0.50/0.50) survives on a genuinely held-out question set, comparing "
      "exactly CONTROL (element candidate stream disabled) vs TREATMENT "
      "(production element retrieval enabled), everything else frozen.")
    w()
    w("---")
    w()

    # 2
    w("## 2. Why Held-Out Confirmation Is Required")
    w()
    w("The calibration result is promising evidence, not proof. The prior "
      "0.50/0.50 and the PROMISING label were selected while observing the "
      "full corpus, so the same questions cannot independently confirm the "
      "effect. A held-out confirmation checks whether the effect is consistent "
      "on questions not used to *develop* the evidence, before any claim is "
      "made. It also guards against a weight chosen for admission geometry "
      "incidentally overfitting to specific questions.")
    w()
    w("**Honesty note:** the earlier calibration *execution* measured all 72 "
      "questions. This split is held-out from the designated development "
      "population (outcome-blind, see §3), not never-before-seen data. The "
      "confirmation therefore tests effect consistency on a designated "
      "held-out subset, not generalisation to unseen data.")
    w()
    w("---")
    w()

    # 3
    w("## 3. Split Methodology")
    w()
    w(f"**Rule:** {split['rule']}")
    w()
    w(f"* confirmation (held-out) questions: **{split['counts']['confirmation']}**")
    w(f"* development questions: **{split['counts']['development']}**")
    w(f"* total: **{split['counts']['total']}**")
    w(f"* no overlap: **{split['no_overlap']}** (overlap ids: {split['overlap_qids'] or 'none'})")
    w(f"* covers all questions: **{split['covers_all_questions']}**")
    w()
    w("Per-stratum assignment (auditable):")
    w()
    w("| stratum (discrimination | category) | n | confirmation | development |")
    w("|---|---:|---|---|")
    for key, s in split["per_stratum"].items():
        w(f"| {key} | {s['n']} | {', '.join(s['confirmation'])} | {', '.join(s['development'])} |")
    w()
    w(f"**Confirmation question IDs ({split['counts']['confirmation']}):** "
      f"`{', '.join(split['confirmation_qids'])}`")
    w()
    w(f"**Development question IDs ({split['counts']['development']}):** "
      f"`{', '.join(split['development_qids'])}`")
    w()
    w("---")
    w()

    # 4
    w("## 4. Held-Out Population")
    w()
    conf = subsets["confirmation_DISCRIMINATING"]
    w(f"Primary held-out evaluation population: **confirmation DISCRIMINATING** "
      f"({conf['n']} questions):")
    w()
    w(f"`{', '.join(conf['question_ids'])}`")
    w()
    w("Stratified so category representation is preserved across the split "
      "(multi_hop_structural, page_crossing, section_heading, "
      "structural_distractor, table_row_cell all appear in confirmation), and "
      "answerable/unanswerable is preserved (unanswerable questions form their "
      "own stratum, split the same way).")
    w()
    w("---")
    w()

    # 5
    w("## 5. Experimental Controls")
    w()
    w("Frozen: corpus documents, held-out questions, gold annotations, parser, "
      "chunker, embeddings, QA model, database contents/schema, `k=60`, "
      "`top_k=5`, weights `0.50/0.50`, candidate-generation logic, evidence "
      "fusion logic, evaluation metrics.")
    w()
    w("Weights injected strictly inside the harness (wrapping "
      "`chat.rag.fuse_dual_path`), as in the completed calibration. Nothing "
      "was tuned using held-out results; the split is outcome-blind. "
      "Production RRF configuration and production code are unmodified.")
    w()
    w("---")
    w()

    # 6
    w("## 6. Reachability")
    w()
    w("Funnel on the held-out confirmation population (and all-question "
      "reference):")
    w()
    for name, block in (
        ("confirmation_DISCRIMINATING", subsets["confirmation_DISCRIMINATING"]),
        ("development_DISCRIMINATING", subsets["development_DISCRIMINATING"]),
        ("confirmation_all", subsets["confirmation_all"]),
    ):
        tf = block["funnel_treatment"]["counts"]
        cf = block["funnel_control"]["counts"]
        w(f"### {name} (n={block['n']})")
        w()
        w("| stage | TREATMENT | CONTROL |")
        w("|---|---:|---:|")
        for stage in base.FUNNEL_STAGES:
            w(f"| {stage} | {tf[stage]} | {cf[stage]} |")
        w()
        w(f"* structural-element admission (element in final top-k): "
          f"**{block['element_admission_count']}**")
        w()
    w("---")
    w()

    # 7
    w("## 7. Ranking Influence")
    w()
    w("Distinguished effects on the held-out confirmation population:")
    w()
    ri = conf["ranking_influence"]
    w("| metric | count |")
    w("|---|---:|")
    w(f"| element enters top-k directly | {ri['1_element_enters_top_k_directly']['count']} |")
    w(f"| element changes rank indirectly | {ri['2_element_changes_rank_indirectly']['count']} |")
    w(f"| top-k set changed | {ri['3_top_k_set_changes']['count']} |")
    w(f"| gold evidence changed | {ri['4_gold_evidence_changes']['count']} |")
    w(f"| answer changed | {ri['5_answer_changes']['count']} |")
    w(f"| rank-order changed (any) | {ri['rank_order_changed_any']['count']} |")
    w(f"| beneficial | {ri['beneficial_changes']['count']} |")
    w(f"| harmful | {ri['harmful_changes']['count']} |")
    w()
    w(f"Question IDs — top-k set changed: "
      f"{ri['3_top_k_set_changes']['question_ids'] or 'none'}; gold changed: "
      f"{ri['4_gold_evidence_changes']['question_ids'] or 'none'}; answer "
      f"changed: {ri['5_answer_changes']['question_ids'] or 'none'}")
    w()
    w("---")
    w()

    # 8
    w("## 8. Retrieval Results")
    w()
    w("CONTROL vs TREATMENT (evidence_unit gold view + evidence coverage).")
    w()
    w("| population | arm | n | Recall@5 | Precision@5 | MRR | nDCG@5 | evidence coverage |")
    w("|---|---|---:|---:|---:|---:|---:|---:|")
    for name in ("confirmation_DISCRIMINATING", "development_DISCRIMINATING", "confirmation_all_answerable", "confirmation_all"):
        retr_rows(name, subsets[name])
    w()
    w("DELTA (TREATMENT − CONTROL), evidence_unit:")
    w()
    w("| population | ΔRecall@5 | ΔPrecision@5 | ΔMRR | ΔnDCG@5 |")
    w("|---|---:|---:|---:|---:|")
    for name in ("confirmation_DISCRIMINATING", "development_DISCRIMINATING", "confirmation_all_answerable", "confirmation_all"):
        d = subsets[name]["retrieval"]["DELTA"]["evidence_unit"]
        w(f"| {name} | {_f(d.get('recall@5'))} | {_f(d.get('precision@5'))} | "
          f"{_f(d.get('mrr'))} | {_f(d.get('ndcg@5'))} |")
    w()
    w("---")
    w()

    # 9
    w("## 9. Answer Results")
    w()
    w("| population | arm | EM | token F1 | accuracy | grounding | unsupported rate |")
    w("|---|---|---:|---:|---:|---:|---:|")
    for name in ("confirmation_DISCRIMINATING", "development_DISCRIMINATING", "confirmation_unanswerable", "confirmation_all"):
        b = subsets[name]
        for arm in ("CONTROL", "TREATMENT"):
            a = b["answers"][arm]
            w(f"| {name} | {arm} | {_f(a['exact_match_rate'])} | {_f(a['token_f1'])} | "
              f"{_f(a['answer_accuracy'])} | {_f(a['factual_grounding_rate'])} | "
              f"{_f(a['unsupported_answer_rate'])} |")
    w()
    w("---")
    w()

    # 10
    w("## 10. Transition Analysis")
    w()
    w("| population | correct→correct | correct→wrong | wrong→correct | wrong→wrong |")
    w("|---|---:|---:|---:|---:|")
    for name in ("confirmation_DISCRIMINATING", "development_DISCRIMINATING", "confirmation_all_answerable", "confirmation_all"):
        t = subsets[name]["transitions"]["counts"]
        w(f"| {name} | {t.get('correct_to_correct', 0)} | {t.get('correct_to_wrong', 0)} | "
          f"{t.get('wrong_to_correct', 0)} | {t.get('wrong_to_wrong', 0)} |")
    w()
    w("No regression is hidden behind aggregates: any correct→wrong flip on the "
      "held-out population is reported above and counted as a harmful "
      "transition.")
    w()
    w("---")
    w()

    # 11
    w("## 11. Category Analysis")
    w()
    w("Per-category answer metrics on the held-out confirmation questions "
      "(TREATMENT) with CONTROL comparison:")
    w()
    w("| category | n | EM (C→T) | token F1 (C→T) | accuracy (C→T) | element in top-k |")
    w("|---|---:|---|---|---|---:|")
    for cat, row in subsets["confirmation_by_category"].items():
        w(f"| {cat} | {row['n']} | {_f(row['answers_CONTROL']['exact_match_rate'])}→"
          f"{_f(row['answers_TREATMENT']['exact_match_rate'])} | "
          f"{_f(row['answers_CONTROL']['token_f1'])}→{_f(row['answers_TREATMENT']['token_f1'])} | "
          f"{_f(row['answers_CONTROL']['answer_accuracy'])}→{_f(row['answers_TREATMENT']['answer_accuracy'])} | "
          f"{row['element_admission_count']} |")
    w()
    w("---")
    w()

    # 12
    w("## 12. Determinism")
    w()
    w("Two independent complete runs (user/ingest/measure/teardown), identical "
      "deterministic-id seed, existing normalisations preserved (model warm-up "
      "outside the id region; semantic stream re-sorted by `(-similarity, "
      "chunk_id)`). No timestamps, random UUIDs, absolute paths or "
      "nondeterministic ordering in canonical outputs.")
    w()
    if det:
        w(f"* runs compared: **{det.get('runs_compared')}**")
        w(f"* core payload byte-identical: **{det.get('core_byte_identical')}**")
        w(f"* run 1 SHA-256: `{det.get('sha256_run1')}`")
        w(f"* run 2 SHA-256: `{det.get('sha256_run2')}`")
    w()
    w("---")
    w()

    # 13
    w("## 13. Isolation Verification")
    w()
    w("CONTROL/TREATMENT must differ only in the element candidate stream.")
    w()
    w("| check | result |")
    w("|---|---|")
    w(f"| semantic stream identical | {iso['semantic_streams_identical']} |")
    w(f"| chunk-structural stream identical | {iso['chunk_structural_streams_identical']} |")
    w(f"| element seed metadata identical | {iso['element_seed_sets_identical']} |")
    w(f"| CONTROL element stream empty | {iso['control_element_stream_empty']} |")
    w(f"| arms differ only in element stream | {iso['arms_differ_only_in_element_stream']} |")
    w()
    w(f"Questions compared: {iso['questions_compared']}; first mismatch: "
      f"{iso['first_mismatch'] or 'none'}")
    w()
    w("---")
    w()

    # 14
    w("## 14. Comparison with Calibration Result")
    w()
    cal = comparison["calibration_reported_all_DISCRIMINATING"]
    w("Calibration reported on the full DISCRIMINATING set (32 questions) at "
      "0.50/0.50:")
    w()
    w(f"* Recall@5 {cal['recall@5']}, Precision@5 {cal['precision@5']}, "
      f"MRR {cal['mrr']}, nDCG@5 {cal['ndcg@5']}, EM {cal['exact_match_rate']}, "
      f"token-F1 {cal['token_f1']}, harmful {cal['harmful_transitions']}, "
      f"admission {cal['element_admission_count']}")
    w()
    w("Held-out confirmation result on the confirmation DISCRIMINATING subset "
      f"({conf['n']} questions):")
    w()
    d = conf["retrieval"]["DELTA"]["evidence_unit"]
    da = conf["answers"]["DELTA"]
    w(f"* ΔRecall@5 {_f(d.get('recall@5'))}, ΔPrecision@5 {_f(d.get('precision@5'))}, "
      f"ΔMRR {_f(d.get('mrr'))}, ΔnDCG@5 {_f(d.get('ndcg@5'))}, "
      f"ΔEM {_f(da.get('exact_match_rate'))}, Δtoken-F1 {_f(da.get('token_f1'))}, "
      f"harmful {conf['transitions']['counts'].get('correct_to_wrong', 0)}, "
      f"admission {conf['element_admission_count']}")
    w()
    w(f"Development subset effect (for reference): ΔRecall@5 "
      f"{_f(subsets['development_DISCRIMINATING']['retrieval']['DELTA']['evidence_unit'].get('recall@5'))}, "
      f"ΔnDCG@5 {_f(subsets['development_DISCRIMINATING']['retrieval']['DELTA']['evidence_unit'].get('ndcg@5'))}")
    w()
    w(f"Verdict: **{decision['classification']}**")
    w()
    w("---")
    w()

    # 15
    w("## 15. Research Interpretation")
    w()
    w("This distinguishes: structural **admission** (did elements enter top-k), "
      "**ranking influence** (did the fused order change), **retrieval "
      "improvement**, **answer-quality improvement**, and **replication of the "
      "prior effect**.")
    w()
    cls = decision["classification"]
    if cls == "POSITIVE":
        w("**Observed:** structural elements were admitted into the held-out "
          "top-k and the primary DISCRIMINATING retrieval/answer deltas on the "
          "held-out subset are positive with no harmful transitions. This is "
          "**replicated evidence** on a designated held-out subset — not "
          "universal proof of the structural hypothesis, and not causality "
          "beyond what the experiment supports. Because the corpus was fully "
          "measured during calibration, this confirms effect *consistency* on "
          "an outcome-blind held-out subset rather than generalisation to "
          "unseen data.")
    elif cls == "NEUTRAL":
        w("**Observed:** structural elements were admitted into the held-out "
          "top-k, but retrieval/answer metrics on the held-out subset are "
          "neutral (no meaningful gain, no regression). The architecture is "
          "reachable and calibratable, but the effect does not translate into "
          "answer gains on the held-out questions. Corpus/question design or "
          "structural evidence quality may be the limiting factor. This is a "
          "valid neutral result.")
    else:  # NOT_CONFIRMED or BLOCKED
        w("**Observed:** the prior effect did not replicate on the held-out "
          "subset — either primary metrics regressed, harmful transitions "
          "appeared, or no structural admission occurred. Reporting this "
          "honestly: the calibration effect does not survive the held-out "
          "confirmation under these conditions. This is a valid research "
          "result; the promising calibration signal is not confirmed.")
    w()
    w("---")
    w()

    # 16
    w("## 16. Limitations")
    w()
    w("* **Not never-seen data.** The calibration execution measured all 72 "
      "questions; the held-out split is outcome-blind and disjoint from the "
      "designated development set, but not independent of the calibration "
      "run. A fully independent confirmation requires new, independently "
      "authored questions.")
    w("* **Split size.** The held-out DISCRIMINATING subset is small; metric "
      "deltas are coarse and individual question flips are visible.")
    w("* **Weight is harness-injected**, not a production change; results "
      "describe the current architecture at 0.50/0.50.")
    w("* **Shared augmentation stream** present in both arms (only the ranked "
      "element contribution isolated).")
    w("* **Single corpus, one `top_k`, no evidence gate.**")
    w()
    w("---")
    w()

    # 17
    w("## 17. Exact Next Step")
    w()
    if cls == "POSITIVE":
        w("Run a **fully independent replication**: author a small, "
          "independently written structure-discriminating question set (new "
          "wording, same document corpus) with gold annotations prepared "
          "without reference to these results, then repeat this CONTROL vs "
          "TREATMENT comparison at 0.50/0.50 on that unseen set. Accept only "
          "if the positive effect reproduces with zero harmful transitions. "
          "Do not change production weights until independently replicated.")
    else:
        w("**Diagnose before more tuning.** Measure candidate-generation "
          "quality directly (gold-resolved elements vs generated candidates) "
          "and the parser's gold-resolution gap, on the held-out questions, at "
          "0.50/0.50. Keep corpus, prior and production fixed. This separates "
          "'architecture reachable but evidence weak' from 'evidence good but "
          "questions can't reward it' before any further weight search.")
    w()
    w("No parser, schema, corpus, QA-model or embeddings change is part of the "
      "next step.")
    w()

    return "\n".join(L)


# ---------------------------------------------------------------------------
# One complete confirmation run
# ---------------------------------------------------------------------------

async def run_once(run_seed: str, smoke: bool = False) -> dict:
    from evaluation.isolation import assert_cleanup_execution_authorized

    assert_cleanup_execution_authorized(engine, operation="structure confirmation alternate execution")
    import uuid as _uuid

    from passlib.context import CryptContext

    from auth.models import User
    from chat.models import ChatMessage, ChatSession  # noqa: F401
    from config import get_settings
    from documents.chunking import resolve_chunker_version
    from documents.models import Document, DocumentChunk  # noqa: F401
    from graph.models import (  # noqa: F401
        DocumentGraphEdge,
        DocumentStructureEdge,
        DocumentStructureElement,
    )
    from reliability.models import ReliabilityLog, SourceRef  # noqa: F401
    from user.models import UserSettings  # noqa: F401
    from verification.models import VerificationResult  # noqa: F401

    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    corpus, unsupported, acceptable, _prefix = base.ablation.load_corpus(
        "structure_discriminating"
    )
    meta = {q.qid: q for q in corpus.questions}
    chunker_version = resolve_chunker_version(get_settings().chunker_version)

    split = split_questions(meta)
    conf_ids = set(split["confirmation_qids"])
    dev_ids = set(split["development_qids"])

    base._warm_models()

    with base.DeterministicUUIDs(run_seed):
        async with async_session() as db:
            existing = (
                await db.execute(select(User).where(User.email == EVAL_EMAIL))
            ).scalar_one_or_none()
            if existing is not None:
                await base.ablation._delete_user_data(db, existing.id)
                await db.execute(delete(User).where(User.id == existing.id))
                await db.commit()

            user = User(
                id=_uuid.uuid4(),
                email=EVAL_EMAIL,
                name="Structure Confirmation",
                hashed_password=pwd.hash("TestPass123!"),
                is_active=True,
            )
            db.add(user)
            await db.flush()
            user_id = user.id

            ingested = await base.ingest_corpus(db, user_id, corpus, chunker_version)
            questions = base.ablation.build_questions(
                corpus, unsupported, ingested, acceptable
            )
            if smoke:
                questions = questions[:8]  # cheap validation subset
            persisted = await base.load_persisted_elements(db, user_id)

            print(
                f"  [{run_seed}] ingested "
                f"{sum(len(v['chunk_ids']) for v in ingested.values())} chunks, "
                f"{len(persisted)} structure elements, {len(questions)} questions; "
                f"split {len(conf_ids)}/{len(dev_ids)}"
            )

            with calib.rrf_weights(SEMANTIC_WEIGHT, STRUCTURAL_WEIGHT):
                control = await base.measure_arm(
                    db, user_id, questions, meta, "CONTROL", ingested, persisted, corpus
                )
                treatment = await base.measure_arm(
                    db, user_id, questions, meta, "TREATMENT", ingested, persisted, corpus
                )
            print(f"  [{run_seed}] CONTROL/TREATMENT measured")

            await base.ablation._delete_user_data(db, user_id)
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()

    await engine.dispose()

    isolation = calib.isolation_check(control, treatment)

    # subset populations
    def ids_where(pred):
        return {q for q in meta if pred(meta[q])}

    disc = ids_where(lambda q: q.discrimination == "DISCRIMINATING")
    all_ans = ids_where(lambda q: q.answerable)
    unans = ids_where(lambda q: not q.answerable)

    subsets = {
        "confirmation_DISCRIMINATING": subset_metrics(control, treatment, conf_ids & disc),
        "development_DISCRIMINATING": subset_metrics(control, treatment, dev_ids & disc),
        "confirmation_all": subset_metrics(control, treatment, conf_ids),
        "development_all": subset_metrics(control, treatment, dev_ids),
        "confirmation_all_answerable": subset_metrics(control, treatment, conf_ids & all_ans),
        "confirmation_unanswerable": subset_metrics(control, treatment, conf_ids & unans),
    }

    # per-category on confirmation questions
    by_cat: dict[str, set[str]] = defaultdict(set)
    for q in conf_ids:
        by_cat[meta[q].category].add(q)
    conf_by_category = {}
    for cat in sorted(by_cat):
        m = subset_metrics(control, treatment, by_cat[cat])
        conf_by_category[cat] = {
            "n": m["n"],
            "question_ids": m["question_ids"],
            "element_admission_count": m["element_admission_count"],
            "answers_CONTROL": m["answers"]["CONTROL"],
            "answers_TREATMENT": m["answers"]["TREATMENT"],
        }
    subsets["confirmation_by_category"] = conf_by_category

    decision = evaluate_confirmation(subsets, isolation)

    # comparison with calibration (read the recorded calibration artifact)
    comparison = {}
    try:
        with open(
            REPORTS_DIR / "structure_rrf_calibration.json", encoding="utf-8"
        ) as fh:
            calib_json = json.load(fh)
        prim = calib_json["configurations"]["sw050_st050"]["analysis"]["populations"][
            "DISCRIMINATING_answerable"
        ]
        rd = prim["retrieval_metrics"]["DELTA"]["evidence_unit"]
        ad = prim["answer_metrics"]["DELTA"]
        comparison["calibration_reported_all_DISCRIMINATING"] = {
            "recall@5": rd.get("recall@5"),
            "precision@5": rd.get("precision@5"),
            "mrr": rd.get("mrr"),
            "ndcg@5": rd.get("ndcg@5"),
            "exact_match_rate": ad.get("exact_match_rate"),
            "token_f1": ad.get("token_f1"),
            "harmful_transitions": prim["answer_transitions"]["counts"].get("correct_to_wrong", 0),
            "element_admission_count": calib_json["configurations"]["sw050_st050"][
                "reachability"
            ]["element_admission_count_overall"],
        }
    except Exception as exc:  # noqa: BLE001 — record honestly, never fabricate
        comparison["calibration_reported_all_DISCRIMINATING"] = {
            "error": f"calibration artifact unavailable: {type(exc).__name__}"
        }

    return {
        "experiment": "structure_confirmation",
        "corpus": "structure_discriminating_v1",
        "corpus_unchanged": True,
        "configuration": {
            "semantic_weight": SEMANTIC_WEIGHT,
            "structural_weight": STRUCTURAL_WEIGHT,
            "k": RRF_K,
            "top_k": TOP_K,
            "weight_injection": (
                "harness wraps chat.rag.fuse_dual_path and passes explicit "
                "weights; production chat/rag.py is unmodified"
            ),
            "control_switch": (
                "chat.rag.retrieve_structural_element_candidates returns [] for "
                "the CONTROL arm only"
            ),
        },
        "split": split,
        "isolation": isolation,
        "subsets": subsets,
        "comparison_with_calibration": comparison,
        "confirmation": decision,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def bind_database_runtime() -> None:
    """Bind the database-dependent names.  The guard runs first; idempotent."""
    global async_session, engine, rag, RRF_K
    if engine is not None:
        return
    # The calibration runner's binding runs the central guard before any storage
    # import, and binds its own names (and the element runner's).
    calib.bind_database_runtime()
    from chat import rag as rag_module  # noqa: E402
    from storage.database import async_session as session_factory  # noqa: E402
    from storage.database import engine as db_engine  # noqa: E402

    base.verify_bound_engine(db_engine)
    rag = rag_module
    RRF_K = rag.RRF_K
    async_session = session_factory
    engine = db_engine


async def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    smoke = "--smoke" in argv
    # `--replace` deliberately re-publishes over recorded evidence.  It is never
    # implied: without it, an existing report is preserved and the run refuses.
    replace = "--replace" in argv
    bind_database_runtime()

    # Diagnostic prints use Greek letters (delta) and arrows.  On Windows the
    # console encoding (e.g. cp1252) cannot represent them, which would crash
    # the run *after* the artifacts are written.  Reconfigure the diagnostic
    # streams to UTF-8 so reporting never fails on an encoding boundary.  The
    # canonical JSON/report artifacts are written separately as UTF-8 and are
    # unaffected by the console encoding.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001 — best-effort, never blocks the run
            pass

    print("=" * 78)
    print("STRUCTURE HELD-OUT CONFIRMATION — 0.50/0.50")
    print("  corpus: structure_discriminating_v1 (unchanged)")
    print("=" * 78)

    runs: list[dict] = []
    for index in range(1, RUNS + 1):
        print(f"\n--- run {index}/{RUNS} ---")
        runs.append(await run_once("structure-confirmation", smoke))
        if smoke and index == 1:
            break

    if smoke:
        import tempfile

        out_dir = Path(tempfile.mkdtemp(prefix="structure-confirmation-smoke-"))
        (out_dir / "payload.json").write_text(canonical(runs[0]), encoding="utf-8")
        (out_dir / "report.md").write_text(render_report(runs[0]), encoding="utf-8")
        print(f"\nsmoke artifacts written to {out_dir}")
        print(f"confirmation: {runs[0]['confirmation']['classification']}")
        return 0

    blobs = [canonical(run).encode("utf-8") for run in runs]
    hashes = [hashlib.sha256(blob).hexdigest() for blob in blobs]
    determinism = {
        "runs_compared": len(runs),
        "core_byte_identical": len(set(blobs)) == 1,
        "sha256_run1": hashes[0],
        "sha256_run2": hashes[1] if len(hashes) > 1 else None,
    }
    payload = dict(runs[0])
    payload["determinism"] = determinism
    payload2 = dict(runs[1])
    payload2["determinism"] = determinism
    determinism["analysis_final_byte_identical"] = canonical(payload) == canonical(payload2)
    payload["determinism"] = determinism
    all_identical = determinism["core_byte_identical"] and determinism["analysis_final_byte_identical"]

    # --- publish: append-only unless the operator explicitly asks to replace ---
    # Both names are pre-flighted before the first byte is written, so a collision
    # leaves the previous evidence completely intact instead of producing a
    # half-written artifact set.  The text written is exactly what the previous
    # revision wrote: only the write mechanism changed.
    json_target = REPORTS_DIR / "structure_confirmation.json"
    md_target = REPORTS_DIR / "structure_confirmation_report.md"
    if not replace:
        collisions = [str(path) for path in (json_target, md_target) if path.exists()]
        if collisions:
            print(
                "\nREFUSING to publish: existing evaluation evidence would be "
                f"replaced: {', '.join(collisions)}",
                file=sys.stderr,
            )
            print(
                "Nothing was written; the recorded evidence is unchanged. "
                "Move or rename it, or re-run with --replace to deliberately "
                "re-publish over it.",
                file=sys.stderr,
            )
            return 2
    try:
        write_evidence(json_target, canonical(payload), replace=replace)
        write_evidence(md_target, render_report(payload), replace=replace)
    except ArtifactExistsError as exc:
        print(f"\nREFUSING to publish: {exc}", file=sys.stderr)
        print(
            "A file appeared after the pre-flight check, so the artifact set is "
            "incomplete. Nothing further was written.",
            file=sys.stderr,
        )
        return 2
    print("\nwrote evaluation/reports/structure_confirmation.json")
    print("wrote evaluation/reports/structure_confirmation_report.md")

    split = payload["split"]
    decision = payload["confirmation"]
    iso = payload["isolation"]
    conf = payload["subsets"]["confirmation_DISCRIMINATING"]
    print()
    print(f"split: confirmation {split['counts']['confirmation']} / "
          f"development {split['counts']['development']}, "
          f"no_overlap {split['no_overlap']}")
    print(f"isolation (arms differ only in element stream): "
          f"{iso['arms_differ_only_in_element_stream']}")
    print(f"held-out DISCRIMINATING n={conf['n']}, admission "
          f"{conf['element_admission_count']}, harmful "
          f"{conf['transitions']['counts'].get('correct_to_wrong', 0)}")
    d = conf["retrieval"]["DELTA"]["evidence_unit"]
    print(f"held-out ΔRecall@5 {d.get('recall@5')}, ΔnDCG@5 {d.get('ndcg@5')}, "
          f"ΔEM {conf['answers']['DELTA'].get('exact_match_rate')}, "
          f"ΔF1 {conf['answers']['DELTA'].get('token_f1')}")
    print(f"  determinism (byte-identical): {all_identical}")
    print(f"  {decision['status']}")

    if not all_identical:
        print("DETERMINISM FAILURE: runs differ — investigate before reporting.",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
