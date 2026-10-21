# STEP 1.6T — Manifest Classification Corrections and Safety-Boundary Crosswalk

Date: 2026-10-13
Owner: COORDINATOR. Role-scoped read-only checks were executed by generic runtime subagents; the named project specialists (`DATABASE_AGENT`, `SECURITY_AGENT`, `EVALUATION_AGENT`, `TEST_AGENT`, `VERIFIER`) did not execute as named agents (see §1).

Sources reviewed:
- `backend/architecture/STEP1_6R_CANONICAL_CALLABLE_MANIFEST_2026-10-12.md` (historical inventory, 1732 lines)
- `backend/architecture/STEP1_6S_INDEPENDENT_MANIFEST_REVIEW_2026-10-12.md` (independent review; findings U-01…U-08, S-1…S-5)

**Verdict: COMPLETE (documentation/inventory only).** The four principal gaps — module-scope database initialization, authorization-helper coverage, decorator false-positive classification, and filesystem guard-helper coverage — are addressed with source evidence and reproducible counts, recorded as additive records and revised semantic counts that do not replace the historical 1.6R values. No application code, test, migration, configuration, or safety gate was changed. PostgreSQL remains **NO-GO**.

## 1. Agent-dispatch attempts and execution outcomes

The runtime exposes only generic subagents (`code-searcher`, `file-picker`, and a non-terminal worker). No mechanism instantiates the named project roles defined in `agents/*.md`; that dispatch target is unavailable and was recorded as unavailable in 1.6R §2 and 1.6S §1. No review is attributed to those roles.

| Role | Dispatch attempted | Actually executed | Evidence returned |
|---|---|---|---|
| COORDINATOR | n/a (self) | Yes | Classification scanner, revised counts, safety-helper and caller crosswalks, Git comparison, this report |
| DATABASE_AGENT (named) | Yes — unavailable | No | — |
| SECURITY_AGENT (named) | Yes — unavailable | No | — |
| EVALUATION_AGENT (named) | Yes — unavailable | No | — |
| TEST_AGENT (named) | Yes — unavailable | No | — |
| VERIFIER (named) | Yes — unavailable | No | — |
| Generic `code-searcher` #1 (DATABASE-scoped, T-01) | Yes | Yes | `storage.database` importer list; engine/session creation sites; `get_db` consumers; migration/lifespan references |
| Generic `code-searcher` #2 (SECURITY/EVALUATION-scoped, T-02) | Yes | Yes | `evaluation.isolation` definition sites, 8 runner import sites, `tests/fixtures/integration_db.py:66-73`, 16 unit test modules |
| Generic `code-searcher` #3 (SECURITY-scoped, T-04) | Yes | Yes | `cleanup_path` call sites (`cleanup_orphan_uploads.py:50,197,203`), `unlink`/`rmdir` sites, unit tests |
| Generic `code-searcher` #4 (TEST/VERIFIER-scoped, T-03) | Yes | Yes | All `@router.*` / `@app.*` decorators (26 + 18), receiver analysis enabling the decorator rule |

**Subagent execution limitation (recorded, not hidden).** Of 17 ripgrep batches issued across the four generic agents, **14 executed and 3 failed** with `ENOENT: uv_spawn 'C:\Users\moham\.config\manicode\rg.exe'` (vendored ripgrep unavailable in this runtime). The three failed batches covered: `main.py` lifecycle patterns, the `cleanup_path` function-definition listing, and one decorator batch. Their subject matter was recovered by other executed batches and by the COORDINATOR's own AST scanner, so no finding depends solely on a failed batch.

## 2. References to the findings being addressed

| 1.6S finding | This report |
|---|---|
| S-1 / U-01 (HIGH) — production engine/session factory has no callable-level record | §4 (T-01) |
| S-2 / U-03 (MEDIUM) — evaluation authorization module absent from the record set | §5 (T-02) |
| U-02 (MEDIUM) — `@router.delete` classified as a `delete` effect | §7 (T-03) |
| S-3 (MEDIUM) — non-matching filesystem guard helpers invisible | §6 (T-04) |
| U-04 / U-05 / U-07 (LOW) — count semantics, file-scoped site column, snapshot line endings | §8, §9, §11 |

## 3. Disposition table — T-01 through T-05

| ID | Requirement | Disposition | Evidence |
|---|---|---|---|
| T-01 | Represent module-scope engine/session creation explicitly; identify owning module, initialization context and triggering import/startup paths; separate configuration-time construction from an actual connection; claim no identity/permissions | **RESOLVED (inventory)** | §4; source `backend/storage/database.py:11-63`; 21 static importers enumerated; connection triggers identified |
| T-02 | Inventory safety-relevant functions of `evaluation/isolation.py` even without vocabulary-matched calls; record responsibility and callers; distinguish authorization helper from destructive op; preserve refusals | **RESOLVED (inventory)** | §5; 18 callables, all `is_effect_matched=False`; caller mapping incl. `tests/fixtures/integration_db.py:66-73` |
| T-03 | Distinguish route decorators from deletion; document a decorator rule; preserve raw match counts separately; reconcile affected records | **RESOLVED (rule + analysis)** | §7; exactly 1 decorator false positive in scope: `backend/documents/routes.py:600` → module site `M-da4eab41f6483c` |
| T-04 | Inventory path-containment helpers and callers; identify TOCTOU/symlink concerns only where source supports them; execute nothing | **RESOLVED (inventory)** | §6; 3 callables in `backend/scripts/cleanup_path.py`; callers and the check-then-use window documented |
| T-05 | Keep 1.6R counts historical; report revised semantic counts separately; distinguish raw nodes / sites / module sites / records / safety-helper records; reproducible scanner; document dynamic targets as unresolved | **RESOLVED** | §8, §9; historical values re-derived and unchanged; revised counts are additive and separately labelled |

**Decision on modifying Step 1.6R.** The 1.6R document and its embedded scanner were **not modified**. The decorator mislabel is a classification improvement, not a defect that invalidates any published count: 1.6R's raw syntactic totals stay true under its declared rule. Changing the historical artifact would destroy the "historical baseline" the task requires preserving, so the correction lives here as an additive rule (D-1) plus a reclassification of the affected site. No append-only correction note to 1.6R is therefore required.

## 4. T-01 — Module-scope engine/session-factory records and initialization paths

**Owner module:** `backend/storage/database.py`. All four module-scope constructs are configuration-time; none opens a socket.

| Init ID | Location | Construct | Classification | Creates a connection at import? |
|---|---|---|---|---|
| I-01 | `backend/storage/database.py:39` | `_database_url, _connect_args = _asyncpg_engine_args(settings.database_url)` | config-time URL normalisation (pure string transform; def at `:11-38`) | **No** |
| I-02 | `backend/storage/database.py:43-48` | `engine = create_async_engine(_database_url, echo=False, pool_pre_ping=True, connect_args=_connect_args)` | config-time engine construction | **No** — SQLAlchemy `Engine` connects lazily |
| I-03 | `backend/storage/database.py:49` | `async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)` | config-time session factory | **No** |

`create_async_engine` is a constructor for a connection-pool manager; the first physical connection happens when a session or connection is acquired. The module's own consumers confirm the split: `get_db()` (`:56-63`) acquires via `async with async_session()`, and `backend/scripts/db_check.py:26` acquires via `engine.connect()` inside `main()` (driven by the module-level `asyncio.run(main())` at `:33`).

**Static initialization triggers (import-time).** Importing `storage.database` executes I-01…I-03. Statically identified importers (21 sites, from source):

- production modules: `main.py:13` (`Base, engine`), `auth/dependencies.py:11`, `auth/routes.py:13`, `chat/models.py:8`, `chat/routes.py:9`, `documents/models.py:20`, `documents/routes.py:29`, `embeddings/routes.py:16`, `graph/models.py:30`, `reliability/models.py:8`, `reliability/routes.py:11`, `settings/routes.py:20`, `user/models.py:8`, `verification/models.py:8`
- migrations: `migrations/env.py:19` (`Base`), `migrations/env.py:50` (`_asyncpg_engine_args`)
- scripts: `scripts/db_check.py:13` (`engine`), `scripts/create_test_user.py:33` (`async_session`), `scripts/cleanup_smoke.py:40` (`async_session`), `create_test_user.py:25` (`async_session`)
- tests: `tests/conftest.py:167,193`
- evaluation runners: imported **inside `main()`** after the guard, e.g. `run_phase3d_evaluation.py:674`, `run_phase3e_integration.py:208`, `run_dual_path_ablation.py:675`, `run_structure_*` (`:1875`, `:890`, `:1111`) — deliberately deferred so the target guard runs before the engine is built.

**Connection-time triggers (static, not executed).** `storage/database.py:56-63` (`get_db`, used by every DB route via `Depends(get_db)`); `backend/main.py:44-53` lifespan `_run_migrations` (`command.upgrade(alembic_cfg, "head")` at `:53`, invoked at `:65`); `backend/scripts/setup_db.py:41-42` (subprocess `alembic upgrade head`); `backend/tests/fixtures/integration_db.py:429-441` (`migrate_to_head`, called at `:564`); `backend/scripts/db_check.py:26`.

**Explicit non-claims.** No connection identity, role, TLS mode, pool/reconnect behaviour, or database permission was verified. This section records *where* initialization and connection are attempted in source, nothing about what a connection would reach.

## 5. T-02 — Authorization-helper records and caller mappings

`backend/evaluation/isolation.py` yields **zero** effect-matched records under the 1.6R vocabulary because it performs no database or filesystem call — it is pure string inspection and refusal. It is now inventoried as **safety-helper records**: 18 callables, all `is_effect_matched=False`.

| Line range | Callable | Responsibility (source docstring) | Raises |
|---|---|---|---|
| 107-122 | `_read_env_file_value` | Read one `KEY=VALUE` from an env file | — |
| 125-143 | `application_database_url` | The DSN the application itself uses (`.env` outranks environment) | — |
| 146-164 | `database_identity` | `(host, port, database)` of a DSN, credentials excluded | `UnsafeEvaluationTarget` |
| 167-170 | `describe_identity` | Credential-free identity rendering | — |
| 173-184 | `display_dsn` | Credential-free DSN rendering | — |
| 187-218 | `evaluation_database_url` | Resolve the evaluation target; explicit, never invented | `UnsafeEvaluationTarget` |
| 226-246 | `_refuse_unverifiable_url` | Refuse a URL whose connection cannot be tied to the named database | `UnsafeEvaluationTarget` |
| 249-314 | `assert_safe_evaluation_target` | Prove target ≠ application database, or refuse; runs before any connection | `UnsafeEvaluationTarget` |
| 317-325 | `describe_targets` | Two credential-free target lines | — |
| 363-366 | `_proof_is_live` | No proof is live without an enforceable lifecycle authority | — |
| 369-374 | `record_created_database` | Refuse caller-asserted creation evidence | `UnsafeEvaluationTarget` |
| 377-412 | `assert_disposal_authorized` | Always refuse destruction; no enforceable lifecycle authority exists | `UnsafeEvaluationTarget` |
| 415-440 | `assert_creation_authorized` | Refuse creation without an enforceable create authority | `UnsafeEvaluationTarget` |
| 443-453 | `assert_row_cleanup_authorized` | Refuse row cleanup under the same missing-authority rule | — |
| 456-474 | `assert_cleanup_execution_authorized` | Block destructive callables before inspecting a session/engine | `UnsafeEvaluationTarget` |
| 477-482 | `release_database_proof` | Refuse lifecycle release | `UnsafeEvaluationTarget` |
| 485-501 | `assert_engine_bound_to_proof` | Refuse unless the engine targets the proof's database | — |
| 504-522 | `assert_engine_matches_target` | Refuse unless the engine is configured for the named DSN | `UnsafeEvaluationTarget` |

**Caller mapping (static).**

- Evaluation runners importing the guard at module scope: `run_dual_path_ablation.py:127-132`, `run_phase3d_upload_integration.py:83-87`, `run_phase3d_evaluation.py:71-75`, `run_phase3e_validation.py:37-40`, `run_phase3e_integration.py:37-41`, `run_phase3f_evaluation.py:51-54`, `run_phase4b_evaluation.py:48`, `run_structure_element_measurement.py:88`, `run_table_evidence_measurement.py:253-256`.
- Deferred in-`main` imports: `run_structure_confirmation.py:700`, `run_structure_rrf_calibration.py:955`, `run_phase3d_upload_integration.py:263`, `run_phase3e_validation.py:215`, `run_phase3f_evaluation.py:851`, `run_phase4b_evaluation.py:831`, `run_table_evidence_measurement.py:481,644,1099-1104`.
- Integration fixture: `tests/fixtures/integration_db.py:66-73` imports `DisposalProof`, `assert_creation_authorized`, `assert_disposal_authorized`, `assert_row_cleanup_authorized`, `assert_safe_evaluation_target`, `record_created_database`, `release_database_proof`, `database_identity`.
- E2E validation: `tests/integration/rag/test_real_e2e_validation.py:66` imports `assert_engine_bound_to_proof`.
- Unit tests: 16 modules import `from evaluation import isolation` (e.g. `test_isolation_guard_identity.py:14`, `test_lifecycle_authorization.py:21`, `test_function_cleanup_authorization.py:16`).

**Authorization helper vs destructive operation.** The distinction is now explicit in the inventory: helper records have `is_effect_matched=False` and a populated `raises` column; destructive operations keep their 1.6R record identity and effect list. No refusal behaviour was changed, relaxed, or reordered — this task read the file and wrote documentation only.

## 6. T-04 — Filesystem guard-helper records and caller mappings

`backend/scripts/cleanup_path.py` also yields zero effect-matched records (it deletes nothing, opens no database — stated in the module docstring). Inventoried as safety-helper records:

| Line range | Callable | Responsibility | Raises |
|---|---|---|---|
| 18-34 | `is_under` | True only if `path` is inside `root` after resolving both | — |
| 37-51 | `forbid_symlink_roots` | Refuse an upload root that is itself a symlink | `RuntimeError` |
| 54-66 | `filesystem_supports_relative_symlinks` | Pre-flight claim about relative-symlink support | — |

**Caller mapping (static).** `backend/scripts/cleanup_orphan_uploads.py:50` (import-time pre-flight), `:197` (`forbid_symlink_roots(root)` immediately before the deletion loop), `:203` (`is_under(root, path)` per orphan), plus `tests/unit/scripts/test_cleanup_orphan_uploads.py:32,239,244,255`.

**Source-supported concerns (no execution).**

1. **Check-then-use window.** `forbid_symlink_roots(root)` at `:197` and `is_under(root, path)` at `:203` are evaluated per iteration, and the destructive `path.unlink()` at `:210` follows. A path replaced between check and unlink is a classic TOCTOU window; the source performs no `os.open(..., O_NOFOLLOW)`-style handle-bound deletion. Recorded as a source-supported observation, not a proven exploitable defect.
2. **Unguarded contract stub.** `filesystem_supports_relative_symlinks()` returns `True` unconditionally (`:54-66`); its docstring says real support "is asserted in a later step". The import-time gate at `cleanup_orphan_uploads.py:50` therefore cannot fail closed on a filesystem that does not support relative symlinks.
3. **Guard scope.** The helper constrains deletion to the upload root; it does not authorize *which* root. `settings.upload_path` provenance is outside this helper and remains with the owning review.

No cleanup script was run and no file was deleted, moved, or created outside the authorized report.

## 7. T-03 — Decorator false-positive rule and affected-record analysis

**Rule D-1 (documented classification rule).** *A matched callee name appearing inside a decorator expression (`FunctionDef.decorator_list` / `AsyncFunctionDef.decorator_list` / `ClassDef.decorator_list`) is classified `decorator-annotation`, not an operational effect. It remains counted as a raw syntactic match. Decorators execute at definition/import time and register routing, caching, or fixtures; they do not themselves delete, write, or connect.*

**Affected-record analysis.** Under the 1.6R vocabulary, exactly **one** decorator match exists in the whole scoped tree:

| Path:line | Expression | Callee | Receiver | 1.6R record | Revised classification |
|---|---|---|---|---|---|
| `backend/documents/routes.py:600` | `@router.delete("/{document_id}", status_code=status.HTTP_200_OK)` | `delete` | `router` | module site `M-da4eab41f6483c` (§9) | `decorator-annotation` (not an operational effect) |

The real deletion in that module is inside the callable body and is unaffected: `backend/documents/routes.py:628` `await db.delete(doc)` and `:697` `await db.delete(chunk)` remain effect-matched records (`delete_document` `C-2018205798555c`, `reprocess_document` `C-25f908d87c337e` in 1.6R §7).

**Additional false-positive class found while validating the rule.** Twelve matched `delete` calls are HTTP requests on a client receiver, not database deletions:

- `backend/evaluation/experiments/run_phase3e_integration.py:421`; `run_phase3e_validation.py:637,740`
- `backend/tests/integration/documents/test_document_mutation_id_validation.py:108,138,159,182,208,282,316,350`
- `backend/tests/integration/graph/test_graph_security.py:253`

These are `client.delete("/api/documents/...")` calls. They are therefore reclassified `http-request` under rule D-2 (receiver-root `client`), again retaining the raw count.

**Rule D-2 (receiver-based reclassification, evidence-bounded).** *A matched attribute call whose receiver root is `client` is classified `http-request`.* Only this one receiver is reclassified, because the source corpus uses `client` exclusively for HTTP test/validation calls. `np`/`numpy` receivers (rule D-3) produced **0** matches in scope, so no array-op misclassification exists inside the declared roots.

**Raw vs semantic separation.** Rule D-1 and D-2 change *classification only*. The 1.6R totals (969 raw nodes / 929 sites / 17 module-scope sites) remain the raw syntactic baseline and are unchanged; the semantically classified counts appear in §8 and are explicitly labelled new.

## 8. Historical versus revised counts

Historical values below were **re-derived** by the 1.6T scanner using the 1.6R declared rule and match 1.6R exactly; nothing historical was replaced.

| Unit | 1.6R historical | 1.6T re-derived | Revised semantic | Notes |
|---|---:|---:|---:|---|
| Files parsed (0 syntax errors) | 226 | 226 | — | unchanged |
| Callable definitions | 2,345 | 2,345 | — | unchanged |
| Effect-matched callable records | 348 | 348 | — | unchanged (unique IDs 348) |
| Raw matched call nodes (callable bodies) | 969 | 969 | 957 operational-candidate + 12 http-request | classification split only |
| Unique operation sites (callable bodies) | 929 | 929 | 917 operational-candidate (+12 http-request sites) | classification split only |
| Module/class-scope sites | 17 | 17 | 16 operational-candidate + 1 decorator-annotation | classification split only |
| Literal `__main__` blocks | 27 | 27 | — | unchanged |
| Selected entry callables | 103 | 103 | — | unchanged |
| **New:** safety-helper records | not represented | — | **22** | 18 `evaluation/isolation.py` + 3 `scripts/cleanup_path.py` + 1 `storage/database.py::_asyncpg_engine_args` |
| **New:** module-scope initialization records | not represented | — | **3** | I-01, I-02, I-03 (§4) |
| **New:** decorator-annotation records | miscounted as effects | — | **1** | `backend/documents/routes.py:600` |
| **New:** http-request records | counted as effects | — | **12** | §7 |
| Raw matched call nodes, **all lexical positions** in scope | 986 total (969 body + 17 module) | 986 | 973 operational-candidate + 12 http-request + 1 decorator-annotation | composition only |

The scanner also emits a reproducible receiver breakdown so any reader can audit classification without re-running the tool. Highest-volume groups (callable bodies): `execute <- db` 177, `add <- db` 61, `delete <- <name>` 58, `flush <- db` 55, `commit <- db` 50, `unlink <- os` 41, `replace_document_graph <- <name>` 30, `create_index <- op` 26, `drop_index <- op` 26, `write_text <- <name>` 18, `dispose <- engine` 16, `delete <- client` 12, `run <- asyncio` 10, `run <- subprocess` 9, `open <- fitz` 12, `save <- doc` 8, `async_sessionmaker <- <name>` 9, `create_async_engine <- <name>` 9, `mkdir <- REPORTS_DIR` 7.

**Counts deliberately not forced to agree.** The revised values are smaller than the historical ones by exactly the reclassified members (12 http-request body matches, 1 decorator module match). They were not adjusted to reach any target; the differences are the classification rule's whole output.

## 9. Scanner procedure, scope, exclusions, limitations, reproducibility

**Procedure.** `backend/venv/Scripts/python.exe <temp>/step16t_scan.py <temp>/step16t-scan.json`, run from the repository root. Standard library only (`ast`, `hashlib`, `json`, `pathlib`, `collections`); parses source and writes one JSON file **outside** the repository. It imports no project module, opens no socket, runs no SQL, and touches no database or uploaded file.

**Scope/exclusions.** Identical to 1.6R §4: every `backend/**/*.py` with path components `venv`, `phases`, `architecture`, `models`, `__pycache__`, `phase4f_gpu` excluded; the same 57-name effect vocabulary. Because `architecture/` is excluded, this report is not self-scanned.

**Limitations (unchanged from 1.6R plus new ones).** Dynamic dispatch, aliases, monkeypatching, framework-generated routes, SQL built indirectly, non-Python startup/compose/Docker entrypoints, and runtime database identity/permissions are unresolved. New to 1.6T: (a) the receiver root is a syntactic name, so `client` aliased or reassigned would defeat D-2; (b) other generic receivers remain unresolved false-positive candidates (e.g. `add <- seen`, `save <- doc`); (c) safety-helper detection is limited to the three declared safety modules — other guard-only modules outside that list would still be absent; (d) the scanner classifies nothing by semantics beyond rules D-1…D-3, so `operational-candidate` means "not reclassified", not "proven destructive".

**Reproducibility evidence.** Re-running the scanner on the unchanged tree reproduces the historical block exactly (226 / 0 / 2,345 / 348 / 969 / 929 / 17 / 27 / 103), and the revised block deterministically. The complete scanner is embedded below so the procedure survives without the temporary file.

```python
"""Step 1.6T classification scanner (read-only, stdlib only)."""
import ast, hashlib, json, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path.cwd()
EXCLUDED = {'venv', 'phases', 'architecture', 'models', '__pycache__', 'phase4f_gpu'}
EFFECTS = set("""create_async_engine create_engine async_sessionmaker sessionmaker connect create_connection execute exec_driver_sql commit rollback flush add delete unlink rmdir rmtree remove mkdir write_text write_bytes open Popen psql psql_value migrate_to_head upgrade downgrade run_migrations create_table drop_table create_index drop_index add_column drop_column alter_column replace_document_graph replace_document_structure dispose begin request delete_upload cleanup_new_file save_upload copy move database_exists create_database drop_database run urlopen ZipFile copyfile copytree postgres_available truncate delete_file save""".split())
DECORATOR_RULE = "matched callee inside a decorator expression -> 'decorator-annotation' (rule D-1)"
HTTP_RECEIVERS = {'client'}        # rule D-2: httpx/TestClient verbs; not DB or filesystem
ARRAY_RECEIVERS = {'np', 'numpy'}  # rule D-3
SAFETY_MODULES = ['backend/evaluation/isolation.py', 'backend/scripts/cleanup_path.py', 'backend/storage/database.py']

def dig(p, v):
    return p + '-' + hashlib.sha256(v.encode()).hexdigest()[:14]

def callee(n):
    f = n.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return '<dynamic>'

def receiver_root(n):
    if not isinstance(n.func, ast.Attribute):
        return None
    cur = n.func.value
    while isinstance(cur, ast.Attribute):
        cur = cur.value
    if isinstance(cur, ast.Name):
        return cur.id
    if isinstance(cur, ast.Call):
        c = cur.func
        if isinstance(c, ast.Name):
            return c.id
        if isinstance(c, ast.Attribute):
            return c.attr
        return '<call>'
    return None

def kindof(n, method):
    gen = any(isinstance(x, (ast.Yield, ast.YieldFrom)) for x in ast.walk(n))
    return ('async-' if isinstance(n, ast.AsyncFunctionDef) else '') + ('generator' if gen else ('method' if method else 'function'))

def walk_body(body):
    st = list(body)
    while st:
        x = st.pop()
        if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(x, ast.Call):
            yield x
        st.extend(ast.iter_child_nodes(x))

sources = []
for p in (ROOT / 'backend').rglob('*.py'):
    rel = p.relative_to(ROOT).as_posix()
    if EXCLUDED.intersection(Path(rel).parts):
        continue
    sources.append((p, rel))
sources.sort(key=lambda x: x[1])

hist_records = []; body_matches = []; module_matches = []; decorator_matches = []
all_defs = 0; files = []; safety = {}

class ModV(ast.NodeVisitor):
    def __init__(self, path):
        self.path = path
    def _decorators(self, n):
        for d in n.decorator_list:
            for c in ast.walk(d):
                if isinstance(c, ast.Call) and callee(c) in EFFECTS:
                    decorator_matches.append((self.path, c.lineno, callee(c), receiver_root(c)))
    def visit_ClassDef(self, n):
        self._decorators(n)
        for ch in n.body:
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.visit_FunctionDef(ch)
            else:
                self.visit(ch)
    def visit_FunctionDef(self, n):
        self._decorators(n)
        for d in list(n.args.defaults) + [x for x in n.args.kw_defaults if x is not None]:
            self.visit(d)
    visit_AsyncFunctionDef = visit_FunctionDef
    def visit_Lambda(self, n):
        for d in list(n.args.defaults) + [x for x in n.args.kw_defaults if x is not None]:
            self.visit(d)
    def visit_Call(self, n):
        nm = callee(n)
        if nm in EFFECTS:
            module_matches.append((self.path, n.lineno, nm, receiver_root(n)))
        self.generic_visit(n)

def first_doc_line(node):
    d = ast.get_docstring(node)
    return d.strip().split('\n')[0] if d else ''

def collect(scope, path, qual=(), in_class=False):
    for node in getattr(scope, 'body', []):
        if isinstance(node, ast.ClassDef):
            collect(node, path, qual + (node.name,), True)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            q = '.'.join(qual + (node.name,))
            k = kindof(node, in_class)
            eff = []
            for c in walk_body(node.body):
                nm = callee(c)
                if nm in EFFECTS:
                    body_matches.append((path, c.lineno, nm, receiver_root(c), q, node.lineno))
                    eff.append((c.lineno, nm))
            if eff:
                hist_records.append({'id': dig('C', path + '|' + q + '|' + str(node.lineno) + '|' + k), 'path': path, 'qual': q, 'line': node.lineno, 'kind': k})
            if path in SAFETY_MODULES:
                raises = set()
                for r in ast.walk(node):
                    if isinstance(r, ast.Raise) and isinstance(r.exc, ast.Call):
                        nm = callee(r.exc)
                        if nm.endswith('Error') or nm.endswith('Target'):
                            raises.add(nm)
                safety.setdefault(path, []).append({
                    'qual': q, 'line': node.lineno, 'end': node.end_lineno, 'kind': k,
                    'doc': first_doc_line(node),
                    'guarded_by': sorted({nm for _, nm in eff}),
                    'raises': sorted(raises),
                    'is_effect_matched': bool(eff),
                })
            collect(node, path, qual + (node.name,), in_class)

mains = []
for path, rel in sources:
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except (SyntaxError, UnicodeDecodeError):
        continue
    files.append(rel)
    all_defs += sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in ast.walk(tree))
    collect(tree, rel)
    for n in ast.walk(tree):
        if (isinstance(n, ast.If) and isinstance(n.test, ast.Compare) and isinstance(n.test.left, ast.Name)
                and n.test.left.id == '__name__'
                and any(isinstance(c, ast.Constant) and c.value == '__main__' for c in n.test.comparators)):
            mains.append([rel, n.lineno])
    mv = ModV(rel)
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            mv._decorators(n)
            for d in list(n.args.defaults) + [x for x in n.args.kw_defaults if x is not None]:
                mv.visit(d)
        else:
            mv.visit(n)

def classify(name, recv):
    if recv in HTTP_RECEIVERS:
        return 'http-request'
    if recv in ARRAY_RECEIVERS:
        return 'array-op'
    return 'operational-candidate'

body_by_class = defaultdict(list); module_by_class = defaultdict(list)
for pm in body_matches:
    body_by_class[classify(pm[2], pm[3])].append(pm)
for pm in module_matches:
    module_by_class[classify(pm[2], pm[3])].append(pm)

def sitecount(rows):
    return len({(r[0], r[1]) for r in rows})

recv_groups = defaultdict(int)
for _p, _l, nm, recv, _q, _d in body_matches:
    recv_groups[(nm, recv or '<name>')] += 1

entries = 0
mainfiles = {p for p, _l in mains}
for r in hist_records:
    nm = r['qual'].split('.')[-1]
    if nm.startswith('test_') and '/tests/' in r['path']:
        entries += 1
    elif nm in ('main', 'amain') and r['path'] in mainfiles:
        entries += 1

out = {
    'HISTORICAL_1_6R_declared_rule': {
        'files': len(files), 'all_callable_definitions': all_defs,
        'manifest_records': len(hist_records), 'unique_record_ids': len({r['id'] for r in hist_records}),
        'raw_matched_call_nodes_callable_body_only': len(body_matches),
        'unique_operation_sites_callable_body_only': sitecount(body_matches),
        'module_scope_sites': sitecount(module_matches) + sitecount(decorator_matches),
        'literal_main_blocks': len(mains), 'selected_entry_callables': entries,
    },
    'REVISED_semantic_classification': {
        'decorator_annotations': {'rule': DECORATOR_RULE, 'nodes': len(decorator_matches), 'sites': sitecount(decorator_matches),
                                  'where': [{'path': p, 'line': l, 'effect': n, 'receiver': r} for p, l, n, r in sorted(set(decorator_matches))]},
        'http_request_matches': {'rule': 'receiver root in ' + str(sorted(HTTP_RECEIVERS)),
                                 'nodes': len(module_by_class['http-request']) + len(body_by_class['http-request']),
                                 'where': sorted({(p, l, n) for p, l, n, r, q, d in body_by_class['http-request']})},
        'array_op_matches': {'rule': 'receiver root in ' + str(sorted(ARRAY_RECEIVERS)),
                             'nodes': len(module_by_class['array-op']) + len(body_by_class['array-op'])},
        'operational_candidate_body_nodes': len(body_by_class['operational-candidate']),
        'operational_candidate_body_sites': sitecount(body_by_class['operational-candidate']),
        'operational_candidate_module_nodes': len(module_by_class['operational-candidate']),
        'operational_candidate_module_sites': sitecount(module_by_class['operational-candidate']),
        'receiver_groups_body': {k[0] + ' <- ' + k[1]: v for k, v in sorted(recv_groups.items(), key=lambda x: -x[1])},
    },
    'SAFETY_HELPER_INVENTORY': safety,
    'modules_parsed': len(files),
}
Path(sys.argv[1]).write_text(json.dumps(out, indent=2, default=str), encoding='utf-8')
print(json.dumps(out['HISTORICAL_1_6R_declared_rule']))
print(json.dumps({k: v for k, v in out['REVISED_semantic_classification'].items() if not isinstance(v, dict)}))
```

## 10. Unresolved-findings register

| ID | Severity | Evidence | Impact | Next action |
|---|---|---|---|---|
| T-R01 | HIGH | I-02/I-03 are configuration-time only, but 21 static importers execute them and `get_db` (`storage/database.py:56-63`) opens connections for every DB route | The manifest's per-record authorization language still does not attach to the production engine/session factory | DATABASE_AGENT review of I-01…I-03; keep as inventory, do not treat as approved boundary |
| T-R02 | HIGH | `evaluation/isolation.py` has 18 headless helpers; all refusal paths (`assert_disposal_authorized` etc.) reject every constructed claim, incl. `DisposableDatabase`/lifecycle tests that were **not run** | Authorization exists in source but is unproven at runtime; nothing here establishes that destructive evaluation paths are blocked in practice | EVALUATION_AGENT + SECURITY_AGENT review; run nothing |
| T-R03 | MEDIUM | `cleanup_path.is_under` (18-34) then `path.unlink()` (`cleanup_orphan_uploads.py:210`); `filesystem_supports_relative_symlinks` returns `True` unconditionally (54-66) | TOCTOU window and a gate that cannot fail closed on unsupported filesystems | SECURITY_AGENT: define a handle-bound deletion contract; TEST_AGENT: propose a no-I/O regression test |
| T-R04 | MEDIUM | The 12 `client.delete(...)` sites (§7) were classified as `delete` effects under 1.6R | Test/runner HTTP calls inflate apparent destructive-operation counts unless rule D-2 is applied | COORDINATOR: apply D-2 in future inventories; TEST_AGENT: confirm no test relies on the old label |
| T-R05 | MEDIUM | Other generic receivers remain unresolved (`add <- seen` 8, `save <- doc`/`document` 14, `open <- fitz` 12, `run <- asyncio` 10) | `operational-candidate` is not a proof of a destructive operation | Leave open; classify per-receiver only with source evidence |
| T-R06 | LOW | `duplicate/overlapping` semantics: one module site may link several calls; per-file O-series site counts (1.6S U-05) still need relabelling in 1.6R | A reader can still mistake file-scoped lists for finding-scoped ones | COORDINATOR: carry the 1.6S wording corrections forward in the next inventory revision |
| T-R07 | LOW | Snapshot line endings differ (1.6S U-07): stored baselines are CRLF, fresh captures LF | Naive byte diffs misreport; comparisons must normalise | COORDINATOR: normalise line endings in future snapshots |
| T-R08 | INFO | Named specialist agents remain undispatchable in this runtime | Formal specialist sign-off still missing | Obtain the reviews where those roles can actually execute |

## 11. Git preservation evidence

- HEAD before this task: `6baaa2a0773df66e5fb26814afbe67647fb43435`; HEAD after: **unchanged** (same value).
- Baseline snapshot for this task captured to a **new** path `%TEMP%/step16t-status-before.txt`, `git status --porcelain=v1 --untracked-files=all`, **1145 rows** (which already includes the 1.6R and 1.6S reports). Existing snapshots `step16r-*` and `step16s-*` were **not** overwritten.
- The 1.6R report and its embedded scanner were **not modified**; the 1.6S report was **not modified**.
- Post-report comparison: see §12 (recorded after this file was written).

## 12. Post-report status comparison and decision

- Final `git status --porcelain=v1 --untracked-files=all`: **1146 rows**; normalised set difference against the 1145-row baseline is **one added path** — `?? backend/architecture/STEP1_6T_MANIFEST_CLASSIFICATION_AND_SAFETY_BOUNDARIES_2026-10-13.md` — with **0 removed** and **0 changed** rows. Tracking-status entries (non-untracked) are byte-identical between baseline and final.
- HEAD final: `6baaa2a0773df66e5fb26814afbe67647fb43435` (**UNCHANGED**).

**What remains blocked.**
1. **PostgreSQL execution: NO-GO.** No connection identity, role, TLS, least-privilege, or application-DB-denial evidence exists; the authorization helpers are source-verified only and the tests that exercise them were **NOT RUN**.
2. **Database lifecycle implementation: NOT AUTHORIZED.** Creation, provisioning, migration running, and cleanup remain out of scope; `assert_creation_authorized`, `assert_disposal_authorized`, and `assert_row_cleanup_authorized` continue to refuse by design.
3. **Specialist sign-off: OUTSTANDING.** T-R01, T-R02, T-R03 require DATABASE/SECURITY/EVALUATION/TEST review in a runtime that can execute those roles.
4. **Inventory completeness: PARTIAL.** The revised inventory distinguishes callables, module-scope execution, operations, safety helpers, syntactic non-operations, and caller/callee boundaries far better than 1.6R, but dynamic/aliased targets and non-Python boundaries remain unresolved (§9).

**Recommended next bounded task.** Obtain the named specialist reviews (DATABASE for T-R01, EVALUATION+SECURITY for T-R02/T-R03, TEST for T-R03/T-R04, VERIFIER as independent challenger) and have the COORDINATOR apply the 1.6S wording corrections (T-R06) and snapshot normalisation (T-R07) in the next inventory revision — before any implementation or PostgreSQL work.

---

Verification note: this report was produced with read-only static analysis only. The historical and revised counts were produced by the embedded scanner run with `backend/venv/Scripts/python.exe` from the repository root; the Git comparisons were run as plain commands with their exit status read directly. Every factual claim cites a source file and line range. Unsafe or unverifiable steps are marked NOT RUN with the reason.
