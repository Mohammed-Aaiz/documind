# STEP 1.6U — Independent Finding Adjudication

Date: 2026-10-13
Owner: COORDINATOR.

## PROVISIONAL — INDEPENDENT REVIEW GATE NOT SATISFIED

This report is a **provisional, non-independent adjudication**. The named project specialists (`DATABASE_AGENT`, `SECURITY_AGENT`, `EVALUATION_AGENT`, `TEST_AGENT`, `VERIFIER`) are **NOT EXECUTED — runtime dispatch unavailable** in this environment (§2). A single coordinator performed all analysis; generic read-only search workers gathered evidence but are not specialists. No finding below may be treated as having satisfied the independent-review gate. Two decisions (§13, §14) are deliberately non-authorizing.

## 1. Executive verdict and scope

**Verdict: COMPLETE as a provisional adjudication; the independent-review gate remains OPEN.**

What the current evidence establishes:

1. **Nothing destructive can currently execute through the reviewed lifecycle paths.** Every creation, disposal, row-cleanup and cleanup-execution gate in `backend/evaluation/isolation.py` raises unconditionally (`:377-412`, `:415-440`, `:443-453`, `:456-474`, `:477-482`), and `_proof_is_live()` is hard-coded `False` (`:363-366`). This is a *total refusal*, not an approval path.
2. **One confirmed source-level defect exists in the filesystem cleanup controls**: the symlink-root refusal in `backend/scripts/cleanup_path.py:37-51` cannot fire — it compares a value with itself (`:44` and `:48`). The `filesystem_supports_relative_symlinks()` gate is also an unconditional stub (`:54-66`).
3. **No runtime verification of anything exists.** No test execution is recorded in any reviewed artifact; every safety property is either source-inspected or asserted by unrun test definitions.

Scope: review and adjudication of U-01…U-06 only, using current source plus the Step 1.6N/O/P/Q/R/S/T reports as *evidence of earlier findings*. Static analysis only; no execution of any kind (§7 boundaries). Historical reports were read, not modified.

## 2. Named-agent dispatch and actual-execution evidence

Dispatch was attempted for all six named roles. The runtime exposes only generic subagents (`code-searcher`, `file-picker`, non-terminal worker); it has no target that instantiates the project roles defined in `agents/*.md`.

| Named role | Dispatch attempted | Actual status | Runtime evidence | Files/findings it would have covered | Concrete output |
|---|---|---|---|---|---|
| COORDINATOR | n/a | **EXECUTED** | This report | All | Plan, register, decisions, report |
| DATABASE_AGENT | Yes | **NOT EXECUTED — runtime dispatch unavailable** | No specialist agent type exists; `spawn_agents` accepts only `code-searcher` / `file-picker` / `base3-fast-worker-deepseek-flash` | U-01, engine/connection/permission evidence | None (role not run) |
| SECURITY_AGENT | Yes | **NOT EXECUTED — runtime dispatch unavailable** | as above | U-02, U-03 | None (role not run) |
| EVALUATION_AGENT | Yes | **NOT EXECUTED — runtime dispatch unavailable** | as above | U-02 runner/cleanup interaction | None (role not run) |
| TEST_AGENT | Yes | **NOT EXECUTED — runtime dispatch unavailable** | as above | U-05 | None (role not run) |
| VERIFIER | Yes | **NOT EXECUTED — runtime dispatch unavailable** | as above | All | None (role not run) |
| Generic `code-searcher` #1 (DATABASE/EVALUATION-scoped) | Yes | EXECUTED | 5 query batches; 78/28/32/10/137 line-referenced matches | U-01, U-02 evidence gathering | Guard/engine/`DELETE`/import order sites |
| Generic `code-searcher` #2 (SECURITY-scoped) | Yes | EXECUTED | 5 batches; 240/155/5/35/24 matches | U-02, U-03 evidence gathering | `DisposalProof`/`_proof_is_live` sites; `resolve`/symlink sites; archive ordering |
| Generic `code-searcher` #3 (TEST-scoped) | Yes | EXECUTED | 5 batches; 188/156/91/14/9 matches | U-05 evidence gathering | Test definitions; `inspect.getsource`/`source.index` assertions |
| Generic `code-searcher` #4 (VERIFIER-scoped) | Yes | EXECUTED | 5 batches; 71/17/83/62/0 matches | U-02, U-05 falsification | `monkeypatch` neutralisation sites; env/DSN reads |

**Integrity statement.** No specialist review is claimed or simulated. The coordinator's own analysis is the only analysis. Where this report disagrees with a prior report, that is a coordinator disagreement, not a reviewer consensus.

## 3. Source-artifact existence and availability

| Artifact | Exists | Size | Used as |
|---|---|---|---|
| `STEP1_6N_EVALUATION_SAFETY_REMEDIATION_ARCHITECTURE_2026-10-12.md` | YES | 221,272 B | Historical architecture intent |
| `STEP1_6O_INDEPENDENT_ARCHITECTURE_REVIEW_2026-10-12.md` | YES | 48,853 B | Historical review |
| `STEP1_6P_COMPLETE_CALLABLE_INVENTORY_AND_BYPASS_AUDIT_2026-10-12.md` | YES | 54,258 B | Historical inventory (P-series) |
| `STEP1_6Q_NORMALIZED_CALLABLE_INVENTORY_2026-10-12.md` | YES | 69,341 B | Historical inventory (Q-series) |
| `STEP1_6R_CANONICAL_CALLABLE_MANIFEST_2026-10-12.md` | YES | 589,745 B | Historical counts baseline |
| `STEP1_6S_INDEPENDENT_MANIFEST_REVIEW_2026-10-12.md` | YES | 24,963 B | Findings U-01…U-08 / S-1…S-5 |
| `STEP1_6T_MANIFEST_CLASSIFICATION_AND_SAFETY_BOUNDARIES_2026-10-13.md` | YES | 37,817 B | Findings T-R01…T-R08, classification rules |
| `backend/evaluation/isolation.py` | YES | 22,240 B | Primary safety source (522 lines) |
| `backend/storage/database.py` | YES | 1,979 B | Engine/session initialization |
| `backend/scripts/cleanup_path.py` | YES | 2,407 B | Filesystem guard helpers |
| `backend/scripts/cleanup_orphan_uploads.py` | YES | 9,278 B | Filesystem deletion path |
| `backend/tests/fixtures/integration_db.py` | YES | 23,188 B | Mirror guard / lifecycle fixture |
| `backend/scripts/db_check.py`, `backend/main.py`, `backend/scripts/start_server.py` | YES | 860 / 4,332 / 3,817 B | Connection/startup paths |

No listed artifact is absent, so no claim had to be based on a substitute. **Every prior report was read as evidence of an earlier finding only**; current source is the authority in this report, and where source and a prior report disagree, source wins (noted where it occurs).

## 4. Findings adjudication register (U-01 … U-06)

Severity is assigned to the *residual risk* the finding represents now, not to the size of the topic. Every row lists the ten required fields.

### U-01 — Database initialization and ownership

| Field | Value |
|---|---|
| Finding ID | U-01 |
| Severity | **High** (residual: unverified identity/permission; the production engine has no authorization boundary) |
| Primary status | **CONFIRMED** for the construction/connection split; **UNRESOLVED** for identity and permissions |
| Source | `backend/storage/database.py:39,43-48,49,56-63`; `backend/main.py:13,44-53,64`; `backend/scripts/db_check.py:13,18,33`; `backend/scripts/setup_db.py:41-46`; `backend/tests/fixtures/integration_db.py:255,302-340,429-445,528,588` |
| Evidence and reasoning | Module scope contains only `_asyncpg_engine_args(settings.database_url)` (pure string transform, `:11-38`), `create_async_engine(...)` (`:43-48`) and `async_sessionmaker(...)` (`:49`). No `connect`, `execute` or session acquisition occurs at import. **Inference (library semantics, not runtime-verified):** a SQLAlchemy `AsyncEngine` is a lazy pool manager, so construction opens no socket. Connection is instead triggered by `get_db()` (`storage/database.py:56-63`), `db_check.py:18` (`engine.connect()`, module-level `asyncio.run` at `:33`), `main.py:44-53` (`command.upgrade` at `:53`, dispatched from `_ensure_database_schema` via `loop.run_in_executor` at `:64`, with `from storage.database import Base, engine` itself at `:13`), `setup_db.py:41-46` (`subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"])`), and `integration_db.py:302-340` (`psql_value`, a `subprocess.run` of the `psql` binary) with the alembic-upgrade subprocess error path at `:429-445`. **25** Python modules statically import `storage.database` (grep over `backend/`, excluding `venv/`, `phases/`, `models/`, `evaluation/`); each such import executes the module-scope construction at `:39,43,49` when that import statement runs — module scope at import time, deferred (function-body) imports on first call. Note `integration_db.py` deliberately creates no async engine of its own (`:449-454`). |
| Confirmed vs possible impact | **Confirmed:** construction and connection are distinct; the file is importable without connecting (static). **Possible:** the guard's notion of "the application database" derives from `backend/.env` (`isolation.py:76,134`) or `get_settings()`; nothing in the repository binds engine construction to an authorization check. |
| Existing control | Runners import `storage.database` inside `main()` *after* `assert_safe_evaluation_target` (e.g. `run_phase3d_evaluation.py:674`, `run_phase3e_integration.py:208`), and `assert_engine_matches_target` (`isolation.py:504-522`) compares the engine URL to the approved DSN without connecting. |
| Missing evidence | Any runtime proof of server identity, role, TLS mode, pool/reconnect behaviour, or database privileges for the production engine. |
| Required next action | DATABASE_AGENT: define the evidence that establishes a target as genuinely disposable (server identity, role, grants, TLS, connection-bound lifecycle). No such evidence exists in-repo. |
| Reviewer / independent? | Coordinator only. **Not independent.** |

### U-02 — Lifecycle authorization

| Field | Value |
|---|---|
| Finding ID | U-02 |
| Severity | **Medium** (currently fail-closed; residual risk only on a future positive path) |
| Primary status | **CONFIRMED** (all destructive/lifecycle gates currently refuse unconditionally); **PLAUSIBLE** for one caller-order-dependent destructive block |
| Source | `backend/evaluation/isolation.py:350-361,363-366,369-374,377-412,415-440,443-453,456-474,477-482,485-501,504-522`; `backend/evaluation/experiments/run_phase3d_upload_integration.py:196-202,527-545`; `backend/tests/unit/evaluation/test_function_cleanup_authorization.py:20-34,84-87` |
| Evidence and reasoning | `DisposalProof` is `@dataclass(frozen=True)` with `_issuer` (`compare=False`, `repr=False`) and `lifecycle` and is documented as "Legacy evidence-shaped data, never authority". `_proof_is_live()` returns `False` unconditionally. `record_created_database` raises ("Caller declarations are not evidence"). `assert_disposal_authorized` validates name ≠ application name, delegates to `assert_safe_evaluation_target`, then **always raises** "no enforceable disposal boundary". `assert_creation_authorized`, `assert_row_cleanup_authorized` (delegating), `assert_cleanup_execution_authorized` (refuses to even inspect the resource), and `release_database_proof` all raise. `assert_engine_matches_target` compares `engine.url` fields to the DSN and raises on mismatch without connecting. Consequences: (a) the proof object cannot authorize anything, so forgeability/transferability/staleness are **moot today**; (b) protection does not depend on caller discipline *for these gates* because refusal is unconditional; (c) one inline raw-SQL cleanup block (`run_phase3d_upload_integration.py:527-545`, four `text("DELETE FROM …")` statements inside a session) is not individually gated — it is reachable only after `assert_disposal_authorized` at `:202`, which always raises, so it is **dead in practice** but represents caller-order dependence by design. The 12 direct boundaries in `test_function_cleanup_authorization.BOUNDARIES` do each begin with `assert_cleanup_execution_authorized` as their first executable statement (asserted by AST, not by execution). |
| Confirmed vs possible impact | **Confirmed:** no reviewed callable can authorize destruction; all attempts raise `UnsafeEvaluationTarget`. **Possible:** a future positive path would rest on caller discipline plus per-boundary gating, and at least one destructive statement is currently outside the per-boundary set. |
| Existing control | The refusal gates themselves; `assert_cleanup_execution_authorized` refuses "independent of environment/settings" (docstring `:466-470`). |
| Missing evidence | Any runtime demonstration that a real destructive callable is blocked in a live process; any external lifecycle authority; any connection-bound proof. |
| Required next action | SECURITY_AGENT + EVALUATION_AGENT review (unavailable); if a positive path is ever designed, every destructive statement must carry its own gate, and the `backend/.env`-derived notion of "application database" must be replaced by an externally attested identity. |
| Reviewer / independent? | Coordinator only. **Not independent.** |

### U-03 — Filesystem cleanup safety

| Field | Value |
|---|---|
| Finding ID | U-03 |
| Severity | **High** (a fail-closed guard cannot fire) — impact bounded to the operator-invoked cleanup CLI |
| Primary status | **CONFIRMED** source-level defect (dead symlink guard + stub capability check); **PLAUSIBLE** check-then-use window |
| Source | `backend/scripts/cleanup_path.py:18-34,37-51,54-66`; `backend/scripts/cleanup_orphan_uploads.py:50,98-127,192-199,200-224` |
| Evidence and reasoning | **Defect 1 (confirmed).** `forbid_symlink_roots` computes `root_real = root.resolve(strict=False)` (`:44`) and then tests `if root.resolve(strict=False) != root_real:` (`:48`). Both operands are the same expression on the same unchanged path, so the condition is **always False** and the intended refusal at `:49-51` is dead code. No `is_symlink()`/`lstat` check exists anywhere in the module. **Defect 2 (confirmed).** `filesystem_supports_relative_symlinks()` returns `True` unconditionally (`:54-66`); its own docstring says real support "is asserted in a later step". The import-time gate `cleanup_orphan_uploads.py:50` therefore cannot fail closed. **Residual impact:** the sweep resolves `settings.upload_path` and recurses it (`:85,132,154`), so a symlinked root would be traversed to its target; `is_under` (`:18-34`) still contains *resolved* paths, so deletion stays inside the resolved tree — the failure is operating on the wrong tree, not escaping containment. **Ordering:** the archive is written and CRC-verified (`:112-127`) *before* any deletion (archive call `:191-195`, deletion loop `:200-213`), and the archive is refused if inside the upload root (`:103-110`). **Plausible:** `forbid_symlink_roots(root)` (`:197`) and `is_under(root, path)` (`:203`) precede `path.unlink()` (`:210`) with no handle-bound (e.g. `O_NOFOLLOW`) deletion, so a path swapped between check and use is a check-then-use window; no dynamic evidence exists. |
| Confirmed vs possible impact | **Confirmed:** two intended controls cannot operate as written. **Possible (needs dynamic evidence):** TOCTOU exploitation. |
| Existing control | `is_under` resolved-path containment; archive-before-delete ordering; dry-run default (`:178-180`); explicit confirmation unless `--yes` (`:182-189`); unreadable-DB abort (`:135-141`). |
| Missing evidence | Whether the symlink tests ever executed (they `pytest.skip` when symlink creation is unavailable — `tests/unit/scripts/test_cleanup_orphan_uploads.py:203-212,246-255`), and any runtime demonstration of the TOCTOU window. |
| Required next action | SECURITY_AGENT: repair `forbid_symlink_roots` to test the path itself (`is_symlink`/`lstat`) and make the capability check real or remove it; TEST_AGENT: re-run the symlink tests on a POSIX host. **No repair was made in this task.** |
| Reviewer / independent? | Coordinator only. **Not independent.** |

### U-04 — Inventory classification

| Field | Value |
|---|---|
| Finding ID | U-04 |
| Severity | **Low** |
| Primary status | **CONFIRMED** (rules deterministic and consistently applied) with **UNRESOLVED** receiver classes |
| Source | `backend/architecture/STEP1_6T_…_2026-10-13.md` §7–§9; 1.6T scanner (embedded) |
| Evidence and reasoning | Rules D-1 (decorator → `decorator-annotation`), D-2 (receiver `client` → `http-request`) and D-3 (`np`/`numpy` → `array-op`) are deterministic and were verified by executing the embedded scanner in Step 1.6T: historical block unchanged (226 / 0 / 2,345 / 348 / 969 / 929 / 17 / 27 / 103) and classification counts stable (957/917 body, 16/16 module, 1 decorator site, 12 http-request, 0 array-op, 22 safety-helper records). Historical and revised counts are kept in separate columns. |
| Confirmed vs possible impact | **Confirmed:** determinism, separation of historical vs revised, and reproducibility. **Unresolved:** generic receivers not covered by D-2/D-3 (`add <- seen` 8, `save <- doc`/`document` 14, `open <- fitz` 12, `run <- asyncio` 10, `mkdir <- REPORTS_DIR` 7) remain `operational-candidate`, i.e. "not reclassified", not "proven destructive". |
| Existing control | Documented rules and an embedded, re-runnable scanner. |
| Missing evidence | A semantic classification for the residual receiver groups. |
| Required next action | Keep `operational-candidate` explicitly defined as non-proof; extend rules only with source evidence per receiver. |
| Reviewer / independent? | Coordinator; rules were verified by re-execution, not by an independent reviewer. |

### U-05 — Test coverage and verification claims

| Field | Value |
|---|---|
| Finding ID | U-05 |
| Severity | **High** (every safety claim rests on unexecuted tests) |
| Primary status | **UNRESOLVED** — no recorded execution evidence exists for any safety test |
| Source | Test definitions enumerated in §8; `backend/tests/unit/evaluation/test_function_cleanup_authorization.py:1-6` states "This is not DB runtime proof"; `test_legacy_runner_isolation.py:15`; `test_structure_runner_guard_order.py:13-15` |
| Evidence and reasoning | Safety tests exist and are of three kinds: (a) in-process behavioural tests of the guard functions with `PoisonResource`/`_forbidden` monkeypatches that block sockets and subprocesses (`test_isolation_guard_identity.py`, `test_lifecycle_authorization.py`, `test_disposal_authorization_contract.py`, `test_function_cleanup_authorization.py`, `test_legacy_runner_isolation.py`, `test_disposable_database_authorization.py`); (b) **source-text order assertions** using `inspect.getsource` + `source.index(...)` comparisons (all `test_phase3*_cleanup_scope.py`, `test_phase3_runner_target_order.py`, `test_runner_pre_engine_init.py`, `test_structure_runner_guard_order.py`); (c) DB-backed scope tests using the `db_session` fixture (SQLite per 1.6R §12), and filesystem-isolated tests with a faked DB (`test_cleanup_orphan_uploads.py`). No artifact records an execution result, and every reviewed report states tests were not run. Static source-order assertions cannot establish runtime ordering when modules are imported/deferred differently, and SQLite scope tests cannot establish PostgreSQL behaviour. |
| Confirmed vs possible impact | **Confirmed:** test *definitions* cover the refusal surface and the guard/engine source order. **Unresolved:** whether they pass, and what they establish at runtime. |
| Existing control | The tests themselves (as definitions only). |
| Missing evidence | Recorded execution (and, for the filesystem defect, execution on a symlink-capable host). |
| Required next action | TEST_AGENT to run the unit safety suites on a POSIX host and record results; keep DB-backed suites separate and non-PostgreSQL until authorized. |
| Reviewer / independent? | Coordinator only. **Not independent.** |

### U-06 — Evidence and wording corrections

| Field | Value |
|---|---|
| Finding ID | U-06 |
| Severity | **Medium** (over-strong wording could be read as closure) |
| Primary status | **CONFIRMED** (corrections required) |
| Source | 1.6T §3 ("RESOLVED (inventory)" for T-01…T-05), §7–§8; 1.6S §3–§5 |
| Evidence and reasoning | 1.6T's dispositions are accurate as *inventory* statements but the word "RESOLVED" invites the reading that the underlying safety concerns are closed. They are not: U-01 (unverified identity/permissions), U-02 (no positive authorization path; caller-order dependence at one block), U-03 (two dead/non-functional controls), U-05 (no execution evidence) all remain open. 1.6S's "independently reproduced" counts are sound as *count reproduction* but were produced by generic workers plus the coordinator, not by named specialists — 1.6S did label this, and this report repeats the label. Historical counts (2,345/348/969/929/17/27/103) are raw syntactic values and must not be read as confirmed operations; only the revised operational classes are classification outputs, and they remain candidates. |
| Confirmed vs possible impact | **Confirmed:** wording overstates closure; count semantics need the candidate caveat. **No** prior numeric count is contradicted by current source. |
| Existing control | 1.6T §8/§9 already separate historical from revised counts and label candidates. |
| Missing evidence | None for the wording correction itself. |
| Required next action | Apply these corrections **additively**; do not rewrite 1.6R/1.6S/1.6T in place (a constraint of this task and of AGENTS.md's append-only evidence rule). |
| Reviewer / independent? | Coordinator only. **Not independent.** |

## 5. Source citations

All claims above cite file and line ranges. The load-bearing ones: `backend/evaluation/isolation.py:350-361` (frozen, unauthorized `DisposalProof`), `:363-366` (`_proof_is_live` → False), `:369-374` (no issuer), `:377-412` (disposal always refuses), `:415-440` (creation always refuses), `:443-453` (row cleanup delegates), `:456-474` (execution gate always refuses, no attribute access), `:477-482` (release refuses), `:504-522` (engine/DSN literal comparison, no connection); `backend/storage/database.py:39,43-48,49,56-63`; `backend/scripts/cleanup_path.py:18-34,37-51,54-66`; `backend/scripts/cleanup_orphan_uploads.py:50,98-127,192-224`; `backend/evaluation/experiments/run_phase3d_upload_integration.py:196-202,527-545`.

## 6. Confirmed facts, inferences, and missing evidence

- **Confirmed by direct source:** module-scope construction performs no connection call; every lifecycle/destructive gate raises unconditionally; `_proof_is_live` returns `False`; `forbid_symlink_roots` compares a value to itself so its refusal is unreachable; `filesystem_supports_relative_symlinks` returns `True` unconditionally; archive is CRC-verified before deletion; one inline raw-SQL `DELETE` block exists outside the per-boundary gate set.
- **Inference (labelled):** that a constructed `AsyncEngine` opens no socket before first use (SQLAlchemy lazy-pool semantics, not executed here); that the affected tests would fail if run on a symlink-capable host (derived from the dead guard, not observed).
- **Missing evidence:** runtime connection identity/role/TLS/privileges; any executed test result; any proof that a live destructive callable is blocked; PostgreSQL behaviour of scope/cleanup tests; dynamic evidence for the check-then-use window; an external lifecycle authority.

## 7. Historical versus revised inventory-count semantics

| Unit | Historical (1.6R syntactic) | Revised (1.6T classified) | Semantics |
|---|---:|---:|---|
| Raw matched call nodes (callable bodies) | 969 | 957 operational-candidate + 12 http-request | Historical is raw; revised is classified candidates |
| Unique body sites | 929 | 917 operational-candidate | same |
| Module/class-scope sites | 17 | 16 operational-candidate + 1 decorator-annotation | same |
| Records / defs / entries / main blocks | 348 / 2,345 / 103 / 27 | unchanged | Historical values re-derived and unchanged |
| Safety-helper records | not represented | 22 | New inventory class, no historical counterpart |

Historical counts are **raw syntactic occurrences**, not confirmed operations. Revised counts are **candidates after classification**, not confirmed operations either. Neither column is evidence that an operation executes.

## 8. Test-evidence matrix (definitions vs recorded execution)

| Test module | Kind | Safety property it addresses | Candidate ops in scope | Recorded execution? |
|---|---|---|---|---|
| `tests/unit/evaluation/test_isolation_guard_identity.py` | Behavioural, no I/O (monkeypatched sockets) | Target ≠ application DB; malformed/unsupported URLs fail closed; no credential echoed | — | **Not recorded** |
| `tests/unit/evaluation/test_lifecycle_authorization.py` | Behavioural + AST | Creation/row-cleanup/drop refusal; proof not live; issuer copying not authority | — | **Not recorded** |
| `tests/unit/evaluation/test_disposal_authorization_contract.py` | Behavioural + source-text | Proof cannot authorize; gate precedes `os.environ["DATABASE_URL"]` in runners | identifiers only | **Not recorded** |
| `tests/unit/evaluation/test_function_cleanup_authorization.py` | AST boundary extraction + poisoned resources | Each of 12 direct boundaries refuses before resource access | `cleanup_harness_rows`×6, `_delete_user_data`, `teardown`, `run_once`×4 | **Not recorded** |
| `tests/unit/evaluation/test_legacy_runner_isolation.py` | Behavioural + `inspect.getsource` order | Guard before engine factory; no import-time DB selection | runner entry points | **Not recorded** |
| `tests/unit/evaluation/test_runner_pre_engine_init.py` | Subprocess + source order | Runner import does not import `storage.database` | `run_table_evidence_measurement.amain`, `run_dual_path_ablation.main` | **Not recorded** |
| `tests/unit/evaluation/test_structure_runner_guard_order.py` | Source order + fake modules | Guard before storage import; refusal exports no `DATABASE_URL` | 4 structure runners | **Not recorded** |
| `tests/unit/evaluation/test_phase3_runner_target_order.py` | Source order | Guard → configure → engine → session order | Phase 3D/3E/3F/4B runners | **Not recorded** |
| `tests/unit/evaluation/test_phase3d_cleanup_scope.py`, `…phase3e_integration…`, `…phase3e_validation…`, `…phase3d_evaluation…`, `…phase3f…`, `…phase4b…` | SQLite `db_session` + source order | Row cleanup scoped by ownership; no unscoped `DELETE FROM` | runner cleanup helpers | **Not recorded** |
| `tests/unit/evaluation/test_disposable_database_authorization.py` | Behavioural + source-text | Fixture/central both refuse without proof; provisioning never calls the destructive gate without a proof | `integration_db` lifecycle primitives | **Not recorded** |
| `tests/unit/scripts/test_cleanup_orphan_uploads.py` | Filesystem-isolated, faked DB | Dry-run default; unreadable DB aborts; archive outside upload root; symlinked root rejected; `is_under`/`forbid_symlink_roots` helpers | `cleanup_orphan_uploads` sweep | **Not recorded**; symlink cases `pytest.skip` without symlink capability |
| `tests/unit/storage/test_database_url.py` | Unit | `sslmode` → `ssl` translation; URL otherwise unchanged | `_asyncpg_engine_args` | **Not recorded** |
| `tests/unit/storage/test_sqlite_type_isolation.py` | SQLite `db_session` | SQLite DDL does not mutate `Base.metadata` | — | **Not recorded** |
| `tests/integration/documents/test_table_row_migration.py` | SQLite + subprocess Alembic | 007 upgrade/downgrade on SQLite | migration revisions | **Not recorded** |

No test in this matrix was executed by this task, and no execution record was found in the reviewed artifacts.

## 9. Unresolved Critical/High findings and required closure evidence

| ID | Severity | Unresolved aspect | Required closure evidence |
|---|---|---|---|
| U-01 | High | No evidence of engine identity, role, TLS, privileges or connection-bound lifecycle; production engine has no authorization boundary | Externally attested target identity + role/grants/TLS evidence for every physical connection, and an approved connection-bound lifecycle authority |
| U-03 | High | `forbid_symlink_roots` cannot fire; capability check is a stub; TOCTOU unproven | Corrected guard + a symlink-capable host run of the symlink tests; dynamic evidence for the check-then-use window |
| U-05 | High | No safety test has a recorded execution | Recorded results of the unit safety suites (POSIX host), clearly separated from any PostgreSQL work |
| U-02 | Medium | No positive authorization path exists; one inline destructive block lacks its own gate | SECURITY/EVALUATION review plus per-statement gating if a positive path is ever designed |
| U-06 | Medium | Over-strong "RESOLVED" wording in 1.6T | Additive correction note (this report) — applied |

**Critical:** none. No finding is rated Critical because nothing in the current implementation can execute a destructive database or filesystem operation through the reviewed paths, and the filesystem defect is bounded to an operator-invoked CLI whose containment check still constrains deletion to the resolved tree.

## 10. Disagreements and unresolved classification questions

1. **1.6T's "RESOLVED" dispositions (disagreement).** Coordinator holds that T-01/T-02/T-04/T-05 are *inventory* completions, not safety closures; reclassified here as CONFIRMED findings with open sub-items.
2. **Filesystem guard test status (unresolved).** `test_forbid_symlink_roots_rejects_symlinked_root` asserts a `RuntimeError` the implementation cannot raise. Either the test has never run on a symlink-capable host, or a different code path satisfies it. Not resolvable without executing it (not permitted here).
3. **`filesystem_supports_relative_symlinks` (unresolved).** Documented as a contract stub and treated as a real gate at `cleanup_orphan_uploads.py:50`; whether that gate has ever influenced a decision is unknown.
4. **Inline `DELETE` block (unresolved classification).** `run_phase3d_upload_integration.py:527-545` is destructive SQL that is *outside* the per-boundary gate set but *downstream* of an unconditional refusal, so it is dead-in-practice yet architecturally ungated. Whether that counts as a bypass depends on a positive-path design that does not exist.
5. **Two guards, different rules (unresolved).** `isolation.py:35-45` documents that the `tests/fixtures/integration_db.py` mirror compares `(host, port, database)` textually and does not refuse the host-alias cases the central guard refuses. Which guard is authoritative for a future positive path is undecided.
6. **Application-controlled configuration (unresolved).** `isolation.py:76,134` derives "the application database" from `backend/.env`/`get_settings()`. The module's own "Known limitation" states separation relies on the application URL naming the database it really uses. Today this is shadowed by total refusal; it would matter for any future positive path.

## 11. Git preservation evidence

- HEAD before and after this task: `6baaa2a0773df66e5fb26814afbe67647fb43435` (**unchanged**).
- Baseline snapshot for this task: `%TEMP%/step16u-status-before.txt`, `git status --porcelain=v1 --untracked-files=all`, **1,146 rows** (already includes the 1.6R/1.6S/1.6T reports and all pre-existing working-tree changes). Prior `step16r-*`, `step16s-*`, `step16t-*` snapshots were not overwritten.
- Post-report comparison: §15.

## 12. Decision — implementation planning

**Implementation planning may proceed for documentation-only and non-destructive changes only** (e.g. correcting `cleanup_path.forbid_symlink_roots`, adding tests, applying wording corrections). **No implementation that creates, migrates, drops, truncates or cleans a database, or that performs destructive filesystem deletion, is authorized by this review.** The independent-review gate is unmet, U-01/U-03/U-05 remain open, and U-03's correction would itself require SECURITY_AGENT review plus a symlink-capable test run before it can be called closed.

## 13. Decision — PostgreSQL and destructive filesystem testing

**NO-GO, for both.** No runtime identity, role, TLS, least-privilege or application-database-denial evidence exists; every destructive gate refuses by design; no safety test has a recorded execution; and the filesystem deletion path contains a confirmed non-firing guard. Completion of this review — provisional as it is — is explicitly **not** a basis for authorizing PostgreSQL execution.

## 14. Recommended next bounded task

Obtain the named specialist reviews through a runtime that can actually execute those roles, scoped to: **(1)** DATABASE_AGENT — U-01 closure evidence (identity/role/grants/TLS, connection-bound lifecycle); **(2)** SECURITY_AGENT — U-03 guard repair review + TOCTOU assessment; **(3)** TEST_AGENT — execute the unit safety suites on a POSIX host and record results; **(4)** VERIFIER — challenge this provisional register. Until then, no destructive or PostgreSQL work should be planned beyond the documentation corrections already identified.

## 15. Post-report status comparison

- Final `git status --porcelain=v1 --untracked-files=all`: **1,147 rows**; normalized set difference against the 1,146-row baseline is **exactly one added path** — `?? backend/architecture/STEP1_6U_INDEPENDENT_FINDING_ADJUDICATION_2026-10-13.md` — with **0 removed** and **0 changed** rows; non-untracked tracking entries are byte-identical between baseline and final.
- HEAD final: `6baaa2a0773df66e5fb26814afbe67647fb43435` (**unchanged**).
- No file was deleted, moved, reset, stashed, reverted or overwritten; no prior report was modified.

---

**Provisional status restated.** This adjudication was produced by one coordinator with generic read-only search support. The named specialists did not execute. It satisfies no independent-review gate and must be superseded by genuine specialist review before any PostgreSQL or destructive filesystem testing is authorized. Verification method: static source inspection only — no test, fixture, runner, migration, database or cleanup operation was executed, and no application module was imported.
