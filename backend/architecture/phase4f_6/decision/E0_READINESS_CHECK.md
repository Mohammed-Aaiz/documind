# DocuMind — E0 Readiness Check (Phase 4F.6-C)

**Scope of this check:** evaluate the §13 stop/go criteria of `E0_PROTOCOL.md` against the **local filesystem record only** (searches run 2026-09-23). Missing provenance is identified, never substituted.

# `FINAL STATUS: E0_PROTOCOL_BLOCKED`

Three §13 stop conditions are triggered by precisely identifiable missing local artifacts (§B). The protocol design itself is complete; **execution must not begin** until the blockers are resolved or the scope is explicitly amended.

---

## A. Stop/go checklist (§13 criteria)

| # | §13 criterion | Verdict | Evidence |
|---|---|---|---|
| S-1 | Provenance can be resolved reliably | **NOT READY (partial)** | Benchmark→source-dataset chain verified: `benchmark_manifest.json.source_dataset_hash` = `a517530354fc9bcaeef6f1aa16c3fb9ce92f1967668386bc66781e6e6bbf2e97` **recomputed and matches** `backend/phase4f/dataset/training_data_v3_1.jsonl`; gold-span validation 182/182 and token-span validation 182/182 recorded at build time (`gold_span_validation.json`). **But document-level provenance is unresolved:** no standalone source-document artifact exists for any of the 6 holdout document_ids (§B-3), so L0/L2 cannot be verified against anything independent of the benchmark's own context field (which the protocol labels `BENCHMARK_INTERNAL`, not independent verification) |
| S-2 | Benchmark examples can be mapped to source artifacts | **NOT READY (partial)** | Mapping mechanism verified: `build_benchmark.py` builds exclusively from the hash-verified source dataset; every benchmark example carries `document_id` + `context` + offsets present in that dataset record. Per-example-ID membership check = execution-time verification item. **Fails at document granularity:** the *documents themselves* (`company_history_eta`, `financial_report_q3`, `api_docs_lambda`, `dataset_desc_mu`, `legal_contract_epsilon`, `unanswerable_corpus`) have no source artifact to map onto (§B-3) |
| S-3 | Retrieval traces are missing | **NOT READY — triggered** | **B-1.** No retrieval trace exists anywhere for P3. Evidence of absence: (a) the recorded harness has **no retrieval stage** — `run_experiment.py`, `run_f2.py`, `run_h1.py`, `run_threshold_experiment.py` all encode `tokenizer(question, ex["context"], max_length=384, truncation=True)` directly from the benchmark record; (b) repository searches for retrieval-trace / ranked-chunk / recall artifacts returned **0 matches**; (c) no artifact carries per-example `rank` fields for any P3 example |
| S-4 | Context construction cannot be reconstructed | **NOT READY (corpus level) — triggered** | **B-2.** No stored-chunk corpus exists for the 6 holdout documents: glob `**/chunks*.json*` → 0 files; `company_history_eta`/`financial_report_q3` references exist only in dataset/benchmark/derived/manifest files, never in `backend/documents`, `backend/storage`, or `backend/embeddings`; the chunking configuration exists only as unexercised production code (`chunker_version: "legacy"` = 1000-char/200-overlap per `config.py`; `structure-v2` candidate in `documents/chunking.py`). Tokenization-level construction (context→384-token input) **is** reconstructible and is measured at L4 |
| S-5 | Model-input evidence can be inspected | **READY** | Deterministic reconstruction available: `backend/models/documind-qa/tokenizer.json` + recorded params (`max_length=384, truncation=True, padding="max_length"` in every harness) + per-example `context`; predicted token indices `predicted_start_idx`/`predicted_end_idx` are **observed** for all 182 in `raw_predictions_benchmark.json`; fast-tokenizer offset mapping gives gold char→token spans; `token_span_validation` 182/182. Caveat R-6 (§B): the exact tokenizer artifact of the recorded run must be pinned by hash at execution, and reconstructions are labeled `RECONSTRUCTED`, never `OBSERVED` |
| S-6 | Normalization rules remain ambiguous | **READY** | `NORM-v1` fixes all rule classes before measuring (`E0_PROTOCOL.md` §4): locale pinned `en-US` (decimal comma → `manual_review`, never silent), digit-tokenized forms (`20. 3`) reassembled by explicit regex, currency/percent/suffix rules enumerated, unit/scale conversions and rounding **forbidden**, materially different values never merged, table/list/section dialects handled per category, multi-chunk split-span rule defined, ambiguity (`match_occurrences > 1`) reported rather than resolved silently |

**Rule applied:** any single NOT READY → not ready overall. Three are triggered → `E0_PROTOCOL_BLOCKED`.

---

## B. Precise missing local artifact(s) — no substitutes invented

### B-1 — Retrieval traces (blocks Stage A; blocks §8 `document_retrieval_recall`, `evidence_retrieval_recall`, `P(retrieved evidence | correct document)`; blocks true retrieved-context plausibility on the answerability track)
**Required:** for each of the 182 P3 examples, an ordered ranked list `[rank, chunk_id, document_id, contains_evidence]` produced by a declared retrieval configuration (production default: `top_k = 5`, recorded from `chat/rag.py` / `embeddings/routes.py` / evaluation harness) over an ingested representation of the 6 holdout documents.
**Why absent:** the recorded P3 pipeline never performed retrieval — model input came from the benchmark gold `context` field directly (harness source cited in S-3). No artifact in the repository contains per-example retrieval rankings for P3.
**Not substituted by:** `context_plausibility_proxy` (over the supplied context) — labeled PROXY; and Stage A marked `NOT_APPLICABLE_STRUCTURAL` for recorded runs — never "passed".

### B-2 — Stored-chunk corpus for the 6 holdout documents (blocks corpus-level Stage B; blocks stored-level L2 and stored-level representation-preservation rates)
**Required:** chunker output for `company_history_eta`, `financial_report_q3`, `api_docs_lambda`, `dataset_desc_mu`, `legal_contract_epsilon`, `unanswerable_corpus`: `[chunk_id, document_id, char_offsets, element metadata, chunker_version]`.
**Why absent:** glob for chunk artifacts → 0 files; no document/chunk records referencing these document_ids exist in `backend/documents`, `backend/storage`, or `backend/embeddings`; the chunkers (`legacy`, `structure-v2`) were never run on these documents in any recorded artifact.
**Not substituted by:** context-level representation predicates (they measure what the benchmark context carries — labeled `context-level`, never reported as stored-representation results).

### B-3 — Standalone source-document artifacts for the 6 holdout documents (blocks independent L0; blocks document-level provenance in S-1/S-2)
**Required:** full document text per `document_id` as an artifact independent of the benchmark record.
**Why absent:** the documents are **virtual** — `company_history_eta` and siblings appear only inside dataset records (`training_data*.jsonl`), derived splits, quality reports, negative pools, and the benchmark itself (targeted `grep -rln` over `backend/phase4f`, `backend/documents`, `backend/storage`, `backend/embeddings`); no document-file, corpus-file, or ingested-document record exists.
**Partial path, recorded but NOT relied on:** `backend/phase4f/dataset/generator.py` contains a `_build_docs()` hook (annotated "will be populated by `_build_docs()`"). Whether it materializes complete document text is **UNVERIFIED at design time**. If — and only if — execution-time verification confirms it, deterministic reconstruction could be validated by substring-checking every hash-verified benchmark `context` against the reconstructed document; until verified, this is a hypothesis about an artifact, **not an artifact**, and is not counted as readiness. Note: even a confirmed reconstruction would **not** create B-1 (retrieval traces) or B-2 (chunk corpus).

### R-6 — Tokenizer/checkpoint pinning (non-blocking condition of S-5)
The recorded prediction run's tokenizer must be pinned by hash at execution (`raw_predictions` token indices anchor to it). Production tokenizer present (`backend/models/documind-qa/tokenizer.json`); F2/G checkpoint tokenizer location confirmed and hash-recorded at execution before any L4/L5 report is published. Reconstruction ≠ observation in all labels.

---

## C. What is READY (executable subset — still requires execution authorization, not granted this phase)

- L3 supplied-context variant (three-class matching under NORM-v1, ambiguity/manual-review reporting)
- L4 model-input presence via labeled reconstruction; truncation measurement at 384 tokens
- L5 conditional extraction (EM / F1 / scoring-normalizable reclassification) over `raw_predictions_benchmark.json` (182/182 observed predictions with logits, null scores, confidence)
- Stage C representation predicates at **context level** for TABLE_CELL (24), TABLE_ROW (16), LIST_ITEM (20), SECTION_SPECIFIC (16), MULTI_CHUNK (10), NUMERIC (20) — metadata observed in benchmark records
- Stage D extraction failures and the SUCCESS counts; S0 benchmark-integrity quarantine slot
- Answerability track over the 42: ABSTAIN/SPURIOUS under the recorded rule, null-score/margin/confidence distributions, per-reason/subcategory breakdowns, `context_plausibility_proxy`
- Category-level table with `NOT_EXECUTABLE` cells explicitly flagged (never 0% or 100%)
- Precedence matrix over stages B/C/D for the recorded-pipeline variant, with Stage A row recorded `NOT_EXECUTABLE`

Running this subset unchanged would be a **scoped-down E0 (recorded-pipeline variant only)**; the full protocol (with Stage A and corpus-level B) remains blocked. No scope amendment and no execution are authorized by this phase.

---

## D. Evidence discrepancies discovered during the readiness audit (recorded, not corrected — scope permits only the three E0 files this phase)

1. **A0, A1, and A2 results ON P3 exist** (superseding the 4F.6-BR absence statement made before these artifacts were found): `backend/phase4f/phase4f_5d/analysis/a0_benchmark_v1.json`, `a1_benchmark_v1.json`, `a2_benchmark_v1.json`, `benchmark_comparison.json` report on the frozen 182/140/42:
   - **A0·P3:** EM(answerable) 2.1, F1(answerable) 12.0, abstention 27/42 = 64.3%, spurious 15, false abstention 78/140 = 55.7% (protocol definition)
   - **A1·P3:** EM 3.6, F1 21.3, abstention 0/42, spurious 42, false abstention 0
   - **A2·P3:** EM 3.6, F1 19.4, abstention 0/42, spurious 42, false abstention 0
   These are aggregate/per-category/tier results (no per-example raw predictions for A0/A1/A2 were found; only the F2/G pipeline has `raw_predictions_benchmark.json`). Their `spurious_rate` fields use the of-all-182 denominator (8.2 = 15/182; 23.1 = 42/182) while `abstention_rate` uses of-42 — the same denominator inconsistency already documented as R7 in `PHASE4F6B_RECONCILIATION.md`. **Correction pass completed in Phase 4F.6-C-R:** `EXPERIMENT_CONTROL_MATRIX.md` (C0·P3 + C1b-P3), `ARCHITECTURE_MIGRATION_GATE.md` (criterion 8), `NEXT_EXPERIMENT_DECISION.md` (§8.8), the regenerated `DECISION_SAFETY_CHECK.json`, and H-A/H-B rows in `QA_HYPOTHESIS_MATRIX.md` now record these results — see `PHASE4F6C_RECONCILIATION.md`. **E0 status unchanged: BLOCKED** — the P3 aggregates do **not** satisfy blockers B-1 (retrieval traces), B-2 (stored chunk corpus), or B-3 (standalone source documents), and comparability provenance for the P3 pass is itself unrecorded.
2. Known benchmark property carried forward: `exact_question_duplicates: 10` (`benchmark_manifest.json`) — frozen denominators (182/140/42) are unchanged; duplicate-aware interpretation is a reported property, not a re-denominating one.
3. `max_answer_length` differs across records (100 in `inference_config.json` vs 50 in `run_threshold_experiment.py`) — both recorded in the reproducibility block; the recorded run's operative value pinned at execution.

---

## E. Do-not-invent attestation

- No retrieval trace, chunk record, source document, or provenance link was fabricated, approximated, or inferred to satisfy any readiness item.
- `BENCHMARK_INTERNAL` checks are labeled as such and never presented as independent source verification.
- Reconstructions are labeled `RECONSTRUCTED`; observed fields are labeled `OBSERVED`; missing artifacts are `NOT_EXECUTABLE_MISSING_ARTIFACT`.
- The generator-reconstruction path (§B-3) is recorded as UNVERIFIED and counted as absent.

---

## F. Validation performed this phase (§15)

| Check | Result |
|---|---|
| Benchmark byte-for-byte / hash unchanged | `sha256sum qa_benchmark_v1.jsonl` = `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0`, 182 lines, 42 `is_impossible` — unchanged |
| Production artifacts unchanged | No write outside `backend/architecture/phase4f_6/decision/`; model hashes unchanged (`df592aa8…` dir, `cb9f1dde…` file, recomputed earlier this phase) |
| Model artifacts unchanged | No weight/tokenizer file written |
| Frozen dataset unchanged | `training_data_v3_1.jsonl` hash matches manifest (read-only) |
| Historical experiment artifacts unchanged | All Phase 4F reads were read-only; `git status` shows only untracked doc directories |
| Training occurred | **NO** |
| GitHub / network access | **NO** — local reads and local shell only |
| Protocol contains causal or architectural conclusions | **NO** — §0 language constraints; E0 stated as reducing attribution uncertainty / localizing stages only; CAN/CANNOT lists forbid all seven causal/architectural claims |
| Every metric has an explicit denominator | **YES** — `E0_PROTOCOL.md` §8.1/§8.2/§9/§10 and `E0_SCHEMA.json` `metricDictionary` (140, category n, 42, \|L4 PASS\| stated per metric) |
| Answerable / unanswerable analyses not mixed | **YES** — separate `analysis_track`, separate record branch, separate denominators, stage matrix over answerable only |
| Raw exact-string matching not the sole presence method | **YES** — three matching classes (textual NORM-v1 + numeric-equivalent + structural), occurrence/ambiguity handling, digit-reassembly, split-span rule, triple L5 reporting |
| Files created this phase | Exactly: `E0_PROTOCOL.md`, `E0_SCHEMA.json`, `E0_READINESS_CHECK.md` (no execution scripts) |

---

**`FINAL STATUS: E0_PROTOCOL_BLOCKED`**
**Missing artifacts:** B-1 retrieval traces (per-example ranked chunks, declared config) · B-2 stored-chunk corpus for the 6 holdout documents · B-3 standalone source documents for the 6 holdout document_ids (generator path UNVERIFIED, not counted). Plus non-blocking pin R-6 (tokenizer/checkpoint hash at execution).

*Phase 4F.6-C artifact. Readiness assessment only. No execution. No training. No benchmark, dataset, production, model, or historical-artifact change. No network/GitHub access. No commit. No push.*
