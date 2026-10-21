# Mission 5 — engineering record (2026-10-18)

## Files changed

| File | Change |
|---|---|
| `backend/generation/verification.py` | New `_raw_terms`, `_parse_pipe_table`, `_table_entity_alignment`; `numeric_entity_alignment` consults the table rule before the prose anchor |
| `backend/tests/unit/generation/test_generation_entity_verification.py` | New `TestTableEntityAlignment` (6 tests) |
| `backend/evaluation/experiments/build_answer_error_ledger.py` | New question-level ledger builder |
| `backend/evaluation/reports/answer_quality_mission5_2026-10-18_diagnosis/` | `DIAGNOSIS.md`, `ledger.jsonl`, `summary.json`, `EXPERIMENT.md`, this file |
| `backend/evaluation/README.md` | Ledger and table-alignment entry |
| `backend/architecture/DOCUMIND_TABLE_ENTITY_ALIGNMENT_2026-10-18.md` | New architecture evidence record |
| `DOCUMIND_PROJECT_CONTEXT.md` §0.8.10, `CONTEXT.md` | Dated update, history preserved |

No production default, model, prompt, retrieval, threshold, schema, dataset or
frontend change. Nothing staged or committed.

## Exact behaviour changed

Before: a numeric claim against a pipe table was checked against the sentence
containing the question's rarest term. For `Tier | Rate Limit | …` that term is
`limit`, so the anchor was the **header**; the value row's subject did not
contain `tier/rate` and the claim was returned as a wrong-entity `mismatch`.

After: for a parseable table (header + at least one equal-width data row, at
least three cells), the header names the asked column (cell 0 is the row
label/table title and is never used to infer a column), the data row is located
by its label, and the claim is accepted only when **all** of its numbers in that
row sit in the asked column. Otherwise the function returns `mismatch`. When the
evidence is not a table, or no header cell matches the question, the previous
prose rule runs unchanged.

Why generalizable: it uses the document's table structure, not benchmark IDs,
gold answers or document-specific constants. Any extracted pipe table benefits.

## Tests added (6)

`tests/unit/generation/test_generation_entity_verification.py::TestTableEntityAlignment`

1. value in the asked column is matched (`Precision` rate limit, Standard monthly
   quota, YoY growth);
2. value in a different column is a mismatch (mean asked, minimum claimed);
3. value from a different row is a mismatch;
4. compound value spanning two columns is a mismatch;
5. a table title does not bind the label column (`Payment Schedule` case);
6. non-table evidence keeps the prose rule (lidar calibration).

## Tests executed

| Command | Result |
|---|---|
| `pytest -q tests/unit/generation/test_generation_entity_verification.py` | **25 passed**, exit 0 |
| `python -m compileall -q generation evaluation tests` | exit 0 |
| `pytest -q tests/unit` | **1584 passed, 23 skipped, 0 failed**, exit 0 |
| `run_generation_benchmark ..._m5_post_v1` | exit 0, metrics below |
| `run_generation_benchmark ..._m5_post_v1_r2` | exit 0, identical metrics and answers |
| `run_answer_claim_evaluation --dataset v2 ..._m5_v2` | exit 0 |

Not run: integration, E2E, browser, live server/database, new 15-mark benchmark,
relation-aware verifier benchmark. Reason: outside the changed path; the claim
runner and generation benchmark already exercise the verifier end to end on the
frozen population.

## Measured outcome

Answered 99 → **100/140**; withheld 28 → **27**; rejected claims 29 → **29**;
EM 0.1500 → 0.1500; F1 0.3091 → **0.3103**; unsupported rate 0.2199 → 0.2168;
citation 0.7801 → 0.7832; unanswerable spurious **2/42 unchanged**; claim-level
lexical F1 0.8800 → **0.8889**, false rejects 11 → 10, false accepts 4 → 4.

Row changes: `tc_8340538b` and `tc_06f5c7e8` recovered (correct values, table
header appended by the generator so not exact); `tc_f3617604` removed (wrong
multi-column values for a unit question). No answer text changed.

## Risks and unresolved issues

* The table parser accepts only a single header plus equal-width rows; merged
  cells, multi-row headers and pipe characters inside prose fall back safely.
* A question that names a table title rather than a column falls back to the
  prose rule; that is deliberate (it preserves the `tc_a7432939` behaviour and
  avoids binding the label column).
* The two recovered answers are noisy (header text). Improving the generator's
  table rendering is a separate mission; the verifier must not rewrite answers.
* Section-body alignment, over-wide list claims and the 9 off-target claims are
  documented no-gos for this mission.
