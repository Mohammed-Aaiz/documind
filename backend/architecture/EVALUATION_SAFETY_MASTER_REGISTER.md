# Evaluation Safety Master Register

**Date of inspection:** 2026-10-09
**Task:** Step 1.3 — documentation and repository-inspection only. No runner was executed, no test was run,
no database was contacted, and no product, test, dataset, benchmark, weight, environment or historical
artifact was modified.
**Repository baseline (recorded before any inspection):** branch `main`, HEAD `6baaa2a`;
`git status --porcelain` = **384** entries (**55** untracked `??`, **295** deleted `D`, **34** modified `M`).
The full snapshot is saved outside the repository at `/tmp/register_baseline_status.txt`; the SHA-256 of
`git diff --name-only` at baseline is `de7230db718b1c1538981e41bb7867ff9230b731026f6295dff20d3ec88165c5`.

**Evidence labels used throughout**

| Label | Meaning |
|---|---|
| **Reported** | A claim made in an existing report; not re-observed by this task |
| **Source-inspected** | Checked in this task by reading source or by `grep`/line search (no execution) |
| **Test-defined** | A test definition was read in this task; the test was **not** run |
| **Unit-tested (reported)** | A unit-test result recorded in a report; not re-run |
| **SQLite-tested (reported)** | Behavioural test on the in-memory SQLite fixtures, reported |
| **PostgreSQL-verified** | Executed against a real PostgreSQL database, recorded in a report |

No finding in this register is marked *independently verified by test execution*: this task ran no tests.

---

## Section 1 — Executive Summary

**Purpose and scope.** The evaluation safety remediation program addresses a single class of risk: research
and evaluation runners in `backend/evaluation/` and `backend/phases/` that could write to, delete from, or
overwrite data in the application database, the application upload root, or recorded evidence. The
program started with a read-only audit (Step 0.5) that found 9 uninstrumented database-touching runners,
an unscoped `DELETE FROM` in several harnesses, and fixed-path report overwrites
(`backend/architecture/STEP0_5_EVALUATION_RUNNER_SAFETY_AUDIT_2026-10-09.md` §10, F-1 to F-14).

**Reported as complete.**

| Step | Reported scope | Report |
|---|---|---|
| 0 | Hardened guard and artifact layer; instrumented `run_dual_path_ablation.py` and `run_phase3d_upload_integration.py` | `backend/architecture/STEP0_EVALUATION_INFRASTRUCTURE_HARDENING_2026-10-09.md` |
| 0.5 | Read-only safety audit (no implementation) | `backend/architecture/STEP0_5_EVALUATION_RUNNER_SAFETY_AUDIT_2026-10-09.md` |
| 0.6 | Isolation guard for the five legacy runners | **No report file.** Described only in `backend/evaluation/README.md` §"Five legacy phase runners — required configuration (Step 0.6)" |
| 0.7 | Scoped cleanup, `run_phase3d_upload_integration.py` (F-3) | `backend/architecture/STEP0_7_PHASE3D_DESTRUCTIVE_CLEANUP_REMEDIATION_2026-10-09.md` |
| 0.8 | Scoped cleanup, `run_phase3d_evaluation.py` | `backend/architecture/STEP0_8_PHASE3D_EVALUATION_CLEANUP_REMEDIATION_2026-10-09.md` |
| 0.9 | Scoped cleanup, `run_phase3e_integration.py` | `backend/architecture/STEP0_9_PHASE3E_INTEGRATION_CLEANUP_REMEDIATION_2026-10-09.md` |
| 1.0 | Scoped cleanup, `run_phase3e_validation.py` | `backend/architecture/STEP1_0_PHASE3E_VALIDATION_CLEANUP_REMEDIATION_2026-10-09.md` |
| 1.1 | Scoped cleanup, `run_phase3f_evaluation.py` | `backend/architecture/STEP1_1_PHASE3F_EVALUATION_CLEANUP_REMEDIATION_2026-10-09.md` |
| 1.2 | Scoped cleanup, `run_phase4b_evaluation.py` | `backend/architecture/STEP1_2_PHASE4B_EVALUATION_CLEANUP_REMEDIATION_2026-10-09.md` |

**What was verified in this task (source level only).**

* The five legacy runners (`run_phase3d_evaluation.py`, `run_phase3e_integration.py`,
  `run_phase3e_validation.py`, `run_phase3f_evaluation.py`, `run_phase4b_evaluation.py`) no longer contain
  a module-level `DATABASE_URL` default, and in each the isolation guard call precedes the environment
  assignment and the engine creation (line numbers in §3).
* No executable raw `DELETE FROM` remains in those five runners; the only `DELETE FROM` strings are inside
  docstrings and comments.
* `run_phase3d_upload_integration.py` still contains **four** raw `text("DELETE …")` statements, scoped by
  exact email (lines 504–519). They are disclosed in its own Step 0.7 report but are not model-bound.
* The protected QA weights and frozen benchmark still match their recorded SHA-256 digests (§4, §5).

**Major risks that remain open** (detail in §2 and §5):

1. **No PostgreSQL execution of the post-remediation cleanup code.** The only PostgreSQL runs of the
   instrumented runners predate the Step 0.7–1.2 cleanup changes (Step 0 §7, runs 4–7).
2. **Fixed-path report overwrites** in `run_structure_confirmation.py`, `run_structure_element_measurement.py`,
   `run_structure_rrf_calibration.py`, `run_table_evidence_measurement.py`, and the legacy `write_report`
   default in `evaluation/runner.py` (F-2).
3. **Application upload root is written by evaluation runs** through `save_upload`; no runner redirects
   `upload_dir` (F-4).
4. **Insufficient run provenance on a dirty tree** — the manifest records a dirty flag and a count, not
   digests of the producing code (F-5).
5. **Credentials on the command line** via `--database-url` in seven runners (F-7).
6. **Concurrent or interrupted runs** of the five deterministic-identity harnesses are not tested and have a
   known collision risk (§5, risks 1 and 2).

**Why this register is not a production-safety certification.** Every "reported" result above comes from
unit tests against SQLite fixtures, from source inspection, or from runs recorded before later changes.
No PostgreSQL run exists for the cleanup code as it now stands. The unit suite passing (860 tests reported at
Step 1.2) does not establish database safety, isolation under concurrency, interrupted-run recovery, or
upload-root isolation. The register records what is known and what is not; it is not an approval for a
controlled evaluation run.

---

## Section 2 — Master Finding Register

Severities are copied from the Step 0.5 audit where it assigns one (`Verified` label as written there).
Where no severity is documented, the field reads **Not established**. "Source-inspected" means checked in
this task; see §4 for the test-level evidence.

| Finding ID | Finding | Affected component | Severity | Original evidence | Current status | Verification level | Residual risk | Dependencies | Next action | Acceptance criteria |
|---|---|---|---|---|---|---|---|---|---|---|
| **F-1** | Five legacy runners defaulted to the application DB via a module-level `DATABASE_URL` default and deleted with unscoped or prefix-scoped SQL | `run_phase3d_evaluation.py`, `run_phase3e_integration.py`, `run_phase3e_validation.py`, `run_phase3f_evaluation.py`, `run_phase4b_evaluation.py` (cleanup and guard) | Critical (audit, *Verified*) | Audit §10 F-1 (L470–478); Step 0.5 §4 R3–R7 | **Reported complete** (guard: Step 0.6 README; deletes: Steps 0.8–1.2). Source-confirmed for the default removal and guard ordering | Source-inspected; SQLite-tested (reported); **not PostgreSQL-verified** | Scoped cleanup has never run against PostgreSQL; guard ordering verified in source only; concurrency and interruption behaviour untested | F-6, F-7, PostgreSQL verification (§8 Later) | Run one legacy runner's cleanup once against a disposable isolated PostgreSQL DB (§8 P0.1) | Foreign-owned rows survive a full run; harness rows removed; exit code and report format unchanged; evidence recorded |
| **F-2** | Four research runners and the legacy `write_report` default overwrite fixed historical report paths, and four of them have no isolation guard | `run_structure_confirmation.py`, `run_structure_element_measurement.py`, `run_structure_rrf_calibration.py`, `run_table_evidence_measurement.py`; `evaluation/runner.py` (`write_report(out_dir=None)`); **extended observation:** `run_phase3d_evaluation.py`, `run_phase3f_evaluation.py`, `run_phase4b_evaluation.py` write fixed report names | High (audit, *Verified*) | Audit §6 table; §10 F-2 (L480–488); `runner.py` L400–411 | **Open** | Source-inspected (guard count 0 in the four structure/table runners; fixed-write counts 4/4/4/2; `runner.py` L400–411) | A re-run silently replaces recorded evidence; the four structure/table runners can still target the application DB via `storage.database` (no guard) | Output-directory contract from Step 0 (`RunOutput`) | Route the four runners through `RunOutput` and withdraw the `out_dir=None` branch (§8 P0.2) | Second run into the same directory refused; recorded reports byte-identical; no runner imports `storage.database` without the guard |
| **F-3** | `run_phase3d_upload_integration.py` contained a database-wide `DELETE FROM document_chunks` | `run_phase3d_upload_integration.py` cleanup | High (audit, *Verified*) | Audit §10 F-3 (cites L553); Step 0.7 report | **Partially remediated.** The unscoped chunk delete is gone (source-confirmed); four exact-email raw `text("DELETE …")` statements remain at L504–519 and are disclosed in Step 0.7 §9 and README | Source-inspected; model-bound helper SQLite-tested (17 tests reported, Step 0.7 §4) | Residual raw SQL is not model-bound; **no PostgreSQL run after the Step 0.7 change** (Step 0 run 7 predates it) | P1.1 (model-bound conversion); PostgreSQL verification | Convert L504–519 to `cleanup_harness_rows` and run the upload runner once against an isolated PG DB (§8 P0.1, P1.1) | Raw SQL count in the file = 0; post-change isolated run exits 0 with foreign rows surviving |
| **F-4** | Evaluation runs write documents into the application upload root and never remove them | `save_upload` call sites in `run_dual_path_ablation.py`, `run_phase3d_evaluation.py`, `run_phase3f_evaluation.py`, `run_phase4b_evaluation.py`, `run_structure_element_measurement.py`; `backend/uploads/` | High (audit, *Verified mechanism*) | Audit §10 F-4 (cites L198, L155, L259, L234, L176 — now L181, L142/166, L246/270, L221/245, count 1); Step 0 §9.8 | **Open** | Source-inspected (no runner redirects `upload_dir`; `config.py` default `./uploads`; 1112 entries in `backend/uploads/`) | Every default run pollutes application storage; orphan accumulation; `scripts/cleanup_orphan_uploads.py` exists but was not run | P1.2 (redirect) | Redirect `upload_dir` to a runner-owned temp dir in each of the five runners and add a fixture (§8 P1.2) | Post-run count of `backend/uploads/` entries unchanged; uploads land only under the runner's temp root |
| **F-5** | Run provenance cannot reproduce a result on a dirty tree; the manifest records a dirty flag and count, not digests | `backend/evaluation/artifacts.py` (`collect_run_manifest`) and `manifest` schema | High (audit, *Verified*) | Audit §6, §10 F-5 (L505–511); Step 0 §7.2 (EM 0.5238 recorded vs 0.4524 reproduced) | **Open** | Source-inspected (`artifacts.py` L205–213 records `workingTree` and `changedPathCount` only) | Recorded numbers cannot be attributed to code; discrepancy in Step 0 §7.2 unresolved | P1.3 | Add source digests of the modules on the run path to the manifest (§8 P1.3) | Manifest contains a digest per listed module; a changed module changes the digest; the Step 0 discrepancy is attributable or explicitly recorded |
| **F-6** | Two guard policies: `evaluation/isolation.py` compares (host, port, database); `run_table_evidence_measurement.py` asserts loopback only; a same-named remote DB is permitted | `evaluation/isolation.py`; `run_table_evidence_measurement.py` | Medium (audit, *Verified*) | Audit §5, §10 F-6 (L513–518) | **Open** | Source-inspected (`assert_safe_evaluation_target` count 0 in `run_table_evidence_measurement.py`; loopback check cited from audit, not re-read) | Operator error against a staging copy; no sensitive-target refusal | P1.4 | Route `run_table_evidence_measurement.py` through the central guard (§8 P1.4) | Runner refuses the application DB by identity; loopback-only check is no longer the sole protection |
| **F-7** | Database credentials can appear in process listings and shell history via `--database-url` | `--database-url` in `run_dual_path_ablation.py`, `run_phase3d_upload_integration.py`, `run_phase3d_evaluation.py`, `run_phase3e_integration.py`, `run_phase3e_validation.py`, `run_phase3f_evaluation.py`, `run_phase4b_evaluation.py` | Medium (audit, *Verified*) | Audit §5, §10 F-7 (L519–521); Step 0 §9.6 | **Open** (env-var form documented as the argv-safe alternative, README §"Isolated databases") | Source-inspected (`--database-url` present in all seven) | Argv form still accepted; no warning | P2.2 | Warn on argv DSN or accept only env/file input (§8 P2.2) | Argv-supplied credential is refused or warned, and the warning is tested |
| **F-8** | No regression coverage for uninstrumented runners | `run_structure_confirmation.py`, `run_structure_element_measurement.py`, `run_structure_rrf_calibration.py`, `run_table_evidence_measurement.py`, `run_phase4c_diagnostics.py` | Medium (audit, *Verified*) | Audit §10 F-8 (L523–527) | **Partially remediated.** Legacy five now covered by `test_legacy_runner_isolation.py` (70 cases); upload runner exercised by one behavioural test file (`test_phase3d_cleanup_scope.py`; a second file names it in a docstring only); the four structure/table runners and `run_phase4c_diagnostics.py` still have **0** test references (grep) | Source-inspected (grep); test-defined for coverage that exists | The four runners can regress silently | P2.1 | Add the runners to a spec-driven isolation suite (§8 P2.1) | Each of the five runners appears in a spec with guard, report-path and no-raw-SQL assertions |
| **F-9** | Fixed paths resolve against the process CWD | `run_phase4c_diagnostics.py` (reads L278, writes L584); `tests/e2e/browser/test_phase6_reliability.py` (L99); **extended observation:** the report writes of `run_phase3d_evaluation.py` (L778–779), `run_phase3f_evaluation.py` (L1033–1034), `run_phase4b_evaluation.py` (L965–966) | Medium (audit, *Verified*) | Audit §10 F-9 (L528–533) | **Open** | Source-inspected (all lines above confirmed in this task) | Wrong input or output location when launched from another directory; e2e writes relative to the storage root | P2.3 | Anchor paths to `Path(__file__)` (§8 P2.3) | Each path is absolute or `__file__`-anchored; a test launches from a different CWD |
| **F-10** | The frozen benchmark's 42 unanswerable examples have no runner in the hardened `evaluation/` suite | `phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` (read-only); Phase 4F harness under `backend/phases/` | Medium (audit, *Verified*) | Audit §9B, §10 F-10 | **Open** (carried; not re-checked this task beyond the digest in §5) | Report-only; benchmark digest source-inspected | Abstention is untested against the frozen human-audited set | Phase 1 planning (`PHASE1_GROUNDED_ANSWERING_PLAN_2026-10-09.md`) | Planned; not started (§8 Later) | Isolated-DB runner reports an abstention denominator with manifest and benchmark digest |
| **F-11** | Archived phase runners fetch models from the network and write to fixed directories | `phases/phase4f/balance_gate.py` (L571 `AutoTokenizer.from_pretrained("distilbert-base-cased")`); phase4d/4e/4f modules | Medium (audit, *Verified*) | Audit §10 F-11 (L538–543) | **Open** (fetch line confirmed by grep this task; directory behaviour not re-read) | Source-inspected (one line) | Non-reproducible results; network dependency | None | Document, pin, or vendor the model (§8 P2.4) | Fetch is pinned or explicitly declared; output directory is caller-supplied |
| **F-12** | Empty baseline packages suggest a frozen-baseline architecture that does not exist | `evaluation/baselines/{vector_only,structure_only,dual_path}/` | Low (audit, *Verified*) | Audit §10 F-12 (L544–549) | **Open** — confirmed present: each contains only `__init__.py` (directory listing this task) | Source-inspected | Misleading to readers only | None | Remove or document as placeholders (§8 P2.5) | Packages either removed or each carries a README stating they are empty placeholders |
| **F-13** | `chat/qa_model.py` no longer exposes module-level `torch`/`transformers` | `backend/chat/qa_model.py` | Low (audit, *Verified*) | Audit §10 F-13 (L550–555) | **Open — observed unchanged.** No module-scope `import torch` / `from transformers` found by grep this task | Source-inspected | Future module-scope use fails with `NameError` | None | Note in project context; no change required | Documented; no module-scope reference added without a test |
| **F-14** | A runner documents destructive behaviour without naming the scope at runtime | `run_phase3d_upload_integration.py` (guard `operation` text and module docstring) | Low (audit, *Verified*) | Audit §10 F-14 (L556–560) | **Partially remediated.** Docstring updated in Step 0.7 (L30–46 now describe the scoped helper); runtime `operation` string not re-read in this task | Source-inspected (docstring); runtime message **unknown** | Operator sees an accurate docstring but the runtime text was not re-checked | None | Re-read the runtime message and align it (§8 P2.6) | Runtime message names the scope |
| **N-1** *(new)* | The upload runner's post-Step-0.7 cleanup has no PostgreSQL run on record | `run_phase3d_upload_integration.py` cleanup (L117, L603, L504–519) | **Not established** | Step 0 §7 run 7 (40/0, before Step 0.7); Step 0.7 §4 (SQLite only) | **Open** | Report-only (chronology) | The most recent cleanup change to the one runner that was ever run against PG has not been run against PG | P0.1 | §8 P0.1 | Isolated-PG run after the change: exit 0, foreign rows survive, chunk ids preserved |
| **N-2** *(new)* | `run_phase3d_upload_integration.py` is not in `test_legacy_runner_isolation.py`, which covers only the five legacy runners | `tests/unit/evaluation/test_legacy_runner_isolation.py` | **Not established** | Static test definitions (14 defs × 5 runners = 70); grep for upload runner name returns 0 | **Open** (coverage gap, not a defect) | Test-defined | Upload runner's guard is covered only by its own tests | P2.1 | Add the upload runner to the spec (§8 P2.1) | Upload runner appears in the spec with the same guard assertions |
| **N-3** *(new)* | Interrupted-run "recoverability" is asserted in reports but no test seeds an interrupted run | `STEP1_1_…` §2 and §6.3; `STEP1_2_…` §2 and §6.3; `evaluation/README.md` (Phase 3F and 4B sections) | **Not established** | Test files read: none seeds an interrupted state; `test_repeated_cleanup_*` tests only repeat cleanup | **Open** | Report-only (design inference) | The claim is design inference, not verified behaviour | P2.7 | Add an interrupted-run test (§8 P2.7) | A test seeds leftover rows from a prior run and shows the exact-email sweep removes exactly them |

---

## Section 3 — Runner Remediation Inventory

**Scope note.** This inventory covers the runners named in the Step 0.5 audit (R1–R24) and the Step 0–1.2
reports. It does **not** prove complete coverage of all evaluation entry points. A complete current-source
inventory was not produced in this task; the grep counts below cover the evaluation runners and selected
scripts only.

### 3A — The five legacy runners covered by `test_legacy_runner_isolation.py`

Guard, engine and cleanup line numbers are from source grep in this task. Test counts are **reported** from
the cited report, and the static `def test_` counts are **test-defined** (not executed).

| Runner | Remediation step | Original destructive pattern (reported) | Current cleanup implementation | Guard / env / engine lines (source) | Associated test file | Reported test evidence | Independent source-inspection result | Remaining limitations |
|---|---|---|---|---|---|---|---|---|
| `evaluation/experiments/run_phase3d_evaluation.py` | Step 0.8 (cleanup); Step 0.6 (guard) | 10 raw `DELETE FROM` (5 unpredicated ×2 + `phase3d_%` prefix), per Step 0.8 README | `cleanup_harness_rows` L547; calls L681, L784; `owned_user_ids` | guard **624** < env **637** < engine **654** | `tests/unit/evaluation/test_phase3d_evaluation_cleanup_scope.py` (16 defs); spec entry in `test_legacy_runner_isolation.py` | Step 0.8 §4: 16 passed, exit 0; `tests/unit/evaluation` 287; `tests/unit` 790 | No executable raw DELETE; `save_upload` at L142/L166 (F-4); report `phase3d_evaluation_report.json` written relative to CWD (L778–779) (F-9); no manifest | Never run against PG; F-4, F-7, F-9 |
| `evaluation/experiments/run_phase3e_integration.py` | Step 0.9 | 4 raw `DELETE FROM` (one unpredicated, `document_chunks`) per Step 0.9 §1 | `cleanup_harness_rows` L81; calls L441, L514 | guard **158** < env **171** < engine **193** | `test_phase3e_integration_cleanup_scope.py` (16 defs) | Step 0.9 §4: 16 passed, exit 0; eval 303; unit 806 | No executable raw DELETE; `os.unlink` only on its own `NamedTemporaryFile` inputs (not upload storage); no `save_upload`; console output only | Never run against PG; `--database-url` argv (F-7) |
| `evaluation/experiments/run_phase3e_validation.py` | Step 1.0 | 4 raw `DELETE FROM` (one unpredicated) per Step 1.0 | `cleanup_harness_rows` L81; calls L723, L824; step-5 document-scoped delete is inline in `main()` (Step 1.0 §6) | guard **159** < env **172** < engine **191** | `test_phase3e_validation_cleanup_scope.py` (17 defs) | Step 1.0 §4: first run **86 passed, 1 failed** (exit 1, `test_read_only_diagnostics_are_left_alone`); after the collector fix, eval **320** passed exit 0; unit **823** passed exit 0 | No executable raw DELETE; read-only `text()` diagnostics retained per Step 1.0 (not re-read this task); step-5 delete has source-only coverage | Step-5 inline delete has no behavioural test; never run against PG |
| `evaluation/experiments/run_phase3f_evaluation.py` | Step 1.1 | 10 raw `DELETE FROM` (6 + 4), per Step 1.1 §1 | `cleanup_harness_rows` L717; calls L853, L1038 | guard **800** < env **813** < engine **827** | `test_phase3f_evaluation_cleanup_scope.py` (18 defs) | Step 1.1 §4: 18 passed exit 0; eval **338**; unit **841** | No executable raw DELETE; `save_upload` L246/L270 (F-4); report `phase3f_evaluation_report.json` relative (L1033–1034) (F-9) | Never run against PG; F-4, F-7, F-9; no manifest |
| `evaluation/experiments/run_phase4b_evaluation.py` | Step 1.2 | 10 raw `DELETE FROM` (6 + 4), per Step 1.2 §1 | `cleanup_harness_rows` L697; calls L833, L970 | guard **780** < env **793** < engine **807** | `test_phase4b_evaluation_cleanup_scope.py` (19 defs) | Step 1.2 §4: 19 passed exit 0; isolation 70 passed exit 0; eval **357**; unit **860** | No executable raw DELETE; `save_upload` L221/L245 (F-4); report `phase4b_evaluation_report.json` relative (L965–966) (F-9); no manifest | Never run against PG; F-4, F-7, F-9 |

**Consistency check.** The static `def test_` counts for the five per-runner files (16, 16, 17, 18, 19) match the
counts each report records as passed. The legacy spec has 14 test functions parametrised over five runners,
giving the 70 cases the reports record (static arithmetic; not executed).

### 3B — Instrumented, but outside the five legacy runners

| Runner | Remediation step | Original pattern (reported) | Current cleanup implementation | Guard / env / engine lines (source) | Associated test file | Reported test evidence | Independent source-inspection result | Remaining limitations |
|---|---|---|---|---|---|---|---|---|
| `evaluation/experiments/run_phase3d_upload_integration.py` (R2) | Step 0 (guard, `--out`, manifest); Step 0.7 (cleanup) | Unscoped `DELETE FROM document_chunks` (audit cites L553) | `cleanup_harness_rows(db, *, user_id)` L117, called L603 (model-bound); **residual** raw `text("DELETE …")` block L504–519, exact-email subqueries | guard **192** < env **204** < engine **240** | `tests/unit/evaluation/test_phase3d_cleanup_scope.py` (17 defs); `test_phase3d_evaluation_cleanup_scope.py` references the module in a docstring only | Step 0.7 §4: 17 passed, exit 0; eval 271; unit 774. Step 0 run 7 (**40 passed / 0 failed**, isolated PG) — **predates** Step 0.7 | Guard and env ordering confirmed; no executable unscoped delete; **four raw SQL statements remain**; module-level docstring line 43 mentions the former hard-coded DSN (not executable) | **Not in the legacy spec**; no PG run after Step 0.7 (N-1); success-path-only cleanup; `save_upload` is not called, but the HTTP route stores files in `./uploads` (Step 0 §9.8, F-4) |
| `evaluation/experiments/run_dual_path_ablation.py` (R1) | Step 0 (guard, `--out`, manifest, determinism) | None destructive (raw DELETE count 0) | No delete path | guard **614** < env **623** < `storage.database` import **656** | Step 0 execution evidence (no unit file identified for R1 in this task) | Step 0 §7 runs 4–6 on a freshly provisioned isolated PG DB: 10 artifacts, `completed`; second run identical metrics; same-directory refusal exit 2 — **reported** | Guard ordering confirmed; `save_upload` import L181 (F-4); `--database-url` argv (F-7) | Upload storage written; R1 engine comes from the app module `storage.database` after the env is set (reported Step 0 design) |

### 3C — Uninstrumented or non-cleanup runners (not covered by the five-runner spec)

| Runner | Audit id | Remediation step | Original pattern | Current state (source, this task) | Guard | Associated tests | Reported evidence | Limitations |
|---|---|---|---|---|---|---|---|---|
| `evaluation/experiments/run_structure_confirmation.py` | R8 | none | Imports `storage.database` (app DB); fixed report writes | Fixed writes: count 4 (audit L928–932) | **0 guard calls** | **0 references** in `tests/` | none | F-2, F-8; can target app DB |
| `evaluation/experiments/run_structure_element_measurement.py` | R9 | none | Same shape; `save_upload` count 1 | Fixed writes: count 4 (audit L1841–1854) | **0** | **0** | none | F-2, F-4, F-8 |
| `evaluation/experiments/run_structure_rrf_calibration.py` | R10 | none | Same shape | Fixed writes: count 4 (audit L1144–1148) | **0** | **0** | none | F-2, F-8 |
| `evaluation/experiments/run_table_evidence_measurement.py` | R11 | none | Engine from app settings; loopback-only check (audit L262–271) | Fixed writes: count 2 (audit L188–191, L1205–1213); `_write_deterministic` mode `"w"` | **0 central-guard calls** | **0** | none | F-2, F-6, F-8; loopback check not re-read this task |
| `evaluation/runner.py` (`write_report`) | F-2 | none | Legacy default `out_dir=None` → `REPORTS_DIR` | L400–411 present (source) | n/a | Not identified in this task | none | Any caller omitting `out_dir` overwrites |
| `evaluation/experiments/run_phase4c_diagnostics.py` | R12 | none | No DB; CWD-relative read (L278) and write (L584) | Confirmed by grep | n/a | **0** | none | F-9 |
| `evaluation/experiments/synthesize_structure_discriminating.py`, `evaluation/denominator_sensitivity.py`, `evaluation/structure_eval.py`, `evaluation/datasets/structure_discriminating_v1.py` | R13–R16 | none | Report-only; fixed/default outputs | Fixed writes counted 2, 2, 2, 0 | n/a | Not identified in this task | Report-only per audit | Overwrite of derived artifacts; by design per `evaluation/README.md` |
| `scripts/cleanup_smoke.py` | R17 | none | Deletes application rows and files by design (audit L123–136) | `unlink`/`rmtree`/delete match count 3 | n/a (operator script) | Not identified in this task | Audit only | Destructive against app DB by design; not an evaluation runner |
| `scripts/cleanup_orphan_uploads.py` | R18 | none | Unlinks upload files | match count 1 | n/a | Not identified | Audit only | Requires explicit operator authorisation to run (audit §11 F-4) |
| `scripts/setup_db.py`, `scripts/create_test_user.py`, `scripts/db_check.py`, `scripts/start_server.py` | R19–R22 | none | Schema / user / read-only check / server start | **Not re-inspected** in this task | — | — | Audit only | Listed for completeness |
| `tests/e2e/browser/*` | R23 | none | Live HTTP; self-skipping without a server | `tests/e2e/browser/test_phase6_reliability.py` L99 `os.path.join('uploads', 'phase6_test.pdf')` confirmed | — | 6 skips recorded in Step 0 §8 | Step 0 reported | F-9 |
| `backend/phases/**` (R24) | R24 | none | Archived research; no PG; in-memory SQLite at `phases/phase4d/oracle_eval.py:347` (audit) | `balance_gate.py` L571 fetch confirmed | — | Not run | Audit only | F-11 |

**Coverage statement.** The five legacy runners and the upload runner are the only evaluation runners with a
verified guard-before-engine ordering in source. The four structure/table runners and `run_phase4c_diagnostics.py`
have no guard call and no test reference. No statement in this register claims that every evaluation entry
point is covered.

---

## Section 4 — Verification Evidence Matrix

| Category | Performed in this task? | Supporting report or test | Exact reported result | Independently inspected? | What remains unverified |
|---|---|---|---|---|---|
| **Python compilation** | **No** (task forbids test/runner execution; compilation not re-run) | Step 1.2 §4: `py_compile` runner; `compileall` on runner and two test files | Step 1.2: both **exit 0** | No | Compilation of the final tree after Step 1.2's last edit: the Step 1.2 report records that only Markdown changed afterwards; this was not re-checked |
| **AST / source inspection** | **Yes** — source and `grep` line inspection; **no AST script was run** | Static test-definition reads; per-runner `grep` of guard/env/engine/DELETE/fixed-write/`save_upload` patterns | Guard ordering confirmed for seven runners (§3); raw `DELETE FROM` confined to docstrings in five legacy runners | Yes (this task) | The AST pins in the test files were not executed |
| **Focused cleanup tests** | **No** (not run) | `test_phase3d_cleanup_scope.py` (17), `test_phase3d_evaluation_cleanup_scope.py` (16), `test_phase3e_integration_cleanup_scope.py` (16), `test_phase3e_validation_cleanup_scope.py` (17), `test_phase3f_evaluation_cleanup_scope.py` (18), `test_phase4b_evaluation_cleanup_scope.py` (19) | Reported as passed with exit 0 in each step report (§3) | Static definition counts agree with reported counts | Collected results and exit codes not re-observed |
| **Legacy isolation tests** | **No** | `tests/unit/evaluation/test_legacy_runner_isolation.py` | Step 1.2 §4: **70 passed**, exit 0 (21.82 s) | Static: 14 defs × 5 runners = 70 | Not re-run; this spec does not cover the upload runner or the four structure/table runners |
| **Evaluation unit suite** | **No** | `python -m pytest -q tests/unit/evaluation` | Step 1.2 §4: **357 passed**, exit 0 (47.11 s) | No | Not re-run. Growth path reported: 184 (Step 0) → 254 (before 0.7) → 271 → 287 → 303 → 320 → 338 → 357. The 70-test gap between Step 0 (184) and Step 0.7's "before" (254) is not accounted for by any report (see §6, D-5) |
| **Complete unit suite** | **No** | `python -m pytest -q tests/unit` | Step 1.2 §4: **860 passed**, exit 0 (76.27 s) | No | Not re-run. Path reported: 687 (Step 0) → 757 → 774 → 790 → 806 → 823 → 841 → 860 |
| **SQLite behavioural tests** | **No** | The cleanup-scope test files above, using the in-memory SQLite fixtures with `PRAGMA foreign_keys=ON` | Reported as passing in each step | No | They prove row-selection semantics only, not PostgreSQL plans |
| **PostgreSQL integration tests** | **No** | Step 0 §7 row 3: `python -m pytest -q tests/integration tests/e2e` with PostgreSQL up | Reported: **275 passed, 6 skipped**, exit 0 | No | No log in the repository; the run predates Steps 0.7–1.2 and was not repeated after them |
| **Evaluation harness execution (PostgreSQL)** | **No** | Step 0 §7 runs 4–7 (`run_dual_path_ablation.py` ×3; `run_phase3d_upload_integration.py` ×1) on freshly provisioned isolated DBs, dropped afterwards | Reported: run 4 exit 0, 10 artifacts, `completed`; run 5 identical metrics; run 6 exit 2 refusal with 10 artifacts byte-identical; run 7 **40 passed / 0 failed** | No | Run 7 predates the Step 0.7 change. **No legacy runner (R3–R7) has ever been executed against PostgreSQL** in any report. Step 0 §7 explicitly did not run them |
| **Integration and end-to-end tests** | **No** | Step 0 §7 row 3 and §8 | 275 passed, 6 skipped (the six are browser e2e tests with no live server) | No | The six browser tests have never run in the recorded evidence; the integration suite writes into `./uploads` (Step 0 §9.8) |
| **Upload-storage isolation** | **Partly** — source inspection only | `config.py` `upload_dir = "./uploads"`; `storage/file_store.py`; grep for `upload_dir`/`UPLOAD_DIR` in `evaluation/experiments/*.py` (no matches) | No runner redirects storage | Yes (source) | No isolation mechanism is verified for any runner. Step 0 §9.8 reports that the Step 0 runners were run with `UPLOAD_DIR` redirected **manually** to a temp directory; that is not a mechanism in the repository |
| **Concurrent-run behaviour** | **No** | No test in `tests/unit/evaluation/` seeds two concurrent runs (static read) | Not reported as tested | Yes (absence) | Deterministic harness identities collide under concurrency (Step 1.1 §6.2, Step 1.2 §6.2 caveat). No concurrency safety is claimed anywhere |
| **Interrupted-run recovery** | **No** | Step 1.1 §2 and §6.3; Step 1.2 §2 and §6.3 assert recoverability through the exact-email sweep | Not tested | Yes (absence of a seeding test) | The recoverability claim is design inference (N-3) |
| **Artifact provenance and report integrity** | **Partly** — source inspection | `artifacts.py` L205–213; `RunOutput` `"x"` mode; Step 0 §5 and §7 (byte-identical refusal, reported) | Reported: refusal on the same directory with byte-identical artifacts (run 6) | Yes (source for manifest fields) | Manifest records dirty/count only (F-5). Four runners overwrite fixed reports (F-2). Recorded EM 0.5238 is not reproduced (Step 0 §7.2) |

**Inherited-claim labelling.** Every "reported" result above is labelled **Reported; not independently verified**
for the purposes of this register.

---

## Section 5 — Known Residual Risks

Each risk is labelled with the latest evidence found. None is assumed fixed or open without that evidence.

### 5.1 Deterministic-harness identity collisions during concurrent runs — **Open (acknowledged; not mitigated in code)**

* **Evidence.** `harness_user_email` builds deterministic addresses in `run_phase3f_evaluation.py` and
  `run_phase4b_evaluation.py` (`phase3f_<label>@test.local`, `phase4b_<label>@test.local`). The pre-run sweep
  deletes every row owned by those exact users. Two concurrent instances therefore delete each other's live
  rows. Step 1.1 §6.2 and Step 1.2 §6.2 record this caveat and claim no concurrency safety.
* **Latest status.** Source-confirmed (the sweep at `run_phase3f_evaluation.py` L853 and `run_phase4b_evaluation.py` L833
  call the same helper with the deterministic list). No test exercises concurrency.
* **Also relevant.** The Phase 3D and 3E harnesses use random suffixes (`phase3d_upload_<8 hex>`, `phase3e_<8 hex>`), so
  they avoid collision but cannot recover leftovers; this trade-off is recorded in Steps 0.8 and 0.9.

### 5.2 Cleanup after interruption or failure — **Open**

* **Evidence.** `run_phase3d_upload_integration.py` runs cleanup on the success path only (Step 0.7 §9.1). The five legacy
  runners have no `try/finally` cleanup in `main()` (Steps 1.1 §2 and 1.2 §2 record this from source reading).
* **Recovery claim.** Steps 1.1 and 1.2 state that a later run's exact-email sweep removes an interrupted run's rows.
  No test seeds an interrupted state (N-3). The statement is a design inference.

### 5.3 Evaluation files leaking into the application's upload root — **Open**

* **Evidence.** `save_upload` in `run_dual_path_ablation.py` (import L181), `run_phase3d_evaluation.py` (L142/L166),
  `run_phase3f_evaluation.py` (L246/L270), `run_phase4b_evaluation.py` (L221/L245), and
  `run_structure_element_measurement.py` (count 1) write to `settings.upload_dir`, default `./uploads`.
* **Current state.** `backend/uploads/` contains **1112** entries, the same count recorded in Step 1.1 §5 and
  Step 1.2 §5. Of those, 74 carry a 2026-10-09 modification date. This task cannot attribute those files to a
  specific run.
* **Mitigation absent.** No runner redirects `upload_dir`; the only redirect is a fixture in `tests/fixtures/e2e_config.py`.

### 5.4 The exact-email raw SQL block in `run_phase3d_upload_integration.py` — **Partially remediated (open residual)**

* **Evidence.** Lines 504–519 contain four `text("DELETE …")` statements: `reliability_logs`, `document_chunks`, `documents`
  and `users`, each scoped by `email = :e` via subquery. They run for the two isolation-check users (`meta_email`,
  `other_email`) after the cleanup block.
* **Disclosure.** Step 0.7 §9 and `evaluation/README.md` (Step 0.7 section) disclose the block and call it
  "email-scoped". The Step 0.7 report says the statements are "model-bound rather than raw SQL" for the
  helper; the four residual statements are not model-bound.
* **Risk.** These statements are **not** unscoped, so they do not carry the database-wide risk of the original
  `DELETE FROM document_chunks`. They are unverified on PostgreSQL after the Step 0.7 change (N-1).
* **Discrepancy.** `DOCUMIND_PROJECT_CONTEXT.md` §64 (Step 0.7 pointer) says the step "closes Step 0.5 finding F-3".
  That is accurate for the unscoped chunk delete and overstated for the file as a whole (see §6, D-19).

### 5.5 Other open Step 0.5 findings — **Mixed; see §2**

Open: F-2, F-4, F-5, F-6, F-7, F-9, F-10, F-11, F-12, F-13. Partially remediated: F-3, F-8, F-14. Reported
complete with source confirmation and no PostgreSQL run: F-1. None is established as closed by a PostgreSQL run.

### 5.6 Application database protection and isolation-guard ordering — **Source-confirmed for seven runners; PostgreSQL unverified**

| Runner | Guard line | Env assignment line | Engine line | Ordering holds in source |
|---|---|---|---|---|
| `run_dual_path_ablation.py` | 614 | 623 | `storage.database` import 656 | Yes |
| `run_phase3d_upload_integration.py` | 192 | 204 | 240 | Yes |
| `run_phase3d_evaluation.py` | 624 | 637 | 654 | Yes |
| `run_phase3e_integration.py` | 158 | 171 | 193 | Yes |
| `run_phase3e_validation.py` | 159 | 172 | 191 | Yes |
| `run_phase3f_evaluation.py` | 800 | 813 | 827 | Yes |
| `run_phase4b_evaluation.py` | 780 | 793 | 807 | Yes |

* **Not covered:** the four structure/table runners (no guard) and `run_table_evidence_measurement.py`'s loopback-only check (F-2, F-6).
* **Guard behaviour** (refusal of the application DSN, credential-free messages) is reported as tested in
  Step 0 §5/§7 and Step 0.6 (README) and in `tests/unit/evaluation/test_legacy_runner_isolation.py` and
  `tests/unit/evaluation/test_evaluation_isolation.py` (26 static defs, reported; not re-run).

### 5.7 Historical report overwrite and artifact provenance — **Open**

* **Overwrite.** `run_structure_confirmation.py`, `run_structure_element_measurement.py`,
  `run_structure_rrf_calibration.py`, `run_table_evidence_measurement.py` and `evaluation/runner.py`
  `write_report(out_dir=None)` overwrite fixed paths (F-2). The five legacy runners also write fixed,
  CWD-relative report names (`phase3d_evaluation_report.json`, `phase3f_evaluation_report.json`,
  `phase4b_evaluation_report.json`) — an **extension** of F-2 and F-9 identified in this task.
* **Provenance.** `artifacts.py` L205–213 records a working-tree flag and a changed-path count (F-5).
* **Unresolved measurement discrepancy.** Step 0 §7.2 records EM **0.5238** in the 2026-10-04 report and **0.4524**
  on a fresh run with identical retrieval metrics. The Step 0 report attributes the difference to uncommitted
  changes in `chat/rag.py` dated 2026-10-06 03:04. That attribution is **probable, not established** (F-5, §6 D-7).

### 5.8 Database credentials in command-line arguments or process listings — **Open (still relevant)**

* **Evidence.** `--database-url` appears in seven runners (§2 F-7). The guard's messages are credential-free, but argv
  is visible to other local users and in shell history.
* **Mitigation present.** `DOCUMIND_INTEGRATION_DATABASE_URL` is the argv-safe form (Step 0 §9.6; README "Isolated databases").
  Nothing forbids the argv form.
* **Scope.** The structure/table runners take no DSN argument; they read the application DSN through `storage.database`.

### 5.9 Other risks named in existing reports

| Risk | Source | Latest evidence | Status |
|---|---|---|---|
| Upload runner's cleanup is success-path only | Step 0.7 §9.1 | Source read (cleanup at L603 after assertions) | Open |
| Phase 3F/4B deterministic identities allow a run to recover its own leftovers | Steps 1.1 §2, 1.2 §2 | Design inference (N-3) | Unknown |
| `run_phase4c_diagnostics.py` reads and writes CWD-relative files | Audit F-9 | Confirmed by grep | Open |
| Frozen benchmark has no runner in the hardened suite | Audit F-10 | Not re-checked beyond digest | Open |
| Archived phases fetch a model from the network | Audit F-11 | Confirmed by grep (L571) | Open |
| Latency and peak-memory metrics not captured | Step 0 §9.5 | Reported | Open (by design, per Phase 1 plan §7) |
| Corpus-level abstention not attached to phase3d documents | Step 0 §9.7 (F-08) | Reported | Open |
| `dataset.version` is `"unavailable"` for labelled corpora | Step 0 §9.3 | Reported | Open |

---

## Section 6 — Contradictions and Evidence Gaps

Nothing below has been silently reconciled. Each discrepancy is recorded with its evidence and its resolution status.

| # | Conflicting claims | Available evidence | Resolved by inspection? | Additional evidence required |
|---|---|---|---|---|
| **D-1** | `evaluation/README.md` Step 0.8 section (around L418–424) says the Step 0.6 pin was replaced "for the runners remediated in Steps 0.8/0.9" and "the remaining three keep their existing counts". Later steps (1.0–1.2) replaced the count pin for all five | README text; `test_legacy_runner_isolation.py` now asserts the no-raw-SQL contract for all five (`scoped_cleanup=True`); Step 1.2 §4 | **Yes** — the sentence is stale | Not rewritten (historical record). A future README edit should annotate it |
| **D-2** | README "Instrumented runners" table (L270–279) lists the five legacy runners as instrumented. Audit §3–§5 and Step 0 §2.4 use "instrumented" for R1/R2 only | README table; audit §3 | **Partly** — the two uses of "instrumented" differ; the README's is broader | Agree a definition and label the table accordingly |
| **D-3** | Step 0.7 says the upload runner's statements are "model-bound rather than raw SQL" (for the new helper); the same file retains four raw `text("DELETE …")` statements (L504–519). Step 0.7 §9 discloses them | Step 0.7 report; source L504–519 | **Yes** — disclosed; the claim is scoped to the helper | Model-bound conversion (P1.1) |
| **D-4** | Step 0 run 7 (40/0, isolated PG) is the only PG run of the upload runner. Step 0.7 later changed its cleanup | Chronology: Step 0 precedes Step 0.7 (reports' dates and sections) | **Yes** — the PG run cannot cover the later code | PG run of the current file |
| **D-5** | Step 0 reports `tests/unit/evaluation` = **184** and `tests/unit` = **687**; Step 0.7 reports **254** and **757** "before this change". The **70** difference matches the 70 legacy-isolation cases, but no report records the Step 0.6 run | Step 0 §7; Step 0.7 §4; `test_legacy_runner_isolation.py` static arithmetic | **Partly** — the gap is consistent with Step 0.6, which has no report | Step 0.6 test-run record or a Step 0.6 report |
| **D-6** | Step 0.6 is described in `evaluation/README.md` with a **process-level closed-port run** (exit 1, `ConnectionRefusedError`, no artifacts) for all five runners | README §"Five legacy phase runners" (Step 0.6 section) only | **No** — no log or report on record | Process-run transcript or report |
| **D-7** | Step 0 §7.2: fresh run EM **0.4524** vs 2026-10-04 recorded **0.5238** at identical retrieval metrics. Audit §8 and F-5 say the difference is not attributable. Step 0 §7.2 attributes it to uncommitted changes dated after the report | Step 0 §7.2; audit §8 and F-5; `chat/rag.py` mtime cited in Step 0 | **No** — the attribution is a hypothesis | Committed baseline or a digest-based manifest (P1.3) |
| **D-8** | Audit F-4 cites `save_upload` at L155, L198, L259, L234, L176. Current lines are L142/L166, L181, L246/L270, L221/L245, and one call in `run_structure_element_measurement.py` | Source grep in this task | **Yes** — the mechanism is unchanged; lines moved | None (audit left unchanged) |
| **D-9** | Audit F-1 cites raw deletes at specific lines (e.g. `run_phase3d_evaluation.py` L534–539, L637–640). Those statements no longer exist | Source grep: no executable `DELETE FROM` in the five | **Yes** — removed by Steps 0.8–1.2 | None |
| **D-10** | Steps 1.1 and 1.2 (and the README sections written then) say an interrupted run is "recoverable" through the exact-email sweep | No test seeds an interrupted run (N-3); the claim is design inference | **No** | Interrupted-run test |
| **D-11** | Step 1.2 README and report: "Step 0.5 F-1 (second half) — inventory complete". The inventory is the set of runners with raw or unscoped cleanup as listed in the Step 0.5 audit and Step 0.7 §9 | Source: no executable unscoped delete in the six runners; residual raw SQL in the upload runner (D-3) | **Partly** — "complete" is true only for executable unscoped deletes | Re-state as "no unscoped delete remains; residual raw SQL in one runner" |
| **D-12** | Step 0 §2.4 / §8 says "ten research runners still hard-code or default to the application database"; audit §10 F-1 and F-2 give different subsets; the README now lists four "still uninstrumented" | Counts depend on scope definitions (pre- and post-Step 0.6) | **Yes** — the counts use different definitions | State the definition used per count |
| **D-13** | Step 0.5 F-8 says no test references the nine runner names. Now five legacy runners and the upload runner are referenced | `test_legacy_runner_isolation.py`; grep of `tests/` | **Yes** — F-8 is partly remediated | Coverage for the four structure/table runners |
| **D-14** | Audit F-9 cites `tests/e2e/browser/test_phase6_reliability.py:99` relative `uploads/phase6_test.pdf` | Source L99 still relative | **Yes** — unchanged | None |
| **D-15** | `DOCUMIND_PROJECT_CONTEXT.md` §64 (Step 0.7 pointer) says the step "closes Step 0.5 finding F-3" | Step 0.7 §9 discloses residual raw SQL (D-3) | **Partly** — the unscoped delete is closed; the file is not fully model-bound | Model-bound conversion (P1.1) |
| **D-16** | Step 0 §7 reports `tests/integration tests/e2e` = **275 passed, 6 skipped** with PostgreSQL up | No log in the repository; no later re-run | **No** | Stored run log and exit code |
| **D-17** | Step 0 §7.1 records the QA weights SHA-256 as `cb9f1dde…`, the benchmark as `1166bf4f…` | Recomputed in this task: **`cb9f1dde94fca0e1f82c440bdc184ff54ba02efb6ea432e37a8c6ff8a8f69deb`** and **`1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0`** | **Yes** — both match | None |
| **D-18** | Step 0 §9.8 reports that the integration suite writes into `./uploads`, while Step 1.x reports say nothing in `backend/uploads/` was changed | Count 1112 identical across reports; 74 entries dated 2026-10-09 | **Partly** — the count is stable, but today's date entries show writes during this program's work | Per-run upload manifest |
| **D-19** | Audit F-6 (§10) says "a same-named DB on another host is permitted by design" and treats it as a risk; audit §5 says identity includes host/port and rates it "Allowed by design (documented)" | Both statements are in the same audit and are consistent: the design permits it, and the audit flags it as a residual risk | **Yes** — not a contradiction | None |

---

## Section 7 — Remediation History

| Step | Intended scope | Reported changes | Reported tests | Verification limitations | Risks carried forward |
|---|---|---|---|---|---|
| **0** (`STEP0_EVALUATION_INFRASTRUCTURE_HARDENING_2026-10-09.md`) | Central guard (`isolation.py`), output directory and manifest (`artifacts.py`), instrument `run_dual_path_ablation.py` and `run_phase3d_upload_integration.py` | New `isolation.py`, `artifacts.py`; instrumented two runners; no migration; `UPLOAD_DIR` redirected manually for runs; PG created/dropped for runs | §7: `tests/unit/evaluation` **184**, `tests/unit` **687** (exit 0); `tests/integration tests/e2e` **275 passed, 6 skipped** with PG up (exit 0); runs 4–8 as in §4 | Live-server e2e not run (§8); the five legacy runners not run; no log file for the integration run; §7.2 metric discrepancy unresolved | F-1 (guard missing for R3–R7 at the time), F-2, F-4, F-5, F-6, F-7, F-8, F-9, F-10, F-11, F-12, F-13, F-14, F-3 (unscoped chunk delete) |
| **0.5** (`STEP0_5_EVALUATION_RUNNER_SAFETY_AUDIT_2026-10-09.md`) | Read-only audit of every entry point; §10 F-1 to F-14; §11 recommended order | None (no implementation, per its §15) | None; audit §13 lists commands | Audit did not execute runners; some claims are source-only | All F-findings above |
| **0.6** (**no report file**; `evaluation/README.md` §"Five legacy phase runners", and `tests/unit/evaluation/test_legacy_runner_isolation.py`) | Guard, explicit target and no default DSN for five legacy runners | Module-level `DATABASE_URL` default removed; `--database-url` added; guard before import/engine (source-confirmed, §3A) | Spec file (14 defs × 5 = **70** cases, reported as 70 passing in Step 1.2 §4); README records a closed-port process run (exit 1) — **no transcript on record** (D-6) | No report; counts inferred from D-5 | F-1 (guard half closed; deletes handled in 0.8–1.2), F-6, F-7 |
| **0.7** (`STEP0_7_…`) | Scoped cleanup for the upload runner (F-3) | `cleanup_harness_rows(db, *, user_id)`; unscoped chunk delete removed; docstrings updated; four email-scoped raw statements left (disclosed) | `test_phase3d_cleanup_scope.py` **17 passed**, exit 0; `tests/unit/evaluation` **271**; `tests/unit` **774** | SQLite only; no PG after the change; the runner is not in the legacy spec | Residual raw SQL (D-3, §5.4); success-path cleanup; F-4 |
| **0.8** (`STEP0_8_…`) | Scoped cleanup for `run_phase3d_evaluation.py` | Ten raw statements replaced by `owned_user_ids` / `cleanup_harness_rows`; exact emails; README section added | `test_phase3d_evaluation_cleanup_scope.py` **16 passed**, exit 0; `tests/unit/evaluation` **287**; `tests/unit` **790**; `test_legacy_runner_isolation.py` + cleanup file **86 passed** | SQLite only; PG binding "inferred" (§5 of report) | F-4, F-7, F-9 (CWD report write), concurrency (5.1) |
| **0.9** (`STEP0_9_…`) | Scoped cleanup for `run_phase3e_integration.py` (unscoped `document_chunks`) | Four raw statements replaced; text removed from file | `test_phase3e_integration_cleanup_scope.py` **16 passed**, exit 0; eval **303**; unit **806** | SQLite only | F-7; concurrency (5.1); random identities (no interrupted-run recovery) |
| **1.0** (`STEP1_0_…`) | Scoped cleanup for `run_phase3e_validation.py`; retain read-only `text()` diagnostics | Four raw destructive statements replaced; diagnostics preserved | First run **86 passed, 1 failed** (exit 1, `test_read_only_diagnostics_are_left_alone`), fixed in the collector; then eval **320** (exit 0), unit **823** (exit 0) | SQLite only; step-5 inline delete source-only | Step-5 behavioural gap; F-7; never run on PG |
| **1.1** (`STEP1_1_…`) | Scoped cleanup for `run_phase3f_evaluation.py` (prefix and unpredicated deletes) | Ten raw statements replaced; `HARNESS_LABELS`; `text` import removed | `test_phase3f_evaluation_cleanup_scope.py` **18 passed**, exit 0; isolation **88** (18 + 70) passed, exit 0; eval **338**; unit **841** | SQLite only; PG binding inferred; the harness itself not run | Deterministic identity collision (5.1); interrupted-run claim (N-3, D-10); F-4; F-9 |
| **1.2** (`STEP1_2_…`) | Scoped cleanup for `run_phase4b_evaluation.py` | Ten raw statements replaced; `HARNESS_LABELS`; `text` removed; legacy spec `scoped_cleanup=True` | `test_phase4b_evaluation_cleanup_scope.py` **19 passed**, exit 0; `test_legacy_runner_isolation.py` **70 passed**, exit 0; eval **357**; unit **860**; py_compile / compileall exit 0 | SQLite only; harness not run; PG not run; §9 of report calls the six-runner inventory complete | Same as 1.1, plus D-11 wording |

---

## Section 8 — Prioritised Follow-Up Plan

**Status of every item: Proposed.** These are recommendations, not authorisations. The evidence for the
priority assignments is stated for each. Items with insufficient evidence are marked accordingly.

### P0 — Resolve before any destructive or database-writing evaluation execution

| ID | Action | Bounded scope | Rationale | Acceptance criteria | Priority status |
|---|---|---|---|---|---|
| **P0.1** | Verify the post-change cleanup of `run_phase3d_upload_integration.py` (and, separately, one legacy runner) against a disposable isolated PostgreSQL database | One runner per run; one isolated DB created and dropped; no application-DB connection; explicit operator approval | N-1, D-4: the only PG-tested runner predates its cleanup change; no legacy runner has ever run on PG | Exit 0; foreign-owned rows (documents, chunks, logs) survive with chunk ids preserved; harness rows removed; evidence file recorded | **Proposed P0** — the scoped deletes are unverified on PG |
| **P0.2** | Stop unguarded fixed-path overwrites: route `run_structure_confirmation.py`, `run_structure_element_measurement.py`, `run_structure_rrf_calibration.py`, `run_table_evidence_measurement.py` through `RunOutput`, and make `runner.write_report(out_dir=None)` raise | Four runners plus `runner.py`; no change to metrics or report content | F-2: a re-run replaces recorded evidence; four runners can reach the application DB via `storage.database` | Second run into the same directory is refused; recorded files byte-identical; the four runners refuse the application DSN by guard | **Proposed P0** — the overwrite is destructive to evidence |
| **P0.3** | Decide the argv-credential policy (F-7) before any run with a real credential | Policy decision, then a warning or refusal in the seven runners | F-7 Medium; a run with a real DSN on argv leaks it | Policy recorded; argv DSN produces a warning or refusal (tested) | **Proposed P0** — conditional on whether real credentials will be used |

### P1 — Isolation and artifact management

| ID | Action | Bounded scope | Rationale | Acceptance criteria | Priority status |
|---|---|---|---|---|---|
| **P1.1** | Convert the four residual raw `text("DELETE …")` statements in `run_phase3d_upload_integration.py` (L504–519) to `cleanup_harness_rows` | One file; the two isolation-check users | D-3, §5.4; removes the last executable raw destructive SQL in a remediated runner | Raw destructive SQL count in the file = 0; focused test added; PG run per P0.1 | **Proposed P1** |
| **P1.2** | Redirect `settings.upload_dir` to a runner-owned temporary directory in `run_dual_path_ablation.py`, `run_phase3d_evaluation.py`, `run_phase3f_evaluation.py`, `run_phase4b_evaluation.py`, `run_structure_element_measurement.py`; add a test fixture | Five runners and one fixture; no sweep of existing uploads | F-4, §5.3 | Count of `backend/uploads/` unchanged after a run; uploads land only under the temp root | **Proposed P1** — storage pollution is recorded but its harm is not measured |
| **P1.3** | Add source digests of the run-path modules to the manifest (F-5) | `artifacts.py` and manifest schema; new field only | F-5, D-7 | Manifest digest per listed module; a changed module changes the digest; the Step 0 §7.2 gap is attributed or recorded | **Proposed P1** |
| **P1.4** | Route `run_table_evidence_measurement.py` through the central guard (F-6) | One runner | F-6, §3C | Application DB refused by identity; loopback check no longer sole protection | **Proposed P1** |
| **P1.5** | Re-verify the Step 0.6 process-level closed-port runs or record them (D-6) | Re-run only if authorised; otherwise document the gap | D-6, D-5 | Transcript or report with exit codes | **Proposed P1** — evidence gap, low cost |

### P2 — Broader test coverage, provenance, operations

| ID | Action | Bounded scope | Rationale | Acceptance criteria | Priority status |
|---|---|---|---|---|---|
| **P2.1** | Extend `test_legacy_runner_isolation.py` (or a sibling spec) to the upload runner and the four structure/table runners plus `run_phase4c_diagnostics.py` | Test files only | F-8, N-2, D-13 | Each runner appears with guard, report-path and no-raw-SQL assertions | **Proposed P2** |
| **P2.2** | Warn on or refuse `--database-url` DSNs on argv (F-7) | Seven runners' argument parsing | F-7 | Warning or refusal, tested | **Proposed P2** (P0.3 may promote) |
| **P2.3** | Anchor CWD-relative paths to `Path(__file__)` (F-9, extended to the report writes of three legacy runners) | Four runners plus one e2e test | F-9, §2 | Paths absolute; a test runs from another CWD | **Proposed P2** |
| **P2.4** | Pin or declare the network model fetch in `phases/phase4f/balance_gate.py` (F-11) | One file | F-11 | Pinned revision or declared dependency | **Proposed P2** |
| **P2.5** | Remove or annotate empty `evaluation/baselines/*` packages (F-12) | Three packages | F-12 | Each carries an accurate README or is removed | **Proposed P2** |
| **P2.6** | Align the runtime `operation` message of the upload runner with its scope (F-14) | One string | F-14 | Runtime message names the scope; test asserts it | **Proposed P2** |
| **P2.7** | Add an interrupted-run test for the exact-email sweep (N-3, D-10) | Test only, using SQLite fixtures | §5.2 | Test seeds leftover rows and shows exact removal | **Proposed P2** |
| **P2.8** | Annotate the stale README sentence (D-1) and the "instrumented" label (D-2) without rewriting history | Documentation only | D-1, D-2 | Annotations added; historical text untouched | **Proposed P2** |
| **P2.9** | Write the missing Step 0.6 report, or an annotated summary, citing the test counts it actually produced (D-5, D-6) | Documentation only; no rerun | Evidence gap | Report exists and cites recorded results only | **Proposed P2** |
| **P2.10** | Decide the scope and status of F-10 (frozen benchmark abstention runner) | Planning | F-10; Phase 1 dependency | Decision recorded | **Proposed P2** |

### Later — requires separate authorisation

| ID | Action | Scope | Acceptance criteria | Priority status |
|---|---|---|---|---|
| **L.1** | Isolated PostgreSQL verification of all seven cleanup runners, one at a time | Disposable DB per run; operator approval | Foreign rows survive; exit codes and report formats recorded | **Proposed — Later** |
| **L.2** | Concurrency design: run-id-scoped identities for the two deterministic harnesses (5.1) | Design decision; then implementation | Two concurrent runs in one DB keep each other's rows | **Proposed — Later** (design decision required) |
| **L.3** | Opt-in, env-gated end-to-end job (audit §9C) | CI variant of the six browser tests | Documented skip policy; job runs when enabled | **Proposed — Later** |
| **L.4** | Lecturer-specific evaluation suite | Not built; no corpus exists (audit §9D) | Requirement decision first | **Proposed — Later** (no evidence of scope) |

---

## Section 9 — Closure Criteria

**Unit-test success alone is insufficient** for database-safety or production-safety approval. Every closure
below needs evidence of the kind named.

### 9.1 For this register to be considered complete

* Every finding in §2 has a status drawn from {Open, Partially remediated, Reported complete, Independently verified, Unknown}
  with the evidence cited.
* Every runner in §3 has source-level evidence for guard, cleanup and report path, dated to a recorded commit or digest.
* Every discrepancy in §6 is either resolved with evidence or explicitly carried forward.
* The register's Git and protected-artifact checks (Appendix A) are repeated after any later change to the register.

### 9.2 For an individual finding to be closed

| Finding | Closure evidence required (minimum) |
|---|---|
| F-1 | A PG-verified run of each of the five legacy runners' cleanup, with foreign rows surviving (P0.1 / L.1); guard refusal recorded at process level |
| F-2 | Re-run into the same directory refused; prior artifacts byte-identical; the four runners reachable only through `RunOutput` |
| F-3 | Raw SQL count in the upload runner = 0 (P1.1); PG-verified run after the change (P0.1) |
| F-4 | Post-run `backend/uploads/` count unchanged, and a test that fails if `upload_dir` is not redirected |
| F-5 | Manifest digests verified against source; a deliberate code change produces a different digest in a test |
| F-6 | The four structure/table runners and `run_table_evidence_measurement.py` route through the central guard, with refusal tests |
| F-7 | Test showing argv DSN is refused or warned, and that the env form is accepted |
| F-8 | All nine audit runners appear in a spec or a test file with guard/report/SQL assertions |
| F-9 | Test that runs each affected entry point from a different CWD and proves the path is independent of CWD |
| F-10 | Frozen-benchmark abstention runner with a manifest, digest and denominator (not started) |
| F-11 | Pinned or declared model dependency, or documented removal of the network fetch |
| F-12 | Packages removed or documented |
| F-13 | Documented; no closure test needed unless a module-scope reference is added |
| F-14 | Runtime message test |

### 9.3 For the evaluation infrastructure to be considered ready for isolated PostgreSQL verification

* P1.4 and P2.1 complete: every database-touching runner is guarded and listed in a spec.
* F-2 for the four structure/table runners resolved (P0.2), so no runner can overwrite recorded evidence.
* An isolated-DB provisioning procedure exists and is documented, with a teardown that is verified not to touch the application DB.
* The target identity is recorded in every manifest the runner produces.

### 9.4 For a future controlled evaluation run to be authorised

* The runner is one of the verified set (§3), and its PG-verified cleanup run (P0.1) is recorded.
* The target database is named by the operator, guarded by identity, and not the application database.
* The upload root is redirected (P1.2), or the operator has explicitly accepted the write to `backend/uploads/`.
* Output goes to a new, empty, caller-chosen directory (`RunOutput`), and no existing report is at risk.
* The provenance manifest contains source digests (P1.3), or the operator accepts that the result cannot be reproduced from the repository.
* The operator has approved the run in writing for that specific runner and database.

---

## Appendix A — Inspection Record and Repository Preservation

### A.1 Actions performed in this task

* Read: the Step 0.5 audit (§§1–5, 9, 10, 11), the Step 0 report (§§7–11), the Step 0.7–1.2 reports (test and result sections),
  `backend/evaluation/README.md` (headings, Step 0.6, Step 0.7–1.2 sections, outstanding list), `DOCUMIND_PROJECT_CONTEXT.md`
  (§64 pointers at L1964–1969), `backend/tests/unit/evaluation/test_legacy_runner_isolation.py` (spec and parametrisation).
* Searched (`grep`, line search, directory listing): the runners under `backend/evaluation/experiments/`, `evaluation/runner.py`,
  `evaluation/artifacts.py`, `evaluation/isolation.py`, `config.py`, `storage/file_store.py`, `chat/qa_model.py`,
  `scripts/cleanup_*.py`, `tests/e2e/browser/`, `phases/phase4f/balance_gate.py`, `evaluation/baselines/`, and the `tests/` tree for runner names and `def test_` counts.
* Hashed (read-only): `backend/models/documind-qa/model.safetensors` (SHA-256 `cb9f1dde…`), `backend/phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl`
  (`1166bf4f…`), `backend/.env.example` (`0109d932cfab3c6f89641792720ca1a7448514809d8438bc2d02d2473d1364ed`), `backend/evaluation/reports/ablation_A.json`
  (`9db8a5dd8479f5d9cc00e8894d6ab42cb94a10f044cdec66137dcadb4687d2ee`; first recorded here, no prior digest in any report).
* Stat'd (mtime only): `backend/.env` (2026-10-06), `backend/models/documind-qa/model.safetensors` (2026-09-02), `backend/evaluation/reports/ablation_A.json` (2026-10-04 18:16).
* Counted: `backend/uploads/` entries (**1112**).

### A.2 Actions **not** performed

* No test, runner, `py_compile`, `compileall` or AST script was executed.
* No database was contacted, queried, migrated, created, dropped or truncated.
* No file under `backend/` or the repository root was edited, created or deleted, other than this register.
* No commit, push, reset, stash, clean or checkout.
* No file under `backend/uploads/`, `backend/evaluation/reports/`, `backend/phases/`, `backend/models/`, `backend/.env*` was modified.

### A.3 Preservation checks

| Check | Expected | Observed | Result |
|---|---|---|---|
| Git status entries at baseline | 384 (55 `??`, 295 `D`, 34 `M`) | 384 (55 / 295 / 34) recorded before inspection | Baseline recorded |
| Tracked-modified path list digest | `de7230db…` at baseline | Recorded | Baseline recorded |
| QA weights SHA-256 | Matches Step 0 §7.1 (`cb9f1dde…`) | `cb9f1dde94fca0e1f82c440bdc184ff54ba02efb6ea432e37a8c6ff8a8f69deb` | **Match** (independently recomputed) |
| Frozen benchmark SHA-256 | Matches Step 0 §7.1 (`1166bf4f…`) | `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` | **Match** (independently recomputed) |
| `backend/.env` mtime | 2026-10-06 (Step 1.1 §5, Step 1.2 §5) | 2026-10-06 | Unchanged |
| `backend/evaluation/reports/ablation_A.json` mtime | 2026-10-04 18:16 (Step 0 §7.1, Step 1.x §5) | 2026-10-04 18:16 | Unchanged |
| `backend/uploads/` entries | 1112 (Step 1.1 §5, Step 1.2 §5) | 1112 | Unchanged since the last recorded count |
| `run_phase3d_upload_integration.py` digest | `64e5b2fd…` (Step 0.7 §7) | Recorded in Step 1.2 §8; **not re-hashed** in this task | Not re-verified here |
| Git status after this file is created | Only `backend/architecture/EVALUATION_SAFETY_MASTER_REGISTER.md` added | Checked after writing (see final response) | Pending final check |

### A.4 Items that could not be verified

* **Recorded test results** (§4): not re-run, as the task requires.
* **Step 0.6 report content**: no file exists; its results are read from the README only.
* **`backend/uploads/` attribution**: the 74 entries dated 2026-10-09 cannot be traced to a run from the repository.
* **Interrupted-run and concurrent behaviour**: no test or recorded run exists.
* **PostgreSQL behaviour of the cleanup code**: not executed by anyone since the cleanup changes (§4, D-4).
