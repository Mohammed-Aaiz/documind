# DIAGNOSIS — DocuMind answer quality, Mission 6 (2026-10-21)

Status: **COMPLETE**. Everything below is either read from a recorded artifact or
computed by a named command; nothing is inferred from a design document.

- Repository revision: `6baaa2a0773df66e5fb26814afbe67647fb43435` (unchanged, no commit
  made). The whole `backend/generation/`, `backend/evaluation/` and
  `backend/tests/unit/generation/` trees are **untracked** in this working tree —
  Missions 3–5 were never committed.
- Frozen benchmark: `backend/phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl`,
  SHA-256 `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0`, 182 rows
  (140 answerable / 42 unanswerable). Verified before every run; a mismatch aborts.
- Claim dataset: `answer_claims_v2`, SHA-256
  `f06795eb5034133d8dc600a4685621dc0999f4a00b71afa0f490731e0aecad88`, 103 claims over 86
  examples. Unchanged by this mission.
- Production verifier default: `lexical` (`DOCUMIND_VERIFIER`). Unchanged.
- Previous generation runs read (not regenerated):
  `generation_benchmark_2026-10-18_m4_baseline`,
  `generation_benchmark_2026-10-18_m5_post_v1` / `_r2`.

## 1. Starting baseline (verified)

`generation_benchmark_2026-10-18_m5_post_v1_r2` — the Mission 5 artifact, reproduced
identical earlier; this mission read it rather than re-running it.

| Metric | Value |
|---|---:|
| Answerable answered | 100 / 140 |
| Exact match | 0.1500 (21 rows) |
| Token F1 | 0.3103 |
| Gate refusals (answerable) | 13 |
| Withheld after generation (answerable) | 27 |
| Unanswerable spurious answers | 2 / 42 |
| Claims / supported / unsupported | 143 / 112 / 31 |
| Unsupported-claim rate | 0.2168 |
| Citation accuracy | 0.7832 |
| p50 latency | 317 ms |

Failure buckets over the 140 answerable rows: `incorrect_answer` 73,
`empty_or_abstained` 40, `partially_supported` 6, `none` 21.

The single most important number in that table is **73 wrong answers**, not the
coverage. Improving coverage without fixing correctness would have been the wrong
objective.

## 2. Method

1. Replayed the gate, the verifier and the resolver over **all 182 rows** offline
   (no model call) to attribute each failure to a code path.
2. Reproduced generation for the 40 non-answering answerable rows so the discarded
   model text could be inspected rather than guessed.
3. Rejected interventions were measured before rejection — see §5.
4. Every policy change was evaluated over the full frozen population before being
   kept.

Ledger: `ERROR_LEDGER.jsonl` in this directory (one record per row, unknown fields
written as `"unknown"`).

## 3. Verified error taxonomy (Mission 6 population)

From `summary.json` → `error_categories` (182 rows, mutually exclusive as assigned):

| Category | Rows | Note |
|---|---:|---|
| none (exact, model-generated) | 23 | correct |
| none (table lookup) | 40 | correct after this mission |
| correct abstention (unanswerable) | 40 | |
| false abstention or withholding | 20 | non-empty generation could not be attributed |
| incorrect answer to an answerable question | 39 | |
| false answerability-gate refusal | 11 | |
| metric or annotation artifact | 7 | gold is a section title; the body *is* the answer |
| spurious answer to an unanswerable question | 2 | unchanged by this mission |

Overlapping sub-categories that are **not** mutually exclusive, so they are reported
separately and never added to the table above:

- of the 39 incorrect answers, most are single-fact selections where the asked
  attribute was not honoured (e.g. "What was the division revenue?" answered with a
  neighbouring division's figure);
- of the 20 withheld answers, the discarded text was frequently the *wrong row of a
  list* ("What comes first in the citation?" → `GeoClimate`) — a generation failure
  the verifier correctly refused;
- 7 rows are annotation artifacts: the question asks what a section contains and the
  gold answer is the section **title** (`Station Distribution`, `Forward Guidance`,
  `Fees and Payment`, `Present Day (2021-Present)`, `Dataset Overview`, …). Returning
  the section's body answers the question that was asked. These are *not* model
  failures and were not "fixed".

## 4. Root causes (verified, in priority order)

### RC-1 — the table lookup was delegated to a 250M-parameter seq2seq model (40 rows)

The dominant defect by far. All 40 `TABLE_CELL` / `TABLE_ROW` rows are two-line pipe
tables in which the question names one row label and, for a cell question, one column
header. The generator answered **0 of 40** correctly:

| Symptom | Example | Model output | Gold |
|---|---|---|---|
| returned the header | `tr_11a2c534` | `[1] (benchmark-context) Variable, Unit, Min, Max, Mean, Missing %` | `Temperature \| degrees Celsius \| -42.3 \| 48.7 \| 12.4 \| 0.3%` |
| wrong column | `tc_8faf2be8` "employees for 2010" | `Revenue exceeds $150M` | `650` |
| wrong column | `tc_87f00ad1` "mean for Solar Radiation" | `Missing %` | `198.4` |
| correct cell, then header appended | `tc_8340538b` | `1,000 req/min. Tier \| Rate Limit \| Burst Limit \| Monthly Quota [1]` | `1,000 req/min` |
| row minus its label | `tr_5cc553db` | `0.0, 127.3, 0.8, 1.2%` | `Precipitation \| mm \| 0.0 \| 127.3 \| 0.8 \| 1.2%` |

The last two rows also show RC-3: the answer was right but polluted by the answer
formatter.

### RC-2 — the verifier could not verify a one-word answer that is a stopword

`support_ratio` compares *content* tokens, and `content_tokens` removes stopwords.
`Other` is a stopword, so `support_ratio("Other", evidence) == 0.0` and
`attribute_claim` returned "claim too short to verify". `tc_03298034` ("what division
value does Other show?", gold `Other`) was therefore impossible to answer. Same class
as the 2026-10-17 "a single number *is* a claim" fix, one level down.

### RC-3 — a table header render was appended to complete answers as a "supporting point"

`plan_support_points` treats every evidence sentence as a candidate depth point. A
table header line (`Tier | Rate Limit | Burst Limit | Monthly Quota`) is not a
proposition — the project's own claim dataset labels 22 such renders
`NOT_A_CLAIM`/`table_render` — yet it was appended to correct 10-mark answers,
turning `20 req/min` into `20 req/min. Tier | Rate Limit | … [1]` (F1 0.50 where the
cell alone is exact). It also created the 6 `PARTIALLY_SUPPORTED` rows in the M5 run.

### RC-4 — the model echoed the prompt's evidence-line prefix into the answer

Flan-T5-base copies the numbered context line, so five answers began with
`[1] (benchmark-context) …` — a marker that is not part of the answer and is not
meaningful to a user.

### RC-5 — fiscal-year notation counted as two missing terms

`_TOKEN_RE` does not split a letter/digit boundary, so `FY2024` is one token. Against
evidence that says "fiscal year 2024" the gate counted `fy2024` as absent *and* never
credited the year, then needed a second miss (`current`) to refuse. Measured on
`num_1ae85d6b` and `num_4c6d491a`: both answerable, both answered correctly when
permitted (`$1.24 billion`, `$425 million`).

### RC-6 — boundary-located questions and paraphrase gaps (accepted limitation)

11 answerable rows are still refused by the gate. They are two families, and both
were measured before being left alone — see §5.

## 5. Rejected interventions (measured, then rejected)

| Proposed change | Measurement | Decision |
|---|---|---|
| Allow the 7 "near the boundary between A and B" refusals by treating section names as locators | generation run with the gate bypassed: **0 of 7** answers correct (the model picks the wrong number at the boundary) | **REJECTED** — would add 7 answers and 0 correct ones |
| Allow any question whose *answer type* is present in the evidence (money/percent/count) | the 4 "rate/rating/value" questions in the unanswerable set (`customer churn rate`, `false positive rate`, `customer satisfaction rating`, `average customer lifetime value`) would all be permitted against evidence that contains a percentage but not the term | **REJECTED** — trades a false-refusal for false accepts on the unanswerable population |
| Force the remaining 6 numeric refusals through | 4 of 6 would be exact, but no rule covers them without also covering the rows above; the misses are compound-noun (`page size` vs "items per request") and synonym (`monthly subscription` vs "priced at $4,900 per month") | **REJECTED** as unsafe at this evidence level |
| Prepend the row label / append the unit word so table answers match the gold string | changes answer wording to match an annotation, no correctness gain | **REJECTED** — metric gaming |
| Handle the 7 section-title gold answers by returning the heading | the returned body text answers the question that was asked; the gold is the artifact | **REJECTED** — benchmark review, not code |
| Regenerate `answer_claims_v2` against the new answers | requires new annotation by a human annotator | **REJECTED** — would fabricate labels |

## 6. Priorities carried into implementation

1. RC-1 + RC-3 (table grounding) — 40 rows, highest confidence, answer text is
   evidence verbatim.
2. RC-2 (stopword claim) — 1 row, zero risk.
3. RC-3 (elaboration filter) + RC-4 (echo strip) — formatting/usability and
   unsupported-claim reduction.
4. RC-5 (fiscal-year normalisation) — 2 rows, zero risk on the unanswerable set.
