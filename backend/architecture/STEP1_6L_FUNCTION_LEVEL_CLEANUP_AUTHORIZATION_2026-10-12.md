# Step 1.6L — Function-Level Cleanup Authorization

Date: 2026-10-12
Verdict: **PARTIALLY COMPLETE. PostgreSQL verification remains NO-GO.**

The eight reported helpers and four alternate execution boundaries now refuse before resource access, database-dependent imports, session creation or SQL. No operational lifecycle authority or actual connected-target verification exists. Default refusal addresses the inspected direct-call bypasses, but it does not establish a working authorized lifecycle or PostgreSQL runtime safety.

## 1. Agents, ownership and acceptance

No specialist-dispatch tool exists in this runtime. Only Coordinator executed work; no EVALUATION_AGENT, DATABASE_AGENT, SECURITY_AGENT, TEST_AGENT or VERIFIER independent execution is claimed. Independent specialist reviews remain outstanding.

Before source edits the ownership conflict was raised. The user selected **Authorize a task-specific contract amendment**. `agents/coordinator.md` now permits scoped Step 1.6L evaluation-boundary and database-free test edits, without authorizing positive lifecycles or any database access. Implementation normally owned by EVALUATION_AGENT was performed by Coordinator under that explicit exception, not by a dispatched specialist.

Acceptance: all eight helpers and the table engine-taking path must be locally blocked; preserve existing signatures, scoping and order; do not accept names, environment or freely constructible proof data; retain entry guards/application isolation; test decisions without invoking cleanup or runner bodies; compile; save exact-path evidence; no destructive operation. Actual engine/server identity and positive lifecycle behavior must remain explicitly unverified.

## 2. Baseline and current-state review

Initial HEAD: `6baaa2a0773df66e5fb26814afbe67647fb43435`.
Initial ordinary status: 384 entries. Initial expanded status: 1136 paths. Complete initial listing is appended below. Existing Step 1.6K section 9, central contract, fixture/E2E boundaries and actual helper definitions were reviewed before implementation.

Current proof data is inert; issuance and lifecycle closure refuse. No registry can issue valid authorization. URL matching cannot prove actual connected identity. Step 1.6K correctly identified unguarded cleanup functions taking sessions, despite guarded main entry points. No database or `.env` was read to establish this baseline.

## 3. Verified inventory and caller coverage

Paths below are under `backend/evaluation/experiments/`. Definition line numbers are baseline lines; complete final call expressions and line numbers are appended.

| File | Helper / baseline line | Production callers verified |
| --- | --- | --- |
| `run_phase3d_upload_integration.py` | `cleanup_harness_rows`, 118 | main final cleanup |
| `run_phase3d_evaluation.py` | `cleanup_harness_rows`, 549 | main previous-user and final cleanup |
| `run_phase3e_integration.py` | `cleanup_harness_rows`, 83 | temporary-user and final cleanup |
| `run_phase3e_validation.py` | `cleanup_harness_rows`, 82 | temporary-user and final cleanup |
| `run_phase3f_evaluation.py` | `cleanup_harness_rows`, 718 | main previous-user and final cleanup |
| `run_phase4b_evaluation.py` | `cleanup_harness_rows`, 698 | main previous-user and final cleanup |
| `run_dual_path_ablation.py` | `_delete_user_data`, 861 | ablation main and all three structure run_once functions, before/after evaluation |
| `run_table_evidence_measurement.py` | `teardown`, 479 | run_once before/after measurement |

Table `run_once(engine, ...)` (baseline 640) accepted any supplied engine and opened sessions before teardown. It now refuses at entry. Also blocked structure element `run_once` (1638), RRF `run_once` (954), confirmation `run_once` (699): they used global engines/session factories and could reach direct deletes apart from the shared helper. Main/amain entry guards remain unchanged.

AST inventory scanned Python under `backend/evaluation` and `backend/tests`; final caller listing includes the six cleanup-scope test files. Static name matching cannot discover arbitrary dynamic/reflection callers. Function-local refusal applies to ordinary direct/aliased calls with intact code regardless of how the caller reached the function.

## 4. Implementation and binding guarantees

New pure contract:

```python
assert_cleanup_execution_authorized(resource: object, *, operation: str,
                                    proof: DisposalProof | None = None) -> None
```

It always raises `UnsafeEvaluationTarget`. It does not inspect the resource, proof, environment, configuration, URL, engine or session attributes; even property access on caller-controlled objects could perform I/O. Every affected boundary imports this contract from `evaluation.isolation` and calls it as the first executable expression after that import (and optional docstring). All original body statements remain afterward and unreachable under the intact contract.

The resource passed is the actual helper argument `db`, actual table argument `engine`, or structure-runner global `engine`. No resource is accepted, so mismatch, substitution, stale proof, reuse or later configuration changes cannot enable the inspected paths. **No positive authorization is bound to an actual connection:** this is universal refusal, not validated server identity. A future permissive implementation requires separately approved authoritative lifecycle/connection binding and review of every retained body. Simply replacing this raise with URL or registry checks is insufficient.

Existing application-name rejection and URL/engine guard functions are unchanged. The new refusal additionally protects any supplied resource without resolving the application configuration. Existing proof issuance, creation and closure remain blocked. No successful lifecycle/revocation/drop behavior is claimed.

Security boundary limitation: Python guards are not a sandbox against arbitrary same-process code that monkeypatches functions or directly submits SQL. Inspection found no remaining ordinary direct-call bypass in these eight helpers/four alternate boundaries. This does not certify every arbitrary SQL function or out-of-scope operational cleanup script in the repository.

## 5. Files changed

- `agents/coordinator.md`: user-approved task-only ownership exception.
- `backend/evaluation/isolation.py`: refusal contract above.
- Eight helper-containing experiment files listed in section 3.
- `backend/evaluation/experiments/run_structure_element_measurement.py`.
- `backend/evaluation/experiments/run_structure_rrf_calibration.py`.
- `backend/evaluation/experiments/run_structure_confirmation.py`.
- `backend/tests/unit/evaluation/test_function_cleanup_authorization.py`: new tests.
- This new append-only evidence report.

Total: 15 intended files (12 evaluation source, one new test, one contract, one report). Table source contains two guarded functions. No existing test assertion was changed.

## 6. Test review, exact command and observed evidence

Reviewed candidate test imports, fixture/setup/teardown and called code. New tests read runner AST only, confirm the gate is first and passes the actual named resource, then compile only that exact authorization expression into a pure decision function. They do NOT import or invoke cleanup/runner functions or execute retained bodies. Poison resources reject all attribute access; sockets/subprocess and application resolution are patched to fail. Tests exercise each of 12 boundaries, constructed stale/cross-target/reused claims, invalid/missing authorization and configuration substitution. These are decision/source tests, not full direct cleanup invocation or runtime DB verification.

Existing selected tests use pure guards, source reads, callback metric calculations and poison/stubbed structure binding. Structure binding-order tests replace disposal only in controlled stubs; the separate unauthorized test restores the actual refusal. This is order evidence, not proof of successful authorization. No SQLite fixture was requested.

Exact command, backend cwd:

```bash
PYTHONDONTWRITEBYTECODE=1 ./venv/Scripts/python.exe -B -m pytest -q tests/unit/evaluation/test_function_cleanup_authorization.py tests/unit/evaluation/test_lifecycle_authorization.py tests/unit/evaluation/test_disposable_database_authorization.py tests/unit/evaluation/test_disposal_authorization_contract.py tests/unit/evaluation/test_phase3_runner_target_order.py tests/unit/evaluation/test_isolation_guard_identity.py tests/unit/evaluation/test_metrics.py tests/unit/evaluation/test_unsupported_answer_denominator.py tests/unit/evaluation/test_structure_runner_guard_order.py -p no:cacheprovider > /tmp/s16l_tests.txt 2>&1
result=$?
cat /tmp/s16l_tests.txt
printf '\npytest_exit=%s\n' "$result"
exit "$result"
```

Observed: **299 passed, 1 warning in 1.92s; exit 0**. This includes 29 new tests. Pytest-asyncio reports unset default loop scope and deprecated custom event-loop fixture; neither was suppressed. No failing test was skipped, weakened or repaired in this task.

Compilation used `./backend/venv/Scripts/python.exe -B -` from root, `py_compile.compile(..., cfile=external_temp_path, doraise=True)` for each of the 12 changed evaluation source paths plus the new test. Output bytecode destination: Git Bash `/tmp/s16l_compile`, converted for Windows Python using `cygpath -w`. **13 files compiled; exit 0.** No source file was imported/executed by compilation.

Static verification compared current ASTs with pre-edit content snapshots. For all 12 affected function bodies, removing just the newly inserted import and guard leaves an identical original body AST. Scoping/order/signatures and original statements are preserved. Full content diff for pre-existing untracked files is appended; Git diff alone would omit them.

## 7. Deliberately unrun and remaining limitations

NOT RUN: cleanup/creation/drop functions; runner main/amain/run_once; provisioning/integration fixtures; migrations; E2E; any PostgreSQL or SQLite connection; filesystem cleanup; tests that invoke these paths or resolve real `.env` settings. No destructive database or filesystem operation occurred. No reset, clean, stash, revert, stage, commit or push occurred.

Existing six SQLite cleanup-scope files intentionally assert successful deletion. Those behaviors now conflict with default refusal. They were not run, bypassed or weakened; an approved future working lifecycle/testing design is needed before positive cleanup expectations are valid. The whole evaluation directory is not claimed passing. No frontend build/static typechecker was run for these scoped Python changes; syntax compilation is not typechecking.

No authorized operational lifecycle, actual server identity binding, successful closure or positive cleanup/drop evidence exists. Independent review is outstanding. Out-of-scope `cleanup_smoke.py`, `cleanup_orphan_uploads.py` and retained filesystem cleanup are not declared safe. No performance requirement or measured speedup is claimed.

## 8. Final Git/evidence verification

Initial/final full status listings and their path-level comparison follow. Matching status counts do not prove content preservation: edited evaluation files were already untracked. Pre-edit byte snapshots establish the actual source diffs below; unaffected sampled experiment sources remain byte-identical. The new test and report add expanded paths. The Coordinator contract is also pre-existing untracked and its exact amendment is documented in section 1.

Final HEAD remains the baseline. Worktree content was not reset or discarded. Scope verification distinguishes changed contents from unchanged status labels; broad preservation of every pre-existing untracked file is not inferred from status alone.

**PARTIALLY COMPLETE: inspected direct-call boundaries are safely blocked; operational lifecycle and independent verification remain unavailable. PostgreSQL verification remains NO-GO.**

## 9. Evidence appendices

### 9.1 Complete initial status/path listing

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

### 9.2 Complete final status/path listing

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

### 9.3 Path-level comparison

```text
--- initial expanded status
+++ final expanded status
@@ -469,6 +469,7 @@
 ?? backend/architecture/STEP1_6I_UNIFIED_DESTRUCTIVE_TARGET_AUTHORIZATION_2026-10-11.md
 ?? backend/architecture/STEP1_6J_FAIL_CLOSED_DESTRUCTIVE_EXECUTION_2026-10-12.md
 ?? backend/architecture/STEP1_6K_LIFECYCLE_AUTHORIZATION_HARDENING_2026-10-12.md
+?? backend/architecture/STEP1_6L_FUNCTION_LEVEL_CLEANUP_AUTHORIZATION_2026-10-12.md
 ?? backend/architecture/phase4f_6/ARCHITECTURE_DECISION_RECORD.md
 ?? backend/architecture/phase4f_6/CURRENT_ARCHITECTURE.md
 ?? backend/architecture/phase4f_6/DOMAIN_MODEL.md
@@ -1084,6 +1085,7 @@
 ?? backend/tests/unit/evaluation/test_disposable_database_authorization.py
 ?? backend/tests/unit/evaluation/test_disposal_authorization_contract.py
 ?? backend/tests/unit/evaluation/test_evaluation_isolation.py
+?? backend/tests/unit/evaluation/test_function_cleanup_authorization.py
 ?? backend/tests/unit/evaluation/test_heading_corpus.py
 ?? backend/tests/unit/evaluation/test_isolation_guard_identity.py
 ?? backend/tests/unit/evaluation/test_legacy_runner_isolation.py
```

### 9.4 Actual source content diff against pre-edit snapshots

```text
--- backend/evaluation/isolation.py (baseline)
+++ backend/evaluation/isolation.py (final)
@@ -453,6 +453,27 @@
     )
 
 
+def assert_cleanup_execution_authorized(
+    resource: object,
+    *,
+    operation: str,
+    proof: DisposalProof | None = None,
+) -> None:
+    """Block destructive callables before inspecting a session/engine or doing I/O.
+
+    There is no trusted lifecycle authority or actual-connection identity binding.
+    Thus no resource or proof is accepted, including a configured matching engine.
+    Do not inspect attributes: caller-supplied properties can themselves perform I/O.
+    A future positive path requires an approved connection-bound authority, not a
+    URL comparison or registry. This refusal is independent of environment/settings.
+    """
+    raise UnsafeEvaluationTarget(
+        f"REFUSING {operation}: cleanup execution is blocked; no enforceable, "
+        "connection-bound lifecycle authorization exists. A caller-supplied "
+        "session, engine, URL, or proof object is not authorization."
+    )
+
+
 def release_database_proof(proof: DisposalProof, *, operation: str) -> None:
     """Refuse lifecycle release: no authorized open lifecycle can exist."""
     raise UnsafeEvaluationTarget(
--- backend/evaluation/experiments/run_dual_path_ablation.py (baseline)
+++ backend/evaluation/experiments/run_dual_path_ablation.py (final)
@@ -860,6 +860,9 @@
 

 async def _delete_user_data(db: AsyncSession, user_id) -> None:

     """Delete only the eval user's rows (never an unscoped DELETE)."""

+    from evaluation.isolation import assert_cleanup_execution_authorized

+

+    assert_cleanup_execution_authorized(db, operation="dual-path ablation row cleanup")

     from documents.models import Document, DocumentChunk

     from graph.models import DocumentGraphEdge

     from graph.models import DocumentStructureEdge, DocumentStructureElement

--- backend/evaluation/experiments/run_phase3d_evaluation.py (baseline)
+++ backend/evaluation/experiments/run_phase3d_evaluation.py (final)
@@ -574,6 +574,9 @@
 
     The caller commits, exactly as before.
     """
+    from evaluation.isolation import assert_cleanup_execution_authorized
+
+    assert_cleanup_execution_authorized(db, operation="Phase 3D evaluation row cleanup")
     from sqlalchemy import delete, select
 
     from auth.models import User
--- backend/evaluation/experiments/run_phase3d_upload_integration.py (baseline)
+++ backend/evaluation/experiments/run_phase3d_upload_integration.py (final)
@@ -144,6 +144,9 @@
 

     The caller commits, exactly as before.

     """

+    from evaluation.isolation import assert_cleanup_execution_authorized

+

+    assert_cleanup_execution_authorized(db, operation="Phase 3D upload row cleanup")

     from sqlalchemy import delete, select

 

     from auth.models import User

--- backend/evaluation/experiments/run_phase3e_integration.py (baseline)
+++ backend/evaluation/experiments/run_phase3e_integration.py (final)
@@ -108,6 +108,9 @@
 
     The caller commits, exactly as before.
     """
+    from evaluation.isolation import assert_cleanup_execution_authorized
+
+    assert_cleanup_execution_authorized(db, operation="Phase 3E integration row cleanup")
     from sqlalchemy import delete, select
 
     from auth.models import User
--- backend/evaluation/experiments/run_phase3e_validation.py (baseline)
+++ backend/evaluation/experiments/run_phase3e_validation.py (final)
@@ -108,6 +108,9 @@
 
     The caller commits, exactly as before.
     """
+    from evaluation.isolation import assert_cleanup_execution_authorized
+
+    assert_cleanup_execution_authorized(db, operation="Phase 3E validation row cleanup")
     from sqlalchemy import delete, select
 
     from auth.models import User
--- backend/evaluation/experiments/run_phase3f_evaluation.py (baseline)
+++ backend/evaluation/experiments/run_phase3f_evaluation.py (final)
@@ -745,6 +745,9 @@
 
     The caller commits, exactly as before.
     """
+    from evaluation.isolation import assert_cleanup_execution_authorized
+
+    assert_cleanup_execution_authorized(db, operation="Phase 3F evaluation row cleanup")
     from sqlalchemy import delete, select
 
     from auth.models import User
--- backend/evaluation/experiments/run_phase4b_evaluation.py (baseline)
+++ backend/evaluation/experiments/run_phase4b_evaluation.py (final)
@@ -725,6 +725,9 @@
 
     The caller commits, exactly as before.
     """
+    from evaluation.isolation import assert_cleanup_execution_authorized
+
+    assert_cleanup_execution_authorized(db, operation="Phase 4B evaluation row cleanup")
     from sqlalchemy import delete, select
 
     from auth.models import User
--- backend/evaluation/experiments/run_structure_confirmation.py (baseline)
+++ backend/evaluation/experiments/run_structure_confirmation.py (final)
@@ -697,6 +697,9 @@
 # ---------------------------------------------------------------------------
 
 async def run_once(run_seed: str, smoke: bool = False) -> dict:
+    from evaluation.isolation import assert_cleanup_execution_authorized
+
+    assert_cleanup_execution_authorized(engine, operation="structure confirmation alternate execution")
     import uuid as _uuid
 
     from passlib.context import CryptContext
--- backend/evaluation/experiments/run_structure_element_measurement.py (baseline)
+++ backend/evaluation/experiments/run_structure_element_measurement.py (final)
@@ -1637,6 +1637,9 @@
 
 async def run_once(run_seed: str) -> dict:
     """One complete, independent experiment execution."""
+    from evaluation.isolation import assert_cleanup_execution_authorized
+
+    assert_cleanup_execution_authorized(engine, operation="structure element alternate execution")
     from passlib.context import CryptContext
 
     from auth.models import User
--- backend/evaluation/experiments/run_structure_rrf_calibration.py (baseline)
+++ backend/evaluation/experiments/run_structure_rrf_calibration.py (final)
@@ -952,6 +952,9 @@
 # ---------------------------------------------------------------------------
 
 async def run_once(run_seed: str, smoke: bool = False) -> dict:
+    from evaluation.isolation import assert_cleanup_execution_authorized
+
+    assert_cleanup_execution_authorized(engine, operation="structure RRF alternate execution")
     from passlib.context import CryptContext
 
     from auth.models import User
--- backend/evaluation/experiments/run_table_evidence_measurement.py (baseline)
+++ backend/evaluation/experiments/run_table_evidence_measurement.py (final)
@@ -478,6 +478,9 @@
 
 async def teardown(db: AsyncSession) -> None:
     """Delete only the eval user's rows (FK cascade removes everything owned)."""
+    from evaluation.isolation import assert_cleanup_execution_authorized
+
+    assert_cleanup_execution_authorized(db, operation="table evidence row cleanup")
     from auth.models import User
 
     await db.execute(delete(User).where(User.email == EVAL_EMAIL))
@@ -638,6 +641,9 @@
 # ---------------------------------------------------------------------------
 
 async def run_once(engine, *, run_index: int, chunker_version: str) -> dict[str, Any]:
+    from evaluation.isolation import assert_cleanup_execution_authorized
+
+    assert_cleanup_execution_authorized(engine, operation="table evidence engine-taking execution")
     from brain.adapters import retrieval_adapter  # noqa: F401  (import guard)
     from chat.rag import table_gate_open
     from graph.service import terms_from_question
```

### 9.5 Final helper caller inventory

```text
backend/evaluation/experiments/run_dual_path_ablation.py:813: _delete_user_data(db, user.id)
backend/evaluation/experiments/run_dual_path_ablation.py:696: _delete_user_data(db, existing.id)
backend/evaluation/experiments/run_phase3d_evaluation.py:814: cleanup_harness_rows(db, user_ids=list(users.values()))
backend/evaluation/experiments/run_phase3d_evaluation.py:711: cleanup_harness_rows(db, user_ids=previous_users)
backend/evaluation/experiments/run_phase3d_upload_integration.py:628: cleanup_harness_rows(db, user_id=user_id)
backend/evaluation/experiments/run_phase3e_integration.py:470: cleanup_harness_rows(db, user_ids=other_ids)
backend/evaluation/experiments/run_phase3e_integration.py:543: cleanup_harness_rows(db, user_ids=[user_id])
backend/evaluation/experiments/run_phase3e_validation.py:749: cleanup_harness_rows(db, user_ids=other_ids)
backend/evaluation/experiments/run_phase3e_validation.py:850: cleanup_harness_rows(db, user_ids=[user_id])
backend/evaluation/experiments/run_phase3f_evaluation.py:1064: cleanup_harness_rows(db, user_ids=list(users.values()))
backend/evaluation/experiments/run_phase3f_evaluation.py:879: cleanup_harness_rows(db, user_ids=previous_users)
backend/evaluation/experiments/run_phase4b_evaluation.py:996: cleanup_harness_rows(db, user_ids=list(users.values()))
backend/evaluation/experiments/run_phase4b_evaluation.py:859: cleanup_harness_rows(db, user_ids=previous_users)
backend/evaluation/experiments/run_structure_confirmation.py:779: base.ablation._delete_user_data(db, user_id)
backend/evaluation/experiments/run_structure_confirmation.py:740: base.ablation._delete_user_data(db, existing.id)
backend/evaluation/experiments/run_structure_element_measurement.py:1729: ablation._delete_user_data(db, user_id)
backend/evaluation/experiments/run_structure_element_measurement.py:1674: ablation._delete_user_data(db, existing.id)
backend/evaluation/experiments/run_structure_rrf_calibration.py:1063: base.ablation._delete_user_data(db, user_id)
backend/evaluation/experiments/run_structure_rrf_calibration.py:992: base.ablation._delete_user_data(db, existing.id)
backend/evaluation/experiments/run_table_evidence_measurement.py:654: teardown(db)
backend/evaluation/experiments/run_table_evidence_measurement.py:682: teardown(db)
backend/tests/unit/evaluation/test_phase3d_cleanup_scope.py:85: harness.cleanup_harness_rows(db_session, user_id=owner.id)
backend/tests/unit/evaluation/test_phase3d_cleanup_scope.py:106: harness.cleanup_harness_rows(db_session, user_id=owner.id)
backend/tests/unit/evaluation/test_phase3d_cleanup_scope.py:147: harness.cleanup_harness_rows(db_session, user_id=owner.id)
backend/tests/unit/evaluation/test_phase3d_cleanup_scope.py:169: harness.cleanup_harness_rows(db_session, user_id=owner.id)
backend/tests/unit/evaluation/test_phase3d_cleanup_scope.py:170: harness.cleanup_harness_rows(db_session, user_id=owner.id)
backend/tests/unit/evaluation/test_phase3d_cleanup_scope.py:190: harness.cleanup_harness_rows(db_session, user_id=first.id)
backend/tests/unit/evaluation/test_phase3d_evaluation_cleanup_scope.py:158: runner.cleanup_harness_rows(db_session, user_ids=ids)
backend/tests/unit/evaluation/test_phase3d_evaluation_cleanup_scope.py:194: runner.cleanup_harness_rows(db_session, user_ids=ids)
backend/tests/unit/evaluation/test_phase3d_evaluation_cleanup_scope.py:234: runner.cleanup_harness_rows(db_session, user_ids=ids)
backend/tests/unit/evaluation/test_phase3d_evaluation_cleanup_scope.py:235: runner.cleanup_harness_rows(db_session, user_ids=ids)
backend/tests/unit/evaluation/test_phase3d_evaluation_cleanup_scope.py:244: runner.cleanup_harness_rows(db_session, user_ids=[])
backend/tests/unit/evaluation/test_phase3e_integration_cleanup_scope.py:170: runner.cleanup_harness_rows(db_session, user_ids=[user.id])
backend/tests/unit/evaluation/test_phase3e_integration_cleanup_scope.py:186: runner.cleanup_harness_rows(db_session, user_ids=[owner.id])
backend/tests/unit/evaluation/test_phase3e_integration_cleanup_scope.py:229: runner.cleanup_harness_rows(db_session, user_ids=[owner.id])
backend/tests/unit/evaluation/test_phase3e_integration_cleanup_scope.py:230: runner.cleanup_harness_rows(db_session, user_ids=[owner.id])
backend/tests/unit/evaluation/test_phase3e_integration_cleanup_scope.py:236: runner.cleanup_harness_rows(db_session, user_ids=[])
backend/tests/unit/evaluation/test_phase3e_validation_cleanup_scope.py:172: runner.cleanup_harness_rows(db_session, user_ids=[user.id])
backend/tests/unit/evaluation/test_phase3e_validation_cleanup_scope.py:188: runner.cleanup_harness_rows(db_session, user_ids=[owner.id])
backend/tests/unit/evaluation/test_phase3e_validation_cleanup_scope.py:231: runner.cleanup_harness_rows(db_session, user_ids=[owner.id])
backend/tests/unit/evaluation/test_phase3e_validation_cleanup_scope.py:232: runner.cleanup_harness_rows(db_session, user_ids=[owner.id])
backend/tests/unit/evaluation/test_phase3e_validation_cleanup_scope.py:238: runner.cleanup_harness_rows(db_session, user_ids=[])
backend/tests/unit/evaluation/test_phase3f_evaluation_cleanup_scope.py:185: runner.cleanup_harness_rows(db_session, user_ids=[user.id])
backend/tests/unit/evaluation/test_phase3f_evaluation_cleanup_scope.py:199: runner.cleanup_harness_rows(db_session, user_ids=ids)
backend/tests/unit/evaluation/test_phase3f_evaluation_cleanup_scope.py:216: runner.cleanup_harness_rows(db_session, user_ids=ids)
backend/tests/unit/evaluation/test_phase3f_evaluation_cleanup_scope.py:260: runner.cleanup_harness_rows(db_session, user_ids=ids)
backend/tests/unit/evaluation/test_phase3f_evaluation_cleanup_scope.py:261: runner.cleanup_harness_rows(db_session, user_ids=ids)
backend/tests/unit/evaluation/test_phase3f_evaluation_cleanup_scope.py:278: runner.cleanup_harness_rows(db_session, user_ids=[])
backend/tests/unit/evaluation/test_phase4b_evaluation_cleanup_scope.py:186: runner.cleanup_harness_rows(db_session, user_ids=[user.id])
backend/tests/unit/evaluation/test_phase4b_evaluation_cleanup_scope.py:200: runner.cleanup_harness_rows(db_session, user_ids=ids)
backend/tests/unit/evaluation/test_phase4b_evaluation_cleanup_scope.py:217: runner.cleanup_harness_rows(db_session, user_ids=ids)
backend/tests/unit/evaluation/test_phase4b_evaluation_cleanup_scope.py:261: runner.cleanup_harness_rows(db_session, user_ids=ids)
backend/tests/unit/evaluation/test_phase4b_evaluation_cleanup_scope.py:262: runner.cleanup_harness_rows(db_session, user_ids=ids)
backend/tests/unit/evaluation/test_phase4b_evaluation_cleanup_scope.py:279: runner.cleanup_harness_rows(db_session, user_ids=[])
```

Initial expanded paths: 1136; final expanded paths: 1138. New paths are the test and report; collapsed ordinary status remains 384 entries.
