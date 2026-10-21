# DOCUMIND — MULTI-AGENT IMPLEMENTATION PLAN, REVISED

**Document ID:** `DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_REVISED`
**Revision of:** `backend/architecture/DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_2026-10-14.md` (the original plan is **preserved unmodified**)
**Driven by:** `backend/architecture/DOCUMIND_MULTI_AGENT_PLAN_REVIEW_2026-10-14.md` (findings REV-001 … REV-019)
**Date of revision and evidence verification:** 2026-10-14
**Baseline HEAD:** `6baaa2a0773df66e5fb26814afbe67647fb43435` (branch `main`)
**Kind:** **PLAN ONLY.** No production code, test, schema, migration, dependency, model, configuration, frontend file or agent contract was modified by producing this revision. Nothing was installed, downloaded, provisioned, migrated, staged, committed or pushed. **No implementation phase is started or authorized by this document.**

**Statement labels used throughout** (every substantive claim carries one):

| Label | Meaning |
| --- | --- |
| `[V]` | **VERIFIED FACT** — re-checked against the current repository by this revision, with file and line evidence |
| `[P]` | **PROPOSED** — a design decision made in this revision; not implemented |
| `[D]` | **OWNER DECISION REQUIRED** — not authorized by this task; recorded as a gate |
| `[F]` | **DEFERRED** — deliberately out of scope, with nothing claimed about it |
| `[B]` | **BLOCKED VERIFICATION** — cannot be observed in this environment |
| `[I]` | **INFERENCE** — reasoned from verified facts, not directly observed |

**Integrity:** the digest line below is excluded from its own calculation, so it stays reproducible after substitution:

Plan SHA-256: `13cee3656a10c9fdbb99619d6040c6b108d5bf3ff1d531a626719179a9196455`

---

## 1. Purpose and Scope of This Revision

**Purpose.** Correct the four HIGH findings and the fifteen remaining findings of the independent review **in the plan text**, without redesigning the application and without changing a single line of runtime behaviour. The original plan's architecture, Contracts A–F and Phases 0–7 are retained wherever they remain valid; every correction is targeted and traceable to a finding (see §20).

**In scope of this revision**

1. A disposition for every finding REV-001 … REV-019, each with rationale and evidence (§4).
2. A fully specified document lifecycle and status contract, including the reversal of a documented invariant (§7).
3. An explicit three-option decision for OCR provenance storage, with the evidence that makes one of the review's assumptions impossible (§8).
4. A safe, auditable, approval-gated policy for previously processed documents (§9).
5. A complete, implementable figure evidence path and an explicit equation decision (§10).
6. Model/answer-generation gates plus an honest unavailable-state behaviour (§11).
7. API/frontend compatibility rules that forbid nonfunctional controls (§12).
8. A file-level single-writer ownership matrix that respects the nine registered agents (§13).
9. Phases split so each deliverable is independently verifiable, with prerequisites, prohibited files, rollback and evidence (§14).
10. Measurable acceptance criteria and the full required-test inventory (§15).
11. Security, resource-control, idempotency and recovery requirements (§16), deployment/provisioning/rollback (§17).
12. The owner decisions that remain, each with options, evidence, recommended default and what stays blocked (§18).
13. An explicit list of deferred capabilities, described as unsupported (§19).

**Out of scope (hard boundary).** Implementing any phase; editing production or frontend code; schema or migration authoring; running the audit or any reprocessing; installing packages; downloading models; changing `.env`, auth, deployment or infrastructure; editing the original plan, the review report or the agent contracts; any destructive or state-mutating git operation.

**Two findings discovered by this revision's own re-verification** (not present in the review) are recorded in §2.4 and carried into §4 as `N-001` and `N-002`; both change the shape of an owner decision, and neither is presented as resolved.

---

## 2. Evidence Sources and Verification

### 2.1 Source documents (read-only; digests recorded at this revision's baseline)

| Document | SHA-256 | Role |
| --- | --- | --- |
| `backend/architecture/DOCUMIND_EXAM_ANSWER_DIAGRAM_OCR_CAPABILITY_AUDIT_2026-10-14.md` | `d489f912e68acce0a146b2343dcdf71d5397e72de814a1d0330859be65912d0d` | predecessor capability audit |
| `backend/architecture/DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_2026-10-14.md` | `fb3c7fea88486fa5fbcd9203ebc0c38bace4c1e2b1150b0029f7831ea205d98b` | the plan this document revises |
| `backend/architecture/DOCUMIND_MULTI_AGENT_PLAN_REVIEW_2026-10-14.md` | `e6c5a52c17bf333ca876ae0146c742d774506414070dd82859bff05fd8709f0f` | independent review (REV-001 … REV-019) |

### 2.2 Repository state at revision baseline `[V]`

| Item | Value |
| --- | --- |
| Repo root | `C:/Users/moham/OneDrive/Desktop/stitch_documind_futuristic_3d_ui` |
| Branch / HEAD | `main` / `6baaa2a0773df66e5fb26814afbe67647fb43435` |
| Staged changes | **0** |
| Unstaged tracked changes | **330** (pre-existing; 295 deletions + 35 modifications — **not** attributable to this task and left untouched) |
| Untracked files (repo-wide, `-uall`) | **846** (of which **719** under `backend/`; 718 before this document) |
| Destination `…_REVISED_2026-10-14.md` before writing | **Free** — no file existed, nothing overwritten |
| Python | 3.11.0 (`backend/venv/Scripts/python.exe`) |

### 2.3 Findings re-verified against current source by this revision

Every load-bearing claim below was re-checked directly; nothing here relies on the review's summary. `[V]` throughout.

| # | Claim re-verified | Evidence (file:line) |
| --- | --- | --- |
| 1 | `figure` is declared in the type constants but **never emitted** | `documents/parser.py:156` (`ELEMENT_TYPE_FIGURE`), `:176-182` (`EMITTED_ELEMENT_TYPES` = section, paragraph, table, text_block), `graph/models.py:117`, `:122-131` |
| 2 | The extractor's vocabulary **excludes** `figure` and raises on unknown types | `documents/processing.py:39` (`ALLOWED_ELEMENT_TYPES = {paragraph, heading, table, list, text}`), `:79-82` (`ValueError`) |
| 3 | The parser maps only five extractor types and **raises** on an unmapped one | `documents/parser.py:188-193` (`ELEMENT_TYPE_MAP` = heading/paragraph/table/text/list), `:186` (docstring: every allowed type must be mapped), `:297-304` (`_public_element_type`) |
| 4 | Image blocks are skipped unconditionally | `documents/processing.py:249` (`if block.get("type") == 1:`) |
| 5 | Element-level structural retrieval seeds on **section names only** and **drops** empty-content elements | `chat/rag.py:988-1071` — docstring: "structure names only; element content is never matched"; `content = info["content"] or (" > ".join(path) if path else "")` then `if not content or not content.strip(): continue` |
| 6 | The evidence contract has **no** asset/figure field today | `chat/routes.py:34-78` (`SourceOut`: `chunkId…evidenceKind`, no `figureRef`/`caption`/`extractionMethod`) |
| 7 | The request has **no** marks/diagram field and `topK` is unvalidated | `chat/routes.py:26-28` (`AskRequest{question: str, topK: int = 5}`), used unvalidated at `:336` |
| 8 | The response contract lacks `answerFormat`/`marks`/`diagram`/`generation` | `chat/routes.py:116-124` (`AskResponse`) |
| 9 | The **only** writer of `document_structure_elements` / `document_table_rows` is the persistence layer | `documents/structure.py:79-215` (`replace_document_structure`), called at `documents/routes.py:53,260-269`; the parser's `source_id` has **no column** ("no schema change is made for it", `structure.py:26-30`) |
| 10 | Row evidence is a pure deterministic projection with uniqueness | `documents/tables.py` (module docstring; `table_row_records`), `structure.py` docstring (`(document_id, table_element_id, row_index)` unique) |
| 11 | Element persistence has **no** caption/asset/method column | `graph/models.py:162-205` — `element_type` `:179`, `content` `:186`, `bbox_x0..y1` `:189-192`, `parser_version` `:193`, `created_at` `:195-197`; unique `(document_id, sequence_index)` `:202-205` |
| 11b | Element **bounding boxes are declared but never populated** — the extractor carries no bbox fields and the parser never receives one | `[V]` `documents/processing.py:47-92` (`ExtractedElement`: content, element_type, page, heading_level, heading_path, section, table_data, list_items — **no bbox**); bboxes are used locally only (`:201-215` table boxes, `:253-258` block boxes); `documents/parser.py:226-229` declares `ParsedElement.bbox_x0..y1` and `:253-256` serialises them, but `_build_elements` (`:~385-421`) constructs `ParsedElement` **without** them → `documents/structure.py:112-140` persists `None` for every element today |
| 12 | `documents` has **no** page-count, JSON, or provenance-of-extraction column | `documents/models.py:22-57` (id, user_id, name, file_type, file_size, stored_path, content_hash, chunker_version, parser_version, embedding_model, chunk_count, status, embedding_status, created_at, updated_at, processing_started_at) |
| 13 | `status` is `String(20)` with no CHECK ⇒ a new **value** needs no DDL | `documents/models.py:41-43`; migrations 000-007 contain no CHECK on `status` |
| 14 | The true PDF page count **is known at ingestion but never persisted** | `documents/parser.py:269` (`ParsedDocument.page_count`), `:277` (serialised), `:327-338` (`_pdf_page_count` → `int(doc.page_count)`), `:448` |
| 15 | `insights.pageCount` is **not** a source-page denominator — it is the **highest page seen** | `documents/insights.py:95-102` (`page_count = int(max_page)`, `"pagesRepresented": count(distinct page)`, `"pageCount": page_count`) |
| 16 | Status semantics and invariant text | `documents/routes.py:1-14` (":5 READY means actually searchable and complete … :7 There is no degraded-ready state"); transitions set at `:188` (processing), `:310` (ready), `:200-316` (error paths) |
| 17 | Status consumers | `documents/routes.py:168-169,398-425,321-330,550-551,681`; `documents/schemas.py:13,28,109`; `documents/insights.py:205`; `src/types/index.ts:8`; `src/context/WorkspaceContext.tsx` (`apiDocToFile` cast) |
| 18 | Reprocess already replaces rather than appends | `documents/routes.py:258,286,694` (delete old chunks/structure before reprocess), `structure.py:88-110` (savepoint delete-then-insert) |
| 19 | Fail-closed model provisioning at container start | `docker-entrypoint.sh:19` (`require_dir()`), `:29-31` (the three calls), `:32-35` (the `exit 1` that makes it fail closed), `:45-46` (`alembic upgrade head`), `:49` (`uvicorn … --workers 1`) |
| 20 | The persisted "AI depth" setting is inert for answers | `src/lib/api.ts:554` (`processingDepth`), `src/context/SettingsContext.tsx:29,45,60`, `src/pages/SettingsPage.tsx:32,281-288` (labels Fast…Comprehensive); no consumer in `chat/routes.py` |
| 21 | `AskResponse` frontend mirror lacks the new fields | `src/lib/api.ts:316-330` (`ApiAskResponse`, `apiAskQuestion(question, topK)`) |
| 22 | Stage/gate facts: `DOCUMIND_TABLE_EVIDENCE` (default OFF) and `CHUNKER_VERSION` (default `legacy`) | `chat/rag.py:636-643`; `config.py:65-68` |

### 2.4 New facts discovered by this revision (not in the review)

**N-001 — `insights.pageCount` cannot serve as a coverage denominator.** `[V]` `documents/insights.py:95-102` computes `pageCount` as `int(max_page)` over `document_chunks`. A 5-page PDF whose last two pages were silently dropped reports `pageCount = 3` and `pagesRepresented = 3`, i.e. **it looks complete**. The true count exists only transiently at ingestion (`parser.py:269`, `:327-338`) and is **not persisted**. Consequence: any "document-level completeness" reporting built on today's insights would repeat the silent-loss defect in a new form. This sharpens REV-004 (§8) and adds a required field decision (§18 gate 23).

**N-002 — Deployment files have no registered owner.** `[V]` No agent contract in `agents/*.md` lists `backend/docker-entrypoint.sh`, `backend/Dockerfile`, `compose.yaml` or `Dockerfile.frontend` in its **Owns** list (checked: `backend-agent.md` owns `main.py`, `config.py`, `storage/file_store.py`, `auth/**`, `user/**`, `settings/**`, `verification/**`, `reliability/**`, `documents/**`, `requirements.txt`; `database-agent.md` owns `migrations/**`, `<feature>/models.py`, `storage/database.py`, `alembic.ini`, `scripts/**`). Therefore the original plan's §11/§13 assumption that "deployment changes" are simply a `BACKEND_AGENT` approval item is **not executable under the current ownership layer**. Deployment edits require a `COORDINATOR`-owned contract amendment approved by the user (the 1.6L/1.6L-style precedent in `agents/coordinator.md`). Not blocked, but explicitly gated (§18 gate 22).

---

## 3. Summary of Corrections

| # | Correction made in this revision | Finding(s) | Where |
| --- | --- | --- | --- |
| 1 | Figure evidence now has a **complete, implementable two-path retrieval design** (caption-mediated semantic path + element-type-aware structural path), with association rules, ranking honesty, asset resolution and failure handling | REV-001 | §10.1 |
| 2 | Document lifecycle is a **full contract**: status meanings, permission-ruled transitions, success criteria, retry/failure behaviour, every verified consumer, and transition tests. The reversal of the documented "no degraded-ready state" invariant is now stated explicitly | REV-002 | §7 |
| 3 | Existing-document handling is a **policy**: read-only audit, eligibility, idempotency, recovery, identity preservation, staged rollout, pre-run approval | REV-003 | §9 |
| 4 | OCR provenance storage is a **three-option decision with evidence**, not a claim. "No migration" is no longer described as viable for page-level provenance; the discovery that `pageCount` is `max(page)` is recorded | REV-004, N-001 | §8 |
| 5 | `documents/structure.py` (and `documents/tables.py` as precedent) added to the affected-file lists — it is the **only** writer of structure/row data | REV-005 | §13 |
| 6 | Equations are **explicitly deferred** with no understanding claim; `documents/equations.py` and the Phase 2 equation deliverable are **removed** | REV-006 | §10.3 |
| 7 | `figure` reclassified as **EXTEND**, naming the three exact edits the change requires | REV-007 | §10.2 |
| 8 | Every phase now carries **failure behaviour, rollback, prohibited files, completion evidence**; a migration forward-fix/downgrade policy is defined and gated | REV-008 | §14, §17 |
| 9 | `backend/config.py` assigned to its registered owner `BACKEND_AGENT`; the `chat/routes.py` toucher list corrected to include the generation row | REV-009 | §13 |
| 10 | Resource controls, bounded retries and idempotency are specified as requirements with **owner-approved values** (no invented numbers) | REV-010 | §16 |
| 11 | `includeDiagram` is **deferred out of the request contract** until the diagram capability is approved; no UI control may appear before the API honours it | REV-011 | §12 |
| 12 | A denied/unavailable generation model now has **honest, specified behaviour** (`answerFormat="extractive"`, `marksSupported=false`, explicit unavailable state) | REV-012 | §11.3 |
| 13 | `uploaded` is documented as a **column default that the API never assigns** | REV-013 | §7.2 |
| 14 | Backend statuses and the frontend union are specified as one coordinated change with an exhaustive mapper — the unchecked cast is removed by design | REV-014 | §12 |
| 15 | Provisioning/deployment ordering is specified (provision → mount → deploy, fail-closed preserved); the **unowned deployment files** are recorded as a gate | REV-015, N-002 | §17, §18 |
| 16 | Broad phases split: **1a/1b, 2a/2b(deferred), 3a/3b, 5a/5b** | REV-016 | §14 |
| 17 | Rotation and low-quality scans get **measurable** acceptance rules | REV-017 | §15.2 |
| 18 | The verified ownership strengths and the minimal execution-group model are preserved | REV-018 | §13.4 |
| 19 | The original plan's baseline row (717/718 untracked) is corrected to current values, and its evidence claims re-verified | REV-019 | §2.2, §20 |

**No other element of the original plan was changed.** Contracts A–F remain the contract set; phases 0–7 remain the phase map; the reuse matrix, security table and approval checklist are extended, not replaced.

---

## 4. REV-001 … REV-019 Disposition Matrix

Disposition vocabulary, as required: **FIXED IN PLAN** · **ACCEPTED / DEFERRED — OWNER DECISION REQUIRED** · **NOT APPLICABLE — EVIDENCE PROVIDED** · **UNRESOLVED — BLOCKS IMPLEMENTATION**.

| Finding | Disposition | Revised-plan section | Evidence / rationale | Remaining decision or blocker |
| --- | --- | --- | --- | --- |
| **REV-001** figure evidence has no workable indexing/ranking path | **FIXED IN PLAN** | §10.1 | `[V]` the old path seeds on section names only and drops empty-content elements (§2.3 #5). The revision specifies: caption stored as the figure element's `content` (`[V]` the column exists, `graph/models.py:186`), a caption-mediated semantic path, an element-type-aware structural path, an explicit linkage rule, honest ranking (`score` stays `0.0` for element/structural candidates as today), deterministic asset resolution, and four failure modes | none for design; **Phase 2a approval** required before implementation |
| **REV-002** `partial` reverses a documented invariant; consumers unenumerated | **FIXED IN PLAN** | §7 | `[V]` invariant text `documents/routes.py:5,7`; ten consumers enumerated with line numbers (§7.4); transitions and tests defined | gate **4** — owner must approve `partial` and the `ready` redefinition |
| **REV-003** no backfill policy for existing `ready` documents | **FIXED IN PLAN** | §9 | `[V]` silent loss reproduced in the audit and re-confirmed in the original plan §1.2; `[V]` reprocess already replaces atomically (§2.3 #18) | gate **17** — approval required **before any audit run or reprocessing** |
| **REV-004** "no migration" option is not viable | **FIXED IN PLAN** | §8 | `[V]` `documents` has no suitable column (`models.py:22-57`); the element table cannot hold page records (`graph/models.py:152-200`, unique `(document_id, sequence_index)`); **N-001** shows today's insights cannot even supply a denominator | gate **3** — option A/B/C must be chosen by the owner |
| **REV-005** persistence layer missing from affected-file lists | **FIXED IN PLAN** | §13 (C-1a, C-1b, C-3) | `[V]` `documents/structure.py:79` is the only writer, imported at `documents/routes.py:53` | none |
| **REV-006** equations undefined | **ACCEPTED / DEFERRED — OWNER DECISION REQUIRED** | §10.3, §19 | `[V]` no equation representation exists in any contract; `ALLOWED_ELEMENT_TYPES` has no equation type. Deferral is honest; a claim of support would not be | gate **18** — owner decides: defer (recommended) or specify a representation first |
| **REV-007** `figure` classified REUSE | **FIXED IN PLAN** | §10.2 | `[V]` three exact edits required: `processing.py:39`, `parser.py:188` (`ELEMENT_TYPE_MAP` has no `figure`), `parser.py:176` (`EMITTED_ELEMENT_TYPES`); `_public_element_type` raises otherwise (§2.3 #3) | none |
| **REV-008** no per-phase recovery or migration rollback policy | **FIXED IN PLAN** | §14.2, §17.3 | `[V]` entrypoint applies migrations before uvicorn (`docker-entrypoint.sh:45-49`); `AGENTS.md` forbids live downgrades without permission | gate **20** — downgrade authority |
| **REV-009** `backend/config.py` assigned to `AI_AGENT` | **FIXED IN PLAN** | §13.2 | `[V]` `agents/backend-agent.md` Owns lists `backend/config.py`; `agents/ai-agent.md` does not. The `chat/routes.py` toucher list is corrected to C-6/C-7/C-8/C-9 | none |
| **REV-010** no rate limiting / cost control / idempotency statement | **FIXED IN PLAN** | §16.1-§16.3 | `[V]` no limiter exists in `main.py`/`chat/routes.py`/`documents/routes.py`; `[V]` the single-worker deployment (`docker-entrypoint.sh:49`) makes blocking work a whole-service risk | gate **21** — limit values need benchmarking/owner approval |
| **REV-011** `includeDiagram` would be decorative | **FIXED IN PLAN** | §12.3 | `[V]` no diagram capability exists (§2.3 #1, #2, #4; `graphviz`/`matplotlib`/`mermaid` absent per the original plan §1.1) and the repository rule is *"Mirror real backend state. Never hardcode backend results."* (`agents/frontend-agent.md:23`) with `AGENTS.md` §03 — a field no backend can honour fails that rule. **Attribution correction:** the review's quotation "Do not add decorative controls" does **not** appear anywhere in `agents/*.md` (verified); this revision cites the rule that does exist | gate **19** — whether the field may ship before the capability |
| **REV-012** no fallback when generation is denied | **FIXED IN PLAN** | §11.3, §19 | `[P]` specified fallback: extractive-only answer, `marksSupported=false`, explicit unavailable state; never padded, never relabelled | gate **7/8** — model decision (may be denied) |
| **REV-013** `uploaded` reachability | **NOT APPLICABLE — EVIDENCE PROVIDED** (documented, no defect) | §7.2 | `[V]` `documents/models.py:42` default; migration `000:160` `server_default`; upload writes `processing` (`documents/routes.py:438`) | none |
| **REV-014** status union mismatch / unchecked cast | **FIXED IN PLAN** | §7.4, §12.2 | `[V]` `src/types/index.ts:8` (`'uploading' \| 'processing' \| 'ready' \| 'error'`, no `partial`), cast in `WorkspaceContext.tsx`; `[V]` `'uploading'` is client-only (`WorkspaceContext.tsx:142`) | none (rides gate 4) |
| **REV-015** provisioning vs fail-closed entrypoint | **FIXED IN PLAN** | §17.1-§17.2 | `[V]` `docker-entrypoint.sh:19,29-31` (`require_dir`, `exit 1`); models are read-only mounts | gate **13**, plus **N-002** gate **22** (deployment files unowned) |
| **REV-016** phases too broad | **FIXED IN PLAN** | §14.1 | `[P]` split into 1a/1b, 2a/2b, 3a/3b, 5a/5b with independent exit criteria | none |
| **REV-017** rotation / low-quality scans absent from acceptance | **FIXED IN PLAN** | §15.2 | `[V]` the original plan's §10.1 listed a rotated page but Phase 1's criteria omitted it | gate **17** if the owner prefers deferral |
| **REV-018** preserve verified ownership strengths | **NOT APPLICABLE — EVIDENCE PROVIDED** | §13.4 | `[V]` the phase→agent mapping conforms to `agents/*.md` in every row except REV-009; no cross-agent file collision remains after the split | none |
| **REV-019** preserve accurate evidence; correct stale claims | **FIXED IN PLAN** | §2.2, §2.3, §20 | `[V]` re-verified 22 claims; the original plan's baseline row (717 → 718 untracked) is stale and is corrected here; the digest line in the original plan's header (`464d5177…`) no longer matches the current file (`fb3c7fea…`), which is recorded rather than silently ignored | none |

**Revision-discovered findings**

| Finding | Disposition | Section | Evidence | Blocker |
| --- | --- | --- | --- | --- |
| **N-001** `insights.pageCount` = `max(page seen)`, not the source page count; the true count is not persisted | **FIXED IN PLAN** (as a required decision + corrected reporting design) | §2.4, §8.3, §18 gate 23 | `[V]` `insights.py:95-102`; `[V]` `parser.py:269,327-338` (known at ingest, not stored) | gate **23** |
| **N-002** deployment files (`docker-entrypoint.sh`, `Dockerfile`, `compose.yaml`, `Dockerfile.frontend`) have no registered owner | **FIXED IN PLAN** (as a gated ownership amendment) | §2.4, §13.3, §18 gate 22 | `[V]` no `agents/*.md` Owns list contains them | gate **22** |

**No finding is `UNRESOLVED — BLOCKS IMPLEMENTATION`**: the four HIGH findings now have concrete decisions, contracts, owners and acceptance criteria in the plan text, and each carries the owner gate that its implementation requires. Implementation itself remains blocked until those gates are approved (§18), which is the correct state for a plan-only task.

---

## 5. Current-State vs Proposed-State Capability Matrix

`[V]` = observed today; `[P]` = would exist only after the named phase and its gate.

| Capability | Today | After this plan (proposed) | Phase | Gate |
| --- | --- | --- | --- | --- |
| Digital PDF / DOCX / TXT ingestion | `[V]` implemented, tested | unchanged | — | — |
| Per-page completeness decision inside the extractor | `[V]` absent | `[P]` decided per page from real extracted characters | 1a | 1 |
| Document status honesty (no false `ready`) | `[V]` absent — mixed PDFs reach `ready` | `[P]` `partial` + coverage reporting | 1a | 1, 4, 23 |
| Coverage reporting with a true denominator | `[V]` absent (`pageCount` is `max(page)` — N-001) | `[P]` **Phase 1a reports the status only**; any denominator requires option B (one column) or option A (per-page records) | 1b | 3, 23 |
| OCR of scanned pages | `[V]` not implemented (0 elements) | `[P]` adapter + selected engine, per page, tagged with its extraction method; per-page **confidence only under option A** | 1b | 2, 3 |
| Per-page OCR provenance (method/engine/confidence/failure) | `[V]` impossible in current schema | `[P]` persisted per page (option A) — or **not claimed** (options B/C) | 1b | 3 |
| Table extraction (cells/rows) | `[V]` implemented and tested | unchanged | — | — |
| Table-row retrieval | `[V]` implemented but default **OFF** (`DOCUMIND_TABLE_EVIDENCE`) | unchanged default; promotion is a separate measured decision | — | — |
| Figure elements emitted | `[V]` never emitted | `[P]` emitted with caption + page + bbox + deterministic asset | 2a | 5 |
| Figure **retrieval** | `[V]` impossible (no mechanism, no field) | `[P]` caption-mediated + element-level paths with honest ranking | 3b | 5, 6 |
| Figure assets served safely | `[V]` absent — `storage/file_store.py` exposes `save_upload` `:31`, `delete_upload` `:137`, `cleanup_new_file` `:201` and containment helpers (`_is_link_or_reparse_point` `:80`, `_resolved_within` `:97`), but **no read/serve primitive** | `[P]` a new containment-checked read/serve helper (reusing the existing helpers) plus an ownership-checked route | 2a/3b | 5, 6 |
| Equations | `[V]` not implemented (no math path) | `[F]` **deferred** — text survives verbatim as `text_block`; no notation claim | — | 18 |
| Mark-wise answers (6/8/10/15) | `[V]` not implemented (no field, no UI, extractive model, 384-token window) | `[P]` mark-aware composition + honest unavailable state | 4 | 7, 8, 21 |
| Diagram requirement detection | `[V]` absent | `[P]` rule-based detection with recorded trigger | 5a | 9 |
| New diagram generation | `[V]` absent (no renderer/dependency) | `[F]`/`[P]` optional, highest risk, last | 5b | 9, 10, 11 |
| Frontend marks/figures/partial UI | `[V]` absent; depth control is inert | `[P]` wired controls only where the API honours them | 6 | 12 |
| Live end-to-end verification | `[B]` no PostgreSQL, no live server | unchanged unless an authorized environment is provided | 7 | 14 |

---

## 6. Revised Architecture and Data Flow

**Principle preserved from the original plan:** extend the existing chain; never add a competing parser, retrieval path, vector store or document model. `[V]` the chain today is:

```
upload (documents/routes.py:336-465)
  → extract_text            (documents/processing.py; pages loop; :249 skips images)
  → parser boundary         (documents/parser.py → ParsedDocument/ParsedElement; page_count known at :269)
  → chunk + embed           (documents/processing.py chunk_text | documents/chunking.py chunk_elements)
  → replace_document_structure (documents/structure.py:79 — the ONLY writer of
                               document_structure_elements + document_table_rows; atomic savepoint)
  → structural graph        (graph/service.py)
  → status ready/error      (documents/routes.py:310/315)
```

**Proposed flow after this plan** (all additive; `[P]`):

```
extract_text
  ├─ per-page native text
  ├─ per-page completeness decision  ← NEW (Phase 1a)
  ├─ OCR fallback for insufficient pages     ← NEW (Phase 1b, gated)
  ├─ figure enumeration + caption association + asset write  ← NEW (Phase 2a, gated)
  └─ page-extraction records                 ← NEW only if option A is approved (Phase 1b)
        │
        ▼
parser boundary — extended vocabulary: "figure" added to ALLOWED_ELEMENT_TYPES,
                 ELEMENT_TYPE_MAP and EMITTED_ELEMENT_TYPES          ← Phase 2a
        │
        ▼
chunk + embed (unchanged; captions are ordinary text and already chunk normally)
        │
        ▼
replace_document_structure (+ figures, unchanged writer)             ← Phase 2a
        │
        ▼
ingestion verdict: ready | partial | error                           ← Phase 1a
        │
        ▼
retrieval: semantic (pgvector) + structural (chunk/table/figure) + RRF
           + extractionMethod provenance                             ← Phase 3a/3b
        │
        ▼
answer composition: extractive (today) → optional mark-aware generation ← Phase 4 (gated)
        │
        ▼
API (chat/routes.py) → frontend (src/**)                             ← Phase 6
```

**Data-flow invariants this revision adds (all `[P]`, each testable):**

1. **Every page is accounted for.** The ingestion verdict is computed from per-page facts the extractor already has; it is never inferred from file-level heuristics.
2. **Status never overstates.** A document with any unaccounted page is never `ready`.
3. **Provenance is never lost.** OCR-derived text and figures carry their method and page to the evidence contract.
4. **Nothing is fabricated.** Structural candidates keep `score = 0.0`; a figure match reports a retrieval path and a structural score, never a similarity (§10.1).
5. **Replacement, not accumulation.** Re-ingest replaces chunks, structure elements, table rows, page records and figure assets atomically (`[V]` precedent: `structure.py` savepoint).
6. **Assets are tenant-contained and die with their document.**

---

## 7. Document-Processing Lifecycle and Status Contract

### 7.1 The invariant that changes — stated explicitly (REV-002)

`[V]` `documents/routes.py:5` currently documents: *"READY means actually searchable and complete … There is no degraded-ready state."* This revision **reverses part of that invariant** and must say so: a document whose pages are not all accounted for becomes **`partial`**, not `ready`. The implementation must therefore update that module docstring in the same change (gate 4), because leaving the old sentence in place would contradict the new behaviour.

`[V]` the value itself needs **no DDL**: `status` is `String(20)` with no CHECK constraint (`documents/models.py:41-43`; migrations 000–007). The **contract** is what requires approval.

### 7.2 Status meanings

| Status | Meaning (proposed) | Set when | Reachable via API? |
| --- | --- | --- | --- |
| `uploaded` | stored, not yet processed | **column default only** — `[V]` `documents/models.py:42`, migration `000:160`; the upload route writes `processing` before the row is observable (`documents/routes.py:438`) | **No** — documented as unreachable (REV-013); no retry/recovery logic may be written for it |
| `processing` | pipeline running | `[V]` `documents/routes.py:188` | yes |
| `ready` | **every page of the source document produced usable content** (native or OCR), **or** the format has no pages (DOCX/TXT), and all downstream steps succeeded | ingestion verdict | yes |
| `partial` | **NEW** — at least one page produced usable content and at least one page did not (OCR unavailable, OCR failed, or genuinely no text); all downstream steps succeeded for the pages that did. The reason is recorded **per page where option A is approved, and at document level only otherwise** (§8.4) | ingestion verdict | yes |
| `error` | no page produced usable content, or any pipeline step failed | `[V]` `documents/routes.py:200-316` | yes |

**Success criteria (measurable, `[P]`):** for a **paged format** (PDF), a document is `ready` iff `pages_without_content == 0`, `partial` iff `0 < pages_without_content < pages_total`, and `error` iff `pages_without_content == pages_total`. For a **non-paged format** (DOCX/TXT) the denominator does not exist: coverage is **not applicable**, the verdict is `ready` when every pipeline step succeeded and `error` when any step raised — **never `partial`**. Independently of format, any step raising yields `error`.

### 7.3 Permitted transitions

| From | To | Trigger | Owner of the write |
| --- | --- | --- | --- |
| `uploaded` | `processing` | upload (default never observed) | `documents/routes.py` |
| `processing` | `ready` | complete coverage, all steps ok | ingestion verdict |
| `processing` | `partial` | incomplete coverage, all steps ok | ingestion verdict |
| `processing` | `error` | any step failed, or no usable page | existing error paths |
| `processing` | `processing` | stale-run requeue | `[V]` `documents/routes.py:415-416` |
| `ready` / `partial` / `error` | `processing` | explicit reprocess (`[V]` `:642-681`) or dedupe requeue on error/stale | reprocess route |
| **any** | `uploaded` | **forbidden** | — |

`[V]` the reprocess guard (`:681`) currently blocks only a non-stale `processing` document; the revision requires the same guard for `partial` (a `partial` document may be reprocessed, but not while it is being reprocessed).

### 7.4 Consumers that must change together (verified, exhaustive as of this revision)

| Consumer | Evidence | Required change |
| --- | --- | --- |
| Module docstring / invariant text | `[V]` `documents/routes.py:1-14` | restate the invariant (this is the honesty change) |
| `DocumentOut` builders | `[V]` `:168-169`, `:550-551` | expose the new value (field already typed `str`) |
| Dedupe / return-existing path | `[V]` `:398-425` | decide `partial` handling explicitly (return existing; reprocess only when stale/error) |
| Stale-run detector | `[V]` `:321-330` | unchanged semantics; `partial` must not be treated as stale |
| Reprocess guard | `[V]` `:681` | add the `partial`-while-processing guard |
| `DocumentOut` / `DocumentDetailResponse` / insights schema | `[V]` `documents/schemas.py:13,28,109` | keep `status: str`; add coverage fields (see §8) |
| Insights payload | `[V]` `documents/insights.py:205` | carry the coverage summary; **correct the misleading `pageCount` semantics** (N-001) via **new** fields, leaving the legacy field's meaning documented |
| Frontend type union | `[V]` `src/types/index.ts:8` | add `'partial'` |
| Frontend mapping cast | `[V]` `src/context/WorkspaceContext.tsx` (`apiDocToFile`) | replace the `as DocumentStatus` cast with an exhaustive mapper (§12.2) |
| Frontend rendering | `[V]` `src/pages/WorkspacePage.tsx` | render `partial` with what is missing; render an explicit unknown-status state rather than a silent fallthrough |

### 7.5 Failure and retry behaviour (REV-002)

* An OCR **failure** on a page never aborts the document silently: it is recorded per page (option A) or reflected in the verdict as an unaccounted page (options B/C), and the document is `partial`, never `ready`.
* A pipeline **exception** keeps today's behaviour: `error` + `embedding_status='error'` (`[V]` `:200-316`).
* **Retry** = the existing reprocess route; it deletes derived rows first (`[V]` `:258,286,694`) and rebuilds them atomically (`[V]` `structure.py:88-110`). Retries therefore **replace**, never append.
* A reprocess that fails leaves `error` — never a stale `ready`.

### 7.6 Required transition tests (owned by `TEST_AGENT`)

Every transition in §7.3, plus: `ready` never set with an unaccounted page; `partial` set when exactly one page is unavailable; `error` when no page yields content; `partial` survives reprocess-to-`ready` when OCR becomes available; dedupe path returns `partial` unchanged; stale requeue does not clobber `partial`; insights report the same status as `DocumentOut`; frontend renders `partial` and an unknown status explicitly. `[V]` existing tests that assert status must be updated together: `tests/unit/documents/test_phase3e_processing.py`, `tests/integration/documents/*` (status assertions), `tests/e2e/browser/test_document_flow.py`.

---

## 8. OCR Provenance and Schema Decision (REV-004, N-001)

### 8.1 What is verified, and what the original plan got wrong

* `[V]` `documents` has no column able to hold, per page, the extraction method, engine, confidence, rotation or failure reason (`documents/models.py:22-57`).
* `[V]` `document_structure_elements` is an **element** table with `UNIQUE (document_id, sequence_index)` (`graph/models.py:191-200`); one row per parser element. A page-level record is not an element; writing one there would break the uniqueness contract and the element↔table-row linkage.
* `[V]` the parser's `source_id` has no column by design (`structure.py:26-30`), so an ingestion-local page key cannot be persisted either.
* `[V]` **N-001**: `insights.pageCount` is `int(max_page)` (`insights.py:95-102`), so it cannot act as a denominator; the true page count is known at ingestion (`parser.py:269,327-338`) and never stored.

**Therefore the original plan's statement that "Phase 1 can ship without a migration if per-page OCR provenance is carried in existing structure-element rows" is withdrawn as incorrect.**

### 8.2 Three options

| Option | Schema work | What it enables | Trade-offs |
| --- | --- | --- | --- |
| **A — `document_page_extractions` table** (recommended if OCR is in scope) | one additive migration `008_add_page_extractions` (new table only; no existing column touched) | per-page method/engine/version/languages/mean confidence/char count/rotation/failure reason + parser version; the full coverage summary; OCR provenance on evidence | new table + FK cascade; a second persistence layer to keep atomic (same savepoint discipline as `structure.py`); DATABASE_AGENT-authored model/migration |
| **B — one additive column `documents.page_count`** (minimal honest fix) | migration adding a nullable integer column | a **true denominator**; `ready`/`partial` verifiable after the fact; honest coverage reporting via new insights fields; fixes N-001 | still **no** per-page method/confidence/failure; OCR provenance remains document-level only |
| **C — no DDL at all** | none | status honesty only (`[V]` a new status **value** needs no DDL) | no denominator is persisted, so nothing beyond the status itself can be reported honestly; the UI can say only "incomplete" with no numbers |

**Recommended default (`[P]`, subject to gate 3):** **Option A if OCR is approved**, otherwise **Option B**. Option C is acceptable only if the owner explicitly accepts that coverage numbers cannot be shown. No option is implemented by this revision.

### 8.3 Proposed shape of option A (specification only, not authored)

```
document_page_extractions        (new table; DATABASE_AGENT-owned model + migration)
  id                uuid pk
  document_id       uuid  FK documents(id) ON DELETE CASCADE, indexed
  page_number       int   (1-based; matches existing page provenance)
  method            varchar(16)   -- 'native' | 'ocr' | 'none'
  ocr_engine        varchar(64)  null
  ocr_engine_version varchar(32) null
  languages         varchar(64)  null
  mean_confidence   float        null
  char_count        int          not null
  rotation_applied  int          null      -- degrees, only when detected and applied
  failure_reason    varchar(64)  null
  parser_version    varchar(64)  null
  created_at        timestamptz  not null default now()
  UNIQUE (document_id, page_number)
```
* Replaced atomically on reprocess, exactly like structure rows: delete-then-insert inside the existing savepoint discipline (`[V]` precedent `structure.py:88-110`).
* Written by `[P]` a new persistence-layer module `backend/documents/page_extractions.py` (BACKEND_AGENT: `documents/**` is its ownership; the parser stays database-free — the same boundary rule the project already enforces).
* Migration ordering: current single linear head is `007_add_table_rows` `[V]`; `008` must be additive-only, with `downgrade()` dropping the table, and must not alter existing columns (§17.3).

### 8.4 What stays true regardless of the option chosen

* The **decision** (not the code) is what this task can deliver; the storage choice is gate 3.
* If options B or C are chosen, the plan, the API and the UI **must not** claim per-page OCR provenance — no invented confidence, no per-page reasons.
* If option A is chosen, `extraction_method` on evidence (§10.4) becomes fully answerable; otherwise it is document-level or absent.

---

## 9. Existing-Document Audit and Reprocessing Policy (REV-003)

**Problem restated with evidence.** `[V]` today a mixed PDF can reach `ready` with pages absent (audit finding 2, re-confirmed in the original plan §1.2). An OCR feature added later does not retroactively fix documents already stored. Nothing in the original plan addressed those rows.

### 9.1 Detection strategy (read-only, auditable)

`[P]` a **read-only audit** — never a mutation — executed only after gate 17:

1. **Coverage shortfall:** for each PDF document, compare the source PDF's page count (recomputed from the stored file, read-only) against the distinct pages represented in `document_chunks` and `document_structure_elements`.
2. **Zero-content documents:** documents whose `chunk_count == 0` while `status == 'ready'` (a state the new contract forbids).
3. **Already-flagged documents:** any document already `partial` under the new contract, for reconciliation.
4. **Output:** a report (document ids, name, page counts, missing page numbers, current status, created_at) — counters and ids only, **never** extracted document text.

Ownership: the audit tool is a **script** → `DATABASE_AGENT` (`[V]` `agents/database-agent.md` Owns `backend/scripts/**`), named `[P]` `backend/scripts/audit_page_coverage.py`, **dry-run by default**, with no write path at all (its only mode is reporting). Any future write-capable variant is a separate, separately-approved artifact.

### 9.2 Eligibility and idempotency

* **Eligible** for reprocessing only after OCR is available (otherwise reprocessing cannot improve coverage) and only on explicit approval; not eligible while `processing`.
* **Identity preserved:** document `id`, `name`, `content_hash`, `file_type`, `created_at`, and the stored file are unchanged by reprocessing (`[V]` `documents/routes.py:664` already states identity/hash/file preservation).
* **Duplicate prevention:** reprocessing deletes derived rows before rebuilding (`[V]` `:258,286,694`) and `structure.py` re-inserts inside a savepoint; row uniqueness `(document_id, table_element_id, row_index)` makes duplicate row evidence impossible; chunks are rebuilt with fresh indices. `[P]` the same delete-then-insert rule is required for page records and figure assets so a retry cannot double-write.
* **Citations survive by construction:** `[V]` a source carries `chunkId` **and** the document/page identity (`chat/routes.py:40,43,45`) — the `chunkId` of a rebuilt chunk necessarily changes, while the **document + page** identity survives, which is why stored answer provenance is not invalidated by reprocessing.
* **Failure recovery:** a failed reprocess leaves `error` with the existing error semantics; the operator may retry; no partially rebuilt document is ever left `ready`.

### 9.3 Operational rollout (proposed, gated)

1. Owner approves the policy and the scope (gate 17).
2. Run the audit (§9.1) and record the report.
3. Owner reviews the report and approves a **bounded batch** (a named document-id list or an explicit count ceiling per run).
4. Run reprocessing through the **existing** route — no direct SQL writes, ever; status is written only by the pipeline.
5. Record before/after coverage per document; any document that cannot be improved is reported, not silently retried.

**Status rewrite is not part of the policy**: no script may set `status`; only the pipeline may.

---

## 10. Figure and Equation Representation and Retrieval (REV-001, REV-006, REV-007)

### 10.1 Figure evidence: complete end-to-end path (REV-001)

**Why the original plan was insufficient — `[V]`:** element-level structural candidates are seeded by **section-name matches only** and any element with empty content is **dropped** (`chat/rag.py:988-1071`); images cannot be embedded (the only embedding model is text, 384-dim); and the evidence contract has no asset field (`chat/routes.py:34-78`). Declaring a `figure` evidence kind therefore retrieves nothing.

**Proposed path (all `[P]`):**

| Step | Specification | Owner |
| --- | --- | --- |
| 1. Detection | Enumerate image blocks that the extractor currently skips (`[V]` `documents/processing.py:249`) using the already-pinned PyMuPDF (`page.get_images()` / `get_pixmap()`); each becomes a candidate figure with page + bbox (PyMuPDF boxes are already collected for text) | BACKEND_AGENT |
| 2. Caption association | Deterministic geometric rule: the nearest text block whose box lies below the figure within a declared gap, else above, else **no caption**. The associated caption is stored **verbatim** as the figure element's `content`. Association is recorded, never inferred, and never invented if absent | BACKEND_AGENT |
| 3. Persistence | One `figure` element in the **existing** `document_structure_elements` row shape: `element_type='figure'`, `page_number`, `content` = caption text (or `''` when none), `bbox_x0..y1`, `parser_version`. Persisted by the existing writer (`[V]` `documents/structure.py:79`) — **no new column, no schema change** for figures. **Caption authority rule:** the figure's `content` is an **association copy only**; the caption's own paragraph element remains the **only** chunked/embedded copy (step 6), so the caption text is indexed exactly once. `[V]` requires the bbox data path of §10.2 items 4-5, because element bboxes are currently always `None` | BACKEND_AGENT |
| 4. Asset storage | The extracted image is written inside the document's own upload subtree with a **deterministic name** derived from `document_id` + `sequence_index`; no ad-hoc path joining (reuse `storage/file_store.py` containment) | BACKEND_AGENT |
| 5. Asset reference | `figureRef = "fig:<document_id>:<sequence_index>"` — opaque, server-resolved, **never** a filesystem path or URL, resolved server-side with an ownership check | BACKEND_AGENT |
| 5b. Asset read/serve | `[V]` `storage/file_store.py` has **no** read/serve primitive (`save_upload` `:31`, `delete_upload` `:137`, `cleanup_new_file` `:201`; containment helpers `_is_link_or_reparse_point` `:80`, `_resolved_within` `:97`). A **new** containment-checked read helper must be added there (reusing those helpers, never ad-hoc path joining) and consumed by an ownership-checked asset route | BACKEND_AGENT |
| 6. Retrieval path 1 — caption-mediated semantic | The caption is ordinary document text, so it is already chunked and embedded by the existing pipeline — and by the authority rule in step 3 it is the **only** chunked copy. When a retrieved chunk's content contains a figure's caption (exact normalised match, non-empty) in the same document and page, the retriever **attaches** that figure (`figureRef`, `caption`, `elementId`) to the returned source. No new index, no image embedding, no double-counting | AI_AGENT |
| 7. Retrieval path 2 — element-type-aware structural | In `chat/rag.py:988-1071`: (a) the empty-content filter becomes **element-type aware**, retaining `figure` elements; (b) figure seeding is added for explicit figure intent (question terms such as figure/diagram/chart/illustration, combined with the existing section-name or page scope). Figure candidates keep `score = 0.0` and carry only their `structural_score`/`retrieval_path` | AI_AGENT |
| 8. Ranking honesty | Caption-bearing figures rank through the **existing** RRF fusion like any chunk; element-only figures rank by structural score. **No fabricated similarity is ever reported** for a figure | AI_AGENT |
| 9. Citation/provenance | A figure source carries `documentId`, `page`, `elementId`, `caption`, `figureRef`, `evidenceKind='figure'` and the retrieval path | AI_AGENT |
| 10. Frontend | Renders the figure only through the authorised asset route, with its caption and page; never raw HTML; never a substituted image | FRONTEND_AGENT |

**Failure handling (all `[P]`, each tested):**

| Failure | Required behaviour |
| --- | --- |
| Figure detected, asset extraction failed | Element persisted with `figureRef = None` and a reason; evidence may still be returned as caption-only; the answer must not claim an image is available |
| Figure detected, asset missing at request time | Asset route returns 404 for the owner too; evidence reports `figureRef` unavailable; no placeholder image |
| Figure has no caption | Content is `''`; only path 2 can surface it (explicit figure intent + structural scope); it is **never** described by invented caption text |
| Foreign document / cross-tenant asset request | Ownership resolved server-side from the JWT; 404 (not 403) for a foreign document, matching existing document routes |
| Caption association ambiguous | No association (`caption = None`); ambiguity is not resolved by guessing |

### 10.2 `figure` is EXTEND, not REUSE (REV-007)

`[V]` emitting a figure requires **five** edits across the extractor and the parser, and the parser fails closed on anything unmapped (`parser.py:186,297-304`):

1. `documents/processing.py:39` — add the extractor-side type to `ALLOWED_ELEMENT_TYPES` (otherwise `ExtractedElement.__post_init__` raises at `:79-82`).
2. `documents/parser.py:188-193` — add the mapping in `ELEMENT_TYPE_MAP` (today: heading, paragraph, table, text, list — **no** figure).
3. `documents/parser.py:176-182` — add it to `EMITTED_ELEMENT_TYPES` (today: section, paragraph, table, text_block).
4. `documents/processing.py:47-92` — add bbox fields to `ExtractedElement` and populate them for figures. `[V]` **the extractor carries no bbox fields today** (content, element_type, page, heading_level, heading_path, section, table_data, list_items) and uses boxes only locally (`:201-215` table boxes, `:253-258` block boxes) — so a figure bbox needs a genuinely new data path, not just an emit.
5. `documents/parser.py` `_build_elements` (`:~385-421`) — forward that bbox into `ParsedElement.bbox_x0..y1`, which is declared (`:226-229`) and serialised (`:253-256`) but **never populated**, which is why `documents/structure.py:112-140` persists `None` for every element today.

The public type constant (`parser.py:156`, `graph/models.py:117`) and the graph vocabulary (`graph/models.py:110-131`) are genuinely reused — that part of the original classification was right. **No production consumer of `figure` exists** `[V]` (it has never been emitted), so this change cannot regress current behaviour; the research layer does reference the type and forbids premature use (`backend/evaluation/schemas.py:17`, `backend/evaluation/datasets/structure_discriminating_v1.py:91`), which is the same honesty rule §19 applies.

### 10.3 Equations — explicitly deferred (REV-006)

**Decision in this revision:** `[F]` **equations are not supported and nothing about them is claimed.** Concretely:

* No `backend/documents/equations.py` module (the original plan's C-4 is **withdrawn**).
* No equation element type is introduced; no LaTeX/MathML representation is proposed.
* Equation-like text continues to arrive as ordinary `text_block`/paragraph content, which is **text preservation, not equation understanding** — and this wording must appear wherever the capability is described.
* A test is required that asserts only *preservation*: equation-region text either appears verbatim in a text element or is absent with the page reported as `partial`; **no test may assert notation correctness**.
* If the owner wants notation support later, it needs its own decision record (engine/dependency, accuracy measurement, storage) before any implementation — gate 18.

### 10.4 Contract A/B/C/E deltas in this revision

| Contract | Original | This revision |
| --- | --- | --- |
| **A** canonical representation | `figure` "reuse"; equations implied | `figure` = **EXTEND** with the three exact edits (§10.2); `extraction_method`/`extraction_confidence` only claimable under option A or document-level fields; **equation row removed**; caption stored in the existing `content` column |
| **B** OCR result | per-page record with no home | record exactly as option A's table (§8.3) **if approved**; otherwise document-level honesty only (§8.2) |
| **C** evidence | adds `figure`, `extractionMethod`, `figureRef`, `caption` | same fields, now with the retrieval mechanism (§10.1), the ranking-honesty rule, `elementId`, and the failure matrix |
| **D** answer request/response | adds `marks`, `includeDiagram` | `marks` retained with an honest unsupported state (§11.3); **`includeDiagram` removed from this revision's contract** and deferred to 5b (REV-011); `topK` gains declared bounds (§12.1); **per-section evidence linkage is a required response field for generated answers** (`sectionEvidence`, §12.1) — the review's §12 requirement, now in the contract rather than only in the metrics |
| **E** diagram representation | full payload | unchanged in shape, but **only reachable after gate 9/10** and now explicitly `retrieved_figure`-only until generation is approved |
| **F** processing status | five statuses, definition change | full lifecycle contract with transitions, consumers, failure/retry, tests (§7) |

---

## 11. Answer-Generation and Model Approval Gates (REV-012)

### 11.1 Verified starting point

* `[V]` the QA path is a **single-span extractive** model with a 384-token input window and 100-token answer cap; a probe returned a 16-character span for a factual question and score `0.0` for an unsupported one (audit findings 7-9, re-confirmed in the original plan §1.2).
* `[V]` `AskResponse` has no format/marks/diagram fields (`chat/routes.py:116-124`); the frontend mirror matches (`src/lib/api.ts:316-321`).
* `[V]` `.env.example` reserves commented `LLM_API_KEY` / `LLM_MODEL`; nothing reads them.

### 11.2 Decision required, not made

`[D]` Whether a generation model is introduced, and whether it is local (no egress, needs measured capacity) or hosted (egress + cost + a rule change), remains **gate 7/8**. This revision records the alternatives and the evaluation requirements; it does **not** select a model, and `[B]` no latency/memory/capacity measurement exists in this environment, so no option can be called feasible today.

### 11.3 Honest behaviour while generation is denied or unavailable (REV-012)

`[P]` specified for Phase 4 and mandatory in Phase 6:

| Situation | Required response | Required UI |
| --- | --- | --- |
| `marks` absent | today's behaviour exactly: extractive span, `answerFormat="extractive"` | unchanged |
| `marks` present, generation **not approved / not configured** | extractive answer, `answerFormat="extractive"`, `marksRequested` echoed, `marksSupported=false`, `outcome`/`generation.degraded=true` with `reason`; **never padded, never relabelled as an exam answer** | an explicit "marks-based answers are not available" state; no fake long answer, no word-count padding |
| Generation configured but fails / times out | honest failure state (`UNAVAILABLE`/`degraded=true` + reason); never a fabricated or silently truncated answer | error state with retry affordance, distinct from an empty answer |
| Evidence insufficient | existing gate outcome (`[V]` `brain/gate.py`) unchanged; generation adds no new authority to answer | existing insufficient-evidence state |

### 11.4 Evaluation requirements before any generation release (thresholds are gate 21)

`[P]` no release without separately-reported metrics for: answer accuracy against evidence; evidence coverage; groundedness/unsupported-claim rate; structural completeness per mark level (assessed by rubric, **never** by word count alone); redundancy; citation correctness (document + page); latency p50/p95; and failure/abstention rates. `[D]` every numeric threshold is an owner decision (no defensible baseline exists today); the plan invents none.

---

## 12. API and Frontend Compatibility Requirements (REV-011, REV-014)

### 12.1 `AskRequest` / `AskResponse` deltas

`[P]` `chat/routes.py:26-28` gains only what can be honoured:

```
AskRequest
  question : str                  # unchanged, non-empty
  topK     : int = 5              # NOW validated: ge=1, le=<declared ceiling>  [D] ceiling value
  marks    : int | None = None    # one of {6,8,10,15}; None = current behaviour
  # includeDiagram: NOT added in this revision (REV-011) — see §12.3

AskResponse (additive; existing fields untouched)
  answerFormat     : "extractive" | "exam"
  marksRequested   : int | None
  marksSupported   : bool
  diagram          : DiagramPayload | None    # only after gate 9/10
  generation       : { model: str, degraded: bool, reason: str | None }
  sectionEvidence  : dict[str, list[str]] | None   # NEW: per-answer-section evidence ids (generated answers only)
```

* `[V]` `topK` is currently unvalidated (`chat/routes.py:28`, used at `:336`). Bounding it is a deliberate, documented tightening: out-of-range values that are accepted today would become `422`. This must be recorded in the contract so no client is surprised.
* `[P]` `SourceOut` (`chat/routes.py:34-78`) gains `extractionMethod`, `figureRef`, `caption`, `elementId` — all nullable, so existing clients and legacy rows are unaffected, matching the class's established convention.

### 12.2 Status contract compatibility (REV-014)

* `[V]` backend statuses: `processing`, `ready`, `error` (+ `uploaded` default, + proposed `partial`); the frontend union at `src/types/index.ts:8` lists `'uploading'` (a **client-only** value set at `src/context/WorkspaceContext.tsx:142`) and lacks `partial`.
* `[P]` one coordinated change: extend the union to the backend's real values (including `partial`), keep `'uploading'` explicitly documented as client-side, and replace the `as DocumentStatus` cast with an **exhaustive mapper** whose default branch produces an explicit `unknown` state that the UI renders as such (never a silent fallthrough to a wrong state).
* `[P]` required test: a mapping test asserting every backend value renders a defined state, plus an unknown value rendering the explicit unknown state.
* `[V]` `insights` already carries `status` (`documents/insights.py:205`), so both endpoints must stay consistent; a test asserts equality between the detail and insights statuses.

### 12.3 Nonfunctional controls are forbidden (REV-011)

* `[P]` **No** `includeDiagram` field in the request contract and **no** diagram UI until the diagram capability exists (gate 9/10). The original plan's inclusion of the field with a note that it is "not a promise" is withdrawn: a field no backend can honour contradicts the frontend contract — *"Mirror real backend state. Never hardcode backend results."* (`agents/frontend-agent.md:23`) — and `AGENTS.md` §03. (**Attribution note:** the review's phrase "Do not add decorative controls" is not present in `agents/*.md`; the rule cited here is the one that exists.)
* `[V]` the **already-inert** `aiProcessing.depth` control exists today (`src/lib/api.ts:554`; `src/context/SettingsContext.tsx:29,45,60`; `src/pages/SettingsPage.tsx:32,281-288`) and is not consumed by the answer path. `[P]` Phase 6 must either **wire it to a real backend behaviour** (only if such behaviour is implemented) or **remove the affordance**; it must not stay inert. This is owner question 11 of the original plan and remains `[D]`.

### 12.4 Frontend rules carried forward

Reuse `src/lib/api.ts`; mirror real backend state; represent loading, empty, error, unavailable and unknown states; never hardcode backend results; never `dangerouslySetInnerHTML`; keep accessibility; do not add a dependency for convenience.

---

## 13. Agent Ownership and File-Level Single-Writer Matrix

### 13.1 Revised matrix (registered agents only; no new ownership system)

| # | Change | Owner | Files (single writer each) | Depends on | Tests | Reviewer | Approval |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **C-1a** | Per-page completeness decision + verdict (`ready`/`partial`/`error`) | `BACKEND_AGENT` | `backend/documents/processing.py`, `backend/documents/routes.py`, `backend/documents/schemas.py`, `backend/documents/insights.py` | — | `TEST_AGENT` | `VERIFIER` | gate 1, 4 |
| **C-1b** | OCR adapter + engine invocation | `BACKEND_AGENT` | `backend/documents/ocr.py` *(new)*, `backend/documents/processing.py`, `backend/requirements.txt`, `backend/config.py` | gates 2, 3 | `TEST_AGENT` | `SECURITY_AGENT`, `VERIFIER` | gates 2, 3, 13 |
| **C-2** | Page-extraction persistence *(only if option A)* | `DATABASE_AGENT` (model + migration) / `BACKEND_AGENT` (writer) | `backend/documents/models.py` (DATABASE_AGENT), `backend/migrations/versions/008_add_page_extractions.py` *(new, DATABASE_AGENT)*, `backend/documents/page_extractions.py` *(new, BACKEND_AGENT)*, `backend/documents/routes.py` | gate 3 | `TEST_AGENT` | `COORDINATOR` + `VERIFIER` | gate 3 |
| **C-2b** | `documents.page_count` column *(only if option B)* | `DATABASE_AGENT` (model + migration) / `BACKEND_AGENT` (write at ingest) | `backend/documents/models.py`, `backend/migrations/versions/008_*.py`, `backend/documents/routes.py`, `backend/documents/insights.py`, `backend/documents/schemas.py` | gate 3, 23 | `TEST_AGENT` | `VERIFIER` | gates 3, 23 |
| **C-3** | Figure extraction, caption association, assets | `BACKEND_AGENT` | `backend/documents/figures.py` *(new)*, `backend/documents/processing.py`, `backend/documents/parser.py`, `backend/documents/routes.py`, **`backend/documents/structure.py`**, `backend/storage/file_store.py` (`documents/tables.py` is the projection precedent, read-only reference) | gate 5 | `TEST_AGENT` | `SECURITY_AGENT`, `VERIFIER` | gate 5 |
| **C-6a** | OCR-derived text in retrieval (`extractionMethod`) | `AI_AGENT` | `backend/chat/rag.py`, `backend/chat/routes.py` | C-1b | `TEST_AGENT` | `VERIFIER` | none |
| **C-6b** | Figure evidence: types, linkage, ranking, asset-aware sources + asset route | `AI_AGENT` (retrieval) + `BACKEND_AGENT` (asset route in `documents/routes.py`) | `backend/chat/rag.py`, `backend/chat/routes.py`, `backend/graph/service.py`, `backend/brain/adapters.py`, `backend/documents/routes.py` | C-3 | `TEST_AGENT` | `SECURITY_AGENT` (IDOR), `VERIFIER` | gate 6 |
| **C-7** | `marks` field + validation + `answerFormat`/`marksSupported` | `AI_AGENT` | `backend/chat/routes.py` | gate 8 | `TEST_AGENT` | `VERIFIER` | gate 8 |
| **C-8** | Generation adapter + composition + honest failure | `AI_AGENT` | `backend/chat/answer_composer.py` *(new)*, `backend/chat/routes.py`, `backend/brain/adapters.py`; **`backend/config.py` → `BACKEND_AGENT`** | gate 7 | `TEST_AGENT` + `EVALUATION_AGENT` | `SECURITY_AGENT` (egress), `VERIFIER` | gate 7 |
| **C-9** | Diagram requirement detection (rule-based, recorded trigger) | `AI_AGENT` | `backend/brain/classifier.py`, `backend/brain/adapters.py`, `backend/chat/routes.py` | C-7 | `TEST_AGENT` | `VERIFIER` | gate 9 |
| **C-10** | Diagram rendering service *(only if generation approved)* | `BACKEND_AGENT` | `backend/diagrams/render.py` *(new package)*, `backend/main.py`, `backend/requirements.txt` | gates 9, 10, 11 | `TEST_AGENT` | `SECURITY_AGENT` (XSS/SSRF), `VERIFIER` | gates 9-11, 22 |
| **C-11** | Frontend: marks, answers, figures, `partial`, unknown status, depth control | `FRONTEND_AGENT` | `src/pages/WorkspacePage.tsx`, `src/context/WorkspaceContext.tsx`, `src/lib/api.ts`, `src/types/index.ts`, `src/pages/SettingsPage.tsx`, `package.json` | C-7, C-12 | `FRONTEND_AGENT` (introduces runner) | `VERIFIER` | gate 12 |
| **C-12** | Status contract + coverage fields + insights correction | `BACKEND_AGENT` + `DATABASE_AGENT` (only if a column/table) | `backend/documents/routes.py`, `backend/documents/schemas.py`, `backend/documents/insights.py` | C-1a | `TEST_AGENT` | `COORDINATOR` | gates 1, 4, 23 |
| **C-13** | Test suites, fixtures, transition tests | `TEST_AGENT` | `backend/tests/**`, `backend/pytest.ini` | each phase | `TEST_AGENT` | `VERIFIER` | none |
| **C-14** | Evaluation corpora, runners, metrics | `EVALUATION_AGENT` | `backend/evaluation/**` | C-1b, C-3, C-8 | `EVALUATION_AGENT` | `VERIFIER` | none |
| **C-15** | Audit script (read-only) | `DATABASE_AGENT` | `backend/scripts/audit_page_coverage.py` *(new)* | gate 17 | `TEST_AGENT` | `VERIFIER` | gates 17, 3 |
| **C-16** | Deployment edits *(entrypoint/Dockerfile/compose)* — **no registered owner** | **UNASSIGNED → requires `COORDINATOR`-owned contract amendment** | `backend/docker-entrypoint.sh`, `backend/Dockerfile`, `compose.yaml`, `Dockerfile.frontend` | gate 22 | `TEST_AGENT` | `SECURITY_AGENT`, `VERIFIER` | gate 22 (N-002) |
| **C-17** | Documentation and evidence records | `COORDINATOR` | `backend/architecture/**` (append-only), `CONTEXT.md`, `ARCHITECTURE.md` | all | — | user | none |
| **C-18** | Diagram package ownership amendment *(if C-10 proceeds)* | `COORDINATOR` | `agents/backend-agent.md` (Owns list) | gate 11 | — | user | gate 11 |

### 13.2 Ownership corrections made by this revision (REV-009, REV-005)

* **`backend/config.py` → `BACKEND_AGENT`.** `[V]` `agents/backend-agent.md` Owns lists `backend/config.py`; `agents/ai-agent.md` lists `chat/**`, `embeddings/**`, `brain/**`, `graph/**`, `tokenization.py`, `outcomes.py` — **not** config. The generation work therefore *requests* a config field; it does not edit the file. Any config addition is a BACKEND_AGENT change applied once, sequentially.
* **`chat/routes.py` toucher list corrected.** `[V]` the original plan's note enumerated C-6/C-7/C-9 and omitted C-8, which also lists `chat/routes.py`. The revision states all four (C-6a, C-6b, C-7, C-8, C-9) as one `AI_AGENT`-owned, **sequential** series.
* **`documents/structure.py` added** to C-3 (and to any row that changes element content/type), because `[V]` it is the only writer of `document_structure_elements` / `document_table_rows` (`structure.py:79`; imported at `documents/routes.py:53`).
* **`documents/tables.py` recorded as the projection precedent** — the model a figure-asset or page-record projection should follow (pure, deterministic, database-free).
* **`backend/scripts/**` → `DATABASE_AGENT`** for the audit script `[V]` (`agents/database-agent.md`).

### 13.3 Single-writer conflicts

| Shared file | Touchers | Resolution |
| --- | --- | --- |
| `backend/documents/processing.py` | C-1a, C-1b, C-3 | sequential, same owner (`BACKEND_AGENT`) |
| `backend/documents/routes.py` | C-1a, C-1b, C-3, C-6b (asset route), C-12 | sequential; the asset route is the only `AI_AGENT`-initiated edit and is applied **by BACKEND_AGENT** on request |
| `backend/chat/routes.py` | C-6a, C-6b, C-7, C-8, C-9 | sequential, same owner (`AI_AGENT`) |
| `backend/documents/models.py` | C-2 / C-2b | `DATABASE_AGENT` only |
| `backend/requirements.txt` | C-1b, C-10 | `BACKEND_AGENT` only, ordered edits, never parallel |
| `backend/documents/insights.py`, `schemas.py` | C-1a, C-2b, C-12 | `BACKEND_AGENT`, one change per phase |
| Deployment files | C-16 | **unowned today** → gate 22 before any edit |

`[V]` forbidden for every agent: `backend/models/documind-qa/**`, `backend/venv/**`, `backend/phases/phase4f_gpu/**`, `backend/uploads/**`, `backend/.env`, `.env`, `dist/`, `node_modules/`.

### 13.4 Minimal execution groups (REV-018, preserved)

Four writers — `BACKEND_AGENT`, `DATABASE_AGENT`, `AI_AGENT`, `FRONTEND_AGENT` — plus `TEST_AGENT` (tests) with `EVALUATION_AGENT` for research evaluation, `SECURITY_AGENT` auditing (remediation routed to the owning agent), and `VERIFIER` owning nothing and re-checking independently. **No agent is added to make the plan look comprehensive.**

---

## 14. Phase Dependencies and Explicit Prerequisites (REV-008, REV-016)

### 14.1 Phase map

```
Phase 0  Reconnaissance ................ COMPLETE (original plan)
   │
   ├─ Phase 1a  Detection + honest status + honest reporting ......... NO new dependency, NO DDL
   ├─ Phase 1b  OCR engine integration ........ gates 2, 3 (+13 deployment)
   │        │
   │        ├─ Phase 2a  Figures + captions + assets  gate 5 (no DDL)
   │        └─ Phase 2b  Equations ................... DEFERRED (gate 18)
   │                 │
   │                 ├─ Phase 3a  OCR text in retrieval
   │                 └─ Phase 3b  Figure evidence in retrieval ..... gate 6
   │                          │
   │                          ├─ Phase 4   Mark-aware generation .... gates 7, 8, 21
   │                          └─ Phase 5a  Diagram detection + existing-figure retrieval ... gate 9
   │                                   └─ Phase 5b  Diagram generation/rendering ... gates 9-11
   │                                            │
   └────────────────────────────────────────► Phase 6  Frontend .... gates 12, 4
                                                     │
                                                     ▼
                                              Phase 7  Integration, evaluation, security, verification ... gate 14
```

**Hard edges:** 1a before 1b; **2a depends on 1a only** (figures need no OCR and no schema change — a denied OCR gate 2/3 must not block figure work); 1b before 3a; 2a before 3b; 1a+3a before 4; 3b before 5a; 5a before 5b; 4 before 6 (for marks); 3b before 6 (figures); everything before 7. Research that changes no production file may run in parallel with 1a.

**Phase 1a is deliberately first** because it is the only step that fixes the verified silent-loss defect **without** a dependency, a model, a migration or an owner schema decision.

### 14.2 Per-phase specification

Each phase records: objective · prerequisites · in/out of scope · responsible agent · files owned · interfaces · **files that must not be edited** · required tests · measurable acceptance criteria · security/data-integrity implications · **failure and recovery** · independent verification · completion evidence · approval gates.

**Phase 0 — Reconnaissance.** `[V]` complete (the original plan). No production change. Completion evidence: the original plan + the audit + the review report.
*Full field set:* Objective = establish the real architecture, confirm gaps, define owners/contracts/sequence/gates; Prerequisites = none; In scope = inspection and planning; Out of scope = any code change; Responsible = `COORDINATOR` (+ `VERIFIER` read-only); Files = none modified; Interfaces = none; Must not edit = everything production; Tests = none (reconnaissance); Acceptance = the original plan's §1-§13 delivered with verified evidence; Security = no secrets printed, no document contents enumerated; Failure/recovery = not applicable (no state changed); Independent verification = `VERIFIER` re-checked the claims; Completion evidence = the original plan, the audit and the review report; Gates = none.
*Note:* the same fourteen fields are given explicitly for every phase below (phases whose work is deferred carry them marked not-applicable rather than omitted).

**Phase 1a — Per-page completeness detection, honest status, honest reporting.**
*Objective:* every page is either extracted or explicitly reported as unaccounted, and no document claims to be complete when it is not.
*Prerequisites:* gate 1 (scope), gate 4 (`partial` contract + invariant restatement), gate 23 (coverage-field decision if any new field is reported).
*In scope:* per-page decision inside the existing page loop; `ready`/`partial`/`error` verdict; the docstring/invariant restatement; consumer updates (§7.4); coverage reporting using only facts that can be told honestly.
*Out of scope:* OCR, any engine or dependency, figures, schema changes, per-page method/confidence claims.
*Responsible:* `BACKEND_AGENT`. *Files:* `documents/processing.py`, `documents/routes.py`, `documents/schemas.py`, `documents/insights.py`.
*Must not edit:* `chat/**`, `brain/**`, `graph/**`, `migrations/**`, `tests/**`, `src/**`, `requirements.txt`.
*Tests:* every transition (§7.6); mixed-PDF page accounting; scanned-only ⇒ `partial`; zero-content ⇒ `error`; no false `ready`; digital PDF unchanged (`tests/integration/documents/*`, `tests/unit/documents/test_phase3e_processing.py`).
*Acceptance:* 100 % of pages accounted for in the fixture set, **including a rotated-page fixture** (§15.2 — a rotated page that yields no text is an unaccounted page, so rotation is an accounting concern here, not only an OCR concern); `ready` never set with an unaccounted page; existing digital-format suites still pass; no change to chunk counts for digital PDFs; **reporting is status-only unless gate 23 selects option A or B** (no denominator is claimed otherwise — §8.2).
*Security/data integrity:* no new input parsing; no new file access; no status written outside the pipeline.
*Failure/recovery:* a page-level failure degrades the verdict, never the process; a raised exception keeps `error` semantics; a reprocess replaces rows atomically.
*Independent verification:* `VERIFIER` re-runs the fixtures and inspects the status transitions in the database.
*Completion evidence:* executed test output with exit codes, fixture results, the diff limited to the four files.
*Gates:* 1, 4, 23.
*Full field set:* Interfaces = the existing extractor return shape + `Document.status` + `DocumentOut`/insights payloads; Must not edit = `chat/**`, `brain/**`, `graph/**`, `migrations/**`, `tests/**`, `src/**`, `requirements.txt`.

**Phase 1b — OCR integration (gated).**
*Objective:* pages with insufficient native text are OCR'd when an approved engine is available, with provenance.
*Prerequisites:* gate 2 (engine + install + provisioning), gate 3 (option A/B/C), gate 13 (deployment change if the engine needs a system binary), gate 22 if deployment files must change.
*In scope:* one adapter interface (`documents/ocr.py`), per-page invocation condition based on real extracted characters, per-page records under the approved option, honest failure reasons.
*Out of scope:* changing the embedding model; OCR of pages with adequate text (a tested **negative** control); any hosted service without gate 16.
*Responsible:* `BACKEND_AGENT` (+ `DATABASE_AGENT` for option A).
*Tests:* scanned-only becomes searchable; mixed PDF complete; adequate pages never sent to OCR; OCR failure ⇒ `partial` with reason; retry replaces rather than appends; timeout/limit behaviour; rotated pages (§15.2).
*Acceptance:* per-page accounting preserved; every OCR page carries method + engine + confidence *if option A* (otherwise no such claim is made); measured per-page latency recorded; limits enforced.
*Security:* hostile-document bounds (page/pixel/time ceilings), no document content in logs, no egress without approval.
*Failure/recovery:* an engine failure degrades to `partial`; a crashed engine is reported, never retried into a loop; reprocess is idempotent.
*Verification:* `VERIFIER` + `SECURITY_AGENT` on the untrusted-input path.
*Gates:* 2, 3, 13, 16, 22.
*Full field set:* Files = `backend/documents/ocr.py` *(new)*, `backend/documents/processing.py`, `backend/documents/routes.py`, `backend/requirements.txt`, `backend/config.py` (BACKEND_AGENT), plus `models.py` + `migrations/versions/008_*.py` (DATABASE_AGENT, option A only) and `documents/page_extractions.py` *(new)* (BACKEND_AGENT); Interfaces = one adapter interface + the approved per-page record; Must not edit = `chat/**`, `brain/**`, `graph/**`, `src/**`, `tests/**`; Completion evidence = executed suite output with exit codes, per-page fixture measurements, the chosen option recorded, provisioning evidence (path + artifact only, never secrets).

**Phase 2a — Figures, captions, assets (gated; no DDL).**
*Objective:* figures survive extraction, persistence, storage and citation.
*Prerequisites:* Phase 1a; gate 5 (figure scope); gate 22 only if assets require a deployment change (they do not — assets live in the upload volume).
*In scope:* the three vocabulary edits (§10.2); image enumeration in place of the skip; caption association; deterministic asset write; `figure` elements through the existing writer.
*Out of scope:* image understanding, OCR of figure text, generated figures, serving assets to anonymous clients.
*Tests:* figure element emitted with page/bbox/caption; caption-less figure still emitted; asset written inside the document subtree; asset deleted with the document and replaced on reprocess; text extraction and table behaviour unchanged; existing structure tests pass.
*Acceptance:* every detected image is accounted for (element + asset) or explicitly reported as failed; no existing element type changes behaviour.
*Security:* containment, symlink/reparse refusal reused; no new path composition; tenant-scoped writes.
*Failure/recovery:* a failed asset write does not fail the document; it reports `figureRef=None` with a reason.
*Verification:* `VERIFIER` + `SECURITY_AGENT` (path/tenancy).
*Gates:* 5.
*Full field set:* Responsible = `BACKEND_AGENT`; Files = `backend/documents/figures.py` *(new)*, `backend/documents/processing.py`, `backend/documents/parser.py`, `backend/documents/routes.py`, `backend/documents/structure.py`, `backend/storage/file_store.py`; Interfaces = `ExtractedElement`, `ParsedElement`, the structure writer, the new read/serve helper; Must not edit = `chat/**`, `brain/**`, `graph/**`, `migrations/**`, `src/**`, `tests/**`; Completion evidence = executed test output with exit codes, emitted-element and asset listings, caption-association fixtures.

**Phase 2b — Equations — DEFERRED.** `[F]` Nothing is implemented; nothing is claimed (§10.3). Gate 18.
*Full field set:* Responsible = none (no phase runs); Files = none — `backend/documents/equations.py` is **withdrawn**; Interfaces = none; Must not edit = all production files stay untouched for this item; Tests = only the preservation assertion of §15.1 row 11; Acceptance = text is preserved verbatim or the page is reported; Completion evidence = not applicable while deferred; Gates = 18.

**Phase 3a — OCR text in retrieval.** *Objective:* OCR-derived text is retrieved like native text and labelled. *Prerequisites:* Phase 1b. *Responsible:* `AI_AGENT`. *Files:* `chat/rag.py`, `chat/routes.py`. *Tests:* a question answerable only from a scanned page retrieves it; `extractionMethod` present; abstention unchanged. *Acceptance:* correct document + page for OCR-only content; no fabricated similarity.
*Full field set:* Responsible = `AI_AGENT`; Files = `backend/chat/rag.py`, `backend/chat/routes.py`; Interfaces = `SourceChunk`/`SourceOut` (`extractionMethod`); Must not edit = `documents/**`, `graph/models.py`, migrations, `src/**`, `tests/**`; Security = OCR text is untrusted data (injection tests, §16.3); Failure/recovery = a missing or failed OCR record degrades to native-only evidence, never fabricated text; Verification = `VERIFIER`; Completion evidence = executed test output with exit codes and the retrieved fixture source (document + page); Gates = none beyond C-1b.

**Phase 3b — Figure evidence in retrieval (gated).** *Objective:* a figure question returns the right figure, document and page. *Prerequisites:* Phase 2a; gate 6. *Tests:* caption-mediated path; element-type-aware retention; explicit figure intent; caption-less figure (no invented caption); asset unavailable ⇒ honest failure; cross-tenant asset request ⇒ 404; ranking reports no fabricated score. *Acceptance:* correct asset for a known fixture; zero fabricated captions; **exactly one chunk contains the caption text** (no RRF double-count); existing retrieval regressions pass. *Verification:* `VERIFIER` + `SECURITY_AGENT` (IDOR).
*Full field set:* Responsible = `AI_AGENT` (retrieval) + `BACKEND_AGENT` (asset route and read/serve helper); Files = `backend/chat/rag.py`, `backend/chat/routes.py`, `backend/graph/service.py`, `backend/brain/adapters.py`, `backend/documents/routes.py`, `backend/storage/file_store.py`; Interfaces = Contract C fields + `figureRef` resolution; Must not edit = `documents/processing.py`, `parser.py`, migrations, `src/**`, `tests/**`; Security = IDOR/BOLA on the asset route (server-side ownership, 404), containment on read; Failure/recovery = unreadable asset ⇒ caption-only evidence + explicit unavailability; Completion evidence = executed test output with exit codes, fixture asset id/document/page, negative-control results (unrelated figure not substituted); Gates = 6.

**Phase 4 — Mark-aware answers (gated).** *Objective:* genuinely different, source-grounded answers for 6/8/10/15 marks — or an honest unavailable state. *Prerequisites:* Phases 1a/1b/3a; gates 7, 8, 21. *Files:* `chat/answer_composer.py` *(new)*, `chat/routes.py`, `brain/adapters.py`; `config.py` by `BACKEND_AGENT`. *Must not edit:* the trained QA weights; the extractive limits. *Tests:* four structures measurably different by rubric; grounding; unsupported questions; insufficient evidence; model-unavailable fallback (§11.3); `marks=None` identical to today. *Acceptance:* ≥ the owner-approved thresholds per metric, or the feature stays disabled and the fallback is what ships. **Per-section evidence linkage is asserted** (`sectionEvidence`, §12.1). *Failure/recovery:* degrade to extractive with `degraded=true`; never fabricate.
*Full field set:* Responsible = `AI_AGENT` (+ `BACKEND_AGENT` for the `config.py` field); Files = `backend/chat/answer_composer.py` *(new)*, `backend/chat/routes.py`, `backend/brain/adapters.py`, `backend/config.py`; Interfaces = Contract D request/response; Must not edit = `backend/models/documind-qa/**` (weights), the extractive limits in `chat/qa_model.py`, migrations, `src/**`, `tests/**`; Security = no egress unless gate 16 approves it, instruction/data separation (§16.3), secrets env-only; Verification = `VERIFIER` + `EVALUATION_AGENT` metrics + `SECURITY_AGENT` (egress/injection); Completion evidence = executed test output with exit codes, the model decision record, measured metrics with the owner-approved thresholds named; Gates = 7, 8, 21.

**Phase 5a — Diagram detection + existing-figure retrieval (gated).** *Objective:* detect diagram need and return the right existing figure. *Prerequisites:* Phase 3b; gate 9. *Tests:* detection precision/recall on a fixture set; trigger recorded; correct figure or an explicit "no figure found" state. *Acceptance:* no unrelated figure substituted — including the **unrelated-but-similar-figure negative control** (§15.1 row 30); failures reported.
*Full field set:* Responsible = `AI_AGENT`; Files = `backend/brain/classifier.py`, `backend/brain/adapters.py`, `backend/chat/routes.py`; Interfaces = the detection signal + the 3b figure evidence; Must not edit = `documents/**`, migrations, `src/**`, `tests/**`; Security = retrieved figure must belong to the authenticated user's document (ownership re-checked); Failure/recovery = detection without a suitable figure yields an explicit "no figure found" state, never a substitute; Verification = `VERIFIER`; Completion evidence = executed test output with exit codes, detection precision/recall on the fixture set, the recorded trigger for each detection; Gates = 9.

**Phase 5b — Diagram generation/rendering (gated, optional).** *Objective:* generate and render only when justified, validated and safe. *Prerequisites:* Phase 5a; gates 9, 10, 11, 22. *Tests:* invalid markup rejected (fail closed); no script/remote fetch; rendering failure reported, never presented as success; attribution present; `includeDiagram`/UI only now (§12.3). *Acceptance:* the highest-risk capability ships only with the smallest-surface renderer approved.
*Full field set:* Responsible = `BACKEND_AGENT` (renderer, on `COORDINATOR`-approved ownership) + `AI_AGENT` (composition) + `FRONTEND_AGENT` (display); Files = `backend/diagrams/render.py` *(new package)*, `backend/main.py`, `backend/requirements.txt`, `backend/chat/routes.py`, `src/**`; Interfaces = Contract E (`DiagramPayload`) + the deferred `includeDiagram` field; Must not edit = untrusted-input-free paths only — never render arbitrary HTML/script; Security = XSS/injection/SSRF rejected and fail-closed, CSP, no `dangerouslySetInnerHTML`; Failure/recovery = validation or rendering failure is reported, never presented as success; Completion evidence = executed test output with exit codes, negative-fixture rejection results, the approved renderer decision; Gates = 9, 10, 11, 22.

**Phase 6 — Frontend integration (gated).** *Objective:* users see honest state. *Prerequisites:* Phases 1a (status), 2a/3b (figures), 4 (marks), gates 4, 12, 23. *Files:* `src/**`, `package.json`. *Tests:* status mapper exhaustiveness; `partial` rendering with what is missing; marks reach the backend; figures render through the asset route; unavailable states for marks/diagrams; a11y; build passes. *Acceptance:* no inert control remains (§12.3); no unsafe HTML; empty/loading/error/unavailable/unknown states all represented.
*Full field set:* Responsible = `FRONTEND_AGENT`; Files = `src/pages/WorkspacePage.tsx`, `src/context/WorkspaceContext.tsx`, `src/lib/api.ts`, `src/types/index.ts`, `src/pages/SettingsPage.tsx`, `package.json`; Interfaces = Contracts C/D/F as amended (including `sectionEvidence` and `partial`); Must not edit = `backend/**`, `.env`, `dist/**`; Security = user/document content and diagram output are untrusted (no raw HTML injection, mirror real backend state); Failure/recovery = each new state (unavailable, unknown, partial) is explicitly rendered rather than silently falling through; Verification = `VERIFIER` (+ `npm run build`); Completion evidence = build output with exit code, the status-mapper test results, a11y checks; Gates = 4, 12, 23.

**Phase 7 — Integration, evaluation, security, verification.** *Objective:* demonstrated end-to-end behaviour. *Prerequisites:* all phases; gate 14 for live E2E; gate 21 for metric thresholds. *Deliverables:* executed suites with recorded exit codes, evaluation report, independent security review, independent verification, documentation update. *Acceptance:* every capability carries observed status; anything unrunnable is reported **BLOCKED**, never as a pass; `[V]` integration tests self-skip or refuse without a database (`tests/fixtures/integration_db.py:294`, `tests/fixtures/disposable_db.py:36`) and `test_real_e2e_validation` errors by design — a skipped suite is never a pass.
*Full field set:* Responsible = `TEST_AGENT` + `EVALUATION_AGENT` (+ `SECURITY_AGENT` audit, `VERIFIER` independent); Files = `backend/tests/**`, `backend/pytest.ini`, `backend/evaluation/**`, `backend/architecture/**`; Interfaces = none (verification only); Must not edit = production source, migrations, `src/**`; Security = no destructive database test, no production data, no guard bypass; Failure/recovery = a failing check is fixed at its cause or reported, never suppressed; Completion evidence = executed command lines with exit codes, per-capability observed status, the blocked-item list, metric values with thresholds named; Gates = 14, 21.

### 14.3 Failure and recovery, per phase (REV-008)

For **every** phase: (a) a failed phase leaves the repository at the previous phase's state; nothing partially migrated and no document left `ready`; (b) application rollback = revert the code change (the derived data is rebuildable by reprocessing); (c) database recovery = forward-fix in preference to downgrade (§17.3); (d) a phase that cannot meet its acceptance criteria is **not** marked complete and its gate stays closed; (e) an incident record is written to `backend/architecture/**` by `COORDINATOR`.

---

## 15. Measurable Acceptance Criteria and Required Tests

### 15.1 Acceptance scope (each claimed test must be run later; **none is claimed to pass here**)

| # | Scenario | Phase | Evidence that will demonstrate success |
| --- | --- | --- | --- |
| 1 | Digital PDF unchanged | 1a | existing suites pass; identical chunk counts on a reference fixture |
| 2 | Scanned-only PDF | 1a/1b | 1a: `partial` (+ explicit reason); 1b: searchable content with `extractionMethod='ocr'` |
| 3 | Mixed digital/scanned PDF | 1a | every page accounted for; status `ready` only when complete |
| 4 | Rotated scan (90/180/270) | 1b | page accounted for; rotation reported; §15.2 |
| 5 | Low-quality scan | 1b | page accounted for with confidence recorded (option A) or explicit unaccounted status |
| 6 | OCR failure | 1b | `partial` with reason; no invented text; retry replaces |
| 7 | Page-level provenance | 1b | per-page method/engine/confidence retrievable **iff option A** |
| 8 | Table structure preservation | 1a/2a | table cells/rows unchanged; `document_table_rows` counts unchanged |
| 9 | Figure extraction + caption linkage | 2a | figure element with page/bbox; caption verbatim; no invented caption |
| 10 | Figure retrieval (caption-mediated and explicit) | 3b | correct asset + document + page for a known fixture |
| 11 | Equation handling | — | **deferred**: text preserved verbatim; **no** notation claim (§10.3) |
| 12 | Structural vs ordinary retrieval | 3a/3b | path provenance reported; no fabricated similarity |
| 13 | Citation correctness / source-page identity | 3b | document + page of the returned evidence match the fixture |
| 14 | Unsupported question / insufficient evidence | 1a-4 | existing gate outcome preserved; no invented answer |
| 15 | Extractive vs generated answers | 4 | `answerFormat` distinguishes them; extractive unchanged when `marks=None` |
| 16 | Requested marks (where supported) | 4 | rubric-based structural difference; never word-count padding |
| 17 | Generation unavailable/denied | 4/6 | honest fallback + explicit UI state (§11.3) |
| 18 | Document status transitions | 1a | every row of §7.3, plus the forbidden transition |
| 19 | Existing-document audit + safe reprocessing | 1a/1b | audit report (read-only) + bounded reprocess with before/after coverage |
| 20 | Authorization / tenant-document isolation | 2a/3b | foreign asset request ⇒ 404; server-side ownership resolution |
| 21 | Prompt injection in uploaded/retrieved content | 4 | document text cannot redirect instructions, tools or data access |
| 22 | Rate limiting / inference-cost controls | 1b/4 | limits enforced and observable (§16.1) |
| 23 | Duplicate prevention / idempotency | 1b/2a | a second reprocess produces identical derived rows, no duplicates |
| 24 | Frontend/backend contract compatibility | 6 | exhaustive status mapper; `marks=None` unchanged; `topK` bounds |
| 25 | Startup/deployment failure | 1b/17 | missing model artifact fails closed with a clear message (preserved behaviour) |
| 26 | Recovery and rollback | 17 | forward-fix path documented and exercised on a disposable database only |
| 27 | Cross-**page** retrieval (evidence must be combined from different pages) | 3a/3b | returned evidence ids span the expected pages; answer cites both |
| 28 | Cross-**document** retrieval (two of the user's documents) | 3a/3b | evidence from both documents with correct ids; ownership respected |
| 29 | Cross-**table** retrieval (cells from different rows) | 3a/3b | row evidence from multiple rows with `rowIndex` intact |
| 30 | Unrelated-but-similar figure present in the corpus (**negative control**) | 3b/5a | the unrelated figure is **not** returned or substituted; the correct figure or an explicit "no figure found" state |
| 31 | OCR returns **garbage** text (not a failure — low-quality output) | 1b | page is accounted for but marked OCR-derived; no silent promotion to native quality; retrieval provenance retains the method |

### 15.2 Rotation and low-quality scans — measurable rules (REV-017)

`[P]` For each rotated/low-quality fixture the **only** acceptable outcomes are: (a) the page's text is recovered (rotation detected and applied or OCR succeeded) and the page is accounted for; or (b) the page is explicitly reported as unaccounted, with `rotation_applied`/`failure_reason` recorded where option A is in force. **Silent omission is a failure of the test.** Measurable acceptance: 100 % of pages accounted for (a count, not a quality threshold); accuracy thresholds for OCR text are **owner-approval items** (gate 21) because no baseline exists. If the owner prefers to defer rotation handling, that must be recorded as a deferral (gate 17) — not left implicit. **Phase placement:** rotation is asserted twice — as an **accounting** rule in Phase 1a (a rotated page that yields no text must be reported as unaccounted, never silently dropped) and as a **handling** rule in Phase 1b (rotation detected and applied, or the page reported with its reason).

### 15.3 Metrics (separate per area; thresholds = gate 21, none invented here)

| Area | Metric | Method |
| --- | --- | --- |
| Extraction | per-page character coverage; OCR CER/WER | fixture ground truth, per engine candidate |
| Retrieval | Recall@K, MRR, path agreement, evidence coverage | existing `backend/evaluation/**` conventions |
| Generation | rubric structural completeness; accuracy vs evidence; redundancy | rubric per mark level |
| Grounding | unsupported-claim rate; per-section evidence linkage | claim→evidence inspection |
| Citations | document + page correctness | known-answer fixtures |
| Figures | detection precision/recall; retrieval correctness; asset-route rejection rates | fixture set |
| Diagram | invalid-source rejection; rendering failure reporting | negative fixtures |
| Reliability | p50/p95 latency per stage; failure/abstention rates; idempotency violations | instrumentation |

`[V]` evaluation is **not** pytest here: `backend/evaluation/**` is `EVALUATION_AGENT`-owned research launched explicitly (`agents/evaluation-agent.md`).

---

## 16. Security, Resource-Control, Idempotency and Failure-Recovery Requirements

### 16.1 Resource controls (REV-010) — values are owner decisions (gate 21)

`[V]` no rate limiter or inference limit exists today, and the deployment runs **one** uvicorn worker (`docker-entrypoint.sh:49`), so blocking work blocks the whole service. Required controls:

| Control | Requirement | Owner | Notes |
| --- | --- | --- | --- |
| OCR page ceiling | max pages processed per document | `BACKEND_AGENT` | value: owner-approved, benchmarked |
| OCR per-page timeout | wall-clock ceiling per page | `BACKEND_AGENT` | must not be raised by a document |
| Image/pixel ceiling | max pixels decoded per page | `BACKEND_AGENT` | hostile-document bound |
| Ingestion concurrency bound | bounded executor for OCR/figure work in `backend/documents/**` | `BACKEND_AGENT` | the event loop must not be blocked; async boundaries preserved |
| Composition concurrency bound | bounded generation concurrency + per-request token/time budget | `AI_AGENT` | applies only if gate 7 approves a generation model |
| Ask rate limit | requests per principal per window on `/api/chat/ask` | `BACKEND_AGENT` — implemented as middleware in `backend/main.py`; it must **not** require an edit to `backend/chat/**`, which is `AI_AGENT`-owned (`agents/backend-agent.md` Must Not Touch) | limit value: owner-approved |
| Generation token/time budget | per-request cap | `AI_AGENT` | only relevant if gate 7 approves generation |
| Request-size validation | existing 50 MB cap reused; `topK` bounds added | `BACKEND_AGENT`/`AI_AGENT` | `[V]` `config.py:max_upload_size_mb = 50` |

### 16.2 Idempotency and duplicate prevention (REV-010)

* `[V]` reprocessing deletes derived rows first (`documents/routes.py:258,286,694`); `structure.py` replaces inside a savepoint; row evidence is unique on `(document_id, table_element_id, row_index)`.
* `[P]` page records and figure assets must follow the same replace discipline; a second identical reprocess must produce identical derived state (a required test).
* `[P]` a retried ingest must not duplicate chunks, elements, rows, pages or assets; ingest is keyed by document id, never by client-supplied identity.
* `[P]` no bulk operation may be run twice concurrently on the same document (guard: status must not be `processing`).

### 16.3 Instruction/data separation (carried from the original plan, strengthened)

* Retrieved text is **data**. `[P]` the composition path must keep instructions structurally separate from evidence and must never place document text where the model can take it as an instruction; the model gains no tool, network or filesystem access.
* `[P]` required injection tests: a fixture document containing instruction-like text must not alter outcome classification, citations, ownership or tool behaviour.

### 16.4 Threat coverage (extends the original plan's §9, unchanged where it was already correct)

The original plan's thirteen-row security table remains valid and is now backed by these additions: the asset route is an IDOR/BOLA target resolved server-side with 404 for foreign documents `[P]`; path containment reuses `storage/file_store.py` `[V]` (no new ad-hoc path joining); diagram/answer output is never injected as HTML `[P]`; secrets stay env-only `[V]`; **no user document leaves the deployment** unless gate 16 authorises a specific service with UI disclosure `[D]`; no destructive database test is ever run against real data.

---

## 17. Deployment, Provisioning and Rollback Strategy (REV-015, N-002)

### 17.1 Provisioning order (mandatory)

`[V]` `docker-entrypoint.sh:19,29-31` refuses to start when a required model directory is absent (`require_dir`, `exit 1`), and models are read-only mounts. Therefore, for any newly required artifact:

1. Provision the artifact locally (operator action; agents may not write `backend/venv/**` or weight directories).
2. Mount it read-only at the expected path.
3. **Then** deploy the image that requires it.

Reverse order = a container that fails closed at boot. The fail-closed behaviour is **preserved deliberately** — it is a security property, not an inconvenience — and any change to it needs gate 13/22.

### 17.2 New-artifact decision

`[D]` For each new artifact (OCR model data, generation weights): is it **required** (fail closed) or **optional with degradation** (feature reports unavailable)? The revision recommends **optional-with-degradation for every new artifact** so a missing model degrades a feature instead of stopping the service — but this is the owner's call (gate 13).

### 17.3 Migration policy (REV-008)

* One linear head today `[V]` (`007_add_table_rows`); any new migration is additive-only with a real `downgrade()` that drops only what it created.
* **Forward-fix is the default.** A downgrade of a live database is permitted only under explicit owner authorization (gate 20) with a recorded backup step, because `AGENTS.md` forbids downgrading a live database without permission.
* Migrations are applied by the entrypoint before the API starts `[V]`; therefore a migration that fails must fail fast and visibly, never leaving a half-upgraded schema unreported.
* No destructive migration (drop column, drop table with data, type narrowing) may be authored as part of Phases 1a–6 without gate 3 and a separate risk note.

### 17.4 Deployment-file ownership (N-002)

`[D]` **Gate 22**: before any edit to `backend/docker-entrypoint.sh`, `backend/Dockerfile`, `compose.yaml` or `Dockerfile.frontend`, the owner must approve a `COORDINATOR`-owned amendment to `agents/**` naming the writer (recommended: `BACKEND_AGENT` for the backend entrypoint/image, `FRONTEND_AGENT` for the frontend image, `COORDINATOR` for `compose.yaml`). Until then these files are **frozen**.

---

## 18. Explicit Decisions Required from the User/Product Owner

**A recommendation is not authorization. None of the following is approved by this document.**

### Group A — OCR and document processing

| Gate | Decision | Options | Evidence needed | Recommended default | Blocked until decided |
| --- | --- | --- | --- | --- | --- |
| 1 | Phase 1 scope | 1a only / 1a+1b | this plan §7, §14 | 1a first (no new dependency, fixes silent loss) | all OCR work |
| 2 | OCR engine + install + provisioning | Tesseract (system binary) / RapidOCR-ONNX (reuses installed `onnxruntime`) / EasyOCR (reuses `torch`) / other | **measured** per-page coverage, CER, latency, memory, licence, offline capability, Windows/container parity | none asserted; measure first (§14 Phase 1b) | Phase 1b |
| 3 | Provenance storage | A new table / B one column / C no DDL | this plan §8 | A if OCR is in scope, else B | Phase 1b |
| 4 | `partial` + `ready` redefinition (invariant reversal) | approve / reject (then the alternative is `error` for any incomplete document) | this plan §7 | approve (honest, and the alternative hides incompleteness) | Phase 1a |
| 5 | Figure scope | emit + store figures / omit | this plan §10.1 | approve (no DDL required) | Phases 2a, 3b |
| 13 | Deployment change for a new artifact | required (fail closed) / optional (degrade) | §17 | optional-with-degradation | Phases 1b, 5b |
| 15 | Image uploads (standalone images) | in scope / PDF-DOCX-TXT only | §14 | out of scope initially (changes validation + OCR surface) | Phase 1b |
| 16 | Data-egress posture | keep "no document leaves the deployment" / authorise a named service | §11, §16.4 | keep local-only | Phase 1b/4 |
| 17 | Historical audit + reprocessing | approve policy / defer | this plan §9 | approve the read-only audit; approve reprocessing separately after seeing the report | C-15, any reprocess |

### Group B — Data model and migrations

| Gate | Decision | Options | Evidence | Recommended default | Blocked |
| --- | --- | --- | --- | --- | --- |
| 3 | (as above) schema change | A / B / C | §8 | A or B | C-2/C-2b |
| 20 | Downgrade authority | who may authorise a live downgrade | `AGENTS.md` §06 | forward-fix default; downgrade only with explicit owner sign-off | any rollback decision |
| 23 | Coverage reporting fields (N-001) | add `sourcePageCount`/`pagesMissing` (needs B or A) / report nothing beyond status | this plan §2.4, §8 | add the fields — otherwise the UI can only say "incomplete" | C-12 |
| — | Backfill strategy for existing rows | see gate 17 | §9 | audited, bounded, approval-gated | any backfill |

### Group C — Answer generation

| Gate | Decision | Options | Evidence | Recommended default | Blocked |
| --- | --- | --- | --- | --- | --- |
| 7 | Introduce a generation model? | local open-weight / hosted API / none | measured capacity + latency + quality; egress decision (gate 16) | none — **not feasible to recommend** until measured `[B]` | Phase 4 |
| 8 | Marks contract | `{6,8,10,15}`, `topK` bounds, `answerFormat`, `marksSupported` | §12.1 | approve the additive shape; owner sets the `topK` ceiling | Phase 4/6 |
| 21 | Metric thresholds (incl. OCR accuracy) | values per metric | measurement first | none invented; proposed after measurement | Phase 4/7 |

### Group D — Multimodal capabilities

| Gate | Decision | Options | Evidence | Recommended default | Blocked |
| --- | --- | --- | --- | --- | --- |
| 6 | Figure evidence contract | approve additive fields + retrieval mechanism / defer | §10.1 | approve (no schema change) | Phase 3b |
| 9 | Diagram scope | detect + retrieve only / include generation | §10.1, §14 Phase 5 | **detect + retrieve only** initially | Phases 5a/5b |
| 10 | Renderer choice | validated source + client render / server render / own deterministic renderer | supply-chain + injection surface | own deterministic structured→SVG (smallest surface) if generation is approved | Phase 5b |
| 11 | Diagram package ownership amendment | approve / reject | `[V]` ownership layer (`agents/*.md`) | approve only if 5b proceeds | C-10, **C-18** |
| 18 | Equations | defer / specify representation first | §10.3 | **defer** (no claim of support) | equations |
| 19 | `includeDiagram` field timing | defer to 5b / add early with rejection semantics | §12.3 | defer to 5b | Phase 4 contract |

### Group E — Deployment and operations

| Gate | Decision | Options | Evidence | Recommended default | Blocked |
| --- | --- | --- | --- | --- | --- |
| 12 | Frontend test runner | approve dependency / no runner | `[V]` no runner exists | approve (a status mapper and figure rendering need tests) | Phase 6 |
| 14 | Authorised disposable database + server | provide / remain blocked | `[V]` the project's own guard refuses creation | provide a disposable environment | Phase 7 E2E |
| 22 | Deployment-file ownership (N-002) | approve amendment / freeze | §2.4, §17.4 | approve the amendment when a deployment change is actually needed | C-16 |
| — | Bulk jobs / production data changes | approve specific run / none | §9 | none until a report exists | any bulk work |

**Consolidated gate list:** 1-5, 6-12, 13-16, 17-23 as numbered above (the original plan's 16 checklist items are preserved as 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16; this revision adds 17 (historical reprocessing), 18 (equations), 19 (`includeDiagram` timing), 20 (downgrade authority), 21 (metric thresholds), 22 (deployment-file ownership), 23 (coverage fields)).

---

## 19. Deferred Capabilities and Unsupported Behaviours

Nothing in this list is implemented, partially implemented, or claimed. `[F]`/`[V]` as marked.

| Capability | Status | Wording that must be used |
| --- | --- | --- |
| Scanned-PDF OCR | `[V]` not implemented; `[F]` until gate 2 | "not supported; scanned pages are reported as unaccounted" |
| Per-page OCR provenance | `[F]` until gate 3 | "not recorded" unless option A is approved |
| Figure extraction/retrieval | `[F]` until gates 5, 6 | "not supported" |
| Equation notation / math recognition | `[F]` gate 18 | "equation text may survive verbatim as plain text; equations are **not** understood or represented" |
| Diagram requirement detection | `[F]` until gate 9 | "not implemented" |
| Diagram generation / rendering | `[F]` until gates 9-11 | "not available" |
| Figure/multimodal evaluation | `[V]` a research guard exists and forbids premature use | "multimodal evaluation is declared but must not be used until real figure/equation support exists" (`backend/evaluation/schemas.py:17`; supported-vocabulary list at `backend/evaluation/datasets/structure_discriminating_v1.py:91`) |
| Mark-wise (6/8/10/15) answers | `[F]` until gates 7, 8 | "extractive answers only; marks-based answers are not available" |
| Long-form answer generation | `[F]` gate 7 | "not implemented" |
| Image (non-PDF) uploads | `[F]` until gate 15 | "PDF, DOCX and TXT only" |
| `structure-v2` chunker as default | `[V]` candidate, default `legacy` (`config.py:65-68`) | "the default chunker remains legacy" |
| Table-row evidence band | `[V]` implemented, default OFF (`chat/rag.py:636-643`) | "present but disabled by default" |
| Live end-to-end verification | `[B]` | "blocked: no PostgreSQL, no live server, no authorised disposable database" |
| Frontend marks/figure/partial UI | `[F]` until phases 4/6 | "not implemented" |
| Inert depth control | `[V]` exists and is inert (`SettingsPage.tsx:281-288`) | "currently has no effect on answers" |

---

## 20. Change Log — Revision to Finding

| Revision entry | Change | Finding(s) | Section |
| --- | --- | --- | --- |
| R-01 | Figure retrieval path fully specified (two paths, linkage, ranking honesty, assets, failure matrix) | REV-001 | §10.1 |
| R-02 | Lifecycle contract: statuses, transitions, consumers, failure/retry, transition tests; invariant reversal stated | REV-002, REV-013, REV-014 | §7 |
| R-03 | Existing-document audit + reprocessing policy with read-only tooling and approval gate | REV-003 | §9 |
| R-04 | Provenance storage reduced to three evidenced options; "no migration" claim withdrawn | REV-004, N-001 | §8 |
| R-05 | `documents/structure.py` (+ `tables.py` precedent) added to affected files | REV-005 | §13.1 |
| R-06 | Equations deferred; `equations.py` and its Phase 2 deliverable removed | REV-006 | §10.3, §19 |
| R-07 | `figure` reclassified EXTEND with three named edits | REV-007 | §10.2 |
| R-08 | Per-phase failure/recovery + migration forward-fix policy + downgrade gate | REV-008 | §14.3, §17.3 |
| R-09 | `config.py` → `BACKEND_AGENT`; `chat/routes.py` toucher list corrected | REV-009 | §13.2 |
| R-10 | Rate limits, bounded retries, idempotency requirements (values owner-approved) | REV-010 | §16 |
| R-11 | `includeDiagram` removed from the contract until the capability exists; inert controls forbidden | REV-011 | §12.3 |
| R-12 | Honest denied/unavailable generation behaviour specified | REV-012 | §11.3 |
| R-13 | Provisioning order + fail-closed preservation; optional-with-degradation recommendation | REV-015 | §17 |
| R-14 | Phases split 1a/1b, 2a/2b, 3a/3b, 5a/5b with independent exit criteria | REV-016 | §14 |
| R-15 | Rotation/low-quality acceptance rules made measurable | REV-017 | §15.2 |
| R-16 | Verified ownership strengths and minimal execution groups preserved | REV-018 | §13.4 |
| R-17 | Original plan's stale baseline corrected; 22 evidence claims re-verified; its digest mismatch recorded | REV-019 | §2.2, §2.3 |
| R-18 | `insights.pageCount` semantics discovered and corrected in the reporting design | N-001 | §2.4, §8 |
| R-19 | Deployment files' missing ownership recorded as a gate | N-002 | §2.4, §13.1, §17.4 |
| R-20 | Independent verification round performed after drafting by two read-only reviewers; 22 findings raised and **all corrected**: figure data-path completeness (bbox fields), caption-authority rule, asset read/serve helper, corrected line citations, corrected `agents/frontend-agent.md` attribution, single-owner resource controls, phase field completeness, rotation in Phase 1a, cross-page/document/table + similar-figure + OCR-garbage test cases, `sectionEvidence` in the contract, non-paged status rule, gate/row cross-references | verification round | §2.3, §5, §7.2, §9.2, §10.1-§10.4, §12.1, §13.1, §14.1-§14.2, §15.1-§15.2, §16.1, §18, §19 |
| R-21 | Two corrections of record: (a) the review report's quotation "Do not add decorative controls" does not exist in `agents/*.md` and is replaced by the rule that does (`agents/frontend-agent.md:23` + `AGENTS.md` §03); (b) the original plan's claim that figure bboxes are already available was wrong — element bboxes are never populated today, so the figure work needs a new data path | REV-011, REV-019, V1-2, V1-9 | §4, §10.2 |

**Closing statement.** This is a **plan revision only**. No production file, test, schema, migration, dependency, model, configuration, frontend asset or agent contract was modified; nothing was installed, downloaded, provisioned, migrated, staged, committed or pushed; the original plan and the review report are untouched; **no phase was started and no gate was opened**.

**Stop and wait for owner decisions on gates 1–23 before any implementation.**

---

## Integrity and Validation of This Revision

| Check | Result |
| --- | --- |
| Revised plan exists at the required path | `[V]` `backend/architecture/DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_REVISED_2026-10-14.md` (destination was verified free before writing; nothing overwritten) |
| All 20 required sections present, in order | `[V]` §1-§20, verified by heading scan |
| Finding coverage | `[V]` REV-001 … REV-019 each have a disposition with rationale and evidence; plus N-001, N-002 |
| SHA-256 recorded and verified after the final edit | `[V]` recorded above; computed with the digest line excluded (`grep -v '^Plan SHA-256' <file> \| sha256sum`), because that line is the only self-referential content |
| Original plan unchanged | `[V]` SHA-256 `fb3c7fea…` before and after |
| Review report unchanged | `[V]` SHA-256 `e6c5a52c…` before and after |
| Production files changed by this task | `[V]` **no** — no source, test, schema, migration, dependency, model or frontend file written |
| Database / migrations modified | `[V]` **no** — no connection, no migration, no data change |
| Dependencies / models changed | `[V]` **no** |
| Git HEAD | `[V]` unchanged `6baaa2a0773df66e5fb26814afbe67647fb43435` |
| Staged / committed / pushed | `[V]` none |
| Pre-existing working-tree changes | `[V]` preserved: 330 unstaged tracked changes untouched |
| Independent verification | `[V]` performed **after drafting** by two read-only verifier reviewers with different angles (technical feasibility vs ownership/process/testability). Outcome: **22 findings**, **all corrected** in the revision above (R-20/R-21); the verification round itself produced no file change other than this document |
