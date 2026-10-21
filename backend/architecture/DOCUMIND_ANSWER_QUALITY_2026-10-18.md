# Answer coverage and the answerability gate — Mission 4 record (2026-10-18)

Status: **IMPLEMENTED — MEASURED**. One production change (gate vocabulary).
Production verifier default unchanged (`lexical`); no model, prompt, retrieval,
threshold, schema, dataset or frontend change. No commit was made.

Diagnostic evidence: `backend/evaluation/reports/answer_quality_diagnosis_2026-10-18_m4/`
(`REPORT.md`, `analysis.json`).
Before/after runs: `generation_benchmark_2026-10-18_m4_baseline`,
`generation_benchmark_2026-10-18_m4_post_v2` (repeat: `..._m4_post_v2_r2`).
The rejected ordinal-inclusive variant is kept as `..._m4_post` (same EM/F1,
spurious 3/42) so the correction is auditable.
Claim-level baseline: `answer_claim_evaluation_2026-10-18_m4_baseline_v1` / `_v2`.

## 1. Verified baseline

140 answerable / 42 unanswerable rows; benchmark SHA-256
`1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0`.
75/140 answerable questions produced an answer (53.6 %); 49 were refused by the
answerability gate and 16 were withheld after generation. 75 propositional
claims (66 SUPPORTED, 5 CONTRADICTED, 2 INSUFFICIENT, 2 PARTIAL) and 28
non-claims (v2); lexical support F1 0.880, relation-aware 0.977; 57/75 claims
answer their question, 9 supported claims are off-target.

## 2. Diagnosed cause

`generation.verification.answerability` counts every content token except
`_QUESTION_WORDS` and `_GENERIC_QUESTION_TERMS` as a topic term and refuses when
more than one is absent. The benchmark's section/table/boundary question
templates use document-structure vocabulary (`section`, `content`, `covered`,
`near`, `boundary`, `between`, `table`, `looking`, `show`, `detailed`,
`context`, `listed`, `comes`, `monetary`, `amount`, `metric`, `count`), which is
not evidence vocabulary even when the answer is present. 44 of the 49 refusals
contained such terms; all 49 had the gold answer inside the recorded context.

## 3. Change

`backend/generation/verification.py`:

* new `_STRUCTURAL_QUESTION_TERMS` (20 terms above), subtracted from
  distinctive question terms;
* ordinals deliberately excluded — adding `first`/`second` let the unanswerable
  row `unans_3b23eb33` ("When was the first version released?") answer
  `September 2025`; keeping them as topic terms preserves the abstention.

Tests: `backend/tests/unit/generation/test_generation_mark_depth.py`
(section question allowed, boundary question allowed, ordinal still refused).
Focused 30 passed; full unit suite 1578 passed / 23 skipped / 0 failed;
`compileall` clean.

## 4. Measured effect (same 182 rows, same hash, unchanged annotations)

| Metric | Before | After |
|---|---:|---:|
| Answerable answered | 75/140 (53.6 %) | 99/140 (70.7 %) |
| Gate abstentions (answerable) | 49 | 13 |
| Withheld (answerable) | 16 | 28 |
| Exact match | 0.1286 | 0.1500 |
| Token F1 | 0.2567 | 0.3091 |
| Unanswerable spurious | 2/42 | 2/42 |
| Unsupported-claim rate | 0.1981 | 0.2199 |
| Citation accuracy | 0.8019 | 0.7801 |

24 new answers, 0 lost, 0 changed; 3 exact matches. The two post runs produce
identical answers (only latency varies). The unsupported-claim rate rises
because more table/list answers are now emitted; the extra spurious unanswerable
answer seen with the ordinal variant (`..._m4_post`, spurious 3/42) is gone.

## 5. Not changed (no-go findings)

* **8 false withholdings** from the lexical verifier (correct values, including
  two exact gold answers, and values inside over-wide lists) and 2 withheld rows
  with no recorded claim: a verifier-policy decision, explicitly out of scope.
* **28 non-claims** (22 table header renders, 5 fragments, 1 heading): excluded
  from the propositional denominator, harmless to support metrics; dataset
  frozen.
* **9 supported off-target claims**: 4 wrong attribute/value/time, 5 single-cell
  answers to row/table questions. Generation/extraction, no small evidence-backed
  fix at this sample size.

## 6. Remaining limitations

The gate is still lexical: 13 answerable refusals remain (5 paraphrase/unit/
header-stripped cases, 8 boundary cases). Coverage gains surface 21
verified-but-not-exact answers. No integration/E2E/browser/DB/live-server run,
single annotator, 75 propositional claims, one benchmark, no new 15-mark run.
