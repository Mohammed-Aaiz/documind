# DOCUMIND — INDEPENDENT REVIEW OF THE MULTI-AGENT IMPLEMENTATION PLAN

**Review ID:** DOCUMIND-PLAN-REVIEW-2026-10-14
**Mode:** READ-ONLY, evidence-based review
**Target under review:** `backend/architecture/DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_2026-10-14.md`
**Target integrity at review baseline:** full-file SHA-256 `fb3c7fea88486fa5fbcd9203ebc0c38bace4c1e2b1150b0029f7831ea205d98b`, 69 051 bytes, mtime 2026-10-14 18:04:34
**Predecessor audit:** `backend/architecture/DOCUMIND_EXAM_ANSWER_DIAGRAM_OCR_CAPABILITY_AUDIT_2026-10-14.md` (full-file SHA-256 `d489f912e68acce0a146b2343dcdf71d5397e72de814a1d0330859be65912d0d`)
**Reviewer stance:** independent. The target plan was produced earlier in this programme; this review was conducted to find its defects, not to confirm them.
**Integrity:** the digest is recorded on its own line below and is excluded from its own hash:

Report SHA-256: `f526790511f6720e083fe3ef5690344640538a843b3434db792e957a78579200`

---

## 1. Executive Verdict

**Verdict: APPROVE WITH REQUIRED REVISIONS.**
**Implementation readiness: READY AFTER REVISIONS.**

The plan's **direction is sound and evidence-grounded**: it extends the existing pipeline instead of adding a competing one, it sequences extraction → structure → retrieval → generation → diagrams → frontend correctly, it keeps the extractive model as a grounding layer rather than pretending it can write long answers, it respects the repository's agent ownership in all but one row, and it is unusually honest about what is not implemented. Its §1.2 re-verification claims were independently re-checked and **almost all hold exactly** (§3.3).

Four findings are **HIGH** and must be corrected in the plan **before Phase 1 implementation**, because each would otherwise be discovered mid-phase and force a redesign:

| ID | One-line summary | Blocks |
| --- | --- | --- |
| **REV-001** | Contract C defines a `figure` evidence kind, but the **existing element-retrieval path cannot surface a figure**: seeds match section names only, and elements with empty content are dropped. No figure indexing/ranking mechanism is specified. | Phase 3 (and 5) |
| **REV-002** | The proposed `partial` status **reverses a documented lifecycle invariant** (`documents/routes.py:5-7` "There is no degraded-ready state") without saying so, and the plan does not enumerate the status consumers that must change. | Phase 1 |
| **REV-003** | No **backfill/reprocess policy** for documents already `ready` under the old definition — i.e. rows that are, by the plan's own evidence, silently incomplete. | Phase 1 |
| **REV-004** | Phase 1's "**can ship without a migration**" option is **not viable as written**: no existing column can hold per-page OCR method/confidence/failure. | Phase 1 |

No CRITICAL findings were identified: nothing here makes the direction unsafe or the sequencing wrong, and no finding requires a different architecture. Eight MEDIUM and five LOW findings are listed with corrections in §14–§15.

**Statement classifications used throughout:** `VERIFIED FACT` (observed by this review), `AGENT-REPORTED FACT NOT INDEPENDENTLY VERIFIED`, `INFERENCE`, `RECOMMENDATION`, `BLOCKED VERIFICATION`.

---

## 2. Scope and Authorization Boundary

**In scope:** independent assessment of the target plan's architecture, contracts, sequencing, ownership, security posture, testability and deployment feasibility, against the actual repository.

**Performed:** read-only inspection; `git` state inspection; source reading with line-level citation; `pytest --collect-only` counts (collection only, **no test was executed**); one read-only TCP reachability probe of `127.0.0.1:5432`/`localhost:5432`; SHA-256 hashing of the two report artifacts.

**Not performed (boundary honoured):** the target plan was **not** modified, renamed, moved or overwritten (`VERIFIED FACT`: its SHA-256 is identical before and after this review — §18); no production code, test, configuration, schema, migration, dependency, model file, frontend file or agent contract was written; nothing was installed, downloaded or provisioned; no database was connected to or mutated; no migration or database creation was attempted; no git operation beyond inspection was performed; no phase was started; no disputed architectural decision was silently resolved — every open decision is left with the owner (§16).

**Explicitly not done in this review:** the full test suites were **not** re-executed (a planning-document review does not justify it, per the review contract).

---

## 3. Repository Baseline and Inspected Evidence

### 3.1 Baseline (`VERIFIED FACT`, captured before any analysis)

| Item | Value |
| --- | --- |
| Branch / HEAD | `main` / `6baaa2a0773df66e5fb26814afbe67647fb43435` |
| Staged | **0** |
| Unstaged (tracked) | **330** = **295 deleted + 35 modified** (pre-existing) |
| Untracked files, `backend/` tree (short-status, all) | **718** (includes the audit report and the target plan; repo-wide total at baseline **845**) |
| Review-report destination | **Free** — `architecture/DOCUMIND_MULTI_AGENT_PLAN_REVIEW_2026-10-14.md` did not exist |
| Python | 3.11.0 (`backend/venv`) |

### 3.2 Artifacts inspected

`AGENTS.md`; `agents/{coordinator,backend-agent,database-agent,ai-agent,frontend-agent,test-agent,evaluation-agent,security-agent,verifier}.md`; the target plan (all 13 sections); the predecessor audit; `backend/documents/{processing,parser,structure,tables,routes,models,schemas}.py`; `backend/graph/models.py`; `backend/chat/{routes,rag,qa_model}.py`; `backend/brain/gate.py`; `backend/storage/file_store.py`; `backend/config.py`; `backend/requirements.txt`; `backend/models/documind-qa/inference_config.json`; `backend/.env.example`; `backend/docker-entrypoint.sh`; `backend/Dockerfile`; `compose.yaml`; `Dockerfile.frontend`; `src/types/index.ts`; `src/context/WorkspaceContext.tsx`; `src/lib/api.ts`; `src/pages/WorkspacePage.tsx`; `backend/migrations/versions/*`; `backend/pytest.ini`.

### 3.3 Independent verification of the plan's load-bearing claims

| Plan claim | Method | Result | Classification |
| --- | --- | --- | --- |
| `documents/processing.py:249` skips image blocks | `grep -n` | **line 249 confirmed** | VERIFIED FACT |
| `documents/processing.py:203` `find_tables()` | `grep -n` | **line 203 confirmed** | VERIFIED FACT |
| `chat/routes.py:26-28` `AskRequest{question, topK}`, no marks | `grep -n` | **lines 26/28 confirmed** | VERIFIED FACT |
| `brain/gate.py` thresholds 0.30 / 0.50 | `grep -n` | **lines 57 / 60 confirmed** | VERIFIED FACT |
| `chat/rag.py:643` table-evidence flag; `:669` gate function | `grep -n` | **confirmed**; default OFF (env unset → false) | VERIFIED FACT |
| `chat/rag.py:185` `dc.page` selected | `grep -n` | **confirmed** | VERIFIED FACT |
| `figure` declared in parser + graph vocabulary | `grep -n` | `documents/parser.py:156`, `graph/models.py:117` | VERIFIED FACT |
| Migration head is `007_add_table_rows` | `ls` | **007 is latest** (000–007) | VERIFIED FACT |
| `document.status` has no CHECK constraint ⇒ `partial` needs no DDL | `grep` migrations | **no CHECK/constraint on status found** | VERIFIED FACT |
| Test counts 1368 / 275 / 6 collected | `--collect-only` | **1368 / 275 / 6** | VERIFIED FACT |
| PostgreSQL unreachable | read-only socket probe | `127.0.0.1:5432` and `localhost:5432` → **TimeoutError** | VERIFIED FACT |
| Entrypoint applies migrations then starts uvicorn with 1 worker | read `docker-entrypoint.sh` | `python -m alembic upgrade head` then `--workers 1` | VERIFIED FACT |
| `.env.example` reserves `LLM_API_KEY`/`LLM_MODEL` | read | present, commented, under "LLM (Phase 2)" | VERIFIED FACT |
| Installed runtime (torch/transformers/onnxruntime/…) | `pip list` | matches the plan's inventory | VERIFIED FACT |
| Suite **results** (1345 passed / 274 passed + 1 error / 6 skipped) | not re-executed | **not independently verified in this review** | AGENT-REPORTED FACT NOT INDEPENDENTLY VERIFIED |
| OCR/generation latency, GPU availability, memory ceilings | not measured | **no measurement exists** | BLOCKED VERIFICATION |

**Conclusion for §3:** the plan's factual foundation is accurate. The findings below are about **plan completeness, precision and one viability claim**, not about fabricated evidence.

---

## 4. Assessment of Existing-Component Reuse

The plan classifies reuse in its §2. This review checked the classifications against the code and answers the eight required questions.

### 4.1 Classification check (sample of load-bearing rows)

| Proposed component | Plan class | Review verdict | Evidence |
| --- | --- | --- | --- |
| Per-page text extraction | EXTEND | **Agree** | `documents/processing.py:187-320` already iterates pages and collects per-page state |
| OCR engine | NEW (`documents/ocr.py`) | **Agree** | no OCR code exists (token search + `find_spec`) |
| Table row evidence | REUSE | **Agree** | `documents/tables.py`, `documents/structure.py:180-215`, migration `007` |
| Figure element type | REUSE | **Disagree — understated.** It is EXTEND of two *internal* vocabularies, not pure reuse (REV-007) | `documents/processing.py:39` excludes `figure`; `documents/parser.py:186` + `_public_element_type` raise on unmapped types |
| Figure **retrieval** | EXTEND (`chat/rag.py`) | **Disagree — incomplete.** No mechanism specified that can actually surface a figure (REV-001) | `chat/rag.py:988-1071` seeds on section names only and drops empty-content elements |
| Canonical representation | REUSE + field additions | **Agree in principle, incomplete in detail** (REV-005, REV-006) | `documents/parser.py:ParsedElement`, `documents/structure.py:79` |
| Embeddings / pgvector | REUSE unchanged | **Agree** | `embeddings/model.py:83` (`all-MiniLM-L6-v2`, 384-d), `chat/rag.py:163-205` |
| Evidence gate / abstention | REUSE | **Agree** | `brain/gate.py` |
| Diagram rendering | NEW + approval | **Agree** | no renderer installed |
| Frontend | EXTEND | **Agree** | `src/lib/api.ts`, `src/types/index.ts`, `WorkspacePage.tsx` |

### 4.2 Required questions

1. **Does the plan preserve existing working components?** **Yes** (`INFERENCE`, supported by §4.1): the reuse matrix keeps pgvector, RRF, the evidence gate, the extractive model, the hardened upload path and the storage containment primitives, and lists no replacement for them.
2. **Does it introduce unnecessary duplicate pipelines?** **No.** It explicitly rejects docling *because* it would duplicate PyMuPDF extraction, and rejects a second parser/retrieval path. `VERIFIED FACT` that no second pipeline is proposed in §2/§5.
3. **Are proposed interfaces compatible with the current implementation?** **Mostly yes.** Contracts C–F are additive/nullable, matching the codebase's established "optional field, legacy rows report `None`" pattern. Two exceptions: REV-001 (a new evidence kind without a retrieval mechanism) and REV-014 (the frontend status union is a closed TS union behind a cast).
4. **Are the abstractions justified by actual requirements?** **Yes** (`RECOMMENDATION` to keep as-is): the six contracts map one-to-one onto phases that have verified gaps; no speculative abstraction was found. Contract D's `includeDiagram` is the one field that is not yet justified (REV-011).
5. **Are components being replaced without adequate evidence?** **No replacements are proposed.** The plan changes `ready` semantics and adds a status; it replaces nothing.
6. **Are there missing interfaces between extraction, indexing, retrieval, generation and rendering?** **Yes — one real gap:** extraction → **indexing/ranking** for figures (REV-001). Figure → frontend rendering is specified (Contract E), and OCR → indexing is specified (Contract B), but figure → retrieval is not.
7. **Are responsibilities placed in inappropriate modules?** **One case:** `backend/config.py` is assigned to AI_AGENT (with a "consultation") although it is BACKEND_AGENT-owned (REV-009). Everything else matches the agent contracts.
8. **Does the architecture remain maintainable as document types and capabilities grow?** **Yes, with one caveat** (`INFERENCE`): the element vocabulary + parser boundary is the right extension point, but `ALLOWED_ELEMENT_TYPES` / `ELEMENT_TYPE_MAP` currently require a code change for every new element type, so the plan should state explicitly that new types are added to both (REV-007).

**Excessive abstraction / speculative components:** none found beyond `includeDiagram` (REV-011).

---

## 5. Architecture and Contract Findings

Full finding records are in §14. Assessment per contract:

| Contract | Intended purpose | Integrates with | Gaps found | Approval |
| --- | --- | --- | --- | --- |
| **A — canonical representation** | one representation, extensible | `ParsedElement`, `DocumentStructureElement`, `DocumentChunk` | **REV-006** (no equation row though C-4 creates an equations module); **REV-007** (`figure` requires two vocabulary extensions, understated as reuse); **REV-005** (persistence layer `documents/structure.py` not named) | Partly (schema) |
| **B — OCR result** | OCR text as tagged evidence | `extracted → chunk → embed` chain | invocation threshold deferred (acceptable, but the value must exist before Phase 1 exit); **REV-004** (storage location unspecified and the no-migration claim is unviable); failure/retry semantics present (`method="none"` + reason) — good | Yes (dependency/weights) |
| **C — evidence** | figure/OCR provenance in citations | `SourceChunk`, `SourceOut`, `evidenceKind` closed set | **REV-001** (no indexing/ranking mechanism); asset serving must reuse `storage/file_store.py` containment — correctly required in §9, not in the contract | No |
| **D — answer request/response** | marks + grounding + honest failure | `AskRequest`/`AskResponse`, `api.ts` | additive and backward compatible (**good**); **REV-011** (`includeDiagram` timing); **REV-012** (no fallback if Phase 4 is denied); `topK` validation added — a real, verified correctness improvement (`chat/routes.py:28` has no bounds today) | Yes |
| **E — diagram** | retrieved vs generated, validated, attributed | new renderer + `WorkspacePage` | strong: explicit "never substitute an unrelated image", "never claim source text rendered", validation must fail closed. No gap found | Yes |
| **F — processing status** | honest completeness | `Document.status` (String(20), no CHECK ⇒ no DDL for the value) | **REV-002** (documented invariant reversal + unenumerated consumers); **REV-003** (no backfill policy); **REV-013** (`uploaded` is a column default, never assigned by a route); **REV-014** (frontend union/cast) | Yes |

**Duplicated sources of truth / missing invariants identified:** `ready` (status) vs per-page coverage (insights) must not be able to disagree — Contract F should state that the coverage summary is derived at ingestion and that `ready` is only set when coverage is complete (an invariant, not advice). **`RECOMMENDATION`.**

---

## 6. OCR and Document-Ingestion Assessment

**Current path (`VERIFIED FACT`):** `extract_pdf` (`documents/processing.py:187`) iterates pages; tables first (`:203`), image blocks skipped (`:249`), text via `get_text("dict")` (`:221`) with a `get_text("text")` fallback (`:230`); no OCR call exists anywhere in the module. Runtime module probe and the predecessor audit's execution probe (scanned-only PDF → 0 elements; mixed PDF → page 2 dropped) were re-confirmed in the plan's §1.2 and remain consistent with the source.

**Assessment of the plan's OCR treatment:**

* **Correct:** engine-agnostic adapter; per-page condition rather than file-level; "never send an adequate page through OCR" as a tested negative control; OCR text is evidence with confidence, not truth; failures leave `method="none"` with a reason; recomputed on reprocess like structure/graph data (matches `documents/structure.py` "Atomicity" precedent).
* **Incorrect / incomplete:** the storage of the per-page record (REV-004); the plan's candidate table is honest and correctly flags the Tesseract system-binary precedent, and correctly warns that docling risks a competing parser (**good**).
* **Rotation and low-quality scans:** present in the programme's requirement list and in §10.1's test table, but **absent from Phase 1's acceptance criteria** (REV-017).

**Candidate re-assessment against the required criteria** (this review adds no winner; the plan correctly refuses one):

| Criterion | Tesseract | RapidOCR/ONNX | EasyOCR | PaddleOCR |
| --- | --- | --- | --- | --- |
| Windows dev compatibility | needs separate installer (`INFERENCE`) | pure wheels (**VERIFIED FACT**: `onnxruntime 1.30.0` installed) | wheels + torch (installed) | separate framework |
| Docker compatibility | Dockerfile change required (`VERIFIED FACT`: image has only `libgomp1`) | no image change needed for the runtime (**INFERENCE**) | no image change | heavier image |
| System binary | **required** | none | none | none |
| Offline | yes | yes (after model provisioning) | yes (per-language weights) | yes |
| Confidence reporting | word/line | line | line | line |
| Provenance/precedent risk | **high** — the repo already rejected a system-binary dependency (Whisper/ffmpeg) | low | low | medium |

**`RECOMMENDATION`:** the plan's evaluation-before-selection method is the right call, but it must be strengthened with (a) **explicit acceptance criteria** — per-page character coverage against ground truth, table-cell fidelity, failure reporting, and an offline-capability check — with **numeric thresholds left as owner-approval items** (this review deliberately invents none); and (b) a **measured** Windows + Linux wheel/`find_spec`/import check before any install.

**Can the proposed tests detect silent page loss and broken structure?** **Yes for page loss** (mixed-PDF case + "every page accounted for" + a no-OCR-on-adequate-page negative control), **partially for tables** (existing table tests plus the new fixture), **no for figures/equations** until Phase 2 defines them (see §12).

---

## 7. Answer-Generation and Model Assessment

**Current mechanism (`VERIFIED FACT`):** extractive DistilBERT (`chat/qa_model.py`), `max_input_length 384`, `max_answer_length 100`, `n_best 20` (`models/documind-qa/inference_config.json`); direct inference in the predecessor audit returned a 16-character single-token span for a factual question and score `0.0` for an unsupported one. There is **no prompt template and no generative component anywhere** in the repository.

**Does the plan correctly distinguish the seven required concepts?**

| # | Concept | Plan treatment | Verdict |
| --- | --- | --- | --- |
| 1 | Extractive QA | kept as grounding/verification layer, limits preserved | **Correct** |
| 2 | Retrieval / evidence selection | unchanged pipeline, own context budget for generation | **Correct** |
| 3 | Long-form generation | new adapter, approval-gated, local-first | **Correct direction; unspecified model** |
| 4 | Grounding / citation verification | explicit "no invented facts/citations/equations"; extractive path retained as verifier; `generation.degraded` honesty field | **Correct and notably well-specified** |
| 5 | Mark-aware structure | four modes described by *sections*, not word count; `answerFormat` distinguishes mechanism | **Correct** |
| 6 | Diagram-required detection | separate phase/capability, recorded trigger | **Correct** |
| 7 | Generated vs source figures | Contract E separates origin, requires attribution, forbids substitution | **Correct** |

**Specific assessments requested:**

* **Should marks control structure, depth, or both?** The plan says "depth and structure, never word count" — which is the defensible answer, but it is **not decided**: §12 leaves marks→depth vs marks→retrieval-breadth open. That open question is correctly flagged, and it is genuinely the owner's (`RECOMMENDATION`: decide it before Phase 4, not during).
* **Can marks be added without breaking existing clients?** **Yes** (`VERIFIED FACT` basis): `AskRequest` has no marks field today and Contract D makes it optional with `None` = current behaviour; `topK` gaining bounds is a validation tightening that could reject previously accepted out-of-range values — **worth an explicit note in the contract** (a client sending `topK=0` or `topK=100000` changes behaviour from "accepted" to "422"). `RECOMMENDATION`: state this as an intentional, documented tightening.
* **Is the context budget adequate for long answers?** **Unknown and correctly not assumed.** The plan states the 384-token window cannot hold a 15-mark answer and defers the budget to Contract D. `BLOCKED VERIFICATION`: no measurement of a candidate model's window, memory or latency exists.
* **Could the generator introduce unsupported claims?** **Yes** — this is the plan's principal residual risk and it is addressed with layered controls (evidence-bounded retrieval + extractive grounding layer + abstention + no-score-promise). The plan does not, however, specify **how each answer section is linked to evidence** (Review Area C asks explicitly). `RECOMMENDATION`: require per-section evidence linkage (each section must cite the evidence ids it used) in Contract D — otherwise "grounded" degrades to "plausible".
* **What happens when evidence is insufficient?** The existing gate outcome vocabulary is reused; the plan requires abstention/disclosure. **Correct.**
* **Can a local model meet quality and resource requirements?** **Not established.** The plan marks capacity as a primary input to the decision and does not assume it. `BLOCKED VERIFICATION` (no GPU/capacity measurement was possible; `backend/phases/phase4f_gpu/**` is a forbidden archived venv and cannot be used).
* **Would a hosted model violate project rules?** **Likely yes without an explicit rule change** (`INFERENCE` from `chat/qa_model.py`'s "does NOT fall back to any external pre-trained model" and `AI_AGENT`'s "No external fallback"). The plan says exactly this and routes it to the owner. **Correct.**

**`RECOMMENDATION`:** the plan's "decide after Phases 1–3" sequencing is right, but it must add a **fallback product state** if the model decision is denied (REV-012), otherwise Phases 5–6 stall behind an undecided item.

---

## 8. Retrieval, GraphRAG, and Evidence Assessment

**Existing architecture (`VERIFIED FACT`):** semantic pgvector cosine (`chat/rag.py:163-205`, user-scoped, `embedding_status='ready'` + non-null embedding filters); chunk-level structural candidates via the chunk graph; element-level structural candidates via `parent_id` **seeded by section-name matches only** and expanded by bounded BFS (`chat/rag.py:988-1071`); RRF fusion with explicit provenance (`fuse_dual_path`, `:1075-1146`); query-gated compact table-row band behind `DOCUMIND_TABLE_EVIDENCE`, default OFF (`:643`, `:669-678`); token-budgeted context assembly from the model window (`:323-440`); evidence gate (`brain/gate.py`).

**Is the plan a genuine improvement rather than a rename?** **Yes** (`INFERENCE`, evidence-backed): it adds (a) OCR-derived evidence with an `extractionMethod` tag, (b) a figure evidence kind, (c) validation of `topK`, and (d) figures/captions into the canonical representation. None of these exist today.

**Critical gap:** (b) has no mechanism (REV-001). Concretely, from `chat/rag.py:988-1071`:
* seeds are `find_element_seed_matches` on **section names only** — the docstring states "structure names only; element content is never matched";
* candidates are **dropped** when `content` is empty and `heading_path` is empty;
* images cannot be embedded (the only embedding model is text, 384-d), so no semantic path exists for a figure.

Therefore a question like "explain the architecture diagram" cannot retrieve a figure under the plan as written.

**Missing evaluation cases this review adds (beyond the plan's §10):** questions requiring information **across pages**; across **table cells in different rows**; across a **figure and its caption**; across **two documents**; and a **negative control** where a visually-similar but unrelated figure exists in the corpus (the "do not substitute an unrelated image" rule of Contract E is currently untested by any proposed case). **`RECOMMENDATION`.**

**Duplication of retrieval logic:** none proposed. The plan correctly reuses `fuse_dual_path` and does not add a second ranker.

---

## 9. Agent Ownership and Coordination Assessment

**Ownership conformance (`VERIFIED FACT` against `agents/*.md`):**

| Plan row | Owner | Contract conformance |
| --- | --- | --- |
| C-1, C-3, C-4, C-10, C-12 (documents/, storage/, main.py, requirements.txt) | BACKEND_AGENT | **conforms** |
| C-2, C-5 (models + migrations) | DATABASE_AGENT | **conforms** (`backend/<feature>/models.py`, `backend/migrations/**`) |
| C-6, C-7, C-8, C-9 (chat/, brain/, graph/) | AI_AGENT | **conforms except `backend/config.py`** → **REV-009** |
| C-11 (src/, package.json) | FRONTEND_AGENT | **conforms** |
| C-13 (tests/**) | TEST_AGENT | **conforms** |
| C-14 (evaluation/**) | EVALUATION_AGENT | **conforms** |
| C-15 (agents/backend-agent.md) | COORDINATOR | **conforms** (coordinator owns `agents/**`; the 1.6L precedent shows an ownership amendment requires explicit user approval) |
| C-16 (architecture/**, CONTEXT.md, ARCHITECTURE.md) | COORDINATOR | **conforms** (append-only evidence) |

**Conflicts and gaps:**

* **Multiple writers on one file:** none in practice — `documents/processing.py` (C-1→C-3→C-4) and `chat/routes.py` (C-6/C-7/C-8/C-9) are each single-owner and are stated as sequential. **But the plan's §4 note enumerates only C-6/C-7/C-9 for `chat/routes.py` and omits C-8, which also lists it** — the note must be corrected (LOW, part of REV-009's cleanup).
* **Database changes without the designated owner:** none — C-2/C-5 are DATABASE_AGENT.
* **Frontend before API stabilisation:** correctly avoided (Phase 6 after Phase 4; C-11 depends on C-7).
* **Tests never independently verified:** avoided (VERIFIER is named as reviewer for C-13/C-14).
* **New packages without approved ownership:** correctly flagged (C-10/C-15, approval item 11).
* **Unclear ownership of API contracts:** `AskRequest`/`AskResponse` live in `chat/routes.py` (AI_AGENT) while `DocumentOut`/status live in `documents/schemas.py` (BACKEND_AGENT). Contract F spans both. **`RECOMMENDATION`:** name one contract owner per contract — Contract D → AI_AGENT, Contract F → BACKEND_AGENT — so a status change cannot be made unilaterally in one half.
* **Coordination overhead:** the plan's 10 roles over 9 real agents is proportionate. **`RECOMMENDATION`:** the smallest practical execution groups are **4 writers** (BACKEND_AGENT, DATABASE_AGENT, AI_AGENT, FRONTEND_AGENT) plus **TEST_AGENT** (with EVALUATION_AGENT invoked per evaluation task) and **VERIFIER** as the independent read-only reviewer; SECURITY_AGENT audits and routes remediation.

**Per-phase responsibility (required by Review Area F — responsible agent / files / inputs / outputs / dependencies / reviewer / exit criteria / prohibited actions):**

| Phase | Responsible | Files owned | Inputs | Outputs | Depends on | Reviewer | Exit criteria | Prohibited |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 (1a detection+status, 1b OCR) | BACKEND_AGENT (+DATABASE_AGENT for C-2) | `documents/{processing,routes,schemas,insights,ocr}.py`, `models.py`, migration, `requirements.txt` | audit+plan, engine approval, sample fixtures | per-page status, coverage summary, OCR adapter | §8.1 approval; REV-002/003/004 corrected | VERIFIER; SECURITY_AGENT (untrusted docs) | scanned+mixed PDFs accounted for; no false `ready`; regressions green | no new model download, no schema change without approval, no frontend edit |
| 2 | BACKEND_AGENT + DATABASE_AGENT | `documents/{processing,parser,figures,equations,structure,chunking}.py`, `storage/file_store.py`, `models.py`, migration | Phase 1 output | emitted figures+captions, extraction metadata, equation policy | Phase 1 | VERIFIER; SECURITY_AGENT (asset serving) | figures persisted with page/caption/bbox; existing extraction unchanged | no competing parser; no asset path outside the upload root |
| 3 | AI_AGENT | `chat/{rag,routes}.py`, `brain/adapters.py`, `graph/service.py` | Phase 1+2 | OCR/figure evidence in retrieval, `extractionMethod` provenance | Phases 2; REV-001 fixed | VERIFIER | figure retrieval returns the right document+page; abstention preserved | no new vector store; no fabricated scores |
| 4 | AI_AGENT | `chat/answer_composer.py`, `chat/routes.py`, `brain/adapters.py` (+BACKEND_AGENT for `config.py`) | §8.2 approval; marks policy | mark-aware grounded answers | Phases 1–3; approval | VERIFIER; EVALUATION_AGENT (metrics); SECURITY_AGENT (egress/injection) | four measurably different structures; grounded; abstains | no fabricated facts/citations; no score promise; no external fallback without rule change |
| 5a / 5b | AI_AGENT (detect/retrieve) + BACKEND_AGENT (render) | `brain/{classifier,adapters}.py`, `chat/routes.py`, `diagrams/render.py`, `main.py` | Phase 2+3; §8.3 approval | detection, figure retrieval, validated generation/rendering | Phases 2–3 | SECURITY_AGENT (injection/XSS); VERIFIER | correct figure; safe rendering; failures reported | no unsafe markup; no invented architecture presented as source |
| 6 | FRONTEND_AGENT | `src/**`, `package.json` | Contracts D/E/F stabilised | marks UI, answers, figures/diagrams, warnings | Phase 4 (+5 if diagrams) | VERIFIER | marks reach backend; citations; a11y; build passes | no backend edits; no decorative controls; no unsafe HTML |
| 7 | TEST_AGENT + EVALUATION_AGENT (+SECURITY_AGENT audit) | `tests/**`, `evaluation/**` | all phases | executed evidence, metrics, security findings | all | VERIFIER (independent) | per-capability status with observed evidence; blocked items marked | no production edits to make tests pass; no DB isolation bypass |

---

## 10. Phase Ordering and Implementation Gates

**Ordering verdict: correct** (`INFERENCE`): extraction/OCR precedes structure, structure precedes evidence retrieval, retrieval precedes generation, and diagrams come after figures exist; frontend last; verification last. The plan's prohibition on starting Phase 4 before Phases 1–3 is **the single most important sequencing decision and it is right** — measuring generation quality against a corpus that silently drops scanned pages would produce misleading results.

**Parallelism:** correctly limited to research that changes no production file (the §8 decision records). No unsafe parallel write is proposed.

**Phase-specific findings:**

* **Phase 1 is too broad** (REV-016): it bundles per-page detection, engine integration, status semantics, coverage API and honest failure reporting. The **detection + honest status** half requires **no new dependency and fixes the verified silent-loss defect on its own**; recommend splitting into **1a** (no engine, no install — highest value, lowest risk) and **1b** (engine integration, approval-gated). This also de-risks REV-004 by shrinking 1a to what needs no provenance storage.
* **Phase 2 bundles three different maturity levels** (REV-016/REV-006): figures are specified (Contract A/E), tables already exist, equations are **not represented in any contract**. Recommend 2a (figures+captions, spec-complete) and deferring equations until their representation is decided.
* **Phase 5 is too broad** (REV-016): detection + retrieval + generation + validation + rendering. Recommend **5a** (detect + retrieve existing figures — high user value, no new dependency) and **5b** (generation + rendering, approval-gated).
* **Missing: rollback/failure behaviour and a migration rollback policy** (REV-008). The review contract requires it per phase. Note the deployment coupling: `backend/docker-entrypoint.sh` runs `alembic upgrade head` **before** uvicorn, so a bad migration fails the container at startup — a forward-fix (or explicit authorised downgrade) policy must be pre-agreed, since `AGENTS.md` forbids downgrading a live database without permission.
* **Missing: a gate on existing-data semantics** (REV-003) before any `ready`-definition change ships.

**Does OCR/page-coverage correctness need to precede long-form generation?** **Yes** — the plan already orders it this way and this review agrees without reservation.

---

## 11. Security, Privacy, and Reliability Findings

The plan's §9 is materially better than average: it names data egress, prompt injection, IDOR on the new asset route, traversal, unsafe diagram output, secret handling, document-content logging, provenance manipulation and supply chain, and it distinguishes existing from proposed controls. Existing controls verified in this review (`VERIFIED FACT`): JWT-derived identity for ownership; magic-byte + size + allowlist validation (`documents/routes.py:366-388`); containment + symlink/reparse refusal in `storage/file_store.py:137-214`; the fail-closed evidence gate; `no-new-privileges` and loopback-only API exposure in `compose.yaml`.

**Gaps found:**

* **REV-010 — no rate limiting / inference-cost control.** Review Area H requires it; the plan has none for `/api/chat/ask` (and a hosted generator adds direct cost exposure). Required control: a request-rate limit and a per-request generation budget, enforced in code.
* **REV-010 (second half) — no explicit retry-idempotency statement.** OCR must be as idempotent as structure persistence already is (`documents/structure.py`, "Atomicity": nested savepoint, delete-then-insert). Required: state that a re-ingest replaces, never appends, OCR/derived rows.
* **REV-011 — `includeDiagram` exposure** is a (minor) security/UX-of-honesty issue: a control that cannot be honoured violates the project's own rule against decorative controls.
* **Must be enforced in code, not prompts** (review requirement): all of the following are correctly code-level in the plan — asset authorization, path containment, diagram-source validation, no-`dangerouslySetInnerHTML`, input validation. **`RECOMMENDATION`:** add one more code-level control: **retrieved document text must never be interpolated into a system/instruction position** for the generator (instruction/data separation) — the plan mentions treating text as data but does not require a structural separation in the composer.
* **Residual risk not covered:** OCR text can be attacker-influenced (white-on-white/hidden text). The plan lists this in §9 as "detect and flag anomalous text layers" but proposes no mechanism or phase owner. `RECOMMENDATION`: either assign it to Phase 2 with a concrete detection rule, or explicitly descope it with a recorded decision.
* **No weakening of existing controls is proposed** — **`VERIFIED FACT`** by inspection of the plan: no proposal touches authentication, ownership scoping, or the evaluation isolation guards.

---

## 12. Testing and Evaluation Gaps

**Current state (`VERIFIED FACT` via `--collect-only`):** 1368 unit / 275 integration / 6 e2e collected. Suite **results** are `AGENT-REPORTED FACT NOT INDEPENDENTLY VERIFIED` in this review (not re-executed). Known environment limits (`VERIFIED FACT`): PostgreSQL unreachable (socket timeout), browser E2E requires a live server, and `test_real_e2e_validation` is refused by the project's own disposable-DB guard.

**Coverage assessment against the required list:**

| Area | Covered by plan? | Gap |
| --- | --- | --- |
| Native-text PDF | yes | — |
| Scanned-only / mixed PDF | yes | must assert **no silent loss** and no false `ready` (present) |
| OCR failure / low confidence | yes | add a case where OCR returns garbage (not just failure) |
| **Page-level coverage metric** | partially | the plan tests completeness but does not define the **coverage metric or its threshold**; leave the value as an owner-approval item (no invented numbers) |
| Tables / multi-page tables | partially | **multi-page table** case absent |
| Figures, captions, equations | yes (as cases) | figure case cannot pass until REV-001 is fixed; **unrelated-but-similar figure** negative control absent |
| 6/8/10/15-mark answers | yes | needs a **rubric**, not word counts; see metrics below |
| Unsupported questions / abstention | yes | — |
| Evidence attribution / citation correctness | yes | cross- **page** and cross- **document** cases absent |
| Diagram detection / generation safety | yes | add invalid-markup and remote-fetch payload cases explicitly |
| API compatibility | **missing** | no explicit test that `marks=None` preserves current behaviour and that `topK` bounds return 422 (the tightening of REV-014/D) |
| Frontend rendering | yes | needs the test runner (approval item 12); include the `partial` badge and a11y assertions |
| Authn / tenant isolation | existing | **extend to the new asset route** (IDOR) — required by the review contract |
| Retries / idempotency | **missing** | re-ingest twice ⇒ identical derived rows, no duplicates |
| Resource / latency limits | **missing** | per-page OCR timeout, max pages, max pixels; generation timeout |
| End-to-end | yes | **BLOCKED** without an authorised disposable DB + server |

**Required metrics (separate per area; thresholds are owner-approval items — none invented here):**

| Area | Metric | Measurement method | Threshold |
| --- | --- | --- | --- |
| Extraction | per-page character coverage; OCR CER/WER vs ground truth | fixture suite, per engine candidate | **owner approval** |
| Retrieval | Recall@K, MRR, evidence coverage, path agreement | existing `evaluation/` harness conventions | **owner approval** |
| Generation | rubric-based structural completeness; factual accuracy vs evidence; redundancy rate | rubric scored per mark level | **owner approval** |
| Grounding | unsupported-claim rate; per-section evidence linkage | manual/automated claim→evidence check | **owner approval** |
| Citations | correct document + page rate | known-answer fixtures | **owner approval** |
| Diagrams | detection precision/recall; retrieval correctness; rendering success; unsafe-output rejection | fixture set | **owner approval** |
| Reliability | p50/p95 latency per stage; failure/abstention rates; idempotency violations | instrumentation + test | **owner approval** |

**Can be run safely now:** unit + integration suites (SQLite-backed, self-skipping where DB is needed) — *not re-run by this review*; collection verified. **Blocked:** live E2E, DB-dependent integration, any OCR/LLM measurement (no engine/model, no install authorisation).

---

## 13. Deployment and Resource Feasibility

| Assumption | Review result | Classification |
| --- | --- | --- |
| Backend image is `python:3.11-slim` + `libgomp1` only | **confirmed** in `backend/Dockerfile` | VERIFIED FACT |
| A system-binary OCR engine would require an image change | **confirmed by inference from the Dockerfile** (no OCR packages, no apt OCR packages) | INFERENCE |
| Migrations run at container start; single uvicorn worker | **confirmed**: `docker-entrypoint.sh` → `alembic upgrade head`, then `--workers 1` | VERIFIED FACT |
| Entrypoint refuses to start if required model dirs are missing | **confirmed**: `require_dir` for QA/whisper/media + `exit 1` (`docker-entrypoint.sh:14-31`) | VERIFIED FACT |
| Models mounted read-only; new artifacts must be provisioned, never baked | **confirmed** (`compose.yaml` volumes, Dockerfile comment) | VERIFIED FACT |
| `OMP_NUM_THREADS=2` | **confirmed** in `compose.yaml` | VERIFIED FACT |
| Blocking OCR/LLM work on a single worker can starve the API | **correct and important** — the plan flags it; the concrete mechanism (thread/executor offload while preserving async boundaries) is not specified | INFERENCE + RECOMMENDATION |
| GPU availability | **not established**; `phase4f_gpu/**` is a forbidden archived venv | BLOCKED VERIFICATION |
| Latency/memory of OCR and of local generation | **not measured anywhere** | BLOCKED VERIFICATION |
| Disk | ~81 GB free on the dev host; per-document asset growth unmeasured | VERIFIED FACT (free space) / BLOCKED (growth) |

**Findings:** REV-015 (fail-closed entrypoint interaction with new model provisioning) and REV-008 (migration rollback). **`RECOMMENDATION`:** any new required model artifact must be provisioned and mounted **before** the image that requires it is deployed, or the deploy will fail closed at boot — which is the correct behaviour but must be a planned rollout step, not a surprise.

---

## 14. Findings Ranked by Severity

Classification tags apply to each statement. "Blocks" = must be corrected before the named phase is implemented.

Every finding record below carries, explicitly: **ID · severity · file path and line numbers · observed evidence (classified) · why it matters · required correction · responsible repository agent · whether owner approval is required · whether it blocks implementation**.

### HIGH

**REV-001 — Figure evidence has no workable indexing/ranking path** · Severity: **HIGH** · Blocks: **Phase 3 (and 5)** · Owner approval: no
* **VERIFIED FACT (evidence):** `backend/chat/rag.py:988-1071` — `retrieve_structural_element_candidates` builds seeds from **section-name matches only** (its docstring: "A. seeds — elements whose own section name (`heading_path[-1]`) matches a meaningful question term (structure names only; element content is never matched)"), then bounded BFS over `parent_id`; candidates are **discarded** when content is empty and no heading path exists (`content = info["content"] or (" > ".join(path) if path else "")` … `if not content or not content.strip(): continue`). Images cannot be embedded (the only model is text, 384-d — `backend/embeddings/model.py:18,83`).
* **Plan location:** §5 Contract C (adds a `figure` evidence kind) and §7 Phase 3 / row C-6 (`backend/chat/rag.py`).
* **Why it matters:** Phase 3's acceptance criterion "figure retrieval returns the correct document and page" **cannot be met** by the mechanism as specified; a caption-only figure has neither a semantic path nor a seed path. Discovering this mid-phase forces a redesign of the evidence contract.
* **Required correction:** specify the mechanism in Contract C — e.g. index the caption (plus a stable figure descriptor) as a retrievable unit that carries `figureRef`, add content-aware seeding for figure elements, define figure ranking, and require a non-empty content invariant for figure elements; add the producing files to C-3/C-6.
* **Responsible agent:** AI_AGENT (+BACKEND_AGENT if the caption unit is produced at ingestion).

**REV-002 — `partial` reverses a documented invariant and its consumers are not enumerated** · Severity: **HIGH** · Blocks: **Phase 1** · Owner approval: **yes** (already checklist item 4)
* **VERIFIED FACT (evidence):** `backend/documents/routes.py:1-14` — "READY means actually searchable and complete… **There is no degraded-ready state.**" (lines 5, 7). Status consumers that branch on the value: dedupe/return-existing path (`:398-425`: `error` → reprocess, stale → reprocess, else return existing), `_is_stale_processing` (`:322-330`), reprocess guard (`:681`), `documents/schemas.py` (list/detail/insights), `documents/insights.py`, `src/types/index.ts:8`, `WorkspaceContext.tsx` (`apiDocToFile` cast), `WorkspacePage.tsx` rendering.
* **Plan location:** §5 Contract F and row C-12.
* **Why it matters:** the plan proposes a semantic reversal without saying that it reverses a documented rule, and without listing the consumers — an unenumerated consumer can silently mishandle `partial` (e.g. never reprocess it, or render it as `ready`).
* **Required correction:** state the reversal explicitly, update the module docstring, enumerate every status consumer in C-12, and require one test per consumer.
* **Responsible agent:** BACKEND_AGENT (+DATABASE_AGENT if column work follows).

**REV-003 — No backfill/reprocess policy for existing `ready` documents** · Severity: **HIGH** · Blocks: **Phase 1** · Owner approval: **yes**
* **VERIFIED FACT (evidence):** the predecessor audit's mixed-PDF probe (re-confirmed in the plan's §1.2) shows documents can be `ready` today while pages are unaccounted for; the plan changes the *meaning* of `ready` but says nothing about rows already in that state.
* **Plan location:** §7 Phase 1 acceptance criteria; §5 Contract F.
* **Why it matters:** without a policy the database keeps rows whose status contradicts the new contract — precisely the dishonesty the change exists to remove.
* **Required correction:** define the policy (reprocess-on-next-access, an operator-run reconciliation, or an explicit "coverage unverified" marker for legacy rows) and record that reprocessing existing user documents is a data operation requiring approval.
* **Responsible agent:** COORDINATOR + DATABASE_AGENT + BACKEND_AGENT.

**REV-004 — Phase 1's "no migration" option is not viable as written** · Severity: **HIGH** · Blocks: **Phase 1** · Owner approval: **yes** (checklist item 3)
* **VERIFIED FACT (evidence):** `backend/documents/models.py:22-57` — `documents` has **no JSON column** (id, user_id, name, file_type, file_size, stored_path, content_hash, chunker_version, parser_version, embedding_model, chunk_count, status, embedding_status, created_at, updated_at, processing_started_at). `document_structure_elements` is an **element** table whose uniqueness is `(document_id, sequence_index)` (`backend/graph/models.py:186-200`) and whose rows are one-to-one projections of parser elements (`backend/documents/structure.py:112-140`); a page-level extraction record is not an element.
* **Plan location:** §6 "Schema gate … Phase 1 can ship **without** a migration if per-page OCR provenance is carried in existing structure-element rows".
* **Why it matters:** it creates false confidence that Phase 1 escapes the schema approval gate; the fallback cannot represent per-page method/confidence/failure without violating the element-table contract.
* **Required correction:** either require the additive migration for a per-page extraction record, or define a reduced Phase 1a that reports only document-level completeness and delete the unsupported claim.
* **Responsible agent:** DATABASE_AGENT + BACKEND_AGENT.

### MEDIUM

**REV-005 — Persistence layer missing from the affected-files lists** · Severity: **MEDIUM** · Blocks: **yes, before Phase 2 is specified** · Owner approval: no
* **VERIFIED FACT:** `backend/documents/structure.py:79 replace_document_structure` is the only writer of `document_structure_elements` and `document_table_rows` (called from `documents/routes.py`), and is where element bbox and table rows are projected (`:112-140`, `:180-215`). C-3/C-4/C-5 do not list it.
* **Why it matters:** a new `figure` element (with caption/asset/bbox) cannot be persisted without changing this file; the ownership matrix would send implementers to the wrong place.
* **Required correction:** add `documents/structure.py` to C-3/C-4/C-5, and note `documents/tables.py` as the row-projection precedent.
* **Responsible agent:** COORDINATOR.

**REV-006 — Equations have no representation although a module is created for them** · Severity: **MEDIUM** · Blocks: **yes, before Phase 2 is specified** · Owner approval: **yes** (scope)
* **VERIFIED FACT:** §5 Contract A has no equation row; §4 C-4 creates `backend/documents/equations.py` with "element vocabulary (no new type unless approved)".
* **Why it matters:** an undefined output representation cannot be persisted, cited or tested; it also risks claiming "equation understanding" from surviving text, which the plan itself forbids.
* **Required correction:** define the representation (element type vs attribute of `text_block`; verbatim text only vs region marking) or descope equations with a recorded decision.
* **Responsible agent:** BACKEND_AGENT + COORDINATOR.

**REV-007 — `figure` classified as REUSE understates the change** · Severity: **MEDIUM** · Blocks: no (precision) · Owner approval: no
* **VERIFIED FACT:** `backend/documents/processing.py:39 ALLOWED_ELEMENT_TYPES = frozenset({"paragraph","heading","table","list","text"})` (no `figure`; `ExtractedElement.__post_init__` raises at `:79-82`); `backend/documents/parser.py:186` states every allowed type must be mapped and `_public_element_type` **raises** on an unmapped internal type.
* **Why it matters:** the matrix sends the work to the public type registry only, while the change must also pass the extractor's closed vocabulary and the parser's fail-closed mapping (`documents/parser.py:186`) — an implementer following the plan as written hits a runtime raise (`documents/processing.py:79-82`).
* **Required correction:** restate as EXTEND (extractor vocabulary + parser mapping + new `ExtractedElement` fields for caption/asset/bbox), keeping the public `figure` type as genuine reuse.
* **Responsible agent:** BACKEND_AGENT.

**REV-008 — No per-phase rollback/failure behaviour and no migration rollback policy** · Severity: **MEDIUM** · Blocks: **yes, per-phase entry** · Owner approval: **yes** (downgrade authority)
* **VERIFIED FACT:** §7 phases have Objective/Deliverables/Files/Acceptance/Risks/Complexity/Approval but no failure/rollback item; `backend/docker-entrypoint.sh` applies migrations before uvicorn starts, so a bad migration prevents startup; `AGENTS.md` forbids downgrading a live database without explicit permission.
* **Why it matters:** with no rollback path, a failed Phase 1 leaves a container that cannot start (migrations are applied before uvicorn) and with no agreed authority to reverse the migration.
* **Required correction:** add per-phase rollback/failure behaviour, a forward-fix vs downgrade policy, and name who authorises a downgrade.
* **Responsible agent:** COORDINATOR + DATABASE_AGENT.

**REV-009 — Single-writer ambiguity: `backend/config.py` assigned to AI_AGENT** · Severity: **MEDIUM** · Blocks: no · Owner approval: no
* **VERIFIED FACT:** C-8 lists `backend/config.py` under AI_AGENT with "BACKEND_AGENT consultation"; `agents/backend-agent.md` Owns includes `backend/config.py`. The plan's §4 note also omits C-8 from the list of rows touching `backend/chat/routes.py`.
* **Why it matters:** it violates the plan's own single-writer rule and would let two agents edit `backend/config.py` in the same phase — the exact collision the ownership matrix exists to prevent.
* **Required correction:** reassign the `config.py` edit to BACKEND_AGENT (AI_AGENT requests the field) or split C-8; fix the `chat/routes.py` toucher list.
* **Responsible agent:** COORDINATOR.

**REV-010 — Missing rate limiting / inference-cost control and retry-idempotency statement** · Severity: **MEDIUM** · Blocks: **Phases 4 and 7** · Owner approval: **yes** (limits)
* **INFERENCE (files: plan §9 contains no such control; no rate limiter exists in `backend/chat/routes.py` or `backend/documents/routes.py`; `backend/documents/processing.py` is the retry path):** a generative path adds unbounded per-request cost and denial-of-service exposure; OCR retries need an explicit replace-not-append guarantee (the structure replace already provides exactly this at `backend/documents/structure.py`, "Atomicity").
* **Why it matters:** Review Area H requires both controls; without them one client can exhaust inference capacity, and a retried ingest could double-write derived rows.
* **Required correction:** require a request-rate limit and a generation budget in code, and state the idempotency invariant plus its test.
* **Responsible agent:** BACKEND_AGENT (+AI_AGENT).

**REV-011 — `includeDiagram` would be a decorative control if shipped early** · Severity: **MEDIUM** · Blocks: **Phase 4/6 contract** · Owner approval: **yes** (item 19)
* **INFERENCE (files: plan §5 Contract D, §7 rows C-9/C-10; `src/lib/api.ts`, `src/pages/WorkspacePage.tsx`; rule `agents/frontend-agent.md` "Do not add decorative controls"):** the field could exist before any capability honours it.
* **Why it matters:** a control the backend cannot honour is a decorative control — a project-rule violation, and dishonest to the user.
* **Required correction:** add the field only with the diagram approval, or require the API to ignore-and-report it and the UI not to expose it until then.
* **Responsible agent:** AI_AGENT + FRONTEND_AGENT.

**REV-012 — No product fallback if the generation-model decision is denied** · Severity: **MEDIUM** · Blocks: **Phases 5–6 planning** · Owner approval: **yes** (items 7–8 decision)
* **INFERENCE (files: plan §13 items 7–8, §7 Phase 4 and Phase 6, row C-11; no alternate product state appears anywhere in the plan):** §13 items 7–8 gate Phase 4, and C-11 (marks UI) depends on C-7.
* **Why it matters:** a denied Phase 4 approval would leave Phases 5–6 with no defined product state, blocking work that does not itself depend on generation.
* **Required correction:** state the fallback (e.g. extractive + retrieval breadth with marks explicitly out of scope, or a documented "not available" state) so later phases are not blocked behind a denied decision.
* **Responsible agent:** COORDINATOR.

### LOW

**REV-013 — `uploaded` is a column default never assigned by a route** · Severity: **LOW** · Blocks: no · Owner approval: no
* **VERIFIED FACT:** `documents/models.py:42` default `"uploaded"`; migration `000_create_base_tables.py:160` `server_default="uploaded"`; the only assignments elsewhere are in tests. The upload route sets `processing` before the row is visible.
* **Why it matters:** Contract F enumerates statuses as if all were reachable; a reader may add retry/recovery handling for a state the API never produces.
* **Required correction:** Contract F should say `uploaded` is the column default and effectively unreachable through the API.
* **Responsible agent:** BACKEND_AGENT.

**REV-014 — Frontend status union mismatch and an unchecked cast** · Severity: **LOW** · Blocks: no · Owner approval: no
* **VERIFIED FACT:** `src/types/index.ts:8` — `status: 'uploading' | 'processing' | 'ready' | 'error'`; `'uploading'` is set only client-side (`src/context/WorkspaceContext.tsx:142`); `'partial'` is absent; `apiDocToFile` maps with `as DocumentFile['status']`, so an unrecognised status passes TypeScript silently.
* **Why it matters:** TypeScript cannot catch an unhandled status through the cast, so a `partial` document falls through to whatever the remaining branch renders — the silent misrepresentation Contract F exists to prevent.
* **Required correction:** enumerate the union and every status branch in C-11, and assert the `partial` rendering in a test.
* **Responsible agent:** FRONTEND_AGENT.

**REV-015 — New model provisioning meets a fail-closed entrypoint** · Severity: **LOW** · Blocks: no (but it is a required deployment step) · Owner approval: **yes** (deployment change)
* **VERIFIED FACT:** `backend/docker-entrypoint.sh:14-31` `require_dir` for QA/whisper/media and `exit 1` when a directory is missing.
* **Why it matters:** the fail-closed check is correct behaviour, but an image that requires an unmounted artifact will not start — an ordering mistake becomes an outage rather than a degraded feature.
* **Required correction:** state the rollout order (provision → mount → deploy) and whether a new model is required or optional-with-degradation.
* **Responsible agent:** BACKEND_AGENT + COORDINATOR.

**REV-016 — Phase breadth (1 and 5)** · Severity: **LOW** (planning quality) · Blocks: no · Owner approval: no
* **Why it matters:** a wide phase cannot be accepted or rejected as a unit, so an approval decision on one dependency inside it blocks work that does not need it.
* **RECOMMENDATION:** split Phase 1 into **1a** (detection + honest status + coverage, no new dependency) and **1b** (engine integration); split Phase 5 into **5a** (detect + retrieve existing figures) and **5b** (generate + render). This also isolates the highest-value/lowest-risk fix and reduces the blast radius of a denied approval.
* **Responsible agent:** COORDINATOR.

**REV-017 — Rotation/low-quality scans absent from Phase 1 acceptance criteria** · Severity: **LOW** · Blocks: **yes, Phase 1 acceptance criteria** · Owner approval: **yes** (to descope)
* **VERIFIED FACT:** the programme lists rotation and §10.1 includes a rotated-page test, but Phase 1's acceptance criteria omit it.
* **Why it matters:** rotation is the failure mode most likely to make a page look "scanned but empty"; if it is neither tested nor explicitly descoped, Phase 1 could pass its criteria while still losing rotated pages silently.
* **Required correction:** add rotation to the criteria or descope it explicitly with a decision.
* **Responsible agent:** BACKEND_AGENT.

### INFORMATIONAL

**REV-018 — Ownership mapping is otherwise sound; minimal execution groups** · Severity: **INFORMATIONAL** · Blocks: no · Owner approval: not applicable
* **VERIFIED FACT:** the phase→agent mapping conforms to `agents/*.md` in all rows except REV-009; there are no cross-agent file collisions. **RECOMMENDATION:** 4 writers + TEST/EVAL + VERIFIER as in §9.
* **Why it matters:** it shows the plan's coordination design is implementable under the existing agent contracts, so the findings above are refinements rather than a re-architecture.
* **Responsible agent:** COORDINATOR.

**REV-019 — The plan's evidence base is accurate** · Severity: **INFORMATIONAL** · Blocks: no · Owner approval: not applicable
* **VERIFIED FACT:** §1.2's re-verification table, all cited line numbers, the dependency inventory, migration head `007`, the `partial`-needs-no-DDL claim, the unreachable-PostgreSQL claim, the entrypoint/worker claims and the test-collection counts all check out (§3.3). No fabricated evidence was found in the plan.
* **Why it matters:** it separates plan defects (the findings above) from plan credibility — the plan can be corrected rather than re-derived, which is what makes APPROVE WITH REQUIRED REVISIONS the right verdict.
* **Required correction:** none — informational; no action required.
* **Responsible agent:** none — VERIFIER if these claims are re-checked on the next plan revision.

**Severity totals: 0 CRITICAL · 4 HIGH · 8 MEDIUM · 5 LOW · 2 INFORMATIONAL.**

---

## 15. Required Revisions to the Original Plan

The target plan **must not be edited by this review**; the coordinator should apply these revisions in a follow-up edit.

**Must be applied before Phase 1 implementation (blocking):**

1. **REV-004** — remove or correct the "Phase 1 can ship without a migration" claim; state the per-page provenance storage decision explicitly (additive migration vs reduced 1a scope).
2. **REV-002** — declare the `ready`/`partial` invariant reversal, update the `documents/routes.py` docstring in the change list, and add the full status-consumer checklist to C-12 with a test per consumer.
3. **REV-003** — add a backfill/reprocess policy for existing `ready` documents, with its approval noted.
4. **REV-005** — add `backend/documents/structure.py` (and note `documents/tables.py`) to C-3/C-4/C-5.
5. **REV-009** — reassign the `backend/config.py` edit to BACKEND_AGENT and correct the `chat/routes.py` toucher list.
6. **REV-008** — add per-phase rollback/failure behaviour and a migration forward-fix/downgrade policy.
7. **REV-013/REV-014** — correct the status tables/unions in Contract F and C-11.

**Must be applied before Phase 3 (blocking):**

8. **REV-001** — specify the figure indexing/ranking mechanism in Contract C and extend C-3/C-6 accordingly.

**Must be applied before Phase 2 (specification-complete):**

9. **REV-006** — define or descope the equation representation.
10. **REV-007** — restate the `figure` change as EXTEND in Contract A/§2.
11. **REV-017** — add rotation to Phase 1 acceptance criteria or descope it.

**Recommended before Phases 4–7 (non-blocking but should be recorded):**

12. **REV-010** — add rate limiting, a generation budget, and the retry-idempotency invariant.
13. **REV-011** — gate `includeDiagram` on the diagram approval.
14. **REV-012** — add the fallback product state if the generation decision is denied.
15. **REV-016** — split Phases 1 and 5 as described.
16. Document-level additions: per-section evidence linkage for generated answers; cross-page/cross-document/cross-table evaluation cases; the unrelated-but-similar-figure negative control; API-compatibility, idempotency and resource-limit tests; and one named contract owner per contract.

---

## 16. Approval Decisions That Remain with the Owner

The plan's 16-item checklist is retained and endorsed as the right gate list. This review **adds three items** and confirms that none of the following may be decided by an agent:

| # | Decision | Source | Blocking |
| --- | --- | --- | --- |
| 1–16 | As listed in the plan's §13 (Phase 1 scope; OCR engine + install + provisioning; schema change; `partial` contract; figure/equation scope; retrieval extensions; generation model + egress; marks contract; diagram scope; renderer + dependency; new package ownership; frontend test runner; deployment changes; disposable DB for E2E; image uploads; data-egress posture) | plan §13 | respective phases |
| **17** | **Backfill/reprocess policy for existing `ready` documents** (REV-003) | this review | Phase 1 |
| **18** | **Equation representation, or explicit descope** (REV-006) | this review | Phase 2 |
| **19** | **Whether the `includeDiagram` field may ship before the capability exists** (REV-011) | this review | Phase 4/6 |
| **20** | **Migration downgrade authority** (who may authorise one, and under what evidence) (REV-008) | this review | Phase 1 |
| **21** | **Metric thresholds** — every metric in §12 (extraction coverage, CER/WER, retrieval, rubric completeness, unsupported-claim rate, citation correctness, diagram safety, latency) has **no defensible baseline today**; each threshold is an owner-approval item | this review | Phase 7 |

---

## 17. Recommended Next Action

**`RECOMMENDATION` (single next step):** the coordinator applies the **blocking revisions of §15** (REV-001 to REV-009, plus REV-013/REV-014/REV-017 where they touch a phase that is about to start) as a **plan-only edit** to the same document, then re-requests independent verification of the revised plan. No implementation should begin until:

1. the four HIGH findings are corrected in the plan text, and
2. the owner approves **approval items 1, 2, 3, 4, 17, 20** (Phase 1 scope; OCR engine and its provisioning; the schema decision; the `partial` contract; the backfill policy; downgrade authority),

because those six together determine whether Phase 1 can be implemented honestly at all. If the owner prefers the lowest-risk first step, **Phase 1a** (per-page detection + honest status + coverage summary, **no new dependency**) is the recommended entry point — it removes the verified silent-page-loss defect without pre-committing to an OCR engine or a schema change.

**This review recommends no implementation now.** Per the review contract, it stops here.

---

## 18. Validation and Repository-Integrity Report

### 18.1 Review-report validation

| Check | Result |
| --- | --- |
| Report exists at the recorded path | **VERIFIED FACT** — `backend/architecture/DOCUMIND_MULTI_AGENT_PLAN_REVIEW_2026-10-14.md` (path was confirmed free before writing; nothing overwritten) |
| All 18 required sections present and ordered | **VERIFIED FACT** — checked by heading scan |
| Placeholders / accidental non-English text / unsupported claims | **VERIFIED FACT** — checked by `grep` for `PLACEHOLDER` and for non-ASCII outside the intended typographic set; no stray characters; labels applied to every substantive statement |
| SHA-256 recorded and verified after the final edit | **VERIFIED FACT** — recorded in the header; computed over the file with the digest line excluded (`grep -v '^Report SHA-256' <file> \| sha256sum`), because the digest line is the only self-referential content |
| Internal consistency of recommendations | **VERIFIED FACT** — no recommendation contradicts another; the two "do not change" statements (no implementation, no plan edit) are consistent with every finding |

### 18.2 Target-artifact integrity

| Check | Result |
| --- | --- |
| Target plan unchanged by this review | **VERIFIED FACT** — full-file SHA-256 `fb3c7fea88486fa5fbcd9203ebc0c38bace4c1e2b1150b0029f7831ea205d98b` identical before and after (69 051 bytes) |
| Predecessor audit unchanged | **VERIFIED FACT** — `d489f912e68acce0a146b2343dcdf71d5397e72de814a1d0330859be65912d0d` (hash taken during review; not re-written) |

### 18.3 Working-tree integrity

| Item | Before review | After review |
| --- | --- | --- |
| Branch / HEAD | `main` / `6baaa2a0773df66e5fb26814afbe67647fb43435` | **identical** |
| Staged | 0 | **0** |
| Unstaged (tracked) | 330 (295 deleted + 35 modified) | **330** — identical composition |
| Untracked files, `backend/` tree | 718 | **719** (+1 = this review report — the only change; repo-wide 845 → 846) |
| Bytecode/editor side-effects | — | **none**: no file under the source/test trees has an mtime after this review began, and no new `.pyc` exists (the collection-only `pytest` run reused valid caches); `__pycache__/` is git-ignored by `.gitignore:2` |

* **Method note:** untracked counts are taken with `git status --porcelain -uall` (which expands untracked directories, so it counts **files**, not collapsed `??` directory entries). Short status without `-uall` reports 55 `??` entries instead; the file-level count is used here because it is the one that changes by exactly one when one file is added.

* **VERIFIED FACT:** no production file, test, schema, migration, dependency declaration, model file, configuration, frontend file or agent contract was modified. The only file created is this review report, inside the COORDINATOR-owned, append-only `backend/architecture/` evidence directory.
* **VERIFIED FACT:** no database was contacted or mutated (the only database-related action was a read-only TCP connect attempt that timed out); no model was downloaded; no dependency was installed; no migration ran; no `git` operation beyond inspection was performed (no stage/commit/push/reset/stash/clean/restore).
* **`BLOCKED VERIFICATION` (honest limitation):** this review did **not** hash the 330 pre-existing modified tracked files at baseline, so it cannot prove byte-identity for those files; it relies on the unchanged `git` counts plus the fact that this review issued no write operation against any production path. A pre-existing modified file could in principle have been altered by the owner between the baseline and now without changing the counts.
* **`BLOCKED VERIFICATION` (environment):** live end-to-end behaviour, database-dependent integration, OCR/generation latency, memory ceilings and GPU availability could not be verified — no PostgreSQL, no live server, no OCR engine, no generation model, and no authorisation to install or download any of them. No guard was bypassed.

**No changes were made to the target plan or to production code. The review is complete and stops here.**
