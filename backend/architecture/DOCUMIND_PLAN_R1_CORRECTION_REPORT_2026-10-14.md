# DOCUMIND — PLAN REVISION R1: CORRECTION REPORT

**Document ID:** `DOCUMIND_PLAN_R1_CORRECTION_REPORT`
**Companion to:** `backend/architecture/DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_REVISED_R1_2026-10-14.md` (the corrected plan, revision **R1**)
**Companion verification report:** `backend/architecture/DOCUMIND_PLAN_R1_VERIFICATION_REPORT_2026-10-14.md`
**Date:** 2026-10-14
**Baseline HEAD:** `6baaa2a0773df66e5fb26814afbe67647fb43435` (branch `main`)
**Kind:** **DOCUMENTATION ONLY.** No production code, frontend code, test, schema, migration, dependency, model, configuration, deployment file or agent contract was modified by this work. No database was touched, nothing was installed or downloaded, and no git state (staging, commit, push, reset, stash) was altered.

**Digest of the corrected plan.** The corrected plan's SHA-256 is recorded in its own front matter (`Plan SHA-256:` line, computed with that line excluded so the value stays reproducible after substitution). It is deliberately not repeated here: this report is written **before** the plan's final digest is stamped, and any value printed here would be stale the moment the stamp is applied.

---

## 1. What this report covers

R1 is a **targeted correction pass** over revision **R0** (`DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_REVISED_2026-10-14.md`, SHA-256 `5afce228a5b88351321dfb40c7c088f2b2fae398ed86eff1cc92b4a8b0cb4380`, preserved **unmodified**). R1 corrects two distinct classes of defect:

| Class | Origin | Corrections | Where in the plan |
| --- | --- | --- | --- |
| **C1–C4** | Four defects found in R0 by direct inspection during this correction pass (they were carried into R0 from the earlier revision and had not been resolved) | R-22, R-23, R-24, R-25 | §3.1, §5, §7, §10, §14, §15, §16, §18, §19 |
| **V-rounds** | Findings raised by **independent read-only verification rounds performed after the correction pass** (four rounds: 12 + 5 + 3 + 3 = 23 findings) | R-26, R-27, R-28, R-29 | as listed per finding in §3 below |

Every correction is traceable in the plan itself through its §20 change log (rows R-22 … R-29).

---

## 2. Corrections C1–C4 (the correction pass proper)

### C1 — Document-status contradiction removed (finding REV-002; plan R-22)

**Defect.** The plan asserted `ready` = every page produced usable content, `partial` = at least one page usable and at least one not, `error` = no page usable — yet elsewhere stated that a **scanned-only PDF with OCR not implemented** should become `partial` in Phase 1a. That is a self-contradiction: with OCR unavailable, a scanned-only document has **no** usable page.

**Correction.** One authoritative verdict function now lives in **§7.2.1**, with worked cases in **§7.2.2**:

- `pages_usable == 0` ⇒ **`error`** — never `partial` (no usable content anywhere).
- Scanned-only, OCR disabled ⇒ **`error`**, reason `no_text_layer_ocr_disabled`; pages lacking text are reported as **unaccounted**, not as partial success.
- Scanned-only that becomes searchable **after** OCR ⇒ **`ready`** (the full-coverage definition is met by the OCR output).
- `0 < pages_usable < pages_total`, all steps OK, no exception ⇒ **`partial`**.
- Any raised pipeline exception or unusable run ⇒ **`error`** (distinguished from a coverage shortfall).
- The distinction between an **unaccounted page** (coverage) and a **document-level pipeline exception** (verdict) is stated once and referenced everywhere.

**Affected sections.** §3.1, §5, §7.2–§7.6, §14.2 (Phases 1a and 1b), §15.1, §15.2, §19.
**Semantics changed?** No. The explicit status definitions that already existed are kept; only the contradicting sentence is removed and the consequences are spelled out. No owner approval is required for C1 as written.

### C2 — OCR failure is a coverage event, not a verdict (finding REV-002/REV-014; plan R-23)

**Defect.** OCR failure was implicitly equated with `partial`, which would report a wholly unusable document as partially successful.

**Correction.** OCR failure is now classified by its effect on coverage, and the **verdict comes only from the §7.2.1 function**:

| Case | Plan behaviour |
| --- | --- |
| OCR fails on one page, other pages have usable native text | `partial` (provided coverage is a strict subset) — the failed page is reported unaccounted |
| OCR fails on **every** page | `error`, reason `ocr_failed_all_pages` |
| Scanned-only PDF, OCR not attempted (capability absent) | `error`, reason `no_text_layer_ocr_disabled` |
| Mixed native-text + scanned PDF | Per-page: native pages count as usable; scanned pages count only if OCR produced usable output and the verdict follows §7.2.1 |
| OCR output exists but is unusable (below the configured minimum) | The page counts as **unaccounted**, not as usable; verdict follows §7.2.1 |
| Raised pipeline exception anywhere in the runner | `error`, reason `pipeline_exception` |

No OCR engine, confidence threshold, latency figure or accuracy threshold is invented; where such a value is required it remains an owner-approved parameter. New scenarios were added as **§15.1 rows 32–34**, and §15.2 acceptance rules were aligned.

**Affected sections.** §3.1, §7.5, §14.2 (Phase 1b), §15.1, §15.2.

### C3 — The unstoreable persisted value is withdrawn (finding REV-001; plan R-24)

**Defect.** R0 proposed persisting a figure element with `figureRef = None` **plus a failure reason** when asset extraction failed, while also claiming no schema change was needed. The existing data model supports **neither** half of the claim: `document_structure_elements` has no asset column and no failure-reason column (`documents/structure.py` is its only writer), and the evidence contract has no asset field.

**Correction.** Chosen option: **an honest API/reporting contract, no persistence of an unstoreable value.**

- **No figure row is written without a successful asset write.** A figure whose image could not be written is **reported, not stored**.
- `figureRef` is **derived** from columns that already exist (deterministic filename convention + successful write), not stored as a new column.
- **No failure reason is persisted** — there is nowhere to store it. Durable per-figure provenance (asset version, failure reason) is explicitly deferred to **owner gate 25**.
- **No schema field was added and no migration was authorised.** If durable provenance is wanted, that is an owner decision with a migration, recorded as a gate, not smuggled in.

**Affected sections.** §3.1, §10.1, §10.5, §14.2 (Phase 2a), §16.2, §18, §19.

### C4 — Figure-asset lifecycle specified without assuming atomicity (finding REV-001/REV-008; plan R-25)

**Defect.** R0 described figure assets as written "atomically" alongside their database rows. Filesystem writes and database commits are **not** one transaction, and the codebase's storage primitives (`storage/file_store.py`: `delete_upload`, `cleanup_new_file`, containment checks, and a `stat.S_ISREG` refusal of non-regular files) are defensive helpers, not a transaction manager.

**Correction.** A complete, implementable lifecycle:

- **Ordering:** file-first, row-last (`write asset → commit rows → sweep leftovers`) so a failed run can never leave a committed element pointing at a missing file.
- **Asset write succeeds, row persistence fails:** a file **created** by this run is safe to remove (`cleanup_new_file`); an **overwritten** path is **never** deleted by the failing run — it is reported as a stale-but-present asset.
- **Row persistence succeeds, asset write fails:** no figure row is written at all (C3), so this state cannot be represented as success.
- **Process termination during extraction:** residue is reported; **created-and-unreferenced** files are prunable per file, **overwritten** paths are reported and never deleted.
- **Reprocessing:** write-then-commit-then-sweep, so a failed reprocess cannot strip assets from already-committed rows.
- **Document deletion:** per-file deletion through the audited primitive that refuses non-regular files; deletion is scoped to the document's own assets.
- **Orphan reconciliation:** an approval-gated, containment-checked listing helper; nothing is pruned automatically.
- **Cross-document / cross-tenant resolution:** impossible by construction — assets live under the per-user upload subtree and resolution passes the existing containment check (no `..`, no symlink/reparse-point ancestor).
- **Residual limitation:** an interrupted *replace* can leave a partially written file at an overwritten path. The plan states this honestly and routes it to **gate 25** rather than pretending it is solved.

**Affected sections.** §3.1, §10.1, §10.5, §14.2 (Phase 2a), §15.1 rows 33–34, §16.2, §18.

---

## 3. Corrections driven by independent verification (23 findings, four rounds)

The verification rounds are reported in full, with dispositions, in the companion report `DOCUMIND_PLAN_R1_VERIFICATION_REPORT_2026-10-14.md`. Summarised here so the plan's change log and this report agree:

### Round 1 — 12 findings (V3-1 … V3-12) → plan R-26

| Finding | Correction applied |
| --- | --- |
| V3-1 | §6 invariant 5 no longer claims figure assets are replaced **atomically**; it distinguishes atomic **database-row** replacement (savepoint) from non-atomic **file** replacement |
| V3-2 | §7.1 defers to the single §7.2.1 partial/error split instead of restating it |
| V3-3 | §10.5 reprocess ordering changed to write → commit → sweep so a failed reprocess cannot strip assets from committed rows |
| V3-4 | "three edits" corrected to **five** in all five places it appeared |
| V3-5 | The C-11 dependency/gate row fixed, and R-20's overstated "all corrected" claim corrected |
| V3-6 | Gate 24 added to Phase 1a and to matrix row C-1a |
| V3-7 | The integrity row now records the **observed** verification outcome instead of pre-claiming it |
| V3-8 | Three citation ranges corrected |
| V3-9 | The equations test now defers to the §7.2.1 verdict function |
| V3-10 | Rotation row and the phase-map gate list aligned |
| V3-11 | The two-owner request-size row split; the duplicated §16.2 bullet merged |
| V3-12 | Stale baseline row, the missing `file_store.py` single-writer row, and the closing gate range corrected |

### Round 2 — 5 findings (V4-1 … V4-5) → plan R-27

| Finding | Correction applied |
| --- | --- |
| V4-1 (**HIGH**) | §10.5's failure-cleanup rule now distinguishes **created** from **overwritten** asset paths, so a failing run can never strip an asset a committed element references |
| V4-2 | The integrity row and change log now record the verification **rounds** rather than a single report |
| V4-3 | The `file_store.py` single-writer row no longer implies a second owner or a false `C-15` cross-reference |
| V4-4 | A namespace note distinguishes correction ids `C1`–`C4` from matrix rows `C-1a`–`C-18` |
| V4-5 | The REV-003 disposition now qualifies "replaces atomically" as **database rows only** |

### Round 3 — 3 findings (V5-1 … V5-3) → plan R-28

| Finding | Correction applied |
| --- | --- |
| V5-1 (**MEDIUM**) | The created-vs-overwritten rule of V4-1 was fixed in §10.5's first row but **not propagated**; it now reads identically in all four normative places — §10.5 (first row and termination row), §16.2 ("assets **created** by a failed run") and §15.1 row 33 |
| V5-2 | The `processing → partial` transition row now carries the §7.2.1 condition instead of the loose phrase "incomplete coverage" |
| V5-3 | The integrity table no longer cites the accompanying reports as if already present; it states they are delivered in the same task as the revision — and they are (§4 below) |

### Round 4 — 3 findings (V6-1 … V6-3) → plan R-29

| Finding | Correction applied |
| --- | --- |
| V6-1 (**MEDIUM**) | The R0-verification row asserted all 22 R0 findings were corrected; it now matches R-20's record that one (`V2-10`) was claimed but only applied in R1 |
| V6-2 | The figure-asset location was stated two ways (§10.1 step 4 and §14.2 Phase 2a said "the document's own … subtree"; §10.5 said the per-user subtree). It is now stated **once**, canonically, in §10.5 — per-user upload subtree with a deterministic per-figure filename — and the other two places reference it |
| V6-3 | §3.1's correction-`C4` summary now says the defensive cleanup covers **the files that run created**, matching §10.5's normative rule |

---

## 4. Deliverables produced by this task

| # | Artifact | Status |
| --- | --- | --- |
| 1 | `backend/architecture/DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_REVISED_R1_2026-10-14.md` — the corrected plan, a **new** clearly named revision; R0 preserved unmodified | `[V]` created |
| 2 | `backend/architecture/DOCUMIND_PLAN_R1_CORRECTION_REPORT_2026-10-14.md` — this report | `[V]` created |
| 3 | `backend/architecture/DOCUMIND_PLAN_R1_VERIFICATION_REPORT_2026-10-14.md` — the independent verification report, findings + dispositions + blockers | `[V]` created |
| 4 | Integrity evidence (digests, HEAD, staged count, tracked-change count, new-file count, before and after) | `[V]` in §5 below and in the verification report |

---

## 5. Integrity evidence

| Item | Before this task | After this task |
| --- | --- | --- |
| Git HEAD | `6baaa2a0773df66e5fb26814afbe67647fb43435` | `6baaa2a0773df66e5fb26814afbe67647fb43435` (unchanged) |
| Branch | `main` | `main` |
| Staged changes | 0 | **0** |
| Unstaged tracked changes | 330 (295 deletions + 35 modifications) | **330** (295 deletions + 35 modifications) — identical, pre-existing, untouched |
| New files added by this task | 0 | **3** (R1 plan + correction report + verification report), all untracked and unstaged |
| Untracked files, repo-wide (`--untracked-files=all`) | **847** (R0 present, R1 not yet) | **850** |
| Untracked files under `backend/` | **720** | **723** |
| Untracked-file chain (corroborates plan §2.2) | 846 / 719 before R0 existed | 847 / 720 with R0 · 848 / 721 with R0 + R1 · **850 / 723** with R1 + both reports — each file adds exactly one, nothing else changed |
| Source digests re-verified | original plan `fb3c7fea88486fa5fbcd9203ebc0c38bace4c1e2b1150b0029f7831ea205d98b`; review `e6c5a52c17bf333ca876ae0146c742d774506414070dd82859bff05fd8709f0f`; capability audit `d489f912e68acce0a146b2343dcdf71d5397e72de814a1d0330859be65912d0d`; R0 `5afce228a5b88351321dfb40c7c088f2b2fae398ed86eff1cc92b4a8b0cb4380` | all four **recomputed and equal** |

**No destructive statement is made here about files this task did not write.** The 330 pre-existing tracked changes were present before this task and are preserved as found.

---

## 6. Owner decisions preserved (not taken on the owner's behalf)

Nothing in this correction pass resolved an owner decision. All gates remain open, and the plan still stops before implementation: **gates 1–25** in §18, including in particular

- gate 23 — persisting the true PDF page count (required for any honest completeness reporting; see N-001),
- gate 22 — ownership of the deployment files (`backend/Dockerfile`, `backend/docker-entrypoint.sh`, `compose.yaml`, `Dockerfile.frontend`), which no agent contract currently owns (N-002),
- gate 25 — durable per-figure provenance (asset version, per-figure failure reason) and the residual interrupted-replace limitation left open by C4.

The OCR-provenance storage decision (§8, three options) and every metric/limit value remain owner-approved parameters; no number was invented anywhere in this pass.

---

## 7. Attestation

No production file, test, schema, migration, dependency, model, configuration, deployment file or agent contract was read-modified by this task; no database or migration was executed; no package was installed and no model downloaded; no git state was changed; the original plan and the review report are byte-identical to their recorded digests; **no implementation phase was started and no gate was opened.**
