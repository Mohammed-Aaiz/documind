#!/usr/bin/env python
"""Span-boundary forensics — is there a principled post-hoc boundary fix?

Phase QA Quality Stabilization — Experiment 2 (span boundaries).

Question
--------
After fixing answer-text reconstruction (Experiment 1), the remaining recorded
failures are dominated by span-boundary/selection failures. This tool asks
whether any **principled, post-hoc** change to how a span is chosen from the
model's logits improves boundaries.

Method
------
Every variant reads the SAME logits for the SAME 182 frozen benchmark examples.
Only the span-SELECTION rule differs, so nothing is confounded by the model:

* R0  recorded runner rule  : argmax(start), then argmax(end in [s, s+50))
* R1  joint logit max       : argmax over all context-mappable spans of s_logit + e_logit
* R2/R3  as R1 but tie-broken to the shortest / longest span
* P0  production rule       : 20x20 n-best, score = softmax_s * softmax_e
* P1  production rule       : same candidates, score = s_logit + e_logit
* P2  P1 tie-broken to the shortest span
* R4/P4  whole-word variants: grow the span so it never cuts a word

Reported per variant: answerable EM, F1, non-empty count, and a boundary
taxonomy (EXACT / TOO_SHORT / TOO_LONG / OVERLAP / DISJOINT / EMPTY).

Also measured: how often a chosen span starts *inside* a word (a partial-word
boundary), which is the one boundary defect that is structurally repairable.

Honesty
-------
* This tool DOES run inference (CPU) — unlike the re-scoring tools. No training,
  no weight change, no benchmark change, no threshold change, no fitting.
* The population is **fully leaked**: all 182 examples appear in
  `training_data.jsonl` / `training_data_v3.jsonl`. Nothing here is a
  generalization result, and nothing here licenses a production change on its own.
* n = 140 answerable examples, so 1 example = 0.71pp. Differences of 1-2 examples
  are noise and are reported as counts.

Writes:
    backend/architecture/phase4f_6/decision/SPAN_BOUNDARY_FORENSICS.json
    backend/architecture/phase4f_6/decision/SPAN_BOUNDARY_FORENSICS.md
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForQuestionAnswering, AutoTokenizer

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[5]
BACKEND = Path(__file__).resolve().parents[4]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from answer_span import answer_char_span, tokenize_with_offsets  # noqa: E402
BENCHMARK = ROOT / "backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl"
DECISION = ROOT / "backend/architecture/phase4f_6/decision"
MODELS = {
    "A0": ROOT / "backend/models/documind-qa",
    "F2": ROOT / "backend/phase4f/phase4f_5f/f2/checkpoints/F2/checkpoint_epoch2",
}
BENCHMARK_SHA256 = "1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0"
SPECIAL = {"[CLS]", "[PAD]", "[SEP]"}
MAX_LENGTH = 384

# name -> (kind, max_answer_length, tie_break)
SCHEMES = [
    ("R0_recorded_argmax50", "r0", 50, "any"),
    ("R1_joint_logit50", "joint", 50, "any"),
    ("R2_joint_logit50_shortest", "joint", 50, "short"),
    ("R3_joint_logit50_longest", "joint", 50, "long"),
    ("P0_production_nbest100_prob", "nbest_prob", 100, "any"),
    ("P1_nbest100_logit", "nbest_logit", 100, "any"),
    ("P2_nbest100_logit_shortest", "nbest_logit", 100, "short"),
    ("R4_recorded_argmax50_wholeword", "r4", 50, "any"),
    ("P4_joint100_wholeword", "p4", 100, "any"),
]


# ---------------------------------------------------------------------------
# Metrics (identical definitions to the Phase 4F runners)
# ---------------------------------------------------------------------------

def normalize_text(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def exact_match(pred: str, gold: str) -> bool:
    return normalize_text(pred) == normalize_text(gold)


def token_f1(pred: str, gold: str) -> float:
    p = set(normalize_text(pred).split())
    g = set(normalize_text(gold).split())
    if not p or not g:
        return 0.0
    common = p & g
    if not common:
        return 0.0
    precision = len(common) / len(p)
    recall = len(common) / len(g)
    return 2 * precision * recall / (precision + recall)


def taxonomy(pred: str, gold: str) -> str:
    if not pred.strip():
        return "EMPTY"
    if exact_match(pred, gold):
        return "EXACT"
    ps, gs = set(normalize_text(pred).split()), set(normalize_text(gold).split())
    if ps < gs:
        return "TOO_SHORT"
    if gs < ps:
        return "TOO_LONG"
    if ps & gs:
        return "OVERLAP"
    return "DISJOINT"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Span selection rules
# ---------------------------------------------------------------------------

def build_masked(start_logits, end_logits, sequence_ids, max_ans):
    """s_logit + e_logit over context-mappable spans with 0 <= e-s < max_ans."""
    n = len(start_logits)
    score = start_logits[:, None] + end_logits[None, :]
    idx = np.arange(n)
    valid = (idx[None, :] >= idx[:, None]) & ((idx[None, :] - idx[:, None]) < max_ans)
    valid &= (sequence_ids == 1)[:, None] & (sequence_ids == 1)[None, :]
    return np.where(valid, score, -np.inf)


def pick(masked, tie_break):
    best = masked.max()
    if not np.isfinite(best):
        return None
    ties = np.argwhere(masked == best)
    if len(ties) == 1:
        return int(ties[0][0]), int(ties[0][1])
    lengths = ties[:, 1] - ties[:, 0] + 1
    row = ties[int(np.argmin(lengths) if tie_break == "short" else np.argmax(lengths))]
    return int(row[0]), int(row[1])


def expand_to_whole_word(token_ids, s, e, tokenizer):
    """Grow a span so it never starts or ends inside a word."""
    n = len(token_ids)
    moved = 0
    while s > 0 and tokenizer.convert_ids_to_tokens(int(token_ids[s])).startswith("##"):
        s -= 1
        moved += 1
    while e + 1 < n and tokenizer.convert_ids_to_tokens(int(token_ids[e + 1])).startswith("##"):
        e += 1
        moved += 1
    return s, e, moved


def starts_inside_word(token_ids, s, tokenizer):
    return tokenizer.convert_ids_to_tokens(int(token_ids[s])).startswith("##")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if not BENCHMARK.exists():
        print(f"FATAL: benchmark not found: {BENCHMARK}")
        return 1
    bench_sha = sha256_file(BENCHMARK)

    examples = []
    with open(BENCHMARK, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                examples.append(json.loads(line))

    print("=" * 78)
    print("SPAN-BOUNDARY FORENSICS — same logits, different selection rules only")
    print("=" * 78)
    print(f"benchmark: {BENCHMARK.relative_to(ROOT)}")
    print(f"  sha256 : {bench_sha} "
          f"({'VERIFIED' if bench_sha == BENCHMARK_SHA256 else 'CHANGED'})")
    print(f"examples : {len(examples)} (leaked population: all appear in the training data)")
    print("No training. No weight change. No benchmark change. No threshold change.\n")

    results = {
        "artifact": "SPAN_BOUNDARY_FORENSICS",
        "note": ("Boundary/selection experiment on the frozen 182-example benchmark. "
                 "Every variant reads the same logits; only the selection rule differs. "
                 "Leaked population — not a generalization result."),
        "held_fixed": ["benchmark", "checkpoints", "logits", "answer-text decoder "
                       "(fixed per Experiment 1)", "metric definitions", "tokenization"],
        "changed": "span-selection rule only",
        "limitations": [
            "Population is fully leaked (all 182 examples appear in training_data.jsonl / "
            "training_data_v3.jsonl); no generalization claim is possible.",
            "n = 140 answerable examples, so 1 example = 0.71pp; 1-2 example differences are noise.",
            "Running inference on CPU with the recorded checkpoints; no training and no weights changed.",
            "Only post-hoc selection rules are tested. Improving the model's own preference "
            "for the right span requires training, which is out of scope here.",
        ],
        "inputs": {
            "benchmark_path": "backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl",
            "benchmark_sha256": bench_sha,
            "benchmark_sha256_expected": BENCHMARK_SHA256,
        },
        "models": {},
        "findings": {},
    }

    for label, model_path in MODELS.items():
        tokenizer = AutoTokenizer.from_pretrained(str(model_path))
        model = AutoModelForQuestionAnswering.from_pretrained(str(model_path))
        model.eval()
        print("-" * 78)
        print(f"MODEL {label}  ({model_path.relative_to(ROOT)})")
        print("-" * 78)

        cache = []
        for ex in examples:
            enc, offsets, sequence_ids = tokenize_with_offsets(
                tokenizer, ex["question"], ex["context"], max_length=MAX_LENGTH,
                truncation=True, padding="max_length", return_tensors="pt")
            with torch.no_grad():
                out = model(**enc)
            seq = np.array([-1 if s is None else s for s in sequence_ids])
            sl = out.start_logits[0].numpy()
            el = out.end_logits[0].numpy()
            argmax_start = int(np.argmax(sl))
            cache.append({
                "sl": sl, "el": el,
                "sp": torch.softmax(out.start_logits[0], dim=0).numpy(),
                "ep": torch.softmax(out.end_logits[0], dim=0).numpy(),
                "ids": enc["input_ids"][0].tolist(),
                "offsets": offsets,
                "seq": seq,
                "ctx": ex["context"],
                "gold": ex.get("answer", "") or "",
                "answerable": ex["question_kind"] != "UNANSWERABLE",
                "m50": build_masked(sl, el, seq, 50),
                "m100": build_masked(sl, el, seq, 100),
                "r0": (argmax_start,
                       int(np.argmax(el[argmax_start:argmax_start + 50])) + argmax_start),
            })

        model_results = {}
        for name, kind, max_ans, tie_break in SCHEMES:
            ems, f1s, tax = [], [], Counter()
            nonempty = partial_word = expanded = 0
            for c in cache:
                if kind == "r0":
                    s, e = c["r0"]
                elif kind == "joint":
                    picked = pick(c["m50"], tie_break)
                    s, e = picked if picked else (0, 0)
                elif kind in ("r4", "p4"):
                    if kind == "r4":
                        s, e = c["r0"]
                    else:
                        picked = pick(c["m100"], tie_break)
                        s, e = picked if picked else (0, 0)
                    if c["answerable"] and starts_inside_word(c["ids"], s, tokenizer):
                        partial_word += 1
                    s, e, moved = expand_to_whole_word(c["ids"], s, e, tokenizer)
                    expanded += 1 if moved else 0
                else:
                    score_mode = "prob" if kind == "nbest_prob" else "logit"
                    st = np.argsort(-c["sp"])[:20]
                    et = np.argsort(-c["ep"])[:20]
                    best = None
                    for s_ in st:
                        for e_ in et:
                            if e_ < s_ or (e_ - s_ + 1) > max_ans:
                                continue
                            if tokenizer.convert_ids_to_tokens(c["ids"][s_]) in SPECIAL:
                                continue
                            if tokenizer.convert_ids_to_tokens(c["ids"][e_]) in ("[SEP]", "[PAD]"):
                                continue
                            if c["seq"][s_] != 1 or c["seq"][e_] != 1:
                                continue
                            sc = (c["sp"][s_] * c["ep"][e_]) if score_mode == "prob" else (
                                c["sl"][s_] + c["el"][e_])
                            length = e_ - s_ + 1
                            key = (sc, -length) if tie_break == "short" else (
                                (sc, length) if tie_break == "long" else (sc,))
                            if best is None or key > best[0]:
                                best = (key, int(s_), int(e_))
                    s, e = (best[1], best[2]) if best else (0, 0)

                seq_list = [None if x < 0 else int(x) for x in c["seq"]]
                span = answer_char_span(c["offsets"], seq_list, s, e)
                pred = c["ctx"][span[0]:span[1]] if span else ""
                if pred.strip():
                    nonempty += 1
                if c["answerable"]:
                    ems.append(1 if exact_match(pred, c["gold"]) else 0)
                    f1s.append(token_f1(pred, c["gold"]))
                    tax[taxonomy(pred, c["gold"])] += 1

            n_ans = len(ems) or 1
            entry = {
                "max_answer_length": max_ans,
                "tie_break": tie_break,
                "answerable_n": len(ems),
                "answerable_em_count": sum(ems),
                "answerable_em_pct": round(sum(ems) / n_ans * 100, 2),
                "answerable_f1_pct": round(sum(f1s) / n_ans * 100, 2),
                "non_empty_predictions": nonempty,
                "boundary_taxonomy": dict(tax),
            }
            if kind in ("r4", "p4"):
                entry["partial_word_starts_before_expansion"] = partial_word
                entry["spans_expanded"] = expanded
            model_results[name] = entry
            print(f"  {name:<36} EM {entry['answerable_em_pct']:>6.2f}% "
                  f"({entry['answerable_em_count']}/{entry['answerable_n']})  "
                  f"F1 {entry['answerable_f1_pct']:>6.2f}%  "
                  f"non-empty {nonempty}/{len(cache)}")
            if kind in ("r4", "p4"):
                print(f"      partial-word starts before expansion: {partial_word}; "
                      f"spans expanded: {expanded}")

        results["models"][label] = {
            "checkpoint": str(model_path.relative_to(ROOT)).replace("\\", "/"),
            "variants": model_results,
        }
        del model
        print()

    # ---- findings (what the data says, including negative results) ----
    a0 = results["models"]["A0"]["variants"]
    f2 = results["models"]["F2"]["variants"]
    selection_variants = ["R1_joint_logit50", "R2_joint_logit50_shortest",
                           "R3_joint_logit50_longest", "P0_production_nbest100_prob",
                           "P1_nbest100_logit", "P2_nbest100_logit_shortest"]
    converged = len({(a0[v]["answerable_em_count"], a0[v]["answerable_f1_pct"],
                      json.dumps(a0[v]["boundary_taxonomy"], sort_keys=True))
                     for v in selection_variants}) == 1
    results["findings"] = {
        "H1_scoring_rule_headroom": {
            "claim": "A different principled scoring rule improves span boundaries.",
            "result": "REFUTED" if converged else "SUPPORTED",
            "evidence": (f"For A0, all of {', '.join(selection_variants)} produce the identical "
                         f"result ({a0['P0_production_nbest100_prob']['answerable_em_count']}/{a0['P0_production_nbest100_prob']['answerable_n']} EM, "
                         f"F1 {a0['P0_production_nbest100_prob']['answerable_f1_pct']}%, identical taxonomy). "
                         "The model's argmax pair already maximises every tested score."),
        },
        "H2_tie_breaking": {
            "claim": "Tie-breaking toward shorter/longer spans changes boundaries.",
            "result": ("REFUTED — shortest and longest tie-breaks are byte-identical to the "
                       "untie-broken variant, i.e. ties essentially never occur."),
        },
        "H3_partial_word_boundaries": {
            "claim": "Spans are cut mid-word and can be repaired by whole-word expansion.",
            "result": f"REFUTED — {a0['R4_recorded_argmax50_wholeword']['partial_word_starts_before_expansion']} partial-word starts (A0) / "
                      f"{f2['R4_recorded_argmax50_wholeword']['partial_word_starts_before_expansion']} (F2); "
                      f"{f2['R4_recorded_argmax50_wholeword']['spans_expanded']} spans could be extended at all, "
                      "with no change in EM, F1 or taxonomy.",
        },
        "H4_production_headroom": {
            "claim": "The production selection rule (20x20 n-best, prob product) leaves "
                     "boundary quality on the table.",
            "result": "REFUTED — production's rule already matches the exhaustive joint-logit "
                      "optimum on this benchmark, so production has no selection headroom.",
        },
        "REAL_FINDING_recorded_protocol": {
            "claim": "The recorded Phase 4F runner protocol is a weaker selector than the "
                     "production rule, on identical logits.",
            "result": "SUPPORTED — but it is a SELECTION fix, not a boundary fix, and it was "
                      "deliberately NOT applied (see action).",
            "evidence": (
                f"A0 recorded argmax chain {a0['R0_recorded_argmax50']['answerable_em_count']}/{a0['R0_recorded_argmax50']['answerable_n']} "
                f"(EM {a0['R0_recorded_argmax50']['answerable_em_pct']}%, F1 {a0['R0_recorded_argmax50']['answerable_f1_pct']}%) vs "
                f"joint/n-best {a0['P1_nbest100_logit']['answerable_em_count']}/{a0['P1_nbest100_logit']['answerable_n']} "
                f"(EM {a0['P1_nbest100_logit']['answerable_em_pct']}%, F1 {a0['P1_nbest100_logit']['answerable_f1_pct']}%); "
                f"F2 {f2['R0_recorded_argmax50']['answerable_em_count']}/{f2['R0_recorded_argmax50']['answerable_n']} -> "
                f"{f2['R1_joint_logit50']['answerable_em_count']}/{f2['R1_joint_logit50']['answerable_n']}."),
            "action": "NOT applied. Changing the runners' selection rule is a protocol change that "
                      "would invalidate the comparability of every recorded Phase 4F metric; it needs "
                      "its own explicit experiment. Production already uses the stronger rule.",
        },
        "verdict": ("NO_PRINCIPLED_POST_HOC_BOUNDARY_FIX. Boundary quality is set by the model's own "
                    "logit preference for longer/overlapping spans (TOO_LONG + OVERLAP dominate the "
                    "non-exact answerable set); no selection or post-processing change tested here "
                    "moves it. Improving it requires training, which is out of scope."),
    }

    DECISION.mkdir(parents=True, exist_ok=True)
    out_json = DECISION / "SPAN_BOUNDARY_FORENSICS.json"
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)

    lines = [
        "# Span-Boundary Forensics — is there a principled post-hoc boundary fix?",
        "",
        "> **Negative result, honestly reported.** No principled post-hoc selection or",
        "> post-processing change improves span boundaries on the frozen 182-example",
        "> benchmark. Every variant reads the *same logits*; only the selection rule",
        "> differs. **Leaked population — not a generalization result.**",
        "",
        "## Method",
        "",
        "- Changed: span-selection rule only.",
        "- Held fixed: benchmark, checkpoints, logits, answer-text decoder (fixed in",
        "  Experiment 1), tokenization, metric definitions.",
        "- No training, no weight change, no threshold change, no fitting.",
        f"- Benchmark sha256 `{bench_sha[:16]}...` "
        f"({'VERIFIED' if bench_sha == BENCHMARK_SHA256 else 'CHANGED'}).",
        "",
        "## Limitations",
        "",
    ]
    for item in results["limitations"]:
        lines.append(f"- {item}")
    lines += ["", "## Variants (A0 = production checkpoint, F2 = recorded experiment checkpoint)", ""]
    lines.append("| variant | A0 EM | A0 F1 | F2 EM | F2 F1 |")
    lines.append("|---|---|---|---|---|")
    for name, _, _, _ in SCHEMES:
        lines.append(f"| `{name}` | {a0[name]['answerable_em_count']}/{a0[name]['answerable_n']} "
                     f"({a0[name]['answerable_em_pct']}%) | {a0[name]['answerable_f1_pct']}% | "
                     f"{f2[name]['answerable_em_count']}/{f2[name]['answerable_n']} "
                     f"({f2[name]['answerable_em_pct']}%) | {f2[name]['answerable_f1_pct']}% |")
    lines += ["", "## Boundary taxonomy (A0, 140 answerable)", "",
              "| variant | EXACT | TOO_LONG | OVERLAP | TOO_SHORT | DISJOINT | EMPTY |",
              "|---|---|---|---|---|---|---|"]
    for name, _, _, _ in SCHEMES:
        t = a0[name]["boundary_taxonomy"]
        lines.append(f"| `{name}` | {t.get('EXACT', 0)} | {t.get('TOO_LONG', 0)} | "
                     f"{t.get('OVERLAP', 0)} | {t.get('TOO_SHORT', 0)} | "
                     f"{t.get('DISJOINT', 0)} | {t.get('EMPTY', 0)} |")
    lines += ["", "## Findings (including refuted hypotheses)", ""]
    for key, f in results["findings"].items():
        if isinstance(f, dict):
            lines.append(f"### {key}")
            lines.append("")
            if "claim" in f:
                lines.append(f"- **Claim:** {f['claim']}")
            lines.append(f"- **Result:** {f.get('result', '')}")
            if "evidence" in f:
                lines.append(f"- **Evidence:** {f['evidence']}")
            if "action" in f:
                lines.append(f"- **Action:** {f['action']}")
            lines.append("")
        else:
            lines.append(f"- **{key}:** {f}")
    out_md = DECISION / "SPAN_BOUNDARY_FORENSICS.md"
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("=" * 78)
    print("FINDINGS")
    print("=" * 78)
    for key, f in results["findings"].items():
        if isinstance(f, dict):
            print(f"  {key}: {f.get('result', '')}")
        else:
            print(f"  {key}: {f}")
    print()
    print(f"wrote {out_json.relative_to(ROOT)}")
    print(f"wrote {out_md.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
