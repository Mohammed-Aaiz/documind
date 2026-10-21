# FINAL REPORT — DocuMind answer quality, Mission 7 (2026-10-21)

**Overall status: COMPLETED** for the answer-quality work; **one unrelated,
pre-existing integration blocker** is reported, not fixed (migration ownership).

## 1. Starting state

- Revision `6baaa2a0773df66e5fb26814afbe67647fb43435`; 401 pre-existing working-tree
  entries, all preserved. `backend/generation/`, `backend/evaluation/` and
  `backend/tests/unit/generation/` are untracked — Missions 3–6 were never committed.
- Frozen benchmark SHA-256 `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0`,
  182 rows (140 answerable / 42 unanswerable), verified unchanged before every run.
- Claim dataset `answer_claims_v2`, SHA-256 `f06795eb…`, 103 claims / 86 examples,
  unchanged.
- Baseline read from `generation_benchmark_2026-10-21_m6_post_v1`:
  EM 0.4500, F1 0.5621, 109/140 answered, 11 gate refusals (answerable),
  20 withheld (answerable), 2/42 spurious, unsupported-claim rate 0.1364,
  citation accuracy 0.8636.

## 2. Root causes (verified)

1. **Ordered-list lookups were delegated to the seq2seq model.** 20 `LIST_ITEM`
   questions; every one supplies a heading plus one item per line and the reference
   answer is that item **verbatim**. The model answered **2 of 20** correctly —
   wrong item, a truncated item (`Elena Vasquez` for `COO: Elena Vasquez (since
   June 2021)`), or two concatenated items.
2. **The verifier's entity check rejected correct list items.** It anchors on the
   sentence containing the question's rarest term; in heading+item evidence that
   sentence is the *heading*, so an item was judged a different entity. 10 rows
   were withheld for this reason.
3. **A sentence-based comparison could never accept those items anyway.** The
   evidence splitter fragments exactly the lines a list resolver returns
   (`R.T. (2025).` → two sentences; `OAuth 2.0 …` merged with the next item).

## 3. Implementation

| Fix | File | Rows affected |
|---|---|---|
| Deterministic ordered-list resolution (positional and content) | `generation/lists.py` (new) + `generation/service.py` | 20 |
| List-membership semantics in the numeric entity check | `generation/verification.py` | 13 |
| One shared heading/row/column tokenizer | `generation/tables.py` (`_subject_terms` → `subject_terms`) | — |
| `EvidenceBlock.truncated`; positional resolution refuses a cut excerpt | `generation/types.py`, `generation/service.py`, `generation/lists.py` | review hardening |
| Producer recorded per benchmark row | `evaluation/experiments/run_generation_benchmark.py` | — |
| Mission 7 ledger schema (38 fields) | `evaluation/experiments/build_answer_quality_ledger.py` | — |

All production changes are inside `backend/generation/`. Verifier default, retrieval,
prompts, thresholds, model, schema/migrations, datasets and frontend are untouched.

The resolved item passes through the **unchanged** verifier: an answer the verifier
cannot attribute falls back to generation, so the new path cannot invent content.

## 4. Before / after (10-mark, same 182 rows, same hash, same annotations)

| Metric | M6 | M7 |
|---|---:|---:|
| Answerable answered | 109/140 | **118/140** |
| Exact match | 0.4500 | **0.5786** |
| Token F1 | 0.5621 | **0.6637** |
| Lead-answer EM | 0.4500 | 0.5571 |
| Incorrect answers | 46 | 35 |
| Gate refusals (answerable) | 11 | 11 |
| Withheld (answerable) | 20 | 13 |
| Unanswerable spurious | 2/42 | 2/42 |
| Claims / supported / unsupported | 132 / 114 / 18 | 134 / 123 / 11 |
| Unsupported-claim rate | 0.1364 | **0.0821** |
| Citation accuracy | 0.8636 | **0.9179** |
| Verified rate (182) | 0.6099 | 0.6484 |
| p50 latency | 236 ms | 0 ms |

Producers on the 140 answerable rows: deterministic table **40**, deterministic list
**20**, model **56**, withheld **13**, gate refusal **11**. `p50` is 0 ms because 60
of the 182 rows are answered without loading or running the model.

**Measured, not inferred.** Three pre-review runs and the post-review run produce
**byte-identical answers** (0 differing rows of 182); only latency and warning text
differ. The decoding path is deterministic (`num_beams=4`, no sampling).

## 5. Regression analysis

| Class | Count |
|---|---:|
| Previously wrong → now correct | **11** |
| Previously withheld → now correct | **7** |
| Previously correct → now wrong | 0 |
| Previously correct → now withheld | 0 |
| Previously correct → abstained | 0 |
| Newly spurious on unanswerable | 0 |
| Changed but still wrong | 0 |
| Unchanged | 164 |

All 18 changed rows are the `LIST_ITEM` family and were inspected individually; the
diff is machine-readable in `ERROR_LEDGER.jsonl` (`answer_change`, `previous_em`,
`current_em`, `disposition`). The scope of the "no regressions" conclusion is exactly:
**the 182 frozen P3 rows at 10 marks, lexical verifier**. The 15-mark spurious rate is
4/42, a pre-existing decoder effect of the depth cue that Mission 6 reproduced by
direct generation; it is not caused by this mission.

## 6. Independent review and the defects it found

The change was reviewed as a whole before it was reported (review only; no edits by
the reviewer). Seven defects were found, all fixed, each pinned by a test. None is
visible on the frozen benchmark — its blocks are never truncated, its list questions
carry one ordinal, and its headings start their run — so the aggregate is unchanged by
the fixes; they close production failure modes.

| # | Severity | Defect | Fix |
|---|---|---|---|
| 1 | HIGH | a positional answer could be read from a truncated block (`content[:1200]` drops the tail silently), so "the eighth item" resolved to the fifth surviving one and the verifier confirmed it | `EvidenceBlock.truncated`; positions refused on a cut block; content matching still allowed |
| 2 | MEDIUM | the first line of a run was assumed to be the heading, so an intro line shifted positions by one | heading may not contain `:` and may not be longer than the shortest item |
| 3 | MEDIUM | a two-ordinal question silently degraded to a content match, contradicting the documented abstention | explicit abstention before resolution |
| 4 | MEDIUM | one test was vacuous (its question did not name the heading, so the tie logic never ran) | test now names the heading and asserts the parse |
| 5 | LOW | the verifier accepted any nearby list when the question had no distinctive term | the list rule returns `None`; the prose rule stays in charge |
| 6 | LOW | verifier and resolver used different heading tokenizers | both use raw terms |
| 7 | LOW | the list warning computed `where` and never used it | warning names the heading and item position |

## 7. Testing actually executed

```
venv/Scripts/python.exe -m pytest -q tests/unit/generation        → 229 passed
venv/Scripts/python.exe -m pytest -q tests/unit                   → 1643 passed, 23 skipped
venv/Scripts/python.exe -m compileall -q generation evaluation/experiments → exit 0
venv/Scripts/python.exe -m pytest -q tests/integration            → 293 passed, 4 failed, 1 error
venv/Scripts/python.exe -m pytest -q tests/e2e                    → 6 skipped (live server absent)
```

1643 = 1611 (Mission 6 recorded) + 32 new. No test was skipped, weakened or removed.

**Integration failures are pre-existing and unrelated**:
`tests/integration/documents/test_table_row_migration.py` (4 tests) and
`tests/integration/rag/test_real_e2e_validation.py` (1 error) fail because Alembic
revision `008` issues `JSONB` and cannot run on the SQLite test database
(`can't render element of type JSONB`). No migration, model or schema file was touched
by this mission. Owner: DATABASE_AGENT.

The claim replay is the check that the verifier change is targeted:

```
python -m evaluation.experiments.run_answer_claim_evaluation --run-id …_m7_reviewed
    → lexical support F1 0.8889 (P 0.9333 / R 0.8485), relations 0.9767,
      false accepts 4 / 0, false rejects 10 / 3
```

**identical** to the Mission 5 record. The change fires only on heading+item
structures, which that annotated population does not contain.

## 8. Artifacts

- `DIAGNOSIS.md`, `ERROR_LEDGER.jsonl` (182 rows, 38 fields), `EXPERIMENT.md`,
  `ENGINEERING.md`, `CHECKPOINT.md`, `FINAL_REPORT.md`, `summary.json` — this directory.
- Runs: `generation_benchmark_2026-10-21_m7_post_v1`, `…_m7_post_v1_r2`,
  `…_m7_post_v2`, `…_m7_reviewed`, `…_m7_fmt5`, `…_m7_fmt15`,
  `…_m7_reviewed_fmt5`, `…_m7_reviewed_fmt15`.
- Claim replays: `answer_claim_evaluation_2026-10-21_m7_v2`,
  `answer_claim_evaluation_2026-10-21_m7_reviewed`.
- Architecture record: `backend/architecture/DOCUMIND_LIST_GROUNDING_2026-10-21.md`.
- New tests: `backend/tests/unit/generation/test_generation_list_answers.py`.

All historical artifacts (`..._m4_*`, `..._m5_*`, `..._m6_*`, `answer_claim_evaluation_*`,
`answer_quality_mission5_*`, `answer_quality_mission6_*`) are preserved and were not
overwritten. The Mission 7 ledger directory was regenerated in place from the
post-review run (`--force`, ledger and summary only; the prose documents are not
written by that script).

## 9. Repository safety

- No `git reset`, `clean`, `gc`, `prune`, checkout, stash or reflog operation.
- Nothing staged, committed, pushed or deployed. `git rev-parse HEAD` still
  `6baaa2a0773df66e5fb26814afbe67647fb43435`.
- Pre-existing modified/deleted/untracked files were not reverted, moved or cleaned.
- `.env`, `backend/models/**`, `backend/uploads/**`, `backend/phases/**` untouched.

## 10. Remaining limitations

1. **11 answerable questions are still refused** by the gate (7 boundary-located, 4
   lexical paraphrase/compound-noun). A deterministic boundary reader was tested and
   rejected: in 6 of 9 rows the second named section is absent from the evidence, and
   the remaining 3 disagree on whether the reference is the last value before the
   heading or the first after it.
2. **13 answerable questions are still withheld** — prose attribute/value selection
   the verifier correctly refuses.
3. **35 answers are still wrong** — wrong attribute/value on prose questions
   (`revenue` for "what value is given for metric"), which no measured rule fixes.
4. **7 rows are annotation artifacts** (gold = section title) and were deliberately not
   "fixed".
5. **2/42 unanswerable rows still answer**; unchanged since Mission 5, no safe rule found.
6. **Claim-level annotation was not regenerated.** `answer_claims_v2` describes the
   Mission 5 answers, so its F1 is not a measurement of these answers. The new answers'
   claim counts (134 / 123 / 11) come from the production verifier, not a human.
7. **Single annotator, one benchmark, no retrieval measurement** (rows are
   self-contained; retrieval is unchanged and unmeasured here).
8. **No live-server, browser or PostgreSQL run.** The integration failures above are
   environmental and pre-existing.
9. **The heading heuristic is a heuristic.** A run of unpunctuated prose lines that
   happens to be shorter than the first line could still be read as a list; the
   heading must be named by the question, which bounds but does not eliminate this.

## 11. Acceptance checklist

| Requirement | Result |
|---|---|
| Known material error categories investigated | PASS |
| Every implemented change has a documented root cause | PASS |
| Regression tests cover the fixed defects | PASS (32 tests) |
| Table-grounding behaviour (Mission 6) still correct | PASS (40 rows unchanged, deterministic-table) |
| List-ordinal family evaluated | PASS (20 rows, 18 newly exact, 0 regressions) |
| Answer relevance and completeness evaluated | PASS (EM/F1, row diff, 7 artifact rows) |
| False accepts and false rejects both measured | PASS (spurious 2/42; withheld 20 → 13) |
| No benchmark/annotation change used to manufacture improvement | PASS (hashes unchanged) |
| Unanswerable behaviour evaluated | PASS (2/42 unchanged) |
| Unsupported claims controlled | PASS (rate 0.1364 → 0.0821) |
| Verification not indiscriminately loosened | PASS (no threshold change; wrong value outside the named list still rejected) |
| Independent review of the change performed, findings fixed | PASS (7/7 fixed, each pinned) |
| Truncated evidence cannot produce a false position | PASS (`truncated` guard + test) |
| Citation support checked, not inferred from formatting | PASS (citation accuracy 0.8636 → 0.9179) |
| All material answer changes inspected | PASS (18/18) |
| Remaining regressions documented | PASS (none at 10 marks; 15-mark effect documented) |
| Full unit suite passes | PASS (1643 passed / 23 skipped) |
| Focused tests pass | PASS |
| Compilation/static checks pass | PASS (`compileall` exit 0) |
| Benchmark outputs reproducible | PASS (four runs byte-identical answers) |
| Datasets and historical artifacts intact | PASS |
| Working tree inspected | PASS |
| No unrelated user changes overwritten | PASS |
| No commit / push / staging / deployment | PASS |
| All safely implementable fixes attempted | PASS within scope; rejected interventions documented with measurements |
| Documentation and project context updated | PASS |
| Remaining issues have evidence-based explanation and priority | PASS |
