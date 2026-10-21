# DOCUMIND — R5 CORRECTION REPORT

**Document ID:** `DOCUMIND_PLAN_R5_CORRECTION_REPORT`
**Date:** 2026-10-14
**Task:** R5 — Gate 27 lifecycle-criteria completion, citation re-measurement and R4-review follow-up (documentation only)
**Scope:** documentation readiness only. **This is not implementation authorization.**

**Integrity:** this report has **no self-digest line**. Its full-file SHA-256 is recorded in **§11 of the R5 verification report** (the only reference direction: verification report → correction report → plan). It was frozen before that §11 was written.

---

## 1. Pre-flight inspection actually performed

| Item | Result |
| --- | --- |
| R5 destinations free? | **yes** — `test -e` on all three R5 paths returned "free" **before any write** |
| R4 baseline artifacts read | `…_PLAN_REVISED_R4_2026-10-14.md`, `DOCUMIND_PLAN_R4_CORRECTION_REPORT_2026-10-14.md`, `DOCUMIND_PLAN_R4_VERIFICATION_REPORT_2026-10-14.md` — all present |
| R4 digests re-measured in this pass | plan stamp `3975c8774c4fec137d344a1e51f72d7df480d9b7b250937f4db76cb5bd72c8e0` (convention: `Plan SHA-256:` line excluded); full-file `49d7976b5fc593d25b01b54253a001e00887ff853a8cdbb2e7853ec72df03b1d`; correction report `386c294ed025080d78bedd67da470db7108d75d14ff78e8669442087a05df806`; verification report `b513a45ad1e5c2b5143f6ccb44cd7e5a598bf4e729f5ff2d1461941715f4db32` |
| Earlier revisions re-measured | R3 `2c39676d…`/`489588f2…`, `233f1bd8…`, `ab98ff8f…`; R2 `2faefa6e…`/`adf51583…`; R1 `ddf43920…`/`ca4d20f4…`; R0 `13cee365…`/`5afce228…`; original plan `fb3c7fea…` — **all unchanged** |
| Source re-measured | `backend/documents/routes.py`, `backend/documents/structure.py`, `backend/tests/conftest.py`, `backend/pytest.ini` (line numbers in §4) |
| Coordinator's earlier numbers trusted? | **No.** Every value reported here was re-measured in this pass; nothing was carried over as a fact |
| Missing artifact? | **none** — no expected file was absent; nothing was fabricated or inferred |

## 2. R5 artifacts created

| Path | State |
| --- | --- |
| `backend/architecture/DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_REVISED_R5_2026-10-14.md` | created as a copy of R4, then edited; stamped (§11) |
| `backend/architecture/DOCUMIND_PLAN_R5_CORRECTION_REPORT_2026-10-14.md` | this file |
| `backend/architecture/DOCUMIND_PLAN_R5_VERIFICATION_REPORT_2026-10-14.md` | created after this report; carries the digest manifest in §11 |

**Nothing was overwritten, renamed, moved or deleted**, and no earlier revision's text was edited.

## 3. The findings, and what was actually done

Status labels are used exactly: **resolved** · **verified — no change needed** · **partially resolved** · **deferred (open requirement)** · **unverified**.

| # | Finding | Sev | Defect before correction | Correction made | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| **R5-01** | Gate 27 had no acceptance criteria for the lifecycle-ending/environmental scenarios; R4 recorded them as a "gap" | MED | R4 §15.6 named four cases and stopped. §10.6 properties **4** and **9** required release-on-unexpected-end and per-scenario crash/retry behaviour, but **no criterion, criterion row or coverage state existed** anywhere for request timeout, client disconnect, container restart, termination-after-claim or release-after-abnormal-end. Naming a gap left both the required behaviour and its verification undefined — and **a named gap is not a covered requirement** | New **§15.8** enumerates **eight** scenarios with protected invariant, expected observable behaviour, Gate 27 requirement identifier, criterion **or** explicit `DEFERRED` marker, and verification class. Five criteria **AC-9…AC-13** added in §15.6; five §15.1 rows (**49-53**); §10.6 properties 4 and 9 refined to require **per-scenario** treatment; §19 gains the mandatory public wording. **Counts stated explicitly: 2 `SPECIFIED`, 5 `PARTIAL`, 1 `DEFERRED` (no criterion), 0 fully covered.** Only mechanism-independent observable outcomes were turned into criteria; every mechanism-dependent clause is marked `DEFERRED` and **counted as open** | the checked-out source for today's behaviour (§7.5's transaction table; `documents/routes.py:445-461`, `:696-713`; `storage/database.py:56-63`); the R4 text for the pre-correction state | **resolved** as a documentation task (criteria written, deferrals explicit); **the deferred requirements remain open** |
| **R5-02** | The failed-asset-write mapping was reported as mis-routed to row 45 | LOW | R4 had already corrected the sentence, but it read as though an **AC-row** covered the case, and §15.6's AC list contains **no** asset-write criterion | **Verified against the matrix and made explicit:** the coverage is **§15.1 row 38** ("Failed replacement preserves the previous committed structure (failure injection)", whose criterion injects "an asset write failing"); **row 45** is the failed-claim/failed-transaction case. §15.6 now says so, and §15.8's matrix cites **row 38**. All `row 38`/`row 45` occurrences searched — **no duplicate or contradictory mapping remains** | §15.1 rows 38, 44, 45, 47 read directly | **verified — one clarification; no claim changed** |
| **R5-03** | Stale/inconsistent source references had to be re-measured, not trusted | LOW | Candidate ranges from earlier rounds had to be confirmed against the checked-out source before any claim could rest on them; one block range was cited loosely | **Full sweep performed.** All current-claim citations are **exact**: `routes.py` `:427` (save_upload), `:438` (status=processing; `:435` is `file_size`), `:442` (add), `:445` (flush), `:452` (pipeline), `:456` (commit), `:398-405` (dedupe probe), `:408`/`:412`/`:416`/`:420` (dedupe/requeue), `:672-685`/`:681` (reprocess guard), `:696-697` (chunk delete), `:701-705` (structure delete, statement `:702`), `:708`/`:711`/`:713` (flush/pipeline/commit); `structure.py` `:79`, `:103` (savepoint), `:110` (`delete(DocumentTableRow)`), `:113` (`delete(DocumentStructureElement)`), `:117` (`flush`); `conftest.py` `:50`, `:147-149`, `:154-156`; `pytest.ini` `:11`. **One refinement made:** the nested-delete block now names its two statements instead of a single range | direct line-number search of each file **in this pass** | **resolved** (sweep + one refinement); **historical entries keep their original ranges as history**, labelled |
| **R5-04** | The front matter carried a duplicated identity block for R1 | LOW | R4's front matter introduced R1 **twice** under the same label with identical digests | **Removed.** One "Also corrects (earlier revisions of record)" line now states R3, R2 and R1 **once each**; the repair is recorded in the front matter. **No digest value was changed or dropped** | the finished R4 front matter read directly | **resolved** |
| **R5-05** | Correction history, finding register and integrity table needed reconciliation | MED | R4's integrity rows still read as R4-pass text ("both created in this pass"), the register stopped at `R-61`, the ledger ended at 859 / 732, and completeness claims were not scoped to the R5 evidence | **Reconciled:** new integrity rows for the R5 plan, the **R4 preservation**, the R5 pass, the R5 review and the R5 reports; the R4 report row labelled as history; ledger extended to **862 / 735**; §20 extends `R-61` → `R-69`; §3.5 added as this pass's register. Every "complete and consistent" claim names the check that supports it | measurements in §11 and the searches in §4 | **resolved** |
| **R5-A1** | *(own audit)* §15.6 described scenario coverage in prose while §15.8 assigns status | LOW | the same requirement could read as **covered in one place and deferred in another** | **Single source of truth:** §15.6 now defines the criteria and the eleven-case mapping and **defers every coverage status to §15.8** | §15.6/§15.8 read as a pair after the edit | **resolved** |
| **R5-A2** | *(own audit)* §10.6 property 9 collapsed process death, restart, timeout and disconnect into one requirement | LOW | a single "crashes" statement does not describe what the runtime does to the process, the request context and the connection — three different endings | **Refined:** properties 4 and 9 now require **per-scenario** treatment, cite the criteria that exist, and state which half is `DEFERRED` | §10.6 properties 4 and 9 | **resolved** |
| **R5-A3** | *(own audit)* §19 had no row for unexpected-termination/release semantics | LOW | a reader could infer that an abandoned run is somehow resolved | **Row added** with mandatory wording: an abnormally ended run is **not resolved by any mechanism that exists**, its claim state is **undefined** until gate 27 is decided, its observable document state is covered only by proposed criteria, and **no recovery, release or cleanup may be claimed for it** | §19's table | **resolved** |

## 3.1 Findings raised by the independent review of R5, and their repairs

The read-only reviewer of the R5 artifacts (file access only, **no shell**, no runtime) returned **REVISE BEFORE OWNER REVIEW** on five defects plus one precision note. All six were re-derived by the coordinator against the files before repair, and the plan was re-stamped afterwards.

| # | Reviewer finding | Re-derived? | Repair |
| --- | --- | --- | --- |
| **D1** | the plan's front-matter Gate-27 paragraph claimed "Six of the eight have at least one specified criterion; two do not", contradicting §15.8's matrix (seven carry at least one; only `S5` has none) and the verification report's "agrees on the counts" claim | **confirmed, row by row** | front matter now reads "**Seven of the eight…; one (`S5`) has none**"; the wrong sentence is **recorded as superseded, not silently replaced** |
| **D2** | front matter cited "§15.1 rows (**49-54**)", implying a sixth row | **confirmed** — rows 49-53 exist, one per `AC-9`…`AC-13` | corrected to "**(49-53)**" |
| **D3** | §20's register was malformed: `R-62` was glued onto `R-61`'s row by a missing newline, so it did not render as a row | **confirmed** by direct read | rows separated; `R-62`…`R-69` each render as their own row |
| **D4** | the R5 verification report's §12/§13 were **unfilled placeholders** while the plan asserted as `[V]` that the review's findings are recorded there — the R4 `F-1`/`F-3` defect class recurring | **confirmed** | §12/§13 filled with the findings, their re-derivation, the repairs and the reviewer's limitations; the plan's assertion is now true of the finished artifact |
| **D5** | the integrity table placed the **R5** review row *before* the **R4** row it supersedes, so the history row read as newest | **confirmed** | the R5 row is labelled "**(current)**" and the R4 row "**(history — retained beneath the R5 row for continuity…)**" |
| **D6** | §3.5's `R5-A1` wording ("no longer states a coverage state of its own") was generous, since §15.6 still enumerates *which* behaviours lack criteria | **confirmed** | the row now distinguishes the **criterion** fact (still stated deliberately) from the **coverage status** (assigned only in §15.8) |

**Reviewer checks that passed** (its words, re-derived): all eight scenarios present with invariant, expected behaviour, requirement id, criterion or `DEFERRED` marker and verification class; `S5` has no criterion and no identifier; no `PARTIAL`/`DEFERRED` row described as covered or passing; the failed-asset-write mapping is row 38 with no contradiction; citations match the source; no stale range in a current claim; Gate 26/Gate 27 separate and unapproved; Phase 2a blocked; no mechanism described as existing; no digest placeholder.

**Not re-reviewed:** the reviewer did **not** see the corrected files again, so its verdict is recorded as **conditional and pre-repair**; the post-repair state is verified by the coordinator only. **No reviewer finding was applied without re-derivation, and none was dismissed.**

**Post-review verdict line (this pass's final edit).** The R5 plan also gained an explicit, clearly labelled **verdict block** ("documentation review status only; not implementation authorization — SUITABLE FOR OWNER REVIEW, WITH CONDITIONS"), which the task requires the plan itself to carry.

## 4. Source references repaired or confirmed in this pass

**Every value below was re-measured from the checked-out source in this pass** (not carried over), and each is **static source inspection — not runtime verification**.

| Citation | Measured line(s) | Used for | State |
| --- | --- | --- | --- |
| `documents/routes.py` dedupe probe | `:398-405` (comment `:397`) | three write paths; S8's competitor case | exact |
| `documents/routes.py` dedupe/requeue branch | `:408` (error branch), `:412` (commit), `:416` (stale branch), `:420` (commit) | §7.5 path table | exact |
| `documents/routes.py` upload chain | `:427`, `:435`, `:438`, `:442`, `:445`, `:452`, `:456` | `processing` non-observability; crash boundary; residue | exact |
| `documents/routes.py` reprocess | `:672-685`, `:681` (guard), `:696-697` (chunk delete), `:701-705`/`:702` (structure delete), `:708`, `:711`, `:713` | delete-first ordering; Gate 27 transaction-shape change | exact |
| `documents/structure.py` | `:79` (writer), `:103` (savepoint), `:110`, `:113` (the two deletes), `:117` (`flush`) | atomicity wording; §15.4 phrase rule | exact — **refined in R5** (was cited as the block `:109-115`) |
| `tests/conftest.py` | `:50`, `:147-149`, `:154-156` | test-readiness (§2.5 C-9) | exact |
| `pytest.ini` | `:11` | test discovery | exact |

**No stale range remains in any current claim.** Historical entries retain their original (mistaken) ranges **and say so**, with a pointer to the correction.

## 5. Reviewer claims that could not be independently verified

| Claim | Position |
| --- | --- |
| Any **digest**, **file count**, **Git state** or **search-measurement** attribution | **coordinator-measured only.** The R4 reviewers had **no shell**, and the R5 reviewer likewise has file access only. These values are labelled coordinator-measured wherever they appear and are **not** presented as independently verified |
| Any **runtime** behaviour: the A-1 race, the A-2 deletion, crash outcomes, claim release/expiry, cleanup safety | **not verified and not verifiable in this environment** — no PostgreSQL, no live server, no mechanism exists. All such statements rest on static reading of the transaction shape and the cleanup predicate |
| The R4 reviewers' other conclusions | re-derived against the source and the plan before use; where a claim could not be re-derived it is reported as **unverified** rather than accepted or dismissed |

## 6. What remains unresolved (open requirements, not satisfied criteria)

1. **Gate 27 as a whole is undecided** — per-document run claim, run identity, cleanup exclusion and now lifecycle-ending behaviour. **Phase 2a stays blocked.**
2. **Scenario S5 (termination/cancellation after claim acquisition) has no criterion**, deliberately, and **no AC identifier** — assigning one would imply a testable criterion where none can be written without the mechanism.
3. **The claim-state half of S1–S4 and S6 is `DEFERRED`.** Their document/asset-state clauses are specified; the release/expiry/reclaim clauses are open.
4. **Gate 26 (asset identity), gate 4 (frontend Option A/B) and gate 24 (`MIN_USABLE_CHARS`) remain open.**
5. **No test was executed, and no concurrency behaviour was observed** — the coverage counts in §15.8 are counts of *criteria*, not of passing tests.

**A deferred requirement remains an open requirement.** Nothing in R5 converts a `DEFERRED` or `PARTIAL` row into a satisfied criterion, and no section may be cited to suggest otherwise.

## 7. Preservation and boundaries

**No application code, test, migration, dependency, model, dataset, research artifact, configuration or ownership contract was modified.** No service was started, no database contacted, no migration run, no package installed, no implementation agent invoked. **Nothing was staged, committed, pushed, reset, stashed, reverted, cleaned or discarded.** R4 and every earlier revision are byte-unchanged (§1, §11 of the verification report). **No gate was opened or approved — including Gate 26 and Gate 27 — and no phase was started.**
