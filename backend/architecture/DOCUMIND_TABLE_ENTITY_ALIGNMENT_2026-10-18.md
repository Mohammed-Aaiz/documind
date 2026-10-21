# Table entity alignment in the lexical verifier — Mission 5 record (2026-10-18)

Status: **IMPLEMENTED — MEASURED**. One production change, confined to
`generation/verification.py`. Production verifier default remains `lexical`; no
model, prompt, retrieval, threshold, schema, dataset, annotation or frontend
change. No commit was made.

Evidence:

* diagnosis, ledger (182 rows) and plan:
  `backend/evaluation/reports/answer_quality_mission5_2026-10-18_diagnosis/`;
* before/after generation: `generation_benchmark_2026-10-18_m4_post_v2` →
  `generation_benchmark_2026-10-18_m5_post_v1` (repeat `..._m5_post_v1_r2`);
* claim-level: `answer_claim_evaluation_2026-10-18_m4_baseline_v2` →
  `..._m5_v2`.

## Defect

`numeric_entity_alignment` located the question's rarest term and anchored on
the sentence containing it. In a pipe table the rarest term is a **column
name**, so the anchor was the header row. Its subject (`tier, rate`) is absent
from the value row, producing a false "value belongs to a different entity"
verdict. Reproduced on `tc_8340538b` (`1,000 req/min`), `tc_06f5c7e8`
(`+4.2%`), and also on four cases where the value genuinely belongs to another
column (`tc_1658c1fb`, `tc_479dca78`, `tc_dcc6b88d`, `tc_03298034`) — the
function could not tell the two apart.

## Change

For evidence that parses as a simple table (header, at least one equal-width
data row, ≥3 cells):

* cell 0 is the row label/table title, never an attribute column;
* the asked column is the header cell (index > 0) sharing the most raw question
  terms, leftmost on a tie;
* the data row is found by its label;
* the claim is `matched` only when all of its numbers in that row sit in the
  asked column; otherwise `mismatch`.

Anything else (not a table, no matching header, unequal widths) uses the
previous prose rule unchanged. No thresholds were changed.

Tests: 6 new in `tests/unit/generation/test_generation_entity_verification.py`
(asked-column match, wrong column, wrong row, compound spanning columns, table
title fallback, prose fallback). Focused 25 passed; full unit suite **1584
passed / 23 skipped / 0 failed**; `compileall` exit 0.

## Measured effect (same 182 rows, same hash, unchanged annotations)

| Metric | M4 (pre-M5) | M5 |
|---|---:|---:|
| Answerable answered | 99/140 | 100/140 |
| Withheld answers (answerable) | 28 | 27 |
| Exact match | 0.1500 | 0.1500 |
| Token F1 | 0.3091 | 0.3103 |
| Unsupported-claim rate | 0.2199 | 0.2168 |
| Citation accuracy | 0.7801 | 0.7832 |
| Unanswerable spurious | 2/42 | 2/42 |
| Lexical claim F1 (v2) | 0.8800 | 0.8889 |
| Lexical false rejects | 11 | 10 |

Row changes: `tc_8340538b` and `tc_06f5c7e8` are recovered with the correct cell
values (their answers append the table header, so they are not exact-match);
`tc_f3617604`, a wrong multi-column dump for a unit question, is now withheld.
No other answer changed. Both M5 runs produce identical answers (latency only).

## Verified metric note

The Mission 4 "unsupported-claim/citation regression" is an artifact of counting
rejected claims from withheld answers: returned answers carry 5 unsupported
claims in both runs (87 → 113 returned claims). Verified per answer in
`EXPERIMENT.md` §3; the metric definition was not changed.

## Not changed

Section-body alignment (`sec_5e1deffc`, `sec_e95f766d`), over-wide list/compound
claims, the 9 supported-but-off-target claims, and the 13 residual gate refusals
remain documented no-gos. They need question-attribute reasoning, evidence
construction, or benchmark review, not another verifier threshold.
