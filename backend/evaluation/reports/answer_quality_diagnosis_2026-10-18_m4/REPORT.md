# Answer relevance, claim coverage and generation quality — Mission 4 diagnosis

Run ID: `answer_quality_diagnosis_2026-10-18_m4`
Date: 2026-10-18
Repository HEAD at diagnosis: `6baaa2a` (no commit or stage was made)
Capture: `analysis.json` in this directory, produced by
`evaluation/experiments/diagnose_answer_quality.py` **before** the gate change
below, so its 49 `gate_cases` describe the pre-change policy and its buckets are
computed from the recorded `fmt10` run. The post-change classification is
`answer_quality_diagnosis_2026-10-18_m4_post/` (99 answered / 13 gate / 28
withheld), produced with `--generation-run
generation_benchmark_2026-10-18_m4_post_v2`; the pre-change JSON remains the
frozen baseline evidence for this mission.

Evaluation inputs (unchanged):

| Item | Value |
|---|---|
| Benchmark | `phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` |
| Benchmark SHA-256 | `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` |
| Benchmark rows | 182 (140 answerable, 42 unanswerable) |
| Claim datasets | `answer_claims_v1` (104 claims / 86 questions), `answer_claims_v2` (103 / 86) |
| Claim reports | `answer_claim_evaluation_2026-10-18_m4_baseline_v1`, `..._v2` (new, this mission) |
| Generation reports | `generation_benchmark_2026-10-18_m4_baseline`, `..._m4_post_v2`, `..._m4_post_v2_r2` |

## A. Mission status

**Completed with a justified, implemented change.** Diagnosis A–F was produced
first; the implementation gate passed for one defect only (the answerability
gate's structural vocabulary). The change was implemented, tested and measured
on the same frozen benchmark.

## B. Verified baseline

Claim-level baseline (identical in v1 and v2):

| Metric | Lexical | Relation-aware |
|---|---:|---:|
| Propositional claims | 75 | 75 |
| Support precision | 0.9322 | 1.0000 |
| Support recall | 0.8333 | 0.9545 |
| Support F1 | 0.8800 | 0.9767 |
| False accepts / rejects | 4 / 11 | 0 / 3 |
| Contradiction P / R / F1 | n/a (binary) | 0.7143 / 1.0000 / 0.8333 |
| Exact three-way | — | 0.9333 |

Population: 75 propositional claims (66 SUPPORTED, 5 CONTRADICTED, 2
INSUFFICIENT_EVIDENCE, 2 PARTIALLY_SUPPORTED) plus 28 non-claims in v2
(29 in v1). Answer relevance, which is annotated per claim and reported by the
runner: **57 of 75 claims answer their question (76.0 %)**; 18 are off-target and
**9 of those are fully evidence-supported** (12 % of all claims).

Generation-level baseline (`generation_benchmark_2026-10-18_m4_baseline`,
format 10, current code, reproduced independently of the older `fmt10` report):

| Metric | Value |
|---|---:|
| Generated answers / answerable | 75 / 140 (53.6 %) |
| Answerability-gate abstentions (answerable) | 49 |
| Withheld-unattributable (answerable) | 16 |
| Exact match / token F1 | 0.1286 / 0.2567 |
| Empty rate (all 182) | 0.5769 |
| Unanswerable spurious answers | 2 / 42 (0.0476) |
| Unsupported-claim rate | 0.1981 |
| Citation accuracy | 0.8019 |
| Gate abstentions (all rows) | 83 |

The `fmt10` report (2026-10-17) was reproduced exactly on EM and F1; claim counts
vary by one between runs because generation length is sampled, which is why this
mission re-ran the baseline instead of relying on the archived file.

## C. Investigation A — answerable questions without claims

**65 of 140 answerable questions produce no claim**; the reported "75/140
answerable produce claims" is confirmed (75 answered, 53.6 %). The two causes are
disjoint:

| Bucket | Count | Stage |
|---|---:|---|
| Answerability gate refused before generation | 49 | generation gate |
| Generation produced text the verifier withheld | 16 | verification policy |

### C1. Gate abstentions (49)

All 49 rows have their gold answer inside the recorded context
(`gold_in_context = true` in `analysis.json` for every case). Missing distinctive
terms cluster into three groups:

| Pattern | Rows | Example |
|---|---:|---|
| Only question/document-structure terms missing (`section`, `content`, `covered`, `near`, `boundary`, `between`, `table`, `looking`, `show`, `detailed`, `context`, `listed`, `comes`, `monetary`, `amount`, `metric`, `count`) | 30 | `sec_569eed5a` "Describe the content of the Transformation Era (2011-2020) section?" — missing `content`, `section`; gold `Transformation Era (2011-2020)` is the section body |
| Structural terms plus one or two genuine content terms | 14 | `mc_98a6aef8` "…near the boundary between Dataset Overview and Station Distribution?" — missing `near`, `boundary`, `between`, `overview` |
| Content terms only (paraphrase, stripped table header, different unit) | 5 | `num_1ae85d6b` "current FY2024 revenue" vs context "Annual revenue of … fiscal year 2024"; `num_40784c07` "division revenue" vs the header-less table row "Enterprise Solutions $412.5 million" |

Cause: `generation.verification.answerability` treats every content token except
`_QUESTION_WORDS` and `_GENERIC_QUESTION_TERMS` as a topic term and refuses when
more than one is absent. The gate already documents that answer-shape words
("compare", "steps") are not topics; document-structure and location words used
by the benchmark's section, table and boundary templates were never added.

### C2. Withheld answers (16)

Classification from the recorded `generative_unsupported` text, gold answer and
question:

| Category | Count | Evidence |
|---|---:|---|
| Correct value/claim withheld (false withholding) | 4 | `tc_8340538b` gold `1,000 req/min`, emitted exactly that; `tc_06f5c7e8` gold `+4.2%`, emitted `+4.2%`; `sec_5e1deffc` and `sec_e95f766d` (content answers to section questions, labelled SUPPORTED/answers-question in v2) |
| Correct value present inside an over-wide list/compound, whole claim rejected | 4 | `li_631f3671` (gold `Free Cash Flow: $189.4 million` inside a 5-item list), `li_050b38c1`, `tc_115f3133` (gold `500,000 requests` inside a 3-value list), `tc_78ac63a0` (gold `$0.0M` in `$0.0M and $1.6M`) |
| Wrong value/attribute (correct withholding) | 5 | `ds_0ea2924f` `$3` vs `142.6 million`; `ds_c8d09ef8` `$2` vs `118.2 million`; `lc_dad0e4e6` `950` vs `1,000`; `tc_1658c1fb` `0.0` vs `4.2`; `tc_479dca78` revenue where the division was asked |
| No claim recorded although the warning says withheld (observability gap) | 2 | `ds_e21b45e0`, `num_ebb0173c`: empty `generative_unsupported`, so the rejected text cannot be inspected |
| Benchmark gold is a section title while the answer states the section's content | 1 | `sec_70c7b5b7` gold `Forward Guidance`; emitted the forward-guidance range |

The 8 false withholdings are a **lexical-verifier** limitation (the relation-aware
verifier accepts all but the over-wide lists), not a generation defect. Changing
the production verifier default is explicitly out of scope for this mission, so
these were documented and left unchanged.

## D. Investigation B — non-claim extraction

Verified: **28 non-claims in v2 (27.2 % of 103)**, 29 in v1 (27.9 % of 104).
v2 categories (`analysis.json`):

| Category | Count | Example |
|---|---:|---|
| `table_render` | 22 | `Variable \| Unit \| Min \| Max \| Mean \| Missing % [1]`, `Tier \| Rate Limit \| Burst Limit \| Monthly Quota` |
| `fragment` | 5 | `percent`, `CFO` |
| `heading` | 1 | `Founding and Early Years` |

The extractor (`generation.planning.split_claims`) splits rendered tables and
list lines on punctuation and pipes and emits header cells as claims. Both
verifiers accept most of them (lexical 28/28, relation-aware 20/28) because the
text really is in the evidence — they are structurally non-propositional, not
unsupported. They are excluded from the propositional denominator, so they do
**not** distort support precision/recall; they do inflate raw claim counts and
would distort any naive "claims supported" metric. No dataset relabelling was
performed. Materiality: **harmless to the current metrics, misleading to a raw
claim count**. A future extractor improvement (drop header rows and bare
fragments) is a separate change with no measured answer-quality benefit.

## E. Investigation C — supported but off-target claims (9)

Every one of the 9 was inspected; `answers_question=false` with
`gold=SUPPORTED`.

| Record | Claim | Why it does not answer |
|---|---|---|
| `lc_430b8915` | `200 employees` | States the 2005 count; the question asks the 2010 count (650) |
| `lc_dad0e4e6` | `950` | Total after the acquisition, not the later 1,000 the question asks |
| `tc_8faf2be8` | `Revenue exceeds $150M` | Answers a different row/column; the question asks employees |
| `tc_e7eb93d1` | `Revenue exceeds $150M.` | Same milestone, but the asked year is different |
| `tc_a7432939` | `$61,250.` | A cell from the Q2 2025 row; the gold span is the row label |
| `tc_e75b3a72` | `Auth required POST.` | The table row does, but the asked method is different |
| `tr_7e68327d` | `Document details` | One column of the asked row (`GET /documents/{id}`) |
| `tr_b0ffbc0f` | `Auth required.` | One column of the asked `DELETE` row |
| `tr_ddbb3252` | `/qa/ask` | One column of the asked endpoint row |

Taxonomy: **4 wrong attribute/value/time** (`lc_430b8915`, `lc_dad0e4e6`,
`tc_8faf2be8`, `tc_e7eb93d1`) and **5 partial table/list extraction**
(`tc_a7432939`, `tc_e75b3a72`, `tr_7e68327d`, `tr_b0ffbc0f`, `tr_ddbb3252`).
None is a verifier error: evidence support and question relevance are different
dimensions, and the verifiers only see the evidence. Responsibility: 4 generation
(answer picked the wrong row/value), 5 generation/extraction (the answer is one
cell rather than the asked row), 2 of which have ambiguous benchmark gold
(`tc_a7432939` gold is the row label). No relevance evaluator is implemented in
production; the 9 are annotated labels in the frozen dataset and are reported by
`_answer_relevance` in the runner.

## F. Investigation D — actual pipeline

| Stage | Implementation | Metric computed? |
|---|---|---|
| Retrieval | `chat/rag.py`; benchmark supplies one recorded context per row | no (not part of this mission) |
| Answerability gate | `generation/service.py` → `generation.verification.answerability` | yes, counted from warnings |
| Generation | `generation/engine.py` (Flan-T5-base, evidence-only prompt) | latency only |
| Claim extraction | `generation.planning.split_claims` | claim counts |
| Support verification | `generation.verification.check_claim` (lexical default); optional `verification_relations` | support P/R/F1, FA/FR, contradiction |
| Withholding | `generation/service.py` (no attributable claim → empty answer) | withheld counts |
| Question relevance | **annotated per claim in the dataset**, not computed at runtime | 57/75 true, 9 supported off-target |
| Coverage | `_coverage` in the claim runner | answered / 140 answerable |
| Non-claim rate | dataset labels | 28/103 (v2) |
| Abstention | generation runner | 2/42 spurious unanswerable |

Missing metrics: expected-answer component coverage, multi-part completion,
per-question relevance prediction, correct/incorrect abstention per row. All
would need new annotations; none is inferred or invented here.

## G. Metric design

Implemented and valid now: claim support P/R/F1 (denominator: 75 propositional
claims), false accept/reject rates (denominator: 9 gold non-supported / 66 gold
supported claims), contradiction P/R/F1 (5 gold contradictions), exact three-way
(75 claims), answer coverage (140 answerable questions), claim count, non-claim
rate (denominator: all annotated claims), unanswerable spurious rate (42 rows).

Measurable but not yet computed: supported-off-target rate (already annotated:
9/75), question-level relevance accuracy (57/75), relevant-answer rate among
answered questions, per-category coverage. Proposed, **not implemented**:
expected-answer component coverage and multi-part completion — the benchmark
does not annotate components, so a value would be invented. Claim count alone is
explicitly not treated as answer quality.

## H. Decision and change

### Go/no-go

Only one defect passed every go criterion:

* **Reproducible**: 49/140 refusals, all with gold in context; the 44 patterns
  are deterministic question templates.
* **Responsible component identified**: `answerability`'s distinctive-term set.
* **In scope**: one production vocabulary set; no model, prompt, retrieval,
  threshold, dataset or verifier-default change.
* **Regression test**: yes, in `tests/unit/generation/test_generation_mark_depth.py`.
* **Measurable without changing the benchmark**: yes, same 182 rows and hash.

All other findings were **no-go**: false withholdings need a verifier-policy
decision (out of scope); non-claims are metric-harmless and dataset-frozen;
off-target claims are a generation/extraction issue with no small fix and a
75-claim evidence base.

### Change

`backend/generation/verification.py`: added `_STRUCTURAL_QUESTION_TERMS` (section,
content, covered, covers, discussed, listed, comes, boundary, between, near,
looking, table, show, detailed, full, context, metric, monetary, amount, count)
and excluded them from distinctive terms. Ordinals (`first`, `second`, …) are
**deliberately excluded from that set**: the first version of the change added
them and turned `unans_3b23eb33` ("When was the first version released?") from a
correct abstention into a spurious `September 2025` answer. With ordinals left as
topic terms the gate behaves identically on the 42 unanswerable rows and the
answerable refusals stay at 13. The rejected intermediate run (ordinals included) is
kept as `generation_benchmark_2026-10-18_m4_post`: same EM 0.1500 / F1 0.3091 but
spurious 3/42, which is the regression the corrected set removes.

Tests added (4): section question allowed, boundary question allowed, ordinal
kept as a topic term (refused), plus the existing gate tests. Focused file: 30
passed. Full unit suite: **1578 passed, 23 skipped, 0 failed** (exit 0).
`compileall` exit 0.

### Before / after (same benchmark, same hash, unchanged annotations)

| Metric | Baseline | Post | Δ |
|---|---:|---:|---:|
| Answerable questions answered | 75 / 140 (53.6 %) | 99 / 140 (70.7 %) | +24 |
| Answerability-gate abstentions (answerable) | 49 | 13 | −36 |
| Withheld unattributable (answerable) | 16 | 28 | +12 |
| Exact match (answerable) | 18 / 140 (0.1286) | 21 / 140 (0.1500) | +3 |
| Token F1 | 0.2567 | 0.3091 | +0.0524 |
| Empty rate (all rows) | 0.5769 | 0.4451 | −0.1318 |
| Unanswerable spurious | 2 / 42 (0.0476) | 2 / 42 (0.0476) | 0 |
| Unsupported-claim rate | 0.1981 (21/106) | 0.2199 (31/141) | +0.0218 |
| Citation accuracy | 0.8019 | 0.7801 | −0.0218 |
| Verified-answer rate | 0.3956 | 0.5275 | +0.1319 |

Row-by-row: **24 new answers, 0 answers lost, 0 answers changed**; 3 of the new
answers are exact matches (`num_ecc1df08` → `45`, `sec_c00a7fc1` → `Operating
Expenses`, `li_5a304295` → `Integration with Licensee's proprietary platforms`).
The other 21 are verified (attributable) but not exact-match; several are
superset/list answers whose gold is a cell. The two post runs
(`..._m4_post_v2`, `..._m4_post_v2_r2`) produce byte-identical answers; only
latency differs, so the table is deterministic.

Claim-level reports were **not** re-run as a "post" claim comparison: both
`m4_baseline` claim reports consume the recorded `fmt10` / `relations_r5`
answers, not a fresh generation, so they would be identical by construction. The
generation benchmark is the honest before/after for this change, and the
post-change diagnosis (`..._m4_post/`, `--generation-run ..._m4_post_v2`)
confirms the bucket shift 75→99 answered, 49→13 gate, 16→28 withheld.

## I. Integrity and reproducibility

* Benchmark hash verified in every generation run (baseline, the rejected ordinal
  variant, both corrected post runs) and both claim runs.
* Datasets untouched: v1 and v2 report the same statistics as Mission 3.
* Historical reports were not modified; all new reports carry new run IDs.
* Production verifier default remains `lexical`; `DOCUMIND_VERIFIER` untouched.
* No thresholds, prompts, models, retrieval, database or frontend changes.
* No git staging, commit, push or deploy; HEAD remains `6baaa2a`.

## J. Limitations and next steps

* The gate remains lexical: 13 answerable refusals survive (5 paraphrase/table
  header/unit cases, 8 boundary cases whose context genuinely omits the asked
  section's terms). Fixing those needs evidence construction, not a stoplist.
* 8 correct answers are still withheld by the lexical verifier; the relation-aware
  verifier accepts most of them. This is the largest remaining coverage loss
  (+8/140 possible) but requires a verifier-policy decision.
* 21 newly surfaced answers are not exact-match; more coverage necessarily
  surfaces weaker answers, and the unsupported-claim rate rose slightly.
* Single annotator, 75 propositional claims, one benchmark; no integration/E2E/
  browser/DB/live-server checks were run, and no new 15-mark benchmark was started.
* Next justified experiment: measure the relation-aware verifier on the **new**
  post-gate answer population (not a default change), and separately evaluate an
  evidence-construction fix for header-stripped table rows.
