# DOCUMIND — MULTI-AGENT IMPLEMENTATION PLAN, REVISED (R2 — TARGETED CORRECTIONS, OPTION-B REPROCESSING DESIGN)

**Document ID:** `DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_REVISED_R2`
**Corrects:** `backend/architecture/DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_REVISED_R1_2026-10-14.md` (revision **R1**, digest `ddf439206111d632a411dced310186e02f471b8e08c7aac0a87f99c866e607b1` under R1's own stated convention — its `Plan SHA-256:` line excluded; full-file digest `ca4d20f4fe264d200860d2171d6705c60ae204aa74165ef0d9fdb2253f49a02a`) — R1 is **preserved unmodified** and remains the previous revision of record; R2 is a separate corrected revision, never an overwrite
**Revision of:** `backend/architecture/DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_REVISED_2026-10-14.md` (revision **R0**, digest `13cee3656a10c9fdbb99619d6040c6b108d5bf3ff1d531a626719179a9196455` under R0's own stated convention; full-file digest `5afce228a5b88351321dfb40c7c088f2b2fae398ed86eff1cc92b4a8b0cb4380`) and `backend/architecture/DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_2026-10-14.md` (the original plan) — both **preserved unmodified**
**Driven by:** `backend/architecture/DOCUMIND_MULTI_AGENT_PLAN_REVIEW_2026-10-14.md` (findings REV-001 … REV-019 against R0), the R1 correction pass (§3.1, C1-C4), the R1 verification rounds (§20, R-26 … R-29) and an **independent readiness audit of R1** whose findings `F-1 … F-13` are corrected here as **R2-01 … R2-06 (§3.2)**
**Owner decision incorporated (2026-10-14):** reprocessing is **OPTION B — write first, commit the new structure, then clean up the old assets** (§10.5). The previous committed structure stays usable if a replacement run fails before its commit. **This authorizes documentation only:** no implementation, schema change, migration, dependency or production edit.
**Date of revision and evidence verification:** 2026-10-14
**Scope of R2:** documentation-only corrections R2-01 … R2-06 (§3.2), the Option-B reprocessing design (§10.5), one **new owner gate (26)** for asset-identity persistence, and a cross-document consistency sweep. Preserve the nine-agent ownership layer, the phase sequence and every contract; no phase is added, none is split further, and no scope is expanded. Implementation remains unauthorized.
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

Plan SHA-256: `2faefa6e013cefd38f38e4abc019d412368448c9df16fc7998b12d56b7668bb0`

---

## 1. Purpose and Scope of This Revision

**Purpose.** Correct the four HIGH findings and the fifteen remaining findings of the independent review **in the plan text**, without redesigning the application and without changing a single line of runtime behaviour. The original plan's architecture, Contracts A–F and Phases 0–7 are retained wherever they remain valid; every correction is targeted and traceable to a finding (see §20).

**Purpose of revision R2 (this document).** R2 inherits the purpose above and adds one narrower job: correct the thirteen findings (`F-1 … F-13`) raised by an **independent readiness audit of R1**, and implement the owner's **Option-B** reprocessing decision. Its corrections are `R2-01 … R2-06` (§3.2) together with the verification-driven corrections `V2R-1 … V2R-8` (§3.2 note, §20 R-39…R-45). Scope is unchanged: no contract is added or removed, no phase is added or split, no capability is promoted to "existing", and the nine-agent ownership layer, the phase sequence and every pre-existing gate are preserved.

**History versus current design.** §3.1, §4, §20's `R-01 … R-30` and the four R1 reports record **R1's** correction pass as history. Where any of them describes the figure-asset lifecycle — deterministic `(document_id, sequence_index)` names, the created-vs-overwritten cleanup rule, or the "bytes overwritten" limitation — **§10.5 as rewritten in R2 supersedes them** and is the only current statement of that lifecycle.

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
| `backend/architecture/DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_2026-10-14.md` | `fb3c7fea88486fa5fbcd9203ebc0c38bace4c1e2b1150b0029f7831ea205d98b` (no self-digest line in that file, so this is its full-file digest) | the plan this document revises |
| `backend/architecture/DOCUMIND_MULTI_AGENT_PLAN_REVIEW_2026-10-14.md` | `e6c5a52c17bf333ca876ae0146c742d774506414070dd82859bff05fd8709f0f` (no self-digest line) | independent review (REV-001 … REV-019) |
| `…_PLAN_REVISED_2026-10-14.md` (**R0**) | `13cee3656a10c9fdbb99619d6040c6b108d5bf3ff1d531a626719179a9196455` — R0's stated convention (its `Plan SHA-256:` line excluded, reproduced for this revision); full-file digest `5afce228a5b88351321dfb40c7c088f2b2fae398ed86eff1cc92b4a8b0cb4380` | previous revision of record, preserved unmodified |
| `…_PLAN_REVISED_R1_2026-10-14.md` (**R1**) | `ddf439206111d632a411dced310186e02f471b8e08c7aac0a87f99c866e607b1` — R1's stated convention (its `Plan SHA-256:` line excluded); full-file digest `ca4d20f4fe264d200860d2171d6705c60ae204aa74165ef0d9fdb2253f49a02a` | the revision this document corrects, preserved unmodified |
| `backend/architecture/DOCUMIND_PLAN_R1_CORRECTION_REPORT_2026-10-14.md` | `b75422213da02f331058baf61480351bf1a82cca900b03e6390d477bae5d2c72` | R1 change list |
| `backend/architecture/DOCUMIND_PLAN_R1_VERIFICATION_REPORT_2026-10-14.md` | `17c1bc5c1b41cae4ad8475ea57f14dbee7ad3ef9407096c97f20f74629098c0c` | R1 independent verification (findings, dispositions, blockers) |

### 2.2 Repository state at R2's baseline `[V]`

| Item | Value |
| --- | --- |
| Repo root | `C:/Users/moham/OneDrive/Desktop/stitch_documind_futuristic_3d_ui` |
| Branch / HEAD | `main` / `6baaa2a0773df66e5fb26814afbe67647fb43435` |
| Staged changes | **0** |
| Unstaged tracked changes | **330** (pre-existing; 295 deletions + 35 modifications — **not** attributable to this task and left untouched) |
| Untracked files (repo-wide, `--untracked-files=all`) at R2's start | **850** / **723** under `backend/` (measured by this revision, with R0 + R1 + both R1 reports present); the full ledger 846/719 → 850/723 is in the integrity table below |
| Destination `…_REVISED_R2_2026-10-14.md` before writing | **Free** — no file existed, nothing overwritten (R2 was created as a copy of R1 and then edited; R1 itself was not modified) |
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
| 18 | Reprocess currently replaces rather than appends — **current behaviour only** | `[V]` `documents/routes.py:695-696` (chunk delete loop) and `:697-703` (up-front `delete(DocumentStructureElement)`, with its comment stating the intent), `structure.py:88-110` (savepoint delete-then-insert inside the writer). **Superseded for the proposed design by §10.5 (Option B: write → commit → clean up)** — this row records what the code does today, not what R2 specifies |
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
| 7 | `figure` reclassified as **EXTEND**, naming the **five vocabulary/parser edits** the change requires (R2 adds the chunk-path exclusion and the gated asset-identity item — §10.2 items 6-7) | REV-007 | §10.2 |
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

### 3.1 Correction pass R1 — the four defects corrected in this revision

These were found by inspection of R0 against the source, not reported by the review. Each is corrected **everywhere it occurs**, not only at its first appearance (§20 lists the entries).

| # | Defect in R0 | Correction made in R1 | Affected sections |
| --- | --- | --- | --- |
| **C1** | **Status contradiction.** R0's Phase 1a test list and the §15.1 acceptance table said a scanned-only PDF becomes `partial` in Phase 1a — but a scanned-only PDF has **zero** usable pages, and R0's own definitions make zero usable pages `error`. Two sections therefore asserted different verdicts for the same document. | One authoritative verdict function is now stated once (§7.2.1) and every other statement refers to it: `pages_usable == 0` ⇒ **`error`** (never `partial`), `1 <= pages_usable < pages_total` ⇒ `partial`, `pages_usable == pages_total` ⇒ `ready`, any raised step ⇒ `error`; a scanned-only document that OCRs fully becomes **`ready`**. `partial` vs `error` is preserved exactly: `error` requires *zero* usable pages. | §5, §7.2-§7.2.2, §7.5, §7.6, §14.2 (1a, 1b), §15.1, §15.2, §19 |
| **C2** | **OCR failure conflated with `partial`.** R0 stated in three places that an OCR failure ⇒ `partial` (verdict bullet, Phase 1b failure rule, §15.1 row), which is wrong when nothing else is usable and would let an entirely unreadable document be reported as "success with disclosure". | OCR failure is now a **coverage** event, not a verdict: verdict per §7.2.1. All-pages OCR failure ⇒ `error`/`ocr_failed_all_pages`; one-page failure with usable pages elsewhere ⇒ `partial`; OCR output below the usability minimum counts as an unaccounted page; raised runner ⇒ `error`/`pipeline_exception`. New test scenario added — **§15.1 row 32** (all-pages OCR failure) — plus the **rewritten row 31** (sub-minimum OCR output now counts as an *unaccounted* page; in R0 that row said the page was accounted for and OCR-derived). Rows 33-34 belong to correction C4, not C2 (attribution corrected in R2, F-11). | §7.5, §14.2 (1b), §15.1, §15.2 |
| **C3** | **Unstoreable persisted value.** R0 said a figure is persisted with `figureRef=None` *and a reason* when asset extraction fails, while also declaring "no schema change". `[V]` `document_structure_elements` has **no** column for a failure reason (and `content` is reserved for the verbatim caption); the claim was unstoreable. | The design no longer persists a failure: the figure **row is created only after its asset was written** (persist-last), `figureRef` is a **derived** value from the existing `(document_id, sequence_index)` columns (never stored), and an asset-write failure produces **no figure row** plus a **reported** (logged / ingestion-summary) diagnostic — with durable figure provenance explicitly routed to an owner decision (gate 25). No schema field was added and no migration was authorized. | §10.1 (steps 3/5, failure matrix), §10.5, §14.2 (2a), §16.2, §18 |
| **C4** | **Asset lifecycle assumed atomicity.** R0 described asset write + row persistence, deletion and reprocessing without stating ordering, partial-failure recovery, orphan handling, or the fact that `[V]` `delete_upload` **refuses non-regular files** (`storage/file_store.py:188-192`, `stat.S_ISREG`) and the project's own delete path is DB-first with **best-effort** file removal. | A complete, non-atomic-by-design lifecycle is specified in §10.5: file-first/DB-last ordering; defensive per-run cleanup **of the files that run created (never of a path that already existed)**; interrupted-run residue; per-file deletion via the **existing audited** primitive plus a new containment-checked listing helper; orphan reconciliation under approval; cross-tenant resolution impossible by construction; and the residual risk (an interrupted replace can leave an asset whose committed element came from the previous run) **stated as a limitation** with its own owner decision (gate 25). | §10.1, §10.5, §14.2 (2a), §15.1, §16.2, §18 |

**Identifier note:** the correction items above are labelled `C1`-`C4` (this revision's correction pass); they are a different namespace from the ownership-matrix rows `C-1a`-`C-18` in §13.1 (`C-4`, the withdrawn equations row, is not related to correction `C4`). Cross-references in this document always use the hyphenated form for matrix rows.

**C1/C2 semantics are compatible with the original plan's status definitions** (`uploaded`/`processing`/`ready`/`error` existed; `partial` is the revision's addition) and with every owner gate: no gate is closed or altered by this pass.

### 3.2 Correction pass R2 — the independent readiness audit's findings, corrected in this revision

An **independent readiness audit of R1** (two read-only reviewers plus coordinator shell measurements; the audit is summarised in `DOCUMIND_PLAN_R2_CORRECTION_REPORT_2026-10-14.md`) raised thirteen findings, `F-1 … F-13` (2 HIGH, 3 MEDIUM, 6 LOW, 2 INFORMATIONAL). R2 corrects them as follows. Each is corrected **everywhere it occurs**; §20 lists the entries (R-31 … R-38).

| # | Audit finding(s) | Defect corrected in R2 | Where | Owner approval needed? |
| --- | --- | --- | --- | --- |
| **R2-01** | **F-1 (HIGH)** | **Figure elements must not enter the ordinary text chunk/embed stream.** R1 added `figure` to the extractor vocabulary and parser maps but never excluded it from `chunk_text`, which emits one chunk per element (`[V]` `documents/routes.py:125,198`); a caption-bearing figure would therefore produce a **second** caption chunk and a caption-less figure an **empty** chunk, while Phase 3b's acceptance demanded "exactly one chunk contains the caption text". R2 adds the chunk-path exclusion as an explicit requirement (§10.2 item 6), states the `DocumentChunk.element_type` behaviour for **both** chunkers, forbids any "chunked exactly once" claim unless the data flow guarantees it, and adds five acceptance rows (§15.1 rows 35-39). | §5, §6, §10.1 (steps 3, 6b, failure matrix), §10.2 (item 6), §14.2 (2a, 3b), §15.1 | no |
| **R2-02** | **F-2 (HIGH)** + **owner decision: Option B** | **Reprocessing is write-first → commit → clean up, with a run-scoped asset set.** R1's §10.5 asserted this ordering as normative while the code the plan itself cites deletes derived rows **up front** (`[V]` `:695-703`), so the stated residue ("previous rows keep their slots with newer bytes") could not occur and the reconciling edit was unassigned. R2 states the design for all twelve required states, replaces deterministic document+sequence asset names with **run-scoped immutable** names, scopes cleanup to the **committed reference set**, defines crash/retry/orphan/corruption/concurrency behaviour, marks the delete-first behaviour as **current only**, assigns the edit to Phase 2a / `BACKEND_AGENT`, and adds **gate 26** for the one piece of persistence the guarantee needs (an asset identifier per element, or an asset table). | §6, §7.5, §9.2, §10.2 (item 7), **§10.5 (rewritten)**, §13.1 (C-3, C-3b), §14.2 (2a), §15.1 (rows 23, 34, 38, 39), §16.2, §18 (gate 26) | **yes** — gate 26 (additive column/table) plus gate 5 |
| **R2-03** | **F-3 (MEDIUM)** | **The deterministic asset-write contract is specified.** R1 defined read/serve, listing and deletion safety but never the write side, and left `<ext>` undefined. R2 fixes the format and extension **server-side** (never from document content), defines path derivation and containment, exclusive creation, temp-then-rename completeness, collision refusal, run association, the refusal to replace a referenced asset, and which primitives are reused versus extended. | §10.5 (write contract), §13.1 (C-3), §14.2 (2a), §16.4, §19 | no |
| **R2-04** | **F-4 (MEDIUM)** | **Status-reason visibility is a contract, not an assumption.** R1 said the reason is "recorded … at document level" while no option (B/C) can store one. R2 adds a **reason-visibility contract** distinguishing transient (ingestion response), logged, durably persisted, and later-API-visible; states explicitly that under options B/C the reason is **transient and not retrievable later**; keeps any durable reason behind gates 3/23; and restricts Phase 1a's acceptance criteria to what the approved storage contract can deliver. | §7.2 (new §7.2.3), §7.4, §8.4, §12.2, §14.2 (1a), §15.1 | only if a field/table route is chosen (gates 3/23) |
| **R2-05** | **F-5 (MEDIUM)** | **The rate-limit change has an owner, a file, a phase and a gate.** R1 required middleware in `backend/main.py` (§16.1) and made it an acceptance criterion (§15.1 row 22) while no matrix row and no 1b/4 phase file list contained that file (only C-10, Phase 5b, did). R2 adds matrix row **C-1c** (`BACKEND_AGENT`, `backend/main.py`, gate 21), lists the file in Phase 1b/4, and adds the missing multi-touch rows to §13.3 (`backend/main.py`, `backend/brain/adapters.py`). | §13.1 (C-1c), §13.3, §14.2 (1b, 4), §15.1 row 22, §16.1 | value only (gate 21) |
| **R2-06** | **F-6 … F-13 (LOW/INFORMATIONAL)** | Eight minimal consistency corrections: (a) `no_text_layer` **removed** from the accepted reason set as redundant, with `ocr_failed_all_pages` defined to include all-pages sub-minimum output; (b) a per-page OCR **timeout** or resource failure explicitly classified as a **page-coverage event**, not a pipeline exception, unless the runner itself raises; (c) §15.1 rows 25-26's phase references corrected and row 26 marked `[B]`; (d) §14.1's map redrawn so 2a/2b hang off 1a as the hard-edge text already stated; (e) §13.3's omissions fixed; (f) the change-log/report attribution for rows 31-34 corrected; (g) the delete-first line references tightened (`:695-703`); (h) the R0 digest attribution corrected with **both** conventions named. | §7.2.1, §7.5, §13.3, §14.1, §14.2, §15.1, §20, integrity table | no |

**Identifier note (unchanged):** `R2-01 … R2-06` are this revision's correction items; `C1-C4` are R1's correction items; `C-1a … C-18` are ownership-matrix rows. The three are different namespaces and are never interchanged.

**Verification-driven corrections (`V2R-1 … V2R-8`), all corrected here.** After the R2-01…R2-06 pass, a **separate read-only reviewer** (file access, no shell) inspected this file against the source and raised eight findings: **V2R-1 (HIGH)** — the chunk exclusion was specified at the wrong point for the `structure-v2` path, where `_merge_class` merges any non-table/non-list type as *prose* and the chunk type is computed over the merged group, so filtering the output object would have been too late; **V2R-2** — three matrix rows claimed migration `008`; **V2R-3** — the rate-limit file was still absent from Phase 1b/4's file lists and gate 21 from Phase 1b's gate list although the change log claimed otherwise; **V2R-4** — the consolidated gate paragraph and the closing line still described the pre-R2 gate set; **V2R-5** — R1-era text in §1/§3/§3.1 and the "five edits" counts read as current design; **V2R-6** — five asset-citation statements were unconditional although gate 26 allows a no-DDL fallback; **V2R-7** — the §16.2 idempotency wording contradicted §9.2/§15.1; **V2R-8** — one mis-citation. Each is corrected in this revision (§20 R-39…R-45) and recorded in `DOCUMIND_PLAN_R2_VERIFICATION_REPORT_2026-10-14.md`.

**No gate is closed, opened or altered by this pass except the addition of gate 26**, which is a *new* decision the corrected design requires because the Option-B guarantee needs one piece of persistence the current schema lacks.

---

## 4. REV-001 … REV-019 Disposition Matrix

Disposition vocabulary, as required: **FIXED IN PLAN** · **ACCEPTED / DEFERRED — OWNER DECISION REQUIRED** · **NOT APPLICABLE — EVIDENCE PROVIDED** · **UNRESOLVED — BLOCKS IMPLEMENTATION**.

| Finding | Disposition | Revised-plan section | Evidence / rationale | Remaining decision or blocker |
| --- | --- | --- | --- | --- |
| **REV-001** figure evidence has no workable indexing/ranking path | **FIXED IN PLAN** | §10.1 | `[V]` the old path seeds on section names only and drops empty-content elements (§2.3 #5). The revision specifies: caption stored as the figure element's `content` (`[V]` the column exists, `graph/models.py:186`), a caption-mediated semantic path, an element-type-aware structural path, an explicit linkage rule, honest ranking (`score` stays `0.0` for element/structural candidates as today), deterministic asset resolution, and four failure modes | none for design; **Phase 2a approval** required before implementation |
| **REV-002** `partial` reverses a documented invariant; consumers unenumerated | **FIXED IN PLAN** | §7 | `[V]` invariant text `documents/routes.py:5,7`; ten consumers enumerated with line numbers (§7.4); transitions and tests defined | gate **4** — owner must approve `partial` and the `ready` redefinition |
| **REV-003** no backfill policy for existing `ready` documents | **FIXED IN PLAN** | §9 | `[V]` silent loss reproduced in the audit and re-confirmed in the original plan §1.2; `[V]` reprocess already replaces its **database rows** atomically (§2.3 #18 — chunks and structure rows; figure assets are separately governed by §10.5 and are **not** part of that transaction) | gate **17** — approval required **before any audit run or reprocessing** |
| **REV-004** "no migration" option is not viable | **FIXED IN PLAN** | §8 | `[V]` `documents` has no suitable column (`models.py:22-57`); the element table cannot hold page records (`graph/models.py:162-205`, unique `(document_id, sequence_index)` `:202-205`); **N-001** shows today's insights cannot even supply a denominator | gate **3** — option A/B/C must be chosen by the owner |
| **REV-005** persistence layer missing from affected-file lists | **FIXED IN PLAN** | §13 (C-1a, C-1b, C-3) | `[V]` `documents/structure.py:79` is the only writer, imported at `documents/routes.py:53` | none |
| **REV-006** equations undefined | **ACCEPTED / DEFERRED — OWNER DECISION REQUIRED** | §10.3, §19 | `[V]` no equation representation exists in any contract; `ALLOWED_ELEMENT_TYPES` has no equation type. Deferral is honest; a claim of support would not be | gate **18** — owner decides: defer (recommended) or specify a representation first |
| **REV-007** `figure` classified REUSE | **FIXED IN PLAN** | §10.2 | `[V]` **five** vocabulary/parser edits required (§10.2 items 1-5): `processing.py:39` (`ALLOWED_ELEMENT_TYPES`), `parser.py:188` (`ELEMENT_TYPE_MAP` has no `figure`), `parser.py:176` (`EMITTED_ELEMENT_TYPES`), plus the two bbox data-path edits; `_public_element_type` raises otherwise (§2.3 #3). R2 adds a **sixth** requirement — the chunk-path exclusion (§10.2 item 6, R2-01) — and a seventh design item for asset identity (§10.2 item 7, gated) | gate **26** for asset citation |
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
| Document status honesty (no false `ready`) | `[V]` absent — mixed PDFs reach `ready` | `[P]` `partial` + coverage reporting per the §7.2.1 verdict function | 1a | 1, 4, 23 |
| Scanned-only PDF (no page has a text layer) | `[V]` reaches `ready` with **zero** content today | `[P]` **`error`** with reason `no_text_layer_ocr_disabled` in 1a — zero usable pages is **not** `partial`; in 1b `ready` when OCR succeeds on every page, `partial` when OCR recovers only some pages | 1a/1b | 1, 2, 4, 24 |
| Coverage reporting with a true denominator | `[V]` absent (`pageCount` is `max(page)` — N-001) | `[P]` **Phase 1a reports the status only**; any denominator requires option B (one column) or option A (per-page records) | 1b | 3, 23 |
| OCR of scanned pages | `[V]` not implemented (0 elements) | `[P]` adapter + selected engine, per page, tagged with its extraction method; per-page **confidence only under option A** | 1b | 2, 3 |
| Per-page OCR provenance (method/engine/confidence/failure) | `[V]` impossible in current schema | `[P]` persisted per page (option A) — or **not claimed** (options B/C) | 1b | 3 |
| Table extraction (cells/rows) | `[V]` implemented and tested | unchanged | — | — |
| Table-row retrieval | `[V]` implemented but default **OFF** (`DOCUMIND_TABLE_EVIDENCE`) | unchanged default; promotion is a separate measured decision | — | — |
| Figure elements emitted | `[V]` never emitted | `[P]` emitted with caption + page + bbox and a **run-scoped** asset, and **excluded from the ordinary text chunk/embed path** (§10.2 item 6) | 2a | 5 |
| Figure elements in the text chunk stream | `[V]` impossible (no figure element exists) | `[P]` **never** — a figure element is excluded from `chunk_text` and from the `structure-v2` chunk-object builder, so the caption stays a single ordinary chunk owned by its paragraph element (R2-01) | 2a | 5 |
| Figure **retrieval** | `[V]` impossible (no mechanism, no field) | `[P]` caption-mediated + element-level paths with honest ranking (**needs no asset and no schema change**) | 3b | 5, 6 |
| Figure **citation with an asset** (`figureRef` / asset route) | `[V]` absent | `[P]` only once an asset identifier can be persisted per element — otherwise figures are cited **without** an image, never with a substituted one | 2a/3b | 5, 6, **26** |
| Figure assets served safely | `[V]` absent — `storage/file_store.py` exposes `save_upload` `:31`, `delete_upload` `:137`, `cleanup_new_file` `:201` and containment helpers (`_is_link_or_reparse_point` `:80`, `_resolved_within` `:97`), but **no read/serve primitive and no deterministic write primitive** | `[P]` a new containment-checked **write** helper (run-scoped, exclusive, temp-then-rename) plus a containment-checked **read/serve** helper and an ownership-checked route | 2a/3b | 5, 6, 26 |
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
  ├─ figure enumeration + caption association + run-scoped asset write ← NEW (Phase 2a, gated)
  │     (figure elements are NOT added to the chunk list — §10.2 item 6, R2-01)
  └─ page-extraction records                 ← NEW only if option A is approved (Phase 1b)
        │
        ▼
parser boundary — extended vocabulary: "figure" added to ALLOWED_ELEMENT_TYPES,
                 ELEMENT_TYPE_MAP and EMITTED_ELEMENT_TYPES          ← Phase 2a
        │
        ▼
chunk + embed (unchanged FOR TEXT; captions are ordinary text and are already chunked
               by their paragraph element — figure elements are filtered OUT of this
               step so the caption has exactly one chunk, R2-01)
        │
        ▼
replace_document_structure (+ figures, unchanged writer)             ← Phase 2a
        │   write assets (run-scoped) → commit the new structure → then sweep the
        │   previous run's now-unreferenced files  ← Option B, §10.5 (R2-02)
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
5. **Replacement, not accumulation.** Re-ingest replaces **database** rows (chunks, structure elements, table rows, page records) atomically inside the savepoint (`[V]` precedent: `documents/structure.py:88-110`). **Filesystem state is never part of that transaction** (§10.5): assets are written **before** the commit under **run-scoped names that no committed element references**, the commit makes the new structure authoritative, and the previous run's files are swept **after** the commit — so the previous committed structure and its images survive any failed replacement (Option B, R2-02).
6. **Assets are tenant-contained and die with their document.**
7. **The caption is chunked exactly once.** A figure element carries the caption as an *association copy* only and is excluded from the chunk/embed path; the caption's own paragraph element remains the single ordinary chunk (R2-01).
8. **A committed structure never references bytes another run overwrote.** Asset names are run-scoped and immutable for the life of the run that wrote them; cleanup removes only files that **no** committed element references.
9. **Nothing is deleted before its replacement is committed.** No derived row and no asset file is removed on the strength of a run that has not committed.

---

## 7. Document-Processing Lifecycle and Status Contract

### 7.1 The invariant that changes — stated explicitly (REV-002)

`[V]` `documents/routes.py:5` currently documents: *"READY means actually searchable and complete … There is no degraded-ready state."* This revision **reverses part of that invariant** and must say so: a document with unaccounted pages is **never `ready`** — it becomes **`partial`** when at least one page is usable, and **`error`** when no page is (the verdict split is defined once in §7.2.1; §7.1 states the consequence, not a competing rule). The implementation must therefore update that module docstring in the same change (gate 4), because leaving the old sentence in place would contradict the new behaviour.

`[V]` the value itself needs **no DDL**: `status` is `String(20)` with no CHECK constraint (`documents/models.py:41-43`; migrations 000–007). The **contract** is what requires approval.

### 7.2 Status meanings

| Status | Meaning (proposed) | Set when | Reachable via API? |
| --- | --- | --- | --- |
| `uploaded` | stored, not yet processed | **column default only** — `[V]` `documents/models.py:42`, migration `000:160`; the upload route writes `processing` before the row is observable (`documents/routes.py:438`) | **No** — documented as unreachable (REV-013); no retry/recovery logic may be written for it |
| `processing` | pipeline running | `[V]` `documents/routes.py:188` | yes |
| `ready` | **every page of the source document produced usable content** (native or OCR), **or** the format has no pages (DOCX/TXT), and all downstream steps succeeded | ingestion verdict | yes |
| `partial` | **NEW** — at least one page produced usable content **and** at least one page did not (OCR unavailable, OCR failed, or genuinely no text); all downstream steps succeeded for the pages that did. Requires `pages_usable >= 1`, so **`partial` is impossible for a document with zero usable pages**. Where the reason is *visible* — transient, logged, or durably persisted — is fixed by the **reason-visibility contract in §7.2.3**, which is the only section allowed to make that claim | ingestion verdict (§7.2.1) | yes |
| `error` | **no page produced usable content** (`pages_usable == 0`) **or** any pipeline step raised | ingestion verdict (§7.2.1); `[V]` exception paths `documents/routes.py:200-316` | yes |

**§7.2.1 Authoritative verdict function — stated ONCE; every phase, test, transition rule and UI statement in this plan refers to this.**

```
usable(page) := the page's FINAL text (native, else OCR) contains at least MIN_USABLE_CHARS
                non-whitespace alphanumeric characters, AND that page's extraction did not raise.
                MIN_USABLE_CHARS is a named declared constant; its VALUE is an owner decision
                (gate 24) and is never invented here.

verdict(document):
  if any pipeline step raised                        -> error   (reason = pipeline_exception;
                                                                  embedding_status = error)
  elif the format has no pages (DOCX/TXT)            -> ready
  elif pages_usable == pages_total                   -> ready
  elif pages_usable >= 1                             -> partial
  else  (pages_usable == 0 on a paged format)        -> error   (reason = ONE of:
                                                                  "no_text_layer_ocr_disabled"
                                                                  "ocr_failed_all_pages")
```

**The accepted reason set is exactly three (R2-06a).** `pipeline_exception` — a raised step; `no_text_layer_ocr_disabled` — zero usable pages and OCR was **not attempted** because it is not configured/approved for this deployment; `ocr_failed_all_pages` — zero usable pages with OCR **attempted**, whether the attempt failed or produced output below `MIN_USABLE_CHARS` on every page. R1 also listed `no_text_layer`, which had **no defined trigger** and duplicated the other two; it is removed from §7.2.1 and from gate 24's accepted set rather than left ambiguous.

**Per-page OCR timeout and resource exhaustion (R2-06b).** A page whose OCR exceeds the §16.1 per-page wall-clock ceiling, or fails for a resource reason (memory, decoder error, engine refusal) **without the runner raising**, is a **page-coverage failure**: that page is unaccounted and the verdict follows the function above — `partial` when another page is usable, `ocr_failed_all_pages` when none is. Only a **raised** pipeline step — including a worker crash whose exception propagates to the runner — yields `error`/`pipeline_exception`. Both paths are required tests in Phase 1b (§14.2 Phase 1b's test list); the sub-minimum-output fixture they share is §15.1 row 31. §15.1 row 6 covers one-page OCR failure and contains no timeout scenario (V2R-8).

**Coverage vs exception (the distinction the verdict depends on):** an **unaccounted page** is a coverage fact (`pages_usable < pages_total`, reason recorded per page or per document); a **raised pipeline step** is an exception fact. Coverage can produce `error` **only** when it is zero; an exception **always** produces `error`, whatever the coverage. The two are never merged into one rule.

**§7.2.2 Worked cases (binding — these are the acceptance cases of §15.1):**

| Case | Verdict | Why |
| --- | --- | --- |
| Digital PDF, every page has text | `ready` | `pages_usable == pages_total` |
| Mixed digital/scanned, OCR available and successful | `ready` | every page becomes usable |
| Mixed digital/scanned, **OCR not enabled** | `partial` | at least one page usable, at least one not |
| **Scanned-only, OCR not enabled** | **`error`** — `no_text_layer_ocr_disabled` | zero usable pages; **not `partial`** (this removes the R0 contradiction, C1) |
| **Scanned-only, OCR attempted but fails on every page** | **`error`** — `ocr_failed_all_pages` | zero usable pages (C2) |
| **Scanned-only, OCR succeeds on every page** | **`ready`** | every page usable — the capability's success case |
| OCR fails on one page, other pages carry native text | `partial` | exactly one usable-content short |
| OCR output exists but is unusable (below `MIN_USABLE_CHARS`) | counts as an **unaccounted page** — `partial` if any other page is usable, otherwise `error` | "garbage output" is not a verdict of its own; it is an unaccounted page |
| Any raised step (parse / embed / structure / graph / OCR runner) | `error` — `pipeline_exception` | an exception is a document-level failure, never a coverage outcome |
| DOCX/TXT | `ready` when all steps succeed, otherwise `error` | no page denominator exists |

### 7.2.3 Reason-visibility contract (R2-04) — what is visible, where, and for how long

R1 said a reason is "recorded … at document level" without naming a place it could be stored. Under option B only `documents.page_count` exists; under option C nothing is added; `[V]` `documents` has no reason column and no other table can hold one (`documents/models.py:22-57`, `graph/models.py:162-205`). R2 therefore states the **only** visibility each channel provides, and no section may claim more:

| Channel | What it can carry | Availability | Requires |
| --- | --- | --- | --- |
| **Ingestion response / processing result** | the verdict reason for the document, and the per-page outcome for this run | **transient** — this run only; never retrievable afterwards | nothing (already the pipeline's return value) |
| **Server log** | the same values, for operators | transient, best-effort, never an API contract | nothing |
| **Durable per-page record** (option A) | method, engine/version, confidence, char counts, rotation, per-page `failure_reason` | durable, retrievable per page | **gate 3 option A** + migration 008 |
| **Document-level coverage numbers** (option B) | `sourcePageCount` (true denominator) and derived missing-page count | durable, retrievable | **gate 3 option B/23** + one additive column |
| **`status` (all options)** | `ready` / `partial` / `error` — already stored today, no DDL | durable, retrievable now | nothing |
| **Document-level reason repository** | any reason string for a **finished** document | **not available today**; would need a new column or table | gate 3 extension (see gate 23/26 note) |

**Consequences that bind every section of this plan.**

1. Under **options B and C** the reason is **transient**: `DocumentOut`, `DocumentDetailResponse` and the insights payload expose `status` (and, under B, the coverage numbers) **only**. No field, UI element or test may assert that a reason persists across restarts or is readable later.
2. Phase 1a is **status-only** unless gate 23 selects option A or B; its acceptance criteria are restricted to what the chosen contract can actually deliver (§14.2 Phase 1a).
3. A durable document-level reason is **an open decision, not a claim**: it is recorded in §18 and is *not* implemented, assumed or referenced as if it existed.
4. No section may repurpose an unrelated column (caption `content`, `parser_version`, `heading_path`, `chunk_count`) to carry a reason.

**Success criteria** are exactly the function in §7.2.1 — defined once so no other section can drift from it.

### 7.3 Permitted transitions

| From | To | Trigger | Owner of the write |
| --- | --- | --- | --- |
| `uploaded` | `processing` | upload (default never observed) | `documents/routes.py` |
| `processing` | `ready` | complete coverage, all steps ok | ingestion verdict |
| `processing` | `partial` | `0 < pages_usable < pages_total`, all steps ok (§7.2.1 — zero usable pages is `error`, never this row) | ingestion verdict |
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
| `DocumentOut` / `DocumentDetailResponse` / insights schema | `[V]` `documents/schemas.py:13,28,109` | keep `status: str`; add coverage fields **only** under the approved option (§8); **no reason field** unless §7.2.3's durable route is approved |
| Insights payload | `[V]` `documents/insights.py:205` | carry the coverage summary **only as far as the chosen option can store it**; **correct the misleading `pageCount` semantics** (N-001) via **new** fields, leaving the legacy field's meaning documented |
| Frontend type union | `[V]` `src/types/index.ts:8` | add `'partial'` |
| Frontend mapping cast | `[V]` `src/context/WorkspaceContext.tsx` (`apiDocToFile`) | replace the `as DocumentStatus` cast with an exhaustive mapper (§12.2) |
| Frontend rendering | `[V]` `src/pages/WorkspacePage.tsx` | render `partial` with what is missing; render an explicit unknown-status state rather than a silent fallthrough |

### 7.5 Failure and retry behaviour (REV-002)

* An OCR **failure** on a page never aborts the document silently: it is recorded per page (option A) or reflected in the verdict as an unaccounted page (options B/C). The verdict then follows §7.2.1 — `partial` **only when at least one other page is usable**, otherwise `error` with the recorded reason. An OCR failure is therefore **never** equated with `partial` on a document that has no usable content (correction C2).
* A pipeline **exception** keeps today's behaviour: `error` + `embedding_status='error'` (`[V]` `:200-316`).
* **Retry** = the existing reprocess route. `[V]` **today** it deletes derived rows **up front** — the chunk loop at `:695-696` and `delete(DocumentStructureElement)` at `:697-703` — and the writer then re-inserts inside a savepoint (`structure.py:88-110`). **That up-front delete is a defect under the owner's Option-B decision and is replaced by the §10.5 ordering, not endorsed here:** the R2 design writes the candidate assets and the replacement rows first, commits, and only then removes what is no longer referenced. The required change is assigned to **Phase 2a / `BACKEND_AGENT`** (§14.2) and the previous behaviour is recorded as current-only.
* A reprocess that fails **before** its commit leaves the previous committed structure and its assets **intact and citable** (Option B invariant G1); the document's status is `error` for that attempt — never a stale `ready` and never a half-replaced structure.
* A reprocess that fails **after** its commit leaves the new structure committed and the previous run's files as reported residue, prunable per file by the approved cleanup (§10.5).

### 7.6 Required transition tests (owned by `TEST_AGENT`)

Every transition in §7.3, plus every worked case in §7.2.2, plus: `ready` never set with an unaccounted page; `partial` set when exactly one page is unavailable; `error` when no page yields content; **scanned-only with OCR disabled ⇒ `error` / `no_text_layer_ocr_disabled` and never `partial`**; **OCR failure on every page ⇒ `error` / `ocr_failed_all_pages`**; **OCR failure on one page while other pages are usable ⇒ `partial`**; **OCR output below `MIN_USABLE_CHARS` is counted as an unaccounted page**; **a per-page OCR timeout or resource failure is a coverage outcome, not a pipeline exception (§7.2.1)**; **a scanned-only document that OCRs fully ⇒ `ready`**; **a raised step ⇒ `error` / `pipeline_exception` regardless of coverage**; `partial` survives reprocess-to-`ready` when OCR becomes available; dedupe path returns `partial` unchanged; stale requeue does not clobber `partial`; insights report the same status as `DocumentOut`; frontend renders `partial` and an unknown status explicitly. `[V]` existing tests that assert status must be updated together: `tests/unit/documents/test_phase3e_processing.py`, `tests/integration/documents/*` (status assertions), `tests/e2e/browser/test_document_flow.py`.

---

## 8. OCR Provenance and Schema Decision (REV-004, N-001)

### 8.1 What is verified, and what the original plan got wrong

* `[V]` `documents` has no column able to hold, per page, the extraction method, engine, confidence, rotation or failure reason (`documents/models.py:22-57`).
* `[V]` `document_structure_elements` is an **element** table with `UNIQUE (document_id, sequence_index)` (`graph/models.py:202-205`); one row per parser element. A page-level record is not an element; writing one there would break the uniqueness contract and the element↔table-row linkage.
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
* **Reason visibility is governed by §7.2.3 whatever the option chosen (R2-04).** Under B/C the verdict reason is **transient** (ingestion response + log) and **not** retrievable later; any later-phase need for it must first route a durable home through gates 3/23. Phase 1a is status-only unless option A or B is selected.
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
* **Duplicate prevention.** `[V]` **today** reprocessing deletes derived rows before rebuilding — the chunk loop `:695-696` and the up-front `delete(DocumentStructureElement)` `:697-703` — and `structure.py` re-inserts inside a savepoint; row uniqueness `(document_id, table_element_id, row_index)` makes duplicate row evidence impossible; chunks are rebuilt with fresh indices. **The R2 design replaces the up-front delete with the Option-B ordering (write → commit → clean up, §10.5):** the deleted rows are replaced *by the committed replacement*, not before it. `[P]` the same replace-on-commit discipline is required for page records, and figure assets follow §10.5 (run-scoped names, reference-scoped cleanup), so a retry cannot double-write and cannot leave two live asset sets for the same committed structure.
* **Idempotency of a retry (R2-02).** A retry is a **new run** with a new `run_id`: derived **rows** after a successful retry are identical to those of any other successful run of the same source; asset **filenames** differ by design (run-scoped, §10.5), which is why the acceptance criterion is stated as *identical derived rows and exactly one live asset set, with no orphan growth* (§15.1 rows 23, 34) rather than "identical filenames".
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
| 3. Persistence | One `figure` element in the **existing** `document_structure_elements` row shape: `element_type='figure'`, `page_number`, `content` = caption text (or `''` when none), `bbox_x0..y1`, `parser_version`. Persisted by the existing writer (`[V]` `documents/structure.py:79`) — **no new column, no schema change** for figures. **Caption authority rule:** the figure's `content` is an **association copy only**; the caption's own paragraph element remains the **only** chunked/embedded copy (step 6), so the caption text is indexed exactly once. `[V]` requires the bbox data path of §10.2 items 4-5, because element bboxes are currently always `None`. **Persistence ordering (C3, restated by R2-02): a figure row is written only *after* its asset file has been written successfully in the same run** — so a persisted figure element always had an asset written for it by the run that created it. The asset's identity is **run-scoped** (§10.5) and its citation is enabled only once gate 26 is decided. No "failure reason" ever needs a column | BACKEND_AGENT |
| 4. Asset storage | The extracted image is written as a **run-scoped regular file** in the **canonical per-user asset location defined once in §10.5** (per-user upload subtree; name `<document_id>__<run_id>__<figure_sequence_index>.<ext>`; format and extension fixed server-side). §10.5 is the single statement of the layout and of the **write contract**, so no second description can drift from it; no ad-hoc path joining (reuse `storage/file_store.py` containment) | BACKEND_AGENT |
| 5. Asset reference | `figureRef = "fig:<asset_ref>"` — opaque, server-resolved, **never** a filesystem path or URL, resolved server-side with an ownership check — where `asset_ref` is the persisted per-element asset identifier. **This requires gate 26**: `asset_ref` has no column today, so under the no-DDL fallback **no `figureRef` is emitted and no asset route is enabled** (figures are then cited by caption/structure only, never with a guessed image). R1's derived-from-`(document_id, sequence_index)` form is **withdrawn** (R2-02): it cannot distinguish two runs for the same slot | BACKEND_AGENT |
| 5b. Asset read/serve | `[V]` `storage/file_store.py` has **no** read/serve primitive (`save_upload` `:31`, `delete_upload` `:137`, `cleanup_new_file` `:201`; containment helpers `_is_link_or_reparse_point` `:80`, `_resolved_within` `:97`). A **new** containment-checked read helper must be added there (reusing those helpers, never ad-hoc path joining) and consumed by an ownership-checked asset route | BACKEND_AGENT |
| 6. Retrieval path 1 — caption-mediated semantic | The caption is ordinary document text, so it is already chunked and embedded by the existing pipeline — and, **because of the exclusion in step 6b**, it is the **only** chunked copy. When a retrieved chunk's content contains a figure's caption (exact normalised match, non-empty) in the same document and page, the retriever **attaches** that figure (`caption`, `elementId`, and `figureRef` **only if gate 26 approves it**) to the returned source. No new index, no image embedding, no double-counting | AI_AGENT |
| **6b. Chunk/embed exclusion (R2-01 — must land with step 3, same phase, same owner)** | A figure element is **never** turned into a `DocumentChunk`. (a) **Legacy path:** the chunk list is built directly from extractor output (`[V]` `documents/routes.py:198` `extract_text` → `:125` `enumerate(chunk_text(elements))`) and `chunk_text` appends a chunk for **every** element with no type filter (and no emptiness check on its short branch), so the builder must filter `element_type == 'figure'` **before** chunking. (b) **`structure-v2` path — the filter must be on the chunker's INPUT, not on its output (V2R-1, corrected):** `[V]` `_merge_class` (`documents/chunking.py:220-225`) returns `prose` for **every** type other than `table`/`list`, grouping is keyed on that class (`:368`, `:398`), and the chunk's single type is computed over the **merged group** by `_chunk_element_type` (`:228`). A `figure` element would therefore be **merged into the surrounding prose** and contribute caption text — or an empty string — to somebody else's chunk, and `DocumentChunk.element_type` (`String(32)` nullable, `documents/models.py:80`) is a product of that group, never copied from one element. So the rule is: **no `figure` element may enter the element list handed to `chunk_elements`** (filter in `documents/routes.py`'s `_build_chunk_objects` at the call site, `[V]` the same place that builds the chunk objects), with the merge class rule as defence in depth; for text elements behaviour is unchanged. Consequence of the rule: a caption-bearing figure produces **exactly one** ordinary chunk (the paragraph's), and a caption-less figure (`content = ''`) produces **no** chunk at all. No section may claim the caption is chunked once unless this exclusion is implemented | BACKEND_AGENT |
| 7. Retrieval path 2 — element-type-aware structural | In `chat/rag.py:988-1071`: (a) the empty-content filter becomes **element-type aware**, retaining `figure` elements; (b) figure seeding is added for explicit figure intent (question terms such as figure/diagram/chart/illustration, combined with the existing section-name or page scope). Figure candidates keep `score = 0.0` and carry only their `structural_score`/`retrieval_path` | AI_AGENT |
| 8. Ranking honesty | Caption-bearing figures rank through the **existing** RRF fusion like any chunk; element-only figures rank by structural score. **No fabricated similarity is ever reported** for a figure | AI_AGENT |
| 9. Citation/provenance | A figure source carries `documentId`, `page`, `elementId`, `caption`, `evidenceKind='figure'` and the retrieval path — plus **`figureRef` only under gate 26 (a)/(b)**; under the no-DDL fallback no `figureRef` is emitted at all | AI_AGENT |
| 10. Frontend | Renders the caption and page always; renders the **image** only through the authorised asset route when gate 26 enables it, otherwise an explicit "image not available in this configuration" state; never raw HTML; never a substituted image | FRONTEND_AGENT |

**Failure handling (all `[P]`, each tested):**

| Failure | Required behaviour |
| --- | --- |
| Figure detected, asset extraction/write failed | **No figure row is persisted** (persist-last ordering, §10.5). The failure is **reported**, not stored: a counter plus the document id and image sequence index are logged and summarised in the ingestion result — `[V]` no column exists to hold a failure reason (`document_structure_elements`, `graph/models.py:162-205`) and the R0 claim that one was persisted is withdrawn. The image is simply not citable; its caption still exists as a paragraph (step 3's authority rule), so no retrieval content is lost. Durable per-figure provenance is an owner decision (gate 25) |
| Figure detected, asset missing at request time | Resolved **from file absence**, not from a persisted flag: the asset route (which exists **only** under gate 26) returns 404 for the owner too, the evidence reports the figure as unavailable, and no placeholder image is ever substituted. Under the no-DDL fallback this row is unreachable because no asset route exists |
| Figure has no caption | Content is `''`; only path 2 can surface it (explicit figure intent + structural scope); it is **never** described by invented caption text |
| Foreign document / cross-tenant asset request | Ownership resolved server-side from the JWT; 404 (not 403) for a foreign document, matching existing document routes |
| Caption association ambiguous | No association (`caption = None`); ambiguity is not resolved by guessing |
| A committed element's asset is missing, unreadable or corrupt | Reported as **unavailable** for that figure; **no** placeholder, no substituted image, no fallback to another run's file. Under the no-DDL fallback (gate 26 option c) this is the normal state for every figure and the UI says so explicitly |
| Two processing runs target the same document (R2-02) | The existing status guard refuses a second run while a non-stale `processing` document exists (`[V]` `documents/routes.py:681`). Even if that guard were bypassed, run-scoped names mean the two runs never share a filename and cleanup is scoped to the **committed** reference set, so no committed structure can be harmed; the duplicate candidate files are reported residue |

### 10.2 `figure` is EXTEND, not REUSE (REV-007)

`[V]` emitting a figure requires **five** vocabulary/parser edits across the extractor and the parser, and the parser fails closed on anything unmapped (`parser.py:186,297-304`) — **plus a sixth requirement (item 6 below) without which the figure would also be chunked and embedded as duplicate text, and a seventh design item (item 7) that is gated**:

1. `documents/processing.py:39` — add the extractor-side type to `ALLOWED_ELEMENT_TYPES` (otherwise `ExtractedElement.__post_init__` raises at `:79-82`).
2. `documents/parser.py:188-193` — add the mapping in `ELEMENT_TYPE_MAP` (today: heading, paragraph, table, text, list — **no** figure).
3. `documents/parser.py:176-182` — add it to `EMITTED_ELEMENT_TYPES` (today: section, paragraph, table, text_block).
4. `documents/processing.py:47-92` — add bbox fields to `ExtractedElement` and populate them for figures. `[V]` **the extractor carries no bbox fields today** (content, element_type, page, heading_level, heading_path, section, table_data, list_items) and uses boxes only locally (`:201-215` table boxes, `:253-258` block boxes) — so a figure bbox needs a genuinely new data path, not just an emit.
5. `documents/parser.py` `_build_elements` (`:~385-421`) — forward that bbox into `ParsedElement.bbox_x0..y1`, which is declared (`:226-229`) and serialised (`:253-256`) but **never populated**, which is why `documents/structure.py:112-140` persists `None` for every element today.
6. **Exclude `figure` from the chunk/embed path (R2-01 — HIGH; this is a *requirement*, not an optional refinement).** `[V]` the ordinary chunk list is built from the extractor's element list (`documents/routes.py:198` → `:125`) and `chunk_text` (`documents/processing.py`) appends one chunk per element with no type filter, so adding `figure` to `ALLOWED_ELEMENT_TYPES` alone would emit **a second chunk containing the caption** and, for a caption-less figure, an **empty** chunk that still gets embedded and counted. The five edits above are therefore incomplete on their own: a filter must be applied to the **element list at the point of consumption**: (a) the list passed to `chunk_text` (legacy) and (b) the list passed to `chunk_elements` (structure-v2) both exclude `figure`, filtered at the call site in `documents/routes.py`'s `_build_chunk_objects` **before** either call — because the structure-v2 chunker merges non-table/non-list types as prose (`[V]` `documents/chunking.py:220-225`, `:368`) and computes the chunk type over the merged group (`:228`), so filtering the resulting object would be too late (V2R-1). §10.1 step 6b is the normative statement; §15.1 rows 35-37 are its tests.
7. **Persist the asset identity — gated (R2-02/R2-03, gate 26).** The run-scoped asset name cannot be re-derived from `(document_id, sequence_index)` once two runs exist for the same document, so a committed figure can be cited with its image only when its asset identifier is stored (§10.5, gate 26: a nullable `asset_ref` column, a small asset table, or **no DDL** with no asset citation). This item is **not** authorized by this document.

The public type constant (`parser.py:156`, `graph/models.py:117`) and the graph vocabulary (`graph/models.py:110-131`) are genuinely reused — that part of the original classification was right. **No production consumer of `figure` exists** `[V]` (it has never been emitted), so this change cannot regress current behaviour; the research layer does reference the type and forbids premature use (`backend/evaluation/schemas.py:17`, `backend/evaluation/datasets/structure_discriminating_v1.py:91`), which is the same honesty rule §19 applies.

### 10.3 Equations — explicitly deferred (REV-006)

**Decision in this revision:** `[F]` **equations are not supported and nothing about them is claimed.** Concretely:

* No `backend/documents/equations.py` module (the original plan's C-4 is **withdrawn**).
* No equation element type is introduced; no LaTeX/MathML representation is proposed.
* Equation-like text continues to arrive as ordinary `text_block`/paragraph content, which is **text preservation, not equation understanding** — and this wording must appear wherever the capability is described.
* A test is required that asserts only *preservation*: equation-region text either appears verbatim in a text element or the page is counted as **unaccounted** and the document verdict follows §7.2.1 (`partial` if another page is usable, otherwise `error`); **no test may assert notation correctness**.
* If the owner wants notation support later, it needs its own decision record (engine/dependency, accuracy measurement, storage) before any implementation — gate 18.

### 10.4 Contract A/B/C/E deltas in this revision

| Contract | Original | This revision |
| --- | --- | --- |
| **A** canonical representation | `figure` "reuse"; equations implied | `figure` = **EXTEND** with the five vocabulary/parser edits plus the chunk-path exclusion and the gated asset-identity item (§10.2 items 1-7); `extraction_method`/`extraction_confidence` only claimable under option A or document-level fields; **equation row removed**; caption stored in the existing `content` column |
| **B** OCR result | per-page record with no home | record exactly as option A's table (§8.3) **if approved**; otherwise document-level honesty only (§8.2) |
| **C** evidence | adds `figure`, `extractionMethod`, `figureRef`, `caption` | same fields, now with the retrieval mechanism (§10.1), the ranking-honesty rule, `elementId`, and the failure matrix |
| **D** answer request/response | adds `marks`, `includeDiagram` | `marks` retained with an honest unsupported state (§11.3); **`includeDiagram` removed from this revision's contract** and deferred to 5b (REV-011); `topK` gains declared bounds (§12.1); **per-section evidence linkage is a required response field for generated answers** (`sectionEvidence`, §12.1) — the review's §12 requirement, now in the contract rather than only in the metrics |
| **E** diagram representation | full payload | unchanged in shape, but **only reachable after gate 9/10** and now explicitly `retrieved_figure`-only until generation is approved |
| **F** processing status | five statuses, definition change | full lifecycle contract with transitions, consumers, failure/retry, tests (§7); the verdict is now a single function (§7.2.1) that every other section defers to |

### 10.5 Figure-asset lifecycle and recovery (C3, C4, R2-02, R2-03) — **OWNER DECISION: OPTION B**

**Owner decision (2026-10-14, binding on this design).** Reprocessing is **write first → commit the new structure → clean up the old assets.** The previously committed structure must remain usable if a replacement run fails before its commit. *Documentation only:* this authorizes no implementation, no schema change, no migration, no production edit. This section is the **single normative statement** of the asset lifecycle; every other section refers to it.

**Non-atomicity stated up front.** `[V]` filesystem writes and database writes are **not** one transaction in this project, and the codebase already documents the consequence: `delete_document` commits the database **first** and then removes the file **best-effort** ("If file deletion fails, the DB is already clean — the orphaned file can be cleaned up later", `documents/routes.py:612-634`), while `cleanup_new_file` (`storage/file_store.py:201-214`) is a defensive rollback helper, not a transaction. This design does not pretend otherwise.

**Two verified constraints shape the design.**

* `[V]` **`delete_upload` deletes regular files only.** It refuses anything else explicitly (`[V]` `storage/file_store.py:188` `lstat`, `:191-192` `stat.S_ISREG` refusal, `:189-190` except/return) and refuses symlinks/reparse points and paths outside the root (`:170-187`). A recursive directory delete **does not exist** in the audited primitives and must not be improvised.
* `[V]` asset *listing* and asset *writing* also do not exist; only `save_upload` `:31`, `delete_upload` `:137`, `cleanup_new_file` `:201` and the containment helpers `_is_link_or_reparse_point` `:80`, `_resolved_within` `:97`.

**Asset identity is run-scoped and immutable (`[P]`, R2-02).** Assets are individual **regular files** under the per-user upload subtree (`[V]` `_user_upload_dir` `storage/file_store.py:24`), named

```
<document_id>__<run_id>__<figure_sequence_index>.<ext>
```

* `run_id` is a **server-generated identifier for one processing run** (never supplied or influenced by a client). `<ext>` is fixed by the server (write contract below).
* **Candidate set** = the files a given run wrote for a document. **Committed set** = the files named by the elements of that document's currently committed structure. The two name spaces are **disjoint for different runs**, so a run can never create, truncate or rename over a name the committed structure references.
* **R1's deterministic `<document_id>__<figure_sequence_index>.<ext>` naming is withdrawn.** With one name per slot, a second run necessarily overwrote the bytes a committed row still pointed at, and no ordering of writes and commits could prevent it — that was the real defect behind R1's "bytes overwritten" limitation. Run-scoped names remove the condition instead of documenting it.
* Residue therefore changes character: it is always a file **no** committed element references (a superseded run's file, or a candidate from a run that never committed).

**Resolution needs one persisted identifier — gate 26 `[D]`.** A reader maps a committed figure element to *its* run's file. Because several files can exist for the same `(document_id, figure_sequence_index)`, a derived `figureRef` cannot identify the right one; the identifier must be stored:

| Option | What it adds | Consequence |
| --- | --- | --- |
| **(a) nullable `asset_ref` on `document_structure_elements`** (preferred) | one additive column holding the run-scoped file name | `figureRef = "fig:<asset_ref>"`, resolved server-side with an ownership check; one additive migration `008_*`, no existing column touched, `DATABASE_AGENT`-authored |
| **(b) a `document_figure_assets` table** | element ↔ asset ↔ run mapping | larger surface; useful only if per-asset metadata (bytes, format, checksum) is also wanted |
| **(c) no DDL** | nothing | **the fallback:** figures are still extracted, persisted and retrievable by caption/structure, and run-scoped assets are still written — but **no `figureRef` is emitted and no asset route is enabled**, because the resolver cannot prove which run's file belongs to a committed row. The UI shows the caption and an explicit "image not available in this configuration" state |

The plan does **not** pretend documentation alone closes this gap: with today's schema (`[V]` `graph/models.py:162-205` has no such column) the guarantee is complete for **writes** and incomplete for **resolution**. That is exactly what gate 26 decides.

**Write contract (`[P]`, R2-03).** The write side is specified here for the first time; R1 specified only read/serve, listing and deletion.

| Concern | Required rule |
| --- | --- |
| Format and extension | **Fixed server-side to one allowed image format** (e.g. PNG). Never derived from document content, embedded filename, declared MIME or client input. The asset route sets an explicit image `Content-Type` and `X-Content-Type-Options: nosniff` |
| Path derivation | Destination = the document owner's upload subtree + the run-scoped basename, built through the storage layer's containment helpers only. No ad-hoc path joining anywhere in the codebase |
| Containment | The resolved destination must lie inside the document owner's subtree; the write refuses `..`, absolute escapes, symlink/reparse-point ancestors and any destination outside the root — the same discipline the deletion primitive already applies (`[V]` `:170-199`) |
| Destination shape | The writer refuses to write when the destination exists as anything other than a regular file (including a symlink or a directory) |
| Collision | Creation is **exclusive** and fails closed if the final name already exists: with run-scoped names a collision is a bug, never an expected replacement |
| Completeness | Bytes go to a temporary name in the same directory; the final name appears **only** through an atomic rename, so a partially written file never carries a final name. Abandoned temp files are residue, handled by the same reconciliation |
| Run association | The asset belongs to the run that wrote it (its name carries `run_id`) and, once gate 26 approves (a) or (b), to the committed element through `asset_ref`. No asset is ever associated by guesswork or by timestamp |
| Never replace a referenced asset | Defensive invariant: the writer must not create, truncate or rename over a name referenced by the currently committed structure. (With run-scoped names this cannot arise; the rule exists so a future change cannot reintroduce it) |
| Primitive reuse | **Reused:** containment helpers, `delete_upload` (per-file deletion), the defensive-cleanup pattern of `cleanup_new_file`. **New helpers (`BACKEND_AGENT`, `storage/file_store.py`):** run-scoped write, containment-checked read/serve (§10.1 step 5b) and containment-checked listing. `[V]` `save_upload:31` forces a UUID name and **cannot** be used for run-scoped figure writes |

**Lifecycle: the twelve required states `[P]`.**

| # | State | Required behaviour |
| --- | --- | --- |
| 1 | A new processing run begins | The previous committed structure **and** its assets are untouched: the run writes only its own run-scoped names. **Nothing is deleted at the start** — this is the change from today's up-front delete (`[V]` `:695-696`, `:697-703`, which remain current behaviour only, R2-02) |
| 2 | New asset writes succeed | They are **candidates**: unreferenced until the run's commit |
| 3 | One or more new asset writes fail | No figure row is written for those figures (persist-last); each failure is reported (counter + document id + sequence index). The run may still commit the rest; page-level effects on the verdict follow §7.2.1 only |
| 4 | New structure persistence fails | The **previous committed structure remains authoritative and citable**, with its images intact. Candidate files are unreferenced residue, prunable per file. Status is `error` for the attempt — never a half-replaced structure |
| 5 | Crash after some writes, before commit | Same as state 4, plus a stale `processing` status recovered by the existing stale-run path (`[V]` `:321-330`, `:415-416`) |
| 6 | Commit succeeds, cleanup fails | The new structure is authoritative and self-consistent; the previous run's files remain as reported residue, no committed element references them, and they are prunable per file by the approved cleanup |
| 7 | Cleanup interrupted partway | The unswept files are still provably unreferenced; the sweep is **resumable and idempotent**; nothing is deleted twice and nothing referenced is touched |
| 8 | Retry after a failed or interrupted run | A **new run id**; previous candidate residue is swept only when provably unreferenced; no double-write of rows or assets |
| 9 | Document deleted | The existing ordering is kept (`[V]` DB commit first, then best-effort file removal, `:612-634`); every asset the document owns is then deleted **per file** with `delete_upload`. `[V]` today's path removes only `doc.stored_path`: **asset deletion is a new code path, not a new mechanism** |
| 10 | Old or abandoned asset with no live reference | A reconciliation is **read-only first** (containment-checked listing + classification: referenced / orphaned); deletion is a **separate, approval-gated** step, per file, never a directory walk |
| 11 | A committed reference points at a missing or corrupt asset | Reported **unavailable** for that figure; nothing substituted, guessed or served from another run. Under gate 26 option (c) this is the normal state for every figure, and it is stated in the UI |
| 12 | Concurrent or repeated attempts on one document | The existing status guard refuses a second non-stale run (`[V]` `:681`). Even if it were bypassed, run-scoped names are not shared and cleanup is scoped to the committed reference set read at cleanup time, so **no committed structure can be harmed**; duplicate candidates are reported residue |

**Concurrency, retry and idempotency.** The only synchronization assumed is the one that exists (`[V]` the status guard, `:681`, plus the stale-run requeue `:321-330`, `:415-416`); **no new lock, transaction boundary or distributed coordination is assumed**. A retry is a new run with a new id, so retries are safe by construction; the acceptance criterion is *identical derived rows and exactly one live asset set, with no orphan growth* (§15.1 rows 23, 34, 39), not "identical filenames".

**Cleanup procedure (approval-gated, per file).** (i) Classify read-only; (ii) re-read the **currently committed** reference set immediately before each deletion; (iii) delete only regular files inside the document owner's subtree whose name is unreferenced; (iv) if non-reference cannot be established (database unavailable, row unreadable, listing uncertain), **delete nothing and report**; (v) never walk a directory tree, never delete a directory, never delete another document's or another user's file.

**Guarantees this design does provide `[P]`.**

* **G1 — a failed replacement never destroys the previous committed structure or its images.** Nothing is deleted before the replacement has committed.
* **G2 — a committed structure never references bytes another run wrote.** Names are run-scoped and never rewritten; resolution derives from the row's own `asset_ref` (gate 26) or the asset is not cited at all.
* **G3 — cleanup never deletes an asset the committed structure may reference**, and deletes nothing when it cannot prove non-reference.
* **G4 — a missing, unreadable or corrupt asset is reported unavailable**; nothing is substituted, guessed or served from another run's file.
* **G5 — cross-document and cross-tenant resolution is impossible** (JWT-scoped document row → that user's subtree → containment + symlink/reparse refusal; 404 for a foreign document).
* **G6 — no destructive operation is invented:** every deletion is one regular file through the audited primitive; nothing walks or removes a directory tree.
* **G7 — no filesystem/database atomicity is claimed anywhere**, and none is assumed.
* **G8 — every residue state is (a) unreferenced and (b) reported**, never silent.

**Limitations this design does NOT remove `[D]`.**

* **Gate 26 unresolved (option c) ⇒ no image is ever cited**, and the assets written are residue by design until the decision. Rationale: a resolver that cannot prove which run a file belongs to must not serve it.
* **Cleanup is best-effort.** A crash between the commit and the sweep leaves unreferenced files until the next run or an approved reconciliation; they are reported, bounded per document and contain no referenced bytes.
* **If the status guard were bypassed**, two runs could both commit; the last commit wins and the losing run's assets become unreferenced residue. That is churn, not corruption of the committed set — but a per-document exclusive run claim (advisory lock) would remove even the churn, and it is **not** assumed here.
* **Genuine cross-store atomicity is still not claimed** and would require a new mechanism (bytes in the database, or a transactional filesystem). The asset-set half of R1's gate 25 is resolved by this design plus gate 26; **gate 25 remains the home for durable per-figure provenance** (asset version, per-figure failure reason).

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
| **C-1a** | Per-page completeness decision + verdict (`ready`/`partial`/`error`, §7.2.1) | `BACKEND_AGENT` | `backend/documents/processing.py`, `backend/documents/routes.py`, `backend/documents/schemas.py`, `backend/documents/insights.py` | — | `TEST_AGENT` | `VERIFIER` | gates 1, 4, 23, 24 |
| **C-1b** | OCR adapter + engine invocation | `BACKEND_AGENT` | `backend/documents/ocr.py` *(new)*, `backend/documents/processing.py`, `backend/requirements.txt`, `backend/config.py` | gates 2, 3 | `TEST_AGENT` | `SECURITY_AGENT`, `VERIFIER` | gates 2, 3, 13 |
| **C-1c** | **Ask rate limit + resource-control middleware (R2-05)** — per-principal window limit on `/api/chat/ask`, implemented in `backend/main.py` and **not** in `backend/chat/**` (`AI_AGENT`-owned) | `BACKEND_AGENT` (`[V]` `backend/main.py` is in its Owns list) | `backend/main.py` (only; reuses the existing `add_middleware` pattern — `[V]` CORS is registered there) | C-1a; gate 21 for the limit value | `TEST_AGENT` | `SECURITY_AGENT`, `VERIFIER` | gate **21** (value); none for the code shape |
| **C-2** | Page-extraction persistence *(only if option A)* | `DATABASE_AGENT` (model + migration) / `BACKEND_AGENT` (writer) | `backend/documents/models.py` (DATABASE_AGENT), `backend/migrations/versions/008_add_page_extractions.py` *(new, DATABASE_AGENT; migration numbering per the note below the matrix)*, `backend/documents/page_extractions.py` *(new, BACKEND_AGENT)*, `backend/documents/routes.py` | gate 3 | `TEST_AGENT` | `COORDINATOR` + `VERIFIER` | gate 3 |
| **C-2b** | `documents.page_count` column *(only if option B)* | `DATABASE_AGENT` (model + migration) / `BACKEND_AGENT` (write at ingest) | `backend/documents/models.py`, `backend/migrations/versions/008_*.py`, `backend/documents/routes.py`, `backend/documents/insights.py`, `backend/documents/schemas.py` | gate 3, 23 | `TEST_AGENT` | `VERIFIER` | gates 3, 23 |
| **C-3** | Figure extraction, caption association, run-scoped assets, **chunk/embed exclusion**, asset write/read/listing helpers | `BACKEND_AGENT` | `backend/documents/figures.py` *(new)*, `backend/documents/processing.py`, `backend/documents/parser.py`, `backend/documents/routes.py`, **`backend/documents/structure.py`**, `backend/storage/file_store.py` (`documents/tables.py` is the projection precedent, read-only reference) | gate 5; **gate 26 for asset citation** (not for extraction, persistence or chunk exclusion) | `TEST_AGENT` | `SECURITY_AGENT`, `VERIFIER` | gate 5 (+ gate 26 for `figureRef`) |
| **C-3b** | **Figure-asset identity persistence (R2-02)** — the `asset_ref` column or the asset table that makes a committed figure's own asset resolvable; **only if gate 26 selects option (a) or (b)** | `DATABASE_AGENT` (model + migration) / `BACKEND_AGENT` (writer) | `backend/graph/models.py`, `backend/migrations/versions/009_*` *(new — C-3b's asset identity; it takes `008` only if gate 26 is approved before any gate-3 option-A/B DDL; see the numbering note below the matrix)*, `backend/documents/structure.py`, `backend/documents/figures.py` | gate 26 | `TEST_AGENT` | `COORDINATOR` + `VERIFIER` | gate 26 |
| **C-6a** | OCR-derived text in retrieval (`extractionMethod`) | `AI_AGENT` | `backend/chat/rag.py`, `backend/chat/routes.py` | C-1b | `TEST_AGENT` | `VERIFIER` | none |
| **C-6b** | Figure evidence: types, linkage, ranking, asset-aware sources + asset route | `AI_AGENT` (retrieval) + `BACKEND_AGENT` (asset route in `documents/routes.py`) | `backend/chat/rag.py`, `backend/chat/routes.py`, `backend/graph/service.py`, `backend/brain/adapters.py`, `backend/documents/routes.py` | C-3 | `TEST_AGENT` | `SECURITY_AGENT` (IDOR), `VERIFIER` | gate 6 |
| **C-7** | `marks` field + validation + `answerFormat`/`marksSupported` | `AI_AGENT` | `backend/chat/routes.py` | gate 8 | `TEST_AGENT` | `VERIFIER` | gate 8 |
| **C-8** | Generation adapter + composition + honest failure | `AI_AGENT` | `backend/chat/answer_composer.py` *(new)*, `backend/chat/routes.py`, `backend/brain/adapters.py`; **`backend/config.py` → `BACKEND_AGENT`** | gate 7 | `TEST_AGENT` + `EVALUATION_AGENT` | `SECURITY_AGENT` (egress), `VERIFIER` | gate 7 |
| **C-9** | Diagram requirement detection (rule-based, recorded trigger) | `AI_AGENT` | `backend/brain/classifier.py`, `backend/brain/adapters.py`, `backend/chat/routes.py` | C-7 | `TEST_AGENT` | `VERIFIER` | gate 9 |
| **C-10** | Diagram rendering service *(only if generation approved)* | `BACKEND_AGENT` | `backend/diagrams/render.py` *(new package)*, `backend/main.py`, `backend/requirements.txt` | gates 9, 10, 11 | `TEST_AGENT` | `SECURITY_AGENT` (XSS/SSRF), `VERIFIER` | gates 9-11, 22 |
| **C-11** | Frontend: marks, answers, figures, `partial`, unknown status, depth control | `FRONTEND_AGENT` | `src/pages/WorkspacePage.tsx`, `src/context/WorkspaceContext.tsx`, `src/lib/api.ts`, `src/types/index.ts`, `src/pages/SettingsPage.tsx`, `package.json` | C-6b (figures), C-7 (marks), C-12 (status) | `FRONTEND_AGENT` (introduces runner) | `VERIFIER` | gates 4, 12, 23 |
| **C-12** | Status contract + coverage fields + insights correction | `BACKEND_AGENT` + `DATABASE_AGENT` (only if a column/table) | `backend/documents/routes.py`, `backend/documents/schemas.py`, `backend/documents/insights.py` | C-1a | `TEST_AGENT` | `COORDINATOR` | gates 1, 4, 23 |
| **C-13** | Test suites, fixtures, transition tests | `TEST_AGENT` | `backend/tests/**`, `backend/pytest.ini` | each phase | `TEST_AGENT` | `VERIFIER` | none |
| **C-14** | Evaluation corpora, runners, metrics | `EVALUATION_AGENT` | `backend/evaluation/**` | C-1b, C-3, C-8 | `EVALUATION_AGENT` | `VERIFIER` | none |
| **C-15** | Audit script (read-only) | `DATABASE_AGENT` | `backend/scripts/audit_page_coverage.py` *(new)* | gate 17 | `TEST_AGENT` | `VERIFIER` | gates 17, 3 |
| **C-16** | Deployment edits *(entrypoint/Dockerfile/compose)* — **no registered owner** | **UNASSIGNED → requires `COORDINATOR`-owned contract amendment** | `backend/docker-entrypoint.sh`, `backend/Dockerfile`, `compose.yaml`, `Dockerfile.frontend` | gate 22 | `TEST_AGENT` | `SECURITY_AGENT`, `VERIFIER` | gate 22 (N-002) |
| **C-17** | Documentation and evidence records | `COORDINATOR` | `backend/architecture/**` (append-only), `CONTEXT.md`, `ARCHITECTURE.md` | all | — | user | none |
| **C-18** | Diagram package ownership amendment *(if C-10 proceeds)* | `COORDINATOR` | `agents/backend-agent.md` (Owns list) | gate 11 | — | user | gate 11 |

**Migration numbering (R2, fixing an ambiguity where three rows claimed `008`).** `[V]` the single linear head today is `007_add_table_rows`. Numbers are **assigned in authoring order** and recorded in each migration's own docstring; no two authors may take the same number and no shipped revision is ever renumbered.

| Order approved | Migration | Content |
| --- | --- | --- |
| first of {gate 3 option A, gate 3 option B, gate 26 (a)/(b)} | `008_*` | whichever DDL the owner approves first — the option-A `document_page_extractions` table, the option-B `documents.page_count` column, or C-3b's asset identity |
| second | `009_*` | the next approved change. **Intended mapping:** `008` = the gate-3 option (A *or* B, never both), `009` = C-3b's asset identity |

Only one of option A / option B can be selected, and gate 26's change is independent, so the worst case is two additive migrations (`008`, `009`), each with a real `downgrade()` that drops only what it created (§17.3).

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
| `backend/storage/file_store.py` | C-3, C-6b | **`BACKEND_AGENT` only** — the run-scoped **write** helper, the read/serve helper and the containment-checked listing helper are separate, sequential additions, applied in that order (R2-03). (`C-15`, the audit script, is `DATABASE_AGENT`'s `backend/scripts/**` and does not touch this file) |
| `backend/main.py` | **C-1c** (rate-limit middleware), C-10 (diagram renderer mount) | **`BACKEND_AGENT` only**, sequential — C-1c lands first (Phase 1b/4), C-10 only if gate 9-11 proceed. Missing from this table in R1 (R2-05/F-10) |
| `backend/brain/adapters.py` | **C-6b** (evidence/asset-aware sources), C-8 (generation adapter), C-9 (detection signal) | **`AI_AGENT` only**, sequential in that order. Missing from this table in R1 (R2-05/F-10) |
| `backend/graph/models.py` | **C-3b** (asset identity, gated), C-2 (page records, gated) | `DATABASE_AGENT` only; both are gated and must not be authored together with a production edit in the same step |
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
   │        │
   │        │        (2a/2b hang off 1a — figures need no OCR and no schema change;
   │        │         a denied OCR gate 2/3 must not block figure work)
   │        ├─ Phase 2a  Figures + captions + run-scoped assets ... gate 5 (+26 for asset citation)
   │        └─ Phase 2b  Equations ................... DEFERRED (gate 18)
   │                 │
   │                 └─ Phase 3b  Figure evidence in retrieval ....... gate 6
   │                          │
   │                          ├─ Phase 5a  Diagram detection + existing-figure retrieval ... gate 9
   │                          │        └─ Phase 5b  Diagram generation/rendering ... gates 9-11
   │                          │
   ├─ Phase 1b  OCR engine integration ........ gates 2, 3, 13, 21 (+22 for deployment)
   │        │
   │        └─ Phase 3a  OCR text in retrieval
   │                 │
   │                 └─ Phase 4   Mark-aware generation .... gates 7, 8, 21
   │
   └────────────────────────────────────────► Phase 6  Frontend .... gates 4, 12, 23, 26 (figures)
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
*Prerequisites:* gate 1 (scope), gate 4 (`partial` contract + invariant restatement), gate 23 (coverage-field decision if any new field is reported), **gate 24 (the `MIN_USABLE_CHARS` value and the `error` reason set — the verdict cannot be computed without them)**.
*In scope:* per-page decision inside the existing page loop; `ready`/`partial`/`error` verdict; the docstring/invariant restatement; consumer updates (§7.4); coverage reporting using only facts that can be told honestly.
*Out of scope:* OCR, any engine or dependency, figures, schema changes, per-page method/confidence claims.
*Responsible:* `BACKEND_AGENT`. *Files:* `documents/processing.py`, `documents/routes.py`, `documents/schemas.py`, `documents/insights.py`.
*Must not edit:* `chat/**`, `brain/**`, `graph/**`, `migrations/**`, `tests/**`, `src/**`, `requirements.txt`.
*Tests:* every transition (§7.6) and **every worked case of §7.2.2**, in particular: mixed PDF ⇒ `partial` while OCR is disabled; **scanned-only with OCR disabled ⇒ `error` / `no_text_layer_ocr_disabled` (never `partial`)**; a document whose every page lacks text ⇒ `error`; a raised step ⇒ `error` / `pipeline_exception`; no false `ready`; digital PDF unchanged (`tests/integration/documents/*`, `tests/unit/documents/test_phase3e_processing.py`).
*Acceptance:* 100 % of pages accounted for in the fixture set, **including a rotated-page fixture** (§15.2 — a rotated page that yields no text is an unaccounted page, so rotation is an accounting concern here, not only an OCR concern); `ready` never set with an unaccounted page; existing digital-format suites still pass; no change to chunk counts for digital PDFs; **reporting is status-only unless gate 23 selects option A or B** (no denominator is claimed otherwise — §8.2). **The verdict reason is transient in 1a (R2-04, §7.2.3):** it is returned in the processing result and written to the log; no Phase 1a test may assert that it is retrievable after the request completes or exposed through an API, unless a durable route was explicitly approved under gates 3/23.
*Security/data integrity:* no new input parsing; no new file access; no status written outside the pipeline.
*Failure/recovery:* a page-level failure degrades the verdict, never the process; a raised exception keeps `error` semantics; a reprocess replaces rows atomically.
*Independent verification:* `VERIFIER` re-runs the fixtures and inspects the status transitions in the database.
*Completion evidence:* executed test output with exit codes, fixture results, the diff limited to the four files.
*Gates:* 1, 4, 23, **24**.
*Full field set:* Interfaces = the existing extractor return shape + `Document.status` + `DocumentOut`/insights payloads; Must not edit = `chat/**`, `brain/**`, `graph/**`, `migrations/**`, `tests/**`, `src/**`, `requirements.txt`.

**Phase 1b — OCR integration (gated).**
*Objective:* pages with insufficient native text are OCR'd when an approved engine is available, with provenance.
*Prerequisites:* gate 2 (engine + install + provisioning), gate 3 (option A/B/C), gate 13 (deployment change if the engine needs a system binary), gate 22 if deployment files must change.
*In scope:* one adapter interface (`documents/ocr.py`), per-page invocation condition based on real extracted characters, per-page records under the approved option, honest failure reasons.
*Out of scope:* changing the embedding model; OCR of pages with adequate text (a tested **negative** control); any hosted service without gate 16.
*Responsible:* `BACKEND_AGENT` (+ `DATABASE_AGENT` for option A).
*Tests:* scanned-only becomes searchable and is `ready` when every page succeeds; mixed PDF complete; adequate pages never sent to OCR (**negative control**); OCR failure on one page with usable pages elsewhere ⇒ `partial`; **OCR failure on every page ⇒ `error` / `ocr_failed_all_pages`**; **OCR output below the usability minimum ⇒ that page is unaccounted** (§15.1 row 31); **a per-page timeout or resource failure ⇒ that page is unaccounted, verdict per §7.2.1 (never `pipeline_exception`)** while **a raised/crashed runner ⇒ `error` / `pipeline_exception`** — both paths tested (R2-06b); retry replaces rather than appends (Option B, §10.5); rotated pages (§15.2).
*Acceptance:* per-page accounting preserved; every OCR page carries method + engine + confidence *if option A* (otherwise no such claim is made); measured per-page latency recorded; limits enforced.
*Security:* hostile-document bounds (page/pixel/time ceilings), no document content in logs, no egress without approval.
*Failure/recovery:* an engine failure is a **coverage** event whose verdict follows §7.2.1 — `partial` when at least one page remains usable, `error` when none does (C2); a crashed runner is reported, never retried into a loop; reprocess is idempotent.
*Verification:* `VERIFIER` + `SECURITY_AGENT` on the untrusted-input path.
*Gates:* 2, 3, 13, 16, **21** (the rate-limit value), 22.
*Full field set:* Files = `backend/documents/ocr.py` *(new)*, `backend/documents/processing.py`, `backend/documents/routes.py`, `backend/requirements.txt`, `backend/config.py` (BACKEND_AGENT), **`backend/main.py` (BACKEND_AGENT — the ask rate-limit middleware, matrix row C-1c, value = gate 21; `[V]` that file is in this agent's Owns list and already registers middleware)**, plus `models.py` + `migrations/versions/008_*.py` (DATABASE_AGENT, option A only) and `documents/page_extractions.py` *(new)* (BACKEND_AGENT); Interfaces = one adapter interface + the approved per-page record; Must not edit = `chat/**`, `brain/**`, `graph/**`, `src/**`, `tests/**`; Completion evidence = executed suite output with exit codes, per-page fixture measurements, the chosen option recorded, provisioning evidence (path + artifact only, never secrets).

**Phase 2a — Figures, captions, assets (gated; no DDL).**
*Objective:* figures survive extraction, persistence, storage and citation.
*Prerequisites:* Phase 1a; gate 5 (figure scope); gate 22 only if assets require a deployment change (they do not — assets live in the upload volume).
*In scope:* the **five** vocabulary/parser edits of §10.2 (items 1-5); **the chunk/embed exclusion (item 6, R2-01 — same phase, same owner; without it the caption is chunked twice and a caption-less figure is embedded as an empty chunk)**; image enumeration in place of the skip; caption association; **run-scoped** asset write under the §10.5 write contract; `figure` elements through the existing writer; **the replacement of the up-front derived-row delete with the Option-B ordering (write → commit → clean up) in `reprocess_document`** (§10.5, `[V]` `:695-703` is the current behaviour being replaced).
*Out of scope:* image understanding, OCR of figure text, generated figures, serving assets to anonymous clients, and any schema change (item 7 / gate 26 is **not** in this phase unless the owner approves it).
*Tests:* figure element emitted with page/bbox/caption; caption-less figure emitted with `content = ''`; **a caption-bearing figure produces exactly one ordinary chunk (the paragraph's) — no second caption chunk**; **a caption-less figure produces no chunk at all**; `DocumentChunk.element_type` never carries `'figure'` in the legacy or `structure-v2` path; asset written as a **regular file** with the server-fixed extension, and an existing destination name is refused rather than overwritten; **no row is written when the asset write fails** (persist-last, §10.5) and the failure is reported; asset deleted with the document, and on reprocess the new run-scoped set is committed before the previous set is swept; **failure injection** — asset-write failure, structure-persistence failure and a simulated crash before the commit each leave the previous committed structure **and its images** intact and citable, with candidate files reported as residue (§15.1 row 38); interrupted-run, orphan-asset, concurrent-run and missing-asset behaviour per §10.5; text extraction, caption chunk counts and table behaviour unchanged on a reference fixture; existing structure tests pass.
*Acceptance:* every detected image is accounted for (element + asset) or explicitly reported as failed; the caption appears in exactly one chunk; no empty chunk is created; no existing element type changes behaviour; **a failed replacement never leaves the document without its previous committed structure** (G1).
*Security:* containment, symlink/reparse refusal and exclusive creation reused for the new write helper; server-fixed format/extension (never from document content); explicit image `Content-Type` + `nosniff` on the serve path; no new path composition; tenant-scoped writes (R2-03).
*Failure/recovery:* a failed asset write does not fail the document and **persists no figure row**; it is reported (log counters + ingestion summary) and the image is uncitable — no failure reason is stored, because `[V]` no column exists for one (§10.5; durable provenance = gate 25). All twelve lifecycle states (including failed replacement, post-commit cleanup failure, interrupted cleanup, retry, deletion, orphans, corruption and concurrency) are specified in §10.5.
*Verification:* `VERIFIER` + `SECURITY_AGENT` (path/tenancy/write contract).
*Gates:* 5 (+ **26** only for enabling `figureRef`/asset serving).
*Full field set:* Responsible = `BACKEND_AGENT`; Files = `backend/documents/figures.py` *(new)*, `backend/documents/processing.py`, `backend/documents/parser.py`, `backend/documents/routes.py`, `backend/documents/structure.py`, `backend/storage/file_store.py`; Interfaces = `ExtractedElement`, `ParsedElement`, the structure writer, the new write/read/serve/listing helpers; Must not edit = `chat/**`, `brain/**`, `graph/**`, `migrations/**`, `src/**`, `tests/**` (a gate-26 schema change is `DATABASE_AGENT`'s, in C-3b, not this phase's); Completion evidence = executed test output with exit codes, emitted-element and asset listings, caption-chunk counts on the reference fixture, failure-injection results, caption-association fixtures.

**Phase 2b — Equations — DEFERRED.** `[F]` Nothing is implemented; nothing is claimed (§10.3). Gate 18.
*Full field set:* Responsible = none (no phase runs); Files = none — `backend/documents/equations.py` is **withdrawn**; Interfaces = none; Must not edit = all production files stay untouched for this item; Tests = only the preservation assertion of §15.1 row 11; Acceptance = text is preserved verbatim or the page is reported; Completion evidence = not applicable while deferred; Gates = 18.

**Phase 3a — OCR text in retrieval.** *Objective:* OCR-derived text is retrieved like native text and labelled. *Prerequisites:* Phase 1b. *Responsible:* `AI_AGENT`. *Files:* `chat/rag.py`, `chat/routes.py`. *Tests:* a question answerable only from a scanned page retrieves it; `extractionMethod` present; abstention unchanged. *Acceptance:* correct document + page for OCR-only content; no fabricated similarity.
*Full field set:* Responsible = `AI_AGENT`; Files = `backend/chat/rag.py`, `backend/chat/routes.py`; Interfaces = `SourceChunk`/`SourceOut` (`extractionMethod`); Must not edit = `documents/**`, `graph/models.py`, migrations, `src/**`, `tests/**`; Security = OCR text is untrusted data (injection tests, §16.3); Failure/recovery = a missing or failed OCR record degrades to native-only evidence, never fabricated text; Verification = `VERIFIER`; Completion evidence = executed test output with exit codes and the retrieved fixture source (document + page); Gates = none beyond C-1b.

**Phase 3b — Figure evidence in retrieval (gated).** *Objective:* a figure question returns the right figure, document and page. *Prerequisites:* Phase 2a; gate 6. *Tests:* caption-mediated path; element-type-aware retention; explicit figure intent; caption-less figure (no invented caption); asset unavailable ⇒ honest failure — and, under the no-DDL fallback, the test asserts the **absence** of the asset route rather than a 404; cross-tenant asset request ⇒ 404 under gate 26; ranking reports no fabricated score. *Acceptance:* correct figure, document and page for a known fixture; zero fabricated captions; **exactly one chunk contains the caption text** — guaranteed by the chunk/embed exclusion in §10.1 step 6b (R2-01), not by hope; existing retrieval regressions pass. **Asset citation exists only under gate 26:** under the no-DDL fallback the figure is cited by caption and structure with an explicit "image not available in this configuration" state, and the asset route does not exist. *Verification:* `VERIFIER` + `SECURITY_AGENT` (IDOR).
*Full field set:* Responsible = `AI_AGENT` (retrieval) + `BACKEND_AGENT` (asset route and read/serve helper); Files = `backend/chat/rag.py`, `backend/chat/routes.py`, `backend/graph/service.py`, `backend/brain/adapters.py`, `backend/documents/routes.py`, `backend/storage/file_store.py`; Interfaces = Contract C fields + `figureRef` resolution; Must not edit = `documents/processing.py`, `parser.py`, migrations, `src/**`, `tests/**`; Security = IDOR/BOLA on the asset route (server-side ownership, 404), containment on read; Failure/recovery = unreadable asset ⇒ caption-only evidence + explicit unavailability; Completion evidence = executed test output with exit codes, fixture asset id/document/page, negative-control results (unrelated figure not substituted); Gates = 6 (+ **26** for asset citation / `figureRef`).

**Phase 4 — Mark-aware answers (gated).** *Objective:* genuinely different, source-grounded answers for 6/8/10/15 marks — or an honest unavailable state. *Prerequisites:* Phases 1a/1b/3a; gates 7, 8, 21. *Files:* `chat/answer_composer.py` *(new)*, `chat/routes.py`, `brain/adapters.py`; `config.py` by `BACKEND_AGENT`. *Must not edit:* the trained QA weights; the extractive limits. *Tests:* four structures measurably different by rubric; grounding; unsupported questions; insufficient evidence; model-unavailable fallback (§11.3); `marks=None` identical to today. *Acceptance:* ≥ the owner-approved thresholds per metric, or the feature stays disabled and the fallback is what ships. **Per-section evidence linkage is asserted** (`sectionEvidence`, §12.1). *Failure/recovery:* degrade to extractive with `degraded=true`; never fabricate.
*Full field set:* Responsible = `AI_AGENT` (+ `BACKEND_AGENT` for the `config.py` field); Files = `backend/chat/answer_composer.py` *(new)*, `backend/chat/routes.py`, `backend/brain/adapters.py`, `backend/config.py`, plus `backend/main.py` (owned by `BACKEND_AGENT` and delivered in Phase 1b as C-1c; listed here only so that the request limit and the generation budget are enforced by the same middleware); Interfaces = Contract D request/response; Must not edit = `backend/models/documind-qa/**` (weights), the extractive limits in `chat/qa_model.py`, migrations, `src/**`, `tests/**`; Security = no egress unless gate 16 approves it, instruction/data separation (§16.3), secrets env-only; Verification = `VERIFIER` + `EVALUATION_AGENT` metrics + `SECURITY_AGENT` (egress/injection); Completion evidence = executed test output with exit codes, the model decision record, measured metrics with the owner-approved thresholds named; Gates = 7, 8, 21; the ask rate limit it depends on is delivered by **C-1c** in Phase 1b (same limit value, gate 21).

**Phase 5a — Diagram detection + existing-figure retrieval (gated).** *Objective:* detect diagram need and return the right existing figure. *Prerequisites:* Phase 3b; gate 9. *Tests:* detection precision/recall on a fixture set; trigger recorded; correct figure or an explicit "no figure found" state. *Acceptance:* no unrelated figure substituted — including the **unrelated-but-similar-figure negative control** (§15.1 row 30); failures reported.
*Full field set:* Responsible = `AI_AGENT`; Files = `backend/brain/classifier.py`, `backend/brain/adapters.py`, `backend/chat/routes.py`; Interfaces = the detection signal + the 3b figure evidence; Must not edit = `documents/**`, migrations, `src/**`, `tests/**`; Security = retrieved figure must belong to the authenticated user's document (ownership re-checked); Failure/recovery = detection without a suitable figure yields an explicit "no figure found" state, never a substitute; Verification = `VERIFIER`; Completion evidence = executed test output with exit codes, detection precision/recall on the fixture set, the recorded trigger for each detection; Gates = 9.

**Phase 5b — Diagram generation/rendering (gated, optional).** *Objective:* generate and render only when justified, validated and safe. *Prerequisites:* Phase 5a; gates 9, 10, 11, 22. *Tests:* invalid markup rejected (fail closed); no script/remote fetch; rendering failure reported, never presented as success; attribution present; `includeDiagram`/UI only now (§12.3). *Acceptance:* the highest-risk capability ships only with the smallest-surface renderer approved.
*Full field set:* Responsible = `BACKEND_AGENT` (renderer, on `COORDINATOR`-approved ownership) + `AI_AGENT` (composition) + `FRONTEND_AGENT` (display); Files = `backend/diagrams/render.py` *(new package)*, `backend/main.py`, `backend/requirements.txt`, `backend/chat/routes.py`, `src/**`; Interfaces = Contract E (`DiagramPayload`) + the deferred `includeDiagram` field; Must not edit = untrusted-input-free paths only — never render arbitrary HTML/script; Security = XSS/injection/SSRF rejected and fail-closed, CSP, no `dangerouslySetInnerHTML`; Failure/recovery = validation or rendering failure is reported, never presented as success; Completion evidence = executed test output with exit codes, negative-fixture rejection results, the approved renderer decision; Gates = 9, 10, 11, 22.

**Phase 6 — Frontend integration (gated).** *Objective:* users see honest state. *Prerequisites:* Phases 1a (status), 2a/3b (figures), 4 (marks), gates 4, 12, 23. *Files:* `src/**`, `package.json`. *Tests:* status mapper exhaustiveness; `partial` rendering with what is missing; marks reach the backend; figures render through the asset route; unavailable states for marks/diagrams; a11y; build passes. *Acceptance:* no inert control remains (§12.3); no unsafe HTML; empty/loading/error/unavailable/unknown states all represented.
*Full field set:* Responsible = `FRONTEND_AGENT`; Files = `src/pages/WorkspacePage.tsx`, `src/context/WorkspaceContext.tsx`, `src/lib/api.ts`, `src/types/index.ts`, `src/pages/SettingsPage.tsx`, `package.json`; Interfaces = Contracts C/D/F as amended (including `sectionEvidence` and `partial`); Must not edit = `backend/**`, `.env`, `dist/**`; Security = user/document content and diagram output are untrusted (no raw HTML injection, mirror real backend state); Failure/recovery = each new state (unavailable, unknown, partial) is explicitly rendered rather than silently falling through; Verification = `VERIFIER` (+ `npm run build`); Completion evidence = build output with exit code, the status-mapper test results, a11y checks; Gates = 4, 12, 23, **26** (figures: asset citation needs gate 26; the caption/structure retrieval path does not).

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
| 2 | Scanned-only PDF | 1a/1b | 1a: **`error` + `no_text_layer_ocr_disabled`** (zero usable pages — **not `partial`**); 1b: **`ready`** when OCR succeeds on every page, **`partial`** when OCR recovers only some pages, searchable content carries `extractionMethod='ocr'` |
| 3 | Mixed digital/scanned PDF | 1a | every page accounted for; **`partial`** while OCR is disabled, `ready` only when every page is usable |
| 4 | Rotated scan (90/180/270) | 1a/1b | 1a: page accounted for (a rotated page with no text is unaccounted, and the verdict follows §7.2.1); 1b: rotation detected/applied or reported; §15.2 |
| 5 | Low-quality scan | 1b | page accounted for with confidence recorded (option A) or explicit unaccounted status |
| 6 | OCR failure on **one** page while other pages are usable | 1b | `partial` with the recorded reason; no invented text; retry replaces |
| 7 | Page-level provenance | 1b | per-page method/engine/confidence retrievable **iff option A** |
| 8 | Table structure preservation | 1a/2a | table cells/rows unchanged; `document_table_rows` counts unchanged |
| 9 | Figure extraction + caption linkage | 2a | figure element with page/bbox; caption verbatim; no invented caption |
| 10 | Figure retrieval (caption-mediated and explicit) | 3b | correct figure, document and page for a known fixture; the **image** is returned only under gate 26 — otherwise the caption/structure evidence plus an explicit unavailable-image state |
| 11 | Equation handling | — | **deferred**: text preserved verbatim; **no** notation claim (§10.3) |
| 12 | Structural vs ordinary retrieval | 3a/3b | path provenance reported; no fabricated similarity |
| 13 | Citation correctness / source-page identity | 3b | document + page of the returned evidence match the fixture |
| 14 | Unsupported question / insufficient evidence | 1a-4 | existing gate outcome preserved; no invented answer |
| 15 | Extractive vs generated answers | 4 | `answerFormat` distinguishes them; extractive unchanged when `marks=None` |
| 16 | Requested marks (where supported) | 4 | rubric-based structural difference; never word-count padding |
| 17 | Generation unavailable/denied | 4/6 | honest fallback + explicit UI state (§11.3) |
| 18 | Document status transitions | 1a | every row of §7.3, plus the forbidden transition |
| 19 | Existing-document audit + safe reprocessing | 1a/1b | audit report (read-only) + bounded reprocess with before/after coverage |
| 20 | Authorization / tenant-document isolation | 2a/3b | foreign asset request ⇒ 404 **under gate 26**; server-side ownership resolution from the JWT-scoped document row; document and evidence paths stay owner-scoped whether or not gate 26 enables assets |
| 21 | Prompt injection in uploaded/retrieved content | 4 | document text cannot redirect instructions, tools or data access |
| 22 | Rate limiting / inference-cost controls | 1b (**C-1c**) / 4 | limits enforced and observable (§16.1); the ask limiter is middleware in `backend/main.py` (owner `BACKEND_AGENT`, matrix row **C-1c**); the limit **value** is gate 21 |
| 23 | Duplicate prevention / idempotency | 1b/2a | a second reprocess produces **identical derived rows and exactly one live asset set**, with no duplicates and no orphan growth (§10.5: run-scoped names, reference-scoped cleanup) |
| 24 | Frontend/backend contract compatibility | 6 | exhaustive status mapper; `marks=None` unchanged; `topK` bounds |
| 25 | Startup/deployment failure | 1b / §17 | missing model artifact fails closed with a clear message (preserved behaviour) |
| 26 | Recovery and rollback | §17 / §14.3 | forward-fix path documented and exercised on a disposable database only — **`[B]` blocked** until gate 14 provides a disposable environment; the row is reported as blocked, never as a pass |
| 27 | Cross-**page** retrieval (evidence must be combined from different pages) | 3a/3b | returned evidence ids span the expected pages; answer cites both |
| 28 | Cross-**document** retrieval (two of the user's documents) | 3a/3b | evidence from both documents with correct ids; ownership respected |
| 29 | Cross-**table** retrieval (cells from different rows) | 3a/3b | row evidence from multiple rows with `rowIndex` intact |
| 30 | Unrelated-but-similar figure present in the corpus (**negative control**) | 3b/5a | the unrelated figure is **not** returned or substituted; the correct figure or an explicit "no figure found" state |
| 31 | OCR returns **garbage** text (not a failure — low-quality output) | 1b | the page is **unaccounted** when its output is below `MIN_USABLE_CHARS`: the document is `partial` if any other page is usable, otherwise `error`; no silent promotion to native quality; retrieval provenance retains the method |
| 32 | **OCR failure on every page of a scanned-only PDF** | 1b | `error` / `ocr_failed_all_pages` — never `partial`, no invented text (C2) |
| 33 | **Process interruption during figure extraction** | 2a | no figure rows for the interrupted run (the transaction never commits); status recovers through the existing stale-run path (`[V]` `:321-330`, `:415-416`); residue is that run's own **unreferenced candidate files**, prunable per file (§10.5 state 5) — and the **previous committed structure and its images remain intact and citable** (G1) |
| 34 | **Document deletion and reprocessing asset lifecycle** | 2a | assets removed per file via the audited primitive after the DB commit; a reprocess writes a **new run-scoped asset set**, commits the replacement structure, then sweeps the previous run's now-unreferenced files (§10.5, Option B); a second identical reprocess yields identical derived rows and exactly one live asset set; a foreign document's asset request ⇒ 404 (under gate 26; otherwise the asset route does not exist) |
| **35** | **Caption-bearing figure: the caption appears in exactly one ordinary chunk (R2-01)** | 2a | the figure element produces **no** `DocumentChunk`; the caption paragraph's single chunk is the only occurrence; `chunk_count` on the figure fixture equals the count without figure elements; figure retrieval by caption still succeeds |
| **36** | **Caption-less figure creates no empty chunk (R2-01)** | 2a | the figure element is persisted with `content = ''`; no empty chunk is created, embedded or counted; the figure is reachable only through the element-type-aware structural path (§10.1 step 7) |
| **37** | **`DocumentChunk.element_type` never receives `'figure'` (R2-01)** | 2a | asserted for **both** the legacy and the `structure-v2` chunker paths; existing text/table chunk counts and types are unchanged on the reference fixture |
| **38** | **Failed replacement preserves the previous committed structure (failure injection, R2-02)** | 2a | with (i) an asset write failing, (ii) the structure-persistence step failing, and (iii) a simulated crash **after** asset writes but **before** the commit: the previously committed figure elements and their assets remain present and citable; the candidate files are reported residue; the attempt's status is `error`; no cleanup deletes a referenced file (G1/G3) |
| **39** | **Run-scoped identity, cleanup scoping, concurrency and corruption (R2-02/R2-03)** | 2a | two successive runs of one document produce **disjoint** asset name sets; after the second commits, the first run's files are unreferenced and swept per file; a cleanup run while the committed reference set cannot be read deletes **nothing**; a concurrent reprocess attempt is refused by the status guard; a committed element whose asset is missing or corrupt is reported **unavailable**, never substituted; under gate 26 option (c) no asset is cited at all |

### 15.2 Rotation and low-quality scans — measurable rules (REV-017)

`[P]` For each rotated/low-quality fixture the **only** acceptable outcomes are: (a) the page's text is recovered (rotation detected and applied or OCR succeeded) and the page is accounted for; or (b) the page is explicitly reported as unaccounted, with `rotation_applied`/`failure_reason` recorded where option A is in force. **Silent omission is a failure of the test.** Measurable acceptance: 100 % of pages accounted for (a count, not a quality threshold); accuracy thresholds for OCR text are **owner-approval items** (gate 21) because no baseline exists. If the owner prefers to defer rotation handling, that must be recorded as a deferral (gate 17) — not left implicit. **Phase placement:** rotation is asserted twice — as an **accounting** rule in Phase 1a (a rotated page that yields no text must be reported as unaccounted, never silently dropped; the **verdict then follows §7.2.1**, so a document whose every page is a rotated scan with no text is `error`, and one that still yields usable pages elsewhere is `partial`) and as a **handling** rule in Phase 1b (rotation detected and applied, or the page reported with its reason).

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
| OCR per-page timeout | wall-clock ceiling per page | `BACKEND_AGENT` | must not be raised by a document; exceeding it is a **page-coverage failure**, not a pipeline exception (§7.2.1, R2-06b) — only a raised runner is `pipeline_exception` |
| Image/pixel ceiling | max pixels decoded per page | `BACKEND_AGENT` | hostile-document bound |
| Ingestion concurrency bound | bounded executor for OCR/figure work in `backend/documents/**` | `BACKEND_AGENT` | the event loop must not be blocked; async boundaries preserved |
| Composition concurrency bound | bounded generation concurrency + per-request token/time budget | `AI_AGENT` | applies only if gate 7 approves a generation model |
| Ask rate limit | requests per principal per window on `/api/chat/ask` | `BACKEND_AGENT` — middleware in **`backend/main.py`** (`[V]` that file is in its Owns list and already registers middleware); it must **not** require an edit to `backend/chat/**`, which is `AI_AGENT`-owned (`agents/backend-agent.md` Must Not Touch). **Scheduled as matrix row C-1c, delivered in Phase 1b/4, acceptance §15.1 row 22 (R2-05)** | limit **value**: owner-approved — gate 21 |
| Generation token/time budget | per-request cap | `AI_AGENT` | only relevant if gate 7 approves generation |
| Upload size validation | existing 50 MB cap reused (upload route) | `BACKEND_AGENT` | `[V]` `config.py:max_upload_size_mb = 50` |
| `topK` bounds validation | declared bounds on `AskRequest.topK` | `AI_AGENT` (`backend/chat/routes.py` is `AI_AGENT`-owned) | `[V]` `chat/routes.py:28` unvalidated today |

### 16.2 Idempotency and duplicate prevention (REV-010)

* `[V]` **today** reprocessing deletes derived rows first (`documents/routes.py:695-696` chunk loop; `:697-703` up-front `DocumentStructureElement` delete); `structure.py` replaces inside a savepoint; row evidence is unique on `(document_id, table_element_id, row_index)`. **Current behaviour only — superseded by §10.5's Option-B ordering (write → commit → clean up), R2-02.**
* `[P]` page records and figure assets must follow the same replace discipline; a second identical reprocess must produce **identical derived rows and exactly one live asset set with no orphan growth** (a required test — §15.1 rows 23 and 34; asset *filenames* differ by design under run-scoped identity, §10.5).
* `[P]` figure assets follow the §10.5 lifecycle (**owner decision: Option B**): **run-scoped immutable names**, so a run never writes over a name the committed structure references; **write → commit → clean up**, so nothing is deleted before its replacement is committed; cleanup scoped to the **committed reference set**, re-read immediately before each deletion, deleting only files it can prove unreferenced (otherwise it deletes nothing and reports); per-file deletion through the audited primitive; orphan reconciliation that reports before it deletes (approval-gated); no directory-walking deletion (the primitive refuses non-regular files by design, `[V]` `storage/file_store.py:188-192`); and **no filesystem/database atomicity claimed anywhere**.
* `[P]` asset resolution derives its path from the **JWT-scoped** document row (never from a client-supplied id or path), so an asset can never be read across a document or tenant boundary — the ingest-keying rule itself is stated above.
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
| 24 | **Usable-content minimum + reason taxonomy** (new, C1/C2) — the value of `MIN_USABLE_CHARS` and the accepted `error` reason set (`pipeline_exception`, `no_text_layer_ocr_disabled`, `ocr_failed_all_pages` — **`no_text_layer` removed in R2** as redundant and without a defined trigger, R2-06a) | propose a value from measured fixture behaviour / fix it by policy | §7.2.1, §15.1 rows 2-6, 31-32 | no defensible baseline exists today → measure first, then choose (values are never invented here) | Phase 1a (`verdict` cannot be final without it) |

### Group B — Data model and migrations

| Gate | Decision | Options | Evidence | Recommended default | Blocked |
| --- | --- | --- | --- | --- | --- |
| 3 | (as above) schema change | A / B / C | §8 | A or B | C-2/C-2b |
| 20 | Downgrade authority | who may authorise a live downgrade | `AGENTS.md` §06 | forward-fix default; downgrade only with explicit owner sign-off | any rollback decision |
| 23 | Coverage reporting fields (N-001) | add `sourcePageCount`/`pagesMissing` (needs B or A) / report nothing beyond status | this plan §2.4, §8 | add the fields — otherwise the UI can only say "incomplete" | C-12 |
| — | Backfill strategy for existing rows | see gate 17 | §9 | audited, bounded, approval-gated | any backfill |
| 25 | **Durable per-figure provenance** (asset version, per-figure failure reason) — the *asset-set* half of R1's gate 25 is **resolved by the R2 design** (run-scoped names + reference-scoped cleanup, §10.5); what remains is whether a failure reason and an asset version are stored at all | accept "reported, not stored" / store a reason or version (schema change) | §10.5 (limitations), §19, `graph/models.py:162-205` | **accept "reported, not stored"** — nothing in the plan claims otherwise | durable per-figure provenance only; **no longer blocks Phase 2a's asset handling** |
| **26** | **Figure-asset identity persistence (NEW in R2, R2-02/R2-03)** — how a committed figure element identifies *its* run's asset. Without this the Option-B guarantee is complete for writes but not for resolution | **(a)** nullable `asset_ref` on `document_structure_elements` (recommended: one additive migration, no existing column touched) / **(b)** a `document_figure_assets` table / **(c)** no DDL | §10.5 (resolution), `[V]` `graph/models.py:162-205` has no such column; migrations end at `007_add_table_rows`, so an additive `008` fits the convention | **(a)** — the smallest change that makes the guarantee complete | **asset citation only** (`figureRef` + the asset route). Extraction, persistence, caption/structure retrieval and the chunk exclusion proceed **without** it; under (c) no image is ever cited |

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

**Consolidated gate list:** 1-5, 6-12, 13-16, 17-26 as numbered above (gate **26** is new in R2; gates 1-25 are unchanged) (the original plan's 16 checklist items are preserved as 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16; R0 added 17 (historical reprocessing), 18 (equations), 19 (`includeDiagram` timing), 20 (downgrade authority), 21 (metric thresholds), 22 (deployment-file ownership), 23 (coverage fields); **R1 adds 24 (usable-content minimum + reason taxonomy) and 25 (durable per-figure provenance — the asset-set half of R1's gate 25 is resolved by the R2 design, so gate 25 is narrowed to provenance only); R2 adds 26 (figure-asset identity persistence)**). **No gate is closed, opened or altered by R2 except the addition of gate 26.**

---

## 19. Deferred Capabilities and Unsupported Behaviours

Nothing in this list is implemented, partially implemented, or claimed. `[F]`/`[V]` as marked.

| Capability | Status | Wording that must be used |
| --- | --- | --- |
| Scanned-PDF OCR | `[V]` not implemented; `[F]` until gate 2 | "not supported; a scanned-only document is reported with status **`error`** (reason `no_text_layer_ocr_disabled`) and the pages that lack text are reported as unaccounted — the document is **not** `partial`, because no page produced usable content" |
| Durable per-figure provenance (asset version, failure reason) | `[F]` until gate 25 | "a figure image that could not be written is reported, not stored; per-figure failure reasons are not persisted" |
| **Figure asset citation** (`figureRef`, image serving) | `[F]` until **gate 26** (and gates 5, 6) | "under the current schema a figure is cited by its caption and location only; no image is served and none is substituted" |
| Per-page OCR provenance | `[F]` until gate 3 | "not recorded" unless option A is approved |
| Figure extraction/retrieval | `[F]` until gates 5, 6 | "not supported" (caption- and structure-mediated retrieval needs no gate 26; only image citation does) |
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
| R-07 | `figure` reclassified EXTEND with five named vocabulary/parser edits (corrected from "three" during the R1 pass, R-26; R2 adds items 6-7, R-31/R-32) | REV-007 | §10.2 |
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
| R-20 | Independent verification round performed after drafting by two read-only reviewers; 22 findings raised. 21 were corrected in R0; **one (V2-10, the C-11 dependency/gate row) was claimed as corrected but was not actually applied** — it is corrected in R1 (see R-26) | verification round | §2.3, §5, §7.2, §9.2, §10.1-§10.4, §12.1, §13.1, §14.1-§14.2, §15.1-§15.2, §16.1, §18, §19 |
| R-21 | Two corrections of record: (a) the review report's quotation "Do not add decorative controls" does not exist in `agents/*.md` and is replaced by the rule that does (`agents/frontend-agent.md:23` + `AGENTS.md` §03); (b) the original plan's claim that figure bboxes are already available was wrong — element bboxes are never populated today, so the figure work needs a new data path | REV-011, REV-019, V1-2, V1-9 | §4, §10.2 |
| **R-22** | **Correction C1 — status contradiction removed.** One authoritative verdict function (§7.2.1) with the worked cases (§7.2.2); `pages_usable == 0` ⇒ `error`, never `partial`; scanned-only with OCR disabled ⇒ `error`/`no_text_layer_ocr_disabled`; OCR-completed scanned-only ⇒ `ready`; coverage vs exception distinguished; `partial`/`error` separation preserved. Applied to §5, §7.2-§7.6, §14.2 (1a, 1b), §15.1, §15.2 and §19 | correction pass (C1) | §3.1, §5, §7, §14.2, §15.1, §15.2, §19 |
| **R-23** | **Correction C2 — OCR failure is a coverage event, not a verdict.** `partial` only when at least one page is usable; all-pages failure ⇒ `error`/`ocr_failed_all_pages`; sub-minimum OCR output counts as an unaccounted page; raised runner ⇒ `error`/`pipeline_exception`. New scenario §15.1 **row 32** plus the **rewritten row 31** (sub-minimum OCR output is now an *unaccounted* page); rows 33-34 belong to C4, not C2 — attribution corrected in R2 (F-11) | correction pass (C2) | §3.1, §7.5, §14.2 (1b), §15.1, §15.2 |
| **R-24** | **Correction C3 — the unstoreable persisted value is withdrawn.** No figure row without a successful asset write; `figureRef` is derived from existing columns; no failure reason is stored (no column exists); durable provenance routed to gate 25. No schema field added, no migration authorised | correction pass (C3) | §3.1, §10.1, §10.5, §14.2 (2a), §16.2, §18, §19 |
| **R-25** | **Correction C4 — the asset lifecycle is specified without assuming atomicity.** File-first/row-last ordering; a failure-cleanup rule that removes only files **created** by the failed run and **never** an **overwritten** path a committed element may reference (V4-1); interrupted-run residue; per-file deletion via the audited primitive (which refuses non-regular files); a containment-checked listing helper; approval-gated orphan reconciliation; cross-tenant impossibility; and the residual interrupted-replace limitation recorded as gate 25 | correction pass (C4) | §3.1, §10.1, §10.5, §14.2 (2a), §15.1 rows 33-34, §16.2, §18 |
| **R-26** | **R1 independent-verification round (V3-1 … V3-12), all corrected:** §6 invariant no longer claims asset atomicity (V3-1); §7.1 defers to the §7.2.1 partial/error split (V3-2); §10.5 reprocessing ordering changed to write→commit→sweep so a failed reprocess cannot strip assets from committed rows (V3-3); "three edits" corrected to five in all five places (V3-4); C-11 dependency/gate row fixed and R-20's overstated claim corrected (V3-5); gate 24 added to Phase 1a and C-1a (V3-6); the integrity row now records the observed verification outcome instead of pre-claiming it (V3-7); three citation ranges corrected (V3-8); the equations test now defers to the verdict function (V3-9); rotation row and the phase-map gate list aligned (V3-10); the two-owner request-size row split and the duplicated §16.2 bullet merged (V3-11); stale baseline row, missing `file_store.py` single-writer row and the closing gate range corrected (V3-12) | verification round (R1) | §2.2, §4, §6, §7.1, §7.2, §10.3, §10.5, §13.1, §13.3, §14.1-§14.2, §15.1, §16.1-§16.2, §20, integrity table |
| **R-27** | **R1 independent-verification round 2 (V4-1 … V4-5), all corrected:** §10.5's failure-cleanup rule now distinguishes **created** from **overwritten** asset paths so a failing run can never strip an asset a committed element references (V4-1, HIGH); the integrity row and the change log now record the verification rounds (§4 note) rather than a single report (V4-2); the `file_store.py` single-writer row no longer implies a second owner or a false `C-15` cross-reference (V4-3); a namespace note distinguishes correction ids `C1`-`C4` from matrix rows `C-1a`-`C-18` (V4-4); the REV-003 disposition now qualifies "replaces atomically" as database rows only (V4-5) | verification round 2 (R1) | §3.1, §4, §10.5, §13.3, integrity table |
| **R-28** | **R1 independent-verification round 3 (V5-1 … V5-3), all corrected:** the created-vs-overwritten rule of V4-1 — which round 2's fix had applied in §10.5's first row and the guarantees but not in the requirement text — is now propagated to §16.2 ("assets **created** by a failed run"), §10.5's termination row and §15.1 row 33 ("created-and-unreferenced prunable; overwritten reported, never deleted"), so the **same rule now reads in all four places** (V5-1); the `processing → partial` transition row now carries the §7.2.1 condition instead of the loose phrase "incomplete coverage" (V5-2); and the integrity table states that both accompanying reports are delivered in the same task as this revision instead of citing artifacts as if already present (V5-3) | verification round 3 (R1) | §7.3, §10.5, §15.1, §16.2, integrity table |
| **R-29** | **R1 independent-verification round 4 (V6-1 … V6-3), all corrected:** the R0-verification row in the integrity table no longer claims all 22 R0 findings were corrected — it now matches R-20's record that one was claimed but only applied in R1 (V6-1); the figure-asset location is stated **once**, canonically, in §10.5 (per-user subtree with a deterministic per-figure filename) and §10.1 step 4 and §14.2 Phase 2a now reference it instead of re-describing it, removing the document-vs-user-subtree ambiguity (V6-2); and §3.1's correction-`C4` summary now says the defensive cleanup covers **the files that run created**, matching the normative rule in §10.5 (V6-3) | verification round 4 (R1) | §3.1, §10.1, §10.5, §14.2 (2a), integrity table |
| **R-30** | **Final integrity stamp (no content change to the corrected text):** the two accompanying reports required by the task were produced as separate files — `DOCUMIND_PLAN_R1_CORRECTION_REPORT_2026-10-14.md` (every change and its affected sections; rationale stated explicitly for C1–C4) and `DOCUMIND_PLAN_R1_VERIFICATION_REPORT_2026-10-14.md` (findings, dispositions, unresolved issues and blockers) — resolving the last residue of V5-3 (citations to artifacts that did not yet exist); their digests are recorded in the integrity table and the plan digest was recomputed with everything else frozen | task deliverable (not a finding) | front matter, §20, integrity table |
| **R-31** | **Correction R2-01 (audit F-1, HIGH) — figure elements are excluded from the chunk/embed stream.** The exclusion is now an explicit requirement (§10.2 item 6), normative in §10.1 step 6b, stated for **both** the legacy and `structure-v2` chunker paths (including `DocumentChunk.element_type`), tied to the same phase and owner as figure persistence, and tested by §15.1 rows 35-37; the phrase "chunked exactly once" is now backed by the data flow instead of asserted | audit F-1; R2-01 | §5, §6, §10.1, §10.2, §14.2 (2a, 3b), §15.1 |
| **R-32** | **Correction R2-02 (audit F-2, HIGH) — Option-B reprocessing design.** *Owner decision: write first → commit → clean up.* Deterministic `(document_id, sequence_index)` asset names are **withdrawn** in favour of **run-scoped immutable** names; all twelve required states are specified; G1-G8 replace R1's five guarantees; cleanup is scoped to the **committed reference set** and deletes nothing it cannot prove unreferenced; concurrency relies only on the existing status guard; the up-front derived-row delete is marked **current behaviour only** and its replacement is assigned to Phase 2a/`BACKEND_AGENT`; **gate 26** is added for the one identifier resolution needs; the obsolete §10.5 "bytes overwritten" limitation is removed because the condition that caused it no longer exists | audit F-2; owner decision | §6, §7.5, §9.2, §10.1, §10.2 (item 7), §10.5 (rewritten), §13.1 (C-3, C-3b), §14.2 (2a), §15.1, §16.2, §18 (26) |
| **R-33** | **Correction R2-03 (audit F-3, MEDIUM) — the asset-write contract.** Server-fixed format/extension, containment, exclusive creation, temp-then-rename completeness, collision and destination-shape refusal, run association, the defensive "never replace a referenced name" invariant, and an explicit reused-versus-new primitive list; `[V]` `save_upload` is recorded as **unusable** for this purpose (it forces a UUID name) | audit F-3; R2-03 | §10.5, §13.1 (C-3), §14.2 (2a), §16.4, §19 |
| **R-34** | **Correction R2-04 (audit F-4, MEDIUM) — reason visibility is a contract.** New §7.2.3 states exactly what each channel can carry and how long it lives; under options B/C the reason is **transient** and not retrievable later; Phase 1a's acceptance is restricted to what the storage contract can deliver; no column is repurposed | audit F-4; R2-04 | §7.2, §7.2.3, §7.4, §8.4, §12.2, §14.2 (1a), §15.1 |
| **R-35** | **Correction R2-05 (audit F-5, MEDIUM) — rate limiting is scheduled and owned.** New matrix row **C-1c** (`BACKEND_AGENT`, `backend/main.py`, gate 21 for the value), the file added to Phase 1b/4, acceptance row 22 corrected, and the two multi-touch files missing from §13.3 (`backend/main.py`, `backend/brain/adapters.py`) added | audit F-5, F-10; R2-05 | §13.1, §13.3, §14.1, §14.2 (1b, 4), §15.1, §16.1 |
| **R-36** | **Correction R2-06a/b/c/d/e (audit F-6 … F-10, LOW).** `no_text_layer` removed from the reason set with `ocr_failed_all_pages` defined to cover all-pages sub-minimum output; per-page OCR timeout/resource failure classified as a **coverage** event; §15.1 rows 25-26 re-phased (row 26 marked `[B]`); the §14.1 map redrawn so 2a/2b hang off 1a as the hard-edge text already said; §13.3 omissions fixed | audit F-6 … F-10; R2-06 | §7.2.1, §13.3, §14.1, §14.2, §15.1 |
| **R-37** | **Correction R2-06f (audit F-11, LOW) — change-log and report attribution for §15.1 rows 31-34.** C2/R-23 now claim **row 32** plus the rewritten **row 31**; rows 33-34 remain C4's; the R1 reports' identical mis-attribution is corrected in this revision's reports | audit F-11; R2-06 | §3.1, §20, R2 reports |
| **R-38** | **Correction R2-06g/h (audit F-12, F-13, INFORMATIONAL) — evidence hygiene.** The delete-first citations now point at the statements (`:695-696`, `:697-703`) instead of comments; the R0 digest attribution is corrected and **both** conventions are named everywhere (self-digest with the `Plan SHA-256:` line excluded, versus full-file), including R1's and R0's values in §2.1 and the integrity table | audit F-12, F-13; R2-06 | §2.1, §2.2, §2.3, §20, integrity table |
| **R-39** | **R2 verification V2R-1 (HIGH) — the chunk exclusion is stated at the consumption point.** The `structure-v2` path merges any non-table/non-list element as *prose* (`[V]` `documents/chunking.py:220-225`, `:368`) and derives the chunk type from the merged group (`:228`), so filtering the built object would have been too late; the requirement is now that **no `figure` element enters the element list handed to `chunk_text` or `chunk_elements`** (filter at the call site in `documents/routes.py`'s `_build_chunk_objects`), with the merge class as defence in depth | verification round (R2) | §10.1 (6b), §10.2 (item 6) |
| **R-40** | **R2 verification V2R-2 — migration numbering made linear.** Three matrix rows claimed `008`; a numbering rule now assigns `008` to the first approved gate-3/gate-26 DDL and `009` to the second, with the intended mapping `008` = option A **or** B, `009` = C-3b's asset identity, and numbers fixed in authoring order | verification round (R2) | §13.1 (C-2, C-2b, C-3b + note) |
| **R-41** | **R2 verification V2R-3 — the rate-limit file and gate are in the delivering phase.** `backend/main.py` added to Phase 1b's and Phase 4's file lists; gate 21 added to Phase 1b's gate list; C-1c unchanged | verification round (R2) | §14.2 (1b, 4) |
| **R-42** | **R2 verification V2R-4 — the gate summary matches the gate table.** The consolidated paragraph now names 24, the **narrowed** 25 and the **new** 26, and states that no gate is closed by R2; the closing stop line reads gates 1–26 | verification round (R2) | §18, §20 |
| **R-43** | **R2 verification V2R-5 — R1-era text marked as history.** §1 gains R2's purpose and an explicit "history versus current design" statement; §3 is retitled; the "five exact edits" counts in §3/§10.4/R-07 now name §10.2 items 1-7; §3.1/§4/§20 R-01…R-30 are designated history that §10.5 supersedes where they describe the asset lifecycle | verification round (R2) | §1, §3, §10.4, §20 |
| **R-44** | **R2 verification V2R-6 — asset citation is conditional everywhere.** §10.1 steps 9-10, the asset-missing failure row, §15.1 rows 10/20 and Phase 3b's tests/interfaces/gates now state the gate-26 condition instead of assuming an asset route | verification round (R2) | §10.1, §14.2 (3b), §15.1 |
| **R-45** | **R2 verification V2R-7, V2R-8 — wording and citation.** §16.2's idempotency bullet now matches §9.2/§15.1 (identical derived rows, one live asset set, no orphan growth); the §7.2.1 timeout paragraph no longer cites §15.1 row 6 for a timeout case it does not contain | verification round (R2) | §7.2.1, §16.2 |

**Closing statement.** This is a **plan revision only**. No production file, test, schema, migration, dependency, model, configuration, frontend asset or agent contract was modified; nothing was installed, downloaded, provisioned, migrated, staged, committed or pushed; the original plan and the review report are untouched; **no phase was started and no gate was opened**.

**Stop and wait for owner decisions on gates 1–26 before any implementation.**

---

## Integrity and Validation of This Revision

| Check | Result |
| --- | --- |
| Corrected plan exists at the required path | `[V]` `backend/architecture/DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_REVISED_R2_2026-10-14.md` (destination verified free before writing; nothing overwritten — R2 was created as a copy of R1 and then edited) |
| R1 preserved unmodified | `[V]` `DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_REVISED_R1_2026-10-14.md` still `ddf439206111d632a411dced310186e02f471b8e08c7aac0a87f99c866e607b1` **under its own stated convention** (its `Plan SHA-256:` line excluded) and `ca4d20f4fe264d200860d2171d6705c60ae204aa74165ef0d9fdb2253f49a02a` **as a full-file digest**; measured before and after R2 was created. R2 is a copy that was edited separately |
| R0 preserved unmodified | `[V]` `DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_REVISED_2026-10-14.md`: `13cee3656a10c9fdbb99619d6040c6b108d5bf3ff1d531a626719179a9196455` **under R0's own stated convention** (its `Plan SHA-256:` line excluded) and `5afce228a5b88351321dfb40c7c088f2b2fae398ed86eff1cc92b4a8b0cb4380` as a full-file digest. **Attribution corrected in R2 (F-13):** R1's table labelled the *full-file* value "the digest recorded by R0"; the value R0 itself recorded is the convention digest `13cee365…`, which this revision reproduced from the file |
| R1 correction pass complete and consistent | `[V]` C1-C4 applied at every occurrence (R-22…R-25); §7.2.1 is the single verdict definition and no section states a competing one (checked by search for `partial`/`error` verdict statements) |
| R2 correction pass complete and consistent | `[V]` R2-01 … R2-06 applied at every occurrence (R-31…R-38); §10.5 is the single normative statement of the asset lifecycle and no section still describes deterministic document+sequence asset names or a delete-first replacement; the reason-visibility contract is stated once (§7.2.3); the chunk/embed exclusion is stated once (§10.1 step 6b) and referenced everywhere else (checked by search for `deterministic`, `overwritten`, `no_text_layer`, `main.py`, `chunk_text`) |
| Independently verified after the R1 correction pass | `[V]` **four** read-only verification rounds (12 findings, then 5, then 3, then 3 — all corrected: R-26…R-29), reported in `DOCUMIND_PLAN_R1_VERIFICATION_REPORT_2026-10-14.md` with the change list in `DOCUMIND_PLAN_R1_CORRECTION_REPORT_2026-10-14.md` |
| Independently verified after the R2 correction pass | `[V]` the R2 corrections were produced from an **independent readiness audit of R1** (two read-only reviewers plus coordinator shell measurements, findings F-1…F-13) and re-checked **after** the corrections by a separate read-only reviewer against this file and the source. See `DOCUMIND_PLAN_R2_VERIFICATION_REPORT_2026-10-14.md` (checks performed, evidence, blocked checks). Coordinator-only checks (digests, counts, Git state) are labelled as such there and are **not** presented as independent |
| R1's accompanying reports exist (history) | `[V]` `backend/architecture/DOCUMIND_PLAN_R1_CORRECTION_REPORT_2026-10-14.md` full-file SHA-256 `b75422213da02f331058baf61480351bf1a82cca900b03e6390d477bae5d2c72`; `backend/architecture/DOCUMIND_PLAN_R1_VERIFICATION_REPORT_2026-10-14.md` full-file SHA-256 `17c1bc5c1b41cae4ad8475ea57f14dbee7ad3ef9407096c97f20f74629098c0c` |
| R2's accompanying correction report exists | `[V]` `backend/architecture/DOCUMIND_PLAN_R2_CORRECTION_REPORT_2026-10-14.md`, **full-file** SHA-256 `b74337d2a20c28fd0e63b3b10e7bfe30db1cde4d0d6cb298ef4bb905156209da` (it has no self-digest line, so this is the only convention that applies to it) |
| R2's accompanying verification report exists | `[V]` `backend/architecture/DOCUMIND_PLAN_R2_VERIFICATION_REPORT_2026-10-14.md`, **full-file** SHA-256 `a81306255cd2dd799762603d3c74eb3cfe45d5f0b5285006056db556bea1e229` (no self-digest line) |
| All 20 required sections present, in order | `[V]` §1-§20, verified by heading scan |
| Finding coverage | `[V]` REV-001 … REV-019 each have a disposition with rationale and evidence; plus N-001, N-002 |
| SHA-256 recorded and verified after the final edit | `[V]` recorded in the front matter; **convention (stated explicitly, per F-13):** the value is computed with the `Plan SHA-256:` line excluded (`grep -v '^Plan SHA-256' <file> \| sha256sum`), because that line is the only self-referential content; the **full-file** digest (`sha256sum <file>`) is a different value and is **not** the one stamped. For this document the stamped value is the binding one, and its full-file digest is deliberately **not embedded anywhere** — embedding it would change it. For the two accompanying reports, which have no self-referential line, the two conventions coincide and their digests are recorded below |
| Original plan unchanged | `[V]` SHA-256 `fb3c7fea…` before and after |
| Review report unchanged | `[V]` SHA-256 `e6c5a52c…` before and after |
| Production files changed by this task | `[V]` **no** — no source, test, schema, migration, dependency, model or frontend file written |
| Database / migrations modified | `[V]` **no** — no connection, no migration, no data change |
| Dependencies / models changed | `[V]` **no** |
| Git HEAD | `[V]` unchanged `6baaa2a0773df66e5fb26814afbe67647fb43435` |
| Staged / committed / pushed | `[V]` none |
| Pre-existing working-tree changes | `[V]` preserved: 330 unstaged tracked changes untouched |
| Untracked-file ledger | `[V]` 846 / 719 (before R0 existed) → 847 / 720 (R0) → 848 / 721 (R0 + R1) → 850 / 723 (R1 + both R1 reports) → **853 / 726** (R2 + both R2 reports); one file per artifact, nothing else added or changed |
| Independent verification (R0) | `[V]` performed **after drafting** by two read-only verifier reviewers with different angles (technical feasibility vs ownership/process/testability). Outcome: **22 findings** — 21 corrected in R0; the 22nd (`V2-10`, the C-11 dependency/gate row) was declared corrected but **not actually applied** until R1 (R-26/R-27), as R-20 records |
| Independent verification (R1) | `[V]` performed **after** the correction pass by read-only verifier reviewers in **four rounds**: round 1 raised **12 findings** (2 HIGH, 5 MEDIUM, 4 LOW, 1 INFORMATIONAL), round 2 raised **5** (1 HIGH, 1 MEDIUM, 3 LOW), round 3 raised **3** (2 MEDIUM, 1 LOW) and round 4 raised **3** (1 MEDIUM, 2 LOW) — the later findings are residues of earlier corrections, not new capability defects. **All 23 are corrected** in this revision (R-26…R-29); each finding, its disposition and the residual owner-gated limitations are recorded in `DOCUMIND_PLAN_R1_VERIFICATION_REPORT_2026-10-14.md`, delivered in the same task as this revision. These rows were written only **after** each round returned — no verification is claimed before it happened |
| Independent verification (R2) | `[V]` performed **after** the R2 corrections by a separate read-only reviewer that had file access but **no shell** (its limitations are stated in the R2 verification report); it independently inspected this file and the source rather than trusting the correction summary, and its findings and dispositions are recorded in `DOCUMIND_PLAN_R2_VERIFICATION_REPORT_2026-10-14.md`. Digest, file-count and Git measurements were performed by the coordinator and are labelled coordinator-verified |
