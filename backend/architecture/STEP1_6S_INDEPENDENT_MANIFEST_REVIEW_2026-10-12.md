# STEP 1.6S — Independent Review of the Step 1.6R Canonical Callable Manifest

Date: 2026-10-12
Reviewer role: COORDINATOR (owns this report). Role-scoped independent source checks were executed by generic read-only runtime subagents; the project-defined specialist agent contracts (`SECURITY_AGENT`, `DATABASE_AGENT`, `EVALUATION_AGENT`, `TEST_AGENT`, `VERIFIER`) did **not** execute as named agents — see §1.

Reviewed artifact: `backend/architecture/STEP1_6R_CANONICAL_CALLABLE_MANIFEST_2026-10-12.md` (1732 lines) and its embedded scanner.

**Headline block.** The seven 1.6R counts were independently reproduced **exactly**, and the 13 O-2 / 5 O-3 call-site mappings were reproduced with identical record IDs, site IDs, qualified names, and line numbers. The embedded scanner is byte-identical to the file that produced the artifacts. Verdict: the inventory is **APPROVED as a static audit artifact**. It is **not** approved as a safety or completeness proof, and no implementation or PostgreSQL execution is authorized. PostgreSQL: **NO-GO**.

## 1. Reviewer participation (actual execution)

The runtime exposed only generic subagents (`code-searcher`, `file-picker`, non-terminal workers). The project's named specialist agent types defined in `agents/*.md` are **not dispatchable targets** in this runtime; no mechanism exists to instantiate a `SECURITY_AGENT` or `DATABASE_AGENT` process. Accordingly:

| Role | Attempted? | Actually executed | Evidence produced |
|---|---|---|---|
| COORDINATOR | n/a (self) | Yes | Count/ID reimplementation, crosswalk, scanner-identity diff, Git comparison, this report |
| SECURITY (named) | Yes — unavailable | **No** | — |
| DATABASE (named) | Yes — unavailable | **No** | — |
| EVALUATION (named) | Yes — unavailable | **No** | — |
| TEST (named) | Yes — unavailable | **No** | — |
| VERIFIER (named) | Yes — unavailable | **No** | — |
| Generic subagent `code-searcher` ×5 (SECURITY-scoped, DATABASE-scoped, EVALUATION-scoped, crosswalk-scoped, VERIFIER-scoped query batches) | Yes | **Yes** (5 agents, read-only ripgrep) | Line-referenced matches for destructive filesystem/DB calls, guards/refusals, engine/session creation, migration revisions, O-2/O-3 call sites, `__main__` guards |
| Generic subagent `file-picker` | No | No | Not needed; file inventory already known |

**Honest attribution.** No finding below is attributed to a named specialist. The named specialist reviews remain **OUTSTANDING**, so the 1.6R §2 statement ("no specialist dispatch mechanism is exposed") is corroborated by this task's own dispatch attempt. Independently, the generic subagents did perform real, non-simulated source inspection, and the COORDINATOR performed independent deterministic reimplementation. Nothing here is a specialist sign-off.

## 2. Review method (reproducible, read-only)

All checks were static and read-only. No application module was imported; no test, fixture, runner, E2E flow, migration, or cleanup script was executed; no database or socket was contacted; no SQL was issued; no file under version control was modified.

1. **Independent reimplementation.** A new scanner (`%TEMP%/step16s_scan.py`) was written from the *declared* rules in 1.6R §4–§5 (roots, exclusions, 57-name effect vocabulary, identity = `path|qualname|line|kind`, `C-`/`S-` = SHA-256 prefix 14 hex, body traversal stopping at nested callables/classes/lambdas, module-scope visitor including decorators/defaults) and run with `backend/venv/Scripts/python.exe` from the repository root. It emitted only to new `%TEMP%` paths. It is a re-derivation, not a copy-and-run: counts were compared, not asserted.
2. **Scanner identity diff.** The `python` fenced block in 1.6R §6 was extracted and compared to `%TEMP%/step16r_scan.py` (the file that produced `/tmp/step16r-scan.json`), after CRLF normalization.
3. **Crosswalk re-derivation.** A second script recomputed the containing callable record ID and operation-site ID for every direct `replace_document_graph` / `replace_document_structure` call under `backend/tests/integration/graph/`, and listed each call's containing qualified name and line.
4. **Section reconciliation.** The report's own tables were re-counted (`^\| C-`, `^\| S-`, `^\| M-`, `^\| E-`, `^\| O-2 |`, `^\| O-3 |`) and per-section attributed with `awk`, then compared against the headline numbers.
5. **O-series site semantics.** A third script recomputed, for each O-1…O-9 mapped file family, the number of unique matched `(path,line)` sites, to test whether the §10 "sites" column is finding-scoped or file-scoped.
6. **Git preservation.** A fresh baseline was captured to a **new** path (`%TEMP%/step16s-status-before.txt`) with `git status --porcelain=v1 --untracked-files=all`; the pre-existing 1.6R snapshots were not overwritten. Baseline comparison was performed after stripping CR so line-ending differences would not masquerade as content differences.

**Method limitations.** (a) The embedded scanner was **not executed as-is**, because it writes `/tmp/step16r-scan.json`, a pre-existing artifact this task must not overwrite; identity was established textually and the counts by independent reimplementation instead. (b) The reimplementation shares the *declared* rule set with 1.6R, so it tests reproducibility of the recipe, not the recipe's adequacy; adequacy is addressed in §5 and §8. (c) The generic subagents used ripgrep with a working directory that sometimes surfaced `backend/phases/**` and packaged site-packages; those are outside the 1.6R scan roots and were ignored in the findings.

## 3. Claim-by-claim findings

| # | 1.6R claim | Disposition | Basis |
|---|---|---|---|
| C1 | Roots = `backend/**/*.py`; exclusions `venv, phases, architecture, models, __pycache__, phase4f_gpu` | **PASS** | Reimplementation produced 226 files; every excluded component exists and was skipped; no `architecture/**` or `phases/**` file entered the set. |
| C2 | Identity rule `path\|qualname\|line\|kind`; ID = `C-`+sha256[:14] | **PASS** | Reproduced `C-27428487fc56bd` = `backend/auth/dependencies.py::get_current_user`@17 `async-function`; all 18 §11 IDs matched exactly (see C12). |
| C3 | Effect-match rule: direct `Name.id`/`Attribute.attr` callee in the 57-name vocabulary; traversal stops at nested callables/classes/lambdas | **PASS** | Vocabulary size confirmed 57; identical record/effect sets reproduced. |
| C4 | 969 raw matched AST call nodes over 929 unique `(path,start-line)` sites | **PASS (with wording caveat)** | Both reproduced. Caveat: the rule counts only calls lexically inside callable bodies; module-scope matched calls are excluded (see U-04). |
| C5 | 17 module/class-scope execution sites | **PASS** | The 17 §9 `M-` sites were reproduced in identical path:line order (including `backend/storage/database.py:43,49`, `backend/scripts/start_server.py:62,64`). |
| C6 | 27 literal `__main__` blocks | **PASS** | 27 guards reproduced across 27 distinct files (identical file list). |
| C7 | 103 selected entry callables | **PASS** | Reproduced 82 effect-bearing `test_*` callables under `backend/tests/` + 21 `main`/`amain` in main-guard files = 103; §9 contains exactly 103 `C-` entry rows plus 27 `E-` main-block rows. |
| C8 | 226 files parsed, 0 syntax errors, 2345 `def`/`async def` definitions | **PASS** | All three reproduced exactly. |
| C9 | 348 unique effect-matched callable records, IDs unique | **PASS** | 348 records and 348 unique `C-` IDs; §7 has exactly 348 rows. |
| C10 | O-1–O-9 crosswalk dispositions | **PASS (with semantics caveat)** | Every O row's callable and site counts reproduce exactly (callables 5/10/6/5/1/6/1/7/4; sites 10/23/10/9/3/23/6/92/8). Caveat: the §10 "sites" column is file-scoped, not finding-scoped (U-05). |
| C11 | P01–P20 crosswalk dispositions | **PARTIAL** | Spot-checked families reproduce (`tests/fixtures/integration_db.py` = 10 records = P03/P04/P06 lists; `tests/fixtures/e2e_config.py` = 3 = P05/P17 subset). P01/P02 are `UNRESOLVED` — and this is substantively correct: `backend/evaluation/isolation.py` yields **0** records (U-03). P18–P20 are broad path-prefix families and are not record-exact by construction (self-disclosed in §10). |
| C12 | 13 O-2 and 5 O-3 direct test-call-site mappings | **PASS** | All 18 rows reproduced identically — same containing qualified names, line numbers, caller record IDs and site IDs (e.g. `test_graph_rag_flow.py:52` → `C-36121bbb851344`/`S-0c3b22d8855edb`; `test_graph_security.py:59` → `C-504b5378395d32`/`S-1013f6e6a591cf`). |
| C13 | All eight scoped migration versions parsed | **PASS** | `000`–`007` present; reimplementation produced 16 `upgrade`/`downgrade` records plus 4 `backend/migrations/env.py` records = 20 migration-family records, all in §7. |
| C14 | Embedded scanner self-contained and reproducible | **PASS** | Embedded block (113 non-blank lines) is **identical** to `%TEMP%/step16r_scan.py`; stdlib-only (`ast, hashlib, json, pathlib, collections`); independent reimplementation converged on all seven counts and sampled IDs/effects. |
| C15 | Git baseline statement (§14) | **PASS** | HEAD unchanged; normalized status diff = baseline **+ exactly one** new untracked path (the 1.6R report). See §9. |
| C16 | Reviewer-participation statement (§2) | **PASS** | Corroborated: no named specialist dispatch mechanism is exposed in this runtime. |
| C17 | "PostgreSQL NO-GO"; no runtime/DB operations performed by 1.6R | **PASS / NOT VERIFIABLE POSITIVELY** | Consistent with all observable evidence; absence of execution cannot be positively proven from static artifacts, and this review likewise executed nothing. |

## 4. Count reconciliation

Independent values are from the reimplementation in §2.1 (declared-rule scope). Differences: **none**.

| Claimed count | 1.6R | Independent | Disposition |
|---|---:|---:|---|
| Files parsed | 226 | 226 | PASS |
| Syntax errors | 0 | 0 | PASS |
| All callable definitions | 2,345 | 2,345 | PASS |
| Effect-matched callable records | 348 | 348 | PASS |
| — unique record IDs | 348 | 348 | PASS |
| Raw matched AST call nodes | 969 | 969 | PASS |
| Unique operation sites | 929 | 929 | PASS |
| Module/class-scope sites | 17 | 17 | PASS |
| Literal `__main__` blocks | 27 | 27 | PASS |
| Selected entry callables | 103 | 103 (82 test + 21 main) | PASS |
| O-2 direct test call sites | 13 | 13 | PASS |
| O-3 direct test call sites | 5 | 5 | PASS |
| Scoped migration versions | 8 | 8 (`000`–`007`) | PASS |

Sampled identity spot-checks: `C-27428487fc56bd` (`get_current_user`, effect `execute@45`), site `S-46402a36274f4a` (`backend/auth/dependencies.py|45`) — both matched.

## 5. Scanner assessment

**Strengths.** Deterministic; stdlib-only; parse-only (no imports); excludes vendored/archived roots; identity rule is collision-checked (`SystemExit` on ID/site collision); separate namespaces for callables (`C-`) and sites (`S-`); record range, effects, guard-like calls, and caller candidates are emitted per record; module-scope effects and literal main guards are accounted for as distinct units; the document embeds the exact scanner used.

**Correctness risks and ambiguities (evidence-backed).**

1. **Decorator false positives.** `@router.delete("/{document_id}", ...)` at `backend/documents/routes.py:600` is recorded as module site `M-da4eab41f6483c` with matched effect name `delete`. This is FastAPI route registration, not a data deletion. Confirmed by reading `backend/documents/routes.py:595-601`. Because records only scan callable *bodies*, this does not corrupt the 348 records, but it does inject a non-effect into the module-site table (§9) and inflates semantic effect counts there. (U-02)
2. **Generic-name false positives generally.** `copy`, `remove`, `add`, `run`, `open`, `save`, `move`, `begin`, `delete` match unrelated methods (e.g. `dict.copy()`, `list.remove()`, `asyncio.run(main())`). 1.6R §12 item 1 already discloses this; the review confirms it is real and should remain prominent.
3. **Module-scope effects are structurally weaker.** Module/class-scope matched calls (§9) are reported with effect names and no owner, containment requirement, or input-provenance column, unlike §7 records. The production engine and session factory (`backend/storage/database.py:43,49`) live only here. (U-01)
4. **Guard detection is a Call-node substring heuristic.** Guards are detected only when a `Call` callee name contains `assert|authoriz|guard|refuse|validat|isolation|proof|disposable|target`. Guards expressed as `raise SomeError(...)` are not "guard-like calls"; statements, type checks, and early returns are invisible. The report's "No syntactic guard-like call found; not proof that no guard exists" wording is therefore appropriate, and is re-affirmed here.
5. **Same-simple-name caller resolution.** Caller/test references are lexical name matches with an ambiguity count; imports, aliases, rebinding, monkeypatching, and dynamic dispatch are unresolved (self-disclosed). Confirmed by the presence of `ambiguous_targets` counts >1 for common names.
6. **Non-Python execution is out of scope.** `Dockerfile.frontend`, `compose.yaml`, shell entrypoints, and `backend/scripts/start_server.py`'s module-body process spawn are only partially represented (the latter as module sites `M-74f45332c68fd2`, `M-86ce143e0d0f59`). Self-disclosed in §4/§12.
7. **Reproducibility friction.** The embedded scanner's output path `/tmp/step16r-scan.json` is fixed and would overwrite the pre-existing artifact if re-run; the report instructs saving it as a temp file, but the hard-coded write target is a mild reproducibility/portability hazard on Windows (drive-root `/tmp`).

**Verdict on the scanner:** the declared counting recipe is reproducible and internally consistent; it is not a semantic effect classifier and 1.6R does not claim it is.

## 6. Crosswalk assessment

**O-1–O-9.** All nine are `CONFIRMED` with source-located references. Independent per-file site counts match the §10 site counts exactly: O-1 10, O-2 23, O-3 10, O-4 9, O-5 3, O-6 23, O-7 6, O-8 92, O-9 8. Callable counts also match (5/10/6/5/1/6/1/7/4). **Caveat:** the §10 "sites" column enumerates *every* matched operation site in the finding's mapped file(s), not only the finding's target call sites — the interpretation is established by exact per-file totals above, and the finding-specific sites are the §11 table. The §10 prose says only "sites:", so this should be labeled.

**O-2 / O-3 (§11).** Independently reproduced 13 O-2 and 5 O-3 rows, matching on all six columns. Representative confirmations:

- `backend/tests/integration/graph/test_graph_ingestion.py:106` and `:107` → both rows correctly share caller `C-96caef1c8188d9` (`TestRebuild.test_rebuild_replaces_rather_than_appends`) with distinct sites `S-5ff802ced12f46` / `S-2eda2e718cc802`.
- `backend/tests/integration/graph/test_graph_rag_flow.py::_seed_graph:52` → `C-36121bbb851344` / `S-0c3b22d8855edb` (a seed helper, not a test body — the report's distinction of "containing test callable" from "target callable" is honored).
- `backend/tests/integration/graph/test_graph_security.py::_foreign_document:59` → `C-504b5378395d32` / `S-1013f6e6a591cf`.
- O-3 `test_table_evidence_bands.py:506` and `:555` are genuine test-method-level calls, distinct from the `_seed_document:94` helper.

The direct-call set is confirmed complete for `backend/tests/integration/graph/` (13 + 5). Note the wider non-graph test set also contains further direct calls (26 `replace_document_graph` and 8 `replace_document_structure` sites across `backend/tests/`), which the manifest represents as records but does not enumerate row-by-row; §11 is explicitly scoped to the graph directory.

**P01–P20.** Group-level, path-prefix families rather than record-exact mappings (self-disclosed). Spot-checks reproduce: `tests/fixtures/integration_db.py` → 10 records (P03/P04/P06), `tests/fixtures/e2e_config.py` → 3 records (P05/P17 subset). P01/P02 = `UNRESOLVED` is substantively correct and points at a real gap (U-03).

## 7. Safety review — omission paths that could bypass authorization

The manifest is a browser of effect-bearing callables, not a control map. The following omissions are the ones that matter for authorization and must be closed by the owning specialist reviews before any controlled PostgreSQL work.

- **S-1 (HIGH) — production engine/session factory have no callable record.** `backend/storage/database.py` yields exactly **one** §7 record (`get_db`). The module-scope `create_async_engine` (`:43`) and `async_sessionmaker` (`:49`) appear only as module sites `M-6d47949c82b557` / `M-f1c199296ceb22`, which carry no owner or containment requirement. The manifest's per-record authorization language therefore does not attach to the object that opens every production connection. Owner: DATABASE_AGENT.
- **S-2 (MEDIUM) — the evaluation guard module is absent from the record set.** `backend/evaluation/isolation.py` (523 lines, owns target resolution / application-DB refusal / disposal authority) produces **0** records because it performs no vocabulary-matched calls. P01/P02 are `UNRESOLVED` for the same reason. No node in §7 represents the module that decides whether an evaluation target is safe. Owner: EVALUATION_AGENT + SECURITY_AGENT.
- **S-3 (MEDIUM) — non-matching guard helpers are invisible.** `backend/scripts/cleanup_path.py` (symlink-escape / upload-root resolution guards, lines 38–57) yields 0 records, while its caller `backend/scripts/cleanup_orphan_uploads.py::run_sweep` (`rmdir`, `unlink`) is a record (O-9). The guard that constrains the destructive path is not enumerated, so §7 cannot show that the destructive record is mediated. Owner: SECURITY_AGENT.
- **S-4 (MEDIUM) — startup/process boundary is module-scope only.** `backend/scripts/start_server.py` records only `_fetch_health` (`urlopen`); the module body itself spawns the server (`Popen` at `:64`) and deletes `__pycache__` (`rmtree` at `:62`), captured only as module sites with no owner. Startup ordering, which determines whether the migration path (`backend/main.py::_run_migrations`) runs before requests are served, has no callable-level record tying it to an authorization requirement. Owner: BACKEND_AGENT/DATABASE_AGENT.
- **S-5 (LOW) — test-only unscoped raw SQL is represented but not separable by risk.** `backend/tests/integration/rag/test_real_e2e_validation.py:129-131` issues unscoped `DELETE FROM document_chunks` / `documents` / `users`; the containing callables are records (test family, 175 §7 rows), and the isolation-guard tests that constrain them were **not run**. Their static presence is correct and honest; whether the guard actually precedes the delete at runtime remains unproven. Owner: TEST_AGENT + EVALUATION_AGENT.

No omission found that would let a *production* request path delete or drop database objects without an authorization check that the manifest claims to have enumerated — because the manifest does not claim to have enumerated authorization at all. That limitation, not a specific missing row, is the governing safety conclusion.

## 8. Unresolved findings

| ID | Severity | Evidence | Impact | Recommended next action |
|---|---|---|---|---|
| U-01 / S-1 | HIGH | `backend/storage/database.py:43,49` are module sites `M-6d47949c82b557`,`M-f1c199296ceb22`; §7 has 1 record for that file | Production engine creation carries no owner/containment requirement | DATABASE_AGENT: classify module-scope engine/session creation and add a record-level requirement |
| U-02 | MEDIUM | `backend/documents/routes.py:600` `@router.delete(...)` → module site effect `delete` | Module-site effect names overstate DB/filesystem effects; reader could mistake route registration for deletion | COORDINATOR: label the §9 column as "matched callee names (may be non-effects)" and cite this example |
| U-03 / S-2 | MEDIUM | 0 §7 rows for `backend/evaluation/isolation.py`; §10 P01/P02 `UNRESOLVED` | The evaluation authorization module is not represented in the manifest | EVALUATION_AGENT + SECURITY_AGENT: add a non-vocabulary record class for guard-only safety modules |
| U-04 | LOW | Scanner builds `site_map` only from callable-body calls; §5 "raw matched call nodes" = 969 | 969/929 exclude the 17 module-scope matched call nodes; totals can be misread as all matched calls | COORDINATOR: state the exclusion explicitly in §5/§8 |
| U-05 | LOW | §10 O-site counts equal per-file matched-site totals (10/23/10/9/3/23/6/92/8) | §10 "sites" column is file-scoped, not finding-scoped; can be mistaken for the finding's own call sites | COORDINATOR: relabel the column and point to §11 for finding-specific sites |
| U-06 | LOW | Guard detection matches only `Call` callee substrings | "No syntactic guard-like call found" cannot see `raise`, early returns, or type checks | Informational; keep the existing disclaimer |
| U-07 | LOW | `%TEMP%/step16r-status-before.txt` uses CRLF; a fresh capture uses LF | A naive byte diff of baselines reports every line changed (observed here: 2287 diff lines) though the content differs by exactly one path | COORDINATOR: normalize line endings in future snapshots/comparisons |
| U-08 | INFO | Named specialist agents are not dispatchable in this runtime | Formal SECURITY/DATABASE/EVALUATION/TEST/VERIFIER sign-off is still missing | Obtain the reviews through a runtime that can execute those roles |

Nothing above is a fabrication risk in the 1.6R counts: the counts themselves are reproducible. The findings concern interpretation, labeling, and the boundary of what the manifest represents.

## 9. Git preservation check

- HEAD before: `6baaa2a0773df66e5fb26814afbe67647fb43435`. HEAD after all review work: **same**.
- Fresh baseline captured to a **new** path `%TEMP%/step16s-status-before.txt` (1144 rows, `--untracked-files=all`). The 1.6R snapshots `step16r-status-before.txt` (1143) / `step16r-status-after.txt` (1144) were **not** overwritten.
- Normalized (`tr -d '\r'`) set comparison of the 1.6R baseline vs the fresh baseline yields **exactly one** added row: `?? backend/architecture/STEP1_6R_CANONICAL_CALLABLE_MANIFEST_2026-10-12.md`; removed/changed rows: 0. This independently confirms 1.6R §14's own claim for the state it was written in.
- Post-report comparison is recorded in §10.
- No reset/revert/stash/clean/stage/commit/delete occurred. No `.env` content was read. No secret values were read.

## 10. Final status comparison (post-report)

Recorded after this report was written (see closing note):

- Fresh baseline: **1144** rows.
- Final status: **1145** rows; the sole added path is `?? backend/architecture/STEP1_6S_INDEPENDENT_MANIFEST_REVIEW_2026-10-12.md`; removed/changed baseline rows: **0**.
- HEAD final = `6baaa2a0773df66e5fb26814afbe67647fb43435` (**UNCHANGED**).

## 11. Final decision

1. **Static audit artifact:** the Step 1.6R inventory is **APPROVED for use as a static audit artifact**. All seven headline counts (2,345 / 348 / 969 / 929 / 17 / 27 / 103), the eight-migration set, and the 13 O-2 + 5 O-3 call-site mappings reproduce exactly under the declared rules; the embedded scanner is identical to the file that produced the artifacts; the Git baseline statement holds.
2. **Completeness/safety proof:** **NOT APPROVED**. The manifest omits the production engine/session factory at callable level (U-01), the evaluation authorization module (U-03), and non-matching guard helpers (S-3), and its effect vocabulary produces known false positives (U-02).
3. **Implementation authorization:** **NONE**. No source, test, migration, configuration, or safety guard was changed by this task, and none is authorized by it.
4. **PostgreSQL execution:** **NO-GO.** No specialist review executed; no runtime identity, role, TLS, least-privilege, or application-DB-denial evidence exists; the safety gaps above are open. Nothing here establishes PostgreSQL safety.

**Recommended next bounded task.** Obtain the named specialist reviews (DATABASE_AGENT for U-01/S-1/S-4, EVALUATION_AGENT for U-03/S-2, SECURITY_AGENT for S-2/S-3, TEST_AGENT for S-5, VERIFIER as independent challenger) in a runtime that can actually execute those roles, and have the COORDINATOR apply the U-02/U-04/U-05/U-07 labeling and snapshot-normalization corrections to the 1.6R document. Do not begin implementation or PostgreSQL testing until those reviews are attributed and the HIGH-severity gap U-01 is closed.

---

Verification note: this report was produced with read-only static analysis only. The seven counts were reproduced by an independent reimplementation run with `backend/venv/Scripts/python.exe` from the repository root; the scanner-identity diff, section re-counts, O-series site-count recomputation, and Git baseline comparison were run as plain commands with their exit status read directly.
