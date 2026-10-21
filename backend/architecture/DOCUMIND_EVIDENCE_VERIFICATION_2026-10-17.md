# DocuMind — claim-level evidence verification (2026-10-17)

Status: **EXPERIMENTAL, behind an opt-in switch.** The production default is unchanged.

> **Decision.** Keep the lexical verifier (`backend/generation/verification.py`) as the
> production default. Keep the relation-aware verifier
> (`backend/generation/verification_relations.py`) available under
> `DOCUMIND_VERIFIER=relations`, measured and documented. The candidate is substantially
> more accurate at *claim-level* support/contradiction decisions, but on the frozen
> generation benchmark it does not improve answer quality (EM equal, token F1 −0.027,
> spurious answers equal), so enabling it by default is not justified by this evidence.
> No production default, model, schema, API contract or frontend behaviour was changed.

## 1. Why the verifier, and what was wrong with it

The generator is `google/flan-t5-base`; the model-selection experiment
(`DOCUMIND_MODEL_SELECTION_2026-10-17.md`) found no replacement worth adopting, so the
binding constraint is *whether a generated claim is actually supported by the retrieved
evidence*. The production verifier decides that with word overlap plus number/entity
checks. Two failure modes follow directly from that:

1. **Correct paraphrase rejected.** "A failed calibration check blocks the robot from
   dispatch" does not share enough words with "the robot cannot be dispatched while a
   calibration failure is unresolved" to clear a 0.60 overlap rule, so a true answer is
   withheld.
2. **Unsupported claim accepted.** Word overlap cannot tell `stored in the maintenance
   log` from `kept for the warranty period`, nor an indicator from a cause, nor a
   narrower case from a universal claim.

The verifier also had no contradiction label at all: it could only say "supported" or
"not supported", so a reversed negation and a missing passage looked identical.

## 2. What was built

| Component | Path | Status |
|---|---|---|
| Relation-aware claim verifier (deterministic + paraphrase fallback) | `backend/generation/verification_relations.py` | EXPERIMENTAL |
| Verifier switch, aggregation into the existing `VerificationReport` | `backend/generation/verification.py` (`verifier_mode`, `verify_with_mode`) | IMPLEMENTED |
| Single call path used by engine and service | `backend/generation/engine.py:251`, `backend/generation/service.py` | IMPLEMENTED |
| Versioned claim-verification dataset (52 examples, dev/test split) | `backend/evaluation/datasets/claim_verification_v1.py` | IMPLEMENTED |
| Claim-level evaluation runner | `backend/evaluation/experiments/run_claim_verification_evaluation.py` | IMPLEMENTED |
| Tests (36) incl. adversarial and regression for single-token answers | `backend/tests/unit/generation/test_verification_relations.py` | IMPLEMENTED |

Per (claim, sentence) the verifier decides contradiction first, then support, else
insufficient evidence — never "similar enough".

* **Contradiction**
  * value conflict: the claim's numbers/units disagree while the sentence covers ≥75 %
    of the claim's salient terms;
  * reversed role (`Elena Vasquez is the CFO` against a `CFO: Robert Tanaka` list);
  * `same value` claim against a sentence that states two different values;
  * negation asymmetry where, ignoring negation, the two sentences are ≥75 % identical;
  * comparative pointing at a different subject — every comparison in both sentences is
    considered, and a shared head with a distinguishing modifier on each side
    (`manual … cheaper` vs `automated … cheaper`) counts as a different subject.
* **Support**
  * values/units agree and the sentence covers the claim's subject; or
  * word overlap ≥60 % **and** values/units agree (so "every 90 days" cannot be accepted
    against "every 30 days" on shared words alone); or
  * paraphrase fallback: cosine similarity ≥0.80, but **only** when the claim's head term
    is present, the claim states **no value**, and the sentence is checked first for
    universals and causal language.
* **Guards against similarity laundering**
  * a claim with added qualifiers is not accepted via similarity
    (`kept for the warranty period of five years` vs `stored in the maintenance log for
    five years`, cosine 0.87 — rejected);
  * a universal claim (`always`, `invariably`) needs universal evidence;
  * a causal claim (`causes`, `leads to`, `because`, …) needs the evidence to state a
    causal relation, not merely co-occurrence;
  * a value-only answer (`every 30 days`) is attributed only to a sentence that mentions
    the question's entity (≥50 % of the question's content terms), so a bare table cell
    (`1`) cannot be attributed to an unrelated question.
* **Partial answers** — claims joined by `and`/`but` are verified clause by clause, so an
  answer whose parts come from different passages is not rejected for that reason, while
  a mixed answer aggregates to `PARTIALLY_SUPPORTED` instead of `SUPPORTED`.
* **Citations** — a claim's stated `[n]` is separate from its truth: `citation_ok=False`
  when the stated block is not among the supporting blocks, and the verdict keeps both.

## 3. Claim-verification dataset

`evaluation/datasets/claim_verification_v1.py`: 52 hand-written **synthetic** examples
(29 dev / 23 held-out test), labels `SUPPORTED` 20, `CONTRADICTED` 20,
`INSUFFICIENT_EVIDENCE` 12. Contradiction and absent evidence are never merged.

Categories (A–K, M from the mission's failure taxonomy):
paraphrase A 6, word-overlap false claim B 5, correct numeric C 5, wrong numeric/unit D 5,
correct entity E 3, wrong entity F 4, negation G 4, unsupported causation H 4,
unsupported comparison I 4, multi-passage J 4, wrong citation K 3, insufficient or
contradictory evidence M 5. Also: 2 hard examples, 3 citation-error examples,
1 evidence-conflict example.

Annotation rules: an added qualifier that the evidence never states is *not* supported;
a value with the wrong unit is contradicted; an unmentioned entity is insufficient, not
contradicted. `B04` is the one label whose strength is contestable — the evidence says
records are *stored in the maintenance log* for five years, the claim says *kept for the
warranty period*; the dataset calls that contradicted, the verifier calls it insufficient
(see §6). The label was left as written; it was not changed after results were seen.

The dataset is synthetic. **None of its numbers are real-world accuracy**; it exists to
separate support from contradiction and from absence.

## 4. Claim-level results

`python -m evaluation.experiments.run_claim_verification_evaluation --split dev|test`
→ `evaluation/reports/claim_verification_2026-10-17_final/`. The earlier
`claim_verification_2026-10-17_r2 … _r8` directories are the calibration history and were
not overwritten; `_final` is the frozen build reported below.

Held-out test (23 examples), same evidence and claim strings for both verifiers:

| Metric | Lexical (production) | Relation-aware |
|---|---:|---:|
| Support precision | 0.333 | **1.000** |
| Support recall | 0.444 | **0.778** |
| Support F1 | 0.381 | **0.875** |
| Contradiction precision | n/a (no label) | **1.000** |
| Contradiction recall | 0.000 (structural) | **0.750** |
| False-accept rate (unsupported accepted) | 0.571 | **0.000** |
| False-reject rate (supported refused) | 0.556 | **0.222** |
| Insufficient-evidence handled correctly | 0/6 | **6/6** |
| Wrong citations detected | 1/1 | 1/1 |

Dev split (29 examples, used for calibration): support F1 0.462 → **0.909**,
false-accept 0.500 → **0.056**, false-reject 0.455 → **0.091**, insufficient 0/6 → 6/6.

Per category on the held-out split (correct / examples, lexical → relation):
A 0/3 → 2/3, B 0/2 → 0/2, C 2/2 → 2/2, D 0/2 → 2/2, E 0/1 → 1/1, F 0/2 → 2/2,
G 0/2 → 2/2, H 0/2 → 2/2, I 1/2 → 2/2, J 0/2 → 1/2, K 1/1 → 1/1, M 0/2 → 2/2.

## 5. Effect on the frozen generation benchmark

Frozen benchmark unchanged: `phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl`,
sha256 `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` (re-verified
before and after the runs). Same protocol, same 182 rows, 10 marks; the lexical control
was re-run on this checkout (`..._fmt10_r2`) and reproduces the recorded baseline exactly,
so the comparison is like for like:

| Metric | Lexical (`..._fmt10_r2`) | Relation-aware (`..._fmt10_relations_r5`) |
|---|---:|---:|
| Exact match (answerable) | 0.129 | 0.129 |
| Token F1 (answerable) | 0.257 | **0.230** |
| Abstention on unanswerable | 0.952 | 0.952 |
| Spurious answer on unanswerable | 0.048 | 0.048 |
| Unsupported-claim rate | 0.198 | **0.165** |
| Citation accuracy | 0.802 | **0.835** |
| Verified rate | 0.396 | 0.412 |
| Answers withheld as unattributable | 22 | 23 |
| Empty-answer rate | 0.577 | 0.582 |

The verifier changes *which* answers survive, not how many: 11 previously withheld
answerable rows are now answered and 12 previously answered rows are now withheld, with
no change on any unanswerable row. Exact match is identical row by row (the same 18 of
140), and F1 is lower by 0.027 because the 12 withdrawn answers carried more partial
overlap than the 11 admitted ones — about four answers' worth of token overlap, inside
the noise band for 140 rows. **The candidate is not an answer-quality improvement on
this benchmark.**

Mark depth is unaffected (5/10/15 marks, `mark_depth_2026-10-17_relations_r4`):
mean words 17.0 / 49.4 / 73.4, key-fact recall 0.617 / 0.767 / 0.933, every answer
`SUPPORTED`, unsupported-claim rate 0.0 — identical to the lexical run. Short factual
answers stay supported: the numeric question (*"How often is the lidar array
calibrated?"*) returns `every 30 days` at all three depths, where an early revision of
the candidate withheld it.

## 6. Remaining errors (not hidden)

| Case | Gold | Verdict | Why |
|---|---|---|---|
| `A06` "Lidar needs recalibrating once a month." | SUPPORTED | INSUFFICIENT | "once a month" = 30 days needs calendar knowledge; no period normalisation |
| `J03` "…calibration cannot repair physical damage" | SUPPORTED | INSUFFICIENT | `repair`→`correct`, `physical`→`physically` defeat the stemmer; cosine 0.75 < 0.80 |
| `B03` "Repeated failures … cause a worn bearing." | CONTRADICTED | INSUFFICIENT | causal guard refuses; it abstains rather than accepting the causal claim |
| `B04` "…kept for the warranty period of five years." | CONTRADICTED | INSUFFICIENT | added qualifier refused (§3: label strength is contestable) |
| `I02` dev "…take about the same time." | CONTRADICTED | SUPPORTED | contradiction spans two passages (2 h vs 30 min); per-sentence check cannot compare across blocks |

## 7. Acceptance gates

| Gate | Result | Evidence |
|---|---|---|
| 1 — no worse safety | **MET** on the claim set (false-accept 0.571 → 0.000 held-out, 0.500 → 0.056 dev) and on the benchmark (spurious 0.048 = 0.048, unsupported 0.198 → 0.165) | §4, §5 |
| 2 — supported paraphrases accepted | **MET** (A 0/3 → 2/3 held-out; `blocks dispatch` accepted) | §4 |
| 3 — contradiction ≠ absence | **MET** (separate labels; contradiction recall 0.75, precision 1.0) | §4 |
| 4 — numbers, dates, units, entities | **MET** (D 0/2 → 2/2; `every 90 days`/`30 weeks` contradicted; wrong entity insufficient) | §4, tests |
| 5 — partial answers | **MET** (`PARTIALLY_SUPPORTED` + per-claim verdicts; clause-wise support) | tests |
| 6 — citation correctness | **MET** (1/1 wrong citations flagged; truth and citation reported separately) | §4 |
| 7 — existing behaviour | **MET** (single-token answers, abstention, 5/10/15 depths; 36 new tests; 1498 passed) | §5, §8 |
| 8 — runtime | **MET with measurement** (see §8) | §8 |
| 9 — reproducibility | **MET** (frozen benchmark hash verified; same protocol; new run directories only) | reports |
| 10 — release authorisation | **NOT REQUESTED** — production default unchanged | this document |

## 8. Runtime, resources, security

* Verification cost per claim (steady state, after warm-up): lexical **0.07 ms**,
  relation-aware **4.7–5.8 ms** mean, **23.8 ms** max (23–29 examples per split).
* One-off embedder cost in a fresh process: **9.7–10.6 s** load, **+458 MB RSS**. In
  production this cost already exists — the retrieval path loads the same MiniLM model
  — so the marginal cost of the verifier is the per-claim time above, not a second model.
  Two encodes per (claim, sentence) pair are cached by text in-process.
* No generative model, no network call, no new service, no schema change, no migration.
* **Prompt injection:** the verifier never builds a prompt; evidence text is consumed by
  regex/tokenisation and by a local embedding model, so document text cannot direct it,
  authorise a tool, or change the decision procedure. This is exactly the property an
  LLM-based entailment layer would give up.
* **Untrusted input:** malformed/empty evidence and claims yield
  `INSUFFICIENT_EVIDENCE`, never a vacuous pass; a 400-sentence evidence block is
  processed in-bounds (unit test asserts < 5 s).
* **Citations** are returned as indices of the evidence blocks that were actually
  checked, so a verdict cannot invent a source reference.
* **Privacy:** no evidence or answer text is logged by the verifier; artifacts written
  in this pass contain only synthetic claim fixtures and the frozen benchmark.

## 9. What is NOT claimed

* Not entailment: a `SUPPORTED` label means "every claim is attributed to evidence that
  contains it", not "the answer is correct".
* Not real-world accuracy: the claim dataset is synthetic and small (23 held-out).
* Not a benchmark improvement: EM equal, F1 −0.027, spurious answers equal. The
  candidate is *safer at claim granularity*, not *better at answering*.
* No production switch was flipped, no commit was made, and `DOCUMIND_VERIFIER` is unset
  in every shipped default.

## 10. Highest-priority next action

Label the claim-level support of the **actual generated answers** on the 140 answerable
frozen-benchmark rows (the candidate already withholds 23 of 182 answers for
attribution), and use that as the evaluation set. Until that exists, claim-level
accuracy is being measured on synthetic evidence/claim pairs while the benchmark still
measures only EM/F1 — the gap that allows a verifier to improve one and not the other.

Secondary, in order: period normalisation (`once a month` = 30 days), a stemmer that
maps `damage/damaged` and `repair/correct`, and cross-passage contradiction for
"same value" claims.
