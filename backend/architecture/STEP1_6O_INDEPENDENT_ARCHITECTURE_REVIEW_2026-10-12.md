# Step 1.6O — Independent Architecture Review and Approval Gate

Date: 2026-10-12  
Decision: **BLOCKED — NOT APPROVED FOR POSITIVE LIFECYCLE IMPLEMENTATION OR POSTGRESQL VERIFICATION.**  
PostgreSQL status: **NO-GO.** This is an architecture/documentation review only.

## 1. Executive decision

**The Step 1.6N proposal is materially stronger than the current implementation and identifies the right trust boundaries, but it is not sufficiently settled or independently reviewed to approve the proposed positive lifecycle or broad implementation program.** Its strongest elements are the separate out-of-process lifecycle authority, refusal of in-process proof objects, immutable target intent, crash quarantine, role separation, use-time connection binding, and a separately governed filesystem executor. These are proposals, not existing safeguards.

Proceed only with narrowly bounded, non-enabling tasks that preserve today’s fail-closed behavior: make the test/runner inventory callable-specific and regression-test its completeness; specify operator ownership and identity attestation; and refine the filesystem platform contract. Do not implement a positive database create/migrate/write/cleanup/drop path, authorize cleanup, or run PostgreSQL. The exact blockers and component-level dispositions are in §10.

**Current safeguards (`SOURCE-VERIFIED`):** `backend/evaluation/isolation.py` refuses database creation, disposal, proof issuance/release, and cleanup execution. `backend/tests/fixtures/integration_db.py` refuses before its reachability/provisioning sequence; the E2E function refuses before engine creation. These are meaningful default denials, not a proof that every lower-level helper is inaccessible, nor a working positive lifecycle.

**Proposed safeguards (`DESIGN-PROPOSAL`):** ELA, immutable manifest, dedicated cluster, role/network restrictions, actual-connection leases, durable journal, quarantine/recovery, and filesystem plan/review/execute. None is implemented or approved. PostgreSQL server identity, permissions, pooling/reconnect behavior, and filesystem platform guarantees cannot be proved from this source review.

## 2. Reviewer participation and independence

The requested assignments are recorded explicitly below. The runtime exposes no specialist-dispatch tool/API; repository instructions and coordinator contract describe delegation responsibilities but do not provide a dispatch mechanism. No specialist was dispatched. The source-based review in this document was performed by the Coordinator alone; it is **not** independent review and is not an approval by the named agents.

| Role | Requested lens | Actual participation / disposition |
|---|---|---|
| COORDINATOR | Scope, evidence, reconciliation, report | Performed source review and authored this report. |
| DATABASE_AGENT | Provisioning, actual-server identity, roles, permissions, closure | Not dispatched; **INDEPENDENT REVIEW OUTSTANDING**. |
| SECURITY_AGENT | Bypass, privilege escalation, destructive and filesystem threats | Not dispatched; **INDEPENDENT REVIEW OUTSTANDING**. |
| EVALUATION_AGENT | Runners, fixtures, cleanup/ingestion/SQL helpers, migration paths | Not dispatched; **INDEPENDENT REVIEW OUTSTANDING**. |
| TEST_AGENT | Determinism and acceptance evidence | Not dispatched; **INDEPENDENT REVIEW OUTSTANDING**. |
| VERIFIER | Independent source/evidence challenge | Not dispatched; **INDEPENDENT REVIEW OUTSTANDING**. |

The Step 1.6L Coordinator ownership exception expired with that step. No implementation-file ownership exception is asserted or used here. No claim below says unavailable agents approved, reviewed, or independently confirmed anything.

## 3. Reports and current sources inspected

Read Step 1.6M before Step 1.6N. Both reports exist at their requested paths. Step 1.6M’s verdict is blocked and PostgreSQL NO-GO; it identifies split configuration/maintenance identity, generic direct SQL/migration helpers, and filesystem cleanup as blockers. Step 1.6N exists and has 48 numbered rows B01–B48, acceptance IDs A1–A21, a state machine, filesystem proposal, work packages, and staged test plan. The 48 row IDs and uniqueness were checked from the actual document.

Current source inspected by reads, source searches, and standard-library AST parsing (without importing project modules):

- `backend/evaluation/isolation.py`; `backend/evaluation/experiments/run_*.py` entry-point, helper, engine/session, deletion, ingestion, and guard references, including `run_table_evidence_measurement.py`, `run_phase3d_evaluation.py`, `run_phase3e_integration.py`, `run_phase3e_validation.py`, the structure runners, and `run_dual_path_ablation.py`.
- `backend/tests/fixtures/integration_db.py`, `backend/tests/fixtures/e2e_config.py`, `backend/tests/fixtures/integration_http.py`, `backend/tests/fixtures/graph_data.py`; `backend/tests/integration/rag/test_real_e2e_validation.py` (the requested `backend/tests/test_real_e2e_validation.py` path does not exist).
- `backend/scripts/cleanup_path.py`, `cleanup_orphan_uploads.py`, `cleanup_smoke.py`, `db_check.py`, `start_server.py`, `setup_db.py`; `backend/storage/database.py`, `backend/storage/file_store.py`, `backend/config.py`, `backend/main.py`, `backend/migrations/env.py`.
- `backend/documents/routes.py`, `backend/documents/structure.py`, `backend/graph/service.py`; integration migration/structure test source including `backend/tests/integration/documents/test_table_row_migration.py`.
- Relevant database-free tests: `backend/tests/unit/evaluation/test_lifecycle_authorization.py`, `test_disposal_authorization_contract.py`, `test_function_cleanup_authorization.py`, `test_evaluation_isolation.py`, and `backend/tests/unit/scripts/test_cleanup_orphan_uploads.py`.
- Agent contracts for Coordinator, Database, Security, Evaluation, Test, and Verifier; `AGENTS.md`, `CONTEXT.md`, and project context.

Inspection was source-based. Some large reports were inspected by relevant sections/search and specific source windows rather than fully re-rendered in one read. Step 1.6N’s recorded broad scans are treated as historical documentation, not as scans independently reproduced in this task. **`HISTORICAL-TRANSCRIPT-ONLY`:** passing totals reported by earlier steps, including Step 1.6L, were not rerun here and are not fresh or independent evidence. Several generic `python`/`python3` commands were unavailable in the shell; the project interpreter was available for the bounded AST/check commands. No project imports were executed.

### Immediate bypass finding — source-verified, not executed

`backend/tests/fixtures/integration_db.py:302-337`, `psql_value(dsn, sql)`, accepts caller-supplied SQL and launches psql without an authorization check of its own; `backend/tests/fixtures/e2e_config.py:207-245`, `psql(sql)`, likewise executes caller SQL against its resolved configured database. The normal fixture lifecycle is blocked by create/disposal refusal, but a direct caller can bypass that entry-point refusal and submit SQL through these generic helpers, subject to the configured credential’s actual privileges. **Impact:** arbitrary SQL can reach a database selected by the helpers; whether DDL/destruction succeeds is unverified because privileges were not queried. **Containment recommendation:** keep the positive lifecycle blocked; do not call these helpers; owning agents should remove the arbitrary SQL interface or enforce an approved operation catalog and target-bound authorization inside the callable, then add direct-call no-I/O refusal tests. This is a confirmed source-level bypass of caller-level authorization, not evidence that this review executed SQL or that destructive privileges exist.

`backend/scripts/db_check.py:33` is a separate import-time connection side effect, but its source only executes `SELECT version()`; it is an unsafe unexpected connection path rather than a demonstrated destructive bypass. Do not import or run it for this review.

The earlier code-search/AST audit found all 48 inventory IDs but additional callable-coverage omissions. No test, runner, database module, or cleanup function was executed to verify these risks dynamically.

## 4. Step 1.6N inventory challenge and omissions

### 4.1 Inventory result

**`SOURCE-VERIFIED`:** B01–B48 all exist exactly once in Step 1.6N. Comparing them with current function names and source searches supports the main groups: evaluation entry points, the eight L cleanup helpers and four engine-taking `run_once` functions, fixture provisioning/psql/migration, E2E, two operational cleanup scripts, application storage/migration/startup, and scratch/file cleanup.

### 4.1 Inventory result

**`SOURCE-VERIFIED`:** B01–B48 all exist exactly once in Step 1.6N. Comparing them with current function names and source searches supports the main groups: evaluation entry points, the eight L cleanup helpers and four engine-taking `run_once` functions, fixture provisioning/psql/migration, E2E, two operational cleanup scripts, application storage/migration/startup, and scratch/file cleanup.

The inventory is a useful starting map, not a complete execution-boundary guarantee. It correctly admits that dynamic/aliased call discovery is incomplete, but several rows aggregate families or omit exact test helper callables. That prevents deterministic closure by row alone. The following are **additional source findings or inventory precision gaps**, not proof that any was executed against PostgreSQL:

| Finding | Exact current source entry point | Inventory gap / significance |
|---|---|---|
| O-1 | `backend/tests/integration/documents/test_table_row_persistence.py::_persist` (source call to `replace_document_structure`) | B46/B47 do not name this session-taking persistence helper. Include any future migration/integration writer boundary by exact callable and fixture/engine provenance. |
| O-2 | `backend/tests/integration/graph/test_graph_ingestion.py::test_rebuild_replaces_rather_than_appends`, `test_reprocessing_with_new_chunks_leaves_no_stale_edges`, and sibling `test_*` functions calling `replace_document_graph` | B47 names `graph_data` and generic API mutation tests, not these direct graph replacement calls. These are test-stage writers, not established production-DB access. |
| O-3 | `backend/tests/integration/graph/test_table_evidence_api.py::_seed`; `backend/tests/integration/graph/test_table_evidence_bands.py::_seed_document` and tests calling `replace_document_structure` | Direct supplied-session structure writes are not itemized in B47. Must be classified by actual test fixture/session, not assumed safe from filename. |
| O-4 | `backend/tests/integration/graph/test_graph_security.py::_foreign_document` | Direct `replace_document_graph` helper use is not individually named. Its intended security assertion does not establish the database target. |
| O-5 | `backend/tests/integration/graph/test_structure_reachability.py::persist_fixture` | Performs fixture persistence and temporary-file unlink; B48’s “integration graph/document temp unlink” is too broad to serve as a callable-level acceptance row. |
| O-6 | `backend/tests/e2e/browser/test_document_flow.py::main` and `test_embedding_flow.py::main` | Call `e2e_config.psql` directly and unlink temporary files. B45 names the broad browser family, but does not list these raw SQL/file effects and their target provenance. |
| O-7 | `backend/tests/e2e/browser/test_phase6_reliability.py::main` | Source inventory records a recursive `__pycache__` removal plus server process/API calls. B45’s broad E2E row does not identify this unlink/rmtree-like cleanup or verify its exact root. |
| O-8 | `backend/evaluation/experiments/run_phase3e_integration.py::main` and `run_phase3e_validation.py::main` | Multiple distinct `os.unlink` calls and API `client.delete` paths exist. B03/B04 classify temp deletion/API execution but do not enumerate exact call sites or partial-failure ordering. A single “X” effect hides several cleanup semantics. |
| O-9 | `backend/scripts/cleanup_orphan_uploads.py::_archive_orphans` and `run_sweep` | Archive creation/parent creation, file unlink, recursive enumeration and directory pruning are different writes. B39 groups them; acceptance should separately cover archive destination races, root replacement, files, and `rmdir`. |

These are “inventory omission/under-specification” findings: no assertion is made that the test paths reach a live database or that each call is independently exploitable. The work package must obtain the fixture and engine provenance for each and decide whether each belongs in a runtime policy or a test-only no-I/O boundary. Archived research trees and unscanned scripts remain outside any completeness claim; reactivation requires a fresh scoped scan.

### 4.2 Specific boundaries corroborated

- **`SOURCE-VERIFIED`:** `isolation.assert_disposal_authorized` / `assert_creation_authorized` refuse; `record_created_database` and `release_database_proof` refuse; `_proof_is_live` always returns false; `assert_cleanup_execution_authorized` unconditionally refuses without inspecting the resource. See `backend/evaluation/isolation.py:369-504`.
- **`SOURCE-VERIFIED`:** The fixture’s top-level provisioning and isolated fixture authorization precede reachability/existence probes (`backend/tests/fixtures/integration_db.py:519-596`), and the retained `_create_database`, `_drop_database`, and `migrate_to_head` operations remain lower-level callable code (`:350-441`). This blocks ordinary intended fixture execution today, not arbitrary callers who invoke lower-level helpers by other means.
- **`SOURCE-VERIFIED`:** `run_full_validation` refuses before SQLAlchemy imports/engine creation, and its cleanup guard precedes the unscoped `DELETE FROM` at `backend/tests/integration/rag/test_real_e2e_validation.py:84-132`. The two standalone branches still route through refusals (`:526-538`). Existing source ordering is a current denial, not connected identity evidence.
- **`SOURCE-VERIFIED`:** All eight L helpers and the four alternate `run_once` functions still begin with `assert_cleanup_execution_authorized`; this policy always denies. It is not a sandbox for every caller-supplied session passed to ingestion or generic SQL APIs.
- **`SOURCE-VERIFIED`:** Table-measurement `_resolve_database_url` uses an explicit environment target, mutates `DATABASE_URL`, clears settings cache and imports `storage.database` before `amain` disposal refusal (`backend/evaluation/experiments/run_table_evidence_measurement.py:243-286, 1098-1118`). Engine construction is not proof of a connection; the ordering does mean “authorization before all imports/configuration effects” cannot be claimed.
- **`SOURCE-VERIFIED`:** `backend/scripts/db_check.py` ends with module-scope `asyncio.run(main())` (`:16-33`); importing it reaches `engine.connect()` and `SELECT version()` absent a failing connection. `storage.database` creates a module-level lazy engine (`backend/storage/database.py:43-47`). A lazy engine object is distinct from a completed server connection.
- **`SOURCE-VERIFIED`:** `backend/migrations/env.py:48-54` catches settings/translation exceptions and retains configured Alembic URL; online migration opens a connection (`:81-99`). `backend/main.py:44-79` invokes migrations in application lifespan. The runtime branch and target were not exercised.

## 5. Lifecycle authority, target resolution, and database isolation

### 5.1 External lifecycle authority

| Review question | Classification and conclusion |
|---|---|
| Who operates/controls ELA? | `DESIGN-PROPOSAL` identifies a local operator and separate OS identity but does not identify the accountable organization/person, host lifecycle, credential custodian, incident owner, journal backup owner, key rotation/recovery authority, or separation-of-duties approval. **Unresolved; operator decision required.** |
| How is a run authorized? | `DESIGN-PROPOSAL` offers admin ticket, caller/action/target/expiry and an immutable spec. It does not define the ticket issuer/authentication, binding to a human/service identity, approval quorum, ticket revocation channel, or exact canonical signed payload/schema and version negotiation. A ticket name/reference alone is not enforceable. |
| Separate from application permissions? | `DESIGN-PROPOSAL` proposes dedicated per-run cluster/network/storage, isolated runner identity, provisioner/migrator/runtime/inspector roles and no app route. This is not deployed or backed by grants/HBA/network evidence. `UNVERIFIED`. |
| Forge/replay/reuse authorization? | `DESIGN-PROPOSAL` correctly rejects Python proof objects and calls for server-side state, caller binding, expiry, generation and terminal tombstones. Token format, nonce/idempotency, caller authentication, concurrency semantics and revocation transaction are not fully specified; prevention is not demonstrable. |
| Reuse after closure? | Proposed CLOSED tombstone/generation refusal is directionally adequate. Durable storage, retention, restore-from-backup behavior, journal rollback/replay protection and authority failover are unspecified. `DESIGN-PROPOSAL`; unresolved until these are acceptance-tested. |
| Crash between create/disposal? | The proposal explicitly says durable create intent before DDL and quarantine on ambiguous acknowledgment, and favors leaking over uncertain drop. It does not define a reconciler’s evidence/decision table across every crash window, journal/server disagreement, concurrent operator action, or backup recovery. Mitigation proposed, not demonstrated. |
| Compromised runner reaching application DB by another path? | Dedicated allocation and no app route are proposals. Current source has independent storage/settings, subprocess/psql, API, and startup paths. If worker receives a raw writer DSN/credential, arbitrary SQL within that DB remains possible; N acknowledges this residual. No OS/network evidence proves that app DB access is impossible. |

**Assessment:** N is a good threat-model direction, not a fully specified authority interface ready to enable. It needs operator ownership, authenticated approval and recovery rules, exact identity attestation semantics, and a formal privilege/network matrix before any positive lifecycle task.

### 5.2 Target resolution, actual server identity, pooling, permissions

- **Configuration is not connection identity (`SOURCE-VERIFIED`).** `database_identity()` and `assert_engine_matches_target()` compare URL/configured `engine.url` only (`backend/evaluation/isolation.py:146-167, 504-522`). They do not authenticate the remote server or inspect the server-side authenticated role.
- **Fixture target splicing (`SOURCE-VERIFIED`).** `integration_db.psql_value(dsn, sql)` obtains host/port/user/password from `e2e_config.postgres()` but the database name from the passed DSN (`backend/tests/fixtures/integration_db.py:302-337`). `e2e_config.database_url()` resolves `DOCUMIND_E2E_DATABASE_URL`, then `backend/.env`, then ambient `DATABASE_URL` (`backend/tests/fixtures/e2e_config.py:135-150`). The SQL endpoint and database name can therefore come from different configurations. Initial `assert_isolated_target()`’s host/port comparison does not bind later re-resolution to a held maintenance connection.
- **Different resolver precedence (`SOURCE-VERIFIED`).** Central isolation reads `backend/.env` before application settings; E2E selects an E2E override first; Pydantic application settings accept environment over `.env`; storage caches a module-level engine. A runner can validate one resolved URL yet a fixture/subprocess/application reader use another. N’s immutable manifest/reject-conflicts plan is a proposed correction, not current behavior.
- **Server/port/database/role/effective grants (`UNVERIFIED`).** No controlled PostgreSQL connection was allowed. No actual host/port, `current_database()`, database OID, `session_user`, `current_user`, TLS endpoint, grant, role membership, ownership, `CONNECT`, `CREATE`, `TEMP`, `SET ROLE`, `BYPASSRLS`, HBA, or cross-database reachability has been measured. Name and configured host checks cannot establish these.
- **Pool/reconnect (`UNVERIFIED`).** Existing engine checks are pre-connection configured URL checks. They do not bind each physical connection/reconnect, server failover/proxy target, role/session state, or pool checkout to an ELA lease. N proposes per-checkout validation but no implementation/evidence exists.
- **Application protection (`UNVERIFIED`).** Source rejects a same database name as a necessary guard, but actual application DB identity/credentials and evaluation role grants are unknown. No claim that eval credentials lack privileges on the application DB can be made.
- **Create/dispose privilege (`SOURCE-VERIFIED` / `UNVERIFIED`).** Repository guards currently refuse all positive creation/drop paths. Whether a PostgreSQL principal has CREATEDB, ownership, superuser or other rights is operational and unverified. N’s restricted roles are not provisioned.

`backend/tests/fixtures/integration_db.py:302-337` also passes SQL to psql by argv, copies ambient environment, and does not supply `-X`/`ON_ERROR_STOP`; `database_exists()` interpolates a name into a literal (`:340-347`), and `_create_database`/`_drop_database` interpolate quoted identifiers (`:350-390`). These retained callable surfaces are blocked in the intended fixture flow now, but unsafe to positively enable without redesign and direct-call authorization.

## 6. Filesystem cleanup adversarial review

### `cleanup_orphan_uploads.py`

- **Root/descendant symlinks:** `forbid_symlink_roots()` compares `root.resolve(strict=False)` with the same resolved value (`backend/scripts/cleanup_path.py:37-51`), so it is not an effective symlink-root discriminator. `Path.resolve`/string-prefix containment is not an atomic no-follow walk. Descendant links, junctions/reparse points, mounts, hard links, and file identity are not governed by a held directory handle.
- **Traversal/absolute paths:** `_key()` normalizes separators and strips boundary slashes but does not itself reject `..`, drive/UNC/device paths or alternate stream syntax (`cleanup_orphan_uploads.py:47-64`). Stored references are compared by a relative key; the deletion candidate originates from recursive enumeration, but no immutable file identity or no-follow capability binds it at deletion time. This is not proof of an outside-root deletion in the review.
- **TOCTOU/replacement:** containment and reference status are checked, then `stat()` and `unlink()` occur later (`:198-211`). A file/root/reference can change between checks. Directory pruning separately re-runs `rglob`, `is_dir`, `iterdir`, and `rmdir` (`:216-228`) without a stable root handle or plan digest. No writer fence prevents a new DB reference after the reference snapshot.
- **Missing/replaced roots:** nonexistent root returns success/no-op (`:152-155`); the root is not tied to an approved file/volume identity, and may be replaced after scan. Symlink guard occurs only immediately before unlink loop and is not a race-free guarantee.
- **Archive/dry-run/interruption:** dry-run is the default and archive CRC/count verification is useful defense-in-depth. `--delete --yes` is a destructive flag, not authorization. Archive parent creation and `ZipFile(..., "w")` happen before deletion (`:91-128`) and have a check-then-create race; an interrupted archive/delete/prune sequence has no durable plan/journal or recovery protocol. Archive CRC proves archive integrity, not source identity or authorization.
- **Database reference set:** `_referenced_keys()` reads current application DB; if that read fails, sweep aborts (good fail-closed behavior). It is still a time-bounded snapshot, not a lock against concurrent upload/reference changes.

### `cleanup_smoke.py`

`_resolve_stored_path()` accepts an absolute path or any existing relative path without proving containment (`backend/scripts/cleanup_smoke.py:47-62`). `cleanup()` deletes files before DB rows, then commits, then `shutil.rmtree`s an empty per-user directory (`:65-137`). Confirmation/`--yes` is not an authorization boundary. No transaction can atomically cover DB+filesystem; failures can leave deleted files with live rows, or committed rows with files remaining. The application `file_store.delete_upload()` also unlinks the supplied path without a root capability (`backend/storage/file_store.py:53-62`).

**Conclusion:** Dry-run, prompts, resolved paths, and archive validation do not demonstrate containment or race safety. N’s no-follow/handle-based/platform fail-closed approach is only a proposal. POSIX and Windows implementations, junction/reparse handling, hard-link policy, network filesystem support, archive exclusive creation, recovery journal, and test permissions remain unresolved. Do not execute either cleanup script or create filesystem probes under project/upload roots.

## 7. Test sufficiency

Step 1.6N’s A1–A21 and T0–T6 are a substantial test outline, but they are not yet deterministic acceptance specifications for every control. “Controlled PostgreSQL,” “signed/admin-recorded approval,” “verified allocation identity,” “independent review,” and “supported filesystem” need named fixture formats, exact failure injection points, expected evidence schemas, cleanup of the test environment, and explicit permissions. Database-free tests must remain described as refusal/source-order evidence only.

| Control/property | Positive test (only after separate permission) | Negative/bypass test | Required environment and acceptance evidence | Limitations |
|---|---|---|---|---|
| Authority authentication, action/target/expiry binding, replay/closure | ELA accepts one valid authenticated approval and one authorized transition; returns a server-issued run generation | forged handle, different caller/action/target, expiry, revoked ticket, copied token, concurrent replay, CLOSED handle, journal rollback all refuse before SQL | Offline protocol/state fake with I/O tripwires; then separately approved authority integration. Record authenticated caller, approval digest, state/generation transitions, operation audit codes | Offline tests cannot prove host ACL, key custody or durable storage. |
| Create intent, successful-create receipt, crash quarantine | Dedicated test cluster: unique authorized name created once; receipt binds allocation/generation/OID and only then admits verification | existing-name race, killed coordinator before/after DDL/ack, lost journal/server response, alternate creator, repeated idempotency key refuse/quarantine without adopting/dropping | Dedicated disposable cluster; fault injection at each DDL/journal edge; before/after catalog and journal snapshots, redacted command results, quarantine state | Cannot assert PostgreSQL DDL/crash semantics from unit tests. |
| Target resolution and actual connection identity | Deliberately configured manifest connects to the intended approved allocation; same held connection reports expected DB OID/name, role/session role, TLS/allocation attestation | conflicting env/CLI/.env, DSN/config split, alias/redirect/proxy, different DB/role/cluster, reconnect/failover, `SET ROLE`, pool-state mutation refuse before writes | Test endpoint plus allocation identity, TLS trust, pool/reconnect injection; immutable spec digest and sanitized actual-connection evidence | SQL identity values alone do not authenticate infrastructure; mapping/attestation must be specified. |
| Least privilege/application DB isolation | On a separately authorized isolated cluster, runtime role performs only approved DML; inspector performs approved reads; ELA admin provisions | runtime attempts CREATE/DROP/DDL, SET ROLE, connect to application DB, cross-database read, role inheritance/escalation, PUBLIC grants, no-TLS/mismatched endpoint | Actual grant catalog, role membership, HBA/network policy, authentication and negative connection results; before/after app-database sentinel evidence only if operator separately permits | No current PostgreSQL proof; app-access denial cannot be inferred from source. |
| Runner/helper and caller-supplied-session boundary | Approved run invokes every catalogued helper through the authority-bound session; retained row scoping is verified with owned and foreign records | call cleanup helper, `run_once`, ingest, raw SQL, fixture psql, API purge, or migration function directly with a production/forged session/engine/URL; assert zero DB calls | First static/no-I/O poison-session tests; then authorized dedicated PG integration with recording executor, foreign-row sentinels, SQL/audit trace, exact transaction/backend ID | Python wrappers alone do not stop same-process code with raw credentials. |
| Migration/startup/import effects | Explicit migration worker applies one approved head on the authorized cluster; imports stay inert | direct Alembic CLI, downgrade, fallback URL, env mismatch, import `db_check`, application lifespan, missing authority; assert no socket/process/DDL before refusal | Offline import tripwires and child env inspection; then separately approved disposable cluster migration logs, actual target/role/revision and schema diff | `alembic heads`/AST/unit checks do not prove connection or DDL target. Production auto-migration change needs separate owner decision. |
| Filesystem root/plan/execute | In approved isolated sandbox, plan exact files, review digest, remove only unchanged authorized file IDs, verify outside sentinels | symlink/junction/descendant, traversal/absolute/UNC/device/ADS, hardlink, root swap, file replacement, reference race, archive collision, missing root, replay/expired plan, unsupported platform; verify refusal | Platform-specific POSIX and Windows sandbox/ACL/volume tests; exact plan digest, file IDs, count/bytes, audit log, before/after hashes and recovery after injected interruption | Do not probe repo/upload paths. Sandbox tests do not establish guarantees on production/network filesystems. |
| E2E and API boundary | Authorized worker/API target chain writes only its isolated run and artifacts | wrong base URL, ambient localhost app, direct script execution, reused token/tenant, model/schema unavailable, API delete to other run; assert no mutation or honest failure | Isolated server/network/database/scratch; allocation identity at server and DB, request logs and sentinel rows/files | Model/E2E success cannot establish cluster permissions unless separately evidenced. |

**Test decision:** database-free coverage can be implemented as a bounded guard/inventory task. It is necessary but not sufficient for any real isolation or permission claim. Do not convert a negative test to a mocked positive lifecycle and report that as PostgreSQL evidence.

## 8. Twelve mandatory adversarial scenarios

Outcome labels answer whether **Step 1.6N’s proposed architecture** demonstrably prevents the scenario. “Current refusal” notes the present source behavior; no attack was executed.

| # | Scenario and source evidence | Outcome |
|---|---|---|
| 1 | Supplied DSN names one DB but fixture configuration points at another server. `integration_db.psql_value` combines passed DSN database name with `e2e_config` host/port/user (`backend/tests/fixtures/integration_db.py:302-337`). | **MERELY PROPOSES MITIGATION.** Immutable manifest/no splicing in N addresses the shape, but no implemented adapter or test proves it. Current fixture’s initial create gate refuses its normal path. |
| 2 | Approved database name matches, actual connected database differs. Configured URL identity does not equal connected-server identity (`isolation.py:146-167, 504-522`). | **UNRESOLVED.** N proposes connection validation and allocation attestation, but the attestation/mapping protocol and real-connection evidence are not implemented. |
| 3 | Authorization artifact replayed after lifecycle closure. | **MERELY PROPOSES MITIGATION.** CLOSED tombstones, generation and server-side checks are proposed; signing/caller binding, journal recovery and replay tests are unspecified. Current Python proofs cannot authorize because all positive paths refuse. |
| 4 | Process crashes after database create and before cleanup. | **MERELY PROPOSES MITIGATION.** Intent journaling and QUARANTINED state are proposed; no current create is permitted. Crash recovery/reconciliation and dedicated cluster containment are not operationally defined or tested. |
| 5 | Runner bypasses normal entry point and calls lower-level destructive helper. | **UNRESOLVED.** L’s eight cleanup helpers/four `run_once` entry points currently unconditionally refuse; fixture `psql_value`, `e2e_config.psql`, and `migrate_to_head` are lower-level callables without their own equivalent lifecycle authorization. N proposes replacing arbitrary SQL and mediating capabilities but is not implemented. |
| 6 | Ingestion helper receives a production session from caller. | **UNRESOLVED.** `run_table_evidence_measurement.py:350-435` `ingest_demo(db, ...)` flushes, replaces structure/graph, and commits a caller session; several `ingest_corpus(db, ...)` functions do likewise. Entry guard does not protect a direct call. N identifies this class and proposes WRITE_DATA, but cannot establish provenance of an arbitrary session. |
| 7 | Migration helper called directly without lifecycle authorization. | **UNRESOLVED.** `integration_db.migrate_to_head(dsn)` (`:429-441`) runs Alembic without its own lifecycle grant; `migrations/env.py` online path connects and has URL fallback. N proposes one-use migration authority; no current helper-local gate. |
| 8 | Imported module connects before guard. | **UNRESOLVED.** `scripts/db_check.py:33` runs `asyncio.run(main())` at module scope; `main()` calls `engine.connect()` (`:16-20`). N notes it and proposes removing import side effects. Current guarded evaluation paths do not make arbitrary `db_check` imports harmless. |
| 9 | Cleanup root or descendant is symlink. | **MERELY PROPOSES MITIGATION.** Current root helper is ineffective equality (`cleanup_path.py:37-51`); per-file resolve containment is not no-follow authority. N proposes handle-based traversal and platform block, not implemented. No cleanup ran. |
| 10 | Path replaced between validation and deletion. | **UNRESOLVED.** `cleanup_orphan_uploads.run_sweep` checks then later stats/unlinks (`:198-211`) and separately prunes directories (`:216-228`); no held handle/identity fence. N proposes one but has no platform implementation or race test. |
| 11 | Evaluation credentials unexpectedly have privileges on application DB. | **UNRESOLVED.** No grants or live connections were inspected. Dedicated cluster/no app route and separate roles in N are only proposals. The repository cannot demonstrate credential scope. |
| 12 | Connection reconnects to different target after initial verification. | **UNRESOLVED.** Current check reads configured `engine.url`; it does not attest each pooled physical connection or reconnect. N proposes checkout/reconnect validation, but no connection-bound lease/runtime test exists. |

## 9. Required design changes and operator decisions

### Required design changes before positive lifecycle work

1. **Name and assign ELA ownership:** operator/service owner, independent approver, credential/key/journal custody, patch/backup/restore/recovery, audit retention, incident response, and authority compromise assumptions. Define authenticated caller identity and canonical approval schema/version, not just a ticket reference.
2. **Make connection attestation implementable:** choose supported PostgreSQL endpoint/proxy/deployment and explain how TLS trust, allocation identity/generation, cluster/server identity, database OID, effective/session role, port translation, pooling, and reconnect are verified on the same physical connection used for the authorized operation. Document which parts require an admin attestation rather than SQL claims.
3. **Specify all privileges:** role-to-action matrix; role grants/inheritance; app DB denial; provisioner versus extension setup; migration owner; runtime DML, inspector, API worker, TEMP/PUBLIC access; connection/network/HBA policy. Operator must allocate a dedicated cluster and separately approve measuring those facts.
4. **Close direct bypasses before any positive capability:** every fixture SQL helper, migration helper, ingestion/session-taking helper, run_once function, API target, application startup path, and direct script/import path must either use the authority executor or stay denied. Raw writer credentials in Python remain arbitrary DML authority and must be explicitly accepted as residual risk or removed from the process.
5. **Specify migration compatibility:** plain Alembic CLI/offline/online behavior, URL fallback, `main.lifespan` auto-migration, migration ordering and extension privileges, and what production startup may do must have a Database/Backend owner decision. No evaluation migration may infer authorization from `DATABASE_URL`.
6. **Define filesystem adapters and recovery:** choose POSIX/Windows primitives and supported filesystems; held-root and file identity; junction/reparse/mount/hard-link policy; root replacement; archive exclusive creation; write fence; DB reference snapshot protocol; interrupted deletion journal/quarantine. Unsupported/unknown must remain blocked.
7. **Turn the inventory into a versioned source map:** exact path, callable/line, direct caller, input resource provenance, effect, current gate order, permitted test stage, owner. Add O-1–O-9. Do not certify archived or dynamically loaded code without a scoped rescan.

### Unresolved operator decisions

- Who owns/runs ELA and the dedicated cluster, on which host/account, and who may approve a run or reconcile quarantine?
- Can a dedicated throwaway cluster be allocated with no production route, shared credentials, or upload mounts? What is its data retention/erasure policy?
- Which TLS CA/identity, proxy mapping, and cluster allocation evidence may ELA read, and with what privilege?
- Which migration/admin role installs pgvector, and is production startup auto-migration to remain enabled independently?
- Which platforms/filesystems must support cleanup? Is unsupported OS a hard no-delete outcome?
- What is the policy for quarantined resources and interrupted file cleanup? Prefer preservation over guessed deletion.
- Who approves the separate future permissions for connect/inspect, create, migrate, DML, row cleanup, database drop, and filesystem delete?

## 10. Component decision matrix

The status is component-specific. No row approves PostgreSQL verification. “Independent review outstanding” is not collapsed into a positive readiness decision.

| Component | Decision | Evidence / condition |
|---|---|---|
| Existing fail-closed source boundaries and a source-only inventory/test task | **READY FOR A BOUNDED IMPLEMENTATION TASK** | A bounded task may add precise static coverage and O-1–O-9 without relaxing guards, importing database modules, or running tests that connect. This is not approval for a working lifecycle. |
| ELA accountable ownership, authentication and approval workflow | **BLOCKED BY OPERATOR DECISION** | Operator, custodian, approver and recovery roles are not named. |
| ELA protocol, journal durability, replay/revocation and crash reconciler | **READY AFTER SPECIFIED DESIGN CHANGE** | Define authenticated principal, canonical approval/artifact schema, durable journal restore/replay rules and exhaustive crash-window reconciliation before implementation. |
| Immutable target resolver/fixture adapter | **READY AFTER SPECIFIED DESIGN CHANGE** | Resolve endpoint, database, role, TLS and maintenance target from one approved revision; eliminate DSN/config field splicing and re-resolution. Test conflicting overrides. |
| Actual server/connection identity and pool/reconnect binding | **BLOCKED BY MISSING ARCHITECTURE** | N lists fields but does not settle attestation authority, proxy/port mapping, cloned cluster identity, physical connection leasing, or failure semantics. |
| Restricted PostgreSQL roles/network and application-database denial | **BLOCKED BY OPERATOR DECISION** | Requires approved dedicated allocation and separately authorized actual grant/network inspection; no live facts exist. |
| Runner, lower-level SQL, migration, API, and caller-session enforcement | **READY AFTER SPECIFIED DESIGN CHANGE** | Decide which operations run in ELA vs worker and prevent raw helper/session bypass. N must specify session provenance; all current refusals remain until reviewed. |
| Application startup and migration boundary | **READY AFTER SPECIFIED DESIGN CHANGE** | Reconcile `migrations/env.py` fallback and `main.lifespan` auto-upgrade with separately owned production behavior. |
| Filesystem cleanup authority and platform adapters | **BLOCKED BY MISSING ARCHITECTURE** | Exact POSIX/Windows no-follow API, hard links, writer fence, archive race, reference race and crash recovery are not selected. |
| Deterministic controlled PostgreSQL/E2E positive tests | **BLOCKED BY OPERATOR DECISION** | No approved cluster, permissions, test data, or connection authorization. Offline tests do not substitute. |
| Filesystem positive destructive tests | **BLOCKED BY OPERATOR DECISION** | User forbids cleanup execution/test artifact creation in project/upload roots; no separately authorized sandbox exists. |
| Independent Database/Security/Evaluation/Test/Verifier decisions | **INDEPENDENT REVIEW OUTSTANDING** | Actual dispatch unavailable; Coordinator-only review cannot satisfy this gate. |

**Overall answer to the objective:** no approval to proceed with broad bounded implementation of positive safeguards yet. Only source-only inventory/test work that maintains unconditional refusal may proceed without resolving the operator decisions. A later positive implementation task needs a revised approved design and actual independent review.

## 11. Bounded implementation sequence recommended by this review

1. **Coordinator, documentation-only design closure:** appoint the ELA operator/security owner and database allocation owner; record approval, identity-attestation, journal restore, role matrix, and platform support decisions. Obtain actual Database and Security review before authorizing a positive lifecycle.
2. **EVALUATION_AGENT + TEST_AGENT, source-only inventory closure:** add exact callables O-1–O-9 and every direct session/engine/SQL/file operation to the source map; establish AST/search regression coverage with import/socket/process tripwires. Preserve current refusal; no database, cleanup, or runner execution.
3. **DATABASE_AGENT + SECURITY_AGENT, architecture contract:** specify authenticated approval/artifact, journal transaction/recovery, manifest fields, attestation and role/network matrix; independently review it. Stop if a dedicated allocation or trustworthy connection identity cannot be provided.
4. **DATABASE_AGENT + TEST_AGENT, fail-closed resolver/SQL/migration adapter:** only after approved contract; remove configuration splicing/fallback and arbitrary SQL bypass while retaining default denial; test conflicting DSN/env/settings and direct-call cases without network.
5. **EVALUATION_AGENT + TEST_AGENT + BACKEND_AGENT, execution boundaries:** route or refuse direct ingestion, run_once, API, migration, startup and cleanup paths. Use separately scoped sessions/executors; no process gets broader credentials than the reviewed threat model. Test helper bypasses offline first.
6. **DATABASE_AGENT + BACKEND_AGENT + SECURITY_AGENT, filesystem contract:** choose supported OS APIs; default deny until race/no-follow/root identity and recovery tests pass in a user-approved external sandbox. Do not use application uploads or project roots for positive destructive tests.
7. **VERIFIER plus independent Database/Security reviewers:** audit changes against the exact inventory and evidence, report unresolved claims. Only then may the Coordinator request separate, explicit authorization for controlled infrastructure tests. Each database operation class requires its own authorization; no approval is implied here.

No sequence step is permission to connect, create/drop/migrate, run evaluation/E2E, or clean files.

## 12. Prerequisites for any future PostgreSQL verification

All are mandatory; none is satisfied by this review:

- Independent Database, Security, Evaluation, Test, and Verifier reviews actually occur and are attributable. Missing dispatch means outstanding, not accepted.
- Operator approves ELA ownership/authentication, dedicated per-run cluster, data retention, quarantine and recovery.
- Reviewed immutable target/maintenance manifest and actual connection/allocation attestation are implemented; target/server/DB/role/TLS/pool/reconnect mismatch fails before mutation.
- Separate least-privilege provisioner, migrator, runtime, cleanup and inspector roles are provisioned and verified; application DB/network/credential access is independently denied and evidenced.
- Direct SQL, fixture, migration, ingestion, API, startup/import and lower-level engine/session paths are either mediated or fail closed; O-1–O-9 and all active paths are closed in an AST/source inventory.
- Durable lifecycle receipt, CLOSED replay protection, create/drop uncertainty handling, quarantine/reconciliation, in-flight operation fencing and failure injection are implemented and independently checked.
- Offline tests pass without project-module connection side effects. These only demonstrate code-level behavior, not PostgreSQL isolation.
- Operator separately approves each exact stage: connect/inspect, create, migrate, runner DML, row cleanup, drop, filesystem activity; with environment identity, commands, stop rules and recovery plan.
- Controlled test evidence records the actual server/allocation, DB OID/name, current/session roles, TLS, effective grants, pool/reconnect behavior, migration revision, before/after unrelated sentinels, journal state and residual resources. Redact all secrets.
- Filesystem authorization/test sandbox and platform-specific containment evidence are separate prerequisites; PostgreSQL approval does not authorize file cleanup.

Until all prerequisites are reviewed and separately approved, PostgreSQL remains **NO-GO**.

## 13. Safety constraints and verification record

- No implementation, test, fixture, migration, configuration, or cleanup file was edited.
- No PostgreSQL, SQLite, or other database was contacted. No runner, migration, E2E, cleanup command, or destructive test was executed.
- No cleanup script was executed and no test files were created in repository/upload/cleanup directories.
- No reset, stash, clean, revert, rename, overwrite, staging, commit, or push occurred. No secret value or `.env` content was read or included.
- Tests were **not run**. The prior Step 1.6L test results quoted in M/N remain historical, not rerun evidence. The project Python interpreter was used only for static AST/report/path checks; source modules were not imported.
- A toolchain limitation was encountered: shell `python` and `python3` were unavailable; `backend/venv/Scripts/python.exe` worked. Some code-search calls also failed when the vendored ripgrep executable was unavailable. Grep, bounded reads, AST parsing, and source references were used instead; these failures are not reported as passing checks.

## 14. Final preservation and Git-state verification

At task start, before creating this report:

- HEAD: `6baaa2a0773df66e5fb26814afbe67647fb43435`.
- Expanded `git status --porcelain=v1 --untracked-files=all`: 1,140 pre-existing entries. The exact status listing was saved outside the repository at `/tmp/step16o-status-before.txt`.
- Step 1.6M and 1.6N reports existed; this Step 1.6O report did not.

After report creation, compare the complete expanded status lines to the saved initial listing. Acceptance requires exactly one additional status entry, `?? backend/architecture/STEP1_6O_INDEPENDENT_ARCHITECTURE_REVIEW_2026-10-12.md`, no missing/changed prior status entry, unchanged HEAD, and no implementation-file status change. This report does not claim a byte-for-byte hash baseline for all pre-existing untracked files; none was captured at task start. Preservation evidence is the saved complete status/path set plus the fact that all task operations on existing sources were reads/searches/AST parsing.

**Final verdict:** documentation review complete; architecture approval **not granted**. Independent reviews, specified operator decisions, and implementation readiness for a positive lifecycle remain outstanding. **PostgreSQL: NO-GO.**