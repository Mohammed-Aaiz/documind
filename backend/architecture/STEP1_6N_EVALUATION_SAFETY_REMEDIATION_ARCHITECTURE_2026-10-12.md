# Step 1.6N — Evaluation Safety Remediation Architecture and Acceptance Plan

Date: 2026-10-12

## 1. Executive decision and claim classification

**DESIGN-PROPOSAL:** Adopt an isolated evaluation environment controlled by an out-of-process lifecycle authority, one immutable target contract, restricted database roles, operation-level enforcement, and a separately authorized filesystem executor. No implementation or positive authorization is introduced by this document.

**BLOCKED:** PostgreSQL verification remains **NO-GO**. This plan is implementation-ready in its interfaces, transitions, dependencies and acceptance requirements, but implementation, infrastructure allocation and operational execution each require separate approval. Design completion is not design approval or PostgreSQL readiness.

Claim labels apply to every paragraph/table within a section unless overridden:

- `SOURCE-VERIFIED`: observed current source or filesystem/Git fact; not executed database behavior.
- `HISTORICAL-TRANSCRIPT-ONLY`: prior execution/approval claims not independently repeated in this task, including recorded test totals.
- `DESIGN-PROPOSAL`: proposed, not implemented or approved safeguards, interfaces, tests and procedures.
- `UNVERIFIED`: facts requiring independent or operational evidence.
- `BLOCKED`: must not execute/enable until stated dependencies and approvals exist.

**SOURCE-VERIFIED:** Available runtime tools expose no specialist dispatch mechanism, so no valid dispatch call can be made. Capability inspection was the dispatch availability attempt; no fictional command or separate agent execution is claimed. Coordinator alone performed source review and documentation. Architecture documents are already Coordinator-owned; no extension of the Step 1.6L implementation exception is needed or made.

| Assigned role | Responsibility in proposed plan | Actual execution in 1.6N |
| --- | --- | --- |
| COORDINATOR | orchestration, consolidation, approval gates, report | Coordinator review/documentation performed |
| DATABASE_AGENT | lifecycle/identity/permissions/maintenance design | unavailable; Coordinator authored proposal, independent review outstanding |
| SECURITY_AGENT | capabilities, SQL/migration bypasses, filesystem threat review | unavailable; independent review outstanding |
| EVALUATION_AGENT | runner/helper mapping and adapter design | unavailable; independent review outstanding |
| TEST_AGENT | no-I/O/controlled-runtime test architecture | unavailable; independent review outstanding |
| VERIFIER | independent contradiction/omission review | unavailable; independent verification outstanding |

## 2. Scope, inspected files and baseline — SOURCE-VERIFIED

Read Step 1.6M first. Read/AST-parsed current source rather than treating reports as authority. Core inspected files:

- `backend/architecture/STEP1_6M_READ_ONLY_POSTGRESQL_READINESS_REVIEW_2026-10-12.md`, substantive sections of H/I/J/K/L reports at their actual architecture paths; K's completion-review addendum, not just its initial summary.
- `backend/evaluation/isolation.py`; `backend/tests/fixtures/integration_db.py`, `e2e_config.py`; `backend/storage/database.py`, `file_store.py`; `backend/migrations/env.py` and migration version function ASTs; `backend/config.py` source (not settings resolution).
- All `backend/evaluation/experiments/run_*.py`: dual_path_ablation, phase3d_evaluation, phase3d_upload_integration, phase3e_integration, phase3e_validation, phase3f_evaluation, phase4b_evaluation, phase4c_diagnostics, structure_element_measurement, structure_rrf_calibration, structure_confirmation, table_evidence_measurement.
- `backend/scripts/cleanup_smoke.py`, `cleanup_orphan_uploads.py`, `cleanup_path.py`, `setup_db.py`, `create_test_user.py`, `db_check.py`, `start_server.py`; `backend/main.py` migration/lifespan functions; parser/voice temporary cleanup source windows.
- Actual E2E validation `backend/tests/integration/rag/test_real_e2e_validation.py`; E2E browser source ASTs; integration document migration source ASTs; fixture graph_data source AST; relevant evaluation-test AST inventory and Step 1.6L boundary-test source from prior source review context.
- Scan roots: `backend/evaluation`, `backend/scripts`, `backend/tests/fixtures`, `backend/storage`, `backend/migrations` (66 Python files parsed in first scanner); supplemental E2E/integration AST scans. Raw discovered function/call lists are appended as an inventory cross-check.

Path corrections: `backend/tests/test_real_e2e_validation.py` is absent; use the integration/rag path above. Repo-root `scripts/cleanup_smoke.py` and `scripts/cleanup_orphan_uploads.py` are absent; actual scripts are under `backend/scripts/`. H–L report paths exist. The broad text search also returned ignored third-party GPU-venv matches; those are not project boundary evidence and are excluded from this inventory. Archived phase research/third-party packages are not silently certified; any reactivation requires another scoped scan. Application HTTP mutation handlers are transitive dependencies, not evaluation authorities.

Initial HEAD: `6baaa2a0773df66e5fb26814afbe67647fb43435`; expanded initial Git status: 1139 entries. Full status/path snapshots and final comparison are appended. SHA-256 baseline captured 914 existing regular, nonsecret, nonruntime files identified by Git paths. Excluded secret-named env files, symlinks, models/venvs/uploads/node_modules/dist and ignored runtime assets. No `.env` content was read. Hashes provide bounded preservation evidence, not proof about excluded files.

## 3. Current findings and blocker-to-acceptance map

The following findings are `SOURCE-VERIFIED`. Risk severity is a review assessment, not a demonstrated attack.

| Finding | Current evidence | Proposed remedy | Acceptance ID / owners |
| --- | --- | --- | --- |
| F-M1 positive authority absent | isolation: create/disposal/evidence/release refuse; proof never live; no external issuer | authority/state machine, exclusive provisioning credentials and durable journal, section 4 | A1–A5; Coordinator, DATABASE_AGENT, EVALUATION_AGENT |
| F-M2 split target/precedence | integration_db.psql_value uses DSN database with e2e_config host/port/credentials; repeated resolution; app/env/fixture precedence differs | one signed nonsecret manifest + secret references; immutable TargetSpec for all consumers; no field-splicing/fallback | A6–A8; DATABASE_AGENT, TEST_AGENT, EVALUATION_AGENT |
| F-M3 unsafe execution assumptions | interpolated database literals/identifiers; psql inherits env, lacks -X/ON_ERROR_STOP; migrations/env.py fallback on configuration exception | typed admin operations, safe SQL composition, sanitized child env, explicit migration target and acknowledgment | A9–A11; DATABASE_AGENT, TEST_AGENT, SECURITY_AGENT |
| F-M4 arbitrary execution surfaces | fixture psql_value, e2e psql, migrate_to_head and API purge lack local lifecycle gate | remove arbitrary-SQL bypass, authority-mediated operation catalog and verified connection factory | A12–A14; TEST_AGENT, DATABASE_AGENT, EVALUATION_AGENT |
| F-M5 filesystem boundary absent | root resolves compared to itself; support stub True; absolute stored-path acceptance; ungated unlink/rmtree/pruning | separate root/file capability, plan/review/execute, no-follow handles, platform fail-closed | A15–A19; DATABASE_AGENT, BACKEND_AGENT, SECURITY_AGENT |
| F-N1 direct ingestion writes | ingest_corpus in ablation/phase3d/phase3f/phase4b/structure; table ingest_demo uses caller session, flush/commit and structure replacement without local lifecycle authorization | WRITE_DATA capability at every session-taking writer and storage boundary; no assumption that name 'ingest' means nondestructive | A12/A14/A20; EVALUATION_AGENT |
| F-N2 import/startup effects | scripts/db_check.py executes asyncio.run(main()) at module scope; start_server.py clears pycache and starts server; main lifespan applies migrations | no import-time execution; explicit read/connect/start/migrate capabilities, isolated startup | A11/A21; DATABASE_AGENT, BACKEND_AGENT |

`SOURCE-VERIFIED`: Step 1.6L's eight cleanup helpers and four alternate run_once paths currently call unconditional cleanup-execution refusal before resource activity. Their original retained SQL is not a permitted positive lifecycle. The table resolver imports storage/builds a lazy engine before amain disposal authorization; no claim of connection is inferred from construction. E2E run_full_validation refuses before imports/engine and additionally checks configured engine before sessions. Generic execution/writer surfaces above remain wider gaps. Exact examples: table ingest_demo commits and replaces document structure; ablation ingest_corpus performs replace_document_structure and replace_document_graph. A read-only-looking function name is not sufficient capability classification.

`SOURCE-VERIFIED`: Existing name-based application rejection and connection-override parameter rejection are useful necessary preflight rules. Engine URL comparisons do not authenticate a server. Filesystem resolved-prefix checks do not prevent replacement races, hard-link aliasing or Windows reparse-point traversal by themselves.

`HISTORICAL-TRANSCRIPT-ONLY`: Recorded H/I operator-name authorization and J private-sentinel proof claims are superseded, not approval for use. K addendum records bypasses; L records 299 passing tests and blocked boundaries. Those test runs were not repeated or independently verified here. No current claim relies on historical positive authorization being valid. Existing reports are preserved, not overwritten; contradictions are resolved by distinguishing source state from historical statements.

## 4. Enforceable lifecycle authorization — DESIGN-PROPOSAL

### 4.1 Trust/threat model and authority placement

The runner process is NOT trusted to issue or validate its own disposal permission. Private sentinels, dataclasses, module registries, flags and matching names cannot establish authority. Compromised host admin/authority itself is outside the achievable guarantee and must be documented. Protect against accidental configuration, ordinary direct calls, forged/replayed grants, hostile runner requests, redirects/reconnects and concurrent target replacement.

Use a locally operated, out-of-process **Evaluation Lifecycle Authority (ELA)** in a separate OS security identity and process/container boundary. This is a proposed internal security component, not a third-party service selection or installed dependency. It owns the approval trust anchor, durable run journal and exclusive cluster-admin/provisioner credentials. Runners cannot read its secrets or mutate its journal, cluster storage, sockets policy or signing keys. Network/OS ACLs restrict runner access to an authenticated operation interface. A server-controlled opaque handle is only a reference: the authority checks authenticated caller, state, generation, action, target and expiry each time. A caller-created Python object is never accepted as evidence.

Primary supported deployment: a dedicated throwaway PostgreSQL **cluster per approved run** with no production/application database, credentials, network route or upload mounts. Sharing the application cluster is unsupported in the first implementation. Current fixture same-application-host constraint must be replaced in a separately reviewed adapter change, while central application-name refusal remains intact. Neither loopback nor a container name proves disposability.

ELA bootstrap/setup administrator may allocate isolated cluster and install pgvector under a separate permission. Provisioner has CREATE DATABASE only in that dedicated cluster and no application access. Migrator owns only the new evaluation DB/schema and approved extension usage, not superuser/CREATEDB/CREATEROLE/BYPASSRLS or SET ROLE escalation. Runtime writer/cleanup roles have scoped DML only, not database ownership, DDL or connection to any other database. Inspector is SELECT/approved catalog only; PostgreSQL 'read only transaction' is defense-in-depth, not protection against arbitrary volatile functions by itself. Revoke PUBLIC CONNECT/TEMP as appropriate and role inheritance/escalation; use restrictive HBA/network/TLS. Verify grants under a separately authorized runtime stage. No role schema is implemented by this plan.

For the stronger guarantee that stale/arbitrary SQL cannot bypass ELA, cleanup and privileged SQL execute inside ELA/controlled worker with authority-owned connections, not a raw runner session. Runners receive neither admin nor cleanup credentials. DML test application workers must be isolated, run-scoped, revocable and unable to reach another target. If raw writer credentials remain in a Python worker, document residual arbitrary-DML capability inside that run and enforce lifetime/network termination outside Python. That is not equivalent to mediation of every SQL statement; cleanup authority must still remain separate.

### 4.2 State machine and transitions

| State | Entry evidence / allowed operations | Exit / failure rule |
| --- | --- | --- |
| DENIED (default) | no trusted approval; no connections or filesystem deletes | only operator-approved ticket can enter APPROVED |
| APPROVED | signed/admin-recorded environment approval; immutable spec digest, caller, action set, expiry; connection identification only if explicitly permitted | invalid/revoked/expired → DENIED; ELA creates durable CREATING intent before DDL |
| CREATING | exclusive dedicated cluster lease, reserved unique name and idempotency key; ELA opens verified maintenance connection | SQL CREATE success + catalog identity + durable receipt → CREATED_UNVERIFIED; pre-existing name → fail without adopt/drop |
| CREATED_UNVERIFIED | ELA records created DB OID, name, cluster generation/identity, owner and receipt; no runner DML | verify actual connection/roles, approved migration if ticket allows → VERIFIED; failure → QUARANTINED |
| VERIFIED | target/certificate/role/database identity, permissions and schema verified; not yet active | explicit run activation grants bounded actions → ACTIVE |
| ACTIVE | authorized run/operations only on current generation and verified held connection; minimal capabilities | expiry, close, failure, target/role/reconnect change → DRAINING or QUARANTINED, never auto-reactivate |
| DRAINING | atomically revoke new leases, stop writers, wait for in-flight operations; no new write/cleanup requests | permitted scoped cleanup, then separately authorized drop or preserved evidence → DROP_PENDING/QUARANTINED |
| DROP_PENDING | ELA-only maintenance op; receipt/cluster lease/catalog match, no unowned connections, exclusive lock discipline | acknowledged DROP + absence verification → CLOSED; unknown outcome → QUARANTINED |
| CLOSED | durable terminal generation tombstone; no SQL/session/file execution | replay/copy/retry must refuse; a new run needs a new DB name/generation/approval |
| QUARANTINED | uncertain create/drop/identity, interrupted migrations, unexplained resources; no destructive worker use | operator incident review; separately authorized reconciler may inspect, never adopt/drop by name alone |

Create permission precedes successful-create evidence. Existing-target refusal is atomic CREATE failure, not a check-then-create assumption. ELA serializes provisioners with a dedicated-cluster lock and restricts CREATE to ELA; other administrators mutating cluster violate the operating assumptions and trigger quarantine. PostgreSQL CREATE/DROP DATABASE is not transactionally combined with a journal. Handle the commit gap explicitly: write intent/fsync first, issue DDL, record receipt after server acknowledgment; lost acknowledgment/authority crash never manufactures 'created by us' from a name. Quarantine the dedicated cluster; inspect using infrastructure allocation receipt and admin-only catalog evidence. Destruction of a quarantined cluster is a separate infrastructure action, not assumed DB ownership. Prefer leaked disposable data over uncertain deletion.

No default DROP WITH FORCE. Unexpected connections/writers stop drop and quarantine; an operator may separately approve termination of identified run-owned backends only. No IF EXISTS that silently treats an unrelated replacement or missing receipt as lifecycle success. DB OID/name alone are not stable cross-recreation identity; use authority-exclusive provisioning, cluster generation, receipt and nonreuse policy. Closed runs cannot be reopened.

### 4.3 Actual connection validation and use-time binding

Before any connection: authenticate request and validate action/approval/spec/expiry/application deny rules. After an explicitly permitted connection but before mutating SQL: authenticate the server through the approved private endpoint/TLS trust anchor and infrastructure allocation identity; validate PostgreSQL cluster system identifier through an ELA-admin attestation if permitted, cluster generation and server version. In the same held connection collect current_database, database OID, current_user AND session_user, server address/port, backend id, recovery status, TLS properties and role privileges. Compare to ELA's immutable approved record; normalize proxy/internal port differences only via an explicitly reviewed endpoint-to-server mapping. Never accept a different observed port because it is 'probably Docker'. A self-reported SQL string alone is not trusted cluster identity; cloned clusters require allocation identity plus generation, not system identifier alone.

Runtime has no SET ROLE/SET SESSION AUTHORIZATION rights; reset/validate pool state and reject drifted search_path/schema ownership/settings. Every pool checkout/new connection/reconnect revalidates. An operation lease is server-owned and tied to the verified physical backend, generation, action and transaction; a helper cannot swap a session after checking. ELA executes cleanup in that transaction on that connection, not 'check engine then accept arbitrary db'. In-flight-operation fence serializes closure: after DRAINING starts, no new SQL lease; existing lease reaches bounded completion or is canceled/rolled back, then connection disposed. Stale copied handles, target revision, role change or revoked approval refuse. SQL parameters and row-scope constraints are validated again within the executor.

API-level proposed messages (descriptive protocol, not implemented):

```text
ApproveEnvironment(admin_ticket) -> environment_revision
CreateDatabase(approval_ref, run_id, idempotency_key) -> opaque_lifecycle_ref
OpenVerifiedSession(ref, action, expected_generation) -> ELA-owned session lease
ExecuteOperation(lease_ref, catalog_operation, validated_parameters) -> redacted result
BeginClose(ref, expected_generation) -> drain receipt
DropCreatedDatabase(ref, drop_approval) -> closed receipt
```

Read-only inspection, migration, data ingestion, scoped cleanup, database drop and filesystem deletion are distinct actions. No `ExecuteArbitrarySQL` interface for runners. Authority failures/timeouts refuse before work, never 'fallback locally'. Signed tokens, if used, require server-side state/revocation and caller binding; signature alone is insufficient lifecycle enforcement.

## 5. One authoritative target-resolution contract — DESIGN-PROPOSAL

The single evaluation source is an **operator-approved immutable environment manifest** loaded once by ELA from a protected path/authenticated channel. Secret references point to protected local credential material unavailable to runners; do not embed DSN credentials in artifacts or protocol. Proposed schema:

```text
EnvironmentSpec v1:
 approval_id, revision, environment_id, allocation_id, expires_at,
 cluster_generation, approved_endpoint(host, port, TLS policy/trust reference),
 expected_cluster_attestation, maintenance_database,
 provisioner_role_ref, migrator_role_ref, runtime_role_ref, inspector_role_ref,
 application_deny_identities(names + cluster/allocation references),
 allowed_actions, isolated_network_id, approved_scratch_root_identity,
 migration_head, code_digest, approver_identity
RunSpec v1:
 environment_revision_digest, run_id, lifecycle_generation,
 authority_generated_database_name, created_database_oid, schema_identity,
 request_caller, operation_lease_limits
```

Some RunSpec fields exist only after creation; earlier states cannot claim them. No default application DSN or automatically derived integration name. No runner may supply a DSN to construct privileged credentials. CLI accepts approval/run reference, not authority; selecting a reference is not granting approval.

All adapters (runners, fixture, psql replacement, migrations, E2E app startup) consume the same read-only manifest revision and ELA session/capability interface. No `dsn.database + e2e_config.host/user/password` splice. Maintenance and target endpoints derive from the same approved allocation but different explicit DB/role identities, verified on their own connections. Credential rotation needs a new manifest revision and drained leases; mutable env is not re-resolved at drop.

Legacy DATABASE_URL / DOCUMIND_E2E_DATABASE_URL / DOCUMIND_INTEGRATION_DATABASE_URL or --database-url cannot override this contract in evaluation mode. Adapter rejects nonempty conflicting legacy sources BEFORE model/database imports; equivalence comparison must include normalized scheme, host/port/database, credential reference/role and approved TLS options, not merely name. Prefer reject any alternate configured evaluation source unless migration compatibility is explicitly approved; never dump secrets in conflict messages. Production settings remain a separate supported application contract; do not silently change app production precedence. E2E worker is started with an isolated explicit evaluation settings object and network, not reused application get_settings cache/environment mutation. The authority's application deny list is operator-maintained nonsecret policy; missing/unknown deny policy refuses.

Keep existing central URL validity/override/name rejection as necessary preflight. Replace misleading 'prove different' terminology during a future owned documentation update. Use exact supported PostgreSQL drivers and allowlisted TLS/connect options; reject libpq service/hostaddr/alternate sockets/redirect query values unless explicitly modeled. Preserve conservative casefold/decoded same-application-name denial even on another cluster in v1; dedicated evaluation names eliminate legitimate need to weaken it. The old fixture same-app-server requirement must be replaced by verified same-**approved evaluation allocation** requirement under Database/Security review, not dropped without replacement.

SQL/client contract: typed parameters for values; driver SQL identifier composition/strict ELA-generated names for DDL (not string escaping guesses). Empty/malformed identifiers fail; existing DB never dropped. Fixed operation catalog; read operations are predefined SELECTs under read-only role, not substring 'starts SELECT'. If psql must remain as an admin-only migration transport, use trusted absolute executable, -X, ON_ERROR_STOP=1, bounded statement/lock/connect timeouts, explicit endpoint/role/database, minimal allowlisted environment, controlled HOME/PG* and credentials not argv. Capture/redact errors and require SQL-result acknowledgment, not process exit only. No shell=True. ELA passes exact approved migration connection/identity; migrations/env.py must not catch and substitute Alembic fallback URL. Plain Alembic CLI in evaluation context refuses without authenticated one-use migration channel. Production auto-migration behavior requires a separately owned compatibility decision.

## 6. Execution-boundary inventory and controls

`SOURCE-VERIFIED` applies to file/function/effects/current protection columns. `DESIGN-PROPOSAL` applies to boundary/failure/tests/owner columns. File prefixes: E=`backend/evaluation/experiments/`; F=`backend/tests/fixtures/`; S=`backend/scripts/`; R=`backend/tests/integration/rag/`. Definitions/actual call-line inventories are appended. One row may name multiple explicitly listed functions with the identical control contract; no claim of exhaustive dynamic-call detection is made.

Effect keys: C=connect/session; Q=SQL/read; W=DML/structure replacement; M=migration/DDL; D=DB create/drop; X=file deletion; P=process/API execution. Test IDs: T0 pure authority; T1 static inventory/import; T2 controlled PostgreSQL; T3 runner/fixture; T4 E2E; T5 filesystem; T6 independent review.

| ID | File / function(s) | Effects; current protection | Proposed boundary / required failure | Tests | Owner |
| --- | --- | --- | --- | --- | --- |
| B01 | E run_phase3d_evaluation.main | C/W; disposal refusal before DB work | ELA ACTIVE + WRITE_DATA/CLEAN_ROWS leases; refuse preflight/no imports if absent | T0–T3 | EVALUATION_AGENT |
| B02 | E run_phase3d_upload_integration.main; nested upload | C/W/P, TemporaryDirectory X; main refusal | run-scoped app/session and SCRATCH capability; nested upload inherits checked lease, cannot choose live API | T0–T4/T5 | EVALUATION_AGENT |
| B03 | E run_phase3e_integration.main | C/W/P/X; main refusal | same incl API DELETE/individual temp unlink | T0–T5 | EVALUATION_AGENT |
| B04 | E run_phase3e_validation.main | C/W/M-like schema assertions/P/X; main refusal | approved operation catalog incl explicit schema-read, no ad hoc upgrade; SCRATCH executor | T0–T5 | EVALUATION_AGENT |
| B05 | E run_phase3f_evaluation.main | C/W; main refusal | ACTIVE + per-operation lease | T0–T3 | EVALUATION_AGENT |
| B06 | E run_phase4b_evaluation.main | C/W; main refusal | ACTIVE + per-operation lease | T0–T3 | EVALUATION_AGENT |
| B07 | E run_dual_path_ablation.main | C/W; main refusal | ACTIVE + catalog DML, dedicated worker connection | T0–T3 | EVALUATION_AGENT |
| B08 | E run_table_evidence_measurement.main/amain/_resolve_database_url | C/P; amain refusal after settings/storage import; main wrapper | resolve immutable spec and auth before storage import; no arbitrary URL/cache side effects | T0–T3 | EVALUATION_AGENT |
| B09 | E run_structure_element_measurement.main/guard_evaluation_target/bind_database_runtime/verify_bound_engine | C/config; shared refusal; URL-only engine check | ELA verified connection factory, no global cached authorization | T0–T3 | EVALUATION_AGENT |
| B10 | E run_structure_rrf_calibration.main/bind_database_runtime | C; shared binding guard | same, revalidate idempotent binding state/generation | T0–T3 | EVALUATION_AGENT |
| B11 | E run_structure_confirmation.main/bind_database_runtime | C; shared binding guard | same | T0–T3 | EVALUATION_AGENT |
| B12 | E run_table_evidence_measurement.run_once(engine,...) | C/W; local unconditional refusal | remove raw engine acceptance or require ELA-owned verified lease; invalid resource refuses before session | T0/T1/T2 | EVALUATION_AGENT |
| B13 | E structure_element_measurement.run_once; structure_rrf_calibration.run_once; structure_confirmation.run_once | C/W; local unconditional refusal, global engine | verified lease injected, no global factory substitution | T0–T3 | EVALUATION_AGENT |
| B14 | E run_phase3d_upload_integration.cleanup_harness_rows | W; local refusal (1/8) | CLEAN_ROWS inside same authority transaction; preserve owned user predicate | T0–T3 | EVALUATION_AGENT |
| B15 | E run_phase3d_evaluation.cleanup_harness_rows | W; local refusal (2/8) | same, ids checked against run ownership, including empty input | T0–T3 | EVALUATION_AGENT |
| B16 | E run_phase3e_integration.cleanup_harness_rows | W; local refusal (3/8) | same | T0–T3 | EVALUATION_AGENT |
| B17 | E run_phase3e_validation.cleanup_harness_rows | W; local refusal (4/8) | same | T0–T3 | EVALUATION_AGENT |
| B18 | E run_phase3f_evaluation.cleanup_harness_rows | W; local refusal (5/8) | same | T0–T3 | EVALUATION_AGENT |
| B19 | E run_phase4b_evaluation.cleanup_harness_rows | W; local refusal (6/8) | same | T0–T3 | EVALUATION_AGENT |
| B20 | E run_dual_path_ablation._delete_user_data | Q/W; local refusal (7/8); structure callers too | CLEAN_ROWS, no caller raw session; preserve FK-safe scope | T0–T3 | EVALUATION_AGENT |
| B21 | E run_table_evidence_measurement.teardown | W/commit; local refusal (8/8) | CLEAN_ROWS, run-owned ids not only reusable email | T0–T3 | EVALUATION_AGENT |
| B22 | E run_dual_path_ablation.ingest_corpus; run_phase3d_evaluation.ingest_corpus; run_phase3f_evaluation.ingest_corpus; run_phase4b_evaluation.ingest_corpus; run_structure_element_measurement.ingest_corpus | W/commit/X; caller sessions, no local ELA; structure replacement in some | WRITE_DATA at function/session boundary, run-owned records and scratch lease; refuse invalid connection before work | T0–T3/T5 | EVALUATION_AGENT |
| B23 | E run_table_evidence_measurement.ingest_demo | W/replace/commit; no local ELA | WRITE_DATA before flush/replace; do not let demo source path become deletion target | T0–T3 | EVALUATION_AGENT |
| B24 | E phase3d/3e/3f/4b.owned_user_ids; phase3e_validation._get_chunk_ids_for_doc; structure_element.load_persisted_elements; table.load_persisted_rows/_ensure_schema | Q/C read; caller/engine-based, no authority | READ_SCHEMA/READ_DATA leases; fixed catalog, same connection; failed schema query not swallowed as ready | T0–T3 | EVALUATION_AGENT |
| B25 | E run_phase4c_diagnostics.main | recorded-data/model/scratch X; no lifecycle | OFFLINE_REPORT + SCRATCH, prohibit database imports/network; classify offline, not one of nine | T1/T5 | EVALUATION_AGENT |
| B26 | F integration_db.psql_value; e2e_config.psql | arbitrary Q/W/M/D/P; no local lifecycle gate | remove public arbitrary SQL; catalog ELA executor; admin transport isolated, deny raw SQL requests | T0–T3 | TEST_AGENT; DATABASE_AGENT transport |
| B27 | F integration_db.database_exists/inspect_schema/verify_schema | Q via psql_value; no local capability | fixed READ_SCHEMA catalog and maintenance spec, no interpolated names/redirect | T0/T2/T3 | TEST_AGENT |
| B28 | F integration_db._create_database | D; central create refusal | ELA CreateDatabase only; exclusive CREATE, atomic existing refusal | T0/T2/T3 | TEST_AGENT adapter + DATABASE_AGENT authority |
| B29 | F integration_db._drop_database | D; central drop refusal; app-maintenance re-resolution | ELA DropCreatedDatabase, receipt/generation fence, no FORCE or name-only drop | T0/T2/T3 | TEST_AGENT + DATABASE_AGENT |
| B30 | F integration_db.provisioned_integration_database/isolated_database | C/D/M; create refusal before probe | lifecycle client, finally cannot invent drop privilege; quarantine uncertain outcomes | T0–T3 | TEST_AGENT |
| B31 | F integration_db.postgres_available/require_postgres | C/socket probe; no authority within probe | CONNECT_INSPECT permission even for probes; unavailable != passed, stop not silently substitute | T0/T1/T2 | TEST_AGENT |
| B32 | F integration_db._alembic_env/alembic_head/migrate_to_head | P/M; no local migration auth, env inherited | ELA-issued one-use migrator channel + exact manifest; offline revision parse separate from importing env | T0–T3 | TEST_AGENT + DATABASE_AGENT |
| B33 | backend/migrations/env.py run_migrations_online/run_async_migrations/do_run_migrations/run_migrations_offline; versions/000..007 upgrade/downgrade | C/M/drop; config fallback, no evaluation grant | ELA migration worker exact approved revision; identity checked first; unauthorized CLI/direct downgrade refuses; offline script generation no connection and separate approval | T1/T2/T3 | DATABASE_AGENT |
| B34 | S setup_db.main; backend/main._run_migrations/_ensure_database_schema/lifespan | P/C/M; application auto-upgrade | explicit evaluation migration capability; runtime app no implicit DDL; production startup change separately reviewed | T0–T4 | DATABASE_AGENT setup; BACKEND_AGENT main |
| B35 | R test_real_e2e_validation.run_full_validation/test_real_e2e_validation and both __main__ branches | C/W/unscoped DELETE; first row refusal + engine-config check | same ACTIVE capability from fixture/ELA; no existing-target flag bypass; table-wide reset only if separately approved on run-exclusive DB | T0–T4 | TEST_AGENT |
| B36 | F e2e_config.ensure_test_user/purge_documents/login/document_names; integration_http.api_call and raw HTTP transport | P/API auth/read/write/delete; JWT user scope, not disposable authority | bind API base/server attestation and run tenant; WRITE_DATA/CLEAN_ROWS lease per destructive request; no ambient localhost fallback | T0/T3/T4 | TEST_AGENT; BACKEND_AGENT server adapter |
| B37 | S create_test_user.create_user/main; db_check.main + module asyncio.run | C/Q/W; app settings, import executes db_check | explicit evaluated target/read or write grant, import side-effect removal, nonzero failure and redaction | T0/T1/T2 | DATABASE_AGENT |
| B38 | S cleanup_smoke.cleanup/_resolve_stored_path/main | C/W/X; confirmation/--yes only; accepts abs/existing paths | separate maintenance policy for live app, never evaluation grant; FS plan+root executor + approved row ids, default blocked | T0/T2/T5/T6 | DATABASE_AGENT; BACKEND_AGENT file service |
| B39 | S cleanup_orphan_uploads.run_sweep/main/_referenced_keys/_scan_uploads/_archive_orphans/_key | C/Q/X/archive write; dry run, ref-read abort, containment; missing model/session bindings visible | snapshot+write quiescence, immutable reviewed FS plan, safe no-follow executor, archive bounded exclusive create; no missing DB → orphan inference | T0/T2/T5 | DATABASE_AGENT |
| B40 | S cleanup_path.is_under/forbid_symlink_roots/filesystem_supports_relative_symlinks | path inspection; ineffective root equality + support stub | OS handle-based root identity/capability adapter; unsupported -> delete blocked, not True | T0/T5/T6 | DATABASE_AGENT |
| B41 | backend/storage/file_store.delete_upload/cleanup_new_file; save_upload/_user_upload_dir | X/write; no local deletion containment | BACKEND file capability matching created/stored file identity and authorized owner; evaluation scratch only; no caller absolute path | T0/T5 | BACKEND_AGENT |
| B42 | backend/storage/database.py module engine + get_db | C/W/commit; app settings/cached engine | evaluation injection from verified ELA worker factory, no app global engine borrowing; no imported settings authority | T0–T4 | DATABASE_AGENT + BACKEND_AGENT |
| B43 | S start_server module port probe/pycache rmtree/Popen | C/X/P/M via startup; top-level | explicit START_WORKER + SCRATCH; remove recursive cwd deletion, no startup without migration policy | T1/T4/T5 | DATABASE_AGENT |
| B44 | backend/documents/parser.parse_pdf byte branch; backend/voice.transcribe temp finally | X of OS temp; no shared FS lease | owned scratch handles; no-follow cleanup, preserve error evidence; application compatibility separate | T5 | BACKEND_AGENT; AI_AGENT voice if contract assigns |
| B45 | backend/tests/e2e/browser/{test_browser_flow,test_document_flow,test_embedding_flow,test_phase6_reliability,test_rag_flow}.main/__main__; test_real_browser.test_real_browser_playwright_flow | API/P/Q/X; live settings, purge, subprocess startup/temp deletes | pytest-only controlled E2E stage, same API/DB allocation + SCRATCH; no direct-file execution, no reused demo corpus | T1/T4/T5 | TEST_AGENT |
| B46 | backend/tests/integration/documents/test_table_row_migration._run_alembic/_alembic + upgrade/downgrade tests; backend/tests/conftest _test_engine/_create_tables/db_session/client | SQLite C/M/create/drop/test mutations; no production cert | explicit separate SQLite/PG test stage, no DB in offline tests; connection tripwire, never collect unsafe fixture by accident | T0/T1/T2/T3 | TEST_AGENT |
| B47 | F graph_data.create_document_with_chunks/create_test_user; integration mutation tests using client.delete | W fixtures/API; test DB dependency | only stage-bound verified test session; deny fake fixture passed into production authority | T0/T3 | TEST_AGENT |
| B48 | test/corpus TemporaryDirectory finally and integration graph/document temp unlink | X scratch; test-local not lifecycle-governed | require SCRATCH identity and explicit filesystem-test approval; no model/benchmark/application upload paths | T1/T5 | TEST_AGENT/EVALUATION_AGENT by file |

B44 voice callable is `backend/voice.py:transcribe` (definition near line 196; temp-finally unlink near line 261), verified from current definitions; public interface changes still require the owning agent's review. Inventory includes discovered runtime transitive boundaries but does not propose wrapping every production CRUD handler with evaluation authorization. Production JWT/file ownership remains separate; isolated evaluation worker plus run-bound adapters prevents accidental production reuse.

Additional boundary evidence not to misclassify: evaluation/artifacts._git subprocess is Git metadata, not a database runner. Corpus synthesis/offline metric functions may write artifacts/scratch but are not PostgreSQL authority. Filesystem archival creation is itself write I/O and requires approved destination, not only delete permission. Full AST scan lists below expose read/write candidates so implementers must resolve dynamic and aliased calls before enabling any runner.

## 7. Filesystem remediation — DESIGN-PROPOSAL

### 7.1 Root and platform contract

Use a separate **Filesystem Execution Authority** under ELA's protected OS boundary or equally restricted local executor; no raw delete path accepted from runner. Operator approves an existing dedicated root with canonical absolute path, filesystem/volume id, root file-id/inode, owner/mode/ACL, allocation/run generation and permitted operation. Never silently create a missing root for a delete request. Reject empty/relative root, root drive/UNC share root, home/repository/model/benchmark/venv/application-upload root in evaluation mode, ambiguous case/alias, unapproved mount/network filesystem and unsupported platform. Production maintenance needs a different ticket and backups; evaluation approval never permits live uploads.

Walk components with no-follow semantics, rejecting symlinks, Windows junctions/reparse points, mount changes and '..', NUL, drive-relative/UNC/device paths, alternate data streams and encoded path tricks. Absolute stored paths are rejected by default; an explicitly approved legacy conversion may convert to a relative key only after handle-based containment and owner checks, never 'exists therefore accept'. Hard-linked files require deny multiple-link files or a separately reviewed policy; resolved strings alone do not prove exclusive data ownership. Root identity must remain held/open, not re-resolved after approval.

POSIX adapter: directory handles, relative no-follow opens, file identity checks and deletion relative to held directories, with exclusive controlled tree access. Windows adapter: handle-based no-reparse traversal and file/volume identity under exclusive ACLs; implementation/API selection requires platform review. No claim Python Path.resolve provides equivalent atomic protection. If the required no-follow/race guarantees cannot be implemented on a filesystem/OS, execution remains blocked and read-only plan may be emitted. Symlink 'support' is not safety. Capability detection returns SUPPORTED/UNSUPPORTED/UNKNOWN based on actual supported operations and separately authorized sandbox probes; never a hardcoded True or permission error interpreted as supported.

### 7.2 Plan/review/execute for both operational scripts

Separate `PlanCleanup` (read-only scan and approved DB-reference read; may not delete) from `ExecuteCleanup(plan_digest, approval_ref)`. Plan records root id, run/allocation, exact relative paths, file ids/types/link counts/sizes, database snapshot/run identity, generation, approval expiry and count/byte limits. It excludes referenced/protected files; enumeration error, ambiguous root, unreadable reference DB, unknown capability or changed file halts. Dry-run is default. Human/operator reviews digest and summary; --yes is convenience only, never capability issuance. Executor revalidates plan digest, root/file ids, current reference state and caller authorization under an exclusive upload writer fence. File substitution/ref changes/partial archives invalidate the plan; do not 'best effort skip' unexpected boundary escapes then claim overall success.

For orphan sweeping, quiesce writers or use an application-managed two-phase quarantine protocol with fenced DB metadata; a stale reference snapshot is insufficient. Do not delete freshly created/unknown files. Archive only to an approved external destination, exclusive creation with handle/no-follow safeguards and no overwrite; verified CRC/count are integrity checks, not authorization or race control. Prune only explicitly planned, revalidated empty directories within the same held root boundary; never rglob over a swapped root. Root itself is never removed by a file cleanup operation.

For smoke cleanup, bind approved row/user ids and file identities, not reusable email alone. Prefer transactionally marked deletion intent followed by quarantined files and committed row transition; reconcile failures, do not lose sole path evidence by deleting files before DB intent. Database and filesystem cannot be atomically committed together: journal each phase, preserve audit and recovery, quarantine uncertainty. `delete_upload`/`cleanup_new_file` must enforce created-file/storage capability internally so operational callers cannot bypass script checks. Logs omit credentials/token/path-sensitive data; failures produce redacted codes and nonzero status.

## 8. Dependency-ordered implementation work packages — DESIGN-PROPOSAL

No package is authorized for implementation by this report. Coordinator must issue scoped tasks; no agent edits outside ownership.

| Order | Work package / named owner | Dependencies | Definition of done / rollback |
| --- | --- | --- | --- |
| P0 | Coordinator + SECURITY_AGENT + DATABASE_AGENT approve threat model, isolated cluster choice, trust/journal/caller model and tickets | independent review available or explicit outstanding gate | approved ADR and operator allocation policy; all current refusal unchanged |
| P1 | DATABASE_AGENT designs/implements ELA administration, roles/network identity and one target manifest; EVALUATION_AGENT owns pure client contract under evaluation | P0; Coordinator assigns exact new ELA source ownership before creation | T0/T1 capability/state/conflict tests, no operational connects; unavailable ELA refuses; no raw secret grants |
| P2 | TEST_AGENT removes/gates arbitrary SQL fixture/e2e/migration adapters; DATABASE_AGENT fixes SQL composition, psql/env/migrations/setup | P1 API; migration compatibility decision | A6–A13; no fallback/plain CLI bypass; default refusal remains until integration proof |
| P3 | EVALUATION_AGENT routes all B01–B25 writers/readers/cleanup into verified leases; TEST_AGENT rewires fixture/E2E; BACKEND_AGENT isolated app factory | P1/P2 | A12/A14/A20/A21; no global engine/env mutation, all direct calls refuse without capability; data scoping unchanged |
| P4 | DATABASE_AGENT scripts + BACKEND_AGENT file_store platform cleanup; SECURITY_AGENT reviews | P0 root policy, P1 trust; before any destructive runtime stages | A15–A19, Windows/POSIX adapters or explicit unsupported block; no live-root deletion |
| P5 | TEST_AGENT prepares independent no-I/O/static + controlled PG/E2E/FS suites; VERIFIER reviews code & evidence | incremental P1–P4; no skipped security assertions | offline gates pass, authorized test manifests, no DB during test collection; report positive cleanup tests incompatible until authority exists |
| P6 | Coordinator obtains separate runtime/environment and action authorizations; DATABASE_AGENT administers disposable infrastructure | P0–P5 and independent security/database approval | grant/identity evidence, exact procedure and recovery, no application data exposure |
| P7 | TEST_AGENT runs separately authorized staged tests; VERIFIER + SECURITY_AGENT + DATABASE_AGENT approve final readiness | P6; each stage explicit permission | exact logs/status/resources and no unaddressed bypass; any failure reverts operational enablement to refusal, not Git reset |

Ownership conflicts: central production storage/main and scripts cannot be changed by EVALUATION_AGENT/TEST_AGENT; Coordinator requests DATABASE_AGENT/BACKEND_AGENT. ELA new module ownership/transport is an explicit P0 decision, not assumed permission to add a service. Archived research activation requires EVALUATION_AGENT inventory. No benchmark/model or production retrieval changes belong to these packages.

## 9. Verification stages and acceptance criteria — DESIGN-PROPOSAL / BLOCKED execution

All stages below are plans only. No tests run in 1.6N. Future Python test execution uses `python -m pytest <explicit inspected paths>` with interpreter/environment agreed in the task, not direct test-file execution. Preserve real command exit codes before filtering. No counts/latency/performance claims are predicted.

| Stage | Prerequisites / allowed operations | Prohibited targets/operations | Evidence / pass and stop conditions |
| --- | --- | --- | --- |
| T0 DB-free authorization/refusal | reviewed imports/conftest; pure state/manifest logic, mocked transport, poison resource and socket/process/file tripwires | every DB including SQLite, runner/helper destructive bodies, real network, filesystem deletion | A1–A14/A20/A21 negative/state tests pass; no tripwire fired; fabricated/replayed grants, changed target/caller/role/expiry/closure refuse; unexpected I/O stops |
| T1 static/source safety | P1–P5 reviewed source; AST/import graph without project module execution | app/start_server/db_check imports with side effects, migrations/fixtures/runtime | inventory-to-source mapping complete; no arbitrary SQL or env splice/fallback; every direct writer/executor has boundary; original scope/order preserved; unresolved dynamic call stops enablement |
| T2 isolated PostgreSQL lifecycle | P6 explicit connect/create/migrate/DML/cleanup/drop permissions separately; dedicated cluster and verified grant/network/identity baseline | application/shared cluster, production credentials/upload mounts, unapproved FORCE/downgrade | real same-connection identity/role/permission evidence, existing-name refusal and no sentinel modification; crash/race/close/replay negative tests; ambiguous receipt/server or residual unrelated session stops and quarantines |
| T3 runner/fixture integration | T0–T2 + runner action authorization and disposable datasets | uninspected whole suite, runtime fallback targets, shared demo accounts | each B01–B35 direct/entry path targets one run; invalid raw session/engine before SQL; failure injection at create/migration/setup/cleanup/close; unrelated rows preserved; no masked errors |
| T4 E2E | T3; separately approved isolated app/network/upload worker, authorized API base identity, model availability recorded | live server/localhost assumed existing app, implicit startup migrations, reused demo content | request→worker→database+filesystem allocation identity chain; ownership/isolation/failures measured; no false PASS when model/schema unavailable; mismatch stops before mutation |
| T5 filesystem cleanup | T0/T1 + separately approved sandbox create/link/delete operations and OS permissions; selected platform | application uploads, repo/models/benchmark, host absolute paths, unsupported network/reparse behavior | outside-root sentinel hashes unchanged; path traversal/abs/junction/symlink/hardlink/race/root replacement/missing-root/capability UNKNOWN refuse; archive limits/plan replay/ref races tested; no destructive test before FS approval |
| T6 independent security/database/verifier review | source/test evidence and P0 assumptions available; independent actual reviewers | treating single Coordinator role-play as independent approval; unapproved DB probes | signed attributable review findings, zero unresolved in-scope destructive bypass; compare intended/actual artifacts, no security test weakening; missing reviews keeps gate closed |

T6 review begins at P0 and repeats after implementation, not only after execution. Positive stages cannot be justified by T0 pass count. PostgreSQL CONNECT permission does not authorize migrations/DDL/cleanup; FS creation permission does not authorize deletion. Stop on secret leakage, wrong target/role/root, unsupported identity, incomplete grants, unexpected startup side effects, missing proof receipt, expired approval, nonzero test or uncertain cleanup result. Leave quarantined resources for approved reconciliation, never recover by dropping by name.

Acceptance catalog (DESIGN-PROPOSAL; identifiers referenced by inventory and work packages):

- **A1:** no approval/missing authority/invalid caller → no connection or SQL; expiry/revocation/replay refused.
- **A2:** create success evidence only from ELA's acknowledged CREATE plus journal/catalog; existing DB collision causes zero drop/adoption.
- **A3:** every state transition valid, terminal CLOSED cannot reopen; closure fences in-flight lease and rejects stale/cross-lifecycle handles.
- **A4:** lost CREATE/DROP acknowledgment and authority crash quarantine; no fabricated receipt or blind retry cleanup.
- **A5:** restricted roles/networks prevent runner create/drop/app access; authority compromise assumptions reviewed.
- **A6:** one manifest revision yields whole target and maintenance spec; no DSN field splicing.
- **A7:** conflicting legacy CLI/env/settings, unsafe scheme/options or missing application deny policy reject pre-import; no fallback/cache target substitution.
- **A8:** actual server/allocation/port/DB OID/current+session user verified on held connection; proxy mapping explicit; reconnect/role/pool/target mutation denied/reverified.
- **A9:** quotes/Unicode/empty/malformed identifiers and malicious values handled safely by typed composition; no arbitrary SQL evaluator.
- **A10:** minimal child environment/startup, -X/ON_ERROR_STOP and bounded timeouts if psql retained; secret-safe nonzero failures and actual SQL acknowledgment.
- **A11:** migration direct/CLI/app-start boundary cannot select alternate/fallback target; authorized head/revision only; runtime no admin role.
- **A12:** each inventoried cleanup/SQL/write helper rejects direct caller absent current capability before session/flush/SQL/file activity; empty scope does not skip authorization.
- **A13:** read helpers use fixed catalog/read role; arbitrary SELECT/function/multiple statement cannot gain write/admin privilege.
- **A14:** same-physical-connection and operation scope enforced through executor; caller-supplied engine/session cannot substitute after validation; owned-row cleanup ordering retained.
- **A15:** missing/ambiguous root, '..', absolute/device/drive-relative/UNC/ADS, symlink/junction/reparse/mount change refuse.
- **A16:** race-safe held-root/file ids, hardlink policy and exclusive writer fence prevent outside-root/deletion of replaced referenced files; outside sentinels unchanged.
- **A17:** dry run cannot delete; approved plan digest/path/count/bytes/expiry governs execution; --yes alone no authority; replay/change invalidates.
- **A18:** unsupported/unknown filesystem capability blocks deletion, never pretends tested support; Windows+POSIX cases explicitly evidenced.
- **A19:** archive exclusive destination/verification and directory pruning share boundary; DB-file failure journal preserves recovery and root never deleted implicitly.
- **A20:** direct ingestion/structure-replacement and schema/read helpers mapped, not merely eight cleanup names; alternate run_once cannot bypass.
- **A21:** importing db_check/startup/test modules does not connect/delete/start migration; startup operations separated and explicitly scoped.

## 10. Risks, decisions and approvals — UNVERIFIED / BLOCKED

Unresolved operator/architecture decisions: ELA host ownership and authenticated local transport; protected journal/trust-anchor storage; exact PostgreSQL attestation privilege/CA and proxy mapping; dedicated cluster provisioning method; role grants and extension admin path; OS-specific no-follow/delete primitives and hardlink policy; app migration decoupling; production smoke cleanup retain/replace/disable decision; long-running lease expiry/drain timeouts; quarantined resource retention/data handling. No new dependency/provider is selected or installed. These decisions have proposed safe defaults above but require explicit P0 approval.

Residual risk: arbitrary compromised evaluation worker with raw writer credentials can mutate its isolated run database while credentials are live. Stronger mediation requires all privileged execution inside ELA and revocable worker channels, not an in-process check. Host admin/authority compromise, concurrent external administrators and OS/filesystem guarantees cannot be proven by Python tests. Distinct allocations/roles/roots bound consequence even when a guard has a bug. Positive operational claims remain UNVERIFIED until controlled stages actually run.

Immediate bypass remediation requests (not patches): F-M4/F-M5 and F-N1/F-N2 need dedicated implementation tasks and explicit affected-owner approvals. Do not import db_check to 'check readiness', or run operational script dry-run assuming it cannot connect. Do not call generic SQL helpers with allegedly disposable targets. Preserving current refusing helpers does not close other APIs.

Independent review: DATABASE_AGENT, SECURITY_AGENT, EVALUATION_AGENT, TEST_AGENT and VERIFIER execution unavailable; all review approvals outstanding. Documentation authorship is complete only subject to the bounded inventory/preservation limitations, not independent design endorsement.

## 11. Prerequisites before PostgreSQL verification can be reconsidered — BLOCKED checklist

- [ ] Coordinator/operator approve this architecture and exact ownership, including ELA trust boundary.
- [ ] F-M1–F-M5 and F-N1/F-N2 remediated by owning agents with A1–A21 evidence; no arbitrary SQL/migration/filesystem bypass remains.
- [ ] Immutable target and application-deny contract replaces split config; actual identity mechanism implemented and reviewed.
- [ ] Durable lifecycle state, exclusive provisioner and fail-safe quarantine/reconciliation implemented.
- [ ] Restricted roles/network/TLS/allocated isolated cluster and dedicated scratch roots independently verified under separate permission.
- [ ] No-I/O/static tests pass without database collection side effects; legitimate assertions preserved.
- [ ] Independent Security/Database/Verifier reviews recorded with attributable evidence.
- [ ] Operator separately authorizes exact connection, creation, migration, DML, cleanup/drop and FS actions/limits/stop conditions/recovery; no authorization inferred from a ticket name.
- [ ] Future staged T2–T5 test task approved; reports record real outcomes and leftovers, not expected success.

**PostgreSQL status: NO-GO. Design only; do not begin implementation or database execution from this document.**

## 12. Task validation and Git evidence — SOURCE-VERIFIED

Executed only source reads/search, Git HEAD/status/path listing, and Python standard-library AST/hash/document checks. No pytest, project module import, runner, migration, DB connection, cleanup or destructive filesystem operation. No .env read/secret printing, reset/clean/stash/revert/stage/commit/push. Existing reports remain untouched. Final verification and complete baseline/final evidence follow.

Final HEAD unchanged: `6baaa2a0773df66e5fb26814afbe67647fb43435`. Expanded status **1139 → 1140**; both status and complete Git-path set differences add only this new report and remove no path. **914 snapshotted regular nonsecret/nonruntime existing files remain byte-identical**. Excluded secret/runtime/symlink paths were not hashed, so no universal byte-preservation claim is made for them. No implementation edit was made.

### 12.1 Complete initial expanded status — SOURCE-VERIFIED

```text
 M .gitignore
 M DOCUMIND_PROJECT_CONTEXT.md
 M backend/brain/__init__.py
 M backend/brain/adapters.py
 M backend/brain/response.py
 M backend/brain/types.py
 M backend/chat/qa_model.py
 M backend/chat/rag.py
 M backend/chat/routes.py
 M backend/documents/models.py
 M backend/documents/processing.py
 M backend/documents/routes.py
 M backend/documents/schemas.py
 M backend/embeddings/model.py
 M backend/embeddings/routes.py
 M backend/evaluation/harness/corpus.py
 D backend/evaluation/harness/evaluator.py
 M backend/main.py
 M backend/migrations/env.py
 D backend/phase3d_evaluation_report.json
 D backend/phase3f_evaluation_report.json
 D backend/phase3f_validation_report.txt
 D backend/phase3g_pipeline_audit.txt
 D backend/phase4a_qa_failure_audit.txt
 D backend/phase4b_evaluation_report.json
 D backend/phase4b_qa_evaluation_report.txt
 D backend/phase4c_failure_matrix.json
 D backend/phase4c_qa_failure_isolation_report.txt
 D backend/phase4d/__init__.py
 D backend/phase4d/__main__.py
 D backend/phase4d/evaluate_candidates.py
 D backend/phase4d/generate_report.py
 D backend/phase4d/oracle_eval.py
 D backend/phase4d/reconciliation.py
 D backend/phase4d/train.py
 D backend/phase4d/training_data.py
 D backend/phase4d_1_reconciliation.json
 D backend/phase4d_1_reconciliation_report.txt
 D backend/phase4d_experiment_results.json
 D backend/phase4d_oracle_baseline_results.json
 D backend/phase4d_qa_model_improvement_report.txt
 D backend/phase4e/__init__.py
 D backend/phase4e/capability_analysis.py
 D backend/phase4e/generate_report.py
 D backend/phase4e_capability_matrix.json
 D backend/phase4e_diagnostic_results.json
 D backend/phase4e_qa_architecture_analysis.txt
 D backend/phase4f/__init__.py
 D backend/phase4f/balance_gate.py
 D backend/phase4f/dataset/__init__.py
 D backend/phase4f/dataset/dataset_manifest.json
 D backend/phase4f/dataset/dataset_manifest_v3.json
 D backend/phase4f/dataset/dataset_manifest_v3_1.json
 D backend/phase4f/dataset/dataset_metadata.json
 D backend/phase4f/dataset/dataset_quality_report.json
 D backend/phase4f/dataset/dataset_quality_report_v3.json
 D backend/phase4f/dataset/dataset_quality_report_v3_1.json
 D backend/phase4f/dataset/expand_and_audit.py
 D backend/phase4f/dataset/generator.py
 D backend/phase4f/dataset/training_data.jsonl
 D backend/phase4f/dataset/training_data_v3.jsonl
 D backend/phase4f/dataset/training_data_v3_1.jsonl
 D backend/phase4f/experiments/evaluate.py
 D backend/phase4f/experiments/experiment_manifest.json
 D backend/phase4f/experiments/final_gpu_package/README_GPU_EXECUTION.md
 D backend/phase4f/experiments/final_gpu_package/dataset/training_data_v3_1.jsonl
 D backend/phase4f/experiments/final_gpu_package/dataset_checksum.txt
 D backend/phase4f/experiments/final_gpu_package/evaluation/evaluate.py
 D backend/phase4f/experiments/final_gpu_package/expected_output_structure.txt
 D backend/phase4f/experiments/final_gpu_package/final_gpu_package_manifest.json
 D backend/phase4f/experiments/final_gpu_package/production_model_checksum.txt
 D backend/phase4f/experiments/final_gpu_package/requirements.txt
 D backend/phase4f/experiments/final_gpu_package/training/experiment_config.json
 D backend/phase4f/experiments/final_gpu_package/training/train.py
 D backend/phase4f/experiments/phase4f_3_results.json
 D backend/phase4f/experiments/phase4f_3_training_report.txt
 D backend/phase4f/experiments/phase4f_3r_freeze_report.txt
 D backend/phase4f/experiments/phase4f_4_controlled_gpu_experiment_report.txt
 D backend/phase4f/experiments/phase4f_4_experiment_manifest.json
 D backend/phase4f/experiments/phase4f_4_results.json
 D backend/phase4f/experiments/phase4f_4e_cuda_environment.json
 D backend/phase4f/experiments/phase4f_4e_cuda_environment_report.txt
 D backend/phase4f/experiments/requirements.txt
 D backend/phase4f/experiments/results/A0/evaluation_results.json
 D backend/phase4f/experiments/results/A0/metadata.json
 D backend/phase4f/experiments/results/A1/checkpoint_best/config.json
 D backend/phase4f/experiments/results/A1/checkpoint_best/tokenizer.json
 D backend/phase4f/experiments/results/A1/checkpoint_best/tokenizer_config.json
 D backend/phase4f/experiments/results/A1/evaluation_results.json
 D backend/phase4f/experiments/results/A1/training_metadata.json
 D backend/phase4f/experiments/results/A2/checkpoint_best/config.json
 D backend/phase4f/experiments/results/A2/checkpoint_best/tokenizer.json
 D backend/phase4f/experiments/results/A2/checkpoint_best/tokenizer_config.json
 D backend/phase4f/experiments/results/A2/evaluation_results.json
 D backend/phase4f/experiments/results/A2/training_metadata.json
 D backend/phase4f/experiments/results/A3/checkpoint_best/config.json
 D backend/phase4f/experiments/results/A3/checkpoint_best/tokenizer.json
 D backend/phase4f/experiments/results/A3/checkpoint_best/tokenizer_config.json
 D backend/phase4f/experiments/results/A3/evaluation_results.json
 D backend/phase4f/experiments/results/A3/training_metadata.json
 D backend/phase4f/experiments/results/all_results.json
 D backend/phase4f/experiments/run_experiment.py
 D backend/phase4f/experiments/train.py
 D backend/phase4f/freeze_gate.py
 D backend/phase4f/phase4f_1_dataset_audit_report.txt
 D backend/phase4f/phase4f_2_dataset_quality_gate_report.txt
 D backend/phase4f/phase4f_2r_dataset_balance_report.txt
 D backend/phase4f/phase4f_4r_manifest.json
 D backend/phase4f/phase4f_5/configs/a1_config.json
 D backend/phase4f/phase4f_5/configs/a2_config.json
 D backend/phase4f/phase4f_5/dataset/data_quality_gate.json
 D backend/phase4f/phase4f_5/dataset/derived_dataset.jsonl
 D backend/phase4f/phase4f_5/dataset/span_alignment_audit.json
 D backend/phase4f/phase4f_5/dataset/truncation_audit.json
 D backend/phase4f/phase4f_5/diagnostics/a0_forensics.json
 D backend/phase4f/phase4f_5/diagnostics/a1_forensics.json
 D backend/phase4f/phase4f_5/diagnostics/a2_forensics.json
 D backend/phase4f/phase4f_5/diagnostics/all_inference_results.json
 D backend/phase4f/phase4f_5/diagnostics/failure_taxonomy.json
 D backend/phase4f/phase4f_5/evaluation/evaluate.py
 D backend/phase4f/phase4f_5/evaluation/evaluation_protocol.json
 D backend/phase4f/phase4f_5/logs/a1_training.json
 D backend/phase4f/phase4f_5/logs/a2_training.json
 D backend/phase4f/phase4f_5/manifests/experiment_manifest.json
 D backend/phase4f/phase4f_5/manifests/final_experiment_manifest.json
 D backend/phase4f/phase4f_5/manifests/source_integrity.json
 D backend/phase4f/phase4f_5/manifests/split_manifest.json
 D backend/phase4f/phase4f_5/prepare_experiment.py
 D backend/phase4f/phase4f_5/reports/phase4f_5a_preparation_report.txt
 D backend/phase4f/phase4f_5/reports/phase4f_5b_training_report.txt
 D backend/phase4f/phase4f_5/results/a0_test.json
 D backend/phase4f/phase4f_5/results/a1_test.json
 D backend/phase4f/phase4f_5/results/a2_test.json
 D backend/phase4f/phase4f_5/results/comparison.json
 D backend/phase4f/phase4f_5/run_experiment.py
 D backend/phase4f/phase4f_5c/em_f1_gap_analysis.json
 D backend/phase4f/phase4f_5c/failure_matrix.json
 D backend/phase4f/phase4f_5c/generate_analysis.py
 D backend/phase4f/phase4f_5c/list_audit.json
 D backend/phase4f/phase4f_5c/long_context_audit.json
 D backend/phase4f/phase4f_5c/normalization_diagnostic.json
 D backend/phase4f/phase4f_5c/numeric_audit.json
 D backend/phase4f/phase4f_5c/per_category_comparison.json
 D backend/phase4f/phase4f_5c/phase4f_5c_manifest.json
 D backend/phase4f/phase4f_5c/production_strengths.json
 D backend/phase4f/phase4f_5c/reports/phase4f_5c_qa_analysis_report.txt
 D backend/phase4f/phase4f_5c/root_cause_analysis.json
 D backend/phase4f/phase4f_5c/table_audit.json
 D backend/phase4f/phase4f_5c/test_composition.json
 D backend/phase4f/phase4f_5c/training_curve_analysis.json
 D backend/phase4f/phase4f_5d/analysis/a0_benchmark_v1.json
 D backend/phase4f/phase4f_5d/analysis/a1_benchmark_v1.json
 D backend/phase4f/phase4f_5d/analysis/a2_benchmark_v1.json
 D backend/phase4f/phase4f_5d/analysis/benchmark_comparison.json
 D backend/phase4f/phase4f_5d/analysis/category_balance.json
 D backend/phase4f/phase4f_5d/analysis/duplicate_audit.json
 D backend/phase4f/phase4f_5d/analysis/gold_span_validation.json
 D backend/phase4f/phase4f_5d/analysis/leakage_audit.json
 D backend/phase4f/phase4f_5d/analysis/test_composition.json
 D backend/phase4f/phase4f_5d/analysis/unanswerable_audit.json
 D backend/phase4f/phase4f_5d/benchmark/benchmark_checksum.txt
 D backend/phase4f/phase4f_5d/benchmark/benchmark_manifest.json
 D backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl
 D backend/phase4f/phase4f_5d/build_benchmark.py
 D backend/phase4f/phase4f_5d/phase4f_5d_manifest.json
 D backend/phase4f/phase4f_5d/reports/phase4f_5d_benchmark_hardening_report.txt
 D backend/phase4f/phase4f_5e/analysis/capability_matrix.json
 D backend/phase4f/phase4f_5e/analysis/confidence_distribution.json
 D backend/phase4f/phase4f_5e/analysis/f1_gain_analysis.json
 D backend/phase4f/phase4f_5e/analysis/next_experiment_matrix.json
 D backend/phase4f/phase4f_5e/analysis/production_vs_experiment.json
 D backend/phase4f/phase4f_5e/analysis/root_cause_matrix.json
 D backend/phase4f/phase4f_5e/analysis/split_category_matrix.json
 D backend/phase4f/phase4f_5e/analysis/threshold_sweep.json
 D backend/phase4f/phase4f_5e/analysis/training_data_audit.json
 D backend/phase4f/phase4f_5e/analysis/unanswerable_audit.json
 D backend/phase4f/phase4f_5e/phase4f_5e_manifest.json
 D backend/phase4f/phase4f_5e/reports/phase4f_5e_qa_capability_audit.txt
 D backend/phase4f/phase4f_5e/run_analysis.py
 D backend/phase4f/phase4f_5f/dataset/experiment_f1_manifest.json
 D backend/phase4f/phase4f_5f/dataset/experiment_f1_quality_report.json
 D backend/phase4f/phase4f_5f/dataset/experiment_f1_split.json
 D backend/phase4f/phase4f_5f/f2/config/f2_config.json
 D backend/phase4f/phase4f_5f/f2/evaluation/f2_benchmark.json
 D backend/phase4f/phase4f_5f/f2/evaluation/f2_holdout.json
 D backend/phase4f/phase4f_5f/f2/evaluation/f2_validation.json
 D backend/phase4f/phase4f_5f/f2/logs/f2_training.json
 D backend/phase4f/phase4f_5f/f2/manifests/f2_dataset_ids.json
 D backend/phase4f/phase4f_5f/f2/manifests/f2_manifest.json
 D backend/phase4f/phase4f_5f/f2/reconciliation/f2_baseline_comparison.json
 D backend/phase4f/phase4f_5f/f2/reconciliation/f2_data_balance_audit.json
 D backend/phase4f/phase4f_5f/f2/reconciliation/f2_label_audit.json
 D backend/phase4f/phase4f_5f/f2/reconciliation/f2_no_answer_logic_audit.json
 D backend/phase4f/phase4f_5f/f2/reconciliation/f2_prediction_audit.json
 D backend/phase4f/phase4f_5f/f2/reconciliation/f2_root_cause_analysis.json
 D backend/phase4f/phase4f_5f/f2/reports/phase4f_5f_f2_final_report.txt
 D backend/phase4f/phase4f_5f/f2/reports/phase4f_5f_f2_reconciliation_report.txt
 D backend/phase4f/phase4f_5f/f2/reports/phase4f_5f_g_threshold_report.txt
 D backend/phase4f/phase4f_5f/f2/run_f2.py
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/benchmark_result.json
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/holdout_result.json
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/margin_sweep.json
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/raw_prediction_audit.json
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/raw_predictions_benchmark.json
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/raw_predictions_holdout.json
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/raw_predictions_validation.json
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/run_threshold_experiment.py
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/stability_analysis.json
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/threshold_experiment_manifest.json
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/threshold_sweep.json
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/validation_calibration.json
 D backend/phase4f/phase4f_5f/h/audits/duplicate_audit.json
 D backend/phase4f/phase4f_5f/h/audits/leakage_audit.json
 D backend/phase4f/phase4f_5f/h/audits/quality_gate_failures.json
 D backend/phase4f/phase4f_5f/h/audits/semantic_audit.json
 D backend/phase4f/phase4f_5f/h/candidates/all_candidates.jsonl
 D backend/phase4f/phase4f_5f/h/generate_h_candidates.py
 D backend/phase4f/phase4f_5f/h/manifests/h_manifest.json
 D backend/phase4f/phase4f_5f/h/pools/h10.jsonl
 D backend/phase4f/phase4f_5f/h/pools/h20.jsonl
 D backend/phase4f/phase4f_5f/h/pools/h30.jsonl
 D backend/phase4f/phase4f_5f/h/reports/phase4f_5f_h_dataset_design_report.txt
 D backend/phase4f/phase4f_5f/h1/config/f1_reconciled_ids.json
 D backend/phase4f/phase4f_5f/h1/config/h1_config.json
 D backend/phase4f/phase4f_5f/h1/evaluation/h1_benchmark.json
 D backend/phase4f/phase4f_5f/h1/evaluation/h1_holdout.json
 D backend/phase4f/phase4f_5f/h1/evaluation/h1_null_analysis.json
 D backend/phase4f/phase4f_5f/h1/evaluation/h1_validation.json
 D backend/phase4f/phase4f_5f/h1/logs/h1_training.json
 D backend/phase4f/phase4f_5f/h1/manifests/h1_manifest.json
 D backend/phase4f/phase4f_5f/h1/reports/phase4f_5f_h1_final_report.txt
 D backend/phase4f/phase4f_5f/h1/run_h1.py
 D backend/phase4f/phase4f_5f/h1_reconciliation/H1_RECONCILIATION_REPORT.md
 D backend/phase4f/phase4f_5f/h1_reconciliation/README.md
 D backend/phase4f/phase4f_5f/h1_reconciliation/checksums.txt
 D backend/phase4f/phase4f_5f/h1_reconciliation/h1_count_reconciliation.json
 D backend/phase4f/phase4f_5f/h1_reconciliation/h1_label_integrity.json
 D backend/phase4f/phase4f_5f/h1_reconciliation/h1_metric_recalculation.json
 D backend/phase4f/phase4f_5f/h1_reconciliation/h1_no_answer_analysis.json
 D backend/phase4f/phase4f_5f/h1_reconciliation/h1_null_score_analysis.json
 D backend/phase4f/phase4f_5f/h1_reconciliation/h1_overlap_report.json
 D backend/phase4f/phase4f_5f/h1_reconciliation/h1_protocol_audit.json
 D backend/phase4f/phase4f_5f/h1_reconciliation/h1_reconciled_comparison.json
 D backend/phase4f/phase4f_5f/phase4f_5f_f1_reconciliation_manifest.json
 D backend/phase4f/phase4f_5f/reconciliation/dataset_reconciliation.json
 D backend/phase4f/phase4f_5f/reconciliation/final_holdout_ids.json
 D backend/phase4f/phase4f_5f/reconciliation/final_training_ids.json
 D backend/phase4f/phase4f_5f/reconciliation/final_validation_ids.json
 D backend/phase4f/phase4f_5f/reconciliation/invalid_span_audit.json
 D backend/phase4f/phase4f_5f/reconciliation/training_protocol_audit.json
 D backend/phase4f/phase4f_5f/recovery/artifact_inventory.json
 D backend/phase4f/phase4f_5f/recovery/gpu_environment_report.json
 D backend/phase4f/phase4f_5f/recovery/gpu_environment_report.txt
 D backend/phase4f/phase4f_5f/recovery/phase4f_5f_recovery_report.txt
 D backend/phase4f/phase4f_5f/recovery/recovery_manifest.json
 D backend/phase4f/phase4f_5f/reports/phase4f_5f_f1_preparation_report.txt
 D backend/phase4f/phase4f_5f/reports/phase4f_5f_f1_reconciliation_report.txt
 D backend/phase4f/phase4f_5f/run_experiment.py
 D backend/phase4f/quality_gate.py
 D backend/phase4f/reconciliation/a0_reproduction.json
 D backend/phase4f/reconciliation/checkpoint_audit.json
 D backend/phase4f/reconciliation/cross_phase_evaluation_compatibility.json
 D backend/phase4f/reconciliation/dataset_label_audit.json
 D backend/phase4f/reconciliation/evaluation_parity_matrix.json
 D backend/phase4f/reconciliation/experiment_artifact_inventory.json
 D backend/phase4f/reconciliation/failure_taxonomy_reconciliation.json
 D backend/phase4f/reconciliation/manual_forensic_traces.json
 D backend/phase4f/reconciliation/model_initialization_audit.json
 D backend/phase4f/reconciliation/phase4f_4r_reconciliation_report.txt
 D backend/phase4f/reconciliation/token_span_audit.json
 D backend/phase4f/reconciliation/training_configuration_audit.json
 D backend/phase4f/training/__init__.py
 D backend/phase4f/training/configs.py
 D backend/phase4f/training/environment.json
 D backend/phase4f/training/train.py
 D backend/phase4f_qa_architecture_experiment_report.txt
 M backend/pytest.ini
 M backend/reliability/routes.py
 M backend/requirements.txt
 D backend/start_server.py
 D backend/test_browser_flow.py
 D backend/test_document_flow.py
 D backend/test_embedding_flow.py
 D backend/test_phase3d_evaluation.py
 D backend/test_phase3d_upload_integration.py
 D backend/test_phase3e_integration.py
 D backend/test_phase3e_validation.py
 D backend/test_phase3f_evaluation.py
 D backend/test_phase4b_evaluation.py
 D backend/test_phase4c_diagnostics.py
 D backend/test_phase6_reliability.py
 D backend/test_rag_flow.py
 D backend/test_real_browser.py
 M backend/tests/conftest.py
 D backend/tests/integration_http.py
 D backend/tests/phase3d_corpus.py
 D backend/tests/phase4b_corpus.py
 D backend/tests/test_answer_span.py
 D backend/tests/test_auth.py
 D backend/tests/test_brain_orchestration.py
 D backend/tests/test_brain_types.py
 D backend/tests/test_chat_unit.py
 D backend/tests/test_config_security.py
 D backend/tests/test_cors.py
 D backend/tests/test_database_url.py
 D backend/tests/test_file_validation.py
 D backend/tests/test_outcomes.py
 D backend/tests/test_phase3d_chunking.py
 D backend/tests/test_phase3d_context.py
 D backend/tests/test_phase3d_reconciliation.py
 D backend/tests/test_phase3e_processing.py
 D backend/tests/test_qa_answer_reconstruction.py
 D backend/tests/test_real_e2e_validation.py
 D backend/tests/test_settings.py
 D backend/tests/test_sql_safety.py
 D backend/tests/test_structured_extraction.py
 D backend/tests/test_verification_integrity.py
 M backend/verification/routes.py
 M package-lock.json
 M package.json
 M runbooks/README.md
 M runbooks/database-failure.md
 M runbooks/migration-failure.md
 M src/lib/api.ts
 M src/pages/ReliabilityPage.tsx
 M src/pages/VerificationPage.tsx
 M src/pages/WorkspacePage.tsx
 M src/types/index.ts
 M vite.config.ts
?? .dockerignore
?? .env.example
?? AGENTS.md
?? ARCHITECTURE.md
?? CONTEXT.md
?? DESIGN.md
?? Dockerfile.frontend
?? Field_Robotics_Deployment_and_Maintenance_Report.pdf
?? PRD.md
?? README.md
?? agents/README.md
?? agents/agentic-coding-agents/01-product-strategist-agent.md
?? agents/agentic-coding-agents/02-product-research-agent.md
?? agents/agentic-coding-agents/03-competitive-intelligence-agent.md
?? agents/agentic-coding-agents/04-requirements-agent.md
?? agents/agentic-coding-agents/05-ux-research-agent.md
?? agents/agentic-coding-agents/06-ux-ui-designer-agent.md
?? agents/agentic-coding-agents/07-accessibility-agent.md
?? agents/agentic-coding-agents/08-software-architect-agent.md
?? agents/agentic-coding-agents/09-frontend-architect-agent.md
?? agents/agentic-coding-agents/10-backend-architect-agent.md
?? agents/agentic-coding-agents/11-database-architect-agent.md
?? agents/agentic-coding-agents/12-api-architect-agent.md
?? agents/agentic-coding-agents/13-distributed-systems-agent.md
?? agents/agentic-coding-agents/14-security-architect-agent.md
?? agents/agentic-coding-agents/15-infrastructure-architect-agent.md
?? agents/agentic-coding-agents/16-frontend-coding-agent.md
?? agents/agentic-coding-agents/17-backend-coding-agent.md
?? agents/agentic-coding-agents/18-full-stack-agent.md
?? agents/agentic-coding-agents/19-database-engineer-agent.md
?? agents/agentic-coding-agents/20-api-integration-agent.md
?? agents/agentic-coding-agents/21-sdk-library-agent.md
?? agents/agentic-coding-agents/22-cli-agent.md
?? agents/agentic-coding-agents/23-desktop-agent.md
?? agents/agentic-coding-agents/24-mobile-agent.md
?? agents/agentic-coding-agents/25-ai-ml-architect-agent.md
?? agents/agentic-coding-agents/26-ml-fundamentals-agent.md
?? agents/agentic-coding-agents/27-data-science-agent.md
?? agents/agentic-coding-agents/28-data-engineering-agent.md
?? agents/agentic-coding-agents/29-feature-engineering-agent.md
?? agents/agentic-coding-agents/30-classical-ml-agent.md
?? agents/agentic-coding-agents/31-deep-learning-agent.md
?? agents/agentic-coding-agents/32-computer-vision-agent.md
?? agents/agentic-coding-agents/33-nlp-agent.md
?? agents/agentic-coding-agents/34-multimodal-ai-agent.md
?? agents/agentic-coding-agents/35-llm-engineer-agent.md
?? agents/agentic-coding-agents/36-rag-engineer-agent.md
?? agents/agentic-coding-agents/37-agentic-ai-engineer-agent.md
?? agents/agentic-coding-agents/38-fine-tuning-agent.md
?? agents/agentic-coding-agents/39-model-evaluation-agent.md
?? agents/agentic-coding-agents/40-prompt-engineering-agent.md
?? agents/agentic-coding-agents/41-embeddings-vector-search-agent.md
?? agents/agentic-coding-agents/42-knowledge-graph-agent.md
?? agents/agentic-coding-agents/43-ai-safety-guardrails-agent.md
?? agents/agentic-coding-agents/44-ml-pipeline-agent.md
?? agents/agentic-coding-agents/45-mlops-agent.md
?? agents/agentic-coding-agents/46-model-serving-agent.md
?? agents/agentic-coding-agents/47-gpu-compute-optimization-agent.md
?? agents/agentic-coding-agents/48-model-compression-agent.md
?? agents/agentic-coding-agents/49-data-model-versioning-agent.md
?? agents/agentic-coding-agents/50-ai-cost-optimization-agent.md
?? agents/agentic-coding-agents/51-test-architect-agent.md
?? agents/agentic-coding-agents/52-unit-testing-agent.md
?? agents/agentic-coding-agents/53-integration-testing-agent.md
?? agents/agentic-coding-agents/54-e2e-testing-agent.md
?? agents/agentic-coding-agents/55-api-testing-agent.md
?? agents/agentic-coding-agents/56-performance-testing-agent.md
?? agents/agentic-coding-agents/57-ai-evaluation-agent.md
?? agents/agentic-coding-agents/58-security-testing-agent.md
?? agents/agentic-coding-agents/59-code-review-agent.md
?? agents/agentic-coding-agents/60-debugging-agent.md
?? agents/agentic-coding-agents/61-reliability-agent.md
?? agents/agentic-coding-agents/62-devops-agent.md
?? agents/agentic-coding-agents/63-cloud-engineer-agent.md
?? agents/agentic-coding-agents/64-docker-container-agent.md
?? agents/agentic-coding-agents/65-kubernetes-agent.md
?? agents/agentic-coding-agents/66-infrastructure-as-code-agent.md
?? agents/agentic-coding-agents/67-deployment-agent.md
?? agents/agentic-coding-agents/68-observability-agent.md
?? agents/agentic-coding-agents/69-incident-response-agent.md
?? agents/agentic-coding-agents/70-sre-agent.md
?? agents/agentic-coding-agents/71-cost-finops-agent.md
?? agents/agentic-coding-agents/72-application-security-agent.md
?? agents/agentic-coding-agents/73-dependency-security-agent.md
?? agents/agentic-coding-agents/74-secrets-security-agent.md
?? agents/agentic-coding-agents/75-identity-auth-agent.md
?? agents/agentic-coding-agents/76-privacy-agent.md
?? agents/agentic-coding-agents/77-threat-modeling-agent.md
?? agents/agentic-coding-agents/78-ai-security-agent.md
?? agents/agentic-coding-agents/79-documentation-agent.md
?? agents/agentic-coding-agents/80-api-documentation-agent.md
?? agents/agentic-coding-agents/81-architecture-documentation-agent.md
?? agents/agentic-coding-agents/82-codebase-knowledge-agent.md
?? agents/agentic-coding-agents/83-changelog-release-agent.md
?? agents/agentic-coding-agents/84-git-agent.md
?? agents/agentic-coding-agents/85-dependency-management-agent.md
?? agents/agentic-coding-agents/86-refactoring-agent.md
?? agents/agentic-coding-agents/87-legacy-migration-agent.md
?? agents/agentic-coding-agents/88-performance-optimization-agent.md
?? agents/agentic-coding-agents/89-database-optimization-agent.md
?? agents/agentic-coding-agents/90-accessibility-ui-qa-agent.md
?? agents/agentic-coding-agents/AGENT-CONTRACT.md
?? agents/agentic-coding-agents/README.md
?? agents/ai-agent.md
?? agents/backend-agent.md
?? agents/coordinator.md
?? agents/database-agent.md
?? agents/evaluation-agent.md
?? agents/frontend-agent.md
?? agents/security-agent.md
?? agents/test-agent.md
?? agents/verifier.md
?? backend/.dockerignore
?? backend/Dockerfile
?? backend/architecture/EVALUATION_SAFETY_MASTER_REGISTER.md
?? backend/architecture/IMPLEMENTATION_REPORT_2026-09-30.md
?? backend/architecture/PATH_MIGRATION.md
?? backend/architecture/PHASE0_CLOSURE_2026-10-09.md
?? backend/architecture/PHASE0_FAILURE_AUDIT_2026-10-09.md
?? backend/architecture/PHASE1_GROUNDED_ANSWERING_PLAN_2026-10-09.md
?? backend/architecture/REPOSITORY_AUDIT_2026-09-30.md
?? backend/architecture/STEP0_5_EVALUATION_RUNNER_SAFETY_AUDIT_2026-10-09.md
?? backend/architecture/STEP0_7_PHASE3D_DESTRUCTIVE_CLEANUP_REMEDIATION_2026-10-09.md
?? backend/architecture/STEP0_8_PHASE3D_EVALUATION_CLEANUP_REMEDIATION_2026-10-09.md
?? backend/architecture/STEP0_9_PHASE3E_INTEGRATION_CLEANUP_REMEDIATION_2026-10-09.md
?? backend/architecture/STEP0_EVALUATION_INFRASTRUCTURE_HARDENING_2026-10-09.md
?? backend/architecture/STEP1_0_PHASE3E_VALIDATION_CLEANUP_REMEDIATION_2026-10-09.md
?? backend/architecture/STEP1_1_PHASE3F_EVALUATION_CLEANUP_REMEDIATION_2026-10-09.md
?? backend/architecture/STEP1_2_PHASE4B_EVALUATION_CLEANUP_REMEDIATION_2026-10-09.md
?? backend/architecture/STEP1_4_POSTGRESQL_VERIFICATION_READINESS_ASSESSMENT_2026-10-09.md
?? backend/architecture/STEP1_5_EVALUATION_SAFETY_P0_REMEDIATION_PLAN_2026-10-09.md
?? backend/architecture/STEP1_6A_GUARD_FIRST_REMEDIATION_2026-10-10.md
?? backend/architecture/STEP1_6B_ISOLATION_GUARD_REMEDIATION_2026-10-10.md
?? backend/architecture/STEP1_6C_GUARD_FIRST_STRUCTURE_RUNNERS_2026-10-10.md
?? backend/architecture/STEP1_6D_PRE_ENGINE_TARGET_VALIDATION_2026-10-10.md
?? backend/architecture/STEP1_6E_REMAINING_RUNNER_INITIALIZATION_AUDIT_2026-10-10.md
?? backend/architecture/STEP1_6F_LEGACY_RUNNER_AND_CLEANUP_SAFETY_2026-10-11.md
?? backend/architecture/STEP1_6G_RUNNER_AND_FIXTURE_TARGET_SAFETY_2026-10-11.md
?? backend/architecture/STEP1_6H_DISPOSABLE_DATABASE_AUTHORIZATION_2026-10-11.md
?? backend/architecture/STEP1_6I_UNIFIED_DESTRUCTIVE_TARGET_AUTHORIZATION_2026-10-11.md
?? backend/architecture/STEP1_6J_FAIL_CLOSED_DESTRUCTIVE_EXECUTION_2026-10-12.md
?? backend/architecture/STEP1_6K_LIFECYCLE_AUTHORIZATION_HARDENING_2026-10-12.md
?? backend/architecture/STEP1_6L_FUNCTION_LEVEL_CLEANUP_AUTHORIZATION_2026-10-12.md
?? backend/architecture/STEP1_6M_READ_ONLY_POSTGRESQL_READINESS_REVIEW_2026-10-12.md
?? backend/architecture/phase4f_6/ARCHITECTURE_DECISION_RECORD.md
?? backend/architecture/phase4f_6/CURRENT_ARCHITECTURE.md
?? backend/architecture/phase4f_6/DOMAIN_MODEL.md
?? backend/architecture/phase4f_6/MODULE_SEAMS.md
?? backend/architecture/phase4f_6/NEXT_STAGE_RAG_EXECUTION_PLAN.md
?? backend/architecture/phase4f_6/PHASE4F6_ARCHITECTURE_AUDIT.md
?? backend/architecture/phase4f_6/QUESTION_WORKFLOW_MATRIX.md
?? backend/architecture/phase4f_6/TARGET_ARCHITECTURE.md
?? backend/architecture/phase4f_6/decision/ABSTENTION_GATE_RESCORING.json
?? backend/architecture/phase4f_6/decision/ABSTENTION_GATE_RESCORING.md
?? backend/architecture/phase4f_6/decision/ANSWERABILITY_SIGNAL_FORENSICS.json
?? backend/architecture/phase4f_6/decision/ANSWERABILITY_SIGNAL_FORENSICS.md
?? backend/architecture/phase4f_6/decision/ARCHITECTURE_MIGRATION_GATE.md
?? backend/architecture/phase4f_6/decision/AUC_INFLUENCE_JACKKNIFE_FORENSICS.json
?? backend/architecture/phase4f_6/decision/AUC_INFLUENCE_JACKKNIFE_FORENSICS.md
?? backend/architecture/phase4f_6/decision/CLS_DIRECTION_REVERSAL_FORENSICS.json
?? backend/architecture/phase4f_6/decision/CLS_DIRECTION_REVERSAL_FORENSICS.md
?? backend/architecture/phase4f_6/decision/DECISION_SAFETY_CHECK.json
?? backend/architecture/phase4f_6/decision/E0_CHUNK_MANIFEST.json
?? backend/architecture/phase4f_6/decision/E0_CORPUS_MANIFEST.json
?? backend/architecture/phase4f_6/decision/E0_ERRATUM_2026-09-27.md
?? backend/architecture/phase4f_6/decision/E0_MEDIA_DETECTION_RECORD.json
?? backend/architecture/phase4f_6/decision/E0_OFFLINE_RUNTIME_PROVISIONING.md
?? backend/architecture/phase4f_6/decision/E0_PREDICTION_PROVENANCE_2026-09-28.md
?? backend/architecture/phase4f_6/decision/E0_PREREQUISITE_STATUS.md
?? backend/architecture/phase4f_6/decision/E0_PROTOCOL.md
?? backend/architecture/phase4f_6/decision/E0_READINESS_CHECK.md
?? backend/architecture/phase4f_6/decision/E0_RETRIEVAL_RUNTIME_READINESS.md
?? backend/architecture/phase4f_6/decision/E0_RETRIEVAL_RUNTIME_RESUME.md
?? backend/architecture/phase4f_6/decision/E0_RETRIEVAL_RUN_MANIFEST.json
?? backend/architecture/phase4f_6/decision/E0_RUNTIME_HANDOFF_MANIFEST.json
?? backend/architecture/phase4f_6/decision/E0_SCHEMA.json
?? backend/architecture/phase4f_6/decision/E0_SOURCE_PROVENANCE.md
?? backend/architecture/phase4f_6/decision/EXPERIMENT_CANDIDATE_MATRIX.md
?? backend/architecture/phase4f_6/decision/EXPERIMENT_CONTROL_MATRIX.md
?? backend/architecture/phase4f_6/decision/ISO_COVERAGE_RESCORING.json
?? backend/architecture/phase4f_6/decision/ISO_COVERAGE_RESCORING.md
?? backend/architecture/phase4f_6/decision/MODEL_40MIN_EVALUATION.json
?? backend/architecture/phase4f_6/decision/MODEL_40MIN_EVALUATION.md
?? backend/architecture/phase4f_6/decision/NEXT_EXPERIMENT_DECISION.md
?? backend/architecture/phase4f_6/decision/PHASE4F6B_RECONCILIATION.md
?? backend/architecture/phase4f_6/decision/PHASE4F6C_RECONCILIATION.md
?? backend/architecture/phase4f_6/decision/PROTOCOL_V2_SPAN_SELECTION_ROLLOUT.json
?? backend/architecture/phase4f_6/decision/PROTOCOL_V2_SPAN_SELECTION_ROLLOUT.md
?? backend/architecture/phase4f_6/decision/QA_HYPOTHESIS_MATRIX.md
?? backend/architecture/phase4f_6/decision/RECONSTRUCTION_BOUND.json
?? backend/architecture/phase4f_6/decision/RECONSTRUCTION_BOUND.md
?? backend/architecture/phase4f_6/decision/SCORE_STATISTIC_ISO_K47.json
?? backend/architecture/phase4f_6/decision/SCORE_STATISTIC_ISO_K47.md
?? backend/architecture/phase4f_6/decision/SCORE_STATISTIC_ISO_K95.json
?? backend/architecture/phase4f_6/decision/SCORE_STATISTIC_ISO_K95.md
?? backend/architecture/phase4f_6/decision/SPAN_BOUNDARY_FORENSICS.json
?? backend/architecture/phase4f_6/decision/SPAN_BOUNDARY_FORENSICS.md
?? backend/architecture/phase4f_6/decision/SPAN_SELECTION_PROTOCOL_EXPERIMENT.json
?? backend/architecture/phase4f_6/decision/SPAN_SELECTION_PROTOCOL_EXPERIMENT.md
?? backend/architecture/phase4f_6/e0_diagnostics/chunks/api_docs_lambda.jsonl
?? backend/architecture/phase4f_6/e0_diagnostics/chunks/company_history_eta.jsonl
?? backend/architecture/phase4f_6/e0_diagnostics/chunks/dataset_desc_mu.jsonl
?? backend/architecture/phase4f_6/e0_diagnostics/chunks/financial_report_q3.jsonl
?? backend/architecture/phase4f_6/e0_diagnostics/chunks/legal_contract_epsilon.jsonl
?? backend/architecture/phase4f_6/e0_diagnostics/chunks/unanswerable_corpus.jsonl
?? backend/architecture/phase4f_6/e0_diagnostics/diagnostics/answerability_signal_bootstrap.json
?? backend/architecture/phase4f_6/e0_diagnostics/diagnostics/auc_influence_jackknife.json
?? backend/architecture/phase4f_6/e0_diagnostics/diagnostics/chunk_evidence_results.jsonl
?? backend/architecture/phase4f_6/e0_diagnostics/diagnostics/cls_direction_reversal_bootstrap.json
?? backend/architecture/phase4f_6/e0_diagnostics/diagnostics/embedding_offline_verification.json
?? backend/architecture/phase4f_6/e0_diagnostics/diagnostics/model_40min_predictions.json
?? backend/architecture/phase4f_6/e0_diagnostics/diagnostics/provenance_results.jsonl
?? backend/architecture/phase4f_6/e0_diagnostics/diagnostics/runtime_validation_schema.json
?? backend/architecture/phase4f_6/e0_diagnostics/diagnostics/summary.json
?? backend/architecture/phase4f_6/e0_diagnostics/offline_runtime_checklist.json
?? backend/architecture/phase4f_6/e0_diagnostics/retrieval_schema_requirements.json
?? backend/architecture/phase4f_6/e0_diagnostics/source_corpus/api_docs_lambda.json
?? backend/architecture/phase4f_6/e0_diagnostics/source_corpus/company_history_eta.json
?? backend/architecture/phase4f_6/e0_diagnostics/source_corpus/dataset_desc_mu.json
?? backend/architecture/phase4f_6/e0_diagnostics/source_corpus/financial_report_q3.json
?? backend/architecture/phase4f_6/e0_diagnostics/source_corpus/legal_contract_epsilon.json
?? backend/architecture/phase4f_6/e0_diagnostics/source_corpus/unanswerable_corpus.json
?? backend/architecture/phase4f_6/e0_diagnostics/tools/answerability_signal_forensics.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/auc_influence_jackknife_forensics.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/build_e0_prereqs.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/cls_direction_reversal_forensics.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/detect_runtime_media.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/reconstruction_bound.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/rescore_abstention_gate.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/rescore_iso_coverage.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/rescore_score_statistics_k47.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/rescore_score_statistics_k95.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/run_model_40min_eval.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/span_boundary_forensics.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/span_selection_protocol_experiment.py
?? backend/docker-entrypoint.sh
?? backend/documents/insights.py
?? backend/documents/parser.py
?? backend/documents/structure.py
?? backend/documents/tables.py
?? backend/evaluation/README.md
?? backend/evaluation/artifacts.py
?? backend/evaluation/baselines/__init__.py
?? backend/evaluation/baselines/dual_path/__init__.py
?? backend/evaluation/baselines/structure_only/__init__.py
?? backend/evaluation/baselines/vector_only/__init__.py
?? backend/evaluation/datasets/__init__.py
?? backend/evaluation/datasets/heading_corpus.py
?? backend/evaluation/datasets/phase3d_corpus.py
?? backend/evaluation/datasets/phase4b_corpus.py
?? backend/evaluation/datasets/structure_discriminating_v1.py
?? backend/evaluation/datasets/structure_eval_corpus.py
?? backend/evaluation/denominator_sensitivity.py
?? backend/evaluation/experiments/__init__.py
?? backend/evaluation/experiments/run_dual_path_ablation.py
?? backend/evaluation/experiments/run_phase3d_evaluation.py
?? backend/evaluation/experiments/run_phase3d_upload_integration.py
?? backend/evaluation/experiments/run_phase3e_integration.py
?? backend/evaluation/experiments/run_phase3e_validation.py
?? backend/evaluation/experiments/run_phase3f_evaluation.py
?? backend/evaluation/experiments/run_phase4b_evaluation.py
?? backend/evaluation/experiments/run_phase4c_diagnostics.py
?? backend/evaluation/experiments/run_structure_confirmation.py
?? backend/evaluation/experiments/run_structure_element_measurement.py
?? backend/evaluation/experiments/run_structure_rrf_calibration.py
?? backend/evaluation/experiments/run_table_evidence_measurement.py
?? backend/evaluation/experiments/synthesize_structure_discriminating.py
?? backend/evaluation/isolation.py
?? backend/evaluation/metrics/__init__.py
?? backend/evaluation/qa_metrics.py
?? backend/evaluation/reports/__init__.py
?? backend/evaluation/reports/ablation_A.json
?? backend/evaluation/reports/ablation_A.md
?? backend/evaluation/reports/ablation_B.json
?? backend/evaluation/reports/ablation_B.md
?? backend/evaluation/reports/ablation_C.json
?? backend/evaluation/reports/ablation_C.md
?? backend/evaluation/reports/ablation_D.json
?? backend/evaluation/reports/ablation_D.md
?? backend/evaluation/reports/ablation_config.json
?? backend/evaluation/reports/ablation_heading_A.json
?? backend/evaluation/reports/ablation_heading_A.md
?? backend/evaluation/reports/ablation_heading_B.json
?? backend/evaluation/reports/ablation_heading_B.md
?? backend/evaluation/reports/ablation_heading_C.json
?? backend/evaluation/reports/ablation_heading_C.md
?? backend/evaluation/reports/ablation_heading_D.json
?? backend/evaluation/reports/ablation_heading_D.md
?? backend/evaluation/reports/ablation_heading_config.json
?? backend/evaluation/reports/ablation_structure_discriminating_A.json
?? backend/evaluation/reports/ablation_structure_discriminating_A.md
?? backend/evaluation/reports/ablation_structure_discriminating_B.json
?? backend/evaluation/reports/ablation_structure_discriminating_B.md
?? backend/evaluation/reports/ablation_structure_discriminating_C.json
?? backend/evaluation/reports/ablation_structure_discriminating_C.md
?? backend/evaluation/reports/ablation_structure_discriminating_D.json
?? backend/evaluation/reports/ablation_structure_discriminating_D.md
?? backend/evaluation/reports/ablation_structure_discriminating_config.json
?? backend/evaluation/reports/denominator_sensitivity.json
?? backend/evaluation/reports/denominator_sensitivity.md
?? backend/evaluation/reports/structural_retrieval_fix_report.md
?? backend/evaluation/reports/structural_retrieval_reachability_audit.md
?? backend/evaluation/reports/structure_confirmation.json
?? backend/evaluation/reports/structure_confirmation_report.md
?? backend/evaluation/reports/structure_discriminating_ablation_report.md
?? backend/evaluation/reports/structure_discriminating_analysis.json
?? backend/evaluation/reports/structure_discriminating_v1_audit.md
?? backend/evaluation/reports/structure_element_measurement_analysis.json
?? backend/evaluation/reports/structure_element_measurement_control.json
?? backend/evaluation/reports/structure_element_measurement_report.md
?? backend/evaluation/reports/structure_element_measurement_treatment.json
?? backend/evaluation/reports/structure_eval.json
?? backend/evaluation/reports/structure_eval.md
?? backend/evaluation/reports/structure_rrf_calibration.json
?? backend/evaluation/reports/structure_rrf_calibration_report.md
?? backend/evaluation/reports/table_evidence_architecture.md
?? backend/evaluation/reports/table_evidence_measurement_analysis.json
?? backend/evaluation/reports/table_evidence_measurement_control.json
?? backend/evaluation/reports/table_evidence_measurement_report.md
?? backend/evaluation/reports/table_evidence_measurement_treatment.json
?? backend/evaluation/retrieval_metrics.py
?? backend/evaluation/runner.py
?? backend/evaluation/schemas.py
?? backend/evaluation/structure_eval.py
?? backend/graph/__init__.py
?? backend/graph/evidence.py
?? backend/graph/models.py
?? backend/graph/service.py
?? backend/migrations/versions/005_add_document_graph.py
?? backend/migrations/versions/006_add_structure_elements.py
?? backend/migrations/versions/007_add_table_rows.py
?? backend/models/media-verification/MANIFEST.json
?? backend/models/media-verification/config.json
?? backend/models/media-verification/preprocessor_config.json
?? backend/models/whisper/small/config.json
?? backend/models/whisper/small/model.bin
?? backend/models/whisper/small/tokenizer.json
?? backend/models/whisper/small/vocabulary.txt
?? backend/phases/phase3d_evaluation_report.json
?? backend/phases/phase3f_evaluation_report.json
?? backend/phases/phase3f_validation_report.txt
?? backend/phases/phase3g_pipeline_audit.txt
?? backend/phases/phase4a_qa_failure_audit.txt
?? backend/phases/phase4b_evaluation_report.json
?? backend/phases/phase4b_qa_evaluation_report.txt
?? backend/phases/phase4c_failure_matrix.json
?? backend/phases/phase4c_qa_failure_isolation_report.txt
?? backend/phases/phase4d/__init__.py
?? backend/phases/phase4d/__main__.py
?? backend/phases/phase4d/evaluate_candidates.py
?? backend/phases/phase4d/generate_report.py
?? backend/phases/phase4d/oracle_eval.py
?? backend/phases/phase4d/reconciliation.py
?? backend/phases/phase4d/train.py
?? backend/phases/phase4d/training_data.py
?? backend/phases/phase4d_1_reconciliation.json
?? backend/phases/phase4d_1_reconciliation_report.txt
?? backend/phases/phase4d_experiment_results.json
?? backend/phases/phase4d_oracle_baseline_results.json
?? backend/phases/phase4d_qa_model_improvement_report.txt
?? backend/phases/phase4e/__init__.py
?? backend/phases/phase4e/capability_analysis.py
?? backend/phases/phase4e/generate_report.py
?? backend/phases/phase4e_capability_matrix.json
?? backend/phases/phase4e_diagnostic_results.json
?? backend/phases/phase4e_qa_architecture_analysis.txt
?? backend/phases/phase4f/__init__.py
?? backend/phases/phase4f/balance_gate.py
?? backend/phases/phase4f/dataset/__init__.py
?? backend/phases/phase4f/dataset/dataset_manifest.json
?? backend/phases/phase4f/dataset/dataset_manifest_v3.json
?? backend/phases/phase4f/dataset/dataset_manifest_v3_1.json
?? backend/phases/phase4f/dataset/dataset_metadata.json
?? backend/phases/phase4f/dataset/dataset_quality_report.json
?? backend/phases/phase4f/dataset/dataset_quality_report_v3.json
?? backend/phases/phase4f/dataset/dataset_quality_report_v3_1.json
?? backend/phases/phase4f/dataset/expand_and_audit.py
?? backend/phases/phase4f/dataset/generator.py
?? backend/phases/phase4f/dataset/training_data.jsonl
?? backend/phases/phase4f/dataset/training_data_v3.jsonl
?? backend/phases/phase4f/dataset/training_data_v3_1.jsonl
?? backend/phases/phase4f/experiments/evaluate.py
?? backend/phases/phase4f/experiments/experiment_manifest.json
?? backend/phases/phase4f/experiments/final_gpu_package/README_GPU_EXECUTION.md
?? backend/phases/phase4f/experiments/final_gpu_package/dataset/training_data_v3_1.jsonl
?? backend/phases/phase4f/experiments/final_gpu_package/dataset_checksum.txt
?? backend/phases/phase4f/experiments/final_gpu_package/evaluation/evaluate.py
?? backend/phases/phase4f/experiments/final_gpu_package/expected_output_structure.txt
?? backend/phases/phase4f/experiments/final_gpu_package/final_gpu_package_manifest.json
?? backend/phases/phase4f/experiments/final_gpu_package/production_model_checksum.txt
?? backend/phases/phase4f/experiments/final_gpu_package/requirements.txt
?? backend/phases/phase4f/experiments/final_gpu_package/training/experiment_config.json
?? backend/phases/phase4f/experiments/final_gpu_package/training/train.py
?? backend/phases/phase4f/experiments/phase4f_3_results.json
?? backend/phases/phase4f/experiments/phase4f_3_training_report.txt
?? backend/phases/phase4f/experiments/phase4f_3r_freeze_report.txt
?? backend/phases/phase4f/experiments/phase4f_4_controlled_gpu_experiment_report.txt
?? backend/phases/phase4f/experiments/phase4f_4_experiment_manifest.json
?? backend/phases/phase4f/experiments/phase4f_4_results.json
?? backend/phases/phase4f/experiments/phase4f_4e_cuda_environment.json
?? backend/phases/phase4f/experiments/phase4f_4e_cuda_environment_report.txt
?? backend/phases/phase4f/experiments/requirements.txt
?? backend/phases/phase4f/experiments/results.pre_joint_selection_v1/all_results.json
?? backend/phases/phase4f/experiments/results/A0/evaluation_results.json
?? backend/phases/phase4f/experiments/results/A0/metadata.json
?? backend/phases/phase4f/experiments/results/A1/checkpoint_best/config.json
?? backend/phases/phase4f/experiments/results/A1/checkpoint_best/tokenizer.json
?? backend/phases/phase4f/experiments/results/A1/checkpoint_best/tokenizer_config.json
?? backend/phases/phase4f/experiments/results/A1/evaluation_results.json
?? backend/phases/phase4f/experiments/results/A1/training_metadata.json
?? backend/phases/phase4f/experiments/results/A2/checkpoint_best/config.json
?? backend/phases/phase4f/experiments/results/A2/checkpoint_best/tokenizer.json
?? backend/phases/phase4f/experiments/results/A2/checkpoint_best/tokenizer_config.json
?? backend/phases/phase4f/experiments/results/A2/evaluation_results.json
?? backend/phases/phase4f/experiments/results/A2/training_metadata.json
?? backend/phases/phase4f/experiments/results/A3/checkpoint_best/config.json
?? backend/phases/phase4f/experiments/results/A3/checkpoint_best/tokenizer.json
?? backend/phases/phase4f/experiments/results/A3/checkpoint_best/tokenizer_config.json
?? backend/phases/phase4f/experiments/results/A3/evaluation_results.json
?? backend/phases/phase4f/experiments/results/A3/training_metadata.json
?? backend/phases/phase4f/experiments/results/all_results.json
?? backend/phases/phase4f/experiments/results_reconstruction_fix/A0/evaluation_results.json
?? backend/phases/phase4f/experiments/results_reconstruction_fix/A0_gpu_package/evaluation_results.json
?? backend/phases/phase4f/experiments/run_experiment.py
?? backend/phases/phase4f/experiments/train.py
?? backend/phases/phase4f/freeze_gate.py
?? backend/phases/phase4f/gate_common.py
?? backend/phases/phase4f/phase4f_1_dataset_audit_report.txt
?? backend/phases/phase4f/phase4f_2_dataset_quality_gate_report.txt
?? backend/phases/phase4f/phase4f_2r_dataset_balance_report.txt
?? backend/phases/phase4f/phase4f_4r_manifest.json
?? backend/phases/phase4f/phase4f_5/configs/a1_config.json
?? backend/phases/phase4f/phase4f_5/configs/a2_config.json
?? backend/phases/phase4f/phase4f_5/dataset/data_quality_gate.json
?? backend/phases/phase4f/phase4f_5/dataset/derived_dataset.jsonl
?? backend/phases/phase4f/phase4f_5/dataset/span_alignment_audit.json
?? backend/phases/phase4f/phase4f_5/dataset/truncation_audit.json
?? backend/phases/phase4f/phase4f_5/diagnostics/a0_forensics.json
?? backend/phases/phase4f/phase4f_5/diagnostics/a1_forensics.json
?? backend/phases/phase4f/phase4f_5/diagnostics/a2_forensics.json
?? backend/phases/phase4f/phase4f_5/diagnostics/all_inference_results.json
?? backend/phases/phase4f/phase4f_5/diagnostics/failure_taxonomy.json
?? backend/phases/phase4f/phase4f_5/evaluation/A0_test_results.json
?? backend/phases/phase4f/phase4f_5/evaluation/A1_test_results.json
?? backend/phases/phase4f/phase4f_5/evaluation/A2_test_results.json
?? backend/phases/phase4f/phase4f_5/evaluation/evaluate.py
?? backend/phases/phase4f/phase4f_5/evaluation/evaluation_protocol.json
?? backend/phases/phase4f/phase4f_5/logs/a1_training.json
?? backend/phases/phase4f/phase4f_5/logs/a2_training.json
?? backend/phases/phase4f/phase4f_5/manifests/experiment_manifest.json
?? backend/phases/phase4f/phase4f_5/manifests/final_experiment_manifest.json
?? backend/phases/phase4f/phase4f_5/manifests/source_integrity.json
?? backend/phases/phase4f/phase4f_5/manifests/split_manifest.json
?? backend/phases/phase4f/phase4f_5/prepare_experiment.py
?? backend/phases/phase4f/phase4f_5/reports/phase4f_5a_preparation_report.txt
?? backend/phases/phase4f/phase4f_5/reports/phase4f_5b_training_report.txt
?? backend/phases/phase4f/phase4f_5/results.pre_joint_selection_v1/a0_test.json
?? backend/phases/phase4f/phase4f_5/results.pre_joint_selection_v1/a1_test.json
?? backend/phases/phase4f/phase4f_5/results.pre_joint_selection_v1/a2_test.json
?? backend/phases/phase4f/phase4f_5/results.pre_joint_selection_v1/comparison.json
?? backend/phases/phase4f/phase4f_5/results.pre_reconstruction_fix/a0_test.json
?? backend/phases/phase4f/phase4f_5/results.pre_reconstruction_fix/a1_test.json
?? backend/phases/phase4f/phase4f_5/results.pre_reconstruction_fix/a2_test.json
?? backend/phases/phase4f/phase4f_5/results.pre_reconstruction_fix/comparison.json
?? backend/phases/phase4f/phase4f_5/results/a0_test.json
?? backend/phases/phase4f/phase4f_5/results/a0_test.protocol_v1_argmaxchain.json
?? backend/phases/phase4f/phase4f_5/results/a0_test.protocol_v2_joint.json
?? backend/phases/phase4f/phase4f_5/results/a1_test.json
?? backend/phases/phase4f/phase4f_5/results/a1_test.protocol_v1_argmaxchain.json
?? backend/phases/phase4f/phase4f_5/results/a1_test.protocol_v2_joint.json
?? backend/phases/phase4f/phase4f_5/results/a2_test.json
?? backend/phases/phase4f/phase4f_5/results/a2_test.protocol_v1_argmaxchain.json
?? backend/phases/phase4f/phase4f_5/results/a2_test.protocol_v2_joint.json
?? backend/phases/phase4f/phase4f_5/results/comparison.json
?? backend/phases/phase4f/phase4f_5/run_experiment.py
?? backend/phases/phase4f/phase4f_5c/em_f1_gap_analysis.json
?? backend/phases/phase4f/phase4f_5c/failure_matrix.json
?? backend/phases/phase4f/phase4f_5c/generate_analysis.py
?? backend/phases/phase4f/phase4f_5c/list_audit.json
?? backend/phases/phase4f/phase4f_5c/long_context_audit.json
?? backend/phases/phase4f/phase4f_5c/normalization_diagnostic.json
?? backend/phases/phase4f/phase4f_5c/numeric_audit.json
?? backend/phases/phase4f/phase4f_5c/per_category_comparison.json
?? backend/phases/phase4f/phase4f_5c/phase4f_5c_manifest.json
?? backend/phases/phase4f/phase4f_5c/production_strengths.json
?? backend/phases/phase4f/phase4f_5c/reports/phase4f_5c_qa_analysis_report.txt
?? backend/phases/phase4f/phase4f_5c/root_cause_analysis.json
?? backend/phases/phase4f/phase4f_5c/table_audit.json
?? backend/phases/phase4f/phase4f_5c/test_composition.json
?? backend/phases/phase4f/phase4f_5c/training_curve_analysis.json
?? backend/phases/phase4f/phase4f_5d/analysis.pre_joint_selection_v1/a0_benchmark_v1.json
?? backend/phases/phase4f/phase4f_5d/analysis.pre_joint_selection_v1/a1_benchmark_v1.json
?? backend/phases/phase4f/phase4f_5d/analysis.pre_joint_selection_v1/a2_benchmark_v1.json
?? backend/phases/phase4f/phase4f_5d/analysis.pre_joint_selection_v1/benchmark_comparison.json
?? backend/phases/phase4f/phase4f_5d/analysis.pre_joint_selection_v1/category_balance.json
?? backend/phases/phase4f/phase4f_5d/analysis.pre_joint_selection_v1/duplicate_audit.json
?? backend/phases/phase4f/phase4f_5d/analysis.pre_joint_selection_v1/gold_span_validation.json
?? backend/phases/phase4f/phase4f_5d/analysis.pre_joint_selection_v1/leakage_audit.json
?? backend/phases/phase4f/phase4f_5d/analysis.pre_joint_selection_v1/test_composition.json
?? backend/phases/phase4f/phase4f_5d/analysis.pre_joint_selection_v1/unanswerable_audit.json
?? backend/phases/phase4f/phase4f_5d/analysis/a0_benchmark_v1.json
?? backend/phases/phase4f/phase4f_5d/analysis/a1_benchmark_v1.json
?? backend/phases/phase4f/phase4f_5d/analysis/a2_benchmark_v1.json
?? backend/phases/phase4f/phase4f_5d/analysis/benchmark_comparison.json
?? backend/phases/phase4f/phase4f_5d/analysis/category_balance.json
?? backend/phases/phase4f/phase4f_5d/analysis/duplicate_audit.json
?? backend/phases/phase4f/phase4f_5d/analysis/gold_span_validation.json
?? backend/phases/phase4f/phase4f_5d/analysis/leakage_audit.json
?? backend/phases/phase4f/phase4f_5d/analysis/test_composition.json
?? backend/phases/phase4f/phase4f_5d/analysis/unanswerable_audit.json
?? backend/phases/phase4f/phase4f_5d/benchmark/benchmark_checksum.txt
?? backend/phases/phase4f/phase4f_5d/benchmark/benchmark_manifest.json
?? backend/phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl
?? backend/phases/phase4f/phase4f_5d/build_benchmark.py
?? backend/phases/phase4f/phase4f_5d/phase4f_5d_manifest.json
?? backend/phases/phase4f/phase4f_5d/reports/phase4f_5d_benchmark_hardening_report.txt
?? backend/phases/phase4f/phase4f_5e/analysis.pre_joint_selection_v1/capability_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_joint_selection_v1/confidence_distribution.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_joint_selection_v1/f1_gain_analysis.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_joint_selection_v1/next_experiment_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_joint_selection_v1/production_vs_experiment.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_joint_selection_v1/root_cause_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_joint_selection_v1/split_category_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_joint_selection_v1/threshold_sweep.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_joint_selection_v1/training_data_audit.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_joint_selection_v1/unanswerable_audit.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_reconstruction_fix/capability_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_reconstruction_fix/confidence_distribution.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_reconstruction_fix/f1_gain_analysis.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_reconstruction_fix/next_experiment_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_reconstruction_fix/production_vs_experiment.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_reconstruction_fix/root_cause_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_reconstruction_fix/split_category_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_reconstruction_fix/threshold_sweep.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_reconstruction_fix/training_data_audit.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_reconstruction_fix/unanswerable_audit.json
?? backend/phases/phase4f/phase4f_5e/analysis/capability_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis/confidence_distribution.json
?? backend/phases/phase4f/phase4f_5e/analysis/f1_gain_analysis.json
?? backend/phases/phase4f/phase4f_5e/analysis/next_experiment_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis/production_vs_experiment.json
?? backend/phases/phase4f/phase4f_5e/analysis/root_cause_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis/split_category_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis/threshold_sweep.json
?? backend/phases/phase4f/phase4f_5e/analysis/training_data_audit.json
?? backend/phases/phase4f/phase4f_5e/analysis/unanswerable_audit.json
?? backend/phases/phase4f/phase4f_5e/phase4f_5e_manifest.json
?? backend/phases/phase4f/phase4f_5e/reports/phase4f_5e_qa_capability_audit.txt
?? backend/phases/phase4f/phase4f_5e/run_analysis.py
?? backend/phases/phase4f/phase4f_5f/dataset/experiment_f1_manifest.json
?? backend/phases/phase4f/phase4f_5f/dataset/experiment_f1_quality_report.json
?? backend/phases/phase4f/phase4f_5f/dataset/experiment_f1_split.json
?? backend/phases/phase4f/phase4f_5f/f2/config/f2_config.json
?? backend/phases/phase4f/phase4f_5f/f2/evaluation/f2_benchmark.json
?? backend/phases/phase4f/phase4f_5f/f2/evaluation/f2_holdout.json
?? backend/phases/phase4f/phase4f_5f/f2/evaluation/f2_validation.json
?? backend/phases/phase4f/phase4f_5f/f2/logs/f2_training.json
?? backend/phases/phase4f/phase4f_5f/f2/manifests/f2_dataset_ids.json
?? backend/phases/phase4f/phase4f_5f/f2/manifests/f2_manifest.json
?? backend/phases/phase4f/phase4f_5f/f2/reconciliation/f2_baseline_comparison.json
?? backend/phases/phase4f/phase4f_5f/f2/reconciliation/f2_data_balance_audit.json
?? backend/phases/phase4f/phase4f_5f/f2/reconciliation/f2_label_audit.json
?? backend/phases/phase4f/phase4f_5f/f2/reconciliation/f2_no_answer_logic_audit.json
?? backend/phases/phase4f/phase4f_5f/f2/reconciliation/f2_prediction_audit.json
?? backend/phases/phase4f/phase4f_5f/f2/reconciliation/f2_root_cause_analysis.json
?? backend/phases/phase4f/phase4f_5f/f2/reports/phase4f_5f_f2_final_report.txt
?? backend/phases/phase4f/phase4f_5f/f2/reports/phase4f_5f_f2_reconciliation_report.txt
?? backend/phases/phase4f/phase4f_5f/f2/reports/phase4f_5f_g_threshold_report.txt
?? backend/phases/phase4f/phase4f_5f/f2/run_f2.py
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/benchmark_result.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/holdout_result.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/margin_sweep.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/raw_prediction_audit.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/raw_predictions_benchmark.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/raw_predictions_holdout.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/raw_predictions_validation.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/run_threshold_experiment.py
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/stability_analysis.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/threshold_experiment_manifest.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/threshold_sweep.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/validation_calibration.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/benchmark_result.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/holdout_result.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/margin_sweep.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/raw_prediction_audit.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/raw_predictions_benchmark.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/raw_predictions_holdout.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/raw_predictions_validation.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/run_threshold_experiment.py
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/stability_analysis.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/threshold_experiment_manifest.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/threshold_sweep.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/validation_calibration.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/benchmark_result.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/holdout_result.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/margin_sweep.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/raw_prediction_audit.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/raw_predictions_benchmark.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/raw_predictions_holdout.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/raw_predictions_validation.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/run_threshold_experiment.py
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/stability_analysis.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/threshold_experiment_manifest.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/threshold_sweep.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/validation_calibration.json
?? backend/phases/phase4f/phase4f_5f/h/audits/duplicate_audit.json
?? backend/phases/phase4f/phase4f_5f/h/audits/leakage_audit.json
?? backend/phases/phase4f/phase4f_5f/h/audits/quality_gate_failures.json
?? backend/phases/phase4f/phase4f_5f/h/audits/semantic_audit.json
?? backend/phases/phase4f/phase4f_5f/h/candidates/all_candidates.jsonl
?? backend/phases/phase4f/phase4f_5f/h/generate_h_candidates.py
?? backend/phases/phase4f/phase4f_5f/h/manifests/h_manifest.json
?? backend/phases/phase4f/phase4f_5f/h/pools/h10.jsonl
?? backend/phases/phase4f/phase4f_5f/h/pools/h20.jsonl
?? backend/phases/phase4f/phase4f_5f/h/pools/h30.jsonl
?? backend/phases/phase4f/phase4f_5f/h/reports/phase4f_5f_h_dataset_design_report.txt
?? backend/phases/phase4f/phase4f_5f/h1/config/f1_reconciled_ids.json
?? backend/phases/phase4f/phase4f_5f/h1/config/h1_config.json
?? backend/phases/phase4f/phase4f_5f/h1/evaluation/h1_benchmark.json
?? backend/phases/phase4f/phase4f_5f/h1/evaluation/h1_holdout.json
?? backend/phases/phase4f/phase4f_5f/h1/evaluation/h1_null_analysis.json
?? backend/phases/phase4f/phase4f_5f/h1/evaluation/h1_validation.json
?? backend/phases/phase4f/phase4f_5f/h1/logs/h1_training.json
?? backend/phases/phase4f/phase4f_5f/h1/manifests/h1_manifest.json
?? backend/phases/phase4f/phase4f_5f/h1/reports/phase4f_5f_h1_final_report.txt
?? backend/phases/phase4f/phase4f_5f/h1/run_h1.py
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/H1_RECONCILIATION_REPORT.md
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/README.md
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/checksums.txt
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/h1_count_reconciliation.json
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/h1_label_integrity.json
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/h1_metric_recalculation.json
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/h1_no_answer_analysis.json
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/h1_null_score_analysis.json
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/h1_overlap_report.json
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/h1_protocol_audit.json
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/h1_reconciled_comparison.json
?? backend/phases/phase4f/phase4f_5f/phase4f_5f_f1_reconciliation_manifest.json
?? backend/phases/phase4f/phase4f_5f/reconciliation/dataset_reconciliation.json
?? backend/phases/phase4f/phase4f_5f/reconciliation/final_holdout_ids.json
?? backend/phases/phase4f/phase4f_5f/reconciliation/final_training_ids.json
?? backend/phases/phase4f/phase4f_5f/reconciliation/final_validation_ids.json
?? backend/phases/phase4f/phase4f_5f/reconciliation/invalid_span_audit.json
?? backend/phases/phase4f/phase4f_5f/reconciliation/training_protocol_audit.json
?? backend/phases/phase4f/phase4f_5f/recovery/artifact_inventory.json
?? backend/phases/phase4f/phase4f_5f/recovery/gpu_environment_report.json
?? backend/phases/phase4f/phase4f_5f/recovery/gpu_environment_report.txt
?? backend/phases/phase4f/phase4f_5f/recovery/phase4f_5f_recovery_report.txt
?? backend/phases/phase4f/phase4f_5f/recovery/recovery_manifest.json
?? backend/phases/phase4f/phase4f_5f/reports/phase4f_5f_f1_preparation_report.txt
?? backend/phases/phase4f/phase4f_5f/reports/phase4f_5f_f1_reconciliation_report.txt
?? backend/phases/phase4f/phase4f_5f/research_ledger/RESEARCH_LEDGER.md
?? backend/phases/phase4f/phase4f_5f/research_ledger/checksums.txt
?? backend/phases/phase4f/phase4f_5f/research_ledger/research_ledger.json
?? backend/phases/phase4f/phase4f_5f/run_experiment.py
?? backend/phases/phase4f/quality_gate.py
?? backend/phases/phase4f/reconciliation/a0_reproduction.json
?? backend/phases/phase4f/reconciliation/checkpoint_audit.json
?? backend/phases/phase4f/reconciliation/cross_phase_evaluation_compatibility.json
?? backend/phases/phase4f/reconciliation/dataset_label_audit.json
?? backend/phases/phase4f/reconciliation/evaluation_parity_matrix.json
?? backend/phases/phase4f/reconciliation/experiment_artifact_inventory.json
?? backend/phases/phase4f/reconciliation/failure_taxonomy_reconciliation.json
?? backend/phases/phase4f/reconciliation/manual_forensic_traces.json
?? backend/phases/phase4f/reconciliation/model_initialization_audit.json
?? backend/phases/phase4f/reconciliation/phase4f_4r_reconciliation_report.txt
?? backend/phases/phase4f/reconciliation/token_span_audit.json
?? backend/phases/phase4f/reconciliation/training_configuration_audit.json
?? backend/phases/phase4f/training/__init__.py
?? backend/phases/phase4f/training/configs.py
?? backend/phases/phase4f/training/environment.json
?? backend/phases/phase4f/training/train.py
?? backend/phases/phase4f_qa_architecture_experiment_report.txt
?? backend/scripts/cleanup_orphan_uploads.py
?? backend/scripts/cleanup_path.py
?? backend/scripts/cleanup_smoke.py
?? backend/scripts/create_test_user.py
?? backend/scripts/db_check.py
?? backend/scripts/setup_db.py
?? backend/scripts/start_server.py
?? backend/tests/README.md
?? backend/tests/e2e/__init__.py
?? backend/tests/e2e/browser/__init__.py
?? backend/tests/e2e/browser/test_browser_flow.py
?? backend/tests/e2e/browser/test_document_flow.py
?? backend/tests/e2e/browser/test_embedding_flow.py
?? backend/tests/e2e/browser/test_phase6_reliability.py
?? backend/tests/e2e/browser/test_rag_flow.py
?? backend/tests/e2e/browser/test_real_browser.py
?? backend/tests/fixtures/__init__.py
?? backend/tests/fixtures/darwin_proper.pdf
?? backend/tests/fixtures/e2e_config.py
?? backend/tests/fixtures/graph_data.py
?? backend/tests/fixtures/integration_db.py
?? backend/tests/fixtures/integration_http.py
?? backend/tests/fixtures/live_server.py
?? backend/tests/fixtures/paths.py
?? backend/tests/fixtures/pdf_layout.py
?? backend/tests/integration/__init__.py
?? backend/tests/integration/auth/__init__.py
?? backend/tests/integration/auth/test_auth.py
?? backend/tests/integration/documents/__init__.py
?? backend/tests/integration/documents/test_document_detail_pagination.py
?? backend/tests/integration/documents/test_document_insights.py
?? backend/tests/integration/documents/test_document_mutation_id_validation.py
?? backend/tests/integration/documents/test_file_validation.py
?? backend/tests/integration/documents/test_table_row_migration.py
?? backend/tests/integration/documents/test_table_row_persistence.py
?? backend/tests/integration/embeddings/__init__.py
?? backend/tests/integration/embeddings/test_generate_error_handling.py
?? backend/tests/integration/graph/__init__.py
?? backend/tests/integration/graph/test_graph_ingestion.py
?? backend/tests/integration/graph/test_graph_rag_flow.py
?? backend/tests/integration/graph/test_graph_security.py
?? backend/tests/integration/graph/test_structure_augmentation.py
?? backend/tests/integration/graph/test_structure_reachability.py
?? backend/tests/integration/graph/test_table_evidence_api.py
?? backend/tests/integration/graph/test_table_evidence_bands.py
?? backend/tests/integration/rag/__init__.py
?? backend/tests/integration/rag/test_real_e2e_validation.py
?? backend/tests/integration/reliability/__init__.py
?? backend/tests/integration/reliability/test_table_row_reliability_api.py
?? backend/tests/integration/security/__init__.py
?? backend/tests/integration/security/test_cors.py
?? backend/tests/integration/settings/__init__.py
?? backend/tests/integration/settings/test_settings.py
?? backend/tests/integration/verification/__init__.py
?? backend/tests/integration/verification/test_image_verification.py
?? backend/tests/integration/verification/test_verification_integrity.py
?? backend/tests/integration/voice/__init__.py
?? backend/tests/integration/voice/test_voice_synthesize.py
?? backend/tests/integration/voice/test_voice_transcribe.py
?? backend/tests/unit/__init__.py
?? backend/tests/unit/auth/__init__.py
?? backend/tests/unit/auth/test_config_security.py
?? backend/tests/unit/brain/__init__.py
?? backend/tests/unit/brain/test_brain_orchestration.py
?? backend/tests/unit/brain/test_brain_types.py
?? backend/tests/unit/brain/test_outcomes.py
?? backend/tests/unit/chat/__init__.py
?? backend/tests/unit/chat/test_answer_span.py
?? backend/tests/unit/chat/test_chat_unit.py
?? backend/tests/unit/chat/test_phase3d_context.py
?? backend/tests/unit/chat/test_phase3d_reconciliation.py
?? backend/tests/unit/chat/test_qa_answer_reconstruction.py
?? backend/tests/unit/chat/test_table_evidence_gate.py
?? backend/tests/unit/documents/__init__.py
?? backend/tests/unit/documents/test_pdf_read_order.py
?? backend/tests/unit/documents/test_phase3d_chunking.py
?? backend/tests/unit/documents/test_phase3e_processing.py
?? backend/tests/unit/documents/test_structured_extraction.py
?? backend/tests/unit/documents/test_table_rows.py
?? backend/tests/unit/embeddings/__init__.py
?? backend/tests/unit/evaluation/__init__.py
?? backend/tests/unit/evaluation/conftest.py
?? backend/tests/unit/evaluation/test_denominator_sensitivity.py
?? backend/tests/unit/evaluation/test_disposable_database_authorization.py
?? backend/tests/unit/evaluation/test_disposal_authorization_contract.py
?? backend/tests/unit/evaluation/test_evaluation_isolation.py
?? backend/tests/unit/evaluation/test_function_cleanup_authorization.py
?? backend/tests/unit/evaluation/test_heading_corpus.py
?? backend/tests/unit/evaluation/test_isolation_guard_identity.py
?? backend/tests/unit/evaluation/test_legacy_runner_isolation.py
?? backend/tests/unit/evaluation/test_lifecycle_authorization.py
?? backend/tests/unit/evaluation/test_metrics.py
?? backend/tests/unit/evaluation/test_phase3_runner_target_order.py
?? backend/tests/unit/evaluation/test_phase3d_cleanup_scope.py
?? backend/tests/unit/evaluation/test_phase3d_evaluation_cleanup_scope.py
?? backend/tests/unit/evaluation/test_phase3e_integration_cleanup_scope.py
?? backend/tests/unit/evaluation/test_phase3e_validation_cleanup_scope.py
?? backend/tests/unit/evaluation/test_phase3f_evaluation_cleanup_scope.py
?? backend/tests/unit/evaluation/test_phase4b_evaluation_cleanup_scope.py
?? backend/tests/unit/evaluation/test_run_artifacts.py
?? backend/tests/unit/evaluation/test_runner_pre_engine_init.py
?? backend/tests/unit/evaluation/test_runner_report_output.py
?? backend/tests/unit/evaluation/test_structure_discriminating_corpus.py
?? backend/tests/unit/evaluation/test_structure_eval.py
?? backend/tests/unit/evaluation/test_structure_runner_guard_order.py
?? backend/tests/unit/evaluation/test_unsupported_answer_denominator.py
?? backend/tests/unit/graph/__init__.py
?? backend/tests/unit/graph/test_fusion.py
?? backend/tests/unit/graph/test_graph_edges.py
?? backend/tests/unit/graph/test_structural_retrieval.py
?? backend/tests/unit/graph/test_structure_element_retrieval.py
?? backend/tests/unit/reliability/__init__.py
?? backend/tests/unit/reliability/test_table_row_provenance.py
?? backend/tests/unit/scripts/test_cleanup_orphan_uploads.py
?? backend/tests/unit/security/__init__.py
?? backend/tests/unit/security/test_sql_safety.py
?? backend/tests/unit/storage/__init__.py
?? backend/tests/unit/storage/test_database_url.py
?? backend/tests/unit/storage/test_sqlite_type_isolation.py
?? backend/tests/unit/verification/__init__.py
?? backend/verification/service.py
?? backend/voice.py
?? compose.yaml
?? docker/nginx.conf
?? prompts/00_coordinator.md
?? prompts/01_database_agent.md
?? prompts/02_backend_agent.md
?? prompts/03_frontend_agent.md
?? prompts/04_ai_agent.md
?? prompts/05_test_agent.md
?? prompts/06_evaluation_agent.md
?? prompts/07_security_agent.md
?? prompts/08_verifier.md
?? runbooks/docker-runtime.md
?? src/components/common/DocumentInsightsPanel.tsx
?? src/components/common/VoiceInputButton.tsx
?? src/components/common/VoiceSpeakerButton.tsx
```

### 12.2 Complete final expanded status — SOURCE-VERIFIED

```text
 M .gitignore
 M DOCUMIND_PROJECT_CONTEXT.md
 M backend/brain/__init__.py
 M backend/brain/adapters.py
 M backend/brain/response.py
 M backend/brain/types.py
 M backend/chat/qa_model.py
 M backend/chat/rag.py
 M backend/chat/routes.py
 M backend/documents/models.py
 M backend/documents/processing.py
 M backend/documents/routes.py
 M backend/documents/schemas.py
 M backend/embeddings/model.py
 M backend/embeddings/routes.py
 M backend/evaluation/harness/corpus.py
 D backend/evaluation/harness/evaluator.py
 M backend/main.py
 M backend/migrations/env.py
 D backend/phase3d_evaluation_report.json
 D backend/phase3f_evaluation_report.json
 D backend/phase3f_validation_report.txt
 D backend/phase3g_pipeline_audit.txt
 D backend/phase4a_qa_failure_audit.txt
 D backend/phase4b_evaluation_report.json
 D backend/phase4b_qa_evaluation_report.txt
 D backend/phase4c_failure_matrix.json
 D backend/phase4c_qa_failure_isolation_report.txt
 D backend/phase4d/__init__.py
 D backend/phase4d/__main__.py
 D backend/phase4d/evaluate_candidates.py
 D backend/phase4d/generate_report.py
 D backend/phase4d/oracle_eval.py
 D backend/phase4d/reconciliation.py
 D backend/phase4d/train.py
 D backend/phase4d/training_data.py
 D backend/phase4d_1_reconciliation.json
 D backend/phase4d_1_reconciliation_report.txt
 D backend/phase4d_experiment_results.json
 D backend/phase4d_oracle_baseline_results.json
 D backend/phase4d_qa_model_improvement_report.txt
 D backend/phase4e/__init__.py
 D backend/phase4e/capability_analysis.py
 D backend/phase4e/generate_report.py
 D backend/phase4e_capability_matrix.json
 D backend/phase4e_diagnostic_results.json
 D backend/phase4e_qa_architecture_analysis.txt
 D backend/phase4f/__init__.py
 D backend/phase4f/balance_gate.py
 D backend/phase4f/dataset/__init__.py
 D backend/phase4f/dataset/dataset_manifest.json
 D backend/phase4f/dataset/dataset_manifest_v3.json
 D backend/phase4f/dataset/dataset_manifest_v3_1.json
 D backend/phase4f/dataset/dataset_metadata.json
 D backend/phase4f/dataset/dataset_quality_report.json
 D backend/phase4f/dataset/dataset_quality_report_v3.json
 D backend/phase4f/dataset/dataset_quality_report_v3_1.json
 D backend/phase4f/dataset/expand_and_audit.py
 D backend/phase4f/dataset/generator.py
 D backend/phase4f/dataset/training_data.jsonl
 D backend/phase4f/dataset/training_data_v3.jsonl
 D backend/phase4f/dataset/training_data_v3_1.jsonl
 D backend/phase4f/experiments/evaluate.py
 D backend/phase4f/experiments/experiment_manifest.json
 D backend/phase4f/experiments/final_gpu_package/README_GPU_EXECUTION.md
 D backend/phase4f/experiments/final_gpu_package/dataset/training_data_v3_1.jsonl
 D backend/phase4f/experiments/final_gpu_package/dataset_checksum.txt
 D backend/phase4f/experiments/final_gpu_package/evaluation/evaluate.py
 D backend/phase4f/experiments/final_gpu_package/expected_output_structure.txt
 D backend/phase4f/experiments/final_gpu_package/final_gpu_package_manifest.json
 D backend/phase4f/experiments/final_gpu_package/production_model_checksum.txt
 D backend/phase4f/experiments/final_gpu_package/requirements.txt
 D backend/phase4f/experiments/final_gpu_package/training/experiment_config.json
 D backend/phase4f/experiments/final_gpu_package/training/train.py
 D backend/phase4f/experiments/phase4f_3_results.json
 D backend/phase4f/experiments/phase4f_3_training_report.txt
 D backend/phase4f/experiments/phase4f_3r_freeze_report.txt
 D backend/phase4f/experiments/phase4f_4_controlled_gpu_experiment_report.txt
 D backend/phase4f/experiments/phase4f_4_experiment_manifest.json
 D backend/phase4f/experiments/phase4f_4_results.json
 D backend/phase4f/experiments/phase4f_4e_cuda_environment.json
 D backend/phase4f/experiments/phase4f_4e_cuda_environment_report.txt
 D backend/phase4f/experiments/requirements.txt
 D backend/phase4f/experiments/results/A0/evaluation_results.json
 D backend/phase4f/experiments/results/A0/metadata.json
 D backend/phase4f/experiments/results/A1/checkpoint_best/config.json
 D backend/phase4f/experiments/results/A1/checkpoint_best/tokenizer.json
 D backend/phase4f/experiments/results/A1/checkpoint_best/tokenizer_config.json
 D backend/phase4f/experiments/results/A1/evaluation_results.json
 D backend/phase4f/experiments/results/A1/training_metadata.json
 D backend/phase4f/experiments/results/A2/checkpoint_best/config.json
 D backend/phase4f/experiments/results/A2/checkpoint_best/tokenizer.json
 D backend/phase4f/experiments/results/A2/checkpoint_best/tokenizer_config.json
 D backend/phase4f/experiments/results/A2/evaluation_results.json
 D backend/phase4f/experiments/results/A2/training_metadata.json
 D backend/phase4f/experiments/results/A3/checkpoint_best/config.json
 D backend/phase4f/experiments/results/A3/checkpoint_best/tokenizer.json
 D backend/phase4f/experiments/results/A3/checkpoint_best/tokenizer_config.json
 D backend/phase4f/experiments/results/A3/evaluation_results.json
 D backend/phase4f/experiments/results/A3/training_metadata.json
 D backend/phase4f/experiments/results/all_results.json
 D backend/phase4f/experiments/run_experiment.py
 D backend/phase4f/experiments/train.py
 D backend/phase4f/freeze_gate.py
 D backend/phase4f/phase4f_1_dataset_audit_report.txt
 D backend/phase4f/phase4f_2_dataset_quality_gate_report.txt
 D backend/phase4f/phase4f_2r_dataset_balance_report.txt
 D backend/phase4f/phase4f_4r_manifest.json
 D backend/phase4f/phase4f_5/configs/a1_config.json
 D backend/phase4f/phase4f_5/configs/a2_config.json
 D backend/phase4f/phase4f_5/dataset/data_quality_gate.json
 D backend/phase4f/phase4f_5/dataset/derived_dataset.jsonl
 D backend/phase4f/phase4f_5/dataset/span_alignment_audit.json
 D backend/phase4f/phase4f_5/dataset/truncation_audit.json
 D backend/phase4f/phase4f_5/diagnostics/a0_forensics.json
 D backend/phase4f/phase4f_5/diagnostics/a1_forensics.json
 D backend/phase4f/phase4f_5/diagnostics/a2_forensics.json
 D backend/phase4f/phase4f_5/diagnostics/all_inference_results.json
 D backend/phase4f/phase4f_5/diagnostics/failure_taxonomy.json
 D backend/phase4f/phase4f_5/evaluation/evaluate.py
 D backend/phase4f/phase4f_5/evaluation/evaluation_protocol.json
 D backend/phase4f/phase4f_5/logs/a1_training.json
 D backend/phase4f/phase4f_5/logs/a2_training.json
 D backend/phase4f/phase4f_5/manifests/experiment_manifest.json
 D backend/phase4f/phase4f_5/manifests/final_experiment_manifest.json
 D backend/phase4f/phase4f_5/manifests/source_integrity.json
 D backend/phase4f/phase4f_5/manifests/split_manifest.json
 D backend/phase4f/phase4f_5/prepare_experiment.py
 D backend/phase4f/phase4f_5/reports/phase4f_5a_preparation_report.txt
 D backend/phase4f/phase4f_5/reports/phase4f_5b_training_report.txt
 D backend/phase4f/phase4f_5/results/a0_test.json
 D backend/phase4f/phase4f_5/results/a1_test.json
 D backend/phase4f/phase4f_5/results/a2_test.json
 D backend/phase4f/phase4f_5/results/comparison.json
 D backend/phase4f/phase4f_5/run_experiment.py
 D backend/phase4f/phase4f_5c/em_f1_gap_analysis.json
 D backend/phase4f/phase4f_5c/failure_matrix.json
 D backend/phase4f/phase4f_5c/generate_analysis.py
 D backend/phase4f/phase4f_5c/list_audit.json
 D backend/phase4f/phase4f_5c/long_context_audit.json
 D backend/phase4f/phase4f_5c/normalization_diagnostic.json
 D backend/phase4f/phase4f_5c/numeric_audit.json
 D backend/phase4f/phase4f_5c/per_category_comparison.json
 D backend/phase4f/phase4f_5c/phase4f_5c_manifest.json
 D backend/phase4f/phase4f_5c/production_strengths.json
 D backend/phase4f/phase4f_5c/reports/phase4f_5c_qa_analysis_report.txt
 D backend/phase4f/phase4f_5c/root_cause_analysis.json
 D backend/phase4f/phase4f_5c/table_audit.json
 D backend/phase4f/phase4f_5c/test_composition.json
 D backend/phase4f/phase4f_5c/training_curve_analysis.json
 D backend/phase4f/phase4f_5d/analysis/a0_benchmark_v1.json
 D backend/phase4f/phase4f_5d/analysis/a1_benchmark_v1.json
 D backend/phase4f/phase4f_5d/analysis/a2_benchmark_v1.json
 D backend/phase4f/phase4f_5d/analysis/benchmark_comparison.json
 D backend/phase4f/phase4f_5d/analysis/category_balance.json
 D backend/phase4f/phase4f_5d/analysis/duplicate_audit.json
 D backend/phase4f/phase4f_5d/analysis/gold_span_validation.json
 D backend/phase4f/phase4f_5d/analysis/leakage_audit.json
 D backend/phase4f/phase4f_5d/analysis/test_composition.json
 D backend/phase4f/phase4f_5d/analysis/unanswerable_audit.json
 D backend/phase4f/phase4f_5d/benchmark/benchmark_checksum.txt
 D backend/phase4f/phase4f_5d/benchmark/benchmark_manifest.json
 D backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl
 D backend/phase4f/phase4f_5d/build_benchmark.py
 D backend/phase4f/phase4f_5d/phase4f_5d_manifest.json
 D backend/phase4f/phase4f_5d/reports/phase4f_5d_benchmark_hardening_report.txt
 D backend/phase4f/phase4f_5e/analysis/capability_matrix.json
 D backend/phase4f/phase4f_5e/analysis/confidence_distribution.json
 D backend/phase4f/phase4f_5e/analysis/f1_gain_analysis.json
 D backend/phase4f/phase4f_5e/analysis/next_experiment_matrix.json
 D backend/phase4f/phase4f_5e/analysis/production_vs_experiment.json
 D backend/phase4f/phase4f_5e/analysis/root_cause_matrix.json
 D backend/phase4f/phase4f_5e/analysis/split_category_matrix.json
 D backend/phase4f/phase4f_5e/analysis/threshold_sweep.json
 D backend/phase4f/phase4f_5e/analysis/training_data_audit.json
 D backend/phase4f/phase4f_5e/analysis/unanswerable_audit.json
 D backend/phase4f/phase4f_5e/phase4f_5e_manifest.json
 D backend/phase4f/phase4f_5e/reports/phase4f_5e_qa_capability_audit.txt
 D backend/phase4f/phase4f_5e/run_analysis.py
 D backend/phase4f/phase4f_5f/dataset/experiment_f1_manifest.json
 D backend/phase4f/phase4f_5f/dataset/experiment_f1_quality_report.json
 D backend/phase4f/phase4f_5f/dataset/experiment_f1_split.json
 D backend/phase4f/phase4f_5f/f2/config/f2_config.json
 D backend/phase4f/phase4f_5f/f2/evaluation/f2_benchmark.json
 D backend/phase4f/phase4f_5f/f2/evaluation/f2_holdout.json
 D backend/phase4f/phase4f_5f/f2/evaluation/f2_validation.json
 D backend/phase4f/phase4f_5f/f2/logs/f2_training.json
 D backend/phase4f/phase4f_5f/f2/manifests/f2_dataset_ids.json
 D backend/phase4f/phase4f_5f/f2/manifests/f2_manifest.json
 D backend/phase4f/phase4f_5f/f2/reconciliation/f2_baseline_comparison.json
 D backend/phase4f/phase4f_5f/f2/reconciliation/f2_data_balance_audit.json
 D backend/phase4f/phase4f_5f/f2/reconciliation/f2_label_audit.json
 D backend/phase4f/phase4f_5f/f2/reconciliation/f2_no_answer_logic_audit.json
 D backend/phase4f/phase4f_5f/f2/reconciliation/f2_prediction_audit.json
 D backend/phase4f/phase4f_5f/f2/reconciliation/f2_root_cause_analysis.json
 D backend/phase4f/phase4f_5f/f2/reports/phase4f_5f_f2_final_report.txt
 D backend/phase4f/phase4f_5f/f2/reports/phase4f_5f_f2_reconciliation_report.txt
 D backend/phase4f/phase4f_5f/f2/reports/phase4f_5f_g_threshold_report.txt
 D backend/phase4f/phase4f_5f/f2/run_f2.py
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/benchmark_result.json
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/holdout_result.json
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/margin_sweep.json
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/raw_prediction_audit.json
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/raw_predictions_benchmark.json
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/raw_predictions_holdout.json
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/raw_predictions_validation.json
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/run_threshold_experiment.py
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/stability_analysis.json
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/threshold_experiment_manifest.json
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/threshold_sweep.json
 D backend/phase4f/phase4f_5f/f2/threshold_experiment/validation_calibration.json
 D backend/phase4f/phase4f_5f/h/audits/duplicate_audit.json
 D backend/phase4f/phase4f_5f/h/audits/leakage_audit.json
 D backend/phase4f/phase4f_5f/h/audits/quality_gate_failures.json
 D backend/phase4f/phase4f_5f/h/audits/semantic_audit.json
 D backend/phase4f/phase4f_5f/h/candidates/all_candidates.jsonl
 D backend/phase4f/phase4f_5f/h/generate_h_candidates.py
 D backend/phase4f/phase4f_5f/h/manifests/h_manifest.json
 D backend/phase4f/phase4f_5f/h/pools/h10.jsonl
 D backend/phase4f/phase4f_5f/h/pools/h20.jsonl
 D backend/phase4f/phase4f_5f/h/pools/h30.jsonl
 D backend/phase4f/phase4f_5f/h/reports/phase4f_5f_h_dataset_design_report.txt
 D backend/phase4f/phase4f_5f/h1/config/f1_reconciled_ids.json
 D backend/phase4f/phase4f_5f/h1/config/h1_config.json
 D backend/phase4f/phase4f_5f/h1/evaluation/h1_benchmark.json
 D backend/phase4f/phase4f_5f/h1/evaluation/h1_holdout.json
 D backend/phase4f/phase4f_5f/h1/evaluation/h1_null_analysis.json
 D backend/phase4f/phase4f_5f/h1/evaluation/h1_validation.json
 D backend/phase4f/phase4f_5f/h1/logs/h1_training.json
 D backend/phase4f/phase4f_5f/h1/manifests/h1_manifest.json
 D backend/phase4f/phase4f_5f/h1/reports/phase4f_5f_h1_final_report.txt
 D backend/phase4f/phase4f_5f/h1/run_h1.py
 D backend/phase4f/phase4f_5f/h1_reconciliation/H1_RECONCILIATION_REPORT.md
 D backend/phase4f/phase4f_5f/h1_reconciliation/README.md
 D backend/phase4f/phase4f_5f/h1_reconciliation/checksums.txt
 D backend/phase4f/phase4f_5f/h1_reconciliation/h1_count_reconciliation.json
 D backend/phase4f/phase4f_5f/h1_reconciliation/h1_label_integrity.json
 D backend/phase4f/phase4f_5f/h1_reconciliation/h1_metric_recalculation.json
 D backend/phase4f/phase4f_5f/h1_reconciliation/h1_no_answer_analysis.json
 D backend/phase4f/phase4f_5f/h1_reconciliation/h1_null_score_analysis.json
 D backend/phase4f/phase4f_5f/h1_reconciliation/h1_overlap_report.json
 D backend/phase4f/phase4f_5f/h1_reconciliation/h1_protocol_audit.json
 D backend/phase4f/phase4f_5f/h1_reconciliation/h1_reconciled_comparison.json
 D backend/phase4f/phase4f_5f/phase4f_5f_f1_reconciliation_manifest.json
 D backend/phase4f/phase4f_5f/reconciliation/dataset_reconciliation.json
 D backend/phase4f/phase4f_5f/reconciliation/final_holdout_ids.json
 D backend/phase4f/phase4f_5f/reconciliation/final_training_ids.json
 D backend/phase4f/phase4f_5f/reconciliation/final_validation_ids.json
 D backend/phase4f/phase4f_5f/reconciliation/invalid_span_audit.json
 D backend/phase4f/phase4f_5f/reconciliation/training_protocol_audit.json
 D backend/phase4f/phase4f_5f/recovery/artifact_inventory.json
 D backend/phase4f/phase4f_5f/recovery/gpu_environment_report.json
 D backend/phase4f/phase4f_5f/recovery/gpu_environment_report.txt
 D backend/phase4f/phase4f_5f/recovery/phase4f_5f_recovery_report.txt
 D backend/phase4f/phase4f_5f/recovery/recovery_manifest.json
 D backend/phase4f/phase4f_5f/reports/phase4f_5f_f1_preparation_report.txt
 D backend/phase4f/phase4f_5f/reports/phase4f_5f_f1_reconciliation_report.txt
 D backend/phase4f/phase4f_5f/run_experiment.py
 D backend/phase4f/quality_gate.py
 D backend/phase4f/reconciliation/a0_reproduction.json
 D backend/phase4f/reconciliation/checkpoint_audit.json
 D backend/phase4f/reconciliation/cross_phase_evaluation_compatibility.json
 D backend/phase4f/reconciliation/dataset_label_audit.json
 D backend/phase4f/reconciliation/evaluation_parity_matrix.json
 D backend/phase4f/reconciliation/experiment_artifact_inventory.json
 D backend/phase4f/reconciliation/failure_taxonomy_reconciliation.json
 D backend/phase4f/reconciliation/manual_forensic_traces.json
 D backend/phase4f/reconciliation/model_initialization_audit.json
 D backend/phase4f/reconciliation/phase4f_4r_reconciliation_report.txt
 D backend/phase4f/reconciliation/token_span_audit.json
 D backend/phase4f/reconciliation/training_configuration_audit.json
 D backend/phase4f/training/__init__.py
 D backend/phase4f/training/configs.py
 D backend/phase4f/training/environment.json
 D backend/phase4f/training/train.py
 D backend/phase4f_qa_architecture_experiment_report.txt
 M backend/pytest.ini
 M backend/reliability/routes.py
 M backend/requirements.txt
 D backend/start_server.py
 D backend/test_browser_flow.py
 D backend/test_document_flow.py
 D backend/test_embedding_flow.py
 D backend/test_phase3d_evaluation.py
 D backend/test_phase3d_upload_integration.py
 D backend/test_phase3e_integration.py
 D backend/test_phase3e_validation.py
 D backend/test_phase3f_evaluation.py
 D backend/test_phase4b_evaluation.py
 D backend/test_phase4c_diagnostics.py
 D backend/test_phase6_reliability.py
 D backend/test_rag_flow.py
 D backend/test_real_browser.py
 M backend/tests/conftest.py
 D backend/tests/integration_http.py
 D backend/tests/phase3d_corpus.py
 D backend/tests/phase4b_corpus.py
 D backend/tests/test_answer_span.py
 D backend/tests/test_auth.py
 D backend/tests/test_brain_orchestration.py
 D backend/tests/test_brain_types.py
 D backend/tests/test_chat_unit.py
 D backend/tests/test_config_security.py
 D backend/tests/test_cors.py
 D backend/tests/test_database_url.py
 D backend/tests/test_file_validation.py
 D backend/tests/test_outcomes.py
 D backend/tests/test_phase3d_chunking.py
 D backend/tests/test_phase3d_context.py
 D backend/tests/test_phase3d_reconciliation.py
 D backend/tests/test_phase3e_processing.py
 D backend/tests/test_qa_answer_reconstruction.py
 D backend/tests/test_real_e2e_validation.py
 D backend/tests/test_settings.py
 D backend/tests/test_sql_safety.py
 D backend/tests/test_structured_extraction.py
 D backend/tests/test_verification_integrity.py
 M backend/verification/routes.py
 M package-lock.json
 M package.json
 M runbooks/README.md
 M runbooks/database-failure.md
 M runbooks/migration-failure.md
 M src/lib/api.ts
 M src/pages/ReliabilityPage.tsx
 M src/pages/VerificationPage.tsx
 M src/pages/WorkspacePage.tsx
 M src/types/index.ts
 M vite.config.ts
?? .dockerignore
?? .env.example
?? AGENTS.md
?? ARCHITECTURE.md
?? CONTEXT.md
?? DESIGN.md
?? Dockerfile.frontend
?? Field_Robotics_Deployment_and_Maintenance_Report.pdf
?? PRD.md
?? README.md
?? agents/README.md
?? agents/agentic-coding-agents/01-product-strategist-agent.md
?? agents/agentic-coding-agents/02-product-research-agent.md
?? agents/agentic-coding-agents/03-competitive-intelligence-agent.md
?? agents/agentic-coding-agents/04-requirements-agent.md
?? agents/agentic-coding-agents/05-ux-research-agent.md
?? agents/agentic-coding-agents/06-ux-ui-designer-agent.md
?? agents/agentic-coding-agents/07-accessibility-agent.md
?? agents/agentic-coding-agents/08-software-architect-agent.md
?? agents/agentic-coding-agents/09-frontend-architect-agent.md
?? agents/agentic-coding-agents/10-backend-architect-agent.md
?? agents/agentic-coding-agents/11-database-architect-agent.md
?? agents/agentic-coding-agents/12-api-architect-agent.md
?? agents/agentic-coding-agents/13-distributed-systems-agent.md
?? agents/agentic-coding-agents/14-security-architect-agent.md
?? agents/agentic-coding-agents/15-infrastructure-architect-agent.md
?? agents/agentic-coding-agents/16-frontend-coding-agent.md
?? agents/agentic-coding-agents/17-backend-coding-agent.md
?? agents/agentic-coding-agents/18-full-stack-agent.md
?? agents/agentic-coding-agents/19-database-engineer-agent.md
?? agents/agentic-coding-agents/20-api-integration-agent.md
?? agents/agentic-coding-agents/21-sdk-library-agent.md
?? agents/agentic-coding-agents/22-cli-agent.md
?? agents/agentic-coding-agents/23-desktop-agent.md
?? agents/agentic-coding-agents/24-mobile-agent.md
?? agents/agentic-coding-agents/25-ai-ml-architect-agent.md
?? agents/agentic-coding-agents/26-ml-fundamentals-agent.md
?? agents/agentic-coding-agents/27-data-science-agent.md
?? agents/agentic-coding-agents/28-data-engineering-agent.md
?? agents/agentic-coding-agents/29-feature-engineering-agent.md
?? agents/agentic-coding-agents/30-classical-ml-agent.md
?? agents/agentic-coding-agents/31-deep-learning-agent.md
?? agents/agentic-coding-agents/32-computer-vision-agent.md
?? agents/agentic-coding-agents/33-nlp-agent.md
?? agents/agentic-coding-agents/34-multimodal-ai-agent.md
?? agents/agentic-coding-agents/35-llm-engineer-agent.md
?? agents/agentic-coding-agents/36-rag-engineer-agent.md
?? agents/agentic-coding-agents/37-agentic-ai-engineer-agent.md
?? agents/agentic-coding-agents/38-fine-tuning-agent.md
?? agents/agentic-coding-agents/39-model-evaluation-agent.md
?? agents/agentic-coding-agents/40-prompt-engineering-agent.md
?? agents/agentic-coding-agents/41-embeddings-vector-search-agent.md
?? agents/agentic-coding-agents/42-knowledge-graph-agent.md
?? agents/agentic-coding-agents/43-ai-safety-guardrails-agent.md
?? agents/agentic-coding-agents/44-ml-pipeline-agent.md
?? agents/agentic-coding-agents/45-mlops-agent.md
?? agents/agentic-coding-agents/46-model-serving-agent.md
?? agents/agentic-coding-agents/47-gpu-compute-optimization-agent.md
?? agents/agentic-coding-agents/48-model-compression-agent.md
?? agents/agentic-coding-agents/49-data-model-versioning-agent.md
?? agents/agentic-coding-agents/50-ai-cost-optimization-agent.md
?? agents/agentic-coding-agents/51-test-architect-agent.md
?? agents/agentic-coding-agents/52-unit-testing-agent.md
?? agents/agentic-coding-agents/53-integration-testing-agent.md
?? agents/agentic-coding-agents/54-e2e-testing-agent.md
?? agents/agentic-coding-agents/55-api-testing-agent.md
?? agents/agentic-coding-agents/56-performance-testing-agent.md
?? agents/agentic-coding-agents/57-ai-evaluation-agent.md
?? agents/agentic-coding-agents/58-security-testing-agent.md
?? agents/agentic-coding-agents/59-code-review-agent.md
?? agents/agentic-coding-agents/60-debugging-agent.md
?? agents/agentic-coding-agents/61-reliability-agent.md
?? agents/agentic-coding-agents/62-devops-agent.md
?? agents/agentic-coding-agents/63-cloud-engineer-agent.md
?? agents/agentic-coding-agents/64-docker-container-agent.md
?? agents/agentic-coding-agents/65-kubernetes-agent.md
?? agents/agentic-coding-agents/66-infrastructure-as-code-agent.md
?? agents/agentic-coding-agents/67-deployment-agent.md
?? agents/agentic-coding-agents/68-observability-agent.md
?? agents/agentic-coding-agents/69-incident-response-agent.md
?? agents/agentic-coding-agents/70-sre-agent.md
?? agents/agentic-coding-agents/71-cost-finops-agent.md
?? agents/agentic-coding-agents/72-application-security-agent.md
?? agents/agentic-coding-agents/73-dependency-security-agent.md
?? agents/agentic-coding-agents/74-secrets-security-agent.md
?? agents/agentic-coding-agents/75-identity-auth-agent.md
?? agents/agentic-coding-agents/76-privacy-agent.md
?? agents/agentic-coding-agents/77-threat-modeling-agent.md
?? agents/agentic-coding-agents/78-ai-security-agent.md
?? agents/agentic-coding-agents/79-documentation-agent.md
?? agents/agentic-coding-agents/80-api-documentation-agent.md
?? agents/agentic-coding-agents/81-architecture-documentation-agent.md
?? agents/agentic-coding-agents/82-codebase-knowledge-agent.md
?? agents/agentic-coding-agents/83-changelog-release-agent.md
?? agents/agentic-coding-agents/84-git-agent.md
?? agents/agentic-coding-agents/85-dependency-management-agent.md
?? agents/agentic-coding-agents/86-refactoring-agent.md
?? agents/agentic-coding-agents/87-legacy-migration-agent.md
?? agents/agentic-coding-agents/88-performance-optimization-agent.md
?? agents/agentic-coding-agents/89-database-optimization-agent.md
?? agents/agentic-coding-agents/90-accessibility-ui-qa-agent.md
?? agents/agentic-coding-agents/AGENT-CONTRACT.md
?? agents/agentic-coding-agents/README.md
?? agents/ai-agent.md
?? agents/backend-agent.md
?? agents/coordinator.md
?? agents/database-agent.md
?? agents/evaluation-agent.md
?? agents/frontend-agent.md
?? agents/security-agent.md
?? agents/test-agent.md
?? agents/verifier.md
?? backend/.dockerignore
?? backend/Dockerfile
?? backend/architecture/EVALUATION_SAFETY_MASTER_REGISTER.md
?? backend/architecture/IMPLEMENTATION_REPORT_2026-09-30.md
?? backend/architecture/PATH_MIGRATION.md
?? backend/architecture/PHASE0_CLOSURE_2026-10-09.md
?? backend/architecture/PHASE0_FAILURE_AUDIT_2026-10-09.md
?? backend/architecture/PHASE1_GROUNDED_ANSWERING_PLAN_2026-10-09.md
?? backend/architecture/REPOSITORY_AUDIT_2026-09-30.md
?? backend/architecture/STEP0_5_EVALUATION_RUNNER_SAFETY_AUDIT_2026-10-09.md
?? backend/architecture/STEP0_7_PHASE3D_DESTRUCTIVE_CLEANUP_REMEDIATION_2026-10-09.md
?? backend/architecture/STEP0_8_PHASE3D_EVALUATION_CLEANUP_REMEDIATION_2026-10-09.md
?? backend/architecture/STEP0_9_PHASE3E_INTEGRATION_CLEANUP_REMEDIATION_2026-10-09.md
?? backend/architecture/STEP0_EVALUATION_INFRASTRUCTURE_HARDENING_2026-10-09.md
?? backend/architecture/STEP1_0_PHASE3E_VALIDATION_CLEANUP_REMEDIATION_2026-10-09.md
?? backend/architecture/STEP1_1_PHASE3F_EVALUATION_CLEANUP_REMEDIATION_2026-10-09.md
?? backend/architecture/STEP1_2_PHASE4B_EVALUATION_CLEANUP_REMEDIATION_2026-10-09.md
?? backend/architecture/STEP1_4_POSTGRESQL_VERIFICATION_READINESS_ASSESSMENT_2026-10-09.md
?? backend/architecture/STEP1_5_EVALUATION_SAFETY_P0_REMEDIATION_PLAN_2026-10-09.md
?? backend/architecture/STEP1_6A_GUARD_FIRST_REMEDIATION_2026-10-10.md
?? backend/architecture/STEP1_6B_ISOLATION_GUARD_REMEDIATION_2026-10-10.md
?? backend/architecture/STEP1_6C_GUARD_FIRST_STRUCTURE_RUNNERS_2026-10-10.md
?? backend/architecture/STEP1_6D_PRE_ENGINE_TARGET_VALIDATION_2026-10-10.md
?? backend/architecture/STEP1_6E_REMAINING_RUNNER_INITIALIZATION_AUDIT_2026-10-10.md
?? backend/architecture/STEP1_6F_LEGACY_RUNNER_AND_CLEANUP_SAFETY_2026-10-11.md
?? backend/architecture/STEP1_6G_RUNNER_AND_FIXTURE_TARGET_SAFETY_2026-10-11.md
?? backend/architecture/STEP1_6H_DISPOSABLE_DATABASE_AUTHORIZATION_2026-10-11.md
?? backend/architecture/STEP1_6I_UNIFIED_DESTRUCTIVE_TARGET_AUTHORIZATION_2026-10-11.md
?? backend/architecture/STEP1_6J_FAIL_CLOSED_DESTRUCTIVE_EXECUTION_2026-10-12.md
?? backend/architecture/STEP1_6K_LIFECYCLE_AUTHORIZATION_HARDENING_2026-10-12.md
?? backend/architecture/STEP1_6L_FUNCTION_LEVEL_CLEANUP_AUTHORIZATION_2026-10-12.md
?? backend/architecture/STEP1_6M_READ_ONLY_POSTGRESQL_READINESS_REVIEW_2026-10-12.md
?? backend/architecture/STEP1_6N_EVALUATION_SAFETY_REMEDIATION_ARCHITECTURE_2026-10-12.md
?? backend/architecture/phase4f_6/ARCHITECTURE_DECISION_RECORD.md
?? backend/architecture/phase4f_6/CURRENT_ARCHITECTURE.md
?? backend/architecture/phase4f_6/DOMAIN_MODEL.md
?? backend/architecture/phase4f_6/MODULE_SEAMS.md
?? backend/architecture/phase4f_6/NEXT_STAGE_RAG_EXECUTION_PLAN.md
?? backend/architecture/phase4f_6/PHASE4F6_ARCHITECTURE_AUDIT.md
?? backend/architecture/phase4f_6/QUESTION_WORKFLOW_MATRIX.md
?? backend/architecture/phase4f_6/TARGET_ARCHITECTURE.md
?? backend/architecture/phase4f_6/decision/ABSTENTION_GATE_RESCORING.json
?? backend/architecture/phase4f_6/decision/ABSTENTION_GATE_RESCORING.md
?? backend/architecture/phase4f_6/decision/ANSWERABILITY_SIGNAL_FORENSICS.json
?? backend/architecture/phase4f_6/decision/ANSWERABILITY_SIGNAL_FORENSICS.md
?? backend/architecture/phase4f_6/decision/ARCHITECTURE_MIGRATION_GATE.md
?? backend/architecture/phase4f_6/decision/AUC_INFLUENCE_JACKKNIFE_FORENSICS.json
?? backend/architecture/phase4f_6/decision/AUC_INFLUENCE_JACKKNIFE_FORENSICS.md
?? backend/architecture/phase4f_6/decision/CLS_DIRECTION_REVERSAL_FORENSICS.json
?? backend/architecture/phase4f_6/decision/CLS_DIRECTION_REVERSAL_FORENSICS.md
?? backend/architecture/phase4f_6/decision/DECISION_SAFETY_CHECK.json
?? backend/architecture/phase4f_6/decision/E0_CHUNK_MANIFEST.json
?? backend/architecture/phase4f_6/decision/E0_CORPUS_MANIFEST.json
?? backend/architecture/phase4f_6/decision/E0_ERRATUM_2026-09-27.md
?? backend/architecture/phase4f_6/decision/E0_MEDIA_DETECTION_RECORD.json
?? backend/architecture/phase4f_6/decision/E0_OFFLINE_RUNTIME_PROVISIONING.md
?? backend/architecture/phase4f_6/decision/E0_PREDICTION_PROVENANCE_2026-09-28.md
?? backend/architecture/phase4f_6/decision/E0_PREREQUISITE_STATUS.md
?? backend/architecture/phase4f_6/decision/E0_PROTOCOL.md
?? backend/architecture/phase4f_6/decision/E0_READINESS_CHECK.md
?? backend/architecture/phase4f_6/decision/E0_RETRIEVAL_RUNTIME_READINESS.md
?? backend/architecture/phase4f_6/decision/E0_RETRIEVAL_RUNTIME_RESUME.md
?? backend/architecture/phase4f_6/decision/E0_RETRIEVAL_RUN_MANIFEST.json
?? backend/architecture/phase4f_6/decision/E0_RUNTIME_HANDOFF_MANIFEST.json
?? backend/architecture/phase4f_6/decision/E0_SCHEMA.json
?? backend/architecture/phase4f_6/decision/E0_SOURCE_PROVENANCE.md
?? backend/architecture/phase4f_6/decision/EXPERIMENT_CANDIDATE_MATRIX.md
?? backend/architecture/phase4f_6/decision/EXPERIMENT_CONTROL_MATRIX.md
?? backend/architecture/phase4f_6/decision/ISO_COVERAGE_RESCORING.json
?? backend/architecture/phase4f_6/decision/ISO_COVERAGE_RESCORING.md
?? backend/architecture/phase4f_6/decision/MODEL_40MIN_EVALUATION.json
?? backend/architecture/phase4f_6/decision/MODEL_40MIN_EVALUATION.md
?? backend/architecture/phase4f_6/decision/NEXT_EXPERIMENT_DECISION.md
?? backend/architecture/phase4f_6/decision/PHASE4F6B_RECONCILIATION.md
?? backend/architecture/phase4f_6/decision/PHASE4F6C_RECONCILIATION.md
?? backend/architecture/phase4f_6/decision/PROTOCOL_V2_SPAN_SELECTION_ROLLOUT.json
?? backend/architecture/phase4f_6/decision/PROTOCOL_V2_SPAN_SELECTION_ROLLOUT.md
?? backend/architecture/phase4f_6/decision/QA_HYPOTHESIS_MATRIX.md
?? backend/architecture/phase4f_6/decision/RECONSTRUCTION_BOUND.json
?? backend/architecture/phase4f_6/decision/RECONSTRUCTION_BOUND.md
?? backend/architecture/phase4f_6/decision/SCORE_STATISTIC_ISO_K47.json
?? backend/architecture/phase4f_6/decision/SCORE_STATISTIC_ISO_K47.md
?? backend/architecture/phase4f_6/decision/SCORE_STATISTIC_ISO_K95.json
?? backend/architecture/phase4f_6/decision/SCORE_STATISTIC_ISO_K95.md
?? backend/architecture/phase4f_6/decision/SPAN_BOUNDARY_FORENSICS.json
?? backend/architecture/phase4f_6/decision/SPAN_BOUNDARY_FORENSICS.md
?? backend/architecture/phase4f_6/decision/SPAN_SELECTION_PROTOCOL_EXPERIMENT.json
?? backend/architecture/phase4f_6/decision/SPAN_SELECTION_PROTOCOL_EXPERIMENT.md
?? backend/architecture/phase4f_6/e0_diagnostics/chunks/api_docs_lambda.jsonl
?? backend/architecture/phase4f_6/e0_diagnostics/chunks/company_history_eta.jsonl
?? backend/architecture/phase4f_6/e0_diagnostics/chunks/dataset_desc_mu.jsonl
?? backend/architecture/phase4f_6/e0_diagnostics/chunks/financial_report_q3.jsonl
?? backend/architecture/phase4f_6/e0_diagnostics/chunks/legal_contract_epsilon.jsonl
?? backend/architecture/phase4f_6/e0_diagnostics/chunks/unanswerable_corpus.jsonl
?? backend/architecture/phase4f_6/e0_diagnostics/diagnostics/answerability_signal_bootstrap.json
?? backend/architecture/phase4f_6/e0_diagnostics/diagnostics/auc_influence_jackknife.json
?? backend/architecture/phase4f_6/e0_diagnostics/diagnostics/chunk_evidence_results.jsonl
?? backend/architecture/phase4f_6/e0_diagnostics/diagnostics/cls_direction_reversal_bootstrap.json
?? backend/architecture/phase4f_6/e0_diagnostics/diagnostics/embedding_offline_verification.json
?? backend/architecture/phase4f_6/e0_diagnostics/diagnostics/model_40min_predictions.json
?? backend/architecture/phase4f_6/e0_diagnostics/diagnostics/provenance_results.jsonl
?? backend/architecture/phase4f_6/e0_diagnostics/diagnostics/runtime_validation_schema.json
?? backend/architecture/phase4f_6/e0_diagnostics/diagnostics/summary.json
?? backend/architecture/phase4f_6/e0_diagnostics/offline_runtime_checklist.json
?? backend/architecture/phase4f_6/e0_diagnostics/retrieval_schema_requirements.json
?? backend/architecture/phase4f_6/e0_diagnostics/source_corpus/api_docs_lambda.json
?? backend/architecture/phase4f_6/e0_diagnostics/source_corpus/company_history_eta.json
?? backend/architecture/phase4f_6/e0_diagnostics/source_corpus/dataset_desc_mu.json
?? backend/architecture/phase4f_6/e0_diagnostics/source_corpus/financial_report_q3.json
?? backend/architecture/phase4f_6/e0_diagnostics/source_corpus/legal_contract_epsilon.json
?? backend/architecture/phase4f_6/e0_diagnostics/source_corpus/unanswerable_corpus.json
?? backend/architecture/phase4f_6/e0_diagnostics/tools/answerability_signal_forensics.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/auc_influence_jackknife_forensics.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/build_e0_prereqs.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/cls_direction_reversal_forensics.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/detect_runtime_media.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/reconstruction_bound.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/rescore_abstention_gate.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/rescore_iso_coverage.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/rescore_score_statistics_k47.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/rescore_score_statistics_k95.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/run_model_40min_eval.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/span_boundary_forensics.py
?? backend/architecture/phase4f_6/e0_diagnostics/tools/span_selection_protocol_experiment.py
?? backend/docker-entrypoint.sh
?? backend/documents/insights.py
?? backend/documents/parser.py
?? backend/documents/structure.py
?? backend/documents/tables.py
?? backend/evaluation/README.md
?? backend/evaluation/artifacts.py
?? backend/evaluation/baselines/__init__.py
?? backend/evaluation/baselines/dual_path/__init__.py
?? backend/evaluation/baselines/structure_only/__init__.py
?? backend/evaluation/baselines/vector_only/__init__.py
?? backend/evaluation/datasets/__init__.py
?? backend/evaluation/datasets/heading_corpus.py
?? backend/evaluation/datasets/phase3d_corpus.py
?? backend/evaluation/datasets/phase4b_corpus.py
?? backend/evaluation/datasets/structure_discriminating_v1.py
?? backend/evaluation/datasets/structure_eval_corpus.py
?? backend/evaluation/denominator_sensitivity.py
?? backend/evaluation/experiments/__init__.py
?? backend/evaluation/experiments/run_dual_path_ablation.py
?? backend/evaluation/experiments/run_phase3d_evaluation.py
?? backend/evaluation/experiments/run_phase3d_upload_integration.py
?? backend/evaluation/experiments/run_phase3e_integration.py
?? backend/evaluation/experiments/run_phase3e_validation.py
?? backend/evaluation/experiments/run_phase3f_evaluation.py
?? backend/evaluation/experiments/run_phase4b_evaluation.py
?? backend/evaluation/experiments/run_phase4c_diagnostics.py
?? backend/evaluation/experiments/run_structure_confirmation.py
?? backend/evaluation/experiments/run_structure_element_measurement.py
?? backend/evaluation/experiments/run_structure_rrf_calibration.py
?? backend/evaluation/experiments/run_table_evidence_measurement.py
?? backend/evaluation/experiments/synthesize_structure_discriminating.py
?? backend/evaluation/isolation.py
?? backend/evaluation/metrics/__init__.py
?? backend/evaluation/qa_metrics.py
?? backend/evaluation/reports/__init__.py
?? backend/evaluation/reports/ablation_A.json
?? backend/evaluation/reports/ablation_A.md
?? backend/evaluation/reports/ablation_B.json
?? backend/evaluation/reports/ablation_B.md
?? backend/evaluation/reports/ablation_C.json
?? backend/evaluation/reports/ablation_C.md
?? backend/evaluation/reports/ablation_D.json
?? backend/evaluation/reports/ablation_D.md
?? backend/evaluation/reports/ablation_config.json
?? backend/evaluation/reports/ablation_heading_A.json
?? backend/evaluation/reports/ablation_heading_A.md
?? backend/evaluation/reports/ablation_heading_B.json
?? backend/evaluation/reports/ablation_heading_B.md
?? backend/evaluation/reports/ablation_heading_C.json
?? backend/evaluation/reports/ablation_heading_C.md
?? backend/evaluation/reports/ablation_heading_D.json
?? backend/evaluation/reports/ablation_heading_D.md
?? backend/evaluation/reports/ablation_heading_config.json
?? backend/evaluation/reports/ablation_structure_discriminating_A.json
?? backend/evaluation/reports/ablation_structure_discriminating_A.md
?? backend/evaluation/reports/ablation_structure_discriminating_B.json
?? backend/evaluation/reports/ablation_structure_discriminating_B.md
?? backend/evaluation/reports/ablation_structure_discriminating_C.json
?? backend/evaluation/reports/ablation_structure_discriminating_C.md
?? backend/evaluation/reports/ablation_structure_discriminating_D.json
?? backend/evaluation/reports/ablation_structure_discriminating_D.md
?? backend/evaluation/reports/ablation_structure_discriminating_config.json
?? backend/evaluation/reports/denominator_sensitivity.json
?? backend/evaluation/reports/denominator_sensitivity.md
?? backend/evaluation/reports/structural_retrieval_fix_report.md
?? backend/evaluation/reports/structural_retrieval_reachability_audit.md
?? backend/evaluation/reports/structure_confirmation.json
?? backend/evaluation/reports/structure_confirmation_report.md
?? backend/evaluation/reports/structure_discriminating_ablation_report.md
?? backend/evaluation/reports/structure_discriminating_analysis.json
?? backend/evaluation/reports/structure_discriminating_v1_audit.md
?? backend/evaluation/reports/structure_element_measurement_analysis.json
?? backend/evaluation/reports/structure_element_measurement_control.json
?? backend/evaluation/reports/structure_element_measurement_report.md
?? backend/evaluation/reports/structure_element_measurement_treatment.json
?? backend/evaluation/reports/structure_eval.json
?? backend/evaluation/reports/structure_eval.md
?? backend/evaluation/reports/structure_rrf_calibration.json
?? backend/evaluation/reports/structure_rrf_calibration_report.md
?? backend/evaluation/reports/table_evidence_architecture.md
?? backend/evaluation/reports/table_evidence_measurement_analysis.json
?? backend/evaluation/reports/table_evidence_measurement_control.json
?? backend/evaluation/reports/table_evidence_measurement_report.md
?? backend/evaluation/reports/table_evidence_measurement_treatment.json
?? backend/evaluation/retrieval_metrics.py
?? backend/evaluation/runner.py
?? backend/evaluation/schemas.py
?? backend/evaluation/structure_eval.py
?? backend/graph/__init__.py
?? backend/graph/evidence.py
?? backend/graph/models.py
?? backend/graph/service.py
?? backend/migrations/versions/005_add_document_graph.py
?? backend/migrations/versions/006_add_structure_elements.py
?? backend/migrations/versions/007_add_table_rows.py
?? backend/models/media-verification/MANIFEST.json
?? backend/models/media-verification/config.json
?? backend/models/media-verification/preprocessor_config.json
?? backend/models/whisper/small/config.json
?? backend/models/whisper/small/model.bin
?? backend/models/whisper/small/tokenizer.json
?? backend/models/whisper/small/vocabulary.txt
?? backend/phases/phase3d_evaluation_report.json
?? backend/phases/phase3f_evaluation_report.json
?? backend/phases/phase3f_validation_report.txt
?? backend/phases/phase3g_pipeline_audit.txt
?? backend/phases/phase4a_qa_failure_audit.txt
?? backend/phases/phase4b_evaluation_report.json
?? backend/phases/phase4b_qa_evaluation_report.txt
?? backend/phases/phase4c_failure_matrix.json
?? backend/phases/phase4c_qa_failure_isolation_report.txt
?? backend/phases/phase4d/__init__.py
?? backend/phases/phase4d/__main__.py
?? backend/phases/phase4d/evaluate_candidates.py
?? backend/phases/phase4d/generate_report.py
?? backend/phases/phase4d/oracle_eval.py
?? backend/phases/phase4d/reconciliation.py
?? backend/phases/phase4d/train.py
?? backend/phases/phase4d/training_data.py
?? backend/phases/phase4d_1_reconciliation.json
?? backend/phases/phase4d_1_reconciliation_report.txt
?? backend/phases/phase4d_experiment_results.json
?? backend/phases/phase4d_oracle_baseline_results.json
?? backend/phases/phase4d_qa_model_improvement_report.txt
?? backend/phases/phase4e/__init__.py
?? backend/phases/phase4e/capability_analysis.py
?? backend/phases/phase4e/generate_report.py
?? backend/phases/phase4e_capability_matrix.json
?? backend/phases/phase4e_diagnostic_results.json
?? backend/phases/phase4e_qa_architecture_analysis.txt
?? backend/phases/phase4f/__init__.py
?? backend/phases/phase4f/balance_gate.py
?? backend/phases/phase4f/dataset/__init__.py
?? backend/phases/phase4f/dataset/dataset_manifest.json
?? backend/phases/phase4f/dataset/dataset_manifest_v3.json
?? backend/phases/phase4f/dataset/dataset_manifest_v3_1.json
?? backend/phases/phase4f/dataset/dataset_metadata.json
?? backend/phases/phase4f/dataset/dataset_quality_report.json
?? backend/phases/phase4f/dataset/dataset_quality_report_v3.json
?? backend/phases/phase4f/dataset/dataset_quality_report_v3_1.json
?? backend/phases/phase4f/dataset/expand_and_audit.py
?? backend/phases/phase4f/dataset/generator.py
?? backend/phases/phase4f/dataset/training_data.jsonl
?? backend/phases/phase4f/dataset/training_data_v3.jsonl
?? backend/phases/phase4f/dataset/training_data_v3_1.jsonl
?? backend/phases/phase4f/experiments/evaluate.py
?? backend/phases/phase4f/experiments/experiment_manifest.json
?? backend/phases/phase4f/experiments/final_gpu_package/README_GPU_EXECUTION.md
?? backend/phases/phase4f/experiments/final_gpu_package/dataset/training_data_v3_1.jsonl
?? backend/phases/phase4f/experiments/final_gpu_package/dataset_checksum.txt
?? backend/phases/phase4f/experiments/final_gpu_package/evaluation/evaluate.py
?? backend/phases/phase4f/experiments/final_gpu_package/expected_output_structure.txt
?? backend/phases/phase4f/experiments/final_gpu_package/final_gpu_package_manifest.json
?? backend/phases/phase4f/experiments/final_gpu_package/production_model_checksum.txt
?? backend/phases/phase4f/experiments/final_gpu_package/requirements.txt
?? backend/phases/phase4f/experiments/final_gpu_package/training/experiment_config.json
?? backend/phases/phase4f/experiments/final_gpu_package/training/train.py
?? backend/phases/phase4f/experiments/phase4f_3_results.json
?? backend/phases/phase4f/experiments/phase4f_3_training_report.txt
?? backend/phases/phase4f/experiments/phase4f_3r_freeze_report.txt
?? backend/phases/phase4f/experiments/phase4f_4_controlled_gpu_experiment_report.txt
?? backend/phases/phase4f/experiments/phase4f_4_experiment_manifest.json
?? backend/phases/phase4f/experiments/phase4f_4_results.json
?? backend/phases/phase4f/experiments/phase4f_4e_cuda_environment.json
?? backend/phases/phase4f/experiments/phase4f_4e_cuda_environment_report.txt
?? backend/phases/phase4f/experiments/requirements.txt
?? backend/phases/phase4f/experiments/results.pre_joint_selection_v1/all_results.json
?? backend/phases/phase4f/experiments/results/A0/evaluation_results.json
?? backend/phases/phase4f/experiments/results/A0/metadata.json
?? backend/phases/phase4f/experiments/results/A1/checkpoint_best/config.json
?? backend/phases/phase4f/experiments/results/A1/checkpoint_best/tokenizer.json
?? backend/phases/phase4f/experiments/results/A1/checkpoint_best/tokenizer_config.json
?? backend/phases/phase4f/experiments/results/A1/evaluation_results.json
?? backend/phases/phase4f/experiments/results/A1/training_metadata.json
?? backend/phases/phase4f/experiments/results/A2/checkpoint_best/config.json
?? backend/phases/phase4f/experiments/results/A2/checkpoint_best/tokenizer.json
?? backend/phases/phase4f/experiments/results/A2/checkpoint_best/tokenizer_config.json
?? backend/phases/phase4f/experiments/results/A2/evaluation_results.json
?? backend/phases/phase4f/experiments/results/A2/training_metadata.json
?? backend/phases/phase4f/experiments/results/A3/checkpoint_best/config.json
?? backend/phases/phase4f/experiments/results/A3/checkpoint_best/tokenizer.json
?? backend/phases/phase4f/experiments/results/A3/checkpoint_best/tokenizer_config.json
?? backend/phases/phase4f/experiments/results/A3/evaluation_results.json
?? backend/phases/phase4f/experiments/results/A3/training_metadata.json
?? backend/phases/phase4f/experiments/results/all_results.json
?? backend/phases/phase4f/experiments/results_reconstruction_fix/A0/evaluation_results.json
?? backend/phases/phase4f/experiments/results_reconstruction_fix/A0_gpu_package/evaluation_results.json
?? backend/phases/phase4f/experiments/run_experiment.py
?? backend/phases/phase4f/experiments/train.py
?? backend/phases/phase4f/freeze_gate.py
?? backend/phases/phase4f/gate_common.py
?? backend/phases/phase4f/phase4f_1_dataset_audit_report.txt
?? backend/phases/phase4f/phase4f_2_dataset_quality_gate_report.txt
?? backend/phases/phase4f/phase4f_2r_dataset_balance_report.txt
?? backend/phases/phase4f/phase4f_4r_manifest.json
?? backend/phases/phase4f/phase4f_5/configs/a1_config.json
?? backend/phases/phase4f/phase4f_5/configs/a2_config.json
?? backend/phases/phase4f/phase4f_5/dataset/data_quality_gate.json
?? backend/phases/phase4f/phase4f_5/dataset/derived_dataset.jsonl
?? backend/phases/phase4f/phase4f_5/dataset/span_alignment_audit.json
?? backend/phases/phase4f/phase4f_5/dataset/truncation_audit.json
?? backend/phases/phase4f/phase4f_5/diagnostics/a0_forensics.json
?? backend/phases/phase4f/phase4f_5/diagnostics/a1_forensics.json
?? backend/phases/phase4f/phase4f_5/diagnostics/a2_forensics.json
?? backend/phases/phase4f/phase4f_5/diagnostics/all_inference_results.json
?? backend/phases/phase4f/phase4f_5/diagnostics/failure_taxonomy.json
?? backend/phases/phase4f/phase4f_5/evaluation/A0_test_results.json
?? backend/phases/phase4f/phase4f_5/evaluation/A1_test_results.json
?? backend/phases/phase4f/phase4f_5/evaluation/A2_test_results.json
?? backend/phases/phase4f/phase4f_5/evaluation/evaluate.py
?? backend/phases/phase4f/phase4f_5/evaluation/evaluation_protocol.json
?? backend/phases/phase4f/phase4f_5/logs/a1_training.json
?? backend/phases/phase4f/phase4f_5/logs/a2_training.json
?? backend/phases/phase4f/phase4f_5/manifests/experiment_manifest.json
?? backend/phases/phase4f/phase4f_5/manifests/final_experiment_manifest.json
?? backend/phases/phase4f/phase4f_5/manifests/source_integrity.json
?? backend/phases/phase4f/phase4f_5/manifests/split_manifest.json
?? backend/phases/phase4f/phase4f_5/prepare_experiment.py
?? backend/phases/phase4f/phase4f_5/reports/phase4f_5a_preparation_report.txt
?? backend/phases/phase4f/phase4f_5/reports/phase4f_5b_training_report.txt
?? backend/phases/phase4f/phase4f_5/results.pre_joint_selection_v1/a0_test.json
?? backend/phases/phase4f/phase4f_5/results.pre_joint_selection_v1/a1_test.json
?? backend/phases/phase4f/phase4f_5/results.pre_joint_selection_v1/a2_test.json
?? backend/phases/phase4f/phase4f_5/results.pre_joint_selection_v1/comparison.json
?? backend/phases/phase4f/phase4f_5/results.pre_reconstruction_fix/a0_test.json
?? backend/phases/phase4f/phase4f_5/results.pre_reconstruction_fix/a1_test.json
?? backend/phases/phase4f/phase4f_5/results.pre_reconstruction_fix/a2_test.json
?? backend/phases/phase4f/phase4f_5/results.pre_reconstruction_fix/comparison.json
?? backend/phases/phase4f/phase4f_5/results/a0_test.json
?? backend/phases/phase4f/phase4f_5/results/a0_test.protocol_v1_argmaxchain.json
?? backend/phases/phase4f/phase4f_5/results/a0_test.protocol_v2_joint.json
?? backend/phases/phase4f/phase4f_5/results/a1_test.json
?? backend/phases/phase4f/phase4f_5/results/a1_test.protocol_v1_argmaxchain.json
?? backend/phases/phase4f/phase4f_5/results/a1_test.protocol_v2_joint.json
?? backend/phases/phase4f/phase4f_5/results/a2_test.json
?? backend/phases/phase4f/phase4f_5/results/a2_test.protocol_v1_argmaxchain.json
?? backend/phases/phase4f/phase4f_5/results/a2_test.protocol_v2_joint.json
?? backend/phases/phase4f/phase4f_5/results/comparison.json
?? backend/phases/phase4f/phase4f_5/run_experiment.py
?? backend/phases/phase4f/phase4f_5c/em_f1_gap_analysis.json
?? backend/phases/phase4f/phase4f_5c/failure_matrix.json
?? backend/phases/phase4f/phase4f_5c/generate_analysis.py
?? backend/phases/phase4f/phase4f_5c/list_audit.json
?? backend/phases/phase4f/phase4f_5c/long_context_audit.json
?? backend/phases/phase4f/phase4f_5c/normalization_diagnostic.json
?? backend/phases/phase4f/phase4f_5c/numeric_audit.json
?? backend/phases/phase4f/phase4f_5c/per_category_comparison.json
?? backend/phases/phase4f/phase4f_5c/phase4f_5c_manifest.json
?? backend/phases/phase4f/phase4f_5c/production_strengths.json
?? backend/phases/phase4f/phase4f_5c/reports/phase4f_5c_qa_analysis_report.txt
?? backend/phases/phase4f/phase4f_5c/root_cause_analysis.json
?? backend/phases/phase4f/phase4f_5c/table_audit.json
?? backend/phases/phase4f/phase4f_5c/test_composition.json
?? backend/phases/phase4f/phase4f_5c/training_curve_analysis.json
?? backend/phases/phase4f/phase4f_5d/analysis.pre_joint_selection_v1/a0_benchmark_v1.json
?? backend/phases/phase4f/phase4f_5d/analysis.pre_joint_selection_v1/a1_benchmark_v1.json
?? backend/phases/phase4f/phase4f_5d/analysis.pre_joint_selection_v1/a2_benchmark_v1.json
?? backend/phases/phase4f/phase4f_5d/analysis.pre_joint_selection_v1/benchmark_comparison.json
?? backend/phases/phase4f/phase4f_5d/analysis.pre_joint_selection_v1/category_balance.json
?? backend/phases/phase4f/phase4f_5d/analysis.pre_joint_selection_v1/duplicate_audit.json
?? backend/phases/phase4f/phase4f_5d/analysis.pre_joint_selection_v1/gold_span_validation.json
?? backend/phases/phase4f/phase4f_5d/analysis.pre_joint_selection_v1/leakage_audit.json
?? backend/phases/phase4f/phase4f_5d/analysis.pre_joint_selection_v1/test_composition.json
?? backend/phases/phase4f/phase4f_5d/analysis.pre_joint_selection_v1/unanswerable_audit.json
?? backend/phases/phase4f/phase4f_5d/analysis/a0_benchmark_v1.json
?? backend/phases/phase4f/phase4f_5d/analysis/a1_benchmark_v1.json
?? backend/phases/phase4f/phase4f_5d/analysis/a2_benchmark_v1.json
?? backend/phases/phase4f/phase4f_5d/analysis/benchmark_comparison.json
?? backend/phases/phase4f/phase4f_5d/analysis/category_balance.json
?? backend/phases/phase4f/phase4f_5d/analysis/duplicate_audit.json
?? backend/phases/phase4f/phase4f_5d/analysis/gold_span_validation.json
?? backend/phases/phase4f/phase4f_5d/analysis/leakage_audit.json
?? backend/phases/phase4f/phase4f_5d/analysis/test_composition.json
?? backend/phases/phase4f/phase4f_5d/analysis/unanswerable_audit.json
?? backend/phases/phase4f/phase4f_5d/benchmark/benchmark_checksum.txt
?? backend/phases/phase4f/phase4f_5d/benchmark/benchmark_manifest.json
?? backend/phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl
?? backend/phases/phase4f/phase4f_5d/build_benchmark.py
?? backend/phases/phase4f/phase4f_5d/phase4f_5d_manifest.json
?? backend/phases/phase4f/phase4f_5d/reports/phase4f_5d_benchmark_hardening_report.txt
?? backend/phases/phase4f/phase4f_5e/analysis.pre_joint_selection_v1/capability_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_joint_selection_v1/confidence_distribution.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_joint_selection_v1/f1_gain_analysis.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_joint_selection_v1/next_experiment_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_joint_selection_v1/production_vs_experiment.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_joint_selection_v1/root_cause_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_joint_selection_v1/split_category_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_joint_selection_v1/threshold_sweep.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_joint_selection_v1/training_data_audit.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_joint_selection_v1/unanswerable_audit.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_reconstruction_fix/capability_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_reconstruction_fix/confidence_distribution.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_reconstruction_fix/f1_gain_analysis.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_reconstruction_fix/next_experiment_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_reconstruction_fix/production_vs_experiment.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_reconstruction_fix/root_cause_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_reconstruction_fix/split_category_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_reconstruction_fix/threshold_sweep.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_reconstruction_fix/training_data_audit.json
?? backend/phases/phase4f/phase4f_5e/analysis.pre_reconstruction_fix/unanswerable_audit.json
?? backend/phases/phase4f/phase4f_5e/analysis/capability_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis/confidence_distribution.json
?? backend/phases/phase4f/phase4f_5e/analysis/f1_gain_analysis.json
?? backend/phases/phase4f/phase4f_5e/analysis/next_experiment_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis/production_vs_experiment.json
?? backend/phases/phase4f/phase4f_5e/analysis/root_cause_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis/split_category_matrix.json
?? backend/phases/phase4f/phase4f_5e/analysis/threshold_sweep.json
?? backend/phases/phase4f/phase4f_5e/analysis/training_data_audit.json
?? backend/phases/phase4f/phase4f_5e/analysis/unanswerable_audit.json
?? backend/phases/phase4f/phase4f_5e/phase4f_5e_manifest.json
?? backend/phases/phase4f/phase4f_5e/reports/phase4f_5e_qa_capability_audit.txt
?? backend/phases/phase4f/phase4f_5e/run_analysis.py
?? backend/phases/phase4f/phase4f_5f/dataset/experiment_f1_manifest.json
?? backend/phases/phase4f/phase4f_5f/dataset/experiment_f1_quality_report.json
?? backend/phases/phase4f/phase4f_5f/dataset/experiment_f1_split.json
?? backend/phases/phase4f/phase4f_5f/f2/config/f2_config.json
?? backend/phases/phase4f/phase4f_5f/f2/evaluation/f2_benchmark.json
?? backend/phases/phase4f/phase4f_5f/f2/evaluation/f2_holdout.json
?? backend/phases/phase4f/phase4f_5f/f2/evaluation/f2_validation.json
?? backend/phases/phase4f/phase4f_5f/f2/logs/f2_training.json
?? backend/phases/phase4f/phase4f_5f/f2/manifests/f2_dataset_ids.json
?? backend/phases/phase4f/phase4f_5f/f2/manifests/f2_manifest.json
?? backend/phases/phase4f/phase4f_5f/f2/reconciliation/f2_baseline_comparison.json
?? backend/phases/phase4f/phase4f_5f/f2/reconciliation/f2_data_balance_audit.json
?? backend/phases/phase4f/phase4f_5f/f2/reconciliation/f2_label_audit.json
?? backend/phases/phase4f/phase4f_5f/f2/reconciliation/f2_no_answer_logic_audit.json
?? backend/phases/phase4f/phase4f_5f/f2/reconciliation/f2_prediction_audit.json
?? backend/phases/phase4f/phase4f_5f/f2/reconciliation/f2_root_cause_analysis.json
?? backend/phases/phase4f/phase4f_5f/f2/reports/phase4f_5f_f2_final_report.txt
?? backend/phases/phase4f/phase4f_5f/f2/reports/phase4f_5f_f2_reconciliation_report.txt
?? backend/phases/phase4f/phase4f_5f/f2/reports/phase4f_5f_g_threshold_report.txt
?? backend/phases/phase4f/phase4f_5f/f2/run_f2.py
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/benchmark_result.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/holdout_result.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/margin_sweep.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/raw_prediction_audit.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/raw_predictions_benchmark.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/raw_predictions_holdout.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/raw_predictions_validation.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/run_threshold_experiment.py
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/stability_analysis.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/threshold_experiment_manifest.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/threshold_sweep.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_joint_selection_v1/validation_calibration.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/benchmark_result.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/holdout_result.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/margin_sweep.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/raw_prediction_audit.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/raw_predictions_benchmark.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/raw_predictions_holdout.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/raw_predictions_validation.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/run_threshold_experiment.py
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/stability_analysis.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/threshold_experiment_manifest.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/threshold_sweep.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment.pre_reconstruction_fix/validation_calibration.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/benchmark_result.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/holdout_result.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/margin_sweep.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/raw_prediction_audit.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/raw_predictions_benchmark.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/raw_predictions_holdout.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/raw_predictions_validation.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/run_threshold_experiment.py
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/stability_analysis.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/threshold_experiment_manifest.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/threshold_sweep.json
?? backend/phases/phase4f/phase4f_5f/f2/threshold_experiment/validation_calibration.json
?? backend/phases/phase4f/phase4f_5f/h/audits/duplicate_audit.json
?? backend/phases/phase4f/phase4f_5f/h/audits/leakage_audit.json
?? backend/phases/phase4f/phase4f_5f/h/audits/quality_gate_failures.json
?? backend/phases/phase4f/phase4f_5f/h/audits/semantic_audit.json
?? backend/phases/phase4f/phase4f_5f/h/candidates/all_candidates.jsonl
?? backend/phases/phase4f/phase4f_5f/h/generate_h_candidates.py
?? backend/phases/phase4f/phase4f_5f/h/manifests/h_manifest.json
?? backend/phases/phase4f/phase4f_5f/h/pools/h10.jsonl
?? backend/phases/phase4f/phase4f_5f/h/pools/h20.jsonl
?? backend/phases/phase4f/phase4f_5f/h/pools/h30.jsonl
?? backend/phases/phase4f/phase4f_5f/h/reports/phase4f_5f_h_dataset_design_report.txt
?? backend/phases/phase4f/phase4f_5f/h1/config/f1_reconciled_ids.json
?? backend/phases/phase4f/phase4f_5f/h1/config/h1_config.json
?? backend/phases/phase4f/phase4f_5f/h1/evaluation/h1_benchmark.json
?? backend/phases/phase4f/phase4f_5f/h1/evaluation/h1_holdout.json
?? backend/phases/phase4f/phase4f_5f/h1/evaluation/h1_null_analysis.json
?? backend/phases/phase4f/phase4f_5f/h1/evaluation/h1_validation.json
?? backend/phases/phase4f/phase4f_5f/h1/logs/h1_training.json
?? backend/phases/phase4f/phase4f_5f/h1/manifests/h1_manifest.json
?? backend/phases/phase4f/phase4f_5f/h1/reports/phase4f_5f_h1_final_report.txt
?? backend/phases/phase4f/phase4f_5f/h1/run_h1.py
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/H1_RECONCILIATION_REPORT.md
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/README.md
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/checksums.txt
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/h1_count_reconciliation.json
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/h1_label_integrity.json
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/h1_metric_recalculation.json
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/h1_no_answer_analysis.json
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/h1_null_score_analysis.json
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/h1_overlap_report.json
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/h1_protocol_audit.json
?? backend/phases/phase4f/phase4f_5f/h1_reconciliation/h1_reconciled_comparison.json
?? backend/phases/phase4f/phase4f_5f/phase4f_5f_f1_reconciliation_manifest.json
?? backend/phases/phase4f/phase4f_5f/reconciliation/dataset_reconciliation.json
?? backend/phases/phase4f/phase4f_5f/reconciliation/final_holdout_ids.json
?? backend/phases/phase4f/phase4f_5f/reconciliation/final_training_ids.json
?? backend/phases/phase4f/phase4f_5f/reconciliation/final_validation_ids.json
?? backend/phases/phase4f/phase4f_5f/reconciliation/invalid_span_audit.json
?? backend/phases/phase4f/phase4f_5f/reconciliation/training_protocol_audit.json
?? backend/phases/phase4f/phase4f_5f/recovery/artifact_inventory.json
?? backend/phases/phase4f/phase4f_5f/recovery/gpu_environment_report.json
?? backend/phases/phase4f/phase4f_5f/recovery/gpu_environment_report.txt
?? backend/phases/phase4f/phase4f_5f/recovery/phase4f_5f_recovery_report.txt
?? backend/phases/phase4f/phase4f_5f/recovery/recovery_manifest.json
?? backend/phases/phase4f/phase4f_5f/reports/phase4f_5f_f1_preparation_report.txt
?? backend/phases/phase4f/phase4f_5f/reports/phase4f_5f_f1_reconciliation_report.txt
?? backend/phases/phase4f/phase4f_5f/research_ledger/RESEARCH_LEDGER.md
?? backend/phases/phase4f/phase4f_5f/research_ledger/checksums.txt
?? backend/phases/phase4f/phase4f_5f/research_ledger/research_ledger.json
?? backend/phases/phase4f/phase4f_5f/run_experiment.py
?? backend/phases/phase4f/quality_gate.py
?? backend/phases/phase4f/reconciliation/a0_reproduction.json
?? backend/phases/phase4f/reconciliation/checkpoint_audit.json
?? backend/phases/phase4f/reconciliation/cross_phase_evaluation_compatibility.json
?? backend/phases/phase4f/reconciliation/dataset_label_audit.json
?? backend/phases/phase4f/reconciliation/evaluation_parity_matrix.json
?? backend/phases/phase4f/reconciliation/experiment_artifact_inventory.json
?? backend/phases/phase4f/reconciliation/failure_taxonomy_reconciliation.json
?? backend/phases/phase4f/reconciliation/manual_forensic_traces.json
?? backend/phases/phase4f/reconciliation/model_initialization_audit.json
?? backend/phases/phase4f/reconciliation/phase4f_4r_reconciliation_report.txt
?? backend/phases/phase4f/reconciliation/token_span_audit.json
?? backend/phases/phase4f/reconciliation/training_configuration_audit.json
?? backend/phases/phase4f/training/__init__.py
?? backend/phases/phase4f/training/configs.py
?? backend/phases/phase4f/training/environment.json
?? backend/phases/phase4f/training/train.py
?? backend/phases/phase4f_qa_architecture_experiment_report.txt
?? backend/scripts/cleanup_orphan_uploads.py
?? backend/scripts/cleanup_path.py
?? backend/scripts/cleanup_smoke.py
?? backend/scripts/create_test_user.py
?? backend/scripts/db_check.py
?? backend/scripts/setup_db.py
?? backend/scripts/start_server.py
?? backend/tests/README.md
?? backend/tests/e2e/__init__.py
?? backend/tests/e2e/browser/__init__.py
?? backend/tests/e2e/browser/test_browser_flow.py
?? backend/tests/e2e/browser/test_document_flow.py
?? backend/tests/e2e/browser/test_embedding_flow.py
?? backend/tests/e2e/browser/test_phase6_reliability.py
?? backend/tests/e2e/browser/test_rag_flow.py
?? backend/tests/e2e/browser/test_real_browser.py
?? backend/tests/fixtures/__init__.py
?? backend/tests/fixtures/darwin_proper.pdf
?? backend/tests/fixtures/e2e_config.py
?? backend/tests/fixtures/graph_data.py
?? backend/tests/fixtures/integration_db.py
?? backend/tests/fixtures/integration_http.py
?? backend/tests/fixtures/live_server.py
?? backend/tests/fixtures/paths.py
?? backend/tests/fixtures/pdf_layout.py
?? backend/tests/integration/__init__.py
?? backend/tests/integration/auth/__init__.py
?? backend/tests/integration/auth/test_auth.py
?? backend/tests/integration/documents/__init__.py
?? backend/tests/integration/documents/test_document_detail_pagination.py
?? backend/tests/integration/documents/test_document_insights.py
?? backend/tests/integration/documents/test_document_mutation_id_validation.py
?? backend/tests/integration/documents/test_file_validation.py
?? backend/tests/integration/documents/test_table_row_migration.py
?? backend/tests/integration/documents/test_table_row_persistence.py
?? backend/tests/integration/embeddings/__init__.py
?? backend/tests/integration/embeddings/test_generate_error_handling.py
?? backend/tests/integration/graph/__init__.py
?? backend/tests/integration/graph/test_graph_ingestion.py
?? backend/tests/integration/graph/test_graph_rag_flow.py
?? backend/tests/integration/graph/test_graph_security.py
?? backend/tests/integration/graph/test_structure_augmentation.py
?? backend/tests/integration/graph/test_structure_reachability.py
?? backend/tests/integration/graph/test_table_evidence_api.py
?? backend/tests/integration/graph/test_table_evidence_bands.py
?? backend/tests/integration/rag/__init__.py
?? backend/tests/integration/rag/test_real_e2e_validation.py
?? backend/tests/integration/reliability/__init__.py
?? backend/tests/integration/reliability/test_table_row_reliability_api.py
?? backend/tests/integration/security/__init__.py
?? backend/tests/integration/security/test_cors.py
?? backend/tests/integration/settings/__init__.py
?? backend/tests/integration/settings/test_settings.py
?? backend/tests/integration/verification/__init__.py
?? backend/tests/integration/verification/test_image_verification.py
?? backend/tests/integration/verification/test_verification_integrity.py
?? backend/tests/integration/voice/__init__.py
?? backend/tests/integration/voice/test_voice_synthesize.py
?? backend/tests/integration/voice/test_voice_transcribe.py
?? backend/tests/unit/__init__.py
?? backend/tests/unit/auth/__init__.py
?? backend/tests/unit/auth/test_config_security.py
?? backend/tests/unit/brain/__init__.py
?? backend/tests/unit/brain/test_brain_orchestration.py
?? backend/tests/unit/brain/test_brain_types.py
?? backend/tests/unit/brain/test_outcomes.py
?? backend/tests/unit/chat/__init__.py
?? backend/tests/unit/chat/test_answer_span.py
?? backend/tests/unit/chat/test_chat_unit.py
?? backend/tests/unit/chat/test_phase3d_context.py
?? backend/tests/unit/chat/test_phase3d_reconciliation.py
?? backend/tests/unit/chat/test_qa_answer_reconstruction.py
?? backend/tests/unit/chat/test_table_evidence_gate.py
?? backend/tests/unit/documents/__init__.py
?? backend/tests/unit/documents/test_pdf_read_order.py
?? backend/tests/unit/documents/test_phase3d_chunking.py
?? backend/tests/unit/documents/test_phase3e_processing.py
?? backend/tests/unit/documents/test_structured_extraction.py
?? backend/tests/unit/documents/test_table_rows.py
?? backend/tests/unit/embeddings/__init__.py
?? backend/tests/unit/evaluation/__init__.py
?? backend/tests/unit/evaluation/conftest.py
?? backend/tests/unit/evaluation/test_denominator_sensitivity.py
?? backend/tests/unit/evaluation/test_disposable_database_authorization.py
?? backend/tests/unit/evaluation/test_disposal_authorization_contract.py
?? backend/tests/unit/evaluation/test_evaluation_isolation.py
?? backend/tests/unit/evaluation/test_function_cleanup_authorization.py
?? backend/tests/unit/evaluation/test_heading_corpus.py
?? backend/tests/unit/evaluation/test_isolation_guard_identity.py
?? backend/tests/unit/evaluation/test_legacy_runner_isolation.py
?? backend/tests/unit/evaluation/test_lifecycle_authorization.py
?? backend/tests/unit/evaluation/test_metrics.py
?? backend/tests/unit/evaluation/test_phase3_runner_target_order.py
?? backend/tests/unit/evaluation/test_phase3d_cleanup_scope.py
?? backend/tests/unit/evaluation/test_phase3d_evaluation_cleanup_scope.py
?? backend/tests/unit/evaluation/test_phase3e_integration_cleanup_scope.py
?? backend/tests/unit/evaluation/test_phase3e_validation_cleanup_scope.py
?? backend/tests/unit/evaluation/test_phase3f_evaluation_cleanup_scope.py
?? backend/tests/unit/evaluation/test_phase4b_evaluation_cleanup_scope.py
?? backend/tests/unit/evaluation/test_run_artifacts.py
?? backend/tests/unit/evaluation/test_runner_pre_engine_init.py
?? backend/tests/unit/evaluation/test_runner_report_output.py
?? backend/tests/unit/evaluation/test_structure_discriminating_corpus.py
?? backend/tests/unit/evaluation/test_structure_eval.py
?? backend/tests/unit/evaluation/test_structure_runner_guard_order.py
?? backend/tests/unit/evaluation/test_unsupported_answer_denominator.py
?? backend/tests/unit/graph/__init__.py
?? backend/tests/unit/graph/test_fusion.py
?? backend/tests/unit/graph/test_graph_edges.py
?? backend/tests/unit/graph/test_structural_retrieval.py
?? backend/tests/unit/graph/test_structure_element_retrieval.py
?? backend/tests/unit/reliability/__init__.py
?? backend/tests/unit/reliability/test_table_row_provenance.py
?? backend/tests/unit/scripts/test_cleanup_orphan_uploads.py
?? backend/tests/unit/security/__init__.py
?? backend/tests/unit/security/test_sql_safety.py
?? backend/tests/unit/storage/__init__.py
?? backend/tests/unit/storage/test_database_url.py
?? backend/tests/unit/storage/test_sqlite_type_isolation.py
?? backend/tests/unit/verification/__init__.py
?? backend/verification/service.py
?? backend/voice.py
?? compose.yaml
?? docker/nginx.conf
?? prompts/00_coordinator.md
?? prompts/01_database_agent.md
?? prompts/02_backend_agent.md
?? prompts/03_frontend_agent.md
?? prompts/04_ai_agent.md
?? prompts/05_test_agent.md
?? prompts/06_evaluation_agent.md
?? prompts/07_security_agent.md
?? prompts/08_verifier.md
?? runbooks/docker-runtime.md
?? src/components/common/DocumentInsightsPanel.tsx
?? src/components/common/VoiceInputButton.tsx
?? src/components/common/VoiceSpeakerButton.tsx
```

### 12.4 Database/process/filesystem AST call inventory — SOURCE-VERIFIED

```text
backend/evaluation/artifacts.py:177 _git | 180:subprocess.run
backend/evaluation/experiments/run_dual_path_ablation.py:605 main | 690:async_session, 692:(await db.execute(select(User).where(User.email == EVAL_EMAIL))).scalar_one_or_none, 813:_delete_user_data, 814:db.execute, 696:_delete_user_data, 697:db.execute, 693:db.execute
backend/evaluation/experiments/run_dual_path_ablation.py:861 _delete_user_data | 870:(await db.execute(select(Document.id).where(Document.user_id == user_id))).scalars().all, 876:db.execute, 879:db.execute, 883:db.execute, 886:db.execute, 889:db.execute, 870:(await db.execute(select(Document.id).where(Document.user_id == user_id))).scalars, 871:db.execute
backend/evaluation/experiments/run_phase3d_evaluation.py:539 owned_user_ids | 545:db.execute
backend/evaluation/experiments/run_phase3d_evaluation.py:549 cleanup_harness_rows | 596:db.execute, 597:db.execute, 598:db.execute, 599:db.execute, 602:db.execute, 603:db.execute
backend/evaluation/experiments/run_phase3d_evaluation.py:621 main | 683:create_async_engine, 685:async_sessionmaker, 704:session_factory, 814:cleanup_harness_rows, 711:cleanup_harness_rows
backend/evaluation/experiments/run_phase3d_upload_integration.py:118 cleanup_harness_rows | 158:db.execute, 159:db.execute, 162:db.execute, 163:db.execute
backend/evaluation/experiments/run_phase3d_upload_integration.py:188 main | 262:create_async_engine, 266:async_sessionmaker, 282:session_factory, 548:session_factory, 549:(await db.execute(select(Document).where(Document.id == v2_doc_id))).scalar_one, 558:(await db.execute(select(Document).where(Document.id == legacy_doc_id))).scalar_one, 567:(await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == v2_doc_id).order_by(DocumentChunk.chunk_index))).scalars().all, 604:(await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == legacy_doc_id))).scalars().all, 397:session_factory, 485:session_factory, 526:session_factory, 628:cleanup_harness_rows, 567:(await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == v2_doc_id).order_by(DocumentChunk.chunk_index))).scalars, 604:(await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == legacy_doc_id))).scalars, 528:db.execute, 533:db.execute, 539:db.execute, 544:db.execute, 550:db.execute, 559:db.execute, 568:db.execute, 605:db.execute
backend/evaluation/experiments/run_phase3e_integration.py:66 owned_user_ids | 79:db.execute
backend/evaluation/experiments/run_phase3e_integration.py:83 cleanup_harness_rows | 130:db.execute, 131:db.execute, 132:db.execute, 133:db.execute, 136:db.execute, 137:db.execute
backend/evaluation/experiments/run_phase3e_integration.py:155 main | 221:create_async_engine, 223:async_sessionmaker, 229:session_factory, 289:os.unlink, 417:os.unlink, 533:os.unlink, 278:session_factory, 279:(await db.execute(select(Document).where(Document.id == doc_id))).scalar_one, 318:os.unlink, 386:os.unlink, 429:session_factory, 430:(await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == del_doc_id))).scalars().all, 440:session_factory, 468:session_factory, 479:session_factory, 497:session_factory, 498:(await db.execute(select(Document).where(Document.id == stale_id))).scalar_one_or_none, 510:session_factory, 542:session_factory, 470:cleanup_harness_rows, 511:db.execute, 514:db.execute, 543:cleanup_harness_rows, 430:(await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == del_doc_id))).scalars, 279:db.execute, 498:db.execute, 430:db.execute
backend/evaluation/experiments/run_phase3e_validation.py:65 owned_user_ids | 78:db.execute
backend/evaluation/experiments/run_phase3e_validation.py:82 cleanup_harness_rows | 130:db.execute, 131:db.execute, 132:db.execute, 133:db.execute, 136:db.execute, 137:db.execute
backend/evaluation/experiments/run_phase3e_validation.py:155 main | 214:create_async_engine, 218:async_sessionmaker, 229:session_factory, 356:os.unlink, 620:os.unlink, 767:os.unlink, 814:os.unlink, 267:os.unlink, 273:session_factory, 274:(await db.execute(select(Document).where(Document.id == fail_doc_id))).scalar_one, 360:session_factory, 361:(await db.execute(select(Document).where(Document.id == ready_doc_id))).scalar_one, 377:(await db.execute(select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == ready_doc_id))).scalar, 387:(await db.execute(select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == ready_doc_id, DocumentChunk.embedding.isnot(None)))).scalar, 397:(await db.execute(select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == ready_doc_id, DocumentChunk.embedding.is_(None)))).scalar, 411:session_factory, 442:session_factory, 443:(await db.execute(select(Document).where(Document.id == fail_doc_id))).scalar_one, 463:session_factory, 464:(await db.execute(select(Document).where(Document.id == fail_doc_id))).scalar_one, 472:(await db.execute(select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == fail_doc_id))).scalar, 484:(await db.execute(select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == fail_doc_id, DocumentChunk.embedding.isnot(None)))).scalar, 495:(await db.execute(select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == fail_doc_id, DocumentChunk.embedding.is_(None)))).scalar, 505:(await db.execute(text("SELECT COUNT(*) FROM document_chunks dc JOIN documents d ON d.id = dc.document_id WHERE d.id = :doc_id AND d.embedding_status = 'ready' AND dc.embedding IS NOT NULL"), {'doc_id': str(fail_doc_id)})).scalar, 544:session_factory, 578:session_factory, 624:session_factory, 625:(await db.execute(select(Document).where(Document.id == del_doc_id))).scalar_one_or_none, 628:(await db.execute(select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == del_doc_id))).scalar, 641:session_factory, 642:(await db.execute(select(Document).where(Document.id == del_doc_id))).scalar_one_or_none, 645:(await db.execute(select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == del_doc_id))).scalar, 662:session_factory, 663:(await db.execute(select(Document).where(Document.id == ready_doc_id))).scalar_one, 698:session_factory, 717:session_factory, 747:session_factory, 772:session_factory, 773:(await db.execute(select(Document).where(Document.id == legacy_doc_id))).scalar_one, 779:(await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == legacy_doc_id))).scalars().all, 819:session_factory, 820:(await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == v2_doc_id))).scalars().all, 832:session_factory, 833:(await db.execute(text('SELECT version_num FROM alembic_version'))).scalar, 849:session_factory, 284:db.execute, 297:(await db.execute(select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == fail_doc_id, DocumentChunk.embedding.isnot(None)))).scalar, 303:(await db.execute(select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == fail_doc_id, DocumentChunk.embedding.is_(None)))).scalar, 325:db.execute, 414:db.execute, 579:db.execute, 584:db.execute, 718:db.execute, 749:cleanup_harness_rows, 791:db.execute, 850:cleanup_harness_rows, 779:(await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == legacy_doc_id))).scalars, 820:(await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == v2_doc_id))).scalars, 838:db.execute, 274:db.execute, 361:db.execute, 377:db.execute, 387:db.execute, 397:db.execute, 443:db.execute, 464:db.execute, 472:db.execute, 484:db.execute, 495:db.execute, 505:db.execute, 625:db.execute, 628:db.execute, 642:db.execute, 645:db.execute, 663:db.execute, 773:db.execute, 833:db.execute, 297:db.execute, 303:db.execute, 779:db.execute, 820:db.execute
backend/evaluation/experiments/run_phase3e_validation.py:865 _get_chunk_ids_for_doc | 869:db.execute
backend/evaluation/experiments/run_phase3f_evaluation.py:708 owned_user_ids | 714:db.execute
backend/evaluation/experiments/run_phase3f_evaluation.py:718 cleanup_harness_rows | 767:db.execute, 768:db.execute, 769:db.execute, 770:db.execute, 773:db.execute, 774:db.execute
backend/evaluation/experiments/run_phase3f_evaluation.py:796 main | 850:create_async_engine, 854:async_sessionmaker, 871:session_factory, 1064:cleanup_harness_rows, 879:cleanup_harness_rows
backend/evaluation/experiments/run_phase4b_evaluation.py:688 owned_user_ids | 694:db.execute
backend/evaluation/experiments/run_phase4b_evaluation.py:698 cleanup_harness_rows | 747:db.execute, 748:db.execute, 749:db.execute, 750:db.execute, 753:db.execute, 754:db.execute
backend/evaluation/experiments/run_phase4b_evaluation.py:776 main | 830:create_async_engine, 834:async_sessionmaker, 851:session_factory, 996:cleanup_harness_rows, 859:cleanup_harness_rows
backend/evaluation/experiments/run_structure_confirmation.py:699 run_once | 735:async_session, 736:(await db.execute(select(User).where(User.email == EVAL_EMAIL))).scalar_one_or_none, 779:base.ablation._delete_user_data, 780:db.execute, 740:base.ablation._delete_user_data, 741:db.execute, 737:db.execute
backend/evaluation/experiments/run_structure_element_measurement.py:275 load_persisted_elements | 299:(await db.execute(stmt)).fetchall, 299:db.execute
backend/evaluation/experiments/run_structure_element_measurement.py:1638 run_once | 1669:async_session, 1670:(await db.execute(select(User).where(User.email == EVAL_EMAIL))).scalar_one_or_none, 1729:ablation._delete_user_data, 1730:db.execute, 1674:ablation._delete_user_data, 1675:db.execute, 1671:db.execute
backend/evaluation/experiments/run_structure_rrf_calibration.py:954 run_once | 987:async_session, 988:(await db.execute(select(User).where(User.email == EVAL_EMAIL))).scalar_one_or_none, 1063:base.ablation._delete_user_data, 1064:db.execute, 992:base.ablation._delete_user_data, 993:db.execute, 989:db.execute
backend/evaluation/experiments/run_table_evidence_measurement.py:309 _ensure_schema | 313:engine.connect
backend/evaluation/experiments/run_table_evidence_measurement.py:479 teardown | 486:db.execute
backend/evaluation/experiments/run_table_evidence_measurement.py:643 run_once | 651:async_sessionmaker, 653:session_factory, 654:teardown, 659:session_factory, 682:teardown
backend/evaluation/experiments/run_table_evidence_measurement.py:1098 amain | 1113:create_async_engine
backend/scripts/cleanup_orphan_uploads.py:68 _referenced_keys | 70:async_session, 71:(await session.execute(select(Document.stored_path))).scalars().all, 74:(await session.execute(select(VerificationResult.stored_path))).scalars().all, 71:(await session.execute(select(Document.stored_path))).scalars, 74:(await session.execute(select(VerificationResult.stored_path))).scalars, 72:session.execute, 75:session.execute
backend/scripts/cleanup_orphan_uploads.py:131 run_sweep | 210:path.unlink, 223:path.rmdir
backend/scripts/cleanup_smoke.py:65 cleanup | 66:async_session, 67:(await session.execute(select(User).where(User.email == email))).scalar_one_or_none, 77:(await session.execute(select(Document).where(Document.user_id == user_id))).scalars().all, 136:shutil.rmtree, 140:async_session, 141:(await session.execute(select(User).where(User.email == email))).scalar_one_or_none, 144:(await session.execute(select(func.count()).select_from(Document).where(Document.user_id == user_id))).scalar_one, 151:(await session.execute(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.document_id.in_(doc_ids or [])))).scalar_one, 88:(await session.execute(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.document_id.in_(doc_ids)))).scalar_one, 113:delete_upload, 127:session.execute, 77:(await session.execute(select(Document).where(Document.user_id == user_id))).scalars, 122:session.execute, 68:session.execute, 142:session.execute, 145:session.execute, 152:session.execute, 89:session.execute, 78:session.execute
backend/scripts/create_test_user.py:38 create_user | 39:async_session, 41:session.execute
backend/scripts/db_check.py:16 main | 18:engine.connect, 19:conn.execute
backend/scripts/setup_db.py:30 main | 41:subprocess.run
backend/scripts/start_server.py:44 _port_in_use | 47:sock.connect_ex
backend/tests/fixtures/e2e_config.py:207 psql | 223:subprocess.run
backend/tests/fixtures/e2e_config.py:275 ensure_test_user | 305:subprocess.run
backend/tests/fixtures/e2e_config.py:322 purge_documents | 332:api_call, 340:api_call
backend/tests/fixtures/e2e_config.py:346 login | 351:api_call
backend/tests/fixtures/e2e_config.py:362 document_names | 367:api_call
backend/tests/fixtures/integration_db.py:273 postgres_available | 277:socket.create_connection
backend/tests/fixtures/integration_db.py:302 psql_value | 317:subprocess.run
backend/tests/fixtures/integration_db.py:407 alembic_head | 409:subprocess.run
backend/tests/fixtures/integration_db.py:429 migrate_to_head | 431:subprocess.run
backend/tests/fixtures/integration_db.py:519 provisioned_integration_database | 559:_create_database, 564:migrate_to_head, 573:_drop_database
backend/tests/fixtures/integration_db.py:585 isolated_database | 595:provisioned_integration_database
backend/storage/database.py:56 get_db | 57:async_session
backend/storage/file_store.py:53 delete_upload | 61:stored_path.unlink
backend/storage/file_store.py:68 cleanup_new_file | 76:file_path.unlink
backend/migrations/env.py:63 run_migrations_offline | 71:context.begin_transaction
backend/migrations/env.py:75 do_run_migrations | 77:context.begin_transaction
backend/migrations/env.py:81 run_async_migrations | 82:async_engine_from_config, 88:connectable.connect, 90:connectable.dispose, 89:connection.run_sync
backend/migrations/versions/000_create_base_tables.py:100 upgrade | 102:op.execute
```

### 12.5 Supplemental writer/scratch call inventory — SOURCE-VERIFIED

```text
backend/evaluation/experiments/run_dual_path_ablation.py:160 ingest_corpus | 187:tempfile.TemporaryDirectory, 206:db.add, 241:db.commit, 207:db.flush, 213:db.flush, 222:db.flush, 233:replace_document_graph, 228:replace_document_structure
backend/evaluation/experiments/run_dual_path_ablation.py:605 main | 707:db.add, 708:db.flush, 718:ingest_corpus, 813:_delete_user_data, 815:db.commit, 696:_delete_user_data, 698:db.commit, 719:ingested.values
backend/evaluation/experiments/run_dual_path_ablation.py:861 _delete_user_data | 890:db.flush
backend/evaluation/experiments/run_phase3d_evaluation.py:138 ingest_corpus | 150:tempfile.TemporaryDirectory, 181:db.add, 219:db.commit, 182:db.flush, 204:db.add
backend/evaluation/experiments/run_phase3d_evaluation.py:621 main | 712:db.commit, 727:db.add, 814:cleanup_harness_rows, 815:db.commit, 711:cleanup_harness_rows, 728:db.flush, 730:ingest_corpus
backend/evaluation/experiments/run_phase3d_upload_integration.py:188 main | 291:db.add, 292:db.commit, 406:db.add, 417:tempfile.TemporaryDirectory, 494:db.add, 628:cleanup_harness_rows, 629:db.commit, 306:tempfile.TemporaryDirectory, 407:db.commit, 495:db.commit, 545:db.commit
backend/evaluation/experiments/run_phase3d_upload_integration.py:304 upload | 306:tempfile.TemporaryDirectory
backend/evaluation/experiments/run_phase3e_integration.py:155 main | 238:db.add, 289:os.unlink, 417:os.unlink, 533:os.unlink, 239:db.commit, 256:tempfile.NamedTemporaryFile, 318:os.unlink, 386:os.unlink, 408:tempfile.NamedTemporaryFile, 421:client.delete, 449:db.add, 493:db.add, 522:tempfile.NamedTemporaryFile, 309:tempfile.NamedTemporaryFile, 377:tempfile.NamedTemporaryFile, 450:db.commit, 470:cleanup_harness_rows, 471:db.commit, 494:db.commit, 515:db.commit, 543:cleanup_harness_rows, 544:db.commit
backend/evaluation/experiments/run_phase3e_validation.py:155 main | 237:db.add, 356:os.unlink, 620:os.unlink, 767:os.unlink, 814:os.unlink, 238:db.commit, 267:os.unlink, 345:tempfile.NamedTemporaryFile, 558:db.add, 611:tempfile.NamedTemporaryFile, 637:client.delete, 706:db.add, 740:client.delete, 757:tempfile.NamedTemporaryFile, 805:tempfile.NamedTemporaryFile, 257:tempfile.NamedTemporaryFile, 559:db.commit, 587:db.commit, 707:db.commit, 749:cleanup_harness_rows, 750:db.commit, 850:cleanup_harness_rows, 851:db.commit
backend/evaluation/experiments/run_phase3f_evaluation.py:242 ingest_corpus | 253:tempfile.TemporaryDirectory, 279:db.add, 310:db.commit, 280:db.flush, 300:db.add
backend/evaluation/experiments/run_phase3f_evaluation.py:796 main | 880:db.commit, 890:db.add, 1064:cleanup_harness_rows, 1065:db.commit, 879:cleanup_harness_rows, 891:db.flush, 893:ingest_corpus
backend/evaluation/experiments/run_phase4b_evaluation.py:217 ingest_corpus | 228:tempfile.TemporaryDirectory, 254:db.add, 285:db.commit, 255:db.flush, 275:db.add
backend/evaluation/experiments/run_phase4b_evaluation.py:776 main | 860:db.commit, 870:db.add, 996:cleanup_harness_rows, 997:db.commit, 859:cleanup_harness_rows, 871:db.flush, 873:ingest_corpus
backend/evaluation/experiments/run_phase4c_diagnostics.py:272 main | 334:tempfile.TemporaryDirectory, 394:tempfile.TemporaryDirectory
backend/evaluation/experiments/run_structure_confirmation.py:699 run_once | 807:by_cat[meta[q].category].add, 751:db.add, 752:db.flush, 755:base.ingest_corpus, 779:base.ablation._delete_user_data, 781:db.commit, 740:base.ablation._delete_user_data, 742:db.commit, 765:ingested.values
backend/evaluation/experiments/run_structure_confirmation.py:900 main | 932:tempfile.mkdtemp
backend/evaluation/experiments/run_structure_element_measurement.py:170 ingest_corpus | 193:tempfile.TemporaryDirectory, 212:db.add, 270:db.commit, 213:db.flush, 218:db.flush, 227:db.flush, 260:replace_document_graph, 234:replace_document_structure
backend/evaluation/experiments/run_structure_element_measurement.py:319 derive_gold | 348:ingested.get, 343:ingested.items
backend/evaluation/experiments/run_structure_element_measurement.py:508 measure_question | 710:ingested.get(_doc_name(ingested, question), {}).get, 701:ingested.get(_doc_name(ingested, question), {}).get, 710:ingested.get, 701:ingested.get
backend/evaluation/experiments/run_structure_element_measurement.py:835 _doc_name | 836:ingested.items
backend/evaluation/experiments/run_structure_element_measurement.py:1638 run_once | 1685:db.add, 1686:db.flush, 1689:ingest_corpus, 1729:ablation._delete_user_data, 1731:db.commit, 1674:ablation._delete_user_data, 1676:db.commit, 1699:ingested.values
backend/evaluation/experiments/run_structure_element_measurement.py:1884 main | 1906:tempfile.mkdtemp
backend/evaluation/experiments/run_structure_rrf_calibration.py:954 run_once | 1003:db.add, 1004:db.flush, 1007:base.ingest_corpus, 1063:base.ablation._delete_user_data, 1065:db.commit, 992:base.ablation._delete_user_data, 994:db.commit, 1022:ingested.values
backend/evaluation/experiments/run_structure_rrf_calibration.py:1121 main | 1141:tempfile.mkdtemp
backend/evaluation/experiments/run_table_evidence_measurement.py:350 ingest_demo | 379:db.add, 400:db.add, 380:db.flush, 401:db.flush, 406:db.flush, 415:db.flush, 418:replace_document_structure, 419:replace_document_graph, 435:db.commit
backend/evaluation/experiments/run_table_evidence_measurement.py:479 teardown | 487:db.commit
backend/evaluation/experiments/run_table_evidence_measurement.py:643 run_once | 660:ingest_demo
backend/scripts/cleanup_orphan_uploads.py:131 run_sweep | 210:path.unlink, 223:path.rmdir
backend/scripts/cleanup_smoke.py:65 cleanup | 136:shutil.rmtree, 128:session.commit
backend/scripts/create_test_user.py:38 create_user | 54:session.add, 55:session.commit
backend/tests/fixtures/graph_data.py:15 create_document_with_chunks | 42:db.add, 43:db.flush, 59:db.add, 62:db.flush
backend/tests/fixtures/graph_data.py:79 create_test_user | 95:db.add, 96:db.flush
backend/storage/database.py:56 get_db | 60:session.commit
backend/storage/file_store.py:53 delete_upload | 61:stored_path.unlink
backend/storage/file_store.py:68 cleanup_new_file | 76:file_path.unlink
```

### 12.6 E2E/integration call inventory — SOURCE-VERIFIED

```text
backend/tests/e2e/browser/test_browser_flow.py:24 main | 47:api_call, 63:api_call, 71:api_call, 78:api_call, 85:api_call, 95:api_call, 105:api_call, 112:api_call
backend/tests/e2e/browser/test_browser_flow.py module/__main__ | 127:main
backend/tests/e2e/browser/test_document_flow.py:49 api_call | 60:api_call_raw
backend/tests/e2e/browser/test_document_flow.py:72 main | 95:api_call, 114:os.unlink, 126:e2e_config.psql, 134:e2e_config.psql, 140:e2e_config.psql, 149:e2e_config.psql, 169:api_call, 178:api_call, 186:api_call, 190:e2e_config.psql, 196:e2e_config.psql, 204:api_call, 207:api_call, 210:api_call, 230:os.unlink, 245:os.unlink, 161:e2e_config.psql, 252:api_call
backend/tests/e2e/browser/test_document_flow.py module/__main__ | 266:main
backend/tests/e2e/browser/test_embedding_flow.py:73 main | 96:api_call, 112:os.unlink, 130:os.unlink, 137:api_call, 146:psql, 150:psql, 156:api_call, 162:api_call, 170:api_call, 198:api_call, 214:api_call, 230:psql, 237:psql, 249:api_call, 254:api_call, 263:api_call, 271:api_call, 272:api_call
backend/tests/e2e/browser/test_embedding_flow.py module/__main__ | 287:main
backend/tests/e2e/browser/test_phase6_reliability.py:32 main | 57:subprocess.Popen, 82:api_call, 110:api_call, 116:api_call, 147:api_call, 160:api_call, 173:api_call, 176:api_call, 181:api_call, 40:shutil.rmtree, 183:os.unlink
backend/tests/e2e/browser/test_phase6_reliability.py module/__main__ | 205:main
backend/tests/e2e/browser/test_rag_flow.py:68 main | 104:api_call, 111:e2e_config.purge_documents, 125:os.unlink, 133:api_call, 142:api_call, 167:api_call, 180:api_call, 205:api_call, 228:api_call, 236:api_call, 244:api_call, 220:e2e_config.psql
backend/tests/e2e/browser/test_rag_flow.py module/__main__ | 259:main
backend/tests/e2e/browser/test_real_browser.py:589 test_real_browser_playwright_flow | 606:e2e_config.purge_documents, 611:e2e_config.purge_documents
backend/tests/integration/rag/test_real_e2e_validation.py:484 test_real_e2e_validation | 513:run_full_validation
backend/tests/integration/rag/test_real_e2e_validation.py module/__main__ | 534:run_full_validation, 536:provisioned_integration_database, 537:run_full_validation
backend/tests/integration/documents/test_document_mutation_id_validation.py:104 test_delete_malformed_document_id_returns_422 | 108:client.delete
backend/tests/integration/documents/test_document_mutation_id_validation.py:132 test_non_uuid_shaped_paths_still_return_clean_4xx | 138:client.delete
backend/tests/integration/documents/test_document_mutation_id_validation.py:154 test_malformed_id_validation_body_is_structural | 159:client.delete
backend/tests/integration/documents/test_document_mutation_id_validation.py:178 test_delete_valid_unknown_uuid_returns_404 | 182:client.delete
backend/tests/integration/documents/test_document_mutation_id_validation.py:202 test_delete_valid_document_still_succeeds | 208:client.delete
backend/tests/integration/documents/test_document_mutation_id_validation.py:278 test_delete_unauthenticated_rejected | 282:client.delete
backend/tests/integration/documents/test_document_mutation_id_validation.py:309 test_cross_user_delete_returns_404_and_does_not_delete | 316:client.delete
backend/tests/integration/documents/test_document_mutation_id_validation.py:345 test_cross_user_malformed_id_does_not_reveal_ownership | 350:client.delete
backend/tests/integration/documents/test_table_row_migration.py:56 _run_alembic | 59:subprocess.run
backend/tests/integration/documents/test_table_row_migration.py:68 _alembic | 69:_run_alembic
```

### 12.3 Path comparison — SOURCE-VERIFIED

```diff
--- initial expanded status
+++ final expanded status
@@ -471,6 +471,7 @@
 ?? backend/architecture/STEP1_6K_LIFECYCLE_AUTHORIZATION_HARDENING_2026-10-12.md
 ?? backend/architecture/STEP1_6L_FUNCTION_LEVEL_CLEANUP_AUTHORIZATION_2026-10-12.md
 ?? backend/architecture/STEP1_6M_READ_ONLY_POSTGRESQL_READINESS_REVIEW_2026-10-12.md
+?? backend/architecture/STEP1_6N_EVALUATION_SAFETY_REMEDIATION_ARCHITECTURE_2026-10-12.md
 ?? backend/architecture/phase4f_6/ARCHITECTURE_DECISION_RECORD.md
 ?? backend/architecture/phase4f_6/CURRENT_ARCHITECTURE.md
 ?? backend/architecture/phase4f_6/DOMAIN_MODEL.md
```

Validation: standard-library assertions read the final report, checked B01–B48, A1–A21, all required labels/sections, balanced Markdown fences, exact embedded evidence, baseline hashes and unchanged HEAD. Exit 0. This is document/preservation validation, not test execution or database verification.
