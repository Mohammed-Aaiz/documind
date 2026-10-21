# DocuMind — Next Stage: Retrieval + Answer-Path Execution Plan

## 0. Status and authority

| Field | Value |
|---|---|
| Status | **PLANNED — not implemented, not authorized** |
| Kind | Planning / roadmap artifact |
| Owner | COORDINATOR (documentation) — execution delegated per §6 |
| Supersedes | Nothing |
| Related | `TARGET_ARCHITECTURE.md` (Stages 2, 4, 9), `decision/ARCHITECTURE_MIGRATION_GATE.md`, `decision/NEXT_EXPERIMENT_DECISION.md`, `ARCHITECTURE_DECISION_RECORD.md` §7–§9 |

> This document **records a proposed next stage so it can be executed later**. It changes no
> production code, no model, no migration, no benchmark. Per
> `decision/ARCHITECTURE_MIGRATION_GATE.md` §2, implementation may begin only when criteria
> 1–10 are demonstrated or a criterion is explicitly waived in writing with its risk logged in
> the ADR. This plan does **not** open that gate.

The plan originated as a general RAG-improvement proposal (six numbered "fixes"). It is
reproduced here **grounded against the working tree**, because several of the proposal's
premises describe a simpler pipeline than DocuMind actually has. Where the proposal and the
repository disagree, the repository is authoritative and the disagreement is stated explicitly.

---

## 1. What the proposal asked for

Six fixes, in the author's stated order of impact:

1. **Parent-child chunking** — embed small child chunks, return the parent section as context.
2. **Query rewriting / expansion** — search with several paraphrases, merge and deduplicate.
3. **Extractive → generative split** — keep DistilBERT for factual spans, add a generative path
   for conceptual questions.
4. **Small local generative model** — e.g. `google/flan-t5-base` (250 MB), CPU-capable, offline.
5. **Sentence-window retrieval** — return the matched chunk ±1 neighbour.
6. **Answer-type classification** — route factual vs conceptual questions.

The proposal's example failure: *"What is readiness?"* returns the opening of a definition
paragraph instead of the synthesized definition.

---

## 2. Current pipeline — as actually built

This is the real request path today. Every symbol below exists in the working tree.

```text
POST /api/chat/ask
  → backend/chat/routes.py
  → backend/brain/          classify → plan → execute → gate → response
       ├── brain/classifier.py   deterministic keyword Intent classifier
       │                         (DOCUMENT_QUESTION | DOCUMENT_SUMMARY |
       │                          DOCUMENT_SEARCH | MEDIA_VERIFICATION | UNSUPPORTED_REQUEST)
       ├── brain/planner.py      fixed step plan per Intent (no loops)
       ├── brain/executor.py     runs steps; adapters do the work
       └── brain/adapters.py     retrieval_adapter → answer path
             ├── chat/rag.py :: retrieve_dual_path()
             │     ├── retrieve_chunks()            dense pgvector, top-K (default 5)
             │     └── retrieve_structural_candidates()  document-graph traversal
             │     └── fuse_dual_path()             reciprocal-rank fusion (deterministic)
             ├── chat/rag.py :: build_qa_context()  token-budgeted ContextPack
             └── chat/qa_model.py :: answer_question()   local DistilBERT, EXTRACTIVE
  → brain/gate.py           abstention / sufficiency gate
  → brain/response.py       answer + sources + reliability snapshot
```

| Stage | Reality | Source |
|---|---|---|
| Chunking (default) | **legacy, character-based**: 1000 chars / 200 char overlap | `documents/processing.py` (`CHUNK_SIZE`, `CHUNK_OVERLAP`), `config.py chunker_version="legacy"` |
| Chunking (candidate) | **structure-v2, token-based**: target 200 / hard cap 256 / overlap 64 tokens, heading- and page-aware | `documents/chunking.py` (`chunk-v2-structure-tokens`) — selectable, **not** the default |
| Embedding | `all-MiniLM-L6-v2`, 384-dim, real pgvector cosine | `embeddings/model.py`, `chat/rag.py` |
| Retrieval | **already dual-path**: dense pgvector **plus** a document-native structural path (chunk graph `NEXT`/`PREV`/`SAME_PAGE`/`SAME_SECTION`, structure graph `CONTAINS`/`PARENT_OF`/`NEXT`/`REFERENCES`) | `chat/rag.py`, `graph/service.py`, `graph/evidence.py` |
| Context assembly | token-aware, reports which sources it actually contains | `chat/rag.py :: build_qa_context`, `ContextPack` |
| Answering | **single extractive** DistilBERT (`backend/models/documind-qa`, ~66.36M params) | `chat/qa_model.py`, `answer_span.py` |
| Grounding signal | `factual_grounded` = answer span occurs in supplied context | `chat/routes.py`, `reliability/` |

**Consequences for the proposal:** DocuMind is not a flat "embed → top-K → extract" pipeline.
It already has (a) a structure-aware chunker, (b) a structural retrieval path, (c) token-aware
context construction, and (d) a deterministic abstention gate. The proposal's Fixes 1 and 5
are therefore partly *already realised* by different mechanisms than the proposal assumes;
Fixes 2, 3, 4 and 6 are genuinely absent.

---

## 3. Gap analysis — proposal vs repository

### Fix 1 — Parent-child chunking
- **Proposal:** child chunks (~100–150 tokens) embedded for search; parent chunks (~800–1000
  tokens) returned to QA.
- **Reality:** structure-v2 already builds chunks from structure elements with a heading path
  and a token budget, and the structural path returns section parents/descendants on demand.
  But there is **deliberately no persisted chunk → structure mapping** (`README.md` §4): the two
  evidence streams are fused by identity, not by a fabricated correspondence.
- **Gap:** no persisted parent/child relationship; the default production chunker is still legacy.
- **Disposition:** **Adopt as a candidate, but it is a schema change.** It requires (i) enabling
  the structure-v2 chunker in production, (ii) a DATABASE_AGENT migration to persist a
  parent↔child link, and (iii) an ADR entry, because `README.md` §4 currently states the
  opposite design intent. Must clear Gate 1 (retrieval) and Gate 3 (structure) first.

### Fix 2 — Query rewriting / expansion
- **Proposal:** generate 3–4 paraphrases, search all, merge and deduplicate.
- **Reality:** one query string, embedded once; the structural path derives its own terms via
  `graph/service.py :: terms_from_question`.
- **Gap:** none present. Genuinely new.
- **Disposition:** **Adopt**, as a retrieval-side change owned by AI_AGENT, inside
  `TARGET_ARCHITECTURE` Stage 4. Constraint: provenance must record **which query variant**
  found each chunk, and no score may be invented for a variant that did not produce one.
- **Open decision:** template-based expansion (no new model, cheapest, deterministic) vs a
  model-generated rewriter. Start with templates; a model rewriter is a separate proposal.

### Fix 3 — Extractive → generative split
- **Proposal:** keep DistilBERT for factual questions; add a generative path for conceptual
  questions ("What is X", "Explain Y", "Summarize Z").
- **Reality:** The answer-workflow research (`QUESTION_WORKFLOW_MATRIX.md`) already establishes that
  a single extractive engine is the ceiling, and `TARGET_ARCHITECTURE` §7 designs an answer-engine
  router with a `GroundedGenerator` marked **PLANNED**. `brain/classifier.py` classifies *intent*,
  not *question type*; the two are different axes.
- **Gap:** no question-type classifier, no generative route, no router seam implemented.
- **Disposition:** **Adopt in principle** — it converges with the existing target architecture.
  But it is blocked by `decision/NEXT_EXPERIMENT_DECISION.md`: **a hybrid architecture is not
  justified or rejected by current evidence; it is untested.** The router must first be installed
  behaviourally identical to baseline (all routes → existing extractive QA) and measured.

### Fix 4 — Small local generative model (Flan-T5-base)
- **Proposal:** `google/flan-t5-base` (250 MB), CPU, offline, free, no API key.
- **Reality — hard rule conflict.** `DOCUMIND_PROJECT_CONTEXT.md` §15 and §17 require the
  project's own trained QA model and **forbid** substituting an external model; `agents/ai-agent.md`
  states "Use the project's trained DistilBERT QA model. No external fallback." The rules also say
  a change may be made "unless explicitly instructed to change the architecture."
- **Disposition:** **Adopt only as an explicitly approved architecture change**, not a silent
  substitution. The generative path must be **additive** (DistilBERT stays the default extractive
  route), the weights must be **locally operator-provisioned** (no Hub download at request time,
  no external API), and the ADR must record the waiver. Model provisioning follows the existing
  pattern (`backend/models/whisper/small`, `backend/models/media-verification`) and is
  **operator-approved, not agent-installed** (`agents/backend-agent.md`).
- **Not decided here:** Flan-T5-base vs Flan-T5-small vs Phi-2/TinyLlama. Model choice is a
  separate decision requiring an evaluation experiment through the seam.

### Fix 5 — Sentence-window retrieval
- **Proposal:** return matched chunk ±1 neighbour.
- **Reality:** the structural path already reaches `NEXT`/`PREV`/`SAME_SECTION` neighbours and
  section parents/children via `graph/service.py`; but the **semantic** path returns only the
  matched chunks, and `build_qa_context` packs them in token budget order.
- **Gap:** no ±1 window is applied to semantic hits by default.
- **Disposition:** **Adopt — lowest-risk, highest-immediacy change.** Neighbour expansion is a
  bounded, provenance-preserving additive step in `retrieve_dual_path`, and is testable behind the
  existing seam. Respect the token budget: a window must not evict higher-ranked evidence.

### Fix 6 — Answer-type classification
- **Proposal:** `classify_question()` → `factual` | `conceptual`, with keyword patterns.
- **Reality:** `brain/classifier.py` already classifies requests into `Intent`s deterministically
  (keyword rules, honest confidence), and `TARGET_ARCHITECTURE` §6 defines a 15-type question
  taxonomy with a `QuestionClassifier`.
- **Gap:** no question-type classifier distinct from intent; conceptual questions currently fall
  through to extractive QA.
- **Disposition:** **Adopt** as part of Stage 2, but emit an explicit `QuestionType`, keep the
  default route = existing extractive path, and preserve behavioural equivalence until a route has
  its own evidence. Keyword rules alone are acceptable **only** if labelled as a heuristic and
  measured against the benchmark category labels (with the acknowledged limitation that
  category ≠ workflow type).

---

## 4. Corrections to the proposal (truthfulness)

1. **"DistilBERT is extractive" is correct, but the model is not external and not interchangeable.**
   It is DocuMind's own trained model; replacing it is a rule-level change (§3 Fix 4).
2. **"Fixed size → 400 tokens" does not match production.** The default chunker is
   character-based (1000 chars / 200 overlap); the token-based structure-v2 chunker is a *candidate*
   with a 256-token cap, and is not enabled by default.
3. **"Your model only uses ONE chunk" is not accurate.** The semantic path returns top-K chunks
   and the dual path fuses them; the real limitation is that the answer step selects a single
   *span* from one chunk, and context is token-bounded.
4. **"Fewer than 5 distinct measured evaluations" framing:** the answer-quality ceiling and
   category failures are already recorded in `QUESTION_WORKFLOW_MATRIX.md` and
   `PHASE4F6_ARCHITECTURE_AUDIT.md`; this plan does not re-derive them.
5. **The ranked "impact/effort" list is a hypothesis, not evidence.** Estimate order is retained
   below only as a starting sequence, gated by measurement.

---

## 5. Candidate execution order

Ordering follows the migration gate (introduce → measure → enable one route at a time), not the
proposal's effort estimates. All steps are **inert by default** until enabled.

| # | Step | Deliverable | Owner | Prerequisite / gate | Production behaviour change when enabled | Rollback |
|---|---|---|---|---|---|---|
| A | Retrieval recall attribution (E0/Gate 1) | Measured Recall@K on frozen corpus | EVALUATION_AGENT | none | No | n/a |
| B | Sentence-window expansion on semantic hits | Bounded ±1 neighbour assembly in `chat/rag.py` | AI_AGENT | A; seam tests; token budget preserved | Yes (context only) | flag off → baseline |
| C | Query expansion (template-based) | Multi-variant query → merged, deduplicated candidates with per-variant provenance | AI_AGENT | A | Yes (recall) | flag off → baseline |
| D | Question-type classifier + router seam | `QuestionType` emitted; all routes default to existing extractive QA | AI_AGENT | behavioural-equivalence test (gate criterion 8) | **No** (equivalence) | flag off |
| E | Parent-child / structure-linked chunks | Persisted parent↔child link; structure-v2 enabled; child-embed / parent-context retrieval | DATABASE_AGENT (schema) + AI_AGENT (retrieval) | A; Gate 3; ADR entry; `README.md` §4 updated | Yes (retrieval + context) | chunker setting back to `legacy` |
| F | Generative route for conceptual questions | Locally provisioned generator behind the router; grounded output + citations | AI_AGENT (+ BACKEND_AGENT for `requirements.txt`) | D; ADR waiver for §17; E4 evaluation design; Gate 4 (latency) | Yes (new capability) | route disabled → extractive |

> Steps B and C are independent and can run in parallel. Step D is a prerequisite for F only.
> Step E is the largest and the only one requiring a migration.

---

## 6. Ownership map (AGENTS.md)

| File / area | Owner |
|---|---|
| `backend/chat/**` (except `models.py`), `backend/embeddings/**` (except `models.py`), `backend/brain/**`, `backend/graph/**` (except `models.py`), `backend/tokenization.py`, `backend/outcomes.py` | AI_AGENT |
| `backend/documents/**` (except `models.py`), `backend/config.py`, `backend/requirements.txt` | BACKEND_AGENT |
| `backend/migrations/**`, `backend/<feature>/models.py` | DATABASE_AGENT |
| `backend/tests/**`, `backend/pytest.ini` | TEST_AGENT |
| `backend/evaluation/**`, `backend/phases/**` | EVALUATION_AGENT |
| `backend/architecture/**`, `README.md`, `CONTEXT.md`, `AGENTS.md`, `ARCHITECTURE.md` | COORDINATOR |
| Independent verification of any claim above | VERIFIER |

No step in this plan is a single-agent task: each crosses at least one seam and requires the
owning agents to be engaged. **Do not bypass ownership to finish faster.**

---

## 7. Hard constraints (non-negotiable)

1. **No external fallback model and no external LLM API.** Generative capability, if approved,
   runs on **locally provisioned weights** (`local_files_only=True`), like Whisper and the media
   detector. Failure is reported honestly (`503`), never degraded to a substitute.
2. **DistilBERT remains the default extractive path** and the only answer model until the ADR is
   amended. A generative route is additive.
3. **Never fabricate.** No invented confidence, no synthesized score for a path that produced
   none, no query variant credited with a match it did not produce. Reliability values keep a
   real computational origin (`DOCUMIND_PROJECT_CONTEXT.md` §21).
4. **The frozen benchmark is untouched** — 182 examples / 140 answerable / 42 unanswerable,
   hash `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0`. New diagnostic
   populations are labelled separately and never merged into those totals.
5. **Migrations are linear and Alembic-only** (chain ends at `007_add_table_rows`; re-run
   `alembic heads` before acting, since `README.md`/`CONTEXT.md` still cite `006`); no `create_all`; no
   downgrade/reset of a live database.
6. **Do not enable a route without its own measured evidence**, a seam test, a default-path
   regression check, and a documented rollback (`ARCHITECTURE_MIGRATION_GATE.md` §4).
7. **No new dependencies without a need**, and `requirements.txt` is modified only by BACKEND_AGENT
   (`DOCUMIND_PROJECT_CONTEXT.md` §42; `agents/backend-agent.md`).

---

## 8. Acceptance criteria (per step)

Acceptance criteria are stated so they can be **measured**, not asserted. Every metric below must
be produced by a recorded run against the frozen benchmark (or a declared diagnostic population),
not estimated.

| Step | Acceptance criteria |
|---|---|
| A | Recall@K reported for the production pipeline; Gate 1 evaluated (answerable > 70%, unanswerable > 50% at K=10). Result recorded with provenance. |
| B | Neighbour window is bounded by the token budget; no higher-ranked source is evicted; every added source carries the provenance of the neighbour relation; P3 default-path regression = none. |
| C | Each retrieved chunk records the query variant that found it; merge is deterministic and deduplicated by persisted identity; P3 retrieval metrics compared to control. |
| D | Router installed with all routes → existing extractive QA produces **identical** outputs to control on P3 (gate criterion 8); classifier output recorded as a heuristic, not claimed as validated routing ground truth. |
| E | Structure-v2 chunker produces contiguous, deterministic chunks; parent↔child link is persisted and queryable; Gate 3 structure thresholds met; §4 of `README.md` updated to describe the new, real mapping. |
| F | Generator runs locally and offline; every generated answer passes the grounding/provenance/verification checks before reaching the user; latency within the Gate 4 budget; route off restores baseline exactly. |

---

## 9. Validation plan

```bash
# Backend unit/integration suite (SQLite-backed; NOT proof of pgvector/model/E2E)
cd backend && ./venv/Scripts/python.exe -m pytest tests -q

# Migration graph must remain a single, linear head
cd backend && ./venv/Scripts/python.exe -m alembic heads

# Frontend typecheck + production build (from repo root; only if any UI field changes)
npm run build

# Real evaluation (requires PostgreSQL + pgvector + provisioned models)
cd backend && ./venv/Scripts/python.exe -m evaluation...   # harness for the affected step
```

Rules carried from the repository:

- The SQLite suite does **not** exercise pgvector, the real QA model, or the new route. A green
  suite is not an end-to-end pass (`CONTEXT.md` §6).
- Any new reliability/answer field must be produced by the real pipeline and represented honestly
  in the frontend (loading / empty / error / unavailable states).
- New behaviour gets seam tests: unit + integration per `MODULE_SEAMS.md` §8.2.

---

## 10. Open decisions (must be resolved before execution)

1. **Generative model waiver** — does the project explicitly amend `DOCUMIND_PROJECT_CONTEXT.md`
   §15/§17 to permit an additive local generative route? (Coordinator + ADR.)
2. **Model choice** — Flan-T5-base vs Flan-T5-small vs a larger local model; decided by measured
   quality/latency, not by preference.
3. **Query expansion method** — template-based vs model-based rewriter.
4. **Parent-child design** — persist a parent↔child link, or reuse the existing structure graph
   (`CONTAINS`/`PARENT_OF`) as the parent relationship? The second option avoids a new mapping but
   must not fabricate a chunk→element correspondence the repo currently refuses to make.
5. **Step ordering** — should B and C ship before or after A's recall measurement? Measurement
   first reduces ambiguity for every later null result.

---

## 11. Non-goals

- Replacing or retraining the DocuMind QA model.
- Introducing an external LLM API or a hosted generation service.
- Editing the frozen benchmark, model weights, or `.env`.
- Rebuilding completed phases (`DOCUMIND_PROJECT_CONTEXT.md` §46).
- UI work beyond honestly representing any new backend field.

---

## 12. References

- `DOCUMIND_PROJECT_CONTEXT.md` §15, §17, §18, §21, §31, §35–36, §42, §46
- `AGENTS.md` §03–§05, §08
- `agents/ai-agent.md`, `agents/backend-agent.md`, `agents/database-agent.md`, `agents/evaluation-agent.md`, `agents/test-agent.md`
- `backend/architecture/phase4f_6/TARGET_ARCHITECTURE.md` §5.2 (Query Transformation), §6 (Question Understanding), §7 (Answer Engine), §14 (Stages 2/4/9)
- `backend/architecture/phase4f_6/decision/ARCHITECTURE_MIGRATION_GATE.md` §2–§4
- `backend/architecture/phase4f_6/decision/NEXT_EXPERIMENT_DECISION.md` (E0 first; hybrid untested; frozen-benchmark protection)
- `backend/architecture/phase4f_6/ARCHITECTURE_DECISION_RECORD.md` §7–§9, §17
- `backend/architecture/phase4f_6/QUESTION_WORKFLOW_MATRIX.md`
- `README.md` §4, §13, §17; `CONTEXT.md` §4–§6

---

*Next-stage planning artifact. Planning only. No production code, model, migration, benchmark or
dependency changed. No commit. Execution requires the gate in
`decision/ARCHITECTURE_MIGRATION_GATE.md` to open, or an explicit written waiver recorded in the
ADR.*
