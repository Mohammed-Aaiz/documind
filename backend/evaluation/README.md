# DocuMind Research Evaluation

```
tests/          → Is the software correct?      (pytest; backend/tests/)
evaluation/     → Does the research method improve measurable outcomes?
```

The two are deliberately separate. Nothing here is collected by pytest
(`pytest.ini` sets `testpaths = tests`), nothing here is executed at
application startup, and no production module imports from here.

**Research runners must be launched explicitly, from `backend/`**, e.g.:

```bash
cd backend
# The runners write to — and several delete rows from — the database they
# target, so an isolated database is mandatory (placeholders, not real values):
DOCUMIND_INTEGRATION_DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:PORT/documind_integration \
  ./venv/Scripts/python.exe evaluation/experiments/run_phase3f_evaluation.py
```

Without that configuration the run is **refused** (see “Isolated databases and
append-only artifacts”).  …**never** with a bare `python` from an arbitrary
working directory, and never as part of the test run.

## Layout

```
evaluation/
├── harness/          # pre-existing in-process evaluation harness
│   ├── corpus.py     #   corpus loading + metric glue
│   ├── extraction.py #   gold span / evidence extraction
│   └── metrics.py    #   EM / token-F1 / MRR primitives
│                     #   (evaluator.py was removed 2026-09-30: never importable,
│                     #    never imported, never executed — superseded by runner.py)
├── structure_eval.py # offline, deterministic, element-level structure-aware
│                     #   harness (Feature #15); no DB / pgvector / model
├── datasets/         # labelled evaluation corpora + generators
│   ├── phase3d_corpus.py
│   ├── phase4b_corpus.py
│   ├── heading_corpus.py   # PDFs with real font-detected headings and
│   │                       #   sections spanning pages (for the A–D runner)
│   └── structure_eval_corpus.py  # synthetic structure-labelled fixture
│                           #   (elements/chunks/questions + distractors)
├── experiments/      # executable research runners (run_*.py)
├── baselines/        # vector_only/ · structure_only/ · dual_path/
├── metrics/          # retrieval + QA metric implementations
└── reports/          # generated measurement reports
```

`datasets/` is the shared home for the research corpora. It is imported by tests
(the direction **tests → evaluation** is allowed); `evaluation/` never imports
from `tests/`.

## Relocated runners

On 2026-09-30 the standalone measurement harnesses were moved out of the
repository root and out of `Testing_module/`. They were renamed `test_*.py` →
`run_*.py` so that they can never be mistaken for — or collected as — tests.
This is a deliberate categorisation, not a blind rename:

| Old path | New path | Why |
|---|---|---|
| `backend/test_phase3d_evaluation.py` | `evaluation/experiments/run_phase3d_evaluation.py` | chunker/context evaluation harness (writes `DocumentChunk` rows directly, bypassing HTTP ingestion by design) |
| `backend/test_phase3d_upload_integration.py` | `evaluation/experiments/run_phase3d_upload_integration.py` | full-ingestion validation counterpart |
| `backend/test_phase3e_integration.py` | `evaluation/experiments/run_phase3e_integration.py` | processing lifecycle validation against real PostgreSQL |
| `backend/test_phase3e_validation.py` | `evaluation/experiments/run_phase3e_validation.py` | final validation gate: direct SQL inspection |
| `backend/test_phase3f_evaluation.py` | `evaluation/experiments/run_phase3f_evaluation.py` | EM / token-F1 / MRR / failure-taxonomy evaluation |
| `backend/test_phase4b_evaluation.py` | `evaluation/experiments/run_phase4b_evaluation.py` | expanded-corpus arm evaluation |
| `backend/test_phase4c_diagnostics.py` | `evaluation/experiments/run_phase4c_diagnostics.py` | offline failure-isolation diagnostics |

Their shared corpora moved with them:

| Old path | New path |
|---|---|
| `backend/tests/phase3d_corpus.py` | `evaluation/datasets/phase3d_corpus.py` |
| `backend/tests/phase4b_corpus.py` | `evaluation/datasets/phase4b_corpus.py` |

Each runner now resolves the backend package root explicitly
(`Path(__file__).parents[2]`) instead of assuming it sits in `backend/`.
They still expect **`backend/` as the working directory**, because they default
`QA_MODEL_NAME` to `./models/documind-qa`.

## Generative answer evaluation (2026-10-17)

Three runners measure the local generator. Each writes a new, uniquely named
directory under `evaluation/reports/` and never touches a historical report.

| Runner | What it measures | Current report |
|---|---|---|
| `run_generation_benchmark.py --format 5\|10\|15` | frozen P3 benchmark (182 rows: 140 answerable / 42 unanswerable), extractive vs generative, EM / token-F1 / abstention / spurious / unsupported-claim / lead-answer metrics | `reports/generation_benchmark_2026-10-17_fmt5`, `..._fmt10` |
| `run_mark_depth_evaluation.py` | 5 vs 10 vs 15 marks on a 6-section fixture, 5 question types, hand-labelled key facts | `reports/mark_depth_2026-10-17` |
| `run_generation_config_sweep.py` | decoding / prompt variants under identical gate and scoring; writes per-variant predictions for pairwise comparison | `reports/generation_config_sweep_2026-10-17` |
| `run_claim_verification_evaluation.py --split dev\|test` | claim-level support / contradiction / insufficient-evidence decisions of the lexical and relation-aware verifiers on the versioned claim dataset (both splits reported separately; `test` is held out) | `reports/claim_verification_2026-10-17_final` |
| `run_answer_claim_evaluation.py --dataset v1\|v2` | the same two verifiers on the claims the generator **actually emitted** for the frozen benchmark (v1: 104 annotated claims / 86 questions; v2: 103 after the splitter fix), plus coverage, answer-set changes and generation-level consequences from the recorded runs | `reports/answer_claim_evaluation_2026-10-18_m3_v2` (evidence-splitter baseline: `..._m3_pre_v2`; v1: `..._m3_v1`; older: `..._v2`, `..._r4`) |

All three verify the frozen benchmark's SHA-256 before inference and abort without
writing on a mismatch. The benchmark is read-only. Model-selection decisions (and
the reason no replacement model was adopted) are recorded in
`backend/architecture/DOCUMIND_MODEL_SELECTION_2026-10-17.md`.

Every runner now takes `--run-id`, so a re-run writes a new directory instead of
overwriting a historical report (the claim-level runner additionally prints the
two splits separately). Verification changes are recorded in
`backend/architecture/DOCUMIND_EVIDENCE_VERIFICATION_2026-10-17.md`.

```bash
cd backend
./venv/Scripts/python.exe -m evaluation.experiments.run_claim_verification_evaluation --split dev --run-id claim_verification_<date>
./venv/Scripts/python.exe -m evaluation.experiments.run_claim_verification_evaluation --split test --run-id claim_verification_<date>
# The relation-aware verifier is opt-in; the lexical default is unchanged.
DOCUMIND_VERIFIER=relations ./venv/Scripts/python.exe -m evaluation.experiments.run_generation_benchmark --format 10 --run-id generation_benchmark_<date>_relations
DOCUMIND_VERIFIER=relations ./venv/Scripts/python.exe -m evaluation.experiments.run_mark_depth_evaluation --run-id mark_depth_<date>_relations
```

### Claim-level evaluation on actual answers (2026-10-18)

The synthetic claim set answers "can a verifier decide support?" but not "does it
work on what the generator really says?".  `run_answer_claim_evaluation.py`
closes that gap without new inference:

* `datasets/answer_claims_v1.jsonl` (loaded by `datasets/answer_claims_v1.py`) is
the frozen reference set: every claim emitted for an answerable benchmark row in
the recorded 10-mark lexical and relation-verifier runs, annotated against the
row's own `context` (the evidence the generator saw).  It contains 104 claims
over 86 questions: 75 propositional (66 SUPPORTED, 5 CONTRADICTED, 2
INSUFFICIENT, 2 PARTIALLY_SUPPORTED) and 29 non-claim fragments, which are kept
and reported separately rather than silently dropped.  `answer_claims_v2.jsonl`
re-extracts the same answers with the corrected splitter: 103 claims (75
propositional, 28 non-claims); one `Dr.` fragment is gone and `Dr. Sarah Chen`
replaces the `Dr.` + `Sarah Chen` split.
* The runner re-checks every claim against the recorded answers and the frozen
benchmark hash before scoring, then runs both verifiers on **one shared claim,
question and evidence-block list** (`verify_both`).  The lexical verifier is
binary: its native wrong-entity reason is counted separately and is never mapped
to `CONTRADICTED`.  Non-claims are excluded from truth metrics; accepting them is
reported as a generation-quality signal.  `answers_question` is reported
separately from truth, because a supported value can still come from the wrong
column or year.  Undefined rates/F1 are `null`/`n/a`, and `summary.json` records
the denominator of every metric.
* The report also compares the two recorded runs: answer coverage, EM/token-F1,
unsupported-claim rate, abstention, and exactly which answers the candidate
verifier removes or admits.
* Since run `r4`, a value-only claim is bound to the attribute the question asks
  for. A value sitting in another table column, or a per-share fragment offered
  as a total, is not accepted just because it occurs in the passage. Wrong
  attribute is reported as `INSUFFICIENT_EVIDENCE` with an explicit reason, and
  becomes `CONTRADICTED` only when the asked attribute states its own different
  value. The binding block in `summary.json` reports how often the check fired.
* **Versioned extraction.** `--dataset v1` scores the frozen 104-claim set with
  `datasets/legacy_split.py` (a copy of the pre-fix splitter), so the historical
  report reproduces exactly. `--dataset v2` scores `datasets/answer_claims_v2`,
  re-extracted with the corrected production splitter; its one changed record is
  documented in `answer_claims_v2.CHANGES` and rendered in the report. The splitter
  fix is recorded in `backend/architecture/DOCUMIND_ANSWER_CLAIM_EVALUATION_2026-10-18.md` §13.
* **Evidence segmentation.** Claim and evidence splitters now share
  `generation/sentence_boundaries.py`, so `Dr.`, `U.S.`, initials and `e.g.` no
  longer fragment evidence. The re-baseline is
  `reports/answer_claim_evaluation_2026-10-18_m3_v2` (v2) and `..._m3_v1` (v1),
  with the pre-fix runs kept as `..._m3_pre_v1` / `..._m3_pre_v2`; see §14 of the
  architecture record.

```bash
cd backend
./venv/Scripts/python.exe -m evaluation.experiments.run_answer_claim_evaluation --dataset v1 --run-id answer_claim_evaluation_<date>_v1_repro
./venv/Scripts/python.exe -m evaluation.experiments.run_answer_claim_evaluation --dataset v2 --run-id answer_claim_evaluation_<date>_v2
```

The production default is unchanged (lexical).  The recorded result, the
decision and the single-annotator limitation are in
`backend/architecture/DOCUMIND_ANSWER_CLAIM_EVALUATION_2026-10-18.md`.

### Answer coverage and relevance diagnosis (2026-10-18, Mission 4)

`run_answer_claim_evaluation.py` measures claims, but not **why** an answerable
question produced none. `experiments/diagnose_answer_quality.py` classifies each
of the 140 answerable benchmark rows into `gate_abstention`, `withheld` or
`answered_with_claims` from the recorded runs, dumps every gate refusal with its
missing terms and whether the gold answer is in the context, lists every
non-claim, and lists every supported-but-off-target claim:

```bash
cd backend
./venv/Scripts/python.exe -m evaluation.experiments.diagnose_answer_quality
# Classify a newer generation run instead of the recorded fmt10 answers:
./venv/Scripts/python.exe -m evaluation.experiments.diagnose_answer_quality \
    --run-id answer_quality_diagnosis_<date>_post \
    --generation-run generation_benchmark_<date>_post
```

Baseline diagnosis (49 gate refusals, 16 withheld, 28 non-claims, 9 supported
off-target) is frozen in
`reports/answer_quality_diagnosis_2026-10-18_m4/` (`REPORT.md`,
`analysis.json`); `analysis.json` was captured **before** the gate change below.
The post-change classification is `..._m4_post/` (99 answered, 13 gate, 28
withheld).

One defect passed the implementation gate: `answerability` treated the
benchmark's document-structure vocabulary (`section`, `content`, `covered`,
`near`, `boundary`, `between`, `table`, `looking`, `show`, `detailed`,
`context`, `listed`, `comes`, `monetary`, `amount`, `metric`, `count`) as topic
terms. It is now in `_STRUCTURAL_QUESTION_TERMS` and excluded from distinctive
terms; ordinals stay topic terms because `first` carries "When was the first
version released?". Same benchmark and hash:

| Metric | `..._m4_baseline` | `..._m4_post_v2` |
|---|---:|---:|
| Answerable answered | 75/140 | 99/140 |
| Gate abstentions (answerable) | 49 | 13 |
| Exact match | 0.1286 | 0.1500 |
| Token F1 | 0.2567 | 0.3091 |
| Unanswerable spurious | 2/42 | 2/42 |

24 answers added, 0 lost or changed, 3 exact matches; the two post runs produce
identical answers. Claim-level reports were not re-run as a post comparison:
they consume the recorded `fmt10` answers, not a fresh generation. Full record:
`backend/architecture/DOCUMIND_ANSWER_QUALITY_2026-10-18.md`.

### Table entity alignment (2026-10-18, Mission 5)

`numeric_entity_alignment` anchored on the sentence containing the question's
rarest term, which in a pipe table is a column name — so it compared the value
row against the **header** subject and withheld correct cells. It now parses a
simple table, binds the asked column from the header (cell 0 is the row label,
not a column), locates the row by its label, and accepts only when all of the
claim's numbers in that row are in the asked column. Non-tables and ambiguous
headers keep the prose rule.

Mission 5 artifacts:

* `experiments/build_answer_error_ledger.py` writes a 182-row question-level
  ledger joining the benchmark, the baseline/post generation runs and the v2
  claim annotations: `reports/answer_quality_mission5_2026-10-18_diagnosis/`
  (`DIAGNOSIS.md`, `EXPERIMENT.md`, `ENGINEERING.md`, `ledger.jsonl`,
  `summary.json`).
* Generation: `generation_benchmark_2026-10-18_m4_post_v2` →
  `..._m5_post_v1` (repeat `..._m5_post_v1_r2`, identical answers).
* Claims: `answer_claim_evaluation_2026-10-18_m4_baseline_v2` → `..._m5_v2`.

| Metric | M4 | M5 |
|---|---:|---:|
| Answerable answered | 99/140 | 100/140 |
| Withheld answers | 28 | 27 |
| Exact match | 0.1500 | 0.1500 |
| Token F1 | 0.3091 | 0.3103 |
| Unanswerable spurious | 2/42 | 2/42 |
| Lexical claim F1 | 0.8800 | 0.8889 |

The two recovered answers (`tc_8340538b`, `tc_06f5c7e8`) carry the correct cell
but append the table header, so they are not exact matches; one wrong
multi-column answer (`tc_f3617604`) is now withheld. The reported M4
unsupported/citation regression is a metric artifact: rejected claims from
**withheld** answers are counted in the rate while returned answers carry the
same 5 unsupported claims (`EXPERIMENT.md` §3). Full record:
`backend/architecture/DOCUMIND_TABLE_ENTITY_ALIGNMENT_2026-10-18.md`.

## Measuring the A–D ablation

```bash
cd backend
# The runner writes/deletes rows, so it must be pointed at an isolated database
# and at a new output directory.  Both are required now:
DOCUMIND_INTEGRATION_DATABASE_URL=postgresql+asyncpg://user:pass@host:port/documind_integration \
  ./venv/Scripts/python.exe evaluation/experiments/run_dual_path_ablation.py \
    --out /tmp/ablation_run_1

./venv/Scripts/python.exe evaluation/experiments/run_dual_path_ablation.py \
  --corpus heading --out /tmp/ablation_heading_run_1
```

Without an isolated target the runner **refuses to start** (exit status 2): the
target would be the application database.  See “Isolated databases and
append-only artifacts” below.

This ingests a labelled corpus into a dedicated eval user
(`ablation_eval@test.local`), derives gold chunk ids from each question's `evidence`
substrings after ingestion, runs all four variants of `schemas.ABLATION_MATRIX` through
the real pipeline, and writes `reports/ablation_{A,B,C,D}.json/.md` plus a
`reports/ablation_config.json` record of the exact configuration measured. All
setup/teardown deletes are scoped to that one user.

**Production alignment (P0 hardening).** The runner now evaluates the
**production configuration by default**:

* chunker = `settings.chunker_version` (production default **`legacy`**);
* ingestion reuses the production builders (`documents.routes._build_chunk_objects`,
  `documents.parser.parse_pdf` + `documents.structure.replace_document_structure` for
  PDFs, `graph.service.replace_document_graph`);
* **C/D = the exact production retrieval composition**:
  `retrieve_chunks` (pgvector) → `retrieve_dual_path` (heading/section seeds →
  chunk-graph expansion → RRF) → `brain.adapters._augment_with_structure`
  (the `document_structure_elements` stream);
* **D = C + the real production gate** (`brain.gate.evaluate` over a real
  `ExecutionContext`/`EvidenceBundle`), not a runner-local threshold.

Retrieval metrics (Recall/Precision/MRR/nDCG) score **chunk-level** gold only; the
element-level structure stream is included in the answer context (as production does)
but excluded from the retrieval ranking, because its ids are not chunks and would
depress Precision@K for a reason unrelated to retrieval quality.

### Measured result — a null result

Evaluated against the production `legacy` chunker on the two real corpora
(phase3d: 12 docs / 42 q; heading: 4 PDFs / 23 q), semantic-only (**A**) and the
production dual-path composition (**C**) are effectively equivalent:

| corpus | variant | R@5 | nDCG@5 | EM | token F1 | retrieval ms |
|---|---|---|---|---|---|---|
| phase3d | A | 0.7738 | 0.7268 | 0.5238 | 0.6296 | 388 |
| phase3d | C | 0.7738 | 0.7295 | 0.4762 | 0.6189 | 2965 |
| heading | A | 0.8478 | 0.7567 | 0.4783 | 0.7470 | 396 |
| heading | C | 0.8478 | 0.7579 | 0.4348 | 0.6749 | 2099 |

Paired bootstrap (10 000 resamples, 95 % CI of the C−A mean difference): Recall@5
identical on both corpora; nDCG@5 difference is +0.0027 / +0.0012 (CI ≈ [0, small]);
token-F1 and EM are **lower** for C and the CIs include 0 (not statistically
significant). Retrieval latency rises roughly **5–7×** for C/D. **No measurable
quality improvement was demonstrated**; the dual path costs latency without a
measured retrieval or answer-quality gain on these corpora.

The gate (**D**) does produce a measured effect on unanswerable questions.
`unsupported_answer` is the unsupported-answer **rate among the 3 unanswerable
questions** (never a fraction of all questions — see the metric-definition note
below): phase3d A/C = **3/3 = 1.000** → D = **0/3 = 0.000**; heading A/C =
**3/3 = 1.000** → D = **1/3 = 0.333**. That is an honesty improvement on
unsupported questions, not an answer-quality gain. It comes at the cost of a
lower `factual_grounded` rate (abstentions are not "answered"), because that
metric is averaged over all questions, including abstentions.

### Metric definitions (denominators)

Each metric is averaged over its own population; a metric whose population is
empty is reported as `null` (JSON) / `n/a` (markdown), never as `0.0`:

| metric | population |
|---|---|
| `recall@K`, `precision@K`, `mrr`, `ndcg@K` | all measured questions (unanswerable questions carry no gold and score 0.0) |
| `exact_match`, `token_f1` | all measured questions |
| `factual_grounded` | all measured questions (an abstention counts as not grounded) |
| `evidence_coverage`, `path_agreement` | all measured questions |
| `unsupported_answer` | **unanswerable questions only** |

**`unsupported_answer` (`unsupported_answer_rate`)** is computed over the
unanswerable-question population only. If no unanswerable questions exist, the
metric is unavailable (`null`) rather than zero, and the reason is recorded in the
report's `not_measured` map. This matches the documented
`evaluation.qa_metrics.unsupported_answer_rate` population semantics. An earlier
revision averaged its per-question 0/1 indicator over every question, reporting
`3/42 = 0.0714` (phase3d) where the correct value is `3/3 = 1.0`; the current
reports supersede that earlier run.

> **Known divergence (recorded, not corrected here).** The pre-existing runners
> (`experiments/run_phase3d_evaluation.py`, `run_phase3f_evaluation.py`,
> `run_phase4b_evaluation.py`) aggregate retrieval, answer and evidence metrics
> over the **answerable** population (`answerable = [r for r in results if
> r.answerable]`), while this runner's `_aggregate` averages them over all
> measured questions. The unanswerable questions therefore dilute `recall@K`,
> `precision@K`, `mrr`, `ndcg@K`, `exact_match`, `token_f1` and (for abstaining
> variants) `factual_grounded`/`evidence_coverage`. Example (phase3d A): `R@5`
> 0.7738 over all vs 0.8333 over answerable; heading A: 0.8478 vs 0.9750. This is
> left unchanged deliberately by this metric-integrity repair, which was scoped to
> `unsupported_answer`; reconciling the remaining populations to the answerable
> convention is the recommended next step.

`--corpus` selects which labelled corpus to measure (each writes its own reports, so the
two are never confused):

| `--corpus` | module | shape | reports |
|---|---|---|---|
| `phase3d` (default) | `datasets/phase3d_corpus.py` | 12 documents (DOCX/TXT/PDF), 42 questions (39 answerable / 3 unsupported; 35 direct, 7 table) | `reports/ablation_*` |
| `heading` | `datasets/heading_corpus.py` | 4 PDFs with real font-detected headings and page-spanning sections, 23 questions (20 answerable / 3 unsupported; 13 section, 7 cross-page) | `reports/ablation_heading_*` |

`--chunker` overrides the evaluated chunker (`production` by default, i.e.
`settings.chunker_version`). Reports carry a sibling `*_config.json` recording the
exact configuration, corpus statistics and variant flags.

`--out` is **required** and append-only: every artifact is reserved before the
run starts, an existing name aborts the run instead of being replaced, and the
historical `evaluation/reports/*` files are never written to by this runner.
Each run also writes `run_manifest.json` last, and the per-question JSON now
carries a `detail` block (predicted/expected answers, retrieved + supplied
evidence with ranks, outcome and failure attribution) so an aggregate metric can
be traced back to the questions behind it.

The `heading` corpus exists because the Phase 3D `multipage_section.pdf` only carries its
heading on the first page, so no `SAME_SECTION` edge can form across the page break and the
structural path has almost nothing to traverse. The heading corpus' sections continue onto
the next page without repeating the heading, which yields 16 `SAME_SECTION` edges across
its four documents. Its contract (real headings, documented spanning sections, every
labelled question's evidence present in a chunk) is pinned by
`tests/unit/evaluation/test_heading_corpus.py`. Results and an honest reading for both
corpora are in `backend/architecture/IMPLEMENTATION_REPORT_2026-09-30.md` §9.1 (Phase 3D)
and §9.2 (heading).

## Isolated databases and append-only artifacts

Two shared modules make the research runners safe to use against real data:

| module | responsibility |
|---|---|
| `evaluation/isolation.py` | resolve the evaluation DSN, and *prove* it is not the application database before the first connection |
| `evaluation/artifacts.py` | caller-specified output directories, exclusive (never overwriting) writes, and the reproducibility manifest |

### Choosing the database

```
--database-url <dsn>                    (highest precedence)
DOCUMIND_INTEGRATION_DATABASE_URL=<dsn> (the operator workflow, same variable
                                         tests/fixtures/integration_db.py honours)
the application DSN                     (pre-existing behaviour; the guard then
                                         refuses it, so nothing is redirected
                                         behind the caller's back)
```

The guard compares the complete identity `(host, port, database)` — never a bare
database name — against the application's, where “the application's” is resolved
from `backend/.env` **first** so a runner that exports `DATABASE_URL` for its own
children cannot redefine it.  It refuses the application database, and it fails
closed when either identity cannot be established (no host, no database name —
e.g. a SQLite DSN).  It establishes no connection and reads no rows, so it is
safe to run against a database that is down or does not exist.  Errors are
credential-free: only `scheme://host:port/database` is ever printed.

This is a deliberate mirror of the test layer's guard in
`tests/fixtures/integration_db.py`, not an import: `evaluation/` never imports
from `tests/`.  `tests/unit/evaluation/test_evaluation_isolation.py` pins that the
two stay in step.

### Output and manifest

* A run writes only into the directory it was given; colliding file names abort
the run *before* the measurement starts, and each file is created with `open(…,
"x")`, so a race cannot replace a recorded artifact either.
* `run_manifest.json` is written **last and always** (including after a failure,
with `result.status` `failed` + the exception type).  A directory holding
reports but no manifest is by definition an interrupted run.
* The manifest records the repository commit/branch/working-tree state, the
dataset identifier and counts, the frozen benchmark digest, the evaluation
protocol and configuration, the model identifiers (including the QA weights'
SHA-256), the credential-free database identities, the output file list and the
run result.  Anything undeterminable is recorded as `"unavailable"`.

### Instrumented runners (and the documented exceptions)

| runner | isolated DSN | output directory |
|---|---|---|
| `experiments/run_dual_path_ablation.py` | required (`--database-url` / env) | `--out`, required, append-only |
| `experiments/run_phase3d_upload_integration.py` | required (`--database-url` / env) | `--out`, optional (writes `checks.json` + manifest) |
| `experiments/run_phase3d_evaluation.py` | required (`--database-url` / env) | unchanged (historical report paths) |
| `experiments/run_phase3e_integration.py` | required (`--database-url` / env) | unchanged (console only) |
| `experiments/run_phase3e_validation.py` | required (`--database-url` / env) | unchanged (console only) |
| `experiments/run_phase3f_evaluation.py` | required (`--database-url` / env) | unchanged (historical report paths) |
| `experiments/run_phase4b_evaluation.py` | required (`--database-url` / env) | unchanged (historical report paths) |

The five `run_phase3*` / `run_phase4b` runners were secured on 2026-10-09
(Step 0.6): each resolves its target through `evaluation/isolation.py` and proves
it is not the application database **before its first connection** and before the
application is imported.  Their evaluation logic, corpora, metrics and report
paths are unchanged — this was a database-isolation change, not an evaluation
redesign.

### Five legacy phase runners — required configuration (Step 0.6)

Applies to `run_phase3d_evaluation`, `run_phase3e_integration`,
`run_phase3e_validation`, `run_phase3f_evaluation`, `run_phase4b_evaluation`.

**Configuration.** Each runner takes `--database-url`, which wins over
`DOCUMIND_INTEGRATION_DATABASE_URL`; if neither is set, the *application* DSN is
resolved (nothing is redirected behind the caller's back) and the guard then
refuses it.

```bash
cd backend
# Safe invocation — placeholders only, never real credentials:
DOCUMIND_INTEGRATION_DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:PORT/documind_integration \
  ./venv/Scripts/python.exe evaluation/experiments/run_phase3d_evaluation.py

./venv/Scripts/python.exe evaluation/experiments/run_phase3e_validation.py \
  --database-url postgresql+asyncpg://USER:PASSWORD@HOST:PORT/documind_integration
```

**Failure behaviour when configuration is missing.** The run exits non-zero
(`UnsafeEvaluationTarget`) with a credential-free message naming the required
variable; no connection is opened, no row is written or deleted, and the run is
never silently pointed at another database.  An override that is set but empty
is refused too, rather than treated as “unset”.

**Application-database rejection policy.** The target's identity
(`host`, `port`, `database`) must differ from the application's, where “the
application's” is resolved from `backend/.env` first.  A database that merely has
the same *name* on a different server is a different database and is permitted;
a different port is enough.  The refusal message contains no password and no
credential-bearing DSN.  The guard is the single centralized implementation
(`evaluation/isolation.py`); the runners do not carry a copy of it.

**What has actually been demonstrated (and what has not).**

* *Source inspection:* the guard call precedes `os.environ["DATABASE_URL"]` and
  `create_async_engine(evaluation_dsn)` in each runner, and no runner contains a
  hard-coded DSN or an import-time `DATABASE_URL` default any more.
* *Mocked tests* (`tests/unit/evaluation/test_legacy_runner_isolation.py`):
  missing configuration and an explicitly requested application database are
  refused **before the engine factory is reached**; an explicit target reaches
  the engine factory verbatim; an unreachable loopback target fails as a
  connection error with no fallback.
* *Process-level failure path:* all five were launched as real subprocesses
  against a guaranteed-closed loopback port with an explicit target — each exited
  **1** with `ConnectionRefusedError` and wrote no reports or uploads.  What that
  exercises is the CLI/env plumbing and the “permitted but unreachable target”
  path, nothing else.
* *Real database execution:* **not re-demonstrated.** No run of these five
  runners against a live PostgreSQL instance has been performed since the change
  (and none is authorized yet).  The mocked boundary is not a substitute for it,
  and neither is the closed-port run: neither proves anything about behaviour
  *after* a connection succeeds.

**Still uninstrumented** (Step 0.5 findings F-2, outstanding):
`run_table_evidence_measurement.py` (loopback-only guard of its own;
`DOCUMIND_PHASE4_DATABASE_URL`), `run_structure_confirmation.py`,
`run_structure_element_measurement.py`, `run_structure_rrf_calibration.py`
(application DSN via `storage.database`).  `run_phase4c_diagnostics.py` touches
no database.  Do not run any of them until they receive the same treatment.

### Phase 3D upload/ask harness — scoped cleanup (Step 0.7, 2026-10-09)

`experiments/run_phase3d_upload_integration.py` used to end a run with an
**unscoped** `DELETE FROM document_chunks`.  Database isolation proves the
target is not the application database; it does **not** make a database-wide
delete safe — an isolated database shared with another experiment (or re-used
between runs) would have lost every chunk in it.

The cleanup now runs through `cleanup_harness_rows(db, user_id=…)`, scoped by the
ownership key the schema actually has:

```
documents.user_id      -> users.id              (ondelete="CASCADE")
document_chunks.document_id -> documents.id     (ondelete="CASCADE")   # a chunk has no owner column
```

Every document the harness ingests is uploaded through the real HTTP route by
the evaluation user it creates, so `user_id` reaches every row the run owns.
The deletion order is unchanged — reliability logs, chunks, documents, user —
and the two extra users the harness creates for isolation checks are still
removed by the earlier email-scoped block.  The statements are model-bound
rather than raw SQL, matching the cleanup pattern in `run_dual_path_ablation.py`.

Behaviourally verified by `tests/unit/evaluation/test_phase3d_cleanup_scope.py`
(17 tests on the SQLite fixtures): its own rows are removed; another user's
documents, chunks and logs survive — including when they share the document name
and the chunk text; running the cleanup twice is harmless; the guard still
refuses the application database before any engine exists; and the 40 `check()`
calls, the `checks.json`/manifest payload and the chunker-version restoration
are unchanged.

### Phase 3D evaluation runner — scoped cleanup (Step 0.8, 2026-10-09)

`experiments/run_phase3d_evaluation.py` used to bracket a run with **ten** raw
`DELETE FROM` statements: five tables deleted with **no predicate at all**
(`reliability_logs`, `chat_messages`, `chat_sessions`, `document_chunks`,
`documents` — twice: before and after the run) plus
`DELETE FROM users WHERE email LIKE 'phase3d_%'`.  The unpredicated deletes
removed every row of those tables in the target database, and the email prefix
also matched the sibling upload/ask harness's users
(`phase3d_upload_<8 hex>@test.local`) — database isolation proves the target is
not the application database, it does not make a database-wide delete safe.

Ownership is now explicit and single-sourced: the harness owns exactly the two
evaluation users it creates (`HARNESS_ARMS` → `harness_user_email` →
`HARNESS_USER_EMAILS`), and every row the run writes hangs off them:

```
documents.user_id       -> users.id             (ondelete="CASCADE")
reliability_logs.user_id-> users.id             (ondelete="CASCADE")
chat_sessions.user_id   -> users.id             (ondelete="CASCADE")
document_chunks.document_id -> documents.id     # a chunk has no owner column
chat_messages.session_id    -> chat_sessions.id # a message has no owner column
```

Cleanup runs through `owned_user_ids(db, emails=…)` and
`cleanup_harness_rows(db, user_ids=…)`, model-bound rather than raw SQL (so the
same scope is exercised on PostgreSQL and on the SQLite test fixtures).  The
deletion order is unchanged (logs → messages → sessions → chunks → documents →
users), the caller still commits, and the centralized guard still runs first:
`assert_safe_evaluation_target(` precedes both cleanup call sites.  The
evaluation surface (arms A/B/C, `TOP_K = 5`, metrics, the
`phase3d_evaluation_report.json` schema) is untouched.

Behaviourally verified by `tests/unit/evaluation/test_phase3d_evaluation_cleanup_scope.py`
(16 tests on the SQLite fixtures): the harness's own rows are removed; a sibling
harness user and an unrelated user keep their documents, chunk **ids**, chat
rows and reliability logs; running the cleanup twice is harmless; an empty sweep
is a no-op; the guard still refuses the application database before any engine
exists; and no raw `DELETE FROM` remains in the runner (AST-checked).  The
Step 0.6 pin in `test_legacy_runner_isolation.py` that asserted the *old*
statement count is replaced, for the runners remediated in Steps 0.8/0.9, by the
stricter no-raw-SQL contract — the remaining three keep their existing counts.

### Phase 3E integration runner — scoped cleanup (Step 0.9, 2026-10-09)

`experiments/run_phase3e_integration.py` ended a run with four raw `DELETE FROM`
statements, the second of which — `DELETE FROM document_chunks` — had **no
predicate at all** and therefore removed every chunk in the target database, not
just the ones the harness created.  Two further sites were already scoped
(`users WHERE email = :e` in step 8; `document_chunks WHERE document_id = :id` +
`documents WHERE id = :id` in step 9) but written as raw SQL with string UUID
binds, so they had no test coverage and relied on `ON DELETE CASCADE` for the
rows they were responsible for.

The harness creates two users — `phase3e_<8 hex>@test.local` (the owner of every
document, chunk, reliability row and chat row the run produces) and the
temporary isolation-check user `phase3e_other_<8 hex>@test.local` — and every row
hangs off them through the same keys as above (`documents.user_id`,
`reliability_logs.user_id`, `chat_sessions.user_id`; chunks and chat messages
reach their owner via `documents` / `chat_sessions`).  All three cleanup sites
now go through `owned_user_ids(db, emails=…)` (exact-email lookup; used for the
step-8 user) and `cleanup_harness_rows(db, user_ids=…)`, so the deletion order
(logs → messages → sessions → chunks → documents → users) and the per-site
`db.commit()` are unchanged while nothing depends on cascade.  The guard still
runs first, and `text` is no longer used anywhere in the file.

Behaviourally verified by `tests/unit/evaluation/test_phase3e_integration_cleanup_scope.py`
(16 tests on the SQLite fixtures): the harness's own rows are removed; a sibling
`phase3e_other_*` user and an unrelated `phase3d_*` user keep their documents,
chunk **ids**, chat rows and logs; a decoy email that merely shares the prefix is
not selected; cleanup twice is harmless and an empty sweep is a no-op; the guard
refuses the application database before any engine exists; the ten-step protocol
and `check()` semantics are unchanged; and no raw `DELETE` remains (AST-checked).

**Not fixed here, and why:** the per-run emails are random, so an interrupted run
leaks its rows and no *safe* pre-run sweep exists — a `phase3e_%`-prefix sweep
would delete a concurrent run's live data.  Giving the harness a deterministic
identity plus a single-run policy is a design decision, recorded as a follow-up.

### Phase 3E validation gate — scoped cleanup (Step 1.0, 2026-10-09)

`experiments/run_phase3e_validation.py` ended a run with four raw `DELETE FROM`
statements, the second of which — `DELETE FROM document_chunks` — had **no
predicate at all** and therefore removed every chunk in the target database.
That matters most in this runner: it is the *final validation gate*, the harness
whose output is used as evidence, so it was deleting the evidence base of
anything else sharing its target database.  Its two other destructive sites
(step 5's duplicate/stale pair, step 9's isolation-check user) were already
scoped but written as raw SQL with string UUID binds, and step 9 relied on
`ON DELETE CASCADE` for the rows it was responsible for.

The harness creates `validation_<8 hex>@test.local` (owner of every uploaded
document and its chunks) and the temporary `val_other_<8 hex>@test.local`.  All
them now go through `owned_user_ids(db, emails=…)` (exact-email lookup, used for
the step-9 user) and `cleanup_harness_rows(db, user_ids=…)`, with the deletion
order (logs → messages → sessions → chunks → documents → users) and each site's
`db.commit()` unchanged.  Step 5 deliberately keeps the **narrowest** scope —
`document_id IN ([doc_a_id, stale_id])`, chunks before documents — because a
user-scoped delete there would destroy documents the later steps assert on.

The gate's read-only `text("SELECT …")` diagnostics (retrieval probes,
`alembic_version`, `information_schema.columns`) are **not** part of the defect
and were left byte-identical; a test pins their presence so a future "remove all
raw SQL" sweep cannot strip the validation queries.

Behaviourally verified by `tests/unit/evaluation/test_phase3e_validation_cleanup_scope.py`
(17 tests on the SQLite fixtures): the harness's own rows are removed; a sibling
`phase3e_*` user and an unrelated `phase3d_*` user keep their documents, chunk
**ids**, chat rows and logs; a decoy email that merely shares the prefix is not
selected; cleanup twice is harmless and an empty sweep is a no-op; the guard
refuses the application database before any engine exists; the eleven-step gate
and `check()` semantics are unchanged; and no raw destructive SQL remains
(AST-checked, f-strings included).

**Evidence boundary:** the user-scoped cleanup is proven behaviourally on
SQLite; the step-5 document-scoped cleanup is pinned by source/AST assertions
only (it is inline in `main()`, which cannot run without PostgreSQL).

### Phase 3F evaluation runner — scoped cleanup (Step 1.1, 2026-10-09)

`experiments/run_phase3f_evaluation.py` bracketed a run with **ten** raw
`DELETE FROM` statements in two blocks.  Eight had **no predicate at all** —
`reliability_logs`, `chat_messages`, `chat_sessions`, `document_chunks` and
`documents` before the ingest, then `reliability_logs`, `document_chunks` and
`documents` after the report — so pointing this runner at a shared isolated
database wiped every row of those tables (and, for chunks, their embeddings)
before the run even started.  The other two matched users by the `phase3f_%`
email prefix.

This harness is the one legacy runner with **deterministic** identities:
`phase3f_legacy@test.local` (arms A and B) and `phase3f_candidate@test.local`
(arm C), now single-sourced as `HARNESS_LABELS` → `harness_user_email` →
`HARNESS_USER_EMAILS`.  That lets the original "clean previous runs" intent be
kept safely: both blocks now go through `owned_user_ids(db, emails=…)` (exact
addresses, never the prefix) and `cleanup_harness_rows(db, user_ids=…)`, with the
same FK-safe order (logs → messages → sessions → chunks → documents → users) and
the same per-block `db.commit()`.  `text()` is no longer imported: this runner
had no read-only raw SQL, so the file now contains no raw SQL call at all.

Behaviourally verified by `tests/unit/evaluation/test_phase3f_evaluation_cleanup_scope.py`
(18 tests on the SQLite fixtures): the harness's own rows are removed (one user
and both users in one sweep); a sibling `phase3f_upload_*` user and an unrelated
`phase3d_*` user keep their documents, chunk **ids**, chat rows and logs; a decoy
email that merely extends the prefix is not selected; an **empty ownership set is
a no-op** rather than a broad delete; cleanup twice is harmless; the guard refuses
the application database before any engine exists; the protocol markers, arms,
metric keys, report path, CLI and exit code are unchanged; and no raw destructive
SQL remains (AST-checked, f-strings included).

**Concurrency caveat (pre-existing):** the deterministic emails mean two
instances sharing one isolated database share identities, so the pre-run sweep of
the second instance would delete the first's live rows — run one instance at a
time.  Interrupted runs, unlike the Phase 3D/3E harnesses, *are* recoverable here
via that same exact-email sweep.

### Phase 4B evaluation runner — scoped cleanup (Step 1.2, 2026-10-09)

`experiments/run_phase4b_evaluation.py` bracketed a run with **ten** raw
`DELETE FROM` statements in two blocks — the last runner still carrying the
pattern.  Eight had **no predicate at all** (`reliability_logs`, `chat_messages`,
`chat_sessions`, `document_chunks` and `documents` before the ingest, then
`reliability_logs`, `document_chunks` and `documents` after the report), so
pointing it at a shared isolated database wiped every row of those tables — and,
for chunks, their embeddings — before the run even started.  The other two
matched users by the `phase4b_%` email prefix.

Like the Phase 3F harness, this one has **deterministic** identities:
`phase4b_legacy@test.local` (arms A and B) and `phase4b_candidate@test.local`
(arm C), now single-sourced as `HARNESS_LABELS` → `harness_user_email` →
`HARNESS_USER_EMAILS`.  That lets the "clean previous runs" intent be kept
safely: both blocks go through `owned_user_ids(db, emails=…)` (exact addresses,
never the prefix) and `cleanup_harness_rows(db, user_ids=…)`, with the same
FK-safe order (logs → messages → sessions → chunks → documents → users) and the
same per-block `db.commit()`.  `text()` is no longer imported: this runner had no
read-only raw SQL, so the file now contains no raw SQL call at all.

Behaviourally verified by `tests/unit/evaluation/test_phase4b_evaluation_cleanup_scope.py`
(19 tests on the SQLite fixtures): the harness's own rows are removed (one user
and both users in one sweep); a sibling `phase4b_extra_*` user — which the old
prefix *would* have matched — and an unrelated `phase3f_*` user keep their
documents, chunk **ids**, chat rows and logs; an **empty ownership set is a
no-op** rather than a broad delete; cleanup twice is harmless; the guard refuses
the application database before any engine exists; the protocol markers, arms,
metric keys, report path, CLI and exit code are unchanged; and no raw destructive
SQL remains (AST-checked, f-strings included).  `test_legacy_runner_isolation.py`
now pins the no-raw-SQL contract for **all five** legacy runners it tracks; its
per-runner `deletes` counts remain as the pre-remediation audit record.

**Concurrency caveat (pre-existing):** as in Phase 3F, the deterministic emails
mean two instances sharing one isolated database share identities, so the pre-run
sweep of the second instance would delete the first's live rows — run one
instance at a time.  Interrupted runs *are* recoverable here via that same
exact-email sweep.

**Step 0.5 F-1 (second half) — inventory complete, and what that does *not*
mean.**  All six runners that carried raw or unscoped cleanup are now scoped, each
with its own report: `run_phase3d_upload_integration` (Step 0.7),
`run_phase3d_evaluation` (0.8), `run_phase3e_integration` (0.9),
`run_phase3e_validation` (1.0), `run_phase3f_evaluation` (1.1) and
`run_phase4b_evaluation` (1.2).  This is **not** a statement that the evaluation
system is safe: the unscoped-delete class is retired, but F-2 (uninstrumented
runners that target the application database and overwrite fixed historical
reports), F-4 (upload-root leakage), F-5 (manifest source digests) and the rest of
Step 0.5's findings remain open, no runner's behaviour after a successful
connection has been re-demonstrated on PostgreSQL, and
`run_phase3d_upload_integration.py` still removes its two isolation-check users
through one **exact-email-scoped** raw-SQL block (documented in the Step 0.7
section above; model-bound conversion is a recorded follow-up).

`structure_eval.py` and `denominator_sensitivity.py` keep their existing
overwrite behaviour on purpose: their output is a timestamp-free,
byte-reproducible *derived* artifact whose regeneration is pinned by their unit
tests (`write twice → identical bytes`).  Changing that is a separate decision.

## Denominator sensitivity analysis

The production-aligned runner aggregates every metric over all measured
questions, while the earlier runners (`run_phase3d/3f/4b_evaluation.py`) use the
answerable (gold-bearing) population. `denominator_sensitivity.py` quantifies the
difference **without re-running any experiment**: it re-aggregates the frozen
per-question results from `reports/ablation_*.json` / `ablation_heading_*.json`
under the contract-aligned populations and writes a separate
`reports/denominator_sensitivity.{json,md}`. It never modifies the
production-aligned A/B/C/D reports. Output is deterministic and timestamp-free by
default (`--timestamp` opts in).

```bash
cd backend
./venv/Scripts/python.exe evaluation/denominator_sensitivity.py
./venv/Scripts/python.exe evaluation/denominator_sensitivity.py --corpus heading
```

Retrieval and answer metrics rise when the unanswerable questions are excluded
(phase3d A `R@5` 0.7738 → 0.8333, EM 0.5238 → 0.5641; heading A 0.8478 → 0.9750,
EM 0.4783 → 0.5500). The existing all-question figures remain the historical
production-aligned measurement; the contract-aligned values are a sensitivity
view. `factual_grounded` and `path_agreement` are reported `not_applicable`
because no computable alternate population exists in the frozen reports.

## Structure-discriminating corpus (v1)

The production-aligned A–D ablation null result on `phase3d`/`heading` is
explained largely by corpus composition: few questions actually depend on
document structure. `datasets/structure_discriminating_v1.py` is a **new,
separate** corpus built to make the hypothesis falsifiable — table row/cell,
section/heading, page-crossing, multi-hop and structural-distractor questions,
all passed through an explicit anti-leakage / discrimination gate. It does not
modify `phase3d`, `heading`, or any existing report.

```bash
cd backend
./venv/Scripts/python.exe evaluation/datasets/structure_discriminating_v1.py
./venv/Scripts/python.exe evaluation/datasets/structure_discriminating_v1.py --summary
./venv/Scripts/python.exe evaluation/datasets/structure_discriminating_v1.py --json
```

The validator prints `VALID` with the contract counts (72 questions: 64
answerable / 8 unanswerable; 56 structural; 32 `DISCRIMINATING`). Every
document is a real PDF that parses through `documents.parser.parse_pdf` into
`section`/`paragraph`/`table` elements. Only the pre-registered `DISCRIMINATING`
subset forms the primary structure subset; weaker questions are retained as
excluded/reviewed. The dataset audit is
`reports/structure_discriminating_v1_audit.md`. **No ablation has been run on
this corpus yet and no improvement is claimed.**

## Offline structure-aware evaluation (Feature #15)

The A–D runner above measures the **real** pipeline against PostgreSQL/pgvector and the
local QA model. `structure_eval.py` is its complement: a fully **offline, deterministic,
element-level** harness that needs no database, no pgvector, no embeddings and no model,
and that separates retrieval quality from answer quality and grounding.

```bash
cd backend
./venv/Scripts/python.exe evaluation/structure_eval.py            # defaults: top_k=5
./venv/Scripts/python.exe evaluation/structure_eval.py --top-k 3 --output structure_eval_k3
```

It measures four variants over `datasets/structure_eval_corpus.py` (a small, explicitly
**synthetic** structure-labelled fixture with in-section distractors, version
`structure-eval-v2`):

| variant | retrieval |
|---|---|
| `A_semantic_only` | lexical scoring over **chunk** text |
| `B_dual_path_chunk` | chunk scoring interleaved with same-section chunk-graph expansion |
| `C_structure_aware` | element scoring over content + heading path, with section parents |
| `D_fused_dual_path` | chunks + elements fused through `graph.evidence.fuse_evidence` |

Reports (`reports/<name>.json` + `.md`) are machine-readable, path-free and — by default —
timestamp-free, so two runs over the same corpus are **byte-identical**. Every metric is a
mean over the per-question measurements kept in the report; when a metric's population is
empty (for example no question carries gold evidence) it is reported as `null` with a
reason, **never** as `0.0`. The fixture's contract (unique ids, every chunk backs an
element, every gold id exists, answerable questions carry gold and unanswerable ones do
not) is enforced by `structure_eval.validate_corpus` before any metric is produced.

Honest scope: this harness measures the offline **reference lexical baselines**, not the
production pipeline. Its results say nothing about pgvector behaviour or answer quality
under the real QA model — that is exactly what the A–D runner above is for. The extractive
answer step is deliberately simple (longest novel-content span of the best-overlap
sentence), so the answer metrics describe that reference, not the production model.
