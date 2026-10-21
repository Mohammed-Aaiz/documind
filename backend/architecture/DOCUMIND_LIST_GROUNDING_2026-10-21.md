# Deterministic ordered-list grounding — Mission 7 record (2026-10-21)

Status: **IMPLEMENTED — MEASURED**. One new module plus three narrow changes, all
inside `backend/generation/`, and two additive evaluation changes. Production
verifier default remains `lexical`; no model, prompt, retrieval, threshold,
schema, dataset, annotation or frontend change. No commit was made.

Evidence: `backend/evaluation/reports/answer_quality_mission7_2026-10-21/`
(`DIAGNOSIS.md`, `ERROR_LEDGER.jsonl`, `EXPERIMENT.md`, `ENGINEERING.md`,
`FINAL_REPORT.md`, `summary.json`).

## Defect

All 20 `LIST_ITEM` benchmark questions supply a heading line followed by one item
per line, and the reference answer is that item verbatim. The generative path
answered **2 of 20** correctly.

* **Generation.** The model returned the wrong item (`li_938c278e`, third citation
  answered with the first), a truncated item (`li_a4253b0c`, `Elena Vasquez` for
  `COO: Elena Vasquez (since June 2021)`), or two concatenated items
  (`li_1cd424f2`).
* **Verification.** A further 13 rows had a correct item but were withheld.
  `numeric_entity_alignment` anchors on the sentence containing the question's
  rarest term; in a heading+items block that sentence is the heading, so the item
  was judged a different entity. The sentence splitter also fragments exactly the
  lines a list resolver returns (`R.T. (2025).` → two sentences), so a
  sentence-based membership test fails even on byte-identical items.

## Change

1. **`generation/lists.py` (new).** `resolve_list_answer(question, blocks)`:
   * a list is a run of consecutive non-empty lines: a heading plus ≥2 items
     (heading ≤ 8 words, no terminal punctuation, no `|`); a blank line ends it;
   * the question must name the heading (stem-compared subset test);
   * **positional** form ("first", "fourth", "listed eighth", "last") returns the
     item at that 1-based position in the evidence's own order, and abstains when
     the list is too short;
   * **content** form ("handles cfo: robert tanaka") returns the single item with
     the highest term overlap, requiring ≥2 shared terms and a unique winner;
   * never uses retrieval rank or block order as a substitute for a position.
2. **`generation/service.py`.** `_list_answer` runs after the answerability gate
   and after the table reader, and is accepted only if the **unchanged** verifier
   attributes it. Reported as `model: "deterministic-list"`, and not
   mark-elaborated: an item is the complete answer at 5, 10 and 15 marks.
3. **`generation/verification.py`.** `_list_entity_alignment` adds membership
   semantics to the entity check: a claim that occurs inside an item of a list
   whose heading names the question's focus belongs to that list. A value
   elsewhere in the same block is still rejected.
4. **`generation/tables.py`.** `_subject_terms` → public `subject_terms`, shared
   by the table and list readers so the two tokenizers cannot drift.
5. **Evaluation (additive).** `RowResult.generative_model` records the producing
   engine, because the answer text alone cannot distinguish a table answer from a
   list answer; the ledger adds `failure_family`, `uncertainty` and
   `regression_status`.

## Measured effect (same 182 rows, same hash, unchanged annotations)

| Metric | M6 | M7 |
|---|---:|---:|
| Answerable answered | 109/140 | **118/140** |
| Exact match | 0.4500 | **0.5786** |
| Token F1 | 0.5621 | **0.6637** |
| Incorrect answers | 46 | 35 |
| Withheld (answerable) | 20 | 13 |
| Gate refusals (answerable) | 11 | 11 |
| Unanswerable spurious | 2/42 | 2/42 |
| Unsupported-claim rate | 0.1364 | **0.0821** |
| Citation accuracy | 0.8636 | **0.9179** |
| p95 latency | 1103 ms | 617 ms |

Row changes: **18 newly correct** (11 wrong→correct, 7 withheld→correct), **0
newly incorrect, 0 correct→withheld, 0 newly withheld, 0 newly spurious, 0
changed-but-wrong**; 164 rows unchanged. Three runs (`m7_post_v1`, `_r2`,
`_post_v2`) produce byte-identical answers.

Tests: 32 new in `tests/unit/generation/test_generation_list_answers.py`;
`tests/unit/generation` 229 passed; full unit suite **1643 passed / 23 skipped / 0
failed**; `compileall` exit 0. The frozen claim evaluation re-runs byte-identical
to Mission 5 (lexical F1 0.8889, false accepts 4, false rejects 10), confirming
the verifier change does not alter the annotated population. (Counts are after the
independent review below; the reported run is
`generation_benchmark_2026-10-21_m7_reviewed`, whose answers are byte-identical to
the three pre-review runs.)

## Rejected (measured)

* A deterministic reader for the 8 boundary-located questions: in 6 of 9 rows the
  second named section is absent from the evidence, and in the rest the reference
  is the last value before the heading twice and the first value after it once —
  no consistent rule.
* Withholding digit-free answers to quantity questions: converts 4 wrong answers
  into 4 abstentions, gains 0 EM and loses 0.0036 F1 — it hides a generation
  failure instead of fixing it.
* Stripping `$`/units to match reference strings (11 rows), returning section
  headings for the 7 section-title rows, and regenerating `answer_claims_v2`:
  metric gaming or fabricated annotation.

## Independent review and hardening

The change was reviewed as a whole before it was reported. Seven defects were
found; all seven were fixed, each pinned by a test. None is visible on the frozen
benchmark — its blocks are never truncated, its list questions carry one ordinal,
and its headings start their run — so the measured aggregates above did not move.
The review closed production-only failure modes:

* **truncated excerpts.** `build_evidence_blocks` cuts `content` at 1200 chars with
  no marker, so a positional answer could resolve against a list whose tail was
  missing ("the eighth item" → the fifth surviving one) and the verifier would
  confirm it, because it *is* an item of that list. `EvidenceBlock.truncated` now
  records the cut, and positional resolution refuses a truncated block; content
  matching is still allowed, since a missing tail cannot change which item contains
  a phrase.
* **heading recognition.** The first line of a run was assumed to be the heading,
  so a label followed by an unpunctuated intro line shifted every position by one.
  A heading may now contain no `:` (`Revenue: $847.3 million` is an item) and may be
  no longer than the shortest item.
* **ambiguous ordinals.** A two-ordinal question ("the first and third item") fell
  through to the *content* form; it now abstains, as documented.
* **verifier symmetry.** The list rule now returns `None` when the question has no
  distinctive term (the prose rule stays in charge), and heading comparison uses
  the same raw-term tokenizer as the resolver, so a heading cannot be resolvable but
  unverifiable.
* **a vacuous test** was rewritten to name the heading it asserts about, and the
  unused `where` in the list warning now names the heading and item position.

Post-review run: `generation_benchmark_2026-10-21_m7_reviewed` — 81/140 exact, EM
0.5786, F1 0.6637, 2/42 spurious, unsupported-claim rate 0.0821; 36 of 182 records
differ from `m7_post_v2` **only** in `generative_warnings`. The ledger is built from
that run.

## Not changed

11 gate refusals, 13 withheld answers, 2/42 spurious, 7 section-title annotation
artifacts, 11 reference-format variants and 8 ambiguous references. Pre-existing
and out of scope: Alembic revision `008` emits `JSONB` and cannot run on SQLite,
failing 4 integration tests (DATABASE_AGENT).
