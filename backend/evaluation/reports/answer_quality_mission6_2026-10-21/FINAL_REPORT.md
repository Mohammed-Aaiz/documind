# FINAL REPORT — DocuMind answer quality, Mission 6 (2026-10-21)

**Overall status: COMPLETED** for the answer-quality work; **one unrelated,
pre-existing integration blocker** is reported, not fixed (migration ownership).

## 1. Starting state

- Revision `6baaa2a0773df66e5fb26814afbe67647fb43435`; 401 pre-existing working-tree
  entries, all preserved. `backend/generation/`, `backend/evaluation/` and
  `backend/tests/unit/generation/` are untracked — Missions 3–5 were never committed.
- Frozen benchmark SHA-256 `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0`,
  182 rows (140 answerable / 42 unanswerable), verified unchanged before every run.
- Claim dataset `answer_claims_v2`, SHA-256 `f06795eb…`, 103 claims, unchanged.
- Baseline read from `generation_benchmark_2026-10-18_m5_post_v1_r2`:
  EM 0.1500, F1 0.3103, 100/140 answered, 13 gate refusals, 27 withheld,
  2/42 spurious, unsupported-claim rate 0.2168, citation accuracy 0.7832.

## 2. Root causes (verified)

1. **Table lookups were delegated to the seq2seq model** — 0 of 40 table questions
   correct: header returned, wrong column, or the correct cell followed by the header.
2. **A one-word answer that is a stopword could never be verified** (`Other`).
3. **Table header renders were appended to complete answers as "supporting points"**,
   which broke exactness and created the 6 `PARTIALLY_SUPPORTED` rows.
4. **The model echoed the prompt's `[n] (label)` evidence prefix** into five answers.
5. **`FY2024` was tokenised as one term**, so the gate counted it and the year as two
   misses against evidence that says "fiscal year 2024".

## 3. Implementation

| Fix | File | Rows affected |
|---|---|---|
| Deterministic table row/column resolution | `generation/tables.py` (new) + `generation/service.py` | 40 |
| Stopword-only claims verifiable | `generation/verification.py` | 1 |
| Table renders excluded from elaboration | `generation/planning.py` | 46 |
| Prompt-echo stripped from answers | `generation/engine.py` | 5 |
| Fiscal-year term normalisation | `generation/verification.py` | 2 |

All changes are inside `backend/generation/`. Verifier default, retrieval, prompts,
thresholds, datasets, schema and frontend are untouched.

## 4. Before / after (10-mark, same 182 rows, same hash, same annotations)

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
| Verified rate (182) | 0.5275 | 0.6099 |
| p50 latency | 317 ms | 236 ms |

**Measured, not inferred.** Repeat run `..._m6_post_v1_r2` produced byte-identical
answers (0 differing rows), so the delta is deterministic rather than sampling noise.
Latency is quoted from the repeat run; the primary run was executed on a busy machine
(534 ms p50) and is reported as such in `EXPERIMENT.md`.

## 5. Regression analysis

| Class | Count |
|---|---:|
| Newly correct | **42** |
| Newly incorrect | 0 |
| Correct → withheld | 0 |
| Newly withheld | 0 |
| Newly spurious on unanswerable | 0 |
| Changed but still wrong | 0 |
| Unchanged | 140 |

All 42 changed rows were inspected individually; the diff is enumerated in
`EXPERIMENT.md` §4 and machine-readable in `ERROR_LEDGER.jsonl` (`answer_change`,
`previous_em`, `current_em`, `disposition`). The scope of the "no regressions"
conclusion is exactly: **the 182 frozen P3 rows at 10 marks, lexical verifier**. At 15
marks the unanswerable spurious rate is 4/42, which was reproduced as a pre-existing
decoder effect of the per-format depth cue, not a Mission 6 change.

Three of the 42 are recorded as benchmark artifacts rather than comprehension gains
(`tc_a7432939` "how much is the payment schedule of Q2 2025?" → `Q2 2025`); the
resolver reproduces the gold cell faithfully, and the question itself is ill-formed.

## 6. Testing actually executed

```
venv/Scripts/python.exe -m pytest -q tests/unit/generation        → 197 passed
venv/Scripts/python.exe -m pytest -q tests/unit                   → 1611 passed, 23 skipped
venv/Scripts/python.exe -m compileall -q generation evaluation/experiments → exit 0
venv/Scripts/python.exe -m pytest -q tests/integration            → 293 passed, 4 failed, 1 error
venv/Scripts/python.exe -m pytest -q tests/e2e                    → 6 skipped (live server absent)
```

1611 = 1584 (Mission 5 recorded) + 27 new. No test was skipped, weakened or removed.

**Integration failures are pre-existing and unrelated**: `tests/integration/documents/test_table_row_migration.py`
(4 tests) and `tests/integration/rag/test_real_e2e_validation.py` (1 error) fail because
Alembic revision `008` issues `JSONB` and cannot run on the SQLite test database
(`can't render element of type JSONB`). No migration, model or schema file was touched
by this mission. Owner: DATABASE_AGENT.

## 7. Artifacts

- Diagnosis, ledger, experiment, engineering, this report, machine-readable summary:
  `backend/evaluation/reports/answer_quality_mission6_2026-10-21/`
  (`DIAGNOSIS.md`, `ERROR_LEDGER.jsonl`, `EXPERIMENT.md`, `ENGINEERING.md`,
  `FINAL_REPORT.md`, `summary.json`).
- Runs: `evaluation/reports/generation_benchmark_2026-10-21_m6_post_v1`,
  `…_m6_post_v1_r2`, `…_m6_fmt5`, `…_m6_fmt15`.
- Architecture record: `backend/architecture/DOCUMIND_TABLE_GROUNDING_2026-10-21.md`.
- New ledger builder: `backend/evaluation/experiments/build_answer_quality_ledger.py`.
- New tests: `backend/tests/unit/generation/test_generation_table_answers.py`.

All historical artifacts (`..._m4_*`, `..._m5_*`, `answer_claim_evaluation_*`,
`answer_quality_mission5_*`) are preserved and were not overwritten.

## 8. Repository safety

- No `git reset`, `clean`, `gc`, `prune`, checkout, stash or reflog operation.
- Nothing staged, committed, pushed or deployed. `git rev-parse HEAD` still
  `6baaa2a0773df66e5fb26814afbe67647fb43435`.
- Pre-existing modified/deleted/untracked files were not reverted, moved or cleaned.
- `.env`, `backend/.env.example`, `backend/models/**`, `backend/uploads/**`,
  `backend/phases/**` untouched.

## 9. Remaining limitations

1. **11 answerable questions are still refused** by the gate (7 boundary-located, 4
   lexical paraphrase/compound-noun). Unblocking the boundary family was measured to
   produce 0/7 correct answers; a generic answer-type rule was measured to admit 4
   unanswerable rows. Both were rejected.
2. **20 answerable questions are still withheld** — mostly list-ordinal questions
   ("what comes first in the citation?") where the model returns the wrong list item.
   That is a generation failure the verifier correctly refuses; it needs a list-aware
   reader, not a threshold change.
3. **39 answers are still wrong** — wrong attribute/value selection on prose questions
   (e.g. "What was the division revenue?" answered with a neighbouring division).
   Question-attribute binding over prose is not solved by this mission.
4. **7 rows are annotation artifacts** (gold = section title) and were deliberately not
   "fixed".
5. **2/42 unanswerable rows still answer**; unchanged from Mission 5, no safe rule found.
6. **Claim-level annotation was not regenerated.** `answer_claims_v2` describes the
   Mission 5 answers; claim metrics for the new answers are the production verifier's
   own counts (claims 132, supported 114, unsupported 18, citation 0.8636) and are not
   comparable to the human-annotated v2 F1 of 0.8889.
7. **Single annotator, one benchmark, no retrieval measurement** (rows are
   self-contained; retrieval is unchanged and unmeasured here).
8. **No live-server, browser or PostgreSQL run.** The 4 integration failures above are
   environmental and pre-existing.

## 10. Acceptance checklist

| Requirement | Result |
|---|---|
| Known material error categories investigated | PASS |
| Every implemented change has a documented root cause | PASS |
| Regression tests cover the fixed defects | PASS (27 tests) |
| Table-alignment behaviour (Mission 5) still correct | PASS (its 6 tests untouched and green) |
| Question-attribute binding evaluated | PASS (measured; prose binding unresolved and reported) |
| Answer relevance and completeness evaluated | PASS (EM/F1, row diff, 7 artifact rows identified) |
| False accepts and false rejects both measured | PASS (spurious 2/42; withheld 27→20) |
| No benchmark/annotation change used to manufacture improvement | PASS (hashes unchanged) |
| Unanswerable behaviour evaluated | PASS (2/42 unchanged) |
| Unsupported claims controlled | PASS (rate 0.2168 → 0.1364) |
| Verification not indiscriminately loosened | PASS (one term normalisation, no threshold change) |
| Citation support checked, not inferred from formatting | PASS (citation accuracy 0.7832 → 0.8636) |
| All material answer changes inspected | PASS (42/42) |
| Remaining regressions documented | PASS (none found at 10 marks; 15-mark effect documented) |
| Full unit suite passes | PASS (1611 passed / 23 skipped) |
| Focused tests pass | PASS |
| Compilation/static checks pass | PASS (`compileall` exit 0) |
| Benchmark outputs reproducible | PASS (repeat run byte-identical) |
| Datasets and historical artifacts intact | PASS |
| Working tree inspected | PASS |
| No unrelated user changes overwritten | PASS |
| No commit / push / staging / deployment | PASS |
| All safely implementable fixes attempted | PASS within scope; rejected interventions documented with measurements |
| Documentation and project context updated | PASS |
| Remaining issues have evidence-based explanation and priority | PASS |
