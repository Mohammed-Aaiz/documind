# Deterministic table grounding — Mission 6 record (2026-10-21)

Status: **IMPLEMENTED — MEASURED**. One new module plus four narrow changes, all inside
`backend/generation/`. Production verifier default remains `lexical`; no model, prompt,
retrieval, threshold, schema, dataset, annotation or frontend change. No commit was made.

Evidence:

* diagnosis, 182-row ledger, experiment and engineering records:
  `backend/evaluation/reports/answer_quality_mission6_2026-10-21/`;
* before/after generation: `generation_benchmark_2026-10-18_m5_post_v1_r2` →
  `generation_benchmark_2026-10-21_m6_post_v1` (repeat `..._r2`, byte-identical answers;
  formats `..._m6_fmt5`, `..._m6_fmt15`).

## Defect

All 40 `TABLE_CELL` / `TABLE_ROW` benchmark questions are answered by a two-line pipe
table in which the question names one row label and (for a cell) one column header.
The generative engine answered **0 of 40** correctly: it returned the header row
(`tr_11a2c534`), a value from the wrong column (`tc_8faf2be8`, "employees for 2010" →
`Revenue exceeds $150M`; `tc_87f00ad1` → `Missing %`), the row without its label
(`tr_5cc553db`), or the correct cell followed by the table header (`tc_8340538b`).

Two smaller defects were found in the same pass: a one-word answer that is a stopword
could never be verified (`tc_03298034`, gold `Other`, `support_ratio == 0.0`), and
`plan_support_points` appended a table header render to complete answers as a
"supporting point", producing the 6 `PARTIALLY_SUPPORTED` rows.

## Change

1. **`generation/tables.py` (new).** `resolve_table_answer(question, blocks)` returns a
   cell or whole row copied verbatim from the evidence, or `None`:
   * a table is a header line plus ≥1 equal-width data row, ≥3 cells, parsed line by
     line (the sentence splitter joins a newline followed by a digit, which is what a
     data row looks like, so it cannot be used here);
   * the row is the unique data row whose first-cell terms all occur in the question;
   * the column is the unique header cell with the highest term overlap; a tie abstains;
   * with no column and a "values"/"information" cue, the whole row is returned
     pipe-joined;
   * the question must contain a lookup cue (`what`, `which`, `how much/many`, `name`,
     `list`, `give`), so "Where is the Premium tier described?" abstains;
   * cell 0 is a real attribute column in these tables (`Variable`, `Division`, `Year`,
     `Method`, `Tier`) and is not excluded.
2. **`generation/service.py`.** `_table_answer` runs after the answerability gate and
   before generation. It is accepted only if the **unchanged** verifier attributes it to
   the evidence; the answer is reported with `model: "deterministic-table"` and is not
   mark-elaborated (a cell is the complete answer at 5, 10 and 15 marks).
3. **`generation/verification.py`.** `support_ratio` falls back to raw tokens when a
   claim has no content tokens (stopword-only answers); `FY<year>` question terms are
   normalised to the year for the gate.
4. **`generation/planning.py`.** `is_propositional` excludes table renders from
   mark-aware elaboration.
5. **`generation/engine.py`.** `_clean_output` removes a copied `[n] (label)` prompt
   marker from the answer.

## Measured effect (same 182 rows, same hash, unchanged annotations)

| Metric | M5 | M6 |
|---|---:|---:|
| Answerable answered | 100/140 | **109/140** |
| Exact match | 0.1500 | **0.4500** |
| Token F1 | 0.3103 | **0.5621** |
| Incorrect answers | 73 | 46 |
| Gate refusals (answerable) | 13 | 11 |
| Withheld (answerable) | 27 | 20 |
| Unanswerable spurious | 2/42 | 2/42 |
| Unsupported-claim rate | 0.2168 | **0.1364** |
| Citation accuracy | 0.7832 | **0.8636** |
| p50 latency | 317 ms | 236 ms |

Row changes: **42 newly correct, 0 newly incorrect, 0 correct→withheld, 0 newly spurious,
0 changed-but-still-wrong**; 140 rows unchanged. 40 of the 42 are table lookups (24
cells, 16 rows); 2 are fiscal-year gate refusals (`num_1ae85d6b`, `num_4c6d491a`).

Tests: 27 new in `tests/unit/generation/test_generation_table_answers.py`. Focused 197
passed; full unit suite **1611 passed / 23 skipped / 0 failed**; `compileall` exit 0.

## Rejected (measured)

* Loosening the gate for the 7 boundary-located refusals: **0 of 7** answers are correct
  when permitted.
* A generic "answer type present in evidence" gate rule: it would also permit the
  unanswerable `customer churn rate`, `false positive rate`, `customer satisfaction
  rating` and `average customer lifetime value` rows.
* Restating table answers in gold-shaped prose (prepending the row label, appending the
  unit word): metric gaming, no correctness gain.
* Regenerating `answer_claims_v2`: would require new annotation.

## Not changed

The 11 remaining gate refusals, the 20 withheld list-ordinal answers, the 39
wrong-attribute answers, the 7 section-title annotation artifacts and the 2 spurious
unanswerable answers. Pre-existing and out of scope: revision `008` cannot run on SQLite
(`JSONB`), which fails 4 integration tests and the real-e2e validation test
(DATABASE_AGENT).
