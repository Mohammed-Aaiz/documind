# E0 PREREQUISITE STATUS — Phase 4F.6-D (Tasks 13–14)

**Date:** 2026-09-23 · **Supersedes** the §A/§B readiness sections of `E0_READINESS_CHECK.md` (4F.6-C) — blockers **B-2 and B-3 are now RESOLVED**, **B-1 PERSISTS**. This phase performed prerequisite recovery only: **E0 was not executed**.

Evidence bases: `e0_diagnostics/diagnostics/summary.json` (all figures below carry denominators), `decision/E0_SOURCE_PROVENANCE.md`, `decision/E0_CHUNK_MANIFEST.json`, `decision/E0_CORPUS_MANIFEST.json`, `decision/E0_RETRIEVAL_RUN_MANIFEST.json`.

---

## Task 13 — Independent prerequisite classification

| Prerequisite | Status | Evidence (with denominators) |
|---|---|---|
| **SOURCE_PROVENANCE** | **READY_WITH_LIMITATIONS** | 6/6 documents classified `DETERMINISTIC_SOURCE_RECONSTRUCTIBLE` (B) with per-document sha256 recorded; benchmark→document mapping exact for all 6 identities (counts match manifest); answer-level gold evidence present in reconstructed source **140/140**; context-level contiguous source span **86/140**, remaining 54 mapped to specific documented generator constructions (33 header+row pairs, 17 static fragments, 4 section-body concatenations) with **0 unresolved and 0 ambiguous** mappings. *Limitations:* sources are reconstructions (no standalone historical artifact exists); exact context offsets exist for 86/140 only (by construction, not by defect). |
| **CHUNK_CORPUS** | **READY** | Isolated corpus built with the **existing production legacy chunker** (`chunk-v1-legacy-chars-1000-200`; config recorded before execution: `config.py chunker_version="legacy"`, CHUNK_SIZE 1000 / CHUNK_OVERLAP 200, structure-v2 = candidate-not-production): **93 chunks / 6 documents, source offsets resolved 93/93**, per-chunk structure ids attached, gold evidence present in chunks **140/140**, gold fully inside one chunk **140/140**, boundary crossings **0/140**. Production storage/database/chunker untouched. |
| **RETRIEVAL_INSTRUMENTATION** | **BLOCKED** | The existing path (`chat/rag.py::retrieve_chunks` → pgvector SQL) cannot execute locally: Postgres port closed, no postgres tooling, no Docker; isolated corpus is not ingested; a replacement retriever is forbidden by Task 7. Configuration fully recorded for a future authorized run (top_k=5, threshold 0.15, SQL, embedder cached). |
| **RETRIEVAL_TRACES** | **BLOCKED** | **0 of 182** trace records exist; `retrieval_traces.jsonl` deliberately NOT created (would require fabrication); Task 9 validation NOT_APPLICABLE. Precise blocker: `E0_RETRIEVAL_RUN_MANIFEST.json` (B-1a…B-1d). |
| **CONTEXT_ASSEMBLY** | **READY_WITH_LIMITATIONS** | Function-level: `build_qa_context` / `build_context` executed in isolation, **deterministic across repeated runs** (2/2 identical), token budget accounting verified (budget 371 / used 336 of window 384 in probe). Recorded-harness scope: for the recorded F2 predictions the model-input context is the benchmark `context` field itself → deterministically reconstructible (L4 probe passed). *Limitation:* the end-to-end production chain `retrieved chunks → assembly → model input` is **UNRESOLVED at example level** because its input (retrieval) is blocked — `observed_end_to_end: false`. |
| **MODEL_INPUT_RECONSTRUCTION** | **READY** | Exact target config pinned: F2 checkpoint `phase4f_5f/f2/checkpoints/F2/checkpoint_epoch2` (files hashed: model.safetensors `71746317…b164b0`, tokenizer.json `881fa1ca…d09d45`, config.json, tokenizer_config.json); `max_length=384`, `truncation=True`, `padding="max_length"`, decode = argmax span within **max_answer_length=50** (both producer scripts), `n_best` not applicable (argmax chain); production A0 scope recorded separately (100 / 20 via `inference_config.json`); versions: Python 3.11.0, transformers 5.16.1, tokenizers 0.23.1. Single labelled methodology probe `L4_CAPABILITY_PROBE_SINGLE_EXAMPLE` (1 example, no inference, no aggregates): input length 384, answer token span found, status `MODEL_INPUT_RECONSTRUCTIBLE`. |

> **ANSWER-TEXT DECODER PROVENANCE (2026-09-28).** `MODEL_INPUT_RECONSTRUCTION`
> above concerns the *token span*, which is unaffected: the span, the logits and the
> score are bit-identical before vs after the change, so this row stays **READY**.
> The *answer text*, however, was produced with `tokenizer.decode()`, which re-inserts
> spaces at subword boundaries and corrupted split numeric/date/currency values
> (`142.6 million` -> `142. 6 million`), depressing every recorded EM/F1. The decoder is
> now fixed once in `backend/answer_span.py` (used by `chat/qa_model.py` and all Phase 4F
> runners); the affected E0 artifacts and the measured effect are listed in
> `E0_PREDICTION_PROVENANCE_2026-09-28.md`.

## Task 10 — Context-assembly observability record (exact vocabulary)

- Function-level assembly (`build_qa_context`, `build_context`): **DETERMINISTICALLY_RECONSTRUCTIBLE** (executed, repeated, identical).
- Recorded-harness model-input context (benchmark `context` → tokenizer): **DETERMINISTICALLY_RECONSTRUCTIBLE** (L4 probe).
- Full production chain per example (`retrieved chunks → ordering → assembly → truncation → final model input`): **UNRESOLVED** (blocked upstream at retrieval).
- Nothing was claimed OBSERVABLE that was merely reconstructed.

## Task 11 — max_answer_length discrepancy: RESOLVED BY SCOPING (not by silent choice)

| Value | Scope | Evidence |
|---|---|---|
| **50** | **recorded F2 benchmark predictions** (the diagnostic target) | `run_threshold_experiment.py:36 MAX_ANSWER_LENGTH = 50`, used at decode (`end_logits[best_start:best_start+50]`, producer of `raw_predictions_benchmark.json:303`); `run_f2.py:48,157,373` identical (producer of `f2_benchmark.json:610`) |
| 100 | production A0 serving only | `models/documind-qa/inference_config.json → max_answer_length: 100`, read by `chat/qa_model.py:205` |
| 50 (default) | P1 experiment-family records | `phase4f/experiments/evaluate.py:200 ex.get("max_answer_length", 50)`; `quality_gate.py:615`; `experiments/train.py:55` |

**Resolution:** no conflict once scoped — the recorded F2 predictions were decoded with **50**; 100 belongs to a different component (production A0 inference); 50 in evaluate.py is an unrelated family default. Both values recorded with explicit scopes; neither silently chosen.

---

## Task 14 — Critical E0 gate (all eight conditions)

| # | Condition | Result |
|---|---|---|
| 1 | Six P3 source documents independently reproducible | **MET** — 6/6 class B, deterministic, sha256 recorded, generator literals verified |
| 2 | Benchmark examples map to real source spans | **MET WITH STATED LIMITATION** — 140/140 map to their document and structural element (0 unresolved, 0 ambiguous); contiguous context span for 86/140, documented construction view for 54/140; answer-level presence 140/140. No critical provenance gap. |
| 3 | Isolated chunk corpus exists | **MET** — 93 chunks, offsets 93/93, config recorded pre-execution |
| 4 | Actual retrieval traces exist | **NOT MET — BLOCKED** (0/182 traces; precise blocker in `E0_RETRIEVAL_RUN_MANIFEST.json`) |
| 5 | Retrieval configuration recorded | **MET** — top_k 5, threshold 0.15, SQL, engine, embedder (+ cached model) |
| 6 | Context assembly observable or deterministically reconstructible | **MET WITH STATED LIMITATION** — deterministic at function level and for the recorded-harness scope; end-to-end unresolved pending condition 4 |
| 7 | Exact tokenizer/model-input configuration pinned | **MET** — paths + hashes + parameters + versions + single capability probe (§Task 11) |
| 8 | No benchmark or production artifact modified | **MET** — hashes re-verified unchanged (benchmark `1166bf4f…`, dataset `a5175303…`, model `cb9f1dde…`); `git status` shows only untracked documentation directories |

**Gate decision: condition 4 fails → E0 does NOT pass the gate. Do not execute E0.**

### Exact gap preventing E0 execution
1. **A retrieval execution environment**: a running PostgreSQL+pgvector instance available to this project (none exists on this machine: port closed, no postgres tooling, no Docker) — provisioned with explicit authorization, non-production scope.
2. **Authorization to ingest** the already-built isolated 6-document corpus through the existing embedding path (`embeddings/model.py`, model cached) so the *actual* retrieval path can run.
3. **The resulting artifact**: `e0_diagnostics/retrieval_traces.jsonl` with 182 real records (top_k=5, real cosine scores, corpus membership), which then passes the Task 9 validation.

No substitute for these was invented. B-2 (chunk corpus) and B-3 (source provenance) — the other two 4F.6-C blockers — are closed by this phase.

---

## Task 15 — Scientific boundary

This phase determined only **whether the evidence required to measure failure stages can be collected**. It does **not** establish that retrieval is the bottleneck, that representation is the bottleneck, or that extraction is the bottleneck; it does not prove H-A, H-B2, or H-C; it does not favor structured workflows, grounded generation, or hybrid routing; it converts no architectural plausibility into empirical proof. The provenance/chunk counts above are chain-integrity measurements, not stage-attribution results — stage decomposition remains exclusively E0's job, still unexecuted.

## Files produced this phase

**Created (required five):** `decision/E0_SOURCE_PROVENANCE.md` · `decision/E0_CORPUS_MANIFEST.json` · `decision/E0_CHUNK_MANIFEST.json` · `decision/E0_RETRIEVAL_RUN_MANIFEST.json` · `decision/E0_PREREQUISITE_STATUS.md` (this file).
**Updated (FIRST TASK + records):** `decision/PHASE4F6C_RECONCILIATION.md` (4F.6-D A-2 addendum) · `decision/DECISION_SAFETY_CHECK.json` (a2_stale_value_check, B-2/B-3 resolution sync, 4F.6-D status field).
**Diagnostic artifacts (isolated):** `e0_diagnostics/source_corpus/` (6), `e0_diagnostics/chunks/` (6 jsonl, 93 chunks), `e0_diagnostics/diagnostics/{provenance_results.jsonl, chunk_evidence_results.jsonl, summary.json}`, `e0_diagnostics/tools/build_e0_prereqs.py`.
**Not created:** `retrieval_traces.jsonl` (blocked, fabrication-free).
**Untouched:** benchmark, datasets, model weights, production code/storage/database, all historical Phase 4F artifacts, research ledger, previous decision documents' figures (except the two records named above).

---

# `FINAL STATUS: E0_PREREQUISITES_BLOCKED`

```
GITHUB ACCESSED: NO
NETWORK ACCESSED: NO
TRAINING RUN: NO
INFERENCE RUN: NO
E0 EXECUTED: NO
RETRIEVAL RUN: NO — 0 TRACES, NONE FABRICATED
PRODUCTION MODIFIED: NO
DATABASE ALTERED: NO
FROZEN DATASET MODIFIED: NO
BENCHMARK MODIFIED: NO
HISTORICAL ARTIFACT MODIFIED: NO
A-2 STALE VALUES: CORRECTED-RECORDED (zero stale figures existed in artifacts — see PHASE4F6C_RECONCILIATION.md 4F.6-D addendum)
COMMIT: NO
PUSH: NO
```
