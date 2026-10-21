# DOCUMIND — PLAN REVISION R2: INDEPENDENT VERIFICATION REPORT

**Document ID:** `DOCUMIND_PLAN_R2_VERIFICATION_REPORT`
**Subject of verification:** `backend/architecture/DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_REVISED_R2_2026-10-14.md` (revision **R2**)
**Predecessor:** `…_REVISED_R1_2026-10-14.md` (revision **R1**, preserved unmodified) and `…_REVISED_2026-10-14.md` (**R0**, preserved unmodified)
**Companion correction report:** `backend/architecture/DOCUMIND_PLAN_R2_CORRECTION_REPORT_2026-10-14.md`
**Date:** 2026-10-14
**Baseline HEAD:** `6baaa2a0773df66e5fb26814afbe67647fb43435` (branch `main`)
**Owner decision under verification:** reprocessing = **OPTION B (write first → commit → clean up old assets)**, §10.5.
**Kind:** **DOCUMENTATION VERIFICATION ONLY.** No production code, test, schema, migration, dependency, model, configuration, deployment file or agent contract was modified; no database, migration, service or package operation was performed; no Git state was changed. The only files written by the R2 task are the three R2 documents.

**Digest convention (explicit, because this programme uses two numbers per document).** A document's **stamped** digest is computed **with its own self-referential `Plan SHA-256:` line excluded** (`grep -v '^Plan SHA-256' <file> | sha256sum`), so the value stays reproducible after substitution. The **full-file** digest is a different value. Both are recorded — for R2 in the integrity table of R2 itself, and for R1/R0 in §4 below. R2's own two values are not repeated here because this report is written before R2's final stamp is applied; the stamped value is in R2's front matter and is the one to reproduce.

---

## 1. Verification method, independence and its limits

Three distinct activities, deliberately kept apart:

| Stage | Who | What they had | What they produced |
| --- | --- | --- | --- |
| **Audit of R1** | two read-only reviewers with **different focuses** (technical feasibility; verification/delivery) plus coordinator shell measurement | file reads only for the reviewers; shell for the coordinator | findings `F-1 … F-13` (2 HIGH, 3 MEDIUM, 6 LOW, 2 INFO), with file:line evidence |
| **Correction** | coordinator (R2 author) | files + shell | corrections `R2-01 … R2-06` applied to R2, plus the two R2 reports |
| **Verification of R2** | a **separate read-only reviewer**, spawned after the corrections, told to attack the document and not to treat the correction summary as evidence | **file reads and directory listings; no shell** | findings `V2R-1 … V2R-8`, each corrected, and a pass-list of checks it read itself |

**Limits, stated plainly.**

* **Neither reviewer had shell access.** Neither could compute a digest, count files, read Git state, or run a test. Every digest, file count and Git measurement in this report and in R2's integrity table is **coordinator-verified** and is **not** presented as independent verification.
* The R2 verifier read the plan and the source; it did not execute anything. So "the design is implementable" means *the code paths it names exist and behave as described*, not *the proposed code was run* — it was not written.
* **No test was executed, no database was contacted and no service was started.** Nothing in this report is a test result.
* The verification was performed **before** R2's final digest stamp; the stamp itself is a coordinator action whose only effect is to write that value into R2.

## 2. Artifacts inspected

| Artifact | Role | Digest recorded in R2 |
| --- | --- | --- |
| `…_IMPLEMENTATION_PLAN_REVISED_R2_2026-10-14.md` | the document under verification | its own front matter (`Plan SHA-256`), stamped after this report |
| `…_IMPLEMENTATION_PLAN_REVISED_R1_2026-10-14.md` | baseline for comparison (unmodified) | `ddf439206111d632a411dced310186e02f471b8e08c7aac0a87f99c866e607b1` (convention) / `ca4d20f4fe264d200860d2171d6705c60ae204aa74165ef0d9fdb2253f49a02a` (full file) |
| `…_IMPLEMENTATION_PLAN_REVISED_2026-10-14.md` (R0) | earlier revision (unmodified) | `13cee3656a10c9fdbb99619d6040c6b108d5bf3ff1d531a626719179a9196455` (convention) / `5afce228a5b88351321dfb40c7c088f2b2fae398ed86eff1cc92b4a8b0cb4380` (full file) |
| `DOCUMIND_PLAN_R1_CORRECTION_REPORT_2026-10-14.md` | R1 change list | `b75422213da02f331058baf61480351bf1a82cca900b03e6390d477bae5d2c72` |
| `DOCUMIND_PLAN_R1_VERIFICATION_REPORT_2026-10-14.md` | R1 verification | `17c1bc5c1b41cae4ad8475ea57f14dbee7ad3ef9407096c97f20f74629098c0c` |
| `DOCUMIND_PLAN_R2_CORRECTION_REPORT_2026-10-14.md` | R2 change list | recorded in R2's integrity table |
| `DOCUMIND_PLAN_R2_VERIFICATION_REPORT_2026-10-14.md` | this report | recorded in R2's integrity table |
| `…_PLAN_2026-10-14.md`, `…_PLAN_REVIEW_2026-10-14.md`, `…_CAPABILITY_AUDIT_2026-10-14.md` | unchanged inputs | `fb3c7fea…`, `e6c5a52c…`, `d489f912…` (full-file; none has a self-digest line) |

## 3. Source files inspected during verification

`backend/documents/routes.py` (chunk build `:125`, `:198`; `_build_chunk_objects`; reprocess `:640-715`; delete `:600-634`; stale path `:321-330`, `:415-416`; guard `:681`) · `backend/documents/processing.py` (`ALLOWED_ELEMENT_TYPES`, `ExtractedElement`, `chunk_text`) · `backend/documents/chunking.py` (`_merge_class` `:220-225`, `_chunk_element_type` `:228`, grouping `:368`/`:398`, `chunk_elements`) · `backend/documents/models.py` (`:80` `element_type`; the `documents` column set) · `backend/graph/models.py` (`document_structure_elements` columns) · `backend/storage/file_store.py` (`save_upload:31`, `delete_upload`, `cleanup_new_file`, containment helpers, the `S_ISREG` refusal) · `backend/main.py` (middleware registration, lifespan) · `backend/migrations/versions/` (head = `007_add_table_rows`) · `agents/backend-agent.md`, `agents/database-agent.md` (Owns lists) · `backend/tests/` (layout, named suites) · `backend/architecture/` (the artifacts above).

## 4. Findings checked individually

### 4.1 Verification findings against R2 (`V2R-1 … V2R-8`) — all corrected

| ID | Sev | Finding (evidence read) | Disposition in R2 |
| --- | --- | --- | --- |
| **V2R-1** | **HIGH** | The chunk exclusion was specified at the wrong point. R2 named the "chunk-object builder", but `[V]` `_merge_class` (`documents/chunking.py:220-225`) classifies **every** type other than `table`/`list` as `prose`, grouping keys on that class (`:368`, `:398`), and `_chunk_element_type` (`:228`) derives the chunk's type from the whole merged group. A `figure` element would be merged into surrounding prose and its caption (or empty string) would land in another element's chunk — so filtering the built object would have been too late and Phase 3b's "exactly one chunk" acceptance could still fail | **Corrected** (§10.1 step 6b(b), §10.2 item 6): the rule is now that **no `figure` element may enter the element list handed to `chunk_text` *or* `chunk_elements`** — filtered at the call site in `documents/routes.py`'s `_build_chunk_objects` **before** either call — with the merge class as defence in depth and an explicit note that `DocumentChunk.element_type` is a product of the merged group (§20 **R-39**) |
| **V2R-2** | MEDIUM | Three matrix rows claimed migration `008` (C-2, C-2b, and the new C-3b), while `[V]` the head is `007_add_table_rows` and §17.3 requires one linear chain. C-2/C-2b are alternatives, but C-3b is independent — option B **and** gate 26(a) can both be approved, needing two migrations numbered identically | **Corrected:** a numbering rule below the matrix assigns `008` to the first approved gate-3/gate-26 DDL and `009` to the second, with the intended mapping `008` = option A **or** B (never both), `009` = C-3b's asset identity, numbers fixed in authoring order and recorded in each migration's docstring (§20 **R-40**) |
| **V2R-3** | MEDIUM | The rate-limit file was still not in any phase's file list, and Phase 1b's gate list lacked gate 21, although §3.2/R-35 asserted the opposite — the exact "claim not present in the document" class R2 exists to remove | **Corrected:** `backend/main.py` added to Phase 1b's and Phase 4's file lists; gate 21 added to Phase 1b's gate list (and shown in the §14.1 map) (§20 **R-41**) |
| **V2R-4** | MEDIUM | §18's consolidated gate paragraph still described R1's set ("R1 adds 24 and 25 (figure asset-set ↔ row-set atomicity) … No gate is closed by R1") and §20's closing line still said gates 1–25 — contradicting the gate table 20 lines above and hiding the new gate | **Corrected:** the paragraph now names 24, the **narrowed** 25 and the **new** 26 and states that R2 closes nothing; the closing stop line reads **gates 1–26** (§20 **R-42**) |
| **V2R-5** | LOW/MEDIUM | §1's purpose and §3's heading were R1's, with no R2 item; three "five edits" counts understated the figure work now that §10.2 has seven items; §3.1/§4/R-25/R-26/R-29 still described R1-era rules (deterministic filename, created-vs-overwritten cleanup) as current design | **Corrected:** §1 gains R2's purpose and a "history versus current design" statement; §3 retitled; the counts now name §10.2 items 1-7; §3.1/§4/§20 R-01…R-30 are designated history that §10.5 supersedes for the asset lifecycle (§20 **R-43**) |
| **V2R-6** | MEDIUM | Five statements still presumed an asset route: §10.1 steps 9-10, the "asset missing at request time" failure row, §15.1 rows 10 and 20, and Phase 3b's tests/interfaces/gates — although R2 itself designs a no-DDL fallback in which no `figureRef` and no route exist | **Corrected:** each now carries the gate-26 condition and the no-DDL behaviour (assert the route's **absence**, not a 404), and Phase 3b's gates name 26 (§20 **R-44**) |
| **V2R-7** | LOW | §16.2's idempotency bullet still demanded "identical derived state", which under run-scoped names would fail a correct implementation; §9.2 and §15.1 rows 23/34 already said "identical derived rows, exactly one live asset set" | **Corrected:** the bullet now matches §9.2/§15.1 (§20 **R-45**) |
| **V2R-8** | INFO | One mis-citation: the §7.2.1 timeout paragraph pointed at §15.1 row 6, which is the one-page-OCR-failure row and contains no timeout case | **Corrected:** the paragraph now cites Phase 1b's test list and row 31's sub-minimum fixture (§20 **R-45**) |

### 4.2 The audit findings R2 was created to fix — checked as corrected

| Audit finding | Verified in R2 | Where |
| --- | --- | --- |
| F-1 (HIGH) figure duplication in the chunk stream | `[V]` exclusion is a requirement, stated once at the correct consumption point, owned, phased and tested (rows 35-37 / 35-39 numbering) | §10.1 step 6b, §10.2 item 6, §14.2 2a, §15.1 |
| F-2 (HIGH) reprocessing contradiction | `[V]` §10.5 is now one normative statement: run-scoped immutable names, write → commit → clean up, twelve states, G1-G8, reference-scoped cleanup, concurrency via the existing guard; delete-first appears only as **current behaviour** (§2.3, §7.5, §9.2, §16.2) | §10.5, §7.5, §9.2, §16.2, §13.1 (C-3b), §18 (26) |
| F-3 (MEDIUM) write contract | `[V]` format/extension server-side, containment, destination shape, exclusive creation, temp-then-rename, run association, never-replace-referenced, reuse-vs-new primitive list; `save_upload` correctly recorded as unusable for this purpose | §10.5 (write contract), §14.2 2a, §16.4 |
| F-4 (MEDIUM) reason persistence | `[V]` §7.2.3 states each channel and its lifetime; B/C ⇒ transient; Phase 1a acceptance restricted to status-only unless A/B is approved; no column repurposed | §7.2, §7.2.3, §7.4, §8.4, §14.2 1a |
| F-5 (MEDIUM) rate-limit scheduling | `[V]` C-1c exists with owner/file/phase/gate/acceptance; verified `backend/main.py` **is** in `agents/backend-agent.md`'s Owns list and already registers middleware, so the assignment and its shape are sound | §13.1 (C-1c), §13.3, §14.2 1b/4, §15.1 22, §16.1 |
| F-6 … F-13 | `[V]` `no_text_layer` removed from both reason lists; timeout classified consistently in §7.2.1/§16.1/Phase 1b; rows 25-26 re-phased and row 26 marked `[B]`; §14.1's map now matches its own hard edges; §13.3 rows correct against the matrix; row attribution 31-34 corrected; delete-first citations point at `:695-696`/`:697-703`; both digest conventions named | §7.2.1, §13.3, §14.1, §15.1, §2.1-§2.3, §20 |

### 4.3 Checks that pass (read, not asserted)

* §7.2.1 remains a **single** verdict function with exactly three reasons, and `no_text_layer` is gone from both it and gate 24.
* Per-page OCR timeout/resource failure is classified identically in §7.2.1, §16.1's timeout row and Phase 1b's tests: coverage outcome, with `pipeline_exception` reserved for a raised runner.
* §14.1's redrawn map matches its own "Hard edges": 2a/2b off 1a, 4 off 3a, 5a/5b off 3b, 6 after 4/3b.
* §10.5's twelve states cover every state the owner's brief lists; G1-G8 are consistent with the write contract and the cleanup rule; **no** section claims filesystem/DB atomicity; **no** current section still proposes deterministic `(document_id, sequence_index)` names or a delete-first replacement.
* §7.2, §8.2/§8.4, §12.2 and Phase 1a now agree with §7.2.3.
* `backend/main.py`'s ownership and middleware precedent are verified in the repository; `save_upload`'s forced UUID name (`storage/file_store.py:31-33`) is confirmed, which is why the write contract is justified and why its "extension fixed server-side" rule matters (the existing helper takes the extension from the uploaded filename).
* §13.3's rows match the matrix for `backend/main.py` (C-1c, C-10) and `backend/brain/adapters.py` (C-6b, C-8, C-9).
* Test paths R2 names exist in the tree (`tests/unit/documents/`, `tests/integration/documents/`, the e2e browser suite, the integration/disposable fixtures).

## 5. Remaining findings

**None open.** All eight verification findings were corrected in the same revision and re-read after correction; the two HIGH items from the audit (F-1, F-2) and the three MEDIUM items (F-3, F-4, F-5) are corrected with their residual dependencies explicitly gated rather than assumed. Two items are deliberately **not** "solved": they are owner decisions (gate 26 for asset identity; gates 3/23 for a durable status reason), and the plan says so in the places a reader will look.

## 6. Blocked checks

| Check | Status | Why |
| --- | --- | --- |
| Running any test suite | **BLOCKED** | read-only documentation task; the suites need a live database, and none may be contacted |
| Live end-to-end verification | **BLOCKED** | no PostgreSQL, no live server, no authorised disposable database (gate 14) |
| Independent digest / file-count / Git verification | **NOT POSSIBLE** | both reviewers had no shell; these measurements are coordinator-performed and labelled as such |
| Verifying that the *proposed* code works | **NOT APPLICABLE** | nothing was implemented; the plan states `[P]`/`[F]`/`[D]`/`[B]` labels throughout and claims no test result |

## 7. Readiness

* **Plan ready for owner review?** **Yes.** R2 is internally consistent on the two HIGH audit findings, the Option-B design is complete for the twelve required states, every new requirement has an owner, a file, a phase, a gate and an observable acceptance criterion, and the audit's smaller findings are corrected rather than deferred. The conditions attached to that readiness are the owner decisions in §8, not defects in the document.
* **Phase 1a ready to be considered for approval?** **Yes, once its gate values are decided.** Phase 1a is unaffected by every open R2 item (they are §10/§13/§15/§16/§18 concerns reachable in 1b/2a): its files are four `BACKEND_AGENT`-owned modules, its tests exist and assert status, it needs no dependency, model or migration, and the two contract questions it previously left open — where the verdict reason lives (§7.2.3) and which reason strings exist (§7.2.1, gate 24) — are now answered. What still gates it is owner input: **gate 4** (the `partial` contract and the `ready` restatement), **gate 24** (the `MIN_USABLE_CHARS` value and the reason set) and **gate 23** only if a coverage field is reported.
* **No implementation is authorized** by this verification, and none was started.

## 8. Repository integrity

Measured by the coordinator (shell), before and after the R2 documents were written:

| Measurement | Before R2 | After R2 |
| --- | --- | --- |
| Git HEAD / branch | `6baaa2a0773df66e5fb26814afbe67647fb43435` / `main` | identical |
| Staged changes | 0 | **0** |
| Unstaged tracked changes | 330 (35 modified + 295 deleted) | **330** (35 + 295) — pre-existing, untouched |
| Untracked (repo-wide / under `backend/`) | 850 / 723 | **853 / 726** |
| New files added by this task | 0 | **3** (R2 + both R2 reports; untracked, unstaged, uncommitted) |
| Production / test / schema / migration / config / deployment / agent-contract files changed | 0 | **0** |

R1 and R0 were re-hashed after R2 was created: both unchanged under both conventions (§2).

## 9. Digest convention and values

* **Convention:** stamped digest = SHA-256 of the file with its own `Plan SHA-256:` line removed, so the stamped value is reproducible after substitution. Full-file digest = SHA-256 of the bytes as they stand. **R2's stamped value is in R2's front matter** and is the one to reproduce; the same two values for R1 and R0 are in §2. The two R2 reports are quoted full-file in R2's integrity table (neither has a self-referential line).
* **Not claimed here:** that any reviewer computed a digest. The reviewers could not; the coordinator did, and R2's integrity table labels those rows coordinator-verified.

## 10. Owner decisions remaining (the plan's gates 1–26)

Unchanged from R1 except that **gate 25 is narrowed** (durable per-figure provenance only — its asset-set half is resolved by the R2 design) and **gate 26 is new**. Gates that must be resolved before Phase 1a: **1, 4, 24** (and **23** only if a coverage field is reported). Gates for later phases: 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21, 22, 25 and **26**. No gate was closed, opened or altered by this verification, and the plan contains no recommendation presented as an authorization.
