#!/usr/bin/env python3
"""Structure RRF prior calibration — sweep only the fusion weights.

Research code.  Run explicitly from ``backend/``:

    ./venv/Scripts/python.exe evaluation/experiments/run_structure_rrf_calibration.py

What it measures
----------------
The prior measurement established that persisted ``DocumentStructureElement``
candidates are generated and reach the RRF fusion, but can never enter the
final top-k at the production prior (``semantic=0.70``, ``structural=0.30``,
``k=60``, ``top_k=5``), because a structural-only candidate scores at most
``0.30/61 = 0.004918`` while the weakest top-5 occupant scores at least
``0.70/65 = 0.010769``.

This experiment finds the minimum structural prior at which an element can
actually be admitted, and what then happens to retrieval and answers.  It
sweeps ONLY the RRF weights:

    semantic 0.70 / structural 0.30
    semantic 0.55 / structural 0.45
    semantic 0.50 / structural 0.50
    semantic 0.40 / structural 0.60

Everything else — corpus, questions, annotations, parser, persisted structure,
chunker, embeddings, QA model, ``k=60``, ``top_k=5``, database,
candidate-generation, evidence fusion and the evaluation metrics — is fixed.

Weights are injected strictly inside the evaluation harness.  Production
``chat/rag.py`` is never modified: ``fuse_dual_path`` binds its default weights
at definition time, so the harness wraps the ``chat.rag.fuse_dual_path``
module-global (the name ``retrieve_dual_path`` resolves at call time) and
passes explicit weights, and sets ``chat.rag.RRF_SEMANTIC_WEIGHT`` /
``RRF_STRUCTURAL_WEIGHT`` so the recorded per-candidate RRF contributions
reflect the swept weights.  The CONTROL/TREATMENT definition is unchanged: only
``retrieve_structural_element_candidates`` is stubbed to return ``[]`` for the
CONTROL arm.  A per-question integrity check re-fuses the captured streams with
the same ``fuse_dual_path`` and must equal the production output exactly.

Determinism
-----------
The whole sweep is executed twice (independent user/ingest/measure/teardown
cycles, identical deterministic-id seed) and the machine-readable payload must
be byte-identical.  The existing normalisations from the prior measurement are
preserved: one-time model loads are warmed before the deterministic-id region,
and the semantic stream is re-sorted by ``(-similarity, chunk_id)`` so
exactly-tied cosine scores get a fixed order.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

_BACKEND_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from sqlalchemy import delete, select  # noqa: E402

import evaluation.experiments.run_structure_element_measurement as base  # noqa: E402

# Database-dependent names.  Bound by bind_database_runtime() only after the
# central isolation guard has approved the target; nothing here imports storage
# or chat at module scope.
async_session = None
engine = None
rag = None

from evaluation.artifacts import ArtifactExistsError, write_evidence  # noqa: E402

REPORTS_DIR = Path(_BACKEND_DIR) / "evaluation" / "reports"

TOP_K = base.TOP_K
RUNS = 2
EVAL_EMAIL = base.EVAL_EMAIL
RRF_K = None  # bound with rag by bind_database_runtime()

# (config_id, semantic_weight, structural_weight) — ascending structural prior.
SWEEP = (
    ("sw070_st030", 0.70, 0.30),
    ("sw055_st045", 0.55, 0.45),
    ("sw050_st050", 0.50, 0.50),
    ("sw040_st060", 0.40, 0.60),
)

FINAL_STATUSES = {
    "NONE": "FINAL STATUS: RRF CALIBRATION COMPLETE — STRUCTURAL ADMISSION STILL ZERO",
    "HARMFUL": "FINAL STATUS: RRF CALIBRATION COMPLETE — STRUCTURAL WEIGHT HARMFUL",
    "NEUTRAL": "FINAL STATUS: RRF CALIBRATION COMPLETE — STRUCTURAL ADMISSION ACHIEVED BUT NEUTRAL",
    "PROMISING": "FINAL STATUS: RRF CALIBRATION COMPLETE — STRUCTURAL ADMISSION ACHIEVED",
    "BLOCKED": "FINAL STATUS: BLOCKED — RRF CALIBRATION INCOMPLETE",
}

canonical = base.canonical
_r = base._r


# ---------------------------------------------------------------------------
# Theoretical admission threshold
# ---------------------------------------------------------------------------

def theoretical_threshold(k: int, top_k: int) -> dict:
    """Smallest structural weight that admits a rank-1 structural-only candidate.

    A structural-only candidate at structural rank 1 scores ``st / (k + 1)``.
    The weakest top-k occupant scores at least ``sw / (k + top_k)`` (every
    top-k occupant carries a semantic contribution).  With ``sw + st = 1``,
    admission requires::

        st/(k+1) > (1-st)/(k+top_k)
        st*(2k + top_k + 1) > (k + 1)
        st > (k + 1) / (2k + top_k + 1)
    """
    threshold = (k + 1) / (2 * k + top_k + 1)
    return {
        "k": k,
        "top_k": top_k,
        "formula": "structural_weight > (k+1) / (2k+top_k+1)",
        "threshold_structural_weight": round(threshold, 6),
        "equivalent_semantic_weight": round(1.0 - threshold, 6),
        "reasoning": (
            f"structural-only rank-1 contribution = st/(k+1); weakest top-k "
            f"occupant >= sw/(k+top_k); with sw+st=1 the crossover is "
            f"st = (k+1)/(2k+top_k+1) = {threshold:.6f}"
        ),
    }


def config_theory(semantic_weight: float, structural_weight: float, k: int, top_k: int) -> dict:
    struct_rank1 = structural_weight / (k + 1)
    weakest_sem = semantic_weight / (k + top_k)
    return {
        "structural_only_rank1_contribution": round(struct_rank1, 6),
        "weakest_semantic_topk_contribution": round(weakest_sem, 6),
        "admission_mathematically_possible": struct_rank1 > weakest_sem,
    }


# ---------------------------------------------------------------------------
# Weight injection (harness-side only; production untouched)
# ---------------------------------------------------------------------------

@contextmanager
def rrf_weights(semantic_weight: float, structural_weight: float):
    """Run the production retrieval/fusion path at the swept weights.

    ``chat.rag.fuse_dual_path`` is replaced by a thin wrapper that forwards to
    the *unmodified* production function with explicit weights.  Because
    ``chat.rag.retrieve_dual_path`` calls ``fuse_dual_path`` through the module
    global, the production call graph picks up the swept weights without any
    production edit.  The weight constants are also set so the recorded
    per-candidate RRF contributions match the swept prior.
    """
    real_fuse = rag.fuse_dual_path
    real_sem, real_struct = rag.RRF_SEMANTIC_WEIGHT, rag.RRF_STRUCTURAL_WEIGHT

    def _fuse(semantic, structural, top_k, **kwargs):
        return real_fuse(
            semantic,
            structural,
            top_k,
            semantic_weight=semantic_weight,
            structural_weight=structural_weight,
            k=kwargs.get("k", rag.RRF_K),
        )

    rag.fuse_dual_path = _fuse
    rag.RRF_SEMANTIC_WEIGHT = semantic_weight
    rag.RRF_STRUCTURAL_WEIGHT = structural_weight
    try:
        yield
    finally:
        rag.fuse_dual_path = real_fuse
        rag.RRF_SEMANTIC_WEIGHT = real_sem
        rag.RRF_STRUCTURAL_WEIGHT = real_struct


# ---------------------------------------------------------------------------
# Per-configuration measurement
# ---------------------------------------------------------------------------

async def measure_config(
    db,
    user_id,
    questions,
    meta,
    ingested,
    persisted_elements,
    corpus,
    semantic_weight: float,
    structural_weight: float,
):
    with rrf_weights(semantic_weight, structural_weight):
        control = await base.measure_arm(
            db, user_id, questions, meta, "CONTROL", ingested, persisted_elements, corpus
        )
        treatment = await base.measure_arm(
            db, user_id, questions, meta, "TREATMENT", ingested, persisted_elements, corpus
        )
    return control, treatment


def isolation_check(control: list[dict], treatment: list[dict]) -> dict:
    """Verify CONTROL/TREATMENT differ only in the element candidate stream."""
    c_by = {t["question_id"]: t for t in control}
    t_by = {t["question_id"]: t for t in treatment}
    shared = sorted(set(c_by) & set(t_by))
    control_empty = True
    sem_equal = True
    chunk_equal = True
    seeds_equal = True
    first_mismatch = None
    for qid in shared:
        c, t = c_by[qid], t_by[qid]
        if c["structural_candidate_ids"]:
            control_empty = False
            first_mismatch = f"{qid}: CONTROL element stream not empty"
        if c["semantic_candidate_ids"] != t["semantic_candidate_ids"]:
            sem_equal = False
            first_mismatch = first_mismatch or f"{qid}: semantic streams differ"
        if c["chunk_structural_candidate_ids"] != t["chunk_structural_candidate_ids"]:
            chunk_equal = False
            first_mismatch = first_mismatch or f"{qid}: chunk-structural streams differ"
        if c["structural_seed_ids"] != t["structural_seed_ids"]:
            seeds_equal = False
            first_mismatch = first_mismatch or f"{qid}: element seeds differ"
    return {
        "questions_compared": len(shared),
        "control_element_stream_empty": control_empty,
        "semantic_streams_identical": sem_equal,
        "chunk_structural_streams_identical": chunk_equal,
        "element_seed_sets_identical": seeds_equal,
        "arms_differ_only_in_element_stream": (
            control_empty and sem_equal and chunk_equal and seeds_equal
        ),
        "first_mismatch": first_mismatch,
    }


def ranking_influence(control: list[dict], treatment: list[dict]) -> dict:
    """The five distinctions, kept separate (never collapsed into one metric)."""
    c_by = {t["question_id"]: t for t in control}
    t_by = {t["question_id"]: t for t in treatment}
    shared = sorted(set(c_by) & set(t_by))

    element_entered = []
    top_k_set_changed = []
    rank_order_changed = []
    indirect_rank_change = []
    gold_changed = []
    answer_changed = []
    beneficial, harmful = [], []

    for qid in shared:
        c, t = c_by[qid], t_by[qid]
        eff = base.ranking_effects(c, t)
        if t["structure_element_count_in_top_k"] > 0:
            element_entered.append(qid)
        if set(c["final_top_k"]) != set(t["final_top_k"]):
            top_k_set_changed.append(qid)
        if c["final_top_k"] != t["final_top_k"]:
            rank_order_changed.append(qid)
            if set(c["final_top_k"]) == set(t["final_top_k"]):
                indirect_rank_change.append(qid)
        if (
            eff["gold_entered_top_k"]
            or eff["gold_left_top_k"]
            or eff["gold_rank_delta"] not in (0, None)
        ):
            gold_changed.append(qid)
        if c["predicted_answer"] != t["predicted_answer"]:
            answer_changed.append(qid)
        if eff["change_classification"] == "beneficial":
            beneficial.append(qid)
        elif eff["change_classification"] == "harmful":
            harmful.append(qid)

    n = len(shared)
    return {
        "n": n,
        "1_element_enters_top_k_directly": {
            "count": len(element_entered),
            "question_ids": element_entered,
        },
        "2_element_changes_rank_indirectly": {
            "count": len(indirect_rank_change),
            "question_ids": indirect_rank_change,
        },
        "3_top_k_set_changes": {
            "count": len(top_k_set_changed),
            "question_ids": top_k_set_changed,
        },
        "4_gold_evidence_changes": {
            "count": len(gold_changed),
            "question_ids": gold_changed,
        },
        "5_answer_changes": {
            "count": len(answer_changed),
            "question_ids": answer_changed,
        },
        "rank_order_changed_any": {
            "count": len(rank_order_changed),
            "question_ids": rank_order_changed,
        },
        "beneficial_changes": {"count": len(beneficial), "question_ids": beneficial},
        "harmful_changes": {"count": len(harmful), "question_ids": harmful},
    }


def reachability_block(control: list[dict], treatment: list[dict]) -> dict:
    tf, cf = base.funnel_for(treatment), base.funnel_for(control)
    tr_sat = base.saturation_analysis(treatment)
    element_admitted = [
        t["question_id"] for t in treatment if t["structure_element_count_in_top_k"] > 0
    ]
    return {
        "funnel_CONTROL": cf,
        "funnel_TREATMENT": tf,
        "element_admission_rate_overall": (
            _r(len(element_admitted) / len(treatment)) if treatment else None
        ),
        "element_admission_count_overall": len(element_admitted),
        "element_admission_question_ids": sorted(element_admitted),
        "structural_only_admission_rate_overall": tr_sat["overall"][
            "structural_only_admission_rate"
        ],
        "hybrid_structural_influence": {
            "definition": (
                "share of questions whose fused ORDER changed because element "
                "candidates shifted the structural ranks of existing hybrid "
                "chunk candidates, even when the top-k set is unchanged"
            ),
            "rank_order_changed_rate": (
                _r(
                    sum(
                        1
                        for c, t in zip(
                            sorted(control, key=lambda x: x["question_id"]),
                            sorted(treatment, key=lambda x: x["question_id"]),
                        )
                        if c["final_top_k"] != t["final_top_k"]
                    )
                    / len(treatment)
                )
                if treatment
                else None
            ),
        },
    }


# ---------------------------------------------------------------------------
# Selection gate
# ---------------------------------------------------------------------------

def classify(selected: dict) -> tuple[str, dict]:
    prim = selected["analysis"]["populations"]["DISCRIMINATING_answerable"]
    retr = prim["retrieval_metrics"]["DELTA"]["evidence_unit"]
    ans = prim["answer_metrics"]["DELTA"]
    trans = prim["answer_transitions"]["counts"]
    harmful_trans = trans.get("correct_to_wrong", 0)
    retr_loss = any(
        (retr.get(m) or 0.0) < 0.0 for m in ("recall@5", "mrr", "ndcg@5")
    )
    ans_loss = any(
        (ans.get(m) or 0.0) < 0.0
        for m in ("exact_match_rate", "token_f1", "answer_accuracy")
    )
    positive = any(
        (retr.get(m) or 0.0) > 0.0 for m in ("recall@5", "mrr", "ndcg@5")
    ) or any(
        (ans.get(m) or 0.0) > 0.0
        for m in ("exact_match_rate", "token_f1", "answer_accuracy")
    )
    evidence = {
        "harmful_transitions": harmful_trans,
        "primary_retrieval_delta_evidence_unit": retr,
        "primary_answer_delta": ans,
        "primary_retrieval_loss": retr_loss,
        "primary_answer_loss": ans_loss,
        "positive_movement": positive,
    }
    if harmful_trans > 0 or retr_loss or ans_loss:
        return "HARMFUL", evidence
    if positive:
        return "PROMISING", evidence
    return "NEUTRAL", evidence


def _ordered_ids(configs: dict) -> list[str]:
    return [
        cid
        for cid, _c in sorted(
            configs.items(), key=lambda kv: kv[1]["structural_weight"]
        )
    ]


def selection_gate(configs: dict) -> dict:
    ordered = _ordered_ids(configs)
    threshold = theoretical_threshold(RRF_K, TOP_K)["threshold_structural_weight"]
    admitted = [
        cid for cid in ordered if configs[cid]["reachability"]["element_admission_count_overall"] > 0
    ]
    first = admitted[0] if admitted else None
    if first is None:
        return {
            "theoretical_threshold_structural_weight": threshold,
            "configs_in_order": ordered,
            "configs_with_any_element_admission": admitted,
            "selected_config": None,
            "classification": "NONE",
            "evidence": {
                "note": (
                    "no swept structural weight produced element admission; "
                    "the selected configuration is the maximum swept structural "
                    "weight for diagnostic reporting only"
                )
            },
            "final_status": FINAL_STATUSES["NONE"],
        }
    classification, evidence = classify(configs[first])
    evidence["note"] = (
        "selected the smallest structural weight with non-zero element "
        "admission; classification is based on the primary DISCRIMINATING "
        "subset, not on admission count"
    )
    return {
        "theoretical_threshold_structural_weight": threshold,
        "configs_in_order": ordered,
        "configs_with_any_element_admission": admitted,
        "selected_config": first,
        "classification": classification,
        "evidence": evidence,
        "final_status": FINAL_STATUSES[classification],
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
    thr = payload["theoretical_threshold"]
    configs = payload["configurations"]
    ordered = _ordered_ids(configs)
    gate = payload["selection_gate"]
    det = payload.get("determinism", {})
    L: list[str] = []

    def w(line: str = "") -> None:
        L.append(line)

    w("# Structure RRF Prior Calibration — Sweep Report")
    w()
    w("**Experiment:** `structure_rrf_calibration`  ")
    w("**Corpus:** `structure_discriminating_v1` (unchanged)  ")
    w("**Runner:** `backend/evaluation/experiments/run_structure_rrf_calibration.py`  ")
    w("**Machine-readable artifact:** `structure_rrf_calibration.json`  ")
    w("**Nature:** evaluation experiment — only the RRF weights are varied, and "
      "only inside the evaluation harness.")
    w()
    w("---")
    w()

    # 1. Objective
    w("## 1. Objective")
    w()
    w("Find the minimum structural RRF prior at which persisted "
      "`DocumentStructureElement` candidates can actually enter the production "
      "top-k, then determine whether that increased structural influence "
      "produces beneficial, neutral or harmful retrieval/answer changes. This "
      "does not test the structural hypothesis; it establishes whether the "
      "current architecture can expose structural evidence to ranking and what "
      "happens when its prior is calibrated.")
    w()
    w("---")
    w()

    # 2. Baseline
    w("## 2. Baseline")
    w()
    w("The prior measurement (unchanged) established:")
    w()
    w("* corpus `structure_discriminating_v1`, 72 questions (64 answerable); "
      "primary DISCRIMINATING subset 32.")
    w("* production RRF: semantic `0.70`, structural `0.30`, `k=60`, `top_k=5`.")
    w("* element candidates generated and contributed to structural RRF, but "
      "**zero** entered final top-k — mathematically expected because")
    w("  `max structural-only = 0.30/61 = 0.004918` < "
      "`weakest semantic top-5 = 0.70/65 = 0.010769`.")
    w("* top-k set never changed; one NOT_DISCRIMINATING question had an "
      "order-only swap (hybrid rank shift); no gold movement, harmful "
      "transition or answer change; both runs byte-identical.")
    w()
    w("This sweep keeps every one of those factors fixed and varies **only** the "
      "two fusion weights.")
    w()
    w("---")
    w()

    # 3. Experimental matrix
    w("## 3. Experimental Matrix")
    w()
    w("Swept configurations (only the weights differ):")
    w()
    w("| config | semantic | structural | k | top_k | admission mathematically possible |")
    w("|---|---:|---:|---:|---:|---|")
    for cid in ordered:
        c = configs[cid]
        w(f"| `{cid}` | {c['semantic_weight']:.2f} | {c['structural_weight']:.2f} | "
          f"{RRF_K} | {TOP_K} | {'yes' if c['mathematically_possible'] else 'no'} |")
    w()
    w("Fixed across all runs: corpus, question set, annotations, parser, "
      "persisted structure, chunker, embeddings, QA model, `k=60`, `top_k=5`, "
      "database, candidate-generation logic, evidence-fusion logic, evaluation "
      "metrics, and the CONTROL/TREATMENT definition (CONTROL disables only "
      "`retrieve_structural_element_candidates`).")
    w()
    w("### CONTROL/TREATMENT isolation verification")
    w()
    w("For every configuration the harness verifies that the two arms differ "
      "**only** in the element candidate stream: the semantic stream, the "
      "chunk-level structural stream and the element seed set are recorded "
      "identically for both arms, and CONTROL's element stream is empty.")
    w()
    w("| config | semantic identical | chunk-structural identical | element seeds identical | CONTROL element stream empty | arms differ only in element stream |")
    w("|---|---|---|---|---|---|")
    for cid in ordered:
        iso = configs[cid]["isolation"]
        w(f"| `{cid}` | {iso['semantic_streams_identical']} | "
          f"{iso['chunk_structural_streams_identical']} | "
          f"{iso['element_seed_sets_identical']} | "
          f"{iso['control_element_stream_empty']} | "
          f"{iso['arms_differ_only_in_element_stream']} |")
    w()
    w("### Compact comparison across all four weights")
    w()
    w("| config | structural | element admission (n) | top-k set changed | rank order changed | gold changed | answer changed | harmful transitions | classification |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for cid in ordered:
        c = configs[cid]
        ri = c["ranking_influence"]
        cls = "—" if gate["selected_config"] != cid else gate["classification"]
        if gate["classification"] != "NONE":
            cls = gate["classification"] if cid == gate["selected_config"] else "—"
        w(
            f"| `{cid}` | {c['structural_weight']:.2f} | "
            f"{c['reachability']['element_admission_count_overall']} | "
            f"{ri['3_top_k_set_changes']['count']} | "
            f"{ri['rank_order_changed_any']['count']} | "
            f"{ri['4_gold_evidence_changes']['count']} | "
            f"{ri['5_answer_changes']['count']} | "
            f"{ri['harmful_changes']['count']} | {cls} |"
        )
    w()
    w("---")
    w()

    # 4. Theoretical threshold
    w("## 4. Theoretical Threshold")
    w()
    w(f"For a structural-only candidate at structural rank 1: "
      f"`structural_weight/(k+1)`.")
    w(f"For the weakest semantic candidate in top-k: "
      f"`semantic_weight/(k+top_k)`.")
    w()
    w("With `k=60`, `top_k=5`, `semantic + structural = 1`, admission of a "
      "rank-1 structural-only candidate requires")
    w()
    w("```text")
    w(f"structural_weight / 61  >  (1 - structural_weight) / 65")
    w(f"structural_weight > (k+1)/(2k+top_k+1) = 61/126 = "
      f"{thr['threshold_structural_weight']:.6f}")
    w("```")
    w()
    w(f"**Theoretical threshold: structural_weight > "
      f"{thr['threshold_structural_weight']:.6f}** "
      f"(equivalently semantic_weight < {thr['equivalent_semantic_weight']:.6f}).")
    w()
    w("Per-configuration theory:")
    w()
    w("| config | structural | st/(k+1) | sw/(k+top_k) | mathematically possible |")
    w("|---|---:|---:|---:|---|")
    for cid in ordered:
        c = configs[cid]
        th = c["theoretical"]
        w(f"| `{cid}` | {c['structural_weight']:.2f} | "
          f"{_f(th['structural_only_rank1_contribution'])} | "
          f"{_f(th['weakest_semantic_topk_contribution'])} | "
          f"{'yes' if th['admission_mathematically_possible'] else 'no'} |")
    w()
    w("Comparison with the empirical sweep (§5): the theoretical threshold is a "
      "lower bound on difficulty — it assumes the weakest top-k occupant is a "
      "pure rank-5 semantic candidate. In practice the top-5 often contains "
      "*hybrid* candidates whose fusion score exceeds `sw/65`, so real "
      "admission can require a higher structural prior than the threshold. The "
      "five stages are reported separately below:")
    w()
    w("* mathematically possible (§4);")
    w("* candidate actually generated (§5);")
    w("* candidate actually enters top-k (§5/§6);")
    w("* candidate changes gold evidence (§6);")
    w("* candidate changes answer quality (§8/§10).")
    w()
    w("---")
    w()

    # 5. Reachability
    w("## 5. Reachability Results")
    w()
    w("Funnel per configuration (counts of questions, TREATMENT / CONTROL).")
    w()
    for cid in ordered:
        c = configs[cid]
        rb = c["reachability"]
        tf, cf = rb["funnel_TREATMENT"], rb["funnel_CONTROL"]
        w(f"### `{cid}` (semantic {c['semantic_weight']:.2f} / "
          f"structural {c['structural_weight']:.2f})")
        w()
        w("| stage | TREATMENT | CONTROL |")
        w("|---|---:|---:|")
        for stage in base.FUNNEL_STAGES:
            w(f"| {stage} | {tf['counts'][stage]} | {cf['counts'][stage]} |")
        w()
        w(f"* element admission (element in final top-k): "
          f"**{rb['element_admission_count_overall']}** question(s) "
          f"(rate {_f(rb['element_admission_rate_overall'])}); ids "
          f"{rb['element_admission_question_ids'] or 'none'}")
        w(f"* structural-only admission rate (eligible questions): "
          f"{_f(rb['structural_only_admission_rate_overall'])}")
        w(f"* hybrid structural influence (rank-order changed via hybrid "
          f"shift): {_f(rb['hybrid_structural_influence']['rank_order_changed_rate'])}")
        w()
    w("---")
    w()

    # 6. Ranking influence
    w("## 6. Ranking Influence")
    w()
    w("Explicitly separated (never collapsed into one metric):")
    w()
    w("| config | 1. element enters top-k | 2. indirect rank change | 3. top-k set changes | 4. gold evidence changes | 5. answer changes | beneficial | harmful |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|")
    for cid in ordered:
        ri = configs[cid]["ranking_influence"]
        w(f"| `{cid}` | {ri['1_element_enters_top_k_directly']['count']} | "
          f"{ri['2_element_changes_rank_indirectly']['count']} | "
          f"{ri['3_top_k_set_changes']['count']} | "
          f"{ri['4_gold_evidence_changes']['count']} | "
          f"{ri['5_answer_changes']['count']} | "
          f"{ri['beneficial_changes']['count']} | "
          f"{ri['harmful_changes']['count']} |")
    w()
    for cid in ordered:
        ri = configs[cid]["ranking_influence"]
        details = []
        for key, label in (
            ("1_element_enters_top_k_directly", "element enters top-k"),
            ("2_element_changes_rank_indirectly", "indirect rank change"),
            ("3_top_k_set_changes", "top-k set change"),
            ("4_gold_evidence_changes", "gold change"),
            ("5_answer_changes", "answer change"),
        ):
            if ri[key]["count"]:
                details.append(f"{label}: {ri[key]['question_ids']}")
        if details:
            w(f"* `{cid}`: " + "; ".join(details))
    w()
    w("Per-population ranking effects (CONTROL vs TREATMENT):")
    w()
    w("| config | population | n | top-k changed | rank order changed | gold entered | gold left | beneficial | harmful | neutral |")
    w("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for cid in ordered:
        pops = configs[cid]["analysis"]["populations"]
        for pop in ("DISCRIMINATING_answerable", "all_answerable", "all"):
            rk = pops[pop]["ranking_effects"]
            w(f"| `{cid}` | {pop} | {rk.get('n', 0)} | "
              f"{_f(rk.get('top_k_changed_rate'))} | "
              f"{_f(rk.get('rank_order_changed_rate'))} | "
              f"{_f(rk.get('gold_entered_rate'))} | "
              f"{_f(rk.get('gold_left_rate'))} | "
              f"{rk.get('beneficial', 0)} | {rk.get('harmful', 0)} | "
              f"{rk.get('neutral', 0)} |")
    w()
    w("---")
    w()

    # 7. Retrieval metrics
    w("## 7. Retrieval Metrics")
    w()
    w("Primary gold view `evidence_unit`. Metric definitions unchanged "
      "(`evaluation/retrieval_metrics.py`).")
    w()
    for pop in (
        "DISCRIMINATING_answerable",
        "WEAKLY_DISCRIMINATING_answerable",
        "NOT_DISCRIMINATING_answerable",
        "all_answerable",
        "all",
    ):
        w(f"### {pop}")
        w()
        w("| config | arm | n | Recall@5 | Precision@5 | MRR | nDCG@5 | evidence coverage |")
        w("|---|---|---:|---:|---:|---:|---:|---:|")
        for cid in ordered:
            popblock = configs[cid]["analysis"]["populations"][pop]
            rm = popblock["retrieval_metrics"]
            for arm in ("CONTROL", "TREATMENT"):
                ev = rm[arm]["evidence_unit"]
                w(f"| `{cid}` | {arm} | {ev['n']} | {_f(ev['recall@5'])} | "
                  f"{_f(ev['precision@5'])} | {_f(ev['mrr'])} | "
                  f"{_f(ev['ndcg@5'])} | {_f(rm[arm]['evidence_coverage'])} |")
        w()
    w("DELTA (TREATMENT − CONTROL), `evidence_unit`:")
    w()
    w("| config | population | ΔRecall@5 | ΔPrecision@5 | ΔMRR | ΔnDCG@5 |")
    w("|---|---|---:|---:|---:|---:|")
    for cid in ordered:
        for pop in ("DISCRIMINATING_answerable", "all_answerable", "all"):
            d = (
                configs[cid]["analysis"]["populations"][pop]["retrieval_metrics"]["DELTA"]
                .get("evidence_unit", {})
            )
            w(f"| `{cid}` | {pop} | {_f(d.get('recall@5'))} | "
              f"{_f(d.get('precision@5'))} | {_f(d.get('mrr'))} | "
              f"{_f(d.get('ndcg@5'))} |")
    w()
    w("---")
    w()

    # 8. Answer metrics
    w("## 8. Answer Metrics")
    w()
    w("| config | population | arm | EM | token F1 | accuracy | grounding | unsupported rate |")
    w("|---|---|---|---:|---:|---:|---:|---:|")
    for cid in ordered:
        for pop in ("DISCRIMINATING_answerable", "all_answerable", "unanswerable", "all"):
            popblock = configs[cid]["analysis"]["populations"][pop]
            am = popblock["answer_metrics"]
            for arm in ("CONTROL", "TREATMENT"):
                a = am[arm]
                w(f"| `{cid}` | {pop} | {arm} | {_f(a['exact_match_rate'])} | "
                  f"{_f(a['token_f1'])} | {_f(a['answer_accuracy'])} | "
                  f"{_f(a['factual_grounding_rate'])} | "
                  f"{_f(a['unsupported_answer_rate'])} |")
    w()
    w("---")
    w()

    # 9. Category analysis
    w("## 9. Category Analysis")
    w()
    cats = list(configs[ordered[0]]["analysis"]["category_analysis"].keys())
    w("| config | category | n | EM | token F1 | accuracy | element in top-k |")
    w("|---|---|---:|---:|---:|---:|---:|")
    for cid in ordered:
        ca = configs[cid]["analysis"]["category_analysis"]
        for cat in cats:
            b = ca[cat]
            am = b["answer_metrics"]["TREATMENT"]
            el = b["funnel_treatment"]["counts"][
                "questions_with_structure_element_in_final_top_k"
            ]
            w(f"| `{cid}` | {cat} | {b['n']} | {_f(am['exact_match_rate'])} | "
              f"{_f(am['token_f1'])} | {_f(am['answer_accuracy'])} | {el} |")
    w()
    w("---")
    w()

    # 10. Transition analysis
    w("## 10. Transition Analysis")
    w()
    w("Correctness threshold `token F1 ≥ 0.5` (same as `answer_accuracy`).")
    w()
    w("| config | population | correct→correct | correct→wrong | wrong→correct | wrong→wrong |")
    w("|---|---|---:|---:|---:|---:|")
    for cid in ordered:
        for pop in ("DISCRIMINATING_answerable", "all_answerable", "all"):
            t = configs[cid]["analysis"]["populations"][pop]["answer_transitions"]["counts"]
            w(f"| `{cid}` | {pop} | {t.get('correct_to_correct', 0)} | "
              f"{t.get('correct_to_wrong', 0)} | {t.get('wrong_to_correct', 0)} | "
              f"{t.get('wrong_to_wrong', 0)} |")
    w()
    w("---")
    w()

    # 11. Determinism
    w("## 11. Determinism")
    w()
    w("Two independent complete runs (user/ingest/measure/teardown), identical "
      "deterministic-id seed, with the existing normalisations preserved "
      "(model warm-up outside the id region; semantic stream re-sorted by "
      "`(-similarity, chunk_id)`).")
    w()
    if det:
        w(f"* runs compared: **{det.get('runs_compared')}**")
        w(f"* core payload byte-identical: **{det.get('core_byte_identical')}**")
        w(f"* run 1 SHA-256: `{det.get('sha256_run1')}`")
        w(f"* run 2 SHA-256: `{det.get('sha256_run2')}`")
    else:
        w("* determinism block not present")
    w()
    w("---")
    w()

    # 12. Limitations
    w("## 12. Limitations")
    w()
    w("* **Weight injection is harness-side.** Production `chat/rag.py` fusion is "
      "untouched; the sweep calls the unmodified `fuse_dual_path` with explicit "
      "weights. Results therefore describe the current architecture with a "
      "different prior, not a modified production system.")
    w("* **Only the RRF prior is varied.** Candidate generation, gold "
      "annotations, evidence fusion and the corpus are unchanged, so a failure "
      "to improve cannot be attributed to those components — but it also cannot "
      "rule out that the corpus/question design or structural evidence quality "
      "is the limiting factor.")
    w("* **Shared augmentation stream.** The post-ranking "
      "`_augment_with_structure` element stream is present in both arms, so only "
      "the *ranked* element contribution is isolated.")
    w("* **Four discrete weights.** The exact crossover may lie between the "
      "swept points; the theoretical threshold is analytic, the sweep is coarse.")
    w("* **Single corpus, no evidence gate, one `top_k`.**")
    w()
    w("---")
    w()

    # 13. Selected configuration
    w("## 13. Selected Configuration")
    w()
    w(f"* theoretical threshold structural_weight > "
      f"{gate['theoretical_threshold_structural_weight']:.6f}")
    w(f"* configs with any element admission: "
      f"{gate['configs_with_any_element_admission'] or 'none'}")
    if gate["selected_config"]:
        w(f"* **selected (smallest structural weight with non-zero element "
          f"admission): `{gate['selected_config']}`**")
    else:
        w("* **selected configuration: none** — no swept weight produced element "
          "admission")
    w(f"* **classification: {gate['classification']}**")
    ev = gate["evidence"]
    if "primary_retrieval_delta_evidence_unit" in ev:
        w(f"* primary DISCRIMINATING retrieval delta: "
          f"{json.dumps(ev['primary_retrieval_delta_evidence_unit'])}")
        w(f"* primary answer delta: {json.dumps(ev['primary_answer_delta'])}")
        w(f"* harmful transitions: {ev['harmful_transitions']}, positive "
          f"movement: {ev['positive_movement']}")
    w(f"* {ev.get('note','')}")
    w()
    w("---")
    w()

    # 14. Research interpretation
    w("## 14. Research Interpretation")
    w()
    interp = gate["classification"]
    w("This experiment does **not** prove the structural hypothesis. It "
      "establishes only whether the current architecture can expose structural "
      "evidence to ranking and what happens when its prior is calibrated.")
    w()
    if interp == "NONE":
        w("**Observed:** increasing the structural prior across the swept range "
          "still produced **zero** element admission. The architecture remains "
          "reachable (candidates are generated and carry RRF contributions) but "
          "element candidates are out-competed for the top-k slots even at the "
          "highest swept structural weight. This is consistent with the "
          "theoretical threshold being a *lower* bound: hybrid top-k occupants "
          "raise the admission bar above `sw/65`. The null result is retained; "
          "no benefit is claimed.")
    elif interp == "NEUTRAL":
        w("**Observed:** structural evidence did enter the top-k at the selected "
          "prior, but retrieval and answer metrics did not meaningfully improve. "
          "The architecture is therefore reachable and calibratable, yet the "
          "corpus/question design or the quality of the structural evidence "
          "itself may still be insufficient to convert structural admission into "
          "answer gains. This is a reachable-but-neutral result, not evidence "
          "for or against the structural hypothesis.")
    elif interp == "HARMFUL":
        w("**Observed:** raising the structural prior admitted structural "
          "evidence but produced measurable degradation and/or harmful answer "
          "transitions. A larger structural prior is therefore not a safe route "
          "to benefit on this corpus; the direction is harmful and should not be "
          "adopted.")
    else:  # PROMISING
        w("**Observed:** at the selected prior, structural admission occurred "
          "with positive retrieval/answer movement and no harmful transitions on "
          "the primary DISCRIMINATING subset. This is a promising signal only — "
          "it is **not** proof of the structural hypothesis. Preserve the exact "
          "evidence and run a confirmation experiment before any conclusion.")
    w()
    w("---")
    w()

    # 15. Exact next experiment
    w("## 15. Exact Next Experiment")
    w()
    if interp == "PROMISING":
        w("**Confirmation experiment (single change, same corpus).** Repeat this "
          "CONTROL/TREATMENT measurement at the selected prior with two "
          "independent runs and a held-out question split of the same corpus "
          "(or a small second corpus with independently authored structural "
          "gold), keeping parser, embeddings, QA model, `k=60` and `top_k=5` "
          "fixed. Accept only if the primary DISCRIMINATING retrieval and answer "
          "gains reproduce with zero harmful transitions. Do not touch production "
          "weights until confirmed.")
    elif interp in ("NEUTRAL", "HARMFUL"):
        w("**Diagnose structural evidence quality, not the prior.** With the "
          "prior held at the selected value (or back at 0.70/0.30), run a "
          "controlled measurement that scores *candidate quality* directly: for "
          "each question, compare the gold-resolved element set against the "
          "generated element candidates (precision/recall of candidate "
          "generation), and against what the parser persists (see the "
          "gold-resolution gap). Keep the corpus and prior fixed; do not change "
          "production. This separates 'architecture reachable but evidence weak' "
          "from 'evidence good but question design can't reward it'.")
    else:
        w("**Reserve a structural slot instead of raising the prior.** Because "
          "even the maximum swept structural weight produced zero admission, the "
          "next experiment should change *admission geometry* rather than the "
          "prior: reserve `top_k` slots for structural-only candidates (e.g. "
          "force-include the top-2 structural candidates alongside the top-3 "
          "semantic ones) at the production prior, and re-measure the same "
          "CONTROL/TREATMENT comparison. Keep parser, embeddings, QA model, "
          "`k=60` and `top_k=5` fixed; do not modify production until measured.")
    w()
    w("No parser, schema, corpus, QA-model or embeddings change is part of the "
      "next experiment.")
    w()

    return "\n".join(L)


# ---------------------------------------------------------------------------
# One complete sweep run
# ---------------------------------------------------------------------------

async def run_once(run_seed: str, smoke: bool = False) -> dict:
    from evaluation.isolation import assert_cleanup_execution_authorized

    assert_cleanup_execution_authorized(engine, operation="structure RRF alternate execution")
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

    base._warm_models()

    configs_out: dict[str, dict] = {}
    populations_sizes = None

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
                id=__import__("uuid").uuid4(),
                email=EVAL_EMAIL,
                name="Structure RRF Calibration",
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
            persisted = await base.load_persisted_elements(db, user_id)

            sweep = SWEEP
            if smoke:
                # Cheap validation: a handful of questions and the two configs
                # where admission is mathematically possible.
                questions = questions[:6]
                sweep = SWEEP[2:]

            print(
                f"  [{run_seed}] ingested "
                f"{sum(len(v['chunk_ids']) for v in ingested.values())} chunks, "
                f"{len(persisted)} structure elements, {len(questions)} questions"
            )

            for config_id, semantic_weight, structural_weight in sweep:
                control, treatment = await measure_config(
                    db, user_id, questions, meta, ingested, persisted, corpus,
                    semantic_weight, structural_weight,
                )
                analysis = base.build_analysis(control, treatment)
                if populations_sizes is None:
                    populations_sizes = {
                        p: len(base.select_population(treatment, p))
                        for p in base.POPULATIONS
                    }
                configs_out[config_id] = {
                    "config_id": config_id,
                    "semantic_weight": semantic_weight,
                    "structural_weight": structural_weight,
                    "mathematically_possible": config_theory(
                        semantic_weight, structural_weight, RRF_K, TOP_K
                    )["admission_mathematically_possible"],
                    "theoretical": config_theory(
                        semantic_weight, structural_weight, RRF_K, TOP_K
                    ),
                    "population_sizes": populations_sizes,
                    "isolation": isolation_check(control, treatment),
                    "reachability": reachability_block(control, treatment),
                    "ranking_influence": ranking_influence(control, treatment),
                    "analysis": analysis,
                }
                admitted = configs_out[config_id]["reachability"][
                    "element_admission_count_overall"
                ]
                print(
                    f"  [{run_seed}] {config_id}: element admission "
                    f"{admitted}, rank-order changed "
                    f"{configs_out[config_id]['ranking_influence']['rank_order_changed_any']['count']}, "
                    f"harmful {configs_out[config_id]['ranking_influence']['harmful_changes']['count']}"
                )

            await base.ablation._delete_user_data(db, user_id)
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()

    await engine.dispose()

    payload = {
        "experiment": "structure_rrf_calibration",
        "corpus": "structure_discriminating_v1",
        "corpus_unchanged": True,
        "top_k": TOP_K,
        "rrf_k": RRF_K,
        "control_switch": (
            "chat.rag.retrieve_structural_element_candidates returns [] for the "
            "CONTROL arm only"
        ),
        "weight_injection": (
            "harness wraps chat.rag.fuse_dual_path and passes explicit weights; "
            "production chat/rag.py is unmodified"
        ),
        "theoretical_threshold": theoretical_threshold(RRF_K, TOP_K),
        "sweep": [
            {
                "config_id": cid,
                "semantic_weight": configs_out[cid]["semantic_weight"],
                "structural_weight": configs_out[cid]["structural_weight"],
            }
            for cid in _ordered_ids(configs_out)
        ],
        "configurations": configs_out,
    }
    payload["selection_gate"] = selection_gate(configs_out)
    return payload


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def bind_database_runtime() -> None:
    """Bind the database-dependent names.  The guard runs first; idempotent."""
    global async_session, engine, rag, RRF_K
    if engine is not None:
        return
    # The element runner's binding runs the central guard before any storage
    # import, and binds the element runner's own names.
    base.bind_database_runtime()
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
    # Deliberate, never-implied opt-in: the fixed evaluation/reports paths are
    # append-only by default, and --replace re-publishes previous evidence.
    replace = "--replace" in argv
    bind_database_runtime()

    print("=" * 78)
    print("STRUCTURE RRF PRIOR CALIBRATION — weight sweep")
    print("  corpus: structure_discriminating_v1 (unchanged)")
    print("=" * 78)

    runs: list[dict] = []
    for index in range(1, RUNS + 1):
        print(f"\n--- run {index}/{RUNS} ---")
        runs.append(await run_once("structure-rrf-calibration", smoke))
        if smoke and index == 1:
            break

    if smoke:
        import tempfile

        out_dir = Path(tempfile.mkdtemp(prefix="rrf-calibration-smoke-"))
        (out_dir / "payload.json").write_text(
            canonical(runs[0]), encoding="utf-8"
        )
        (out_dir / "report.md").write_text(render_report(runs[0]), encoding="utf-8")
        print(f"\nsmoke artifacts written to {out_dir}")
        print(f"selection gate: {runs[0]['selection_gate']['classification']}")
        return 0

    # --- determinism ------------------------------------------------------
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

    all_identical = determinism["core_byte_identical"] and determinism[
        "analysis_final_byte_identical"
    ]

    # Publication is append-only: both destinations are checked before either is
    # written, so a collision cannot leave a fresh .json beside a stale .md.
    json_target = REPORTS_DIR / "structure_rrf_calibration.json"
    md_target = REPORTS_DIR / "structure_rrf_calibration_report.md"
    if not replace:
        existing = [
            str(target) for target in (json_target, md_target) if target.exists()
        ]
        if existing:
            print(
                "\nREFUSING to publish: recorded evaluation evidence already exists "
                "at " + ", ".join(existing) + ". Evaluation artifacts are "
                "append-only — move the previous report aside, write to a new "
                "name, or re-run with --replace for a deliberate re-publication.",
                file=sys.stderr,
            )
            return 2

    try:
        write_evidence(json_target, canonical(payload), replace=replace)
        write_evidence(md_target, render_report(payload), replace=replace)
    except ArtifactExistsError as exc:
        print(
            f"\nREFUSING to publish: {exc}\n"
            "Nothing was replaced. Evaluation artifacts are append-only — pass "
            "--replace only for a deliberate re-publication.",
            file=sys.stderr,
        )
        return 2

    print("\nwrote evaluation/reports/structure_rrf_calibration.json")
    print("wrote evaluation/reports/structure_rrf_calibration_report.md")

    gate = payload["selection_gate"]
    print()
    print(f"theoretical threshold structural_weight > "
          f"{gate['theoretical_threshold_structural_weight']:.6f}")
    for cid, sw, tw in SWEEP:
        c = payload["configurations"][cid]
        print(
            f"  {cid}: admission {c['reachability']['element_admission_count_overall']}, "
            f"top-k set changed {c['ranking_influence']['3_top_k_set_changes']['count']}, "
            f"gold changed {c['ranking_influence']['4_gold_evidence_changes']['count']}, "
            f"answer changed {c['ranking_influence']['5_answer_changes']['count']}, "
            f"harmful {c['ranking_influence']['harmful_changes']['count']}"
        )
    print(f"  determinism (byte-identical): {all_identical}")
    print(f"  SELECTED: {gate['selected_config']} -> {gate['classification']}")
    print(f"  {gate['final_status']}")

    if not all_identical:
        print("DETERMINISM FAILURE: runs differ — investigate before reporting.",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
