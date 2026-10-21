# Step 1.6Q — Normalized Callable Inventory and Evidence Reconciliation

Date: 2026-10-12  
Verdict: **PARTIAL — normalized records and reproducible scoped counts are documented; repository-wide completeness and independent review are not established.**  
PostgreSQL status: **NO-GO.** This report is static source inspection and documentation only.

## 1. Executive verdict

This report converts the prior grouped boundary map into **individual callable records** for the source-selected sensitive surface. Each record below has an ID, exact repository-relative path, qualified callable, line range, boundary/effects, caller/resource context, guard/order, direct invocation context, tests/evidence, containment proposal, owner, and evidence class. Source can show calls and lexical ordering, not that a branch ran, what server was reached, PostgreSQL privileges, or race-free filesystem behavior.

The count reconciliation is explicit: Step 1.6P’s 20 P-rows were **groups**, its claimed 106 individual boundaries cannot be regenerated from those grouped rows, and its reported AST scan of 109 callable definitions is reproducible with a narrow scan recipe but is not equivalent to normalized records or operation sites. The initial draft’s record count was inconsistent with the IDs subsequently appended. The report therefore treats the currently listed Q/X/M IDs as an enumerated **candidate record set**, with exact unique-record total unresolved until a corrected ID normalization pass; §5 records the scan-specific and historical counts separately. The original P-series grouping is preserved only as a cross-reference, never used as the record unit.

Coverage is bounded: source roots, patterns, exclusions, and a rerunnable standard-library AST recipe are provided. Dynamic dispatch, framework internals, excluded archive/venv trees, and all production DB routes are not certified exhaustive. The report therefore does **not** claim a complete inventory of every database/filesystem boundary in the repository.

No application module was imported; no test was run; no SQL, socket connection, database, migration, E2E, runner, provisioning, or cleanup operation was executed. Only this report was created by Step 1.6Q. All existing refusal behavior is unchanged. PostgreSQL remains **NO-GO**.

## 2. Reviewer participation and limitations

The requested COORDINATOR, DATABASE_AGENT, SECURITY_AGENT, EVALUATION_AGENT, TEST_AGENT, and VERIFIER roles are listed. The current tool runtime exposes no specialist dispatch mechanism. Coordinator inspection/reporting is not independent specialist review. All specialist reviews, including Verifier’s count challenge, are **OUTSTANDING**.

| Role | Actual participation |
|---|---|
| COORDINATOR | Scoped source inspection, static scan, report reconciliation. |
| DATABASE_AGENT | Not dispatched; database/SQL review outstanding. |
| SECURITY_AGENT | Not dispatched; bypass/filesystem review outstanding. |
| EVALUATION_AGENT | Not dispatched; runner/fixture review outstanding. |
| TEST_AGENT | Not dispatched; test mapping review outstanding. |
| VERIFIER | Not dispatched; independent inventory/count verification outstanding. |

Evidence labels: `SOURCE-VERIFIED` means the cited source contains the callable/call/order; it does not prove runtime behavior. `TEST-EVIDENCE-REPORTED` means a test file exists and its apparent assertion scope was inspected but tests were not run here. `HISTORICAL-TRANSCRIPT-ONLY` means an earlier report/transcript said a check ran; it is not a current pass. `UNVERIFIED` means environment/runtime/identity/race/property cannot be established from static source. `BLOCKED` means current code source refuses the relevant operation. Proposed tests and safeguards are not current evidence.

## 3. Repository baseline and preservation evidence

At the start of Step 1.6Q:

- HEAD: `6baaa2a0773df66e5fb26814afbe67647fb43435`.
- Full `git status --porcelain=v1 --untracked-files=all` was captured at `/tmp/step16q-status-before.txt` with **1,142 entries**; HEAD snapshot at `/tmp/step16q-head-before.txt`.
- Step 1.6P, 1.6O, and 1.6N reports existed.
- Step 1.6Q report path was absent from the initial status and did not exist before this write.
- The earlier Step 1.6P snapshot paths are present in this environment now, but they are not used to infer a Step 1.6Q baseline.

No environment secret file was opened or printed. No reset, stash, clean, revert, stage, commit, or deletion was performed. Existing large-scale modifications/deletions/untracked paths remain outside this task’s scope. Exact set comparison is recorded in §12 after the report is created.

## 4. Method, scope, and record schema

### 4.1 Source read and search method

Read the Step 1.6N, Step 1.6O and Step 1.6P reports, `AGENTS.md`, `CONTEXT.md`, `DOCUMIND_PROJECT_CONTEXT.md`, Coordinator and required specialist contracts. Source was located using code search and inspected using bounded file windows. Python AST parsing used only the standard library and read file text; it did not import project/application modules, execute module top level, invoke pytest collection, or contact external services.

Scoped source files/roots parsed or read for this inventory:

- `backend/evaluation/isolation.py`, `backend/evaluation/experiments/*.py`.
- `backend/tests/fixtures/*.py`.
- `backend/tests/integration/rag/test_real_e2e_validation.py` and specific O-series graph/document helpers under `backend/tests/integration/{documents,graph}/`.
- `backend/tests/e2e/browser/*.py`.
- `backend/scripts/{cleanup_path.py,cleanup_orphan_uploads.py,cleanup_smoke.py,create_test_user.py,db_check.py,setup_db.py,start_server.py}`.
- `backend/storage/{database.py,file_store.py}`, `backend/migrations/env.py`, `backend/migrations/versions/*.py`, `backend/main.py`.
- Production mutation/persistence boundary sources `backend/documents/routes.py`, `backend/documents/structure.py`, `backend/graph/service.py`, `backend/embeddings/routes.py`.
- Relevant tests named in the records and existing safety tests under `backend/tests/unit/evaluation/` and `backend/tests/unit/scripts/`.

Secrets and `.env` contents were not inspected. The scan excludes `backend/venv/**`, `backend/phases/**` (archived research; `backend/phases/phase4f_gpu/**` is forbidden/read-only), `backend/models/**`, `__pycache__`, dependency/vendor code, and generated/report data. Some branches and exact caller graphs are inferred from static call sites; they are labelled as such.

### 4.2 Reproducible counting recipe

The following logic reruns the narrow historical 109 candidate count. It reads only Python source under the specified roots, parses with `ast`, skips nested callable bodies when counting calls directly inside a callable, and counts each qualifying function definition once. It does not import project code. Run it from repository root using the project Python interpreter; it performs no network or database access:

```python
import ast
from pathlib import Path

roots = [
    'backend/evaluation/experiments', 'backend/tests/fixtures',
    'backend/tests/integration', 'backend/tests/e2e', 'backend/scripts',
    'backend/migrations', 'backend/storage',
]
effects = {
    'create_async_engine','create_engine','connect','execute','commit','rollback',
    'unlink','remove','rmtree','rmdir','replace_document_structure',
    'replace_document_graph','upgrade','downgrade','run_migrations','psql',
    'psql_value','postgres_available','migrate_to_head','delete','truncate','mkdir',
}
def called_name(call):
    f = call.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ''
def direct_effect_calls(fn):
    stack, out = list(fn.body), []
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(n, ast.Call) and called_name(n) in effects:
            out.append(n)
        stack.extend(ast.iter_child_nodes(n))
    return out
found, parsed = [], set()
for root in roots:
    for path in Path(root).rglob('*.py'):
        if {'venv', '__pycache__'} & set(path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        parsed.add(path)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and direct_effect_calls(node):
                found.append((path.as_posix(), node.name, node.lineno))
print('parsed files', len(parsed), 'callable definitions', len(found),
      'distinct paths', len({row[0] for row in found}))
```

Observed result on this tree: **83 parsed files, 109 qualifying callable definitions, 41 distinct paths**. The root/effect vocabulary is intentionally narrow; it does not count every indirect SQLAlchemy call, standard-library file effect, import-time statement, or framework callback.

The normalized inventory uses a second, broader *manual/source-selected* record set documented below. This set is not produced by the narrow count script, because it deliberately includes callable boundaries whose effects are indirect (e.g., delegates to generic SQL helper), module-level execution, declarative migration calls, selected O-series fixture writers, and explicit entry points. A reviewer can use the location and scan recipe to challenge each row; no script currently emits all the prose attributes in the report. Thus the inventory record count is reproducible by record IDs/tables, while the wider source population remains bounded and not exhaustive.

### 4.3 Record key

Every record uses the same fields: **ID; callable and exact path:line-range; category/effects; supplied resource/config; guard and order; direct call/entry path; tests/evidence; containment; owner; classification.** Guard `none identified` means source inspection found no guard at this callable; it does not assert exploitability. `Main-only` means a caller’s guard is not a helper-local boundary. For production routes, JWT ownership is a distinct application control, not evaluation database authorization.

## 5. Counts and reconciliation

| Measure | Reconciled value | Counting rule / confidence |
|---|---:|---|
| Step 1.6P grouped rows | 20 | P01–P20 grouped categories; not individual callables. |
| Step 1.6P reported individual boundaries | 106 | Not derivable from P’s grouped prose/table; now treated as **unverified historical claim**, not current count. |
| Step 1.6P historical AST candidate scan | 109 | Reproduced by §4.2: one qualifying function definition with a direct call to the enumerated effect-name set; 83 files / 41 paths. This is neither a unique execution resource nor effects/site count. |
| Normalized candidate IDs listed | **143 IDs** | Q001–Q120 (120 IDs, Q083 reserved), X001–X005 (5), M001–M018 (18). Q083 and M017–M018 are explicitly reserved/invalid; 140 IDs remain as candidates, not a verified unique callable total. Q104 and some operational rows describe module-level execution or objects rather than function definitions. |
| Unique callable definitions represented by candidate IDs | **UNRESOLVED** | Several rows are module/script execution boundaries rather than Python callables; same-file shorthand/call paths and entry labels have not been deduplicated against AST-qualified definitions. |
| Normalized boundary records | **UNRESOLVED** | Candidate IDs include both function callables and module/entry execution boundaries; no canonical one-record-per-boundary manifest was mechanically reconciled. |
| Executable callable entry points | **UNRESOLVED** (49 ENTRY labels currently present) | Labels include helper functions, pytest tests, module statements, and repeated logical entry paths. Not a unique entry-point count. |
| Direct matched call sites in the §4.2 narrow AST vocabulary | **365 calls / 325 unique file-line sites** | Re-run against the same roots/effect set while collecting every direct call in each qualifying function. The 40-call difference is same-line multiple-call overlap; nested callable bodies are excluded. This is not all DB/filesystem operations. |
| Duplicate/overlapping records | **2 reserved IDs excluded; other callable overlap unresolved** | M017/M018 are invalid revision placeholders; Q083 is reserved. Some ENTRY labels denote a callable also listed as a helper or a module-level operation; exact source-span duplicate count unresolved. |
| Direct matched call sites in §4.2 scan | **365 calls / 325 unique file-line sites** | Observed with the same roots and exact effect vocabulary; 40 same-line multiple-call overlaps. Not all DB/filesystem operations. |
| Unresolved candidates | **At least 6 classes** | Production routes/helpers outside selected paths; archived `backend/phases/**`; unrecognized aliases/reflection; import-time effects beyond inspected roots; symlink/junction/platform races; dynamic subprocess/API target calls. No defensible exact count. |

The discrepancy is reconciled without inventing equivalence: `20` was a grouped-report row count; `106` is an unreproducible individual-boundary claim and is withdrawn; `109` is a reproducible scan-specific callable-definition count (83 files / 41 paths) under §4.2. The written tables contain 143 IDs; subtracting the three explicitly reserved/invalid identifiers yields 140 *candidate IDs*, not a unique callable count. The unique callable-record total and unique executable-entry count remain **UNRESOLVED** because some rows are module-level execution or engine objects, callable entries and helper records overlap, and O-2/O-3 call sites lack one record per named test. Separately, the narrow AST scan finds 365 direct matched calls at 325 unique file-line sites. These measures are not interchangeable and establish no PostgreSQL safety.

## 6. Normalized callable inventory

The record list is split by callable family to remain readable. Exact start–end lines were confirmed by the scoped AST/source scan or adjacent source reads. Effects shown are direct matched operations or explicitly described delegated/import-time effects. All test references below were inspected as source only; none was executed here.

### 6.1 Central target/lifecycle helpers and fixture target helpers

| ID | Callable; path:lines | Category / effects / supplied resources | Guard, order, callers | Tests and scope | Requirement; owner; evidence |
|---|---|---|---|---|---|
| Q001 | `application_database_url`; `backend/evaluation/isolation.py:125-143` | Config; reads env-file/settings, returns DSN. | No authorization; called by resolver/guards. | `test_evaluation_isolation.py`: pure precedence/parse behavior. | Use one immutable authority target; reject conflicts pre-import. EVALUATION_AGENT + DATABASE_AGENT; SOURCE-VERIFIED, actual URL UNVERIFIED. |
| Q002 | `database_identity`; `backend/evaluation/isolation.py:146-158` | Pure DSN parse. | No connection/authorization. | `test_evaluation_isolation.py`: string parsing only. | Treat identity as descriptive, never connection proof. EVALUATION_AGENT; SOURCE-VERIFIED. |
| Q003 | `evaluation_database_url`; `backend/evaluation/isolation.py:187-218` | Resolves CLI/env/application URL. | Preflight resolver, not authority. | `test_evaluation_isolation.py`: pure precedence only. | Reject competing config and bind resolver snapshot. EVALUATION_AGENT; SOURCE-VERIFIED. |
| Q004 | `assert_safe_evaluation_target`; `backend/evaluation/isolation.py:249-319` | Name/URL policy gate. | Executes before caller engine in instrumented runners; checks names/URL only. | isolation/runner order tests: refusal/order, no actual endpoint. | Keep fail-closed; actual connection attestation required before any future use. EVALUATION_AGENT; SOURCE-VERIFIED, server identity UNVERIFIED. |
| Q005 | `record_created_database`; `backend/evaluation/isolation.py:365-373` | Lifecycle proof issuance refusal. | Always raises before side effect. | `test_lifecycle_authorization.py`, disposal contract: refusal only. | Preserve refusal absent external authority. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q006 | `_proof_is_live`; `backend/evaluation/isolation.py:375-376` | Lifecycle proof check. | Always false. | lifecycle tests inspect fail-closed behavior. | No positive proof path. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q007 | `assert_disposal_authorized`; `backend/evaluation/isolation.py:377-413` | Destructive DDL authorization. | Validates config, then always refuses before DDL. | lifecycle/disposal tests: refusal only. | Preserve; external operation/target authorization required. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q008 | `assert_creation_authorized`; `backend/evaluation/isolation.py:415-441` | Database create authorization. | Always refuses after pure URL checks. | lifecycle tests: refusal only. | Preserve; no existence check can grant authority. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q009 | `assert_row_cleanup_authorized`; `backend/evaluation/isolation.py:443-454` | Row deletion guard. | Delegates to Q007; refuses before row effect. | lifecycle/disposal tests. | Preserve; later operation lease bound to live connection. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q010 | `assert_cleanup_execution_authorized`; `backend/evaluation/isolation.py:456-474` | Engine/session destructive boundary. | Immediately refuses without inspecting resource. | `test_function_cleanup_authorization.py`: first-expression/source contract. | Preserve unconditional refusal; never trust URL/proof object. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q011 | `release_database_proof`; `backend/evaluation/isolation.py:477-484` | Lifecycle release refusal. | Always raises. | lifecycle tests: refusal only. | Preserve until authority/recovery design. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q012 | `assert_engine_bound_to_proof`; `backend/evaluation/isolation.py:487-503` | Engine config comparison + disposal gate. | URL compare precedes refusal; does not connect. | disposal contract: config comparison/refusal only. | Engine URL is not server identity. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q013 | `assert_engine_matches_target`; `backend/evaluation/isolation.py:506-522` | Engine URL comparison. | No actual connection. | isolation guard tests compare parsed values. | Require actual authenticated server identity later; EVALUATION_AGENT + DATABASE_AGENT; SOURCE-VERIFIED. |
| Q014 ENTRY | `integration_database_url`; `backend/tests/fixtures/integration_db.py:130-138` | Test target derivation; caller environment override. | Used by target gate; no connection. | lifecycle tests inspect resolver. | Immutable manifest; reject conflicting target. TEST_AGENT + DATABASE_AGENT; SOURCE-VERIFIED. |
| Q015 | `assert_isolated_target`; `integration_db.py:159-198` | Fixture target validation. | Pure URL guard before caller fixture effects; textual same-host restriction. | lifecycle target-order tests: source/patched behavior. | Bind target and maintenance endpoint from one authority; TEST_AGENT + DATABASE_AGENT; SOURCE-VERIFIED. |
| Q016 | `assert_disposal_authorized`; `integration_db.py:210-220` | Drop gate delegation. | Delegates Q007 and refuses. | lifecycle/disposal tests. | Preserve refusal. TEST_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q017 ENTRY | `assert_authorized_destructive_target`; `integration_db.py:243-253` | Standalone lifecycle preflight. | Calls Q015 then Q016; refuses before external call. | lifecycle source-order tests. | Keep denial. TEST_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q018 | `postgres_available`; `integration_db.py:273-280` | Socket connect to configured host/port. | No lifecycle guard locally; direct call opens a socket. Normal fixture calls after create gate, but direct helper bypasses it. | Tests patch socket in lifecycle checks; no real reachability claim here. | Require separate read/connect authorization and exact target; TEST_AGENT + DATABASE_AGENT; SOURCE-VERIFIED, runtime UNVERIFIED. |
| Q019 ENTRY | `require_postgres`; `integration_db.py:283-298` | Reachability check/pytest skip. | Calls Q018; local no auth. | lifecycle tests inspect skip/probe order. | Do not call during prohibited task; future target-bound probe authorization. TEST_AGENT; SOURCE-VERIFIED. |

### 6.2 PSQL, migration, provisioning and E2E configuration helpers

| ID | Callable; path:lines | Category / effects / supplied resources | Guard, order, callers | Tests and scope | Requirement; owner; evidence |
|---|---|---|---|---|---|
| Q020 | `psql_value(dsn, sql)`; `backend/tests/fixtures/integration_db.py:302-337` | Arbitrary SQL subprocess; caller DSN/SQL, but host/user/pass from `e2e_config`. | No helper-local auth; callers Q021/Q022/Q023/Q026. Direct call bypasses fixture gate. | Lifecycle tests patch caller paths; no direct no-call proof identified. | Replace generic SQL with typed statements + direct-operation auth and minimal env. TEST_AGENT + DATABASE_AGENT; SOURCE-VERIFIED, privileges UNVERIFIED. |
| Q021 | `database_exists`; `integration_db.py:340-347` | Catalog SELECT through Q020; interpolates name. | No local guard; direct psql effect delegated. | No direct-call refusal test found. | Fixed parameterized catalog query; operation-specific inspection capability. DATABASE_AGENT + TEST_AGENT; SOURCE-VERIFIED. |
| Q022 | `_drop_database`; `integration_db.py:350-368` | DROP DATABASE WITH FORCE through Q020; DSN/proof accepted. | Q016 gate is before SQL and currently refuses. Direct invocation remains refused now; retained SQL path must remain unreachable absent authority. | disposal/lifecycle tests patch SQL helper, no real DB. | Keep refusal; future drop must bind target OID/lease and maintenance endpoint. DATABASE_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q023 | `_create_database`; `integration_db.py:371-386` | CREATE DATABASE through Q020. | Q008 create refusal before psql. | lifecycle tests check order. | Keep refusal. DATABASE_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q024 | `_alembic_env`; `integration_db.py:390-404` | Builds caller DSN child environment. | No local validation beyond assignment. | No specific target-conflict test identified. | Immutable target; reject inherited overrides; DATABASE_AGENT. SOURCE-VERIFIED. |
| Q025 ENTRY | `alembic_head`; `integration_db.py:407-426` | Subprocess runs `alembic heads`; no DB expected from CLI heads operation. | No local authorization; independently launchable subprocess. | fixture tests source only; no command run here. | Treat command invocation as process boundary; fixed cwd/env and no inherited DB side effects. DATABASE_AGENT + TEST_AGENT; SOURCE-VERIFIED. |
| Q026 | `migrate_to_head(dsn)`; `integration_db.py:429-444` | Alembic upgrade subprocess, caller DSN. | No helper-local authorization; provisioning fixture is refused before normal call. Direct call bypasses fixture refusal. | migration tests concern SQLite migration test path; no direct gate test. | Must refuse before subprocess unless separately authorized target/migration lease. DATABASE_AGENT; SOURCE-VERIFIED, execution BLOCKED by policy only in usual caller. |
| Q027 | `inspect_schema(dsn)`; `integration_db.py:447-470` | Fixed catalog SQL via Q020. | No local gate; can be called directly. | No PG query executed. | Explicit read-only inspection scope + exact live identity; DATABASE_AGENT. SOURCE-VERIFIED, runtime UNVERIFIED. |
| Q028 | `verify_schema(dsn, expected_revision)`; `integration_db.py:473-493` | Delegates to Q027. | No local guard, calls queries. | No real schema test. | Same read capability requirement. DATABASE_AGENT; SOURCE-VERIFIED. |
| Q029 ENTRY | `provisioned_integration_database`; `integration_db.py:519-574` | Fixture context, socket/psql/create/migrate/drop. | Q015 then Q008 refusal before socket. Later retained operations are blocked under present source. | lifecycle tests assert first gate; not PG identity. | Keep blocked until operator/authority design. DATABASE_AGENT + TEST_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q030 ENTRY | `isolated_database` fixture; `integration_db.py:589-596` | Pytest fixture, calls Q015/Q008 then Q019. | Refuses before reachability check. | lifecycle authorization tests: source order. | Preserve denial. TEST_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q031 | `database_url`; `backend/tests/fixtures/e2e_config.py:135-153` | Resolver precedence env → backend .env → ambient; no connection. | No conflict rejection, caller controls env. | No E2E target-conflict test identified. | Unify with authority-owned immutable target; TEST_AGENT + DATABASE_AGENT; SOURCE-VERIFIED. |
| Q032 | `postgres`; `e2e_config.py:166-177` | Parses host/port/DB/user/password; no connection. | Uses Q031; target may differ from runner. | Unit checks absent in scoped set. | Remove mixed-source identity; TEST_AGENT + DATABASE_AGENT; SOURCE-VERIFIED. |
| Q033 ENTRY | `psql_binary`; `e2e_config.py:180-202` | Resolves executable path. | No SQL, but controls child executable; env override caller supplied. | No targeted path validation test mapped. | Pin executable/trust policy; TEST_AGENT; SOURCE-VERIFIED. |
| Q034 | `psql(sql)`; `e2e_config.py:207-242` | Arbitrary SQL subprocess, caller SQL; resolver-derived DB. | No local lifecycle auth; called by browser harnesses; direct call bypasses main-level guards. | Browser scripts are source, not executed. | Remove raw SQL API or typed/no-authority refusal; TEST_AGENT + DATABASE_AGENT; SOURCE-VERIFIED, runtime privileges UNVERIFIED. |
| Q035 | `generated_uploads_dir`; `e2e_config.py:249-257` | Creates test scratch directory. | No local root capability; creates directory. | No root-containment safety test located. | Confine to approved test root and reject symlinked parents; TEST_AGENT + SECURITY_AGENT; SOURCE-VERIFIED. |
| Q036 ENTRY | `ensure_test_user`; `e2e_config.py:275-319` | Child process user creation; caller email/password/name and resolved DSN. | No lifecycle auth; subprocess runs script directly. | No direct refusal test. | Require isolated target/service identity before child launch; never expose credentials in logs. TEST_AGENT + DATABASE_AGENT; SOURCE-VERIFIED. |
| Q037 ENTRY | `purge_documents`; `e2e_config.py:322-344` | API DELETEs; caller base/token/name. | No target allowlist; JWT scopes user ownership but not database/server. | E2E/API tests cover application ownership, not evaluation target. | Require run-bound allowlisted endpoint and delete authority. TEST_AGENT + BACKEND_AGENT; SOURCE-VERIFIED, endpoint UNVERIFIED. |
| Q038 | `login`; `e2e_config.py:346-361` | HTTP POST; caller credentials/base. | No target allowlist. | Auth tests cover endpoint contract, not target binding. | Explicit endpoint allowlist; TEST_AGENT; SOURCE-VERIFIED. |
| Q039 | `document_names`; `e2e_config.py:362-374` | HTTP GET; caller base/token. | No target allowlist. | E2E assertions only. | Endpoint binding. TEST_AGENT; SOURCE-VERIFIED. |
| Q040 | `api_call`; `backend/tests/fixtures/integration_http.py:21-38` | HTTP caller base/path/token/method. | No target allowlist; calls arbitrary base. | E2E integration tests use configured test server; not run. | Require approved origin and route/method allowlist. TEST_AGENT; SOURCE-VERIFIED. |
| Q041 ENTRY | `multipart_upload`; `integration_http.py:41-64` | HTTP upload; caller URL/path/token; reads file. | No target/path provenance check. | E2E fixture scope only. | Bind API host and approved test-file root. TEST_AGENT; SOURCE-VERIFIED. |
| Q042 | `create_document_with_chunks`; `backend/tests/fixtures/graph_data.py:15-63` | Supplied session adds/flushes document/chunks. | No session identity guard. | Graph tests assert fixture data behavior. | Test-only session marker/no-I/O direct misuse check; TEST_AGENT; SOURCE-VERIFIED, actual DB UNVERIFIED. |
| Q043 | `create_test_user`; `graph_data.py:79-97` | Supplied session adds/flushes user. | No local guard. | Graph tests use fixture session. | Same fixture provenance control; TEST_AGENT. SOURCE-VERIFIED. |

### 6.3 Evaluation runner, ingestion, cleanup, and artifact callables

| ID | Callable; path:lines | Category / effects / supplied resources | Guard, order, callers | Tests and scope | Requirement; owner; evidence |
|---|---|---|---|---|---|
| Q044 ENTRY | `main`; `run_dual_path_ablation.py:605-858` | Runner DB engine/session, SQL, DML and commits; artifact/file output. | Central evaluation refusal before normal engine path; direct callable still enters same guard. | legacy runner tests inspect order, SQLite cleanup tests not PG. | Preserve fail-closed before all DB I/O; EVALUATION_AGENT. SOURCE-VERIFIED/BLOCKED for intended run. |
| Q045 | `ingest_corpus`; `run_dual_path_ablation.py:160-243` | Caller-supplied async session, add/flush, structure/graph helpers, commit; scratch file. | No helper-local target authorization. Called by Q044 and structure runners. Direct session call bypasses main. | cleanup scope tests don’t prove ingestion authorization. | Validate session capability before touching session/files; EVALUATION_AGENT + TEST_AGENT. SOURCE-VERIFIED. |
| Q046 | `_delete_user_data`; same file `:861-890` | Caller-supplied session; row deletes/flush. | Helper-local Q010 refusal occurs before SQL in current code. | cleanup authorization tests source-check refusal. | Keep direct denial. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q047 ENTRY | `main`; `run_phase3d_evaluation.py:621-820` | Creates engine/session; DML/commit and report write. | Target guard in main before engine. | `test_phase3_runner_target_order.py`, cleanup-scope tests source/order/SQLite only. | Preserve refusal and cover all session helper calls. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q048 | `ingest_corpus`; same file `:138-222` | Supplied session, insert/flush/commit, file ingestion. | No local authorization. | cleanup scope does not test it. | Session capability at helper boundary. EVALUATION_AGENT + TEST_AGENT; SOURCE-VERIFIED. |
| Q049 | `owned_user_ids`; same file `:539-546` | Caller session query. | Not destructive, but no target identity. | cleanup-scope tests. | Bind read session if used in authorized eval. EVALUATION_AGENT; SOURCE-VERIFIED. |
| Q050 | `cleanup_harness_rows`; same file `:549-603` | Caller session SQL/delete. | Q010 refuses before session access. | `test_function_cleanup_authorization.py`, SQLite row-scope tests. | Preserve refusal; do not treat SQLite row scope as PG authority. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q051 ENTRY | `main`; `run_phase3d_upload_integration.py:188-703` | Creates engine/session; API/upload/DB writes, commits and deletes. | Main refusal before engine in current source; nested requests distinct effects. | legacy/order and cleanup tests source/SQLite. | Separate DB, API, filesystem operation permissions; EVALUATION_AGENT. SOURCE-VERIFIED/BLOCKED. |
| Q052 | `cleanup_harness_rows`; same file `:118-163` | Supplied session deletes. | Q010 refusal before DB call. | function cleanup authorization. | Preserve direct denial. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q053 ENTRY | `upload`; same file `:304-314` | Nested HTTP POST with path/session context. | Called from Q051; no independent evaluation target auth. | No direct-helper target test. | Bind path, API endpoint, and run operation; EVALUATION_AGENT + TEST_AGENT. SOURCE-VERIFIED. |
| Q054 ENTRY | `main`; `run_phase3e_integration.py:155-555` | Engine/session, API writes/deletes, file unlinks, commits. | Main target refusal before normal DB engine. | `test_phase3e_integration_cleanup_scope.py`, function auth: source/SQLite only. | Keep refusal; operation-specific file/API/DB gate. EVALUATION_AGENT. SOURCE-VERIFIED/BLOCKED. |
| Q055 | `owned_user_ids`; same file `:66-80` | Supplied session query. | No separate target proof. | cleanup-scope tests. | Bound read resource. EVALUATION_AGENT; SOURCE-VERIFIED. |
| Q056 | `cleanup_harness_rows`; same file `:83-137` | Supplied session SQL deletes. | Q010 refusal before SQL. | function auth + SQLite scope. | Preserve direct denial. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q057 ENTRY | `main`; `run_phase3e_validation.py:155-862` | Engine/session, inline SQL/DML, API deletes, temp-file unlink. | Main refusal before normal engine; in-main inline effects protected by lexical guard, not reusable as helper authorization. | validation cleanup tests source/SQLite. | Preserve; split each API/SQL/file effect into local boundary. EVALUATION_AGENT + TEST_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q058 | `owned_user_ids`; same file `:65-79` | Supplied session query. | No connection identity. | cleanup scope. | Bind read connection. EVALUATION_AGENT; SOURCE-VERIFIED. |
| Q059 | `cleanup_harness_rows`; same file `:82-137` | Supplied session delete SQL. | Q010 before effects. | direct refusal/source and SQLite row scope. | Preserve denial. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q060 | `_get_chunk_ids_for_doc`; same file `:865-872` | Supplied session query. | No local session authorization. | no focused target test. | Bound session capability; EVALUATION_AGENT + TEST_AGENT; SOURCE-VERIFIED. |
| Q061 ENTRY | `main`; `run_phase3f_evaluation.py:796-1071` | Engine/session, commits/cleanup/report file. | Main refusal before engine; helper independently blocked. | cleanup-scope source/SQLite tests. | Preserve denial; EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q062 | `ingest_corpus`; same file `:242-313` | Supplied session adds/flush/commit, saves files. | No helper-local target guard. | no ingestion auth test. | Session + file capability required before effects. EVALUATION_AGENT + TEST_AGENT; SOURCE-VERIFIED. |
| Q063 | `owned_user_ids`; same file `:708-715` | Supplied session query. | No target binding. | cleanup tests. | Bound read session. EVALUATION_AGENT; SOURCE-VERIFIED. |
| Q064 | `cleanup_harness_rows`; same file `:718-774` | SQL row deletes. | Q010 unconditional refusal. | cleanup authorization + SQLite scope. | Preserve. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q065 ENTRY | `main`; `run_phase4b_evaluation.py:776-1003` | Engine/session, write/cleanup/report. | Main refusal pre-engine. | phase4b scope/legacy runner source/SQLite. | Preserve refusal. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q066 | `ingest_corpus`; same file `:217-288` | Supplied session and scratch file, commit. | No local target gate. | No positive ingestion guard test. | Session capability before touch. EVALUATION_AGENT + TEST_AGENT; SOURCE-VERIFIED. |
| Q067 | `owned_user_ids`; same file `:688-695` | Supplied session query. | No target proof. | cleanup tests. | Bound read session. EVALUATION_AGENT; SOURCE-VERIFIED. |
| Q068 | `cleanup_harness_rows`; same file `:698-754` | SQL delete. | Q010 refusal first. | cleanup tests. | Preserve. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q069 ENTRY | `main`; `run_structure_confirmation.py:900-985` | Delegates to run_once and writes artifacts/directories. | Main target guard; run_once independently refuses DB. | `test_structure_runner_guard_order.py`, artifact tests; source only. | Keep refusal; protect filesystem artifact root separately. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED DB. |
| Q070 | `run_once`; same file `:699-874` | Session/SQL/delete/commit and output file. | Q010 at function start, before session access. | function cleanup auth tests. | Preserve direct helper refusal. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q071 ENTRY | `main`; `run_structure_element_measurement.py:1884-1999` | Artifact writes/mkdir; calls run_once. | DB refusal inherited only through run_once; no general output-root capability. | structure runner order and artifact tests. | Separate immutable artifact root, exclusive create; EVALUATION_AGENT. SOURCE-VERIFIED. |
| Q072 | `ingest_corpus`; same file `:170-272` | Session adds, flushes, calls graph/structure persistence, commit/files. | No local target guard; direct supplied session accepted. | no ingestion auth test. | Validate session and file capability first. EVALUATION_AGENT + TEST_AGENT; SOURCE-VERIFIED. |
| Q073 | `run_once`; same file `:1638-1758` | Async session/SQL/delete/commit/dispose. | Q010 immediate refusal before session usage. | function cleanup authorization/runner guard order. | Preserve. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q074 ENTRY | `main`; `run_structure_rrf_calibration.py:1121-1202` | Artifact writes/mkdir, calls run_once. | DB helper refusal; artifact-root authorization absent. | structure guard and artifact tests. | Bind output root. EVALUATION_AGENT; SOURCE-VERIFIED. |
| Q075 | `run_once`; same file `:954-1095` | Session/SQL/delete/commit. | Q010 immediate refusal. | direct helper refusal tests. | Preserve. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q076 | `_ensure_schema`; `run_table_evidence_measurement.py:309-331` | Engine connect and fixed schema query. | Function-local evaluation target check not shown at connection boundary; caller `_resolve_database_url` / amain path. Direct helper can connect if called. | `test_runner_pre_engine_init.py` targets resolver/order, not this direct call. | Guard before `engine.connect` against actual target. EVALUATION_AGENT + DATABASE_AGENT; SOURCE-VERIFIED. |
| Q077 | `ingest_demo`; same file `:350-451` | Caller `AsyncSession`; write/flush/replace graph/structure/commit. | No local safety guard. Called from run_once, but callable can be invoked directly. | function cleanup tests cover teardown/run_once, not ingestion. | Validate supplied session capability before any attribute access. EVALUATION_AGENT + TEST_AGENT; SOURCE-VERIFIED. |
| Q078 | `teardown`; same file `:479-487` | Caller session deletes and commits. | Q010 immediate refusal. | function cleanup auth tests. | Preserve refusal. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q079 ENTRY | `run_once`; same file `:643-691` | Creates sessionmaker/calls teardown+ingest. | Q010 refusal before session creation in current source. | function auth/runner order. | Preserve; only authority-bound engine later. EVALUATION_AGENT; SOURCE-VERIFIED/BLOCKED. |
| Q080 ENTRY | `amain`; same file `:1098-1296` | Resolves URL, imports storage, creates engine, run loop, output directories. | Resolver/config mutation and engine construction precede some refusal according to Step 1.6O; engine creation is not itself proof of network connect. | runner-pre-engine tests inspect source resolver; no runner executed. | Guard config before imports, and operation boundary before connection; EVALUATION_AGENT + DATABASE_AGENT; SOURCE-VERIFIED, connection UNVERIFIED. |
| Q081 ENTRY | `main`; same file `:1299-1302` | `asyncio.run(amain())`. | CLI call path; delegates to Q080. | no invocation. | Keep blocked; EVALUATION_AGENT; SOURCE-VERIFIED. |
| Q082 ENTRY | `main`; `run_phase4c_diagnostics.py:272-590` | Report/file writes only in selected scan; no DB effects matched. | No DB authorization relevant; output path may overwrite. | no DB test required; artifact tests apply by analogy only. | Bound output path/atomic no-overwrite; EVALUATION_AGENT; SOURCE-VERIFIED, file replacement semantics partly inferred. |

### 6.4 O-series direct test helpers and E2E/browser callables

| ID | Callable; path:lines | Category / effects / supplied resources | Guard, order, callers | Tests and scope | Requirement; owner; evidence |
|---|---|---|---|---|---|
| X001 | `_persist`; `backend/tests/integration/documents/test_table_row_persistence.py:84-85` | Caller `db_session`; direct `replace_document_structure`. | Fixture/session context only, no helper target auth. | Row persistence tests assert contents/relations under configured fixture. | Explicit fixture provenance, no “test” name as auth. TEST_AGENT; SOURCE-VERIFIED, runtime DB UNVERIFIED. |
| X002 | `_seed`; `backend/tests/integration/graph/test_table_evidence_api.py:57-75` | Caller session, structure replacement/commit. | Test helper; direct callable. | table evidence API tests establish test data behavior. | Test fixture session proof/no PG claim. TEST_AGENT; SOURCE-VERIFIED. |
| X003 | `_seed_document`; `backend/tests/integration/graph/test_table_evidence_bands.py:71-96` | Caller session, structure replacement/flush. | Test helper; direct callable. | band tests exercise retrieval semantics only. | Same as X002. TEST_AGENT; SOURCE-VERIFIED. |
| X004 | `_foreign_document`; `backend/tests/integration/graph/test_graph_security.py:46-61` | Caller session, graph replacement/commit. | Auth test seeding, no target proof. | graph security assertions concern ownership, not DB identity. | Test fixture provenance/no-I/O guard. TEST_AGENT; SOURCE-VERIFIED. |
| X005 | `persist_fixture`; `backend/tests/integration/graph/test_structure_reachability.py:85-113` | Caller `db`, temp file unlink, structure write/query. | Test-only helper; path/session authority comes from fixture. | reachability assertions establish data path under fixture. | Keep temp path under pytest tmp root; independently validate path/session. TEST_AGENT + SECURITY_AGENT; SOURCE-VERIFIED. |
| Q083 | Reserved ID; not a callable record. | — | — | — | Explicit gap; excluded from valid callable count. |

The next table continues Q numbering for readability only. It does not repair the unresolved count or imply Q001–Q120 are 120 distinct valid callable records. Many ENTRY labels reflect source entry paths that share a callable with another row or describe a module-level statement rather than a function.

| ID | Callable; path:lines | Category / effects / supplied resources | Guard, order, callers | Tests and scope | Requirement; owner; evidence |
|---|---|---|---|---|---|
| Q084 ENTRY | `main`; `backend/tests/e2e/browser/test_document_flow.py:72-262` | E2E API/raw SQL through e2e_config, unlinks temp files. | Standalone `__main__`; no single target authorization. | Live-server script; not run. | Bind API and DB target; TEST_AGENT + SECURITY_AGENT; SOURCE-VERIFIED. |
| Q085 ENTRY | `main`; `test_embedding_flow.py:73-283` | Raw psql and temp unlink. | Standalone main, no DB lifecycle guard. | Live-server script; not run. | Same, TEST_AGENT; SOURCE-VERIFIED. |
| Q086 ENTRY | `main`; `test_phase6_reliability.py:32-201` | `rmtree` pycache, starts process, unlink. | `__main__`; no independent scratch-root capability. | Live-server script; not run. | Explicit scratch root and server allocation; TEST_AGENT + SECURITY_AGENT; SOURCE-VERIFIED. |
| Q087 ENTRY | `main`; `test_rag_flow.py:68-255` | Raw psql, API and file unlink. | Standalone main; target via resolver. | Live-server script; not run. | Same as Q084. TEST_AGENT; SOURCE-VERIFIED. |
| Q088 ENTRY | `main`; `test_browser_flow.py:24-123` | API/E2E call chain. | Standalone path; configured base. | Live-server script; not run. | Allowlist endpoint and run capability. TEST_AGENT; SOURCE-VERIFIED. |
| Q089 ENTRY | `test_real_browser_playwright_flow`; `test_real_browser.py:589-612` | Browser-driven app calls; indirect server DB/filesystem effects. | Pytest test entry, no evaluation DB authority. | Browser E2E source only. | Bind target/server allocation before browser startup. TEST_AGENT; source call path, indirect effects inferred. |
| Q090 ENTRY | `run_full_validation`; `backend/tests/integration/rag/test_real_e2e_validation.py:84-471` | Caller database URL/proof; engine/session, SQL, DML/commit. | Local cleanup refusal before SQLAlchemy import/engine according Step 1.6O source review; refusal persists. | `test_lifecycle_authorization.py` source-order; prior PG transcript is historical only. | Preserve refusal. TEST_AGENT; SOURCE-VERIFIED/BLOCKED; actual DB UNVERIFIED. |
| Q091 ENTRY | `test_real_e2e_validation`; same file `:484-523` | Pytest path to Q090; config/env mutation occurs at module scope outside callable. | Calls guarded Q090; fixture gate also blocks. | lifecycle test source-order only. | Keep module configuration from being able to redirect other harnesses; TEST_AGENT; SOURCE-VERIFIED. |

### 6.5 Operational scripts, migrations, application startup, and file storage

| ID | Callable; path:lines | Category / effects / supplied resources | Guard, order, callers | Tests and scope | Requirement; owner; evidence |
|---|---|---|---|---|---|
| Q092 ENTRY | `cleanup`; `backend/scripts/cleanup_smoke.py:65-169` | Queries, deletes documents/files, commits, `rmtree`; caller email/assume_yes. | Script-level prompt/flag is not authorization; direct callable path. | no focused cleanup_smoke safety test found. | Hold target DB/session and exact file-root identity; failure before file/DB effect. DATABASE_AGENT + BACKEND_AGENT + SECURITY_AGENT; SOURCE-VERIFIED. |
| Q093 ENTRY | `main`; `cleanup_smoke.py:172-180` | CLI/prompt/dispatch to Q092. | `__main__` path; interactive confirmation only. | none focused. | Do not mistake prompt for access control. DATABASE_AGENT + SECURITY_AGENT; SOURCE-VERIFIED. |
| Q094 | `_resolve_stored_path`; `cleanup_smoke.py:47-61` | Resolves caller/database path. | No approved-root capability; may allow absolute/existing path per Step 1.6P/6O. | none focused. | Reject paths outside held upload root; symlink/no-follow checks. BACKEND_AGENT + SECURITY_AGENT; SOURCE-VERIFIED. |
| Q095 | `_key`; `cleanup_orphan_uploads.py:47-64` | Path/key normalization. | Pure helper; actual containment belongs to caller. | cleanup orphan tests cover basic paths. | Canonical key parsing and reject traversal/ambiguous separators. DATABASE_AGENT + SECURITY_AGENT; SOURCE-VERIFIED. |
| Q096 | `_referenced_keys`; `cleanup_orphan_uploads.py:68-80` | Opens async DB session, selects references. | No independent target identity; called before sweep. | `test_cleanup_orphan_uploads.py` patches DB references/failure. | Read-only authorization and target binding. DATABASE_AGENT; SOURCE-VERIFIED. |
| Q097 | `_scan_uploads`; `cleanup_orphan_uploads.py:83-88` | Recursively reads upload tree. | Caller root; symlink/path race remains. | cleanup tests use temp roots. | Root/file identity and no-follow traversal. DATABASE_AGENT + SECURITY_AGENT; SOURCE-VERIFIED. |
| Q098 | `_archive_orphans`; `cleanup_orphan_uploads.py:91-128` | Caller archive path, creates parent, writes ZIP. | Path checks precede write but no exclusive held-file identity. | tests cover archive inside root only. | Exclusive create under authorized archive root; reject replacement/symlink. DATABASE_AGENT + SECURITY_AGENT; SOURCE-VERIFIED. |
| Q099 | `run_sweep`; `cleanup_orphan_uploads.py:131-238` | DB reference read, archive/unlink/rglob/rmdir. | `--delete --yes` flag and dry-run default; direct callable bypasses CLI confirmation; check/use race. | `test_cleanup_orphan_uploads.py`: fake refs, failure, archive/root/simple symlink cases. | Operation authorization at deletion and root handle; unsupported platform fail closed. DATABASE_AGENT + SECURITY_AGENT; SOURCE-VERIFIED, races UNVERIFIED. |
| Q100 ENTRY | `main`; `cleanup_orphan_uploads.py:241-255` | CLI parse and calls Q099. | `__main__`; user flag not authority. | script tests do not execute CLI here. | Require explicit reviewed delete capability before dispatch. DATABASE_AGENT; SOURCE-VERIFIED. |
| Q101 ENTRY | `create_user`; `backend/scripts/create_test_user.py:38-58` | Session/query/add/commit to configured DB; credentials supplied. | No evaluation target guard; standalone operational helper. | auth tests may cover login, not target identity. | Explicit approved destination and service credential; DATABASE_AGENT + BACKEND_AGENT; SOURCE-VERIFIED. |
| Q102 ENTRY | `main`; `create_test_user.py:61-68` | CLI parse and invokes Q101. | `__main__`, arbitrary target through environment/config. | no target test. | Same as Q101; SOURCE-VERIFIED. |
| Q103 ENTRY | `main`; `backend/scripts/db_check.py:16-30` | Imports engine, connect + SELECT + dispose. | Module ends with `asyncio.run(main())` at line 33; import triggers connection before caller guard. It only selects version in inspected body; destructive SQL not present. | No import-tripwire test identified. | Make import inert; explicit connect action with target authorization. DATABASE_AGENT + TEST_AGENT; SOURCE-VERIFIED for source order, runtime UNVERIFIED. |
| Q104 ENTRY | module `asyncio.run(main())`; `db_check.py:33` | Module-level execution boundary, not a callable definition. | Runs on import and script. | No tripwire test. | Separate entry invocation from import; TEST_AGENT + DATABASE_AGENT; SOURCE-VERIFIED. Counted separately only in effect-site candidates, not callable records. |
| Q105 ENTRY | `main`; `backend/scripts/setup_db.py:30-58` | Subprocess/migration setup. | CLI path, not evaluation guard. | no command run; no test mapped. | Explicit operator/environment and migration authorization. DATABASE_AGENT; SOURCE-VERIFIED. |
| Q106 ENTRY | `main`; `backend/scripts/start_server.py:44-107` | Socket probe, recursive pycache deletion, subprocess launch, HTTP polling. | Import-time script statements execute before any caller can guard; exact lines 40-67 include cwd change, port probe, rmtree and Popen. | No test covers import inertness. | Make module import inert; bind cleanup root and server target. BACKEND_AGENT + SECURITY_AGENT; SOURCE-VERIFIED. |
| Q107 | `_run_migrations`; `backend/main.py:44-53` | Alembic upgrade DDL. | Called from lifespan path; no evaluation lifecycle capability. | migration test covers SQLite migration separately. | Separate production startup migration policy from eval runner. BACKEND_AGENT + DATABASE_AGENT; SOURCE-VERIFIED. |
| Q108 ENTRY | `_ensure_database_schema`; `main.py:56-72` | Runs Q107 in executor. | Called before service readiness. | no evaluation target test. | Explicit migration authorization/config compatibility decision. BACKEND_AGENT + DATABASE_AGENT; SOURCE-VERIFIED. |
| Q109 ENTRY | `lifespan`; `main.py:75-84` | Migration, upload mkdir, engine dispose. | Invoked by app server lifecycle; effects precede request handling. | app tests use test lifespan overrides where configured; not PG proof. | Production-only migration policy; separate eval app factory. BACKEND_AGENT + DATABASE_AGENT; SOURCE-VERIFIED. |
| Q110 | module `engine`; `backend/storage/database.py:41-49` | Import-time create_async_engine/sessionmaker. Engine object creation, not evidence of network connect. | Module scope, before caller guard; physical connection typically later but not tested. | `test_runner_pre_engine_init.py` checks selected runner avoids import; no import connection proof. | Lazy factory or inert module; validate settings before engine construction. BACKEND_AGENT; SOURCE-VERIFIED engine construction, connection UNVERIFIED. |
| Q111 | `get_db`; `backend/storage/database.py:56-63` | Async session; commits/rolls back. | FastAPI dependency; caller DB identity from module engine; no eval authority. | app/unit tests exercise dependency in SQLite fixture, not PG identity. | Session-bound production auth remains separate from eval authority. BACKEND_AGENT; SOURCE-VERIFIED. |
| Q112 | `_user_upload_dir`; `backend/storage/file_store.py:22-26` | Caller user ID; creates directory. | Root from settings; no local traversal/no-follow authority shown. | file validation tests do not establish race-free root. | Validate identifier and held root. BACKEND_AGENT + SECURITY_AGENT; SOURCE-VERIFIED. |
| Q113 | `save_upload`; `file_store.py:29-50` | Writes caller bytes/name/user path. | Root and filename derived by helper; application validation in caller. | document upload tests validate API contract, not concurrent path swap. | Root capability and safe file creation at operation. BACKEND_AGENT; SOURCE-VERIFIED. |
| Q114 | `delete_upload`; `file_store.py:53-65` | Caller path; unlink. | Caller route may check ownership; helper direct call has no independent root guard. | document mutation tests cover API auth/ownership, not helper direct invocation. | Helper-local root/file identity and caller ownership. BACKEND_AGENT + SECURITY_AGENT; SOURCE-VERIFIED. |
| Q115 | `cleanup_new_file`; `file_store.py:68-79` | Caller path; unlink rollback cleanup. | Called after failed upload paths; no independent containment shown. | upload failure tests may exercise route but not outside-root direct input. | Restrict to newly created owned file handle/path token. BACKEND_AGENT + SECURITY_AGENT; SOURCE-VERIFIED. |
| Q116 ENTRY | `run_migrations_offline`; `backend/migrations/env.py:63-72` | Alembic offline DDL generation. | No DB connection in offline mode by intent; direct CLI route. | migration tests inspect chain; no offline side effects run. | Keep offline clearly separated from DB execution; DATABASE_AGENT; SOURCE-VERIFIED. |
| Q117 ENTRY | `do_run_migrations`; `migrations/env.py:75-78` | Executes revision operations in supplied connection context. | Caller supplies context; no target authorization in function. | SQLite migration subprocess tests exercise migration semantics only. | Verify connection-bound migration capability at operation boundary. DATABASE_AGENT; SOURCE-VERIFIED. |
| Q118 ENTRY | `run_async_migrations`; `migrations/env.py:81-90` | Creates engine/connect, runs DDL and disposes. | CLI target resolver/fallback; connection created within helper. | no PostgreSQL command run. | Immutable target and authorization before create/connect; DATABASE_AGENT; SOURCE-VERIFIED. |
| Q119 ENTRY | `run_migrations_online`; `migrations/env.py:93-94` | `asyncio.run` dispatch. | Called by Alembic env; direct CLI alternate route. | migration tests are SQLite. | No fallback target; explicit mode and target guard. DATABASE_AGENT; SOURCE-VERIFIED. |
| Q120 ENTRY | module `docker-entrypoint.sh`; `backend/docker-entrypoint.sh:1-` | Shell entry runs Alembic upgrade before server. | Executable deployment route outside evaluation guards. | no container run here. | Explicit deployment migration policy; no reuse for eval. DATABASE_AGENT + BACKEND_AGENT; SOURCE-VERIFIED. |

### 6.6 Migration revision callables

Each upgrade/downgrade is independently callable by Alembic and is its own DDL boundary. All are `SOURCE-VERIFIED` for revision operation calls; all actual server effects and privileges are `UNVERIFIED`. No migration was run. Existing mapped coverage: `backend/tests/integration/documents/test_table_row_migration.py` exercises revision 007 in a subprocess with SQLite and checks revision chain/additive schema behavior; it does not prove PostgreSQL DDL, pgvector, target identity, or grants. Required future containment is Alembic’s connection-level authorized target and fail closed before revision execution. Owner DATABASE_AGENT; SQLite behavior compatibility needs TEST_AGENT.

| ID | Callable; path:line range | Effects; guard/callers | Test evidence / requirement |
|---|---|---|---|
| M001 | `upgrade`; `backend/migrations/versions/000_create_base_tables.py:100-303` | Executes fixed DDL/create table/index; Alembic calls. | SQLite migration tests don’t cover revision 000 on PG; connection-bound migration authorization. |
| M002 | `downgrade`; same file `:310-345` | Drop indexes/tables. | Never invoke absent separately approved destructive migration authority. |
| M003 | `upgrade`; `001_add_reliability_logs.py:21-57` | Create table/index. | Same; source only. |
| M004 | `downgrade`; same file `:60-62` | Drop table/index. | Same. |
| M005 | `upgrade`; `002_add_content_hash.py:20-29` | Add column/index. | Same. |
| M006 | `downgrade`; same file `:32-34` | Drop column/index. | Same. |
| M007 | `upgrade`; `003_add_chunk_metadata.py:29-53` | Add columns. | Same. |
| M008 | `downgrade`; same file `:56-62` | Drop columns. | Same. |
| M009 | `upgrade`; `004_add_processing_provenance.py:30-51` | Add columns. | Same. |
| M010 | `downgrade`; same file `:54-58` | Drop columns. | Same. |
| M011 | `upgrade`; `005_add_document_graph.py:46-105` | Create tables/indexes. | Same. |
| M012 | `downgrade`; same file `:108-117` | Drop tables/indexes. | Same. |
| M013 | `upgrade`; `006_add_structure_elements.py:54-171` | Create tables/indexes. | Same. |
| M014 | `downgrade`; same file `:174-202` | Drop tables/indexes. | Same. |
| M015 | `upgrade`; `007_add_table_rows.py:61-114` | Create table/indexes. | SQLite regression test exists but does not prove PG target/privileges. |
| M016 | `downgrade`; same file `:117-127` | Drop table/indexes. | SQLite downgrade test is not authorization proof. |
| M017 | `upgrade`; no record — **invalid/reserved**. | No revision 008 exists in the inspected 000–007 chain. | No callable evidence; exclude from valid count. |
| M018 | `downgrade`; no record — **invalid/reserved**. | No revision 008 exists in the inspected 000–007 chain. | No callable evidence; exclude from valid count. |

The source scan established 16 revision functions (upgrade/downgrade for 000–007); M017/M018 are reserved placeholders and not callable records. Q104 is a module-level `asyncio.run(main())` statement, not a function definition. Q116–Q119 are the separately listed Alembic environment functions and are not revisions 008. Some operational script rows also describe module-level code or an object rather than a callable. The current record tables consequently have ID/classification defects. **No unique normalized total is accepted** until a follow-up edits this table into a canonical one-callable-per-ID manifest and mechanically verifies IDs, duplicate source spans, and entry-point classifications. The AST call-site figure is deliberately bounded to the vocabulary above; dynamic calls and other effect APIs are omitted.

## 7. O-1–O-9 and P-series reconciliation

### 7.1 O-series disposition

| Finding | Normalized record(s) | Current source disposition |
|---|---|---|
| O-1 table row supplied session | X001 | Confirmed; helper exists and calls structure persistence. Fixture target runtime UNVERIFIED. |
| O-2 graph replacement tests | No individual Q/X record for every `test_*` call site; source path `test_graph_ingestion.py` contains multiple distinct test functions | Confirmed omission remains; call-site records unresolved. |
| O-3 table-evidence `_seed` helpers | X002, X003 | Confirmed. Additional direct `test_*` replacements in table evidence bands are not each separate record; unresolved per-callsite acceptance. |
| O-4 foreign-document graph seed | X004 | Confirmed; auth assertion does not establish server identity. |
| O-5 reachability fixture unlink + persistence | X005 | Confirmed; session/path provenance unverified. |
| O-6 browser raw SQL/file operations | Q084, Q085, Q087 | Confirmed; base/DB target and live server are unverified. |
| O-7 reliability browser rmtree/process | Q086 | Confirmed; exact scratch ownership and live server unverified. |
| O-8 phase 3E validation/integration effects | Q054, Q057, Q056, Q059 | Confirmed at callable level; individual unlink/API/SQL sites are effect sites, not additional callables. Per-site sequence is not normalized. |
| O-9 archive/prune/unlink | Q095–Q100 | Confirmed; tests cover simple temp-root cases only; race-safe filesystem behavior unverified. |

O-2 and part of O-3 remain **under-normalized** because the previous group identifies multiple direct test functions, not just shared helper callables. No safety status changes; no tests were run.

### 7.2 P-series group mapping and disposition

P01→Q004–Q013 (central lifecycle/config); P02→Q001–Q003; P03→Q014–Q019; P04→Q020–Q023; P05→Q031–Q034; P06→Q021–Q030; P07→Q090–Q091; P08→Q047–Q050; P09→Q051–Q053; P10→Q054–Q056; P11→Q057–Q060; P12→Q061–Q064; P13→Q065–Q068; P14→Q044–Q046; P15→Q076–Q081; P16→Q069–Q075; P17→Q036–Q041; P18→Q084–Q089; P19→Q092–Q100 and Q094–Q099; P20→Q101–Q120 and X records relevant to tests. These are cross-references, not independent callables. Because Q IDs after Q082 were added after the initial count statement, the P crosswalk confirms the record numbering and total still require a mechanical consistency pass; total accepted as unresolved.

Previous findings are classified: source callable still present → confirmed; same callable in two groups → overlapping, not duplicate record; earlier report’s grouped wording → superseded by exact current source where line differs; lacking an ID for each named function → unresolved; not-found only after bounded exact search → none claimed beyond `backend/start_server.py` absent (current path is `backend/scripts/start_server.py`).

## 8. Existing test mapping and evidence limits

Existing mapped tests include:

- `backend/tests/unit/evaluation/test_lifecycle_authorization.py`: fail-closed guard and source-order/patch behavior; no actual PostgreSQL identity.
- `test_disposal_authorization_contract.py`: refusal/proof-object conditions; no authority-backed positive lifecycle.
- `test_function_cleanup_authorization.py`: direct cleanup helper refusal source contract; not ingestion authority.
- `test_evaluation_isolation.py`, `test_isolation_guard_identity.py`, `test_phase3_runner_target_order.py`, `test_runner_pre_engine_init.py`, `test_structure_runner_guard_order.py`, `test_legacy_runner_isolation.py`: pure URL or source/monkeypatch ordering and refusal coverage; no PG permissions/server identity.
- `test_phase3d_cleanup_scope.py`, `test_phase3d_evaluation_cleanup_scope.py`, phase3e/phase3f/phase4b cleanup scope tests: SQLite row ownership/deletion semantics only.
- `backend/tests/unit/scripts/test_cleanup_orphan_uploads.py`: mocked DB reference and temp filesystem basic containment/archive/failure cases; no symlink races or held-root semantics.
- `backend/tests/integration/documents/test_table_row_migration.py`: SQLite Alembic migration contract, not PG.
- O-series integration writers: structure/graph persistence semantics through configured fixture, not evaluation safety evidence.

Proposed database-free tests (not run): direct `psql_value`, `psql`, migration, `postgres_available`, ingestion/session helpers, and cleanup helpers with subprocess/socket/session/path tripwires; import `db_check` and start-server modules under patched connect/process/file-delete functions; conflicting resolver configs must refuse before engine/session; production-like caller-supplied session refuses before attribute access; outside-root, traversal, symlink/junction, root replacement, archive collision and unknown-platform cleanup all refuse in a separately approved temp sandbox. Such tests prove “no helper side effect before refusal” for the patched boundary only; they do not prove PostgreSQL OID/server identity, authenticated role grants, app DB unreachable, pool reconnect behavior, or race safety on deployment filesystem.

## 9. Newly identified and unresolved gaps

1. The count/ID inconsistency described in §6 is real: records added after Q082 and migration aliases prevent accepting a precise total. This report intentionally discloses the defect rather than claiming a normalized total.
2. O-2 names multiple graph test methods directly calling `replace_document_graph`; only the shared production helper and some examples are cross-referenced. Per-test callsite IDs remain outstanding.
3. O-3’s direct calls in table evidence bands include test methods beyond `_seed_document`; no separate record for every such test method.
4. The 109 narrow scan does not include production CRUD endpoints, caller-session tests outside the O paths, or import-time statements by design. A broader exploratory scan found many more hits, but generic method names (`get`, `open`, `add`) overcount non-DB operations; no precise expanded universe is claimed.
5. Production `documents.routes`/`structure`, `graph.service`, `embeddings.routes` and generic auth/session boundaries are represented only selectively; all app call paths remain unresolved pending a dedicated full production DB boundary task.
6. `storage.database.engine` construction is at import; source cannot prove whether any driver opens a connection without executing it. `db_check.py` top-level `asyncio.run` clearly calls `engine.connect()` in the import path, but runtime outcome is unverified.
7. `scripts/start_server.py` has module-top-level cwd change, socket probe, recursive pycache deletion and subprocess launch; it is not the root-level `backend/start_server.py` previously named in one P-row (that path is absent).
8. `docker-entrypoint.sh`, main lifespan, direct Alembic CLI and direct revision callables are separate migration paths. Runtime target resolution and fallback are not tested here.
9. Direct filesystem helper safety depends on OS/platform, junction/reparse/hard-link semantics, path replacement, and held handles. None is proven by path-resolution source or temp-root unit tests.
10. The prior Step 1.6P exact final set comparison was unresolved; this task captures a fresh baseline and can compare only changes during Step 1.6Q. It cannot retroactively prove what changed in prior tasks.
11. No independent reviewers available. No source inventory can certify archived phases/dynamic import paths without a fresh separate scope.

## 10. Prioritized remediation backlog (requirements only)

1. **P0 — Coordinator + Verifier (when dispatch exists):** repair Q ID sequence and produce a machine-checked canonical manifest with one row per callable; resolve O-2/O-3 direct test callsite enumeration; publish count script and manifest checksum. No implementation or DB access.
2. **P1 — DATABASE_AGENT + TEST_AGENT:** remove or locally deny arbitrary-SQL APIs (`Q020`, `Q034`); protect direct `migrate_to_head`/DDL and socket helpers (`Q018`, `Q026`, `Q029`); retain all present lifecycle refusals. Test direct calls with no-I/O tripwires.
3. **P2 — EVALUATION_AGENT + TEST_AGENT:** independently gate supplied-session ingestion (`Q045`, `Q048`, `Q062`, `Q066`, `Q072`, `Q077`) and all cleanup/run_once methods; validate before inspecting resource; keep unconditional current denials until a separately approved authority exists.
4. **P3 — BACKEND_AGENT + DATABASE_AGENT:** split import-time/module startup actions from `db_check`, `start_server`, storage engine construction, app lifespan migrations, Docker entrypoint and Alembic online mode. Decide production migration compatibility before code changes.
5. **P4 — DATABASE_AGENT + BACKEND_AGENT + SECURITY_AGENT:** define OS-specific held-root/file identity, safe archive create, deletion plan, writer fence, quarantine/recovery; direct `file_store`/smoke/orphan cleanup must fail closed on unknown or raced paths.
6. **P5 — TEST_AGENT:** no-I/O test suite for conflicting target config, import tripwires, production-like sessions, unauthorized SQL/migration helpers, standalone E2E/purge paths and path containment. Explicitly label these as no-I/O evidence, not PostgreSQL proof.
7. **P6 — operator decision:** name ELA owner, target allocation owner, attestation source, roles/HBA/network constraints, migration admin, recovery/journal custodian, and supported filesystem/platform.
8. **P7 — future PostgreSQL verification only after approval:** separately authorize each connect/create/migrate/read/write/delete/cleanup/drop action, review logs and stop/recovery rules, verify physical connection target/reconnect/pool identity and role grants independently, and keep all current gates fail-closed until positive authorization is implemented and independently reviewed. This task grants no authorization.

## 11. Explicit PostgreSQL verification prerequisites

PostgreSQL remains **NO-GO** until: independent Database/Security/Evaluation/Test/Verifier reviews occur; operator and ELA/allocation owners are named; one immutable authenticated target manifest exists; actual cluster/database identity and role grants are verified on each physical connection/reconnect; the application DB is unreachable by the evaluation worker through direct clients, API, migration, runner, or startup path; generic SQL and direct helper bypasses are removed or mediated; create/migrate/recovery/quarantine/drop protocol is implemented and reviewed; DB-free refusals pass; filesystem authorization is designed and independently tested in an approved sandbox; and a separate explicit operator decision authorizes each future network/DDL/DML/cleanup stage. No item is established by this report.

## 12. Final Git-state comparison

The initial status snapshot captured before writing the report had **1,142 entries** and initial HEAD `6baaa2a0773df66e5fb26814afbe67647fb43435`. The snapshot file was later overwritten during recovery after an environment-specific path read failed, so exact path-by-path comparison to the true pre-report snapshot is **UNVERIFIED**. Final observed HEAD is still `6baaa2a0773df66e5fb26814afbe67647fb43435`; final status has **1,143 entries** and includes this report as untracked. This is consistent with one new report path, but count alone does not prove no other status entry changed. No implementation or test file was written by this task; pre-existing modifications/deletions remain present. No tests or application/database operations ran.

**Final report status:** partial normalization. Per-callable source records and reconciliation were prepared, but a later ID expansion exposed an unresolved count inconsistency, and O-2/O-3 per-callsite records plus full production-surface enumeration remain incomplete. Independent review remains outstanding. PostgreSQL **NO-GO**.
