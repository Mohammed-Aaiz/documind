# DOCUMIND — PLAN REVISION R2: CORRECTION REPORT

**Document ID:** `DOCUMIND_PLAN_R2_CORRECTION_REPORT`
**Companion to:** `backend/architecture/DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_REVISED_R2_2026-10-14.md` (the corrected plan, revision **R2**)
**Companion verification report:** `backend/architecture/DOCUMIND_PLAN_R2_VERIFICATION_REPORT_2026-10-14.md`
**Date:** 2026-10-14
**Baseline HEAD:** `6baaa2a0773df66e5fb26814afbe67647fb43435` (branch `main`)
**Owner decision incorporated:** reprocessing is **OPTION B — write first, commit the new structure, then clean up the old assets** (§10.5).
**Kind:** **DOCUMENTATION ONLY.** No production code, frontend code, test, schema, migration, dependency, model, configuration, deployment file or agent contract was modified. No database was contacted, nothing was installed or downloaded, no service was started, and no Git state (staging, commit, push, reset, stash, clean) was altered.

**Digest convention (stated explicitly, because two conventions exist in this programme).** R2's SHA-256 is recorded in R2's own front matter, computed **with the `Plan SHA-256:` line excluded** (that line is the only self-referential content), so the stamped value stays reproducible after substitution. A **full-file** digest is a different number and is not the stamped one. Both values are reported for every artifact in this programme, and neither is repeated in this report (it is written before the plan's final stamp is applied).

---

## 1. What this report covers

R2 is a **targeted correction** of revision **R1** (`…_REVISED_R1_2026-10-14.md`, preserved **unmodified**), driven by an **independent readiness audit of R1** that produced thirteen findings, `F-1 … F-13` (2 HIGH, 3 MEDIUM, 6 LOW, 2 INFORMATIONAL), and by the owner's reprocessing decision.

R1 and every earlier artifact are untouched: R1's digest is the same before and after R2 was produced, and R0, the original plan and the review report still hash to the values recorded in R1/R2.

The corrections are grouped as the task required, `R2-01 … R2-06`, and are traceable inside the plan through its §3.2 table and its §20 change log (rows `R-31 … R-38`).

**Audit findings and their disposition**

| Audit finding | Severity | Resolved by |
| --- | --- | --- |
| F-1 figure elements would be duplicated in the chunk/embed stream | HIGH | R2-01 |
| F-2 reprocessing ordering contradicted the cited code; limitation described an unreachable state; reconciling edit unassigned | HIGH | R2-02 (owner: Option B) |
| F-3 deterministic asset-**write** contract unspecified; `<ext>` undefined | MEDIUM | R2-03 |
| F-4 status reason claimed as "recorded at document level" with no storage path | MEDIUM | R2-04 |
| F-5 rate-limit requirement had no phase, no matrix row and no testable scheduling | MEDIUM | R2-05 |
| F-6 `no_text_layer` had no defined trigger | LOW | R2-06a |
| F-7 per-page OCR timeout / resource failure unclassified | LOW | R2-06b |
| F-8 §15.1 rows 25-26 carried a non-existent "Phase 17"; row 26 depended on a blocked environment | LOW | R2-06c |
| F-9 §14.1's map nested 2a/2b under 1b, contradicting its own hard edges | LOW | R2-06d |
| F-10 §13.3 omitted two genuinely multi-touch files | LOW | R2-06e |
| F-11 change-log/report attribution for §15.1 rows 31-34 was wrong | LOW | R2-06f |
| F-12 delete-first citations pointed at comments, not statements | INFORMATIONAL | R2-06g |
| F-13 R0's digest was attributed to the wrong convention | INFORMATIONAL | R2-06h |

No audit finding was dismissed. Nothing in this pass expands scope: the nine-agent ownership layer, the phase sequence, the contracts and every pre-existing owner gate are preserved.

---

## 2. Correction R2-01 — figure elements must not enter the chunk/embed stream (HIGH, audit F-1)

**Original defect.** R1 made `figure` an emittable element type (§10.2 items 1-5) but never excluded it from the ordinary chunking path. `[V]` the chunk list is built directly from the extractor's output (`documents/routes.py:198` → `:125`) and `documents/processing.py`'s `chunk_text` appends a chunk for **every** element with no type filter (and no emptiness check on its short branch). A caption-bearing figure would therefore produce a **second** chunk containing the caption — contradicting R1's own authority rule and making Phase 3b's acceptance criterion ("exactly one chunk contains the caption text") unsatisfiable — while a caption-less figure would produce an **empty** chunk that was still embedded and counted.

**Exact R2 sections changed.** §3.2 (new); §5 (two rows added, one row corrected); §6 (flow diagram + invariants 7-9); §10.1 (step 3, new step **6b**, failure matrix); §10.2 (new item 6, and the "five edits" wording); §14.2 Phase 2a (in scope, tests, acceptance, gates) and Phase 3b (acceptance); §15.1 (new rows 35-37); §20 (R-31).

**What changed.**
1. The exclusion is now a **requirement**: a figure element is never turned into a `DocumentChunk`, stated once in **§10.1 step 6b** for both chunker paths — the legacy path (filter `element_type == 'figure'` before chunking) and the `structure-v2` path (same filter, and `DocumentChunk.element_type` must not carry the value `'figure'`).
2. It must land in the **same phase and with the same owner** as figure persistence (`BACKEND_AGENT`, Phase 2a), so the caption cannot be chunked twice "in the meantime".
3. The caption's paragraph element remains the single authoritative ordinary chunk, and the element-type-aware structural path (§10.1 step 7) is the figure's separate route.
4. Caption-less figures (`content = ''`) create **no** chunk.
5. Three new acceptance rows make it observable: row 35 (exactly one chunk contains the caption), row 36 (no empty chunk), row 37 (`DocumentChunk.element_type` never `'figure'`, both paths).
6. The document states that no section may claim "chunked exactly once" unless this exclusion is implemented (§10.2 item 6, §14.2 Phase 3b).

**Why this resolves the defect.** The claim is no longer asserted on faith: the filter is named, located, owned, phased and tested, and the acceptance criterion can now pass.

**Remaining limitation.** The plan does not dictate the filter's exact call site inside the chunk-object builder — deliberately, since the same rule must apply to two different builders; the *behaviour* is normative and tested, not the internal shape. No owner approval needed.

---

## 3. Correction R2-02 — reprocessing consistency and recovery (HIGH, audit F-2; **owner decision: Option B**)

**Original defect.** R1's §10.5 asserted "write-then-commit-then-sweep, never delete-then-write" as normative while the code path R1 itself cites as `[V]` fact (`§7.5`, `§9.2`, `§16.2`) deletes the chunks and **all** structure elements **up front** (`documents/routes.py:695-696`, `:697-703`). An implementer could not satisfy both; the stated residue ("the still-committed rows keep their slots while the disk bytes are the interrupted run's") could not occur under that code; and the edit that would have reconciled the two was never named or assigned.

**Owner decision.** **Write first → commit the new structure → clean up the old assets.** The previous committed structure remains usable if a replacement run fails before its commit.

**Exact R2 sections changed.** §3.2; §5; §6 (flow + invariants 5, 8, 9); §7.5; §9.2; §10.1 (steps 3-5, failure matrix); §10.2 (new item 7); **§10.5 (rewritten)**; §13.1 (C-3, new **C-3b**); §13.3; §14.1; §14.2 Phase 2a; §15.1 (rows 23, 33, 34, new 38-39); §16.2; §18 (**new gate 26**, revised gate 25); §19; §20 (R-32).

**What changed.**

1. **Asset identity is run-scoped and immutable.** Names become `<document_id>__<run_id>__<figure_sequence_index>.<ext>`, where `run_id` is server-generated per processing run. R1's deterministic `<document_id>__<figure_sequence_index>.<ext>` scheme is **withdrawn**, because with one name per slot a second run necessarily overwrote bytes a committed row still pointed at — no ordering of writes and commits could prevent that.
2. **The candidate set and the committed set are defined**, and they are disjoint name spaces for different runs. A run therefore cannot write over a name the committed structure references; that is a property of the naming, not of the ordering.
3. **All twelve required states are specified** in §10.5 (run begins; asset writes succeed; some writes fail; structure persistence fails; crash before commit; commit succeeds but cleanup fails; cleanup interrupted; retry; document deleted; orphan with no live reference; committed reference to a missing/corrupt asset; concurrent or repeated runs), each with its required behaviour and its residue character.
4. **G1-G8 replace R1's five guarantees**, covering: failed replacement preserves the previous committed structure and its images (G1); a committed structure never references another run's bytes (G2); cleanup never deletes a possibly-referenced asset and deletes nothing when non-reference cannot be proven (G3); missing/corrupt assets are reported unavailable, never substituted (G4); cross-document/tenant resolution is impossible (G5); per-file deletion only, no directory walking (G6); no filesystem/DB atomicity claimed (G7); every residue state is unreferenced **and** reported (G8).
5. **Cleanup is reference-scoped**: classify read-only, re-read the committed reference set immediately before each deletion, delete only regular files inside the document owner's subtree that are provably unreferenced, and delete nothing on uncertainty.
6. **Concurrency and retry**: only the existing status guard (`[V]` `:681`) and the stale-run requeue (`:321-330`, `:415-416`) are assumed; no new lock, transaction boundary or coordination is invented. A retry is a new run, so it is safe by construction, and the idempotency criterion is restated as *identical derived rows and exactly one live asset set with no orphan growth* (row names differ by design under run-scoped identity).
7. **The implementation change is assigned**: Phase 2a, `BACKEND_AGENT`, replacing the up-front derived-row delete in `reprocess_document`; the current behaviour is labelled **current only** everywhere it appears (§7.5, §9.2, §16.2, §2.3).
8. **The obsolete limitation is removed**, because the condition that produced it no longer exists, and R1's old asset-set gate is replaced by **gate 26**.

**Why this resolves the defect.** The design no longer rests on an ordering that contradicts the code; the contradictory statements are reconciled; the residue analysis matches what the design can actually produce; and the one thing the design cannot do without persistence is stated as a new, explicitly gated decision rather than as an assumed mechanism.

**Remaining limitation (disclosed, not hidden).** Resolution of a committed element to *its* run's asset requires one persisted identifier, and the current schema has none (`[V]` `graph/models.py:162-205`; migrations end at `007_add_table_rows`). **Gate 26** therefore offers (a) a nullable `asset_ref` column on `document_structure_elements` (recommended), (b) a small `document_figure_assets` table, or (c) **no DDL**, in which case no `figureRef` is emitted and no asset route exists — figures are then cited by caption and structure only, with an explicit "image not available in this configuration" state and **never** a substituted or guessed image. Cleanup remains best-effort, and cross-store atomicity is still not claimed. **Owner approval required: gates 5 and 26.**

---

## 4. Correction R2-03 — the deterministic asset-write contract (MEDIUM, audit F-3)

**Original defect.** R1 specified containment, refusal and completeness rules for **reading, listing and deleting** assets, but never for **writing** them, and left `<ext>` undefined — for the highest-risk new filesystem path in the plan. `[V]` the only writer in `storage/file_store.py` is `save_upload:31`, which forces a UUID filename and therefore cannot produce a run-scoped or deterministic name.

**Exact R2 sections changed.** §10.5 (new "Write contract" table); §13.1 (C-3, C-3b); §13.3 (file_store row: write → read → listing, sequential); §14.2 Phase 2a (security, tests); §16.4; §19; §20 (R-33).

**What changed.** A normative table now fixes: the **format and extension server-side** (one allowed image format, never derived from document content, filename, declared MIME or client input; explicit image `Content-Type` plus `X-Content-Type-Options: nosniff` on the serve path); destination derivation through the storage layer's containment helpers only; containment refusal rules mirroring the deletion primitive; destination-shape refusal (non-regular, symlink, directory); **exclusive creation** with fail-closed collision (a collision under run-scoped names is a bug, not an expected replacement); **temp-then-rename completeness** so a partial file never carries a final name; run association through the name (and `asset_ref` once gate 26 approves it); a defensive "never replace a referenced name" invariant; and an explicit **reused vs new** primitive list (reuse containment helpers, `delete_upload`, the `cleanup_new_file` pattern; add run-scoped write, read/serve and listing helpers).

**Why this resolves the defect.** Every write-side question the audit raised has one stated answer, and the file/owner/phase assignments match the ownership contracts (`BACKEND_AGENT` owns `storage/file_store.py`).

**Remaining limitation.** The table specifies behaviour, not function signatures; the helper names are indicative. No owner approval needed beyond gate 5.

---

## 5. Correction R2-04 — status-reason persistence claims (MEDIUM, audit F-4)

**Original defect.** R1's §7.2 said the reason "is recorded **per page where option A is approved, and at document level only otherwise** (§8.4)" — but option B adds only `documents.page_count`, option C adds nothing, and `[V]` `documents` has no reason column and no other table could hold one. This repeated, for the status reason, exactly the defect C3 had fixed for figures: a claimed recorded value with no storage path.

**Exact R2 sections changed.** §7.2 (`partial` row); **new §7.2.3**; §7.4 (two rows); §8.4; §14.2 Phase 1a (acceptance); §15.1 (through the Phase 1a restriction); §20 (R-34).

**What changed.** A **reason-visibility contract (§7.2.3)** now states, per channel, what can be carried and for how long: the ingestion response and the log are **transient** (this run only, never a retrieval contract); a durable **per-page** record requires option A; durable **document-level coverage numbers** require option B/23; `status` is durable today with no DDL; and a durable *document-level reason* is **not available today** and remains an open decision, not a claim. Binding consequences: under B/C the reason is transient and no field, UI element or test may assert otherwise; **Phase 1a is status-only** unless gate 23 selects A or B and its acceptance criteria are restricted accordingly; no unrelated column (`content`, `parser_version`, `heading_path`, `chunk_count`) may be repurposed.

**Why this resolves the defect.** Every persistence claim in the plan now has a concrete channel, and the transient/durable distinction is explicit rather than implied.

**Remaining limitation.** If the owner wants a durable document-level reason, a new field or table is required — that stays behind gates 3/23; the plan does not assume it. **Owner approval required only for that durable route.**

---

## 6. Correction R2-05 — the rate-limit change is scheduled and owned (MEDIUM, audit F-5, F-10)

**Original defect.** §16.1 required per-principal ask-rate-limiting middleware in `backend/main.py`, and §15.1 row 22 made enforcement an acceptance criterion for phases 1b/4 — but no matrix row and no phase file list contained `backend/main.py` (only C-10, Phase 5b, mentioned it), so the control had no phase to be built in. §13.3 also omitted two genuinely multi-touch files.

**Exact R2 sections changed.** §13.1 (new row **C-1c**); §13.3 (two rows added, `file_store.py` row ordered); §14.1 (Phase 1b gates); §14.2 Phase 1b files/gates and Phase 4 gates; §15.1 row 22; §16.1 (ask row); §20 (R-35).

**What changed.** Matrix row **C-1c** assigns the middleware to `BACKEND_AGENT` in `backend/main.py` — `[V]` that file is in `backend/backend-agent.md`'s Owns list and already registers middleware (CORS) — with **gate 21** for the value and no gate for the code shape; Phase 1b's file list and gate list now include it, Phase 4 inherits it, and row 22 names the row, the file and the gate. §13.3 gains `backend/main.py` (C-1c, C-10 — sequential) and `backend/brain/adapters.py` (C-6b, C-8, C-9 — sequential, `AI_AGENT` only), plus a gated row for `backend/graph/models.py` (C-2, C-3b — `DATABASE_AGENT` only, never in the same step as a production edit).

**Why this resolves the defect.** The requirement now has an owner, a file, a phase, a gate and an observable acceptance criterion, and the single-writer table covers every multi-touch file.

**Remaining limitation.** The **value** of the limit is still an owner decision (gate 21) and no number is invented. **Owner approval required for the value only.**

---

## 7. Correction R2-06 — smaller verified inconsistencies (LOW/INFORMATIONAL, audit F-6 … F-13)

| Sub-item | Audit | Original defect | R2 section | Correction |
| --- | --- | --- | --- | --- |
| **a** | F-6 | `no_text_layer` was in the accepted reason set with no trigger defined anywhere | §7.2.1, §18 gate 24 | **Removed.** The set is exactly three reasons (`pipeline_exception`, `no_text_layer_ocr_disabled`, `ocr_failed_all_pages`), and `ocr_failed_all_pages` is now defined to include sub-minimum output on every page; gate 24's list matches |
| **b** | F-7 | Per-page OCR timeout/resource failure had no classification, so it could be read as a document-level exception | §7.2.1, §7.6, §14.2 Phase 1b, §16.1 | Classified as a **page-coverage failure** (page unaccounted, verdict per §7.2.1); only a **raised/crashed runner** is `pipeline_exception`; both paths are required tests |
| **c** | F-8 | §15.1 rows 25-26 carried "17" in a Phase column although no Phase 17 exists; row 26 depended on blocked gate 14 without being marked blocked | §15.1 rows 25-26 | Rows re-phased (`1b / §17`, `§17 / §14.3`); row 26 marked **`[B]` blocked** until gate 14 provides a disposable environment |
| **d** | F-9 | §14.1's ASCII map hung 2a/2b off 1b while the same subsection's "Hard edges" said 2a depends on 1a only | §14.1 | Map redrawn: 2a/2b hang off 1a, with the independence rule inline; 3b/5a/5b and 3a/4 branches follow the hard-edge text |
| **e** | F-10 | §13.3 omitted `backend/brain/adapters.py` and `backend/main.py` | §13.3 | Both added with their matrix rows and owners (also covers the F-5 scheduling gap) |
| **f** | F-11 | C2/R-23 claimed "new scenarios §15.1 rows 32-34"; rows 33-34 are C4's, and the rewritten row 31 was counted as new nowhere | §3.1, §20 R-23, this report's §2 and the R2 verification report | Attribution corrected: row 32 (all-pages OCR failure) + the rewritten row 31 (sub-minimum output ⇒ unaccounted page); rows 33-34 attributed to C4 |
| **g** | F-12 | The delete-first citations (`:258,286,694`) pointed at comment lines rather than the statements | §2.3 #18, §7.5, §9.2, §16.2 | Citations now point at `:695-696` and `:697-703`, and the statements are labelled **current behaviour only** |
| **h** | F-13 | The integrity table labelled R0's **full-file** digest "the digest recorded by R0" (R0 actually recorded `13cee365…` under its stated convention) | §2.1, §2.2, integrity table | Both conventions are named everywhere; R0's own recorded value is reproduced and cited; R1's two values are recorded too; the digest convention is stated in R2's integrity row |

**Remaining limitation for R2-06:** none of these items changed behaviour; (a), (c) and (h) changed wording and bookkeeping, (b) made an existing intent explicit, and (d), (e) removed contradictions. No owner approval needed.

---

## 8. Every new or changed requirement has an owner and a phase

| Requirement (R2) | Owner | Phase | Files | Dependencies | Acceptance | Security review | Independent verification | Stop condition |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Chunk/embed exclusion (§10.1 step 6b, item 6) | `BACKEND_AGENT` | 2a | `documents/processing.py`, `documents/routes.py` (via C-3) | gate 5 | §15.1 rows 35-37 | `SECURITY_AGENT` (path/tenancy, unchanged) | `VERIFIER` | no figure row is committed unless the exclusion ships with it |
| Option-B reprocessing ordering + run-scoped assets (§10.5) | `BACKEND_AGENT` | 2a | `documents/routes.py`, `documents/figures.py` *(new)*, `documents/structure.py`, `storage/file_store.py` | gates 5 (26 only for citation) | §15.1 rows 23, 33, 34, 38, 39 | `SECURITY_AGENT` | `VERIFIER` | a failed replacement must leave the previous committed structure intact |
| Write contract (R2-03) | `BACKEND_AGENT` | 2a | `storage/file_store.py` | gate 5 | §15.1 rows 34, 39 | `SECURITY_AGENT` (format/containment/headers) | `VERIFIER` | an unsafe or colliding destination must fail closed |
| Asset identity persistence (C-3b, gate 26) | `DATABASE_AGENT` (model/migration) + `BACKEND_AGENT` (writer) | 2a (only if gate 26 = a/b) | `graph/models.py`, `migrations/versions/008_*.py`, `documents/structure.py`, `documents/figures.py` | gate 26 (+3) | §15.1 rows 34, 39 | `COORDINATOR` + `SECURITY_AGENT` (IDOR) | `VERIFIER` | additive-only migration; no attribution of an asset without a persisted identifier |
| Reason-visibility contract (§7.2.3) | `BACKEND_AGENT` | 1a | `documents/routes.py`, `documents/insights.py`, `documents/schemas.py` | gates 1, 4, 23 (conditional), 24 | §15.1 rows 2-4, 18 | none new | `VERIFIER` | no test may assert a durable reason without an approved durable route |
| Ask rate-limit middleware (C-1c) | `BACKEND_AGENT` | 1b / 4 | `backend/main.py` | gate 21 (value) | §15.1 row 22 | `SECURITY_AGENT` | `VERIFIER` | the limiter must not require an edit to `chat/**` |

---

## 9. Acceptance criteria for this task — status

| # | Criterion | Status |
| --- | --- | --- |
| 1 | All three R2 files exist | `[V]` see §10 |
| 2 | R1 and all earlier artifacts remain unchanged | `[V]` measured before and after; R1's digest identical under both conventions, R0/original/review unchanged |
| 3 | F-1 … F-5 corrected or explicitly blocked with evidence | `[V]` F-1, F-3, F-5 corrected; F-2 corrected **and** its one residual dependency (asset identity) explicitly gated as gate 26; F-4 corrected with the durable route gated |
| 4 | The six smaller consistency corrections are addressed | `[V]` R2-06a … 06h (eight sub-items, covering all six listed plus the two evidence-hygiene items) |
| 5 | No contradiction remains between the reprocessing design and the cited current implementation | `[V]` the delete-first code is labelled current-only in four places and the replacement is assigned; §10.5 is the single normative statement |
| 6 | The Option-B design has explicit failure, recovery, asset-versioning, cleanup and concurrency semantics | `[V]` twelve states, G1-G8, write contract, reference-scoped cleanup, status-guard concurrency |
| 7 | Every new implementation requirement has an owner and a phase | `[V]` §8 above and the plan's §13.1/§14.2 |
| 8 | Acceptance criteria are feasible and observable | `[V]` new rows 35-39 are file/row-level observable; row 26 marked blocked rather than asserted |
| 9 | Reports distinguish verified facts, proposed behaviour, owner decisions and blocked checks | `[V]` `[V]`/`[P]`/`[D]`/`[F]`/`[B]` labels retained throughout; §7.2.3 and §10.5 separate claim from design |
| 10 | Digests computed and recorded consistently | `[V]` one convention stated, both values reported, stamped value reproducible |
| 11 | No product implementation, database operation, migration or gate change occurs | `[V]` §11 |

---

## 10. Deliverables and integrity evidence

| # | Artifact | Status |
| --- | --- | --- |
| 1 | `backend/architecture/DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_REVISED_R2_2026-10-14.md` — complete corrected plan (R1 + R2-01…R2-06), not a patch fragment | `[V]` created |
| 2 | `backend/architecture/DOCUMIND_PLAN_R2_CORRECTION_REPORT_2026-10-14.md` — this report | `[V]` created |
| 3 | `backend/architecture/DOCUMIND_PLAN_R2_VERIFICATION_REPORT_2026-10-14.md` — independent verification, findings, blocked checks | `[V]` created |

| Measurement | Before R2 | After R2 |
| --- | --- | --- |
| Git HEAD / branch | `6baaa2a0773df66e5fb26814afbe67647fb43435` / `main` | identical |
| Staged changes | 0 | **0** |
| Unstaged tracked changes | 330 (35 modified + 295 deleted) | **330** (35 + 295) — pre-existing, untouched |
| Untracked (repo-wide / under `backend/`) | 850 / 723 | **853 / 726** (R2 + both R2 reports) |
| New files added by this task | 0 | **3** (untracked, unstaged, uncommitted) |

---

## 11. Verification-driven corrections (V2R-1 … V2R-8) — the second correction round

After the R2-01…R2-06 pass, a **separate read-only reviewer** (file access, no shell) was spawned to attack R2 against the source rather than to confirm the summary above. It raised eight findings; all eight are corrected in R2 and recorded in the change log as **R-39 … R-45**. The findings themselves are stated with their dispositions in `DOCUMIND_PLAN_R2_VERIFICATION_REPORT_2026-10-14.md` §4.1; in this report's terms:

| ID | Sev | Original defect (in R2 as first written) | Exact R2 section changed | What changed now | Owner approval? |
| --- | --- | --- | --- | --- | --- |
| **V2R-1** | **HIGH** | R2-01's fix named the “chunk-object builder”, but the structure-v2 chunker merges any non-table/non-list element as **prose** (`[V]` `documents/chunking.py:220-225`, grouping `:368`) and computes the chunk type over the **merged group** (`:228`), so filtering the built object would have been too late — the caption could still be duplicated and Phase 3b's acceptance could still fail | §10.1 step 6b(b), §10.2 item 6, §20 (R-39) | The rule is now stated at the **consumption point**: no `figure` element may enter the element list handed to `chunk_text` **or** `chunk_elements` (filtered at the call site in `documents/routes.py`'s `_build_chunk_objects`, before either call), with the merge class as defence in depth and an explicit note that `DocumentChunk.element_type` is a product of the merged group | No |
| **V2R-2** | MEDIUM | Three matrix rows claimed migration `008` (C-2, C-2b, C-3b) although `[V]` the head is `007_add_table_rows` and §17.3 requires one linear chain | §13.1 (C-2, C-2b, C-3b; new numbering note), §20 (R-40) | `008` = the first approved gate-3/gate-26 DDL; `009` = C-3b's asset identity; intended mapping `008` = option A **or** B (never both), numbers assigned in authoring order and recorded in each migration's docstring | No |
| **V2R-3** | MEDIUM | `backend/main.py` was still absent from Phase 1b/4's file lists and gate 21 from Phase 1b's gate list, while §3.2/R-35 asserted the opposite | §14.2 (1b, 4), §14.1, §20 (R-41) | `backend/main.py` added to Phase 1b's and Phase 4's file lists; gate 21 added to Phase 1b's gate list and shown in the map | Value only (gate 21) |
| **V2R-4** | MEDIUM | §18's consolidated gate paragraph and §20's closing line still described R1's gate set (gates 1–25, gate 25 = asset-set atomicity) | §18, §20 (R-42) | The paragraph names 24, the **narrowed** 25 and the **new** 26 and states R2 closes nothing; the closing stop line reads **gates 1–26** | No |
| **V2R-5** | LOW/MEDIUM | §1 and §3 were still R1's words with no R2 item; the “five edits” counts understated the work (seven items now); §3.1/§4/R-25/R-26/R-29 described R1-era asset rules as current design | §1, §3, §10.4, §20 (R-43) | §1 gains R2's purpose and a “history versus current design” statement; §3 retitled; counts now name §10.2 items 1-7; R1-era rows are designated history that §10.5 supersedes for the asset lifecycle | No |
| **V2R-6** | MEDIUM | Five statements presumed an asset route (§10.1 steps 9-10; the asset-missing failure row; §15.1 rows 10 and 20; Phase 3b tests/interfaces/gates) although R2 itself designs a no-DDL fallback with no `figureRef` and no route | §10.1, §14.2 (3b), §15.1, §20 (R-44) | Each now carries the gate-26 condition; under the fallback the test asserts the route's **absence**, and Phase 3b names gate 26 | No |
| **V2R-7** | LOW | §16.2's idempotency bullet demanded “identical derived state”, which run-scoped names make impossible and which contradicted §9.2/§15.1 | §16.2, §20 (R-45) | Aligned to “identical derived rows and exactly one live asset set with no orphan growth” | No |
| **V2R-8** | INFO | The §7.2.1 timeout paragraph cited §15.1 row 6, which covers one-page OCR failure, not a timeout | §7.2.1, §20 (R-45) | Cites Phase 1b's test list and row 31's sub-minimum fixture | No |

**Why V2R-1 matters beyond its own text.** It is the clearest illustration of the rule this programme has followed since R0: a correction is not complete when the *claim* is added, only when the *mechanism* the claim depends on is named at the place it has to happen. R2-01 had the right requirement and the wrong location, and only a reviewer reading `chunking.py` could catch it. It is recorded as a HIGH finding rather than folded silently into R2-01 for that reason.

**Net effect of the two R2 rounds:** one HIGH audit finding (figure duplication) is now fully implementable in both the legacy and `structure-v2` paths; one HIGH audit finding (reprocessing) is specified under the owner's Option-B decision with a single residual, explicitly gated dependency (asset identity, gate 26); three MEDIUM audit findings are closed (write contract, reason visibility, rate-limit scheduling); the eight smaller/verification items are corrected; and no new gap was introduced by the corrections themselves.

---

## 12. Attestation

No production code, frontend code, test, schema, migration, dependency, model weight, configuration, deployment file or agent ownership contract was modified by this task. No database was contacted, no migration was authored or applied, no package was installed, no model was downloaded and no service was started. No Git state was changed. R1, R0, the original plan, the review report, the capability audit and all four R1 reports are byte-identical to their recorded digests. **No approval gate was opened, no gate was closed, and Phase 1a was not started.**
