# DOCUMIND — R3 CORRECTION REPORT

**Document ID:** `DOCUMIND_PLAN_R3_CORRECTION_REPORT`
**Task:** targeted concurrency corrections to the R2 implementation plan, plus independent verification and reporting. **Documentation only.**
**Revision this report accompanies:** `backend/architecture/DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_REVISED_R3_2026-10-14.md`
**Report date:** 2026-10-14 (R3 pass executed 2026-10-15; artifact names follow the required paths)
**Kind:** **CHANGE REPORT ONLY.** No production code, frontend source, test, fixture, schema, migration, dependency manifest, model weight, runtime configuration, deployment file or agent ownership contract was modified. No database was contacted. No service was started. No Git state was changed. **No gate was opened or approved, and no implementation phase was started.**

---

## 1. R2 source artifact hashes (the baseline this report corrects)

Measured by the coordinator at the start of this pass, and **re-measured after the R3 pass** to confirm none of them changed. Two conventions are named explicitly, as R2's own integrity table does:

* **Convention digest** — the SHA-256 of the file with its own `Plan SHA-256:` line removed (`grep -v '^Plan SHA-256' <file> | sha256sum`). Only meaningful for a document that has such a line.
* **Full-file digest** — `sha256sum <file>`, with nothing removed.

| Artifact | Convention digest | Full-file digest | Status |
| --- | --- | --- | --- |
| `DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_REVISED_R2_2026-10-14.md` | `2faefa6e013cefd38f38e4abc019d412368448c9df16fc7998b12d56b7668bb0` | `adf5158338546623d49adee7ee5457c4254f30ab8f2a5b44173783b1a98b390b` | **unchanged** before and after this pass (full-file digest re-measured as the first and the last command of the pass) |
| `DOCUMIND_PLAN_R2_CORRECTION_REPORT_2026-10-14.md` | `b74337d2a20c28fd0e63b3b10e7bfe30db1cde4d0d6cb298ef4bb905156209da` (no self-digest line, so the two conventions coincide) | `b74337d2a20c28fd0e63b3b10e7bfe30db1cde4d0d6cb298ef4bb905156209da` | **unchanged** |
| `DOCUMIND_PLAN_R2_VERIFICATION_REPORT_2026-10-14.md` | `a81306255cd2dd799762603d3c74eb3cfe45d5f0b5285006056db556bea1e229` (no self-digest line) | `a81306255cd2dd799762603d3c74eb3cfe45d5f0b5285006056db556bea1e229` | **unchanged** — note that R3 **does not edit** its overbroad test-readiness row; R3 supersedes that statement in the *R3* verification report (finding `B-1`/`K-05`) |

**The R2 stamped value was reproduced from the file, not copied from R2's text**: `grep -v '^Plan SHA-256' R2 | sha256sum` returns exactly `2faefa6e…`, so R2's integrity table is confirmed by measurement rather than trusted.

**Earlier revisions (context, all preserved):** R1 `ddf43920…` (convention) / `ca4d20f4…` (full-file); R0 `13cee365…` (convention) / `5afce228…` (full-file); original plan `fb3c7fea…`; review `e6c5a52c…`. These were not re-measured in this pass and are **not** claimed to have been; they are cited as R2 recorded them.

### 1.1 R3 artifacts produced by this pass

| Artifact | Convention digest | Full-file digest |
| --- | --- | --- |
| `DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_REVISED_R3_2026-10-14.md` | `2c39676ddfb3ef4bf25f2ec380f087d34ee5e3ffda1baad5b353902a7706468a` | `489588f27b9d9dfd877a54ab7e20f8ad50d37c74e2e6fc31b2ca420b84746a01` |
| `DOCUMIND_PLAN_R3_CORRECTION_REPORT_2026-10-14.md` (this file) | — (no `Plan SHA-256:` line, so the two conventions coincide and there is nothing to exclude) | **recorded in the R3 verification report §11** — this file cannot record its own digest without changing it |
| `DOCUMIND_PLAN_R3_VERIFICATION_REPORT_2026-10-14.md` | — (no `Plan SHA-256:` line) | **deliberately not recorded by any artifact of this pass.** The verification report has no self-digest line, so it cannot contain its own digest; and this report cannot cite it, because the verification report cites *this* report's digest — that would be a circular dependency. The reader recomputes it with `sha256sum` |

**Digest scheme used by this pass (stated so the three artifacts can be checked in one order).** The R3 **plan** carries a self-digest line and is stamped excluding that line, so its digest is stable and may be cited by both reports. The **verification** report cites the plan's digest and the **correction** report's digest. The **correction** report cites the plan's digest only. Nothing cites the verification report's own digest. That is a directed acyclic set of references — every digest recorded anywhere in this pass was computed from a file that was already frozen at the time — and it deliberately avoids the mutual-reference pattern in which a document cites a sibling's digest while the sibling cites its own. **No digest value in this pass was copied from another document; each was measured from the file it describes.**

The plan's stamped value excludes its own `Plan SHA-256:` line, so it remains reproducible after substitution; the R3 digest was recomputed **after** the post-review repairs below and re-verified by reproduction (`grep -v … | sha256sum` returns the stamped value). The plan is stamped at `67744c77…`; the value stamped earlier in the pass (`3bd9a694…`) is superseded by the repairs recorded in §7 and is not cited as final anywhere.

---

## 2. Findings used as the baseline

The baseline is the **R2 Final Concurrency and Verification Audit** — a separate read-only audit of R2 delivered in the R2 conversation (no file was created; the audit's own §3 boundary forbade writing). Its findings are used here **not on trust**: every load-bearing claim of it was re-derived from the repository during this pass, and the re-derivation is recorded as evidence in R3 §2.5 (`C-1 … C-9`) and as new findings `N-003/N-004/N-005`.

| ID | Severity | Finding (as the audit stated it) | Re-derived in this pass? |
| --- | --- | --- | --- |
| `A-1` | HIGH | The status guard is a read-then-act check; `processing` is committed only at the end of the request, so two concurrent requests can both pass the guard. R2 relied on the guard as the concurrency mechanism. | **Yes** — R3 §2.5 C-1/C-2/C-3, from `documents/routes.py:672-685`, `:438`, `:713`, `:426-461`; **and extended**: the audit did not note that `processing` is *never* durably committed (C-3) or that a third write path exists (dedupe/requeue, `:409/:412`, `:417/:420`) |
| `A-2` | HIGH | R2's cleanup predicate (\"unreferenced by the currently committed structure\") does not protect another run's uncommitted candidate assets; the failure is not harmless churn. | **Yes** — R3 §2.5 C-6, N-005, from `documents/models.py:165-175`, `graph/models.py:198-205` plus the run-scoped naming rule |
| `A-3` | MEDIUM | R2 describes stale-run recovery that the current transaction shape may not produce. | **Yes** — R3 §2.5 C-4/C-5/C-7 |
| `A-4` | MEDIUM | \"No orphan growth\" is contradicted by a best-effort, approval-gated cleanup. | **Yes** — R3 §9.2, §16.2 and §15.1 rows 23/34 as written in R2 |
| `A-5` | INFO | (Contextual, informational.) | **Yes** — folded into K-03 |
| `B-1` | MEDIUM | The R2 verification report claims any test suite is blocked because the suites need a live database; the prior audit executed the SQLite-backed unit suite successfully. | **Yes** — R3 §2.5 C-9, from `tests/conftest.py:1-9,50` and `pytest.ini:11` |
| `B-2` | MEDIUM | The backend `partial` status is not in the frontend union, while Phase 1a forbids frontend changes — an unowned contradiction. | **Yes** — `src/types/index.ts:8`; the cast claim is corroborated at `src/context/WorkspaceContext.tsx` (`apiDocToFile`) |
| `B-3` | LOW | The old derived-`figureRef` design is not clearly marked superseded wherever it survives. | **Yes** |
| `B-4` | LOW | Ownership-matrix attribution error: the page-record/model decision is assigned to `backend/graph/models.py` although the contract assigns it to `backend/documents/models.py`. | **Yes** — R2 §13.3's `backend/graph/models.py` row listed C-2; C-2's Files column names `backend/documents/models.py` and §8.3 places the new table there |
| `B-5` | LOW | Phase-map gate inconsistencies (Gate 16 for 1b; Gate 26's conditional relevance to 3b; Gate 22 for 5b). | **Yes** — plus two more the audit did not list (see §3, K-07/B-5) |
| `B-6` | LOW | \"A reprocess replaces rows atomically\" must be qualified: a DB transaction does not make filesystem writes/cleanup atomic. | **Yes** |
| `B-7` | LOW | `MIN_USABLE_CHARS` has no stated home or owner. | **Yes** |

---

## 3. Findings corrected, and exactly where

Correction items `K-01 … K-07` are R3's own namespace; they are defined in R3 §3.3 and expanded in R3 §20 entries `R-46 … R-52`. Section numbers below refer to the **R3** document.

### K-01 — `A-1` (HIGH): the status guard is not an atomic claim; a per-document claim is now a required, gated design input

| | |
| --- | --- |
| **Findings** | `A-1`; new `N-003` |
| **R3 sections changed** | §1 (purpose items 1 and the Gate-27 front-matter note), **§2.5 (new; C-1…C-3, C-5, C-6, N-003, N-005)**, §3.3 (K-01), §5 (two new capability rows), §6 (invariant 10 + reading rule), §7.3 (guard paragraph rewritten), §7.5 (transaction shape, points 1-5), §9.2 (concurrency bullet added), §10.1 (two-run failure row), §10.5 (state 1, state 12, concurrency paragraph, limitations, G9/G10), **§10.6 (new)**, §13.1 (C-3 gates; new row C-19), §14.1, §14.2 (Phase 2a), §15.1 (rows 39, 40-47), **§15.6 (new)**, §15.4, §16.2, §18 (Group F, gate 27; consolidated list), §19, §20 (R-46) |
| **Rationale** | The plan stated a concurrency guarantee whose named mechanism cannot deliver it: the guard reads a snapshot and the status it depends on is not visible until the request's final commit, and the repository contains **zero** locks, conditional updates, claims or constraints that could arbitrate (`§2.5` C-1/C-2). A plan that presents a status check as an exclusivity mechanism is unusable as an implementation brief — a reader would build Phase 2a believing the guard protects it. R3 therefore (a) distinguishes *status check* / *atomic claim* / *committed run record* / *stale-run recovery* / *successful commit* / *post-commit cleanup*, (b) withdraws every claim that the guard alone prevents concurrent processing, (c) states that the Option-B lifecycle **requires** a defensible claim, and (d) records the requirement and the owner decision as **Gate 27** instead of selecting a mechanism. |
| **What R3 changed, precisely** | **Guarantee:** added **G9** (exclusive run, no commit after claim loss) and **G10** (stale-claim recoverable without assuming a timed-out worker stopped), both marked **required / not established**. **Acceptance criteria:** new §15.1 rows **40-47** and new **§15.6** (AC-1…AC-7), written to **fail against today's code**. **Phase dependency:** Phase 2a now lists Gate 27 as a prerequisite; §14.1 states that 2a's block is a *decision*, not a phase. **Ownership:** new matrix row **C-19** (proposed, unauthorized); C-3's gates extended. **Gate:** **new Gate 27** (Group F). |
| **Requires an owner decision?** | **Yes — Gate 27.** R3 does not choose between the four candidate mechanisms; it lists them for evaluation and explicitly rejects the status guard, run-scoped names, the immediate re-read, a bare timeout and \"last commit wins\" as sufficient on their own. |

### K-02 — `A-2` (HIGH): the cleanup sweep could delete an active run's candidate assets

| | |
| --- | --- |
| **Findings** | `A-2`; new `N-005` |
| **R3 sections changed** | §3.3 (K-02), §6 (invariants 8-10 + reading rule), §10.1 (two-run failure row; asset-missing row), §10.5 (**six asset classes** *new*, cleanup procedure rewritten (i)-(vii), guarantees table rebuilt **G3→G3′/G3″** + G8 narrowed + G9/G10, limitations rewritten), §10.6, §13.1 (C-3, C-19), §14.2 (2a), §15.1 (rows 23, 34, 39; 40-47), **§15.5 (new)**, **§15.7 (new)**, §15.4, §16.2, §19, §20 (R-47) |
| **Rationale** | R2's cleanup predicate answers \"does the committed structure reference this file?\" — and a concurrent run's candidate answers **no**, so the sweep matches it and deletes it, after which that run commits a structure referencing deleted files. R2 then described the outcome as \"churn, not corruption of the committed set\". That is not a limitation, it is a defect with a data-integrity consequence, so R3 (a) drops the churn framing and states the failure explicitly, (b) requires an **active-run exclusion**, (c) defines the six classes cleanup must distinguish and makes exactly one of them deletable, (d) makes the indeterminate case **delete nothing and report**, (e) records that \"re-read the committed reference set immediately before deletion\" is necessary but **not sufficient**, and (f) forbids relying on run-scoped filenames alone. |
| **What R3 changed, precisely** | **Guarantee:** **G3 is split** — G3′ (no referenced asset is deleted) is necessary-not-sufficient; **G3″** (no active run's asset is deleted) is **not established**; G8 narrowed (\"unreferenced\" no longer implies \"residue\"). **Acceptance criteria:** new **§15.7** (CC-1…CC-8, the last being a cross-scenario zero-committed-references assertion) and **§15.5** (RC-1…RC-7). **Phase dependency:** unchanged in ordering, but the phase's *scope* gains the exclusion mechanism and its block is restated. **Ownership:** none changed; the exclusion work sits in C-3/C-19. **Gate:** Gate 27. |
| **Requires an owner decision?** | **Yes — Gate 27.** Also an owner policy question (which residue is tolerated, whether an automatic sweep is enabled) which R3 leaves with the owner by design. |

### K-03 — `A-3` (MEDIUM) / `A-5`: the stale-run and failure-recovery story did not match the code

| | |
| --- | --- |
| **Findings** | `A-3`, `A-5`; new `N-004` |
| **R3 sections changed** | §3.3 (K-03), **§7.3** (the `processing → processing` transition row marked unreachable), **§7.5 (rewritten around three single-transaction paths)**, §9.2, §10.5 (states 1, 4, 5), §10.6 (property 5; `processing_started_at is None`), §15.1 (rows 33, 41, 42, 43, 44), §15.6, §16.2, §18, §20 (R-48) |
| **Rationale** | R2 told readers that a crash is recovered by the existing stale-run path. `[V]` the upload and reprocess paths each commit **once**, at the end, after the pipeline has already set the final status — so `processing` is never durably observable, a crash rolls the whole transaction back, and the document retains its **previous committed status** (not `error`, and not stale). The stale path can only act on a *committed* `processing` row, which today's code never writes. Two further consequences are now stated: a crashed **initial upload** leaves no row at all and the stored file is an orphan upload (a class the repo already handles with a dry-run, abort-on-unreadable script); and a crash during **reprocess** leaves the previous status, which is honest because the previous structure is still the authoritative one. Correcting this also required naming the consequence R2 missed: **committing a claim creates a durable `processing` state for the first time**, so any lease must write its timestamp in the same committed statement, or `processing_started_at is None ⇒ stale` (`[V]` `:325-326`) would make it immediately reclaimable. |
| **What R3 changed, precisely** | **Guarantee:** none weakened; G1's scope is now stated against the correct transaction shape. **Acceptance criterion:** §15.1 row 33 corrected (its R2 assertion is explicitly withdrawn); rows 41-44 added. **Phase dependency / ownership:** unchanged. **Gate:** no new gate; the `processing_started_at` requirement is folded into Gate 27's required properties. |
| **Requires an owner decision?** | No for the documentation. **Yes** for any recovery mechanism, which R3 does not invent. |

### K-04 — `A-4` (MEDIUM): \"no orphan growth\" replaced by measurable criteria

| | |
| --- | --- |
| **Findings** | `A-4` |
| **R3 sections changed** | §3.3 (K-04), §9.2, **§15.5 (new, RC-1…RC-7)**, §15.1 (rows 23, 34), §15.4, §16.2, §19, §20 (R-49) |
| **Rationale** | R2 required \"no orphan growth\" while also defining cleanup as best-effort and reconciliation as approval-gated — a criterion its own design cannot meet, in a document whose stated purpose is honesty. R3 removes the phrase everywhere it was a requirement and replaces it with properties the described mechanism can actually demonstrate. |
| **What R3 changed, precisely** | **Guarantee:** G8 restated (residue is unreferenced **and reported**, not eliminated). **Acceptance criteria:** §15.5 RC-1…RC-7 replace the phrase; §15.1 rows 23 and 34 carry the replacement explicitly. **Phase dependency / ownership:** unchanged. **Gate:** none new; the owner retains cleanup policy. |
| **Requires an owner decision?** | No. But R3 states plainly what the owner is *not* being promised: **zero orphans**. |

### K-05 — `B-1` (MEDIUM): test-readiness accuracy

| | |
| --- | --- |
| **Findings** | `B-1` |
| **R3 sections changed** | §2.5 (C-9), §15.5, §19, §20 (R-50) — **and the R3 verification report §2/§5, which is where the corrected statement lives** |
| **Rationale** | R2's verification report recorded \"Running any test suite — **BLOCKED** … the suites need a live database\". `[V]` the suite's default engine is in-memory SQLite (`tests/conftest.py:1-9,50`) with `testpaths = tests` (`pytest.ini:11`), and the **prior** audit already executed the unit suite successfully (1,345 passed, 23 skipped, exit 0, ≈67.6 s). The overbroad claim hid a large body of runnable verification and, worse, was the kind of statement that makes \"blocked\" meaningless. |
| **What R3 changed, precisely** | **Guarantee:** none. **Acceptance criteria:** no change to the plan's criteria; the *reporting* rule changes. **Phase dependency / ownership:** unchanged. **Gate:** none. |
| **Requires an owner decision?** | No. |
| **Important limitation stated rather than hidden** | The 1,345/23/exit-0/≈67.6 s figure is **prior-audit evidence, not a result of this pass**. R3 (the plan) states only the engine fact; the R3 verification report separates *previously executed unit results* / *tests not run in the R2 pass* / *tests not run in this R3 pass* / *PostgreSQL-dependent integration* / *browser E2E*, and claims nothing about the last two. **No test suite was run in this pass except the static checks listed in §6.** |

### K-06 — `B-2` (MEDIUM): the `partial`-versus-frontend decision is presented, not assumed

| | |
| --- | --- |
| **Findings** | `B-2` |
| **R3 sections changed** | §1 (purpose item 6), §3.3 (K-06), **§12.2 (Option A / Option B table + honest window note)**, §14.2 (Phase 1a: prerequisites, gates, *Must not edit* scoping, the Option A/B paragraph; Phase 6 marked the mandatory follow-up owner), §15.1 (row 24), §15.5, §18 (gate 4 sub-decision; §18 preamble), §19, §20 (R-51) |
| **Rationale** | R2 added `partial` in Phase 1a and required the frontend union/mapper/rendering to change \"together\", while Phase 1a's own *Must not edit* list forbade `src/**`. That is a contradiction with two admissible resolutions and no owner decision, so a reader could not tell what Phase 1a was allowed to touch. R3 states both resolutions with their scope, ownership, user-visible behaviour, gates, follow-up and risk, and chooses neither. It also describes the interim behaviour honestly: because `apiDocToFile` **casts** rather than validates, a `partial` value passes the type check unchanged and is *not guaranteed* any correct UI representation — so Option B's window is a real, owner-acceptable trade-off rather than a cosmetic detail. |
| **What R3 changed, precisely** | **Guarantee:** none. **Acceptance criteria:** §15.1 row 24 now names the phase conditionally and forbids asserting a correct `partial` rendering during an Option-B window. **Phase dependency:** Phase 1a's file scope and gate list are conditional on the choice; Phase 6 becomes the mandatory owner of the follow-up under Option B. **Ownership:** optionally adds `FRONTEND_AGENT` to Phase 1a for **three files only**, and **no ownership contract is edited** (`src/**` is already `FRONTEND_AGENT`'s); gate 12 becomes conditional in 1a because the mapper test needs a runner that does not exist. **Gate:** existing **gate 4** gains an explicit sub-decision. |
| **Requires an owner decision?** | **Yes — gate 4 sub-decision.** Neither option is selected. |

### K-07 — `B-3 … B-7` (consistency): five defects corrected at their root

| Sub-item | Finding | R3 sections changed | Rationale | What changed |
| --- | --- | --- | --- | --- |
| **B-3** | Derived-`figureRef` not marked superseded | §1 (new \"Superseded statement\" paragraph), §3.1 (history note + `C3` row struck through and labelled), §10.1 step 5 (named the authoritative statement), §20 (`R-24` struck through) | R1's derived reference is genuinely withdrawn by R2 (run-scoped names make it unidentifiable), but two places still read as current design, and a reader could implement the wrong rule | **Guarantee:** one authoritative identity statement (Gate 26's table in §10.5). **Gate:** unchanged (Gate 26 vs Gate 27 separation now also stated in §10.1 item 7) |
| **B-4** | Wrong ownership attribution | §13.3 (`backend/graph/models.py` row → **C-3b only**, with the correction note) | The page-record model is the new `document_page_extractions` table declared in `backend/documents/models.py` (§8.3), not a `graph/models.py` table; a matrix that names the wrong file misdirects a writer | **Ownership:** corrected assignment; §13.3 now agrees with §13.1 |
| **B-5** | Phase-map gate mismatches | §5 (gate columns), **§14.1 (map rewritten)**, §14.2 (authoritative lists unchanged); plus §13.1 C-11/C-12 gates | The map is what an implementer reads first; six mismatches (the audit named three) meant the map and the specs disagreed | **Phase dependency:** map now equals spec for all eleven phases (**16/22** for 1b; **21** for 7; **22** for 5b; **26** shown conditional for 2a/3b/6; **24** for 1a; **12** conditional in 1a) |
| **B-6** | Atomicity wording | §6 (invariant 5), §14.2 (Phase 1a), **§15.4 (new wording table)** | \"Replaces rows atomically\" was read as covering the filesystem; it never did | **Guarantee:** the claim is scoped to the database transaction; §15.4 lists the permitted and forbidden meanings of eight phrases, including two (`no orphan growth`, `safe under concurrency`) that are **not permitted at all** |
| **B-7** | `MIN_USABLE_CHARS` home/owner unstated | §14.2 (Phase 1a: three candidate homes + owner), §18 (gate 24 row extended) | The verdict cannot be computed without the constant, and \"gate 24 = the value\" left its location — hence its ownership and its configuration surface — undefined | **Ownership:** three candidate homes named with an owner; **no configuration value is introduced implicitly**. **Gate:** gate 24 extended (not renumbered) |

**Two additional consistency defects found by R3's own sweep** (not in the audit's list, corrected in the same pass): the §5 capability matrix's gate columns for status honesty (missing 24), figure citation, figure assets, diagram generation, frontend UI and live E2E (missing 21) — corrected in §5; and the §13.3 attribution omission of `backend/documents/structure.py`, which C-3 and C-3b both write — a row was added.

---

## 4. Guarantee / criterion / dependency / ownership / gate impact — summary

| Finding | Guarantee | Acceptance criterion | Phase dependency | Ownership | Gate |
| --- | --- | --- | --- | --- | --- |
| K-01 (`A-1`) | **added G9, G10** (required, not established) | **+rows 40-47; +§15.6** | **2a blocked on a decision** | **+C-19** (proposed); C-3 gates | **+gate 27** |
| K-02 (`A-2`) | **G3 split → G3′/G3″; G8 narrowed** | **+§15.7; +§15.5** | 2a scope becomes the exclusion mechanism | unchanged | gate 27 |
| K-03 (`A-3`) | G1 scope restated | **row 33 corrected; +41-44** | unchanged | unchanged | property folded into gate 27 |
| K-04 (`A-4`) | G8 restated | **\"no orphan growth\" removed; +§15.5** | unchanged | unchanged | none (owner retains policy) |
| K-05 (`B-1`) | none | reporting rule only | unchanged | unchanged | none |
| K-06 (`B-2`) | none | **row 24 made conditional** | **1a scope + gates conditional; 6 becomes mandatory follow-up** | **+FRONTEND_AGENT in 1a (option A only), 3 files; no contract edited** | **gate 4 sub-decision**; gate 12 conditional |
| K-07 (`B-3`) | one authoritative identity rule | unchanged | unchanged | unchanged | gate 26/27 separation stated |
| K-07 (`B-4`) | none | none | none | **corrected file attribution** | none |
| K-07 (`B-5`) | none | none | **map reconciled with specs** | **C-11/C-12 gate columns corrected** | 26/24 added to two matrix rows |
| K-07 (`B-6`) | atomicity scoped | **+§15.4** | none | none | none |
| K-07 (`B-7`) | none | none | none | **three candidate homes named** | **gate 24 extended** |

**Net gate position: gates 1-26 are carried forward exactly as R2 left them; R3 adds Gate 27 and extends gate 24's row. No gate is closed, opened or altered otherwise. No gate is approved by this pass.**

---

## 5. Findings that could not be resolved without an owner decision

These are **not** unresolved defects in the document — they are decisions the document now names correctly and hands to the owner. Each is a place where R3 could not "fix" anything without choosing on the owner's behalf.

| # | Open decision | Gate | What R3 did instead |
| --- | --- | --- | --- |
| 1 | The per-document claim mechanism, its run identity, its stale-claim evidence, commit-after-claim-loss, and the cleanup exclusion | **27** (new) | stated eleven required properties, eleven cases, four candidate mechanisms for evaluation, five mechanisms explicitly rejected as insufficient, and made Phase 2a's block explicit |
| 2 | Whether Phase 1a includes the minimum frontend change | **4** (sub-decision) | presented Option A and Option B with scope, ownership, behaviour, gates, follow-up and risk; chose neither |
| 3 | The `MIN_USABLE_CHARS` value **and its home** | **24** (extended) | named three candidate homes with an owner and stated that no configuration value is introduced implicitly |
| 4 | Which file a committed figure element names | **26** | kept as-is; explicitly separated from Gate 27 so it cannot absorb concurrency control |
| 5 | Whether a durable per-figure provenance field is ever stored | **25** | unchanged; R3 only re-states that this is provenance, not lifecycle |
| 6 | Provenance storage option A/B/C, coverage fields, downgrade authority, deployment-file ownership | **3, 23, 20, 22** | unchanged |

---

## 6. Checks actually performed in this pass, and their results

| Check | Command / method | Result |
| --- | --- | --- |
| R3 destination free before writing | `test -e` on all three required R3 paths | **free** — nothing overwritten |
| R2 (and its two reports) unmodified | `sha256sum` at baseline and after the pass | **identical** — `adf51583…`, `b74337d2…`, `a8130625…` |
| R2 stamp reproducible from the file | `grep -v '^Plan SHA-256' R2 \| sha256sum` | `2faefa6e…` — **matches R2's own stamped value** |
| R3 stamp reproducible | `grep -v '^Plan SHA-256' R3 \| sha256sum` | `67744c77…` — **matches the stamped line** |
| Git baseline unchanged | `git rev-parse HEAD`; `git rev-parse --abbrev-ref HEAD`; `git diff --cached --name-only \| wc -l`; `git diff --name-only \| wc -l`; `git ls-files --others --exclude-standard \| wc -l` | HEAD `6baaa2a0773df66e5fb26814afbe67647fb43435`, branch `main`, staged **0**, unstaged tracked **330**, untracked **853** at baseline and **856** after the pass (the three new R3 artifacts; `726 → 729` under `backend/`) |
| Concurrency facts re-derived from source | direct reads of `documents/routes.py`, `documents/models.py`, `graph/models.py`, `storage/database.py`; scoped searches for `with_for_update`/`FOR UPDATE`/`pg_advisory`/`advisory_lock`/`run_id`/`asset_ref` | recorded as R3 §2.5 C-1…C-8; **0** application-code hits for locks and for the two identifiers |
| Dedupe/requeue write path exists | `sed` of `documents/routes.py:404-422` | confirmed — `_process_document` + `commit()` at `:409/:412` and `:417/:420` (**corrected R3, which first said \"two paths\"**) |
| Constructor line numbers | `grep -n 'status="processing"'`, `grep -n 'file_size=len'` | **438** and **435** respectively (R3 first said `:435` for the status — **repaired**) |
| `testpaths` line number | `cat -n pytest.ini` | **line 11** (R3 first said `:9` — **repaired**) |
| Test engine is SQLite | reads of `tests/conftest.py`, `pytest.ini`, `tests/fixtures/{integration_db,disposable_db}.py` | confirmed |
| No test suite was run to "look comprehensive" | — | **Correct: no pytest invocation was made in this pass.** Only static/documentation checks and hash/count measurements, as the task requires |
| Static consistency of the R3 document | heading scan (`^## `, `^### `); searches for every withdrawn phrasing | all 20 sections present in order; §2.5, §3.3, §10.6, §15.4-§15.7 and Group F added; each withdrawn phrasing either absent or explicitly labelled withdrawn |
| Independent read-only reviews | two reviewers (angles and results in the R3 verification report) | findings returned; **every load-bearing one re-derived by the coordinator** before use; the repairs they produced are listed in §7 |

---

## 7. Post-review repairs (what the independent reviews changed in R3)

Two read-only reviewers inspected the plan **after** it was first drafted and stamped. Their findings were re-derived by the coordinator; the following were confirmed and repaired, and the R3 stamp was recomputed (`3bd9a694…` → `67744c77…`).

| # | Finding (source) | Repaired in R3 |
| --- | --- | --- |
| 1 | `:435` is `file_size`, not `status="processing"` (Reviewer A) | §2.5 C-3 and §7.5 point 1 now cite **`:438`**; the §7.5 table row's range corrected to `:430-441` |
| 2 | \"Exactly two write paths\" understates the code — the dedupe/requeue branch commits too (Reviewer A) | §7.5 rewritten around **three** paths, with `:412`/`:420` and the consequence that the dedupe branch is a **second instance** of the A-1 defect |
| 3 | Integrity row claimed Gate 27 appears in §13.3 and §15.5, where it does not, and omitted §1/§2.5/§6/§7/§9/§20 (Reviewer B) | the list was **re-counted per section**; §15.5 additionally gained a genuine Gate-27 dependency statement (so the claim is now true of §15.5), and §13.3's `documents/routes.py` row now names C-19's gate-27 decision |
| 4 | §15.1 row 38 still cited `G3`, an identifier the same revision split into G3′/G3″ (Reviewer B) | row 38 now cites **G1/G3′**, with the G3″ half pointed at §15.7 |
| 5 | Integrity row referenced a \"§20 companion statement\" that does not exist (Reviewer B) | reference corrected to the R3 reports themselves, **plus** the reason the plan does not embed sibling digests: the reports hash this plan, so embedding theirs would be circular |
| 6 | `pytest.ini:9` is a comment; `testpaths` is line 11 (Reviewer B) | §2.5 C-9 corrected to `:11` |
| 7 | `AGENTS.md` §03 does not contain the frontend state requirement; §04 does (Reviewer B) | §12.2 corrected to cite `AGENTS.md` **§04 — Frontend** |
| 8 | §10.5 states 6, 7 and 10 read as unconditional safety statements (Reviewer A) | each now carries its active-run-exclusion qualifier and a note that the qualifier was added after review |
| 9 | §7.5 point 3(a) lacked the \"before the commit at `:456`\" bound (Reviewer A) | bound added, with the after-commit case stated |
| 10 | G2's concurrency claim rests on a collision-free run identifier (Reviewer A) | stated explicitly in the guarantees table; **Gate 27 property 3** now requires collision-freedom and cites the existing `evaluation/artifacts.py:77 new_run_id()` precedent (not reusable from production per `AGENTS.md` §03) |
| 11 | A run-identity convention already exists in the research layer; the \"zero hits\" claim should be scoped (Reviewer A) | §2.5 C-2 now states the two scoped searches actually run, notes that a bare `lease` search was **not** run and would produce substring false positives, and records the `evaluation/artifacts.py:77` precedent |
| 12 | G7 has no acceptance test (Reviewer A) | a note states this is deliberate and that G7 is enforced by §15.4's wording table |
| 13 | §13.1 C-11/C-12 gate columns still disagreed with §14.2 (Reviewer B) | C-11 gains **26**; C-12 gains **24** |
| 14 | §13.3 omits `backend/documents/structure.py` although C-3 and C-3b both write it (Reviewer B) | row added |
| 15 | §1 said the derived `figureRef` \"survives in two places\" while §10.5 also discusses it (Reviewer B) | §1 now distinguishes the **two restatements** (both struck through) from §10.5's **rejection** |

**Not repaired, and why** — see §8.

---

## 8. Unresolved issues carried forward

These are carried forward **deliberately** and are not defects of this report:

1. **Gate 27 is undecided and Phase 2a remains blocked.** Consequently the plan asserts **no** concurrency safety for the Option-B asset lifecycle, and §15.6/§15.7's criteria are marked **proposed, not executed, and not satisfiable by the current code** — which is their purpose.
2. **The A-1/A-2 races were never reproduced at runtime.** No database was contacted (the task forbids it), so the two HIGH defects are established by reading the transaction shape and the predicate, not by a measurement. This is stated in the R3 verification report as a limitation, not as a pass.
3. **The stale-run path's reachability conclusion is a reading of the code**, not a kill-test result. Reviewer A reached the same conclusion independently by a different route (the commit-site inventory), which raises confidence but is still static analysis.
4. **R2's verification report still contains the overbroad test-readiness row.** R3 does not edit R2 (preservation requirement) and instead supersedes that statement in the R3 verification report. A reader comparing the two reports must use the R3 one.
5. **`src/context/WorkspaceContext.tsx`'s cast could not be re-read end-to-end in this pass** by the reviewers (file size); the cast claim rests on the coordinator's read. The frontend union fact (`src/types/index.ts:8`) is independently confirmed by both reviewers and by source.
6. **The `MIN_USABLE_CHARS` home remains an owner decision** (gate 24). R3 lists three candidates; it does not pick one, because picking one would introduce a configuration change.
7. **No test suite, database, migration, service or Git operation was performed.** The gate-27 acceptance suites, the cleanup concurrency suites and the residue criteria exist as **proposed criteria only**.
8. **The R2 audit's own runtime-outcome measurements** (e.g. any observed overlapping-run behaviour) could not be reproduced in this pass for the same reason as (2).

---

## 9. Preservation of R2 and every previous artifact

**Confirmed by digest before and after this pass:**

* R2's plan — `adf51583…` (full file) / `2faefa6e…` (convention) — **unchanged**.
* R2's correction report — `b74337d2…` — **unchanged**.
* R2's verification report — `a8130625…` — **unchanged**.
* R1's plan and both R1 reports, R0, the original plan, the review report, the capability audit, the 1.6-series artifacts and every other pre-existing file under `backend/architecture/**` — **not written to by this pass**. R3 was created as a **copy of R2** and then edited, exactly as R2 was created as a copy of R1; no file was overwritten, renamed, moved or deleted, and no `backend/architecture/**` file was modified other than by creating the three new R3 artifacts.
* **Every pre-existing user modification and untracked file was preserved.** The Git baseline is unchanged apart from the three intended new untracked R3 artifacts: HEAD `6baaa2a0…`, branch `main`, staged 0, unstaged tracked 330 (untouched), untracked 853 → 856 repo-wide (726 → 729 under `backend/`).

**Not modified by this pass (explicitly):** production backend code, frontend source, tests, fixtures, database models, migrations, dependency manifests/lockfiles, model weights, inference configuration, runtime configuration, deployment files, agent ownership contracts, and every existing documentation artifact.

---

## 10. Explicit confirmation: no implementation, no gate approval

**No implementation was performed and none was authorized.** Specifically, in this pass:

* no production, frontend, test, fixture, schema, migration, dependency, model, configuration, deployment or ownership-contract file was created, edited, moved or deleted;
* no database was contacted and no migration was run or authored;
* no service, container or deployment workflow was started;
* no dependency or model was installed or downloaded;
* no Git state was mutated — nothing staged, committed, pushed, reset, cleaned or stashed;
* **no gate was opened, closed, altered or approved**, including the newly added **Gate 27**, which is recorded as **not approved**; and
* **no phase was started**, and **Phase 2a remains blocked on Gate 27**.

**Owner review is not implementation authorization.** The R3 artifacts exist so the owner can decide gates 4, 24, 26 and 27 (and the others already listed) with the claims corrected. Nothing in this pass authorizes a line of code.

---

## 11. Where each required report element lives

| Required element | Location |
| --- | --- |
| R2 source artifact hashes | §1 |
| R2 audit findings used as baseline | §2 |
| Every finding ID addressed | §2 (baseline table) and §3 (per-finding correction) |
| Exact R3 section(s) changed per finding | §3, each sub-table's \"R3 sections changed\" row; consolidated in R3 §20 `R-46 … R-52` |
| Rationale per correction | §3, each sub-table's \"Rationale\" row |
| Whether a guarantee / criterion / dependency / ownership / gate changed | §4 (summary matrix), plus the \"What R3 changed, precisely\" row of each §3 sub-table |
| Findings needing an owner decision | §5 |
| Unresolved issues carried forward | §8 |
| Confirmation R2 and previous artifacts were preserved | §1 and §9 |
| Confirmation no implementation or gate approval occurred | §6 (what was run) and §10 |
