# Step 1.6K — Lifecycle Authorization Hardening

Date: 2026-10-12
Verdict: **PARTIALLY COMPLETE; PostgreSQL verification NO-GO.**

Fail-closed refusal is implemented and covered by focused database-free checks. An operational, enforceable disposable-database lifecycle is **NOT IMPLEMENTED**. No successful create, cleanup, drop, migration, real model or PostgreSQL validation is claimed.

## 1. Scope, ownership and review limitations

The runtime provides no specialist-agent dispatch. The prior work performed implementation and review across EVALUATION_AGENT and TEST_AGENT ownership rather than obtaining independent specialist execution. This is an ownership/process deviation, not independent verification. This continuation performs validation and records new Coordinator-owned append-only evidence; it changes no implementation file. SECURITY_AGENT, DATABASE_AGENT, TEST_AGENT and VERIFIER independent reviews remain unfulfilled.

HEAD: `6baaa2a0773df66e5fb26814afbe67647fb43435`.
The worktree was already heavily modified/untracked. Baseline and final ordinary `git status --short` contain 384 entries. Baseline was captured from backend; final is root-relative. Raw textual comparison therefore differs due to relative paths, not necessarily changed status. Full original listings and tracked diff summaries are appended below. Collapsed untracked directories and Git diffs cannot establish this task's content delta; these files were already untracked. No staging, commit, push, reset, clean or revert was performed in this continuation.

## 2. Acceptance criteria and observed disposition

1. URL validity, application isolation, configured target identity, create permission, successful-creation evidence, row-cleanup permission and drop permission must remain distinct. **Implemented in the refusal contract; no operational authority exists.**
2. A URL, free-name claim, environment declaration, constructed Python object, private issuer or mutable registry must not authorize a lifecycle. **Verified by pure refusal tests.**
3. Creation must refuse before provisioning, existence checks, sockets or subprocess access when create authority is missing. **Central guard behavior verified; fixture order checked from source only.**
4. Caller assertions must not issue successful-creation evidence. **Verified:** `record_created_database` always raises.
5. Cleanup and drop must remain blocked, including matching, forged, copied, stale and differently targeted proof-shaped claims. **Verified by guard tests, not execution of destructive functions.**
6. E2E cleanup authorization must precede imports/engine creation; configured engine checks must precede sessions. **Source-order evidence only.**
7. Preserve existing URL parsing, application-name isolation and configured engine-target checks. **Focused identity and order checks pass.** Literal URL matching does not verify actual connected server identity.
8. Do not run provisioning, create/drop primitives, cleanup, runner `main()`, E2E or migrations during restricted validation. **Final focused validation complies; earlier draft checks did not (section 5).**
9. Save exact test evidence and Git listings in a new architecture report. **This record and appendices.**

## 3. Final contract and changed files

| File | Owning contract | Final change recorded from prior work |
| --- | --- | --- |
| `backend/evaluation/isolation.py` | EVALUATION_AGENT | Separate create and row-cleanup guards; all proof issuance, disposal, cleanup and lifecycle release refuse; no live proof registry/issuer exists; configured engine URL check retained |
| `backend/tests/fixtures/integration_db.py` | TEST_AGENT | Create gate before reachability and existence I/O; direct create primitive also gated; isolated fixture refuses before reachability; drop and row cleanup delegate to central refusal; legacy lifecycle implementation retained but unreachable |
| `backend/tests/integration/rag/test_real_e2e_validation.py` | TEST_AGENT | Row-cleanup gate before imports/engine; configured engine/proof gate before sessions; direct validation is blocked |
| `backend/tests/unit/evaluation/test_lifecycle_authorization.py` | TEST_AGENT | Pure guard tests and AST/source ordering; I/O patched to fail; no destructive function or E2E invocation |
| `backend/tests/unit/evaluation/test_disposable_database_authorization.py` | TEST_AGENT | Refusal tests for caller-constructed evidence and configuration changes |
| `backend/tests/unit/evaluation/test_disposal_authorization_contract.py` | TEST_AGENT | Central/fixture refusal invariants and source-only order checks |
| `backend/tests/unit/evaluation/test_legacy_runner_isolation.py` | TEST_AGENT | Earlier draft expectations adjusted to fail-closed refusal; NOT included in final restricted run because it invokes runner main |
| `backend/tests/unit/evaluation/conftest.py` | TEST_AGENT | Draft registry-reset fixture removed; explanatory module only |
| This report | COORDINATOR | New append-only evidence |

### Classification

- **SAFELY BLOCKED at the contract:** create, provision, proof issuance, row cleanup, database drop and lifecycle release. There is no authorized positive path.
- **SAFELY BLOCKED through existing central gates:** evaluation runners and integration validation. Final evidence for execution ordering is source-level, not runtime invocation of those entry points.
- **UNRESOLVED/out of scope:** `cleanup_smoke.py`, `cleanup_orphan_uploads.py`, and previously inventoried filesystem cleanup. Their safety is not established by this change.

The Step 1.6J private-sentinel proof model and its AUTHORIZED classification are superseded by this record: `record_created_database()` was callable by ordinary Python callers and did not establish successful authorized creation. The Step 1.6K draft registry also did not create an external authorization boundary. No declaration of an absent database grants create permission.

## 4. Final verification

Executed from backend, with command status explicitly captured before printing output:

```bash
./venv/Scripts/python.exe -m pytest -q tests/unit/evaluation/test_lifecycle_authorization.py tests/unit/evaluation/test_disposable_database_authorization.py tests/unit/evaluation/test_disposal_authorization_contract.py tests/unit/evaluation/test_phase3_runner_target_order.py tests/unit/evaluation/test_isolation_guard_identity.py tests/unit/evaluation/test_metrics.py -p no:cacheprovider > /tmp/s16k_verified_focused.txt 2>&1
result=$?
cat /tmp/s16k_verified_focused.txt
exit "$result"
```

Observed: **212 passed, 1 warning in 0.51s; exit 0**. Existing pytest-asyncio notices report an unset default loop scope and a redefined event-loop fixture. Neither was suppressed. The two metrics tests that failed in the earlier draft pass with their assertions unchanged. Metrics use in-memory callbacks; they are not measured model or database performance.

Compilation:

```bash
./venv/Scripts/python.exe -m py_compile evaluation/isolation.py tests/fixtures/integration_db.py tests/integration/rag/test_real_e2e_validation.py tests/unit/evaluation/conftest.py tests/unit/evaluation/test_lifecycle_authorization.py tests/unit/evaluation/test_disposable_database_authorization.py tests/unit/evaluation/test_disposal_authorization_contract.py tests/unit/evaluation/test_legacy_runner_isolation.py
```

Observed: compilation completed successfully; the following `git diff --check` executed through `&&`. The combined command exited **2** because repository-wide `git diff --check` reported trailing whitespace in the already-modified `DOCUMIND_PROJECT_CONTEXT.md`. That unrelated file was not repaired in this continuation.

Root command:

```bash
git diff --check -- backend/evaluation/isolation.py backend/tests/fixtures/integration_db.py backend/tests/integration/rag/test_real_e2e_validation.py backend/tests/unit/evaluation
```

Observed: **exit 0**, but these paths are untracked, so this command alone does not inspect their contents. Final edited content was read back separately. No Python static type checker or frontend build was run; compilation is syntax evidence, not typechecking.

## 5. Earlier failures and safety deviations

Saved earlier logs show:

- `/tmp/s16k_unit_eval.txt`: **27 failed, 539 passed**, reflecting stale legacy expectations/draft state.
- `/tmp/s16k_unit_eval2.txt`: **566 passed**, an intermediate draft only; not final evidence.
- `/tmp/s16k_unit_eval3.txt`: **2 failed, 593 passed**, both metrics failures after draft `asyncio.run` calls disturbed pytest's current event loop.
- `/tmp/s16k_final_focused.txt`: **212 passed, 1 warning in 0.89s**, the earlier final-focused result.
- `/tmp/s16k_verified_focused.txt`: final rerun above, **212 passed, 1 warning in 0.51s**, exit 0.

Earlier checks invoked mocked provisioning/create/drop and E2E or runner entry points despite the task's restriction. This was a safety/protocol deviation even when I/O was mocked, and it must not be described as compliance. Those invocation tests were replaced in the lifecycle file with pure guards/source checks; the final focused set excludes legacy runner invocation tests. No assertion was weakened in the metrics tests to make them pass. The unrestricted evaluation unit suite was not rerun because it contains prohibited invocation paths. Its earlier results do not validate the final files.

## 6. Security limits and next authorization design

No Python sentinel, dataclass, registry or private function protects against arbitrary code running in the same process. These gates enforce default refusal in inspected entry points; they are not a sandbox. Actual connection identity, authoritative lifecycle ownership and a trusted successful-create receipt are **NOT IMPLEMENTED**. Literal engine URL checks cannot resolve aliases, proxies, DNS changes or connection redirection.

Before enabling any positive lifecycle, a separately approved authority must enforce:

- restricted database roles and deny direct create/drop outside the authority;
- separate create permission, successful-create evidence, row cleanup and drop permissions;
- authoritative target/actual-connection identity binding;
- unique lifecycle identity and protection against stale/cross-run reuse and target replacement;
- atomic existing-name refusal and no adoption of pre-existing databases;
- revocation/closure and last-use authorization, plus audited failure/crash handling.

A restricted-role provisioning service is a proposed design, **not approved, provisioned, integrated or enabled**. Coordinator approval and independent security/database/verifier review are required. Existing unreachable SQL must be reviewed before any gate changes; it must not become reachable merely by replacing a raise with a proof registry.

No model weights, benchmark, production retrieval algorithm, migration or forbidden data path was intentionally edited for this step. The backend virtual environment was executed, not edited as source. `.env` values are not included in this report. Git path snapshots contain file names only.

## 7. Final report and handoff

Changed: default-refusal lifecycle contract and database-free guard/order tests from prior implementation.
Files: section 3.
Tests/commands/observed results: section 4; earlier failures and deviations: section 5.
Remaining limitations: no enforceable positive authorization path, no actual connected-target verification, no PostgreSQL runtime evidence, no independent verification, unrestricted suite not rerun, existing repository whitespace failure.
Security considerations: section 6; all database lifecycle operations remain blocked.
Handoff: Coordinator for ownership/architecture approval; SECURITY_AGENT and DATABASE_AGENT for authority/identity review; TEST_AGENT for approved positive-path coverage only after that boundary exists; VERIFIER for independent review.

**PostgreSQL verification remains NO-GO.**

## 8. Git evidence appendices

The following snapshots are generated from Git/path-only evidence. Baseline retains its original backend-relative spelling. Final status is captured after this report is created. Tracked diff summaries describe the whole pre-existing worktree, not this task alone. No secret file contents are included.

Same-cwd ordinary status comparison: True. This is path/status evidence only, not content preservation evidence.

### 8.1 Original baseline: git status --short (backend cwd)

```text
 M ../.gitignore
 M ../DOCUMIND_PROJECT_CONTEXT.md
 M brain/__init__.py
 M brain/adapters.py
 M brain/response.py
 M brain/types.py
 M chat/qa_model.py
 M chat/rag.py
 M chat/routes.py
 M documents/models.py
 M documents/processing.py
 M documents/routes.py
 M documents/schemas.py
 M embeddings/model.py
 M embeddings/routes.py
 M evaluation/harness/corpus.py
 D evaluation/harness/evaluator.py
 M main.py
 M migrations/env.py
 D phase3d_evaluation_report.json
 D phase3f_evaluation_report.json
 D phase3f_validation_report.txt
 D phase3g_pipeline_audit.txt
 D phase4a_qa_failure_audit.txt
 D phase4b_evaluation_report.json
 D phase4b_qa_evaluation_report.txt
 D phase4c_failure_matrix.json
 D phase4c_qa_failure_isolation_report.txt
 D phase4d/__init__.py
 D phase4d/__main__.py
 D phase4d/evaluate_candidates.py
 D phase4d/generate_report.py
 D phase4d/oracle_eval.py
 D phase4d/reconciliation.py
 D phase4d/train.py
 D phase4d/training_data.py
 D phase4d_1_reconciliation.json
 D phase4d_1_reconciliation_report.txt
 D phase4d_experiment_results.json
 D phase4d_oracle_baseline_results.json
 D phase4d_qa_model_improvement_report.txt
 D phase4e/__init__.py
 D phase4e/capability_analysis.py
 D phase4e/generate_report.py
 D phase4e_capability_matrix.json
 D phase4e_diagnostic_results.json
 D phase4e_qa_architecture_analysis.txt
 D phase4f/__init__.py
 D phase4f/balance_gate.py
 D phase4f/dataset/__init__.py
 D phase4f/dataset/dataset_manifest.json
 D phase4f/dataset/dataset_manifest_v3.json
 D phase4f/dataset/dataset_manifest_v3_1.json
 D phase4f/dataset/dataset_metadata.json
 D phase4f/dataset/dataset_quality_report.json
 D phase4f/dataset/dataset_quality_report_v3.json
 D phase4f/dataset/dataset_quality_report_v3_1.json
 D phase4f/dataset/expand_and_audit.py
 D phase4f/dataset/generator.py
 D phase4f/dataset/training_data.jsonl
 D phase4f/dataset/training_data_v3.jsonl
 D phase4f/dataset/training_data_v3_1.jsonl
 D phase4f/experiments/evaluate.py
 D phase4f/experiments/experiment_manifest.json
 D phase4f/experiments/final_gpu_package/README_GPU_EXECUTION.md
 D phase4f/experiments/final_gpu_package/dataset/training_data_v3_1.jsonl
 D phase4f/experiments/final_gpu_package/dataset_checksum.txt
 D phase4f/experiments/final_gpu_package/evaluation/evaluate.py
 D phase4f/experiments/final_gpu_package/expected_output_structure.txt
 D phase4f/experiments/final_gpu_package/final_gpu_package_manifest.json
 D phase4f/experiments/final_gpu_package/production_model_checksum.txt
 D phase4f/experiments/final_gpu_package/requirements.txt
 D phase4f/experiments/final_gpu_package/training/experiment_config.json
 D phase4f/experiments/final_gpu_package/training/train.py
 D phase4f/experiments/phase4f_3_results.json
 D phase4f/experiments/phase4f_3_training_report.txt
 D phase4f/experiments/phase4f_3r_freeze_report.txt
 D phase4f/experiments/phase4f_4_controlled_gpu_experiment_report.txt
 D phase4f/experiments/phase4f_4_experiment_manifest.json
 D phase4f/experiments/phase4f_4_results.json
 D phase4f/experiments/phase4f_4e_cuda_environment.json
 D phase4f/experiments/phase4f_4e_cuda_environment_report.txt
 D phase4f/experiments/requirements.txt
 D phase4f/experiments/results/A0/evaluation_results.json
 D phase4f/experiments/results/A0/metadata.json
 D phase4f/experiments/results/A1/checkpoint_best/config.json
 D phase4f/experiments/results/A1/checkpoint_best/tokenizer.json
 D phase4f/experiments/results/A1/checkpoint_best/tokenizer_config.json
 D phase4f/experiments/results/A1/evaluation_results.json
 D phase4f/experiments/results/A1/training_metadata.json
 D phase4f/experiments/results/A2/checkpoint_best/config.json
 D phase4f/experiments/results/A2/checkpoint_best/tokenizer.json
 D phase4f/experiments/results/A2/checkpoint_best/tokenizer_config.json
 D phase4f/experiments/results/A2/evaluation_results.json
 D phase4f/experiments/results/A2/training_metadata.json
 D phase4f/experiments/results/A3/checkpoint_best/config.json
 D phase4f/experiments/results/A3/checkpoint_best/tokenizer.json
 D phase4f/experiments/results/A3/checkpoint_best/tokenizer_config.json
 D phase4f/experiments/results/A3/evaluation_results.json
 D phase4f/experiments/results/A3/training_metadata.json
 D phase4f/experiments/results/all_results.json
 D phase4f/experiments/run_experiment.py
 D phase4f/experiments/train.py
 D phase4f/freeze_gate.py
 D phase4f/phase4f_1_dataset_audit_report.txt
 D phase4f/phase4f_2_dataset_quality_gate_report.txt
 D phase4f/phase4f_2r_dataset_balance_report.txt
 D phase4f/phase4f_4r_manifest.json
 D phase4f/phase4f_5/configs/a1_config.json
 D phase4f/phase4f_5/configs/a2_config.json
 D phase4f/phase4f_5/dataset/data_quality_gate.json
 D phase4f/phase4f_5/dataset/derived_dataset.jsonl
 D phase4f/phase4f_5/dataset/span_alignment_audit.json
 D phase4f/phase4f_5/dataset/truncation_audit.json
 D phase4f/phase4f_5/diagnostics/a0_forensics.json
 D phase4f/phase4f_5/diagnostics/a1_forensics.json
 D phase4f/phase4f_5/diagnostics/a2_forensics.json
 D phase4f/phase4f_5/diagnostics/all_inference_results.json
 D phase4f/phase4f_5/diagnostics/failure_taxonomy.json
 D phase4f/phase4f_5/evaluation/evaluate.py
 D phase4f/phase4f_5/evaluation/evaluation_protocol.json
 D phase4f/phase4f_5/logs/a1_training.json
 D phase4f/phase4f_5/logs/a2_training.json
 D phase4f/phase4f_5/manifests/experiment_manifest.json
 D phase4f/phase4f_5/manifests/final_experiment_manifest.json
 D phase4f/phase4f_5/manifests/source_integrity.json
 D phase4f/phase4f_5/manifests/split_manifest.json
 D phase4f/phase4f_5/prepare_experiment.py
 D phase4f/phase4f_5/reports/phase4f_5a_preparation_report.txt
 D phase4f/phase4f_5/reports/phase4f_5b_training_report.txt
 D phase4f/phase4f_5/results/a0_test.json
 D phase4f/phase4f_5/results/a1_test.json
 D phase4f/phase4f_5/results/a2_test.json
 D phase4f/phase4f_5/results/comparison.json
 D phase4f/phase4f_5/run_experiment.py
 D phase4f/phase4f_5c/em_f1_gap_analysis.json
 D phase4f/phase4f_5c/failure_matrix.json
 D phase4f/phase4f_5c/generate_analysis.py
 D phase4f/phase4f_5c/list_audit.json
 D phase4f/phase4f_5c/long_context_audit.json
 D phase4f/phase4f_5c/normalization_diagnostic.json
 D phase4f/phase4f_5c/numeric_audit.json
 D phase4f/phase4f_5c/per_category_comparison.json
 D phase4f/phase4f_5c/phase4f_5c_manifest.json
 D phase4f/phase4f_5c/production_strengths.json
 D phase4f/phase4f_5c/reports/phase4f_5c_qa_analysis_report.txt
 D phase4f/phase4f_5c/root_cause_analysis.json
 D phase4f/phase4f_5c/table_audit.json
 D phase4f/phase4f_5c/test_composition.json
 D phase4f/phase4f_5c/training_curve_analysis.json
 D phase4f/phase4f_5d/analysis/a0_benchmark_v1.json
 D phase4f/phase4f_5d/analysis/a1_benchmark_v1.json
 D phase4f/phase4f_5d/analysis/a2_benchmark_v1.json
 D phase4f/phase4f_5d/analysis/benchmark_comparison.json
 D phase4f/phase4f_5d/analysis/category_balance.json
 D phase4f/phase4f_5d/analysis/duplicate_audit.json
 D phase4f/phase4f_5d/analysis/gold_span_validation.json
 D phase4f/phase4f_5d/analysis/leakage_audit.json
 D phase4f/phase4f_5d/analysis/test_composition.json
 D phase4f/phase4f_5d/analysis/unanswerable_audit.json
 D phase4f/phase4f_5d/benchmark/benchmark_checksum.txt
 D phase4f/phase4f_5d/benchmark/benchmark_manifest.json
 D phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl
 D phase4f/phase4f_5d/build_benchmark.py
 D phase4f/phase4f_5d/phase4f_5d_manifest.json
 D phase4f/phase4f_5d/reports/phase4f_5d_benchmark_hardening_report.txt
 D phase4f/phase4f_5e/analysis/capability_matrix.json
 D phase4f/phase4f_5e/analysis/confidence_distribution.json
 D phase4f/phase4f_5e/analysis/f1_gain_analysis.json
 D phase4f/phase4f_5e/analysis/next_experiment_matrix.json
 D phase4f/phase4f_5e/analysis/production_vs_experiment.json
 D phase4f/phase4f_5e/analysis/root_cause_matrix.json
 D phase4f/phase4f_5e/analysis/split_category_matrix.json
 D phase4f/phase4f_5e/analysis/threshold_sweep.json
 D phase4f/phase4f_5e/analysis/training_data_audit.json
 D phase4f/phase4f_5e/analysis/unanswerable_audit.json
 D phase4f/phase4f_5e/phase4f_5e_manifest.json
 D phase4f/phase4f_5e/reports/phase4f_5e_qa_capability_audit.txt
 D phase4f/phase4f_5e/run_analysis.py
 D phase4f/phase4f_5f/dataset/experiment_f1_manifest.json
 D phase4f/phase4f_5f/dataset/experiment_f1_quality_report.json
 D phase4f/phase4f_5f/dataset/experiment_f1_split.json
 D phase4f/phase4f_5f/f2/config/f2_config.json
 D phase4f/phase4f_5f/f2/evaluation/f2_benchmark.json
 D phase4f/phase4f_5f/f2/evaluation/f2_holdout.json
 D phase4f/phase4f_5f/f2/evaluation/f2_validation.json
 D phase4f/phase4f_5f/f2/logs/f2_training.json
 D phase4f/phase4f_5f/f2/manifests/f2_dataset_ids.json
 D phase4f/phase4f_5f/f2/manifests/f2_manifest.json
 D phase4f/phase4f_5f/f2/reconciliation/f2_baseline_comparison.json
 D phase4f/phase4f_5f/f2/reconciliation/f2_data_balance_audit.json
 D phase4f/phase4f_5f/f2/reconciliation/f2_label_audit.json
 D phase4f/phase4f_5f/f2/reconciliation/f2_no_answer_logic_audit.json
 D phase4f/phase4f_5f/f2/reconciliation/f2_prediction_audit.json
 D phase4f/phase4f_5f/f2/reconciliation/f2_root_cause_analysis.json
 D phase4f/phase4f_5f/f2/reports/phase4f_5f_f2_final_report.txt
 D phase4f/phase4f_5f/f2/reports/phase4f_5f_f2_reconciliation_report.txt
 D phase4f/phase4f_5f/f2/reports/phase4f_5f_g_threshold_report.txt
 D phase4f/phase4f_5f/f2/run_f2.py
 D phase4f/phase4f_5f/f2/threshold_experiment/benchmark_result.json
 D phase4f/phase4f_5f/f2/threshold_experiment/holdout_result.json
 D phase4f/phase4f_5f/f2/threshold_experiment/margin_sweep.json
 D phase4f/phase4f_5f/f2/threshold_experiment/raw_prediction_audit.json
 D phase4f/phase4f_5f/f2/threshold_experiment/raw_predictions_benchmark.json
 D phase4f/phase4f_5f/f2/threshold_experiment/raw_predictions_holdout.json
 D phase4f/phase4f_5f/f2/threshold_experiment/raw_predictions_validation.json
 D phase4f/phase4f_5f/f2/threshold_experiment/run_threshold_experiment.py
 D phase4f/phase4f_5f/f2/threshold_experiment/stability_analysis.json
 D phase4f/phase4f_5f/f2/threshold_experiment/threshold_experiment_manifest.json
 D phase4f/phase4f_5f/f2/threshold_experiment/threshold_sweep.json
 D phase4f/phase4f_5f/f2/threshold_experiment/validation_calibration.json
 D phase4f/phase4f_5f/h/audits/duplicate_audit.json
 D phase4f/phase4f_5f/h/audits/leakage_audit.json
 D phase4f/phase4f_5f/h/audits/quality_gate_failures.json
 D phase4f/phase4f_5f/h/audits/semantic_audit.json
 D phase4f/phase4f_5f/h/candidates/all_candidates.jsonl
 D phase4f/phase4f_5f/h/generate_h_candidates.py
 D phase4f/phase4f_5f/h/manifests/h_manifest.json
 D phase4f/phase4f_5f/h/pools/h10.jsonl
 D phase4f/phase4f_5f/h/pools/h20.jsonl
 D phase4f/phase4f_5f/h/pools/h30.jsonl
 D phase4f/phase4f_5f/h/reports/phase4f_5f_h_dataset_design_report.txt
 D phase4f/phase4f_5f/h1/config/f1_reconciled_ids.json
 D phase4f/phase4f_5f/h1/config/h1_config.json
 D phase4f/phase4f_5f/h1/evaluation/h1_benchmark.json
 D phase4f/phase4f_5f/h1/evaluation/h1_holdout.json
 D phase4f/phase4f_5f/h1/evaluation/h1_null_analysis.json
 D phase4f/phase4f_5f/h1/evaluation/h1_validation.json
 D phase4f/phase4f_5f/h1/logs/h1_training.json
 D phase4f/phase4f_5f/h1/manifests/h1_manifest.json
 D phase4f/phase4f_5f/h1/reports/phase4f_5f_h1_final_report.txt
 D phase4f/phase4f_5f/h1/run_h1.py
 D phase4f/phase4f_5f/h1_reconciliation/H1_RECONCILIATION_REPORT.md
 D phase4f/phase4f_5f/h1_reconciliation/README.md
 D phase4f/phase4f_5f/h1_reconciliation/checksums.txt
 D phase4f/phase4f_5f/h1_reconciliation/h1_count_reconciliation.json
 D phase4f/phase4f_5f/h1_reconciliation/h1_label_integrity.json
 D phase4f/phase4f_5f/h1_reconciliation/h1_metric_recalculation.json
 D phase4f/phase4f_5f/h1_reconciliation/h1_no_answer_analysis.json
 D phase4f/phase4f_5f/h1_reconciliation/h1_null_score_analysis.json
 D phase4f/phase4f_5f/h1_reconciliation/h1_overlap_report.json
 D phase4f/phase4f_5f/h1_reconciliation/h1_protocol_audit.json
 D phase4f/phase4f_5f/h1_reconciliation/h1_reconciled_comparison.json
 D phase4f/phase4f_5f/phase4f_5f_f1_reconciliation_manifest.json
 D phase4f/phase4f_5f/reconciliation/dataset_reconciliation.json
 D phase4f/phase4f_5f/reconciliation/final_holdout_ids.json
 D phase4f/phase4f_5f/reconciliation/final_training_ids.json
 D phase4f/phase4f_5f/reconciliation/final_validation_ids.json
 D phase4f/phase4f_5f/reconciliation/invalid_span_audit.json
 D phase4f/phase4f_5f/reconciliation/training_protocol_audit.json
 D phase4f/phase4f_5f/recovery/artifact_inventory.json
 D phase4f/phase4f_5f/recovery/gpu_environment_report.json
 D phase4f/phase4f_5f/recovery/gpu_environment_report.txt
 D phase4f/phase4f_5f/recovery/phase4f_5f_recovery_report.txt
 D phase4f/phase4f_5f/recovery/recovery_manifest.json
 D phase4f/phase4f_5f/reports/phase4f_5f_f1_preparation_report.txt
 D phase4f/phase4f_5f/reports/phase4f_5f_f1_reconciliation_report.txt
 D phase4f/phase4f_5f/run_experiment.py
 D phase4f/quality_gate.py
 D phase4f/reconciliation/a0_reproduction.json
 D phase4f/reconciliation/checkpoint_audit.json
 D phase4f/reconciliation/cross_phase_evaluation_compatibility.json
 D phase4f/reconciliation/dataset_label_audit.json
 D phase4f/reconciliation/evaluation_parity_matrix.json
 D phase4f/reconciliation/experiment_artifact_inventory.json
 D phase4f/reconciliation/failure_taxonomy_reconciliation.json
 D phase4f/reconciliation/manual_forensic_traces.json
 D phase4f/reconciliation/model_initialization_audit.json
 D phase4f/reconciliation/phase4f_4r_reconciliation_report.txt
 D phase4f/reconciliation/token_span_audit.json
 D phase4f/reconciliation/training_configuration_audit.json
 D phase4f/training/__init__.py
 D phase4f/training/configs.py
 D phase4f/training/environment.json
 D phase4f/training/train.py
 D phase4f_qa_architecture_experiment_report.txt
 M pytest.ini
 M reliability/routes.py
 M requirements.txt
 D start_server.py
 D test_browser_flow.py
 D test_document_flow.py
 D test_embedding_flow.py
 D test_phase3d_evaluation.py
 D test_phase3d_upload_integration.py
 D test_phase3e_integration.py
 D test_phase3e_validation.py
 D test_phase3f_evaluation.py
 D test_phase4b_evaluation.py
 D test_phase4c_diagnostics.py
 D test_phase6_reliability.py
 D test_rag_flow.py
 D test_real_browser.py
 M tests/conftest.py
 D tests/integration_http.py
 D tests/phase3d_corpus.py
 D tests/phase4b_corpus.py
 D tests/test_answer_span.py
 D tests/test_auth.py
 D tests/test_brain_orchestration.py
 D tests/test_brain_types.py
 D tests/test_chat_unit.py
 D tests/test_config_security.py
 D tests/test_cors.py
 D tests/test_database_url.py
 D tests/test_file_validation.py
 D tests/test_outcomes.py
 D tests/test_phase3d_chunking.py
 D tests/test_phase3d_context.py
 D tests/test_phase3d_reconciliation.py
 D tests/test_phase3e_processing.py
 D tests/test_qa_answer_reconstruction.py
 D tests/test_real_e2e_validation.py
 D tests/test_settings.py
 D tests/test_sql_safety.py
 D tests/test_structured_extraction.py
 D tests/test_verification_integrity.py
 M verification/routes.py
 M ../package-lock.json
 M ../package.json
 M ../runbooks/README.md
 M ../runbooks/database-failure.md
 M ../runbooks/migration-failure.md
 M ../src/lib/api.ts
 M ../src/pages/ReliabilityPage.tsx
 M ../src/pages/VerificationPage.tsx
 M ../src/pages/WorkspacePage.tsx
 M ../src/types/index.ts
 M ../vite.config.ts
?? ../.dockerignore
?? ../.env.example
?? ../AGENTS.md
?? ../ARCHITECTURE.md
?? ../CONTEXT.md
?? ../DESIGN.md
?? ../Dockerfile.frontend
?? ../Field_Robotics_Deployment_and_Maintenance_Report.pdf
?? ../PRD.md
?? ../README.md
?? ../agents/
?? .dockerignore
?? Dockerfile
?? architecture/
?? docker-entrypoint.sh
?? documents/insights.py
?? documents/parser.py
?? documents/structure.py
?? documents/tables.py
?? evaluation/README.md
?? evaluation/artifacts.py
?? evaluation/baselines/
?? evaluation/datasets/
?? evaluation/denominator_sensitivity.py
?? evaluation/experiments/
?? evaluation/isolation.py
?? evaluation/metrics/
?? evaluation/qa_metrics.py
?? evaluation/reports/
?? evaluation/retrieval_metrics.py
?? evaluation/runner.py
?? evaluation/schemas.py
?? evaluation/structure_eval.py
?? graph/
?? migrations/versions/005_add_document_graph.py
?? migrations/versions/006_add_structure_elements.py
?? migrations/versions/007_add_table_rows.py
?? models/media-verification/
?? models/whisper/
?? phases/
?? scripts/
?? tests/README.md
?? tests/e2e/
?? tests/fixtures/
?? tests/integration/
?? tests/unit/
?? verification/service.py
?? voice.py
?? ../compose.yaml
?? ../docker/
?? ../prompts/
?? ../runbooks/docker-runtime.md
?? ../src/components/common/DocumentInsightsPanel.tsx
?? ../src/components/common/VoiceInputButton.tsx
?? ../src/components/common/VoiceSpeakerButton.tsx
```

### 8.2 Final: git status --short (root cwd)

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
?? agents/
?? backend/.dockerignore
?? backend/Dockerfile
?? backend/architecture/
?? backend/docker-entrypoint.sh
?? backend/documents/insights.py
?? backend/documents/parser.py
?? backend/documents/structure.py
?? backend/documents/tables.py
?? backend/evaluation/README.md
?? backend/evaluation/artifacts.py
?? backend/evaluation/baselines/
?? backend/evaluation/datasets/
?? backend/evaluation/denominator_sensitivity.py
?? backend/evaluation/experiments/
?? backend/evaluation/isolation.py
?? backend/evaluation/metrics/
?? backend/evaluation/qa_metrics.py
?? backend/evaluation/reports/
?? backend/evaluation/retrieval_metrics.py
?? backend/evaluation/runner.py
?? backend/evaluation/schemas.py
?? backend/evaluation/structure_eval.py
?? backend/graph/
?? backend/migrations/versions/005_add_document_graph.py
?? backend/migrations/versions/006_add_structure_elements.py
?? backend/migrations/versions/007_add_table_rows.py
?? backend/models/media-verification/
?? backend/models/whisper/
?? backend/phases/
?? backend/scripts/
?? backend/tests/README.md
?? backend/tests/e2e/
?? backend/tests/fixtures/
?? backend/tests/integration/
?? backend/tests/unit/
?? backend/verification/service.py
?? backend/voice.py
?? compose.yaml
?? docker/
?? prompts/
?? runbooks/docker-runtime.md
?? src/components/common/DocumentInsightsPanel.tsx
?? src/components/common/VoiceInputButton.tsx
?? src/components/common/VoiceSpeakerButton.tsx
```

### 8.3 Final: git diff --stat (tracked worktree)

```text
 .gitignore                                         |      7 +-
 DOCUMIND_PROJECT_CONTEXT.md                        |   3419 +-
 backend/brain/__init__.py                          |     58 +
 backend/brain/adapters.py                          |    220 +-
 backend/brain/response.py                          |     33 +
 backend/brain/types.py                             |     60 +-
 backend/chat/qa_model.py                           |     12 +-
 backend/chat/rag.py                                |    707 +-
 backend/chat/routes.py                             |     79 +
 backend/documents/models.py                        |    107 +-
 backend/documents/processing.py                    |     92 +-
 backend/documents/routes.py                        |    201 +-
 backend/documents/schemas.py                       |     75 +
 backend/embeddings/model.py                        |     70 +-
 backend/embeddings/routes.py                       |     18 +-
 backend/evaluation/harness/corpus.py               |      2 +-
 backend/evaluation/harness/evaluator.py            |    712 -
 backend/main.py                                    |      2 +
 backend/migrations/env.py                          |     13 +-
 backend/phase3d_evaluation_report.json             |   2403 -
 backend/phase3f_evaluation_report.json             |   4622 -
 backend/phase3f_validation_report.txt              |    217 -
 backend/phase3g_pipeline_audit.txt                 |    633 -
 backend/phase4a_qa_failure_audit.txt               |    752 -
 backend/phase4b_evaluation_report.json             |   9239 -
 backend/phase4b_qa_evaluation_report.txt           |    502 -
 backend/phase4c_failure_matrix.json                |   1845 -
 backend/phase4c_qa_failure_isolation_report.txt    |    660 -
 backend/phase4d/__init__.py                        |      1 -
 backend/phase4d/__main__.py                        |     58 -
 backend/phase4d/evaluate_candidates.py             |    538 -
 backend/phase4d/generate_report.py                 |    780 -
 backend/phase4d/oracle_eval.py                     |    585 -
 backend/phase4d/reconciliation.py                  |    746 -
 backend/phase4d/train.py                           |    546 -
 backend/phase4d/training_data.py                   |    600 -
 backend/phase4d_1_reconciliation.json              |   3976 -
 backend/phase4d_1_reconciliation_report.txt        |    437 -
 backend/phase4d_experiment_results.json            |   3725 -
 backend/phase4d_oracle_baseline_results.json       |   2570 -
 backend/phase4d_qa_model_improvement_report.txt    |    550 -
 backend/phase4e/__init__.py                        |      1 -
 backend/phase4e/capability_analysis.py             |    854 -
 backend/phase4e/generate_report.py                 |    523 -
 backend/phase4e_capability_matrix.json             |   1566 -
 backend/phase4e_diagnostic_results.json            |   1415 -
 backend/phase4e_qa_architecture_analysis.txt       |    425 -
 backend/phase4f/__init__.py                        |      1 -
 backend/phase4f/balance_gate.py                    |   1112 -
 backend/phase4f/dataset/__init__.py                |      1 -
 backend/phase4f/dataset/dataset_manifest.json      |     22 -
 backend/phase4f/dataset/dataset_manifest_v3.json   |     26 -
 backend/phase4f/dataset/dataset_manifest_v3_1.json |     58 -
 backend/phase4f/dataset/dataset_metadata.json      |     38 -
 .../phase4f/dataset/dataset_quality_report.json    |    639 -
 .../phase4f/dataset/dataset_quality_report_v3.json |    755 -
 .../dataset/dataset_quality_report_v3_1.json       |    111 -
 backend/phase4f/dataset/expand_and_audit.py        |   2609 -
 backend/phase4f/dataset/generator.py               |    762 -
 backend/phase4f/dataset/training_data.jsonl        |   1000 -
 backend/phase4f/dataset/training_data_v3.jsonl     |    918 -
 backend/phase4f/dataset/training_data_v3_1.jsonl   |    918 -
 backend/phase4f/experiments/evaluate.py            |    292 -
 .../phase4f/experiments/experiment_manifest.json   |     60 -
 .../final_gpu_package/README_GPU_EXECUTION.md      |     34 -
 .../dataset/training_data_v3_1.jsonl               |    918 -
 .../final_gpu_package/dataset_checksum.txt         |      3 -
 .../final_gpu_package/evaluation/evaluate.py       |    292 -
 .../expected_output_structure.txt                  |     91 -
 .../final_gpu_package_manifest.json                |     96 -
 .../production_model_checksum.txt                  |      2 -
 .../experiments/final_gpu_package/requirements.txt |      8 -
 .../training/experiment_config.json                |     80 -
 .../final_gpu_package/training/train.py            |    421 -
 backend/phase4f/experiments/phase4f_3_results.json |     25 -
 .../experiments/phase4f_3_training_report.txt      |     68 -
 .../experiments/phase4f_3r_freeze_report.txt       |    244 -
 .../phase4f_4_controlled_gpu_experiment_report.txt |    480 -
 .../experiments/phase4f_4_experiment_manifest.json |     40 -
 backend/phase4f/experiments/phase4f_4_results.json |    106 -
 .../experiments/phase4f_4e_cuda_environment.json   |     90 -
 .../phase4f_4e_cuda_environment_report.txt         |    152 -
 backend/phase4f/experiments/requirements.txt       |      8 -
 .../experiments/results/A0/evaluation_results.json |    101 -
 .../phase4f/experiments/results/A0/metadata.json   |      8 -
 .../results/A1/checkpoint_best/config.json         |     27 -
 .../results/A1/checkpoint_best/tokenizer.json      |  29160 -
 .../A1/checkpoint_best/tokenizer_config.json       |     15 -
 .../experiments/results/A1/evaluation_results.json |    100 -
 .../experiments/results/A1/training_metadata.json  |     44 -
 .../results/A2/checkpoint_best/config.json         |     30 -
 .../results/A2/checkpoint_best/tokenizer.json      |  29160 -
 .../A2/checkpoint_best/tokenizer_config.json       |     15 -
 .../experiments/results/A2/evaluation_results.json |    100 -
 .../experiments/results/A2/training_metadata.json  |     44 -
 .../results/A3/checkpoint_best/config.json         |     38 -
 .../results/A3/checkpoint_best/tokenizer.json      | 512185 ------------------
 .../A3/checkpoint_best/tokenizer_config.json       |     24 -
 .../experiments/results/A3/evaluation_results.json |     99 -
 .../experiments/results/A3/training_metadata.json  |     44 -
 .../phase4f/experiments/results/all_results.json   |    402 -
 backend/phase4f/experiments/run_experiment.py      |    623 -
 backend/phase4f/experiments/train.py               |    421 -
 backend/phase4f/freeze_gate.py                     |    906 -
 backend/phase4f/phase4f_1_dataset_audit_report.txt |    178 -
 .../phase4f_2_dataset_quality_gate_report.txt      |    176 -
 .../phase4f/phase4f_2r_dataset_balance_report.txt  |    159 -
 backend/phase4f/phase4f_4r_manifest.json           |     83 -
 backend/phase4f/phase4f_5/configs/a1_config.json   |     38 -
 backend/phase4f/phase4f_5/configs/a2_config.json   |     38 -
 .../phase4f_5/dataset/data_quality_gate.json       |     52 -
 .../phase4f_5/dataset/derived_dataset.jsonl        |    918 -
 .../phase4f_5/dataset/span_alignment_audit.json    |     47 -
 .../phase4f_5/dataset/truncation_audit.json        |     15 -
 .../phase4f_5/diagnostics/a0_forensics.json        |     41 -
 .../phase4f_5/diagnostics/a1_forensics.json        |     41 -
 .../phase4f_5/diagnostics/a2_forensics.json        |     41 -
 .../diagnostics/all_inference_results.json         |   4643 -
 .../phase4f_5/diagnostics/failure_taxonomy.json    |     30 -
 backend/phase4f/phase4f_5/evaluation/evaluate.py   |    301 -
 .../phase4f_5/evaluation/evaluation_protocol.json  |     77 -
 backend/phase4f/phase4f_5/logs/a1_training.json    |     55 -
 backend/phase4f/phase4f_5/logs/a2_training.json    |     55 -
 .../phase4f_5/manifests/experiment_manifest.json   |     86 -
 .../manifests/final_experiment_manifest.json       |     42 -
 .../phase4f_5/manifests/source_integrity.json      |     44 -
 .../phase4f_5/manifests/split_manifest.json        |     89 -
 backend/phase4f/phase4f_5/prepare_experiment.py    |    587 -
 .../reports/phase4f_5a_preparation_report.txt      |    191 -
 .../reports/phase4f_5b_training_report.txt         |    261 -
 backend/phase4f/phase4f_5/results/a0_test.json     |     76 -
 backend/phase4f/phase4f_5/results/a1_test.json     |     75 -
 backend/phase4f/phase4f_5/results/a2_test.json     |     75 -
 backend/phase4f/phase4f_5/results/comparison.json  |     52 -
 backend/phase4f/phase4f_5/run_experiment.py        |    695 -
 backend/phase4f/phase4f_5c/em_f1_gap_analysis.json |    446 -
 backend/phase4f/phase4f_5c/failure_matrix.json     |    110 -
 backend/phase4f/phase4f_5c/generate_analysis.py    |    136 -
 backend/phase4f/phase4f_5c/list_audit.json         |    214 -
 backend/phase4f/phase4f_5c/long_context_audit.json |    236 -
 .../phase4f_5c/normalization_diagnostic.json       |     13 -
 backend/phase4f/phase4f_5c/numeric_audit.json      |    293 -
 .../phase4f_5c/per_category_comparison.json        |    163 -
 .../phase4f/phase4f_5c/phase4f_5c_manifest.json    |     21 -
 .../phase4f/phase4f_5c/production_strengths.json   |     26 -
 .../reports/phase4f_5c_qa_analysis_report.txt      |    324 -
 .../phase4f/phase4f_5c/root_cause_analysis.json    |     25 -
 backend/phase4f/phase4f_5c/table_audit.json        |   1789 -
 backend/phase4f/phase4f_5c/test_composition.json   |     22 -
 .../phase4f_5c/training_curve_analysis.json        |     79 -
 .../phase4f_5d/analysis/a0_benchmark_v1.json       |     82 -
 .../phase4f_5d/analysis/a1_benchmark_v1.json       |     82 -
 .../phase4f_5d/analysis/a2_benchmark_v1.json       |     82 -
 .../phase4f_5d/analysis/benchmark_comparison.json  |    248 -
 .../phase4f_5d/analysis/category_balance.json      |    101 -
 .../phase4f_5d/analysis/duplicate_audit.json       |     45 -
 .../phase4f_5d/analysis/gold_span_validation.json  |      7 -
 .../phase4f/phase4f_5d/analysis/leakage_audit.json |      6 -
 .../phase4f_5d/analysis/test_composition.json      |     14 -
 .../phase4f_5d/analysis/unanswerable_audit.json    |     55 -
 .../phase4f_5d/benchmark/benchmark_checksum.txt    |      2 -
 .../phase4f_5d/benchmark/benchmark_manifest.json   |     64 -
 .../phase4f_5d/benchmark/qa_benchmark_v1.jsonl     |    182 -
 backend/phase4f/phase4f_5d/build_benchmark.py      |    340 -
 .../phase4f/phase4f_5d/phase4f_5d_manifest.json    |     31 -
 .../phase4f_5d_benchmark_hardening_report.txt      |    227 -
 .../phase4f_5e/analysis/capability_matrix.json     |     23 -
 .../analysis/confidence_distribution.json          |    116 -
 .../phase4f_5e/analysis/f1_gain_analysis.json      |     12 -
 .../analysis/next_experiment_matrix.json           |     53 -
 .../analysis/production_vs_experiment.json         |     25 -
 .../phase4f_5e/analysis/root_cause_matrix.json     |     53 -
 .../phase4f_5e/analysis/split_category_matrix.json |     79 -
 .../phase4f_5e/analysis/threshold_sweep.json       |    458 -
 .../phase4f_5e/analysis/training_data_audit.json   |     60 -
 .../phase4f_5e/analysis/unanswerable_audit.json    |    607 -
 .../phase4f/phase4f_5e/phase4f_5e_manifest.json    |     20 -
 .../reports/phase4f_5e_qa_capability_audit.txt     |    245 -
 backend/phase4f/phase4f_5e/run_analysis.py         |    413 -
 .../phase4f_5f/dataset/experiment_f1_manifest.json |     84 -
 .../dataset/experiment_f1_quality_report.json      |     84 -
 .../phase4f_5f/dataset/experiment_f1_split.json    |     74 -
 .../phase4f/phase4f_5f/f2/config/f2_config.json    |      8 -
 .../phase4f_5f/f2/evaluation/f2_benchmark.json     |     84 -
 .../phase4f_5f/f2/evaluation/f2_holdout.json       |     34 -
 .../phase4f_5f/f2/evaluation/f2_validation.json    |     96 -
 .../phase4f/phase4f_5f/f2/logs/f2_training.json    |     57 -
 .../phase4f_5f/f2/manifests/f2_dataset_ids.json    |     10 -
 .../phase4f_5f/f2/manifests/f2_manifest.json       |     64 -
 .../f2/reconciliation/f2_baseline_comparison.json  |     46 -
 .../f2/reconciliation/f2_data_balance_audit.json   |     37 -
 .../f2/reconciliation/f2_label_audit.json          |     26 -
 .../reconciliation/f2_no_answer_logic_audit.json   |     38 -
 .../f2/reconciliation/f2_prediction_audit.json     |     24 -
 .../f2/reconciliation/f2_root_cause_analysis.json  |     61 -
 .../f2/reports/phase4f_5f_f2_final_report.txt      |    288 -
 .../phase4f_5f_f2_reconciliation_report.txt        |    265 -
 .../f2/reports/phase4f_5f_g_threshold_report.txt   |    201 -
 backend/phase4f/phase4f_5f/f2/run_f2.py            |    731 -
 .../f2/threshold_experiment/benchmark_result.json  |    145 -
 .../f2/threshold_experiment/holdout_result.json    |     15 -
 .../f2/threshold_experiment/margin_sweep.json      |   4571 -
 .../threshold_experiment/raw_prediction_audit.json |     12 -
 .../raw_predictions_benchmark.json                 |   3460 -
 .../raw_predictions_holdout.json                   |    268 -
 .../raw_predictions_validation.json                |   1769 -
 .../run_threshold_experiment.py                    |    684 -
 .../threshold_experiment/stability_analysis.json   |    134 -
 .../threshold_experiment_manifest.json             |     52 -
 .../f2/threshold_experiment/threshold_sweep.json   |   1505 -
 .../validation_calibration.json                    |     30 -
 .../phase4f_5f/h/audits/duplicate_audit.json       |     14 -
 .../phase4f/phase4f_5f/h/audits/leakage_audit.json |     14 -
 .../phase4f_5f/h/audits/quality_gate_failures.json |   4291 -
 .../phase4f_5f/h/audits/semantic_audit.json        |   1526 -
 .../phase4f_5f/h/candidates/all_candidates.jsonl   |   1094 -
 .../phase4f/phase4f_5f/h/generate_h_candidates.py  |   1178 -
 .../phase4f/phase4f_5f/h/manifests/h_manifest.json |     55 -
 backend/phase4f/phase4f_5f/h/pools/h10.jsonl       |     57 -
 backend/phase4f/phase4f_5f/h/pools/h20.jsonl       |    114 -
 backend/phase4f/phase4f_5f/h/pools/h30.jsonl       |    171 -
 .../reports/phase4f_5f_h_dataset_design_report.txt |    316 -
 .../phase4f_5f/h1/config/f1_reconciled_ids.json    |    579 -
 .../phase4f/phase4f_5f/h1/config/h1_config.json    |     11 -
 .../phase4f_5f/h1/evaluation/h1_benchmark.json     |    442 -
 .../phase4f_5f/h1/evaluation/h1_holdout.json       |    222 -
 .../phase4f_5f/h1/evaluation/h1_null_analysis.json |    645 -
 .../phase4f_5f/h1/evaluation/h1_validation.json    |    106 -
 .../phase4f/phase4f_5f/h1/logs/h1_training.json    |     54 -
 .../phase4f_5f/h1/manifests/h1_manifest.json       |    271 -
 .../h1/reports/phase4f_5f_h1_final_report.txt      |    232 -
 backend/phase4f/phase4f_5f/h1/run_h1.py            |    789 -
 .../h1_reconciliation/H1_RECONCILIATION_REPORT.md  |    359 -
 .../phase4f/phase4f_5f/h1_reconciliation/README.md |     37 -
 .../phase4f_5f/h1_reconciliation/checksums.txt     |     10 -
 .../h1_reconciliation/h1_count_reconciliation.json |     48 -
 .../h1_reconciliation/h1_label_integrity.json      |     56 -
 .../h1_reconciliation/h1_metric_recalculation.json |     72 -
 .../h1_reconciliation/h1_no_answer_analysis.json   |     69 -
 .../h1_reconciliation/h1_null_score_analysis.json  |     42 -
 .../h1_reconciliation/h1_overlap_report.json       |     66 -
 .../h1_reconciliation/h1_protocol_audit.json       |    131 -
 .../h1_reconciled_comparison.json                  |     79 -
 .../phase4f_5f_f1_reconciliation_manifest.json     |     78 -
 .../reconciliation/dataset_reconciliation.json     |     96 -
 .../reconciliation/final_holdout_ids.json          |     21 -
 .../reconciliation/final_training_ids.json         |    516 -
 .../reconciliation/final_validation_ids.json       |    103 -
 .../reconciliation/invalid_span_audit.json         |    102 -
 .../reconciliation/training_protocol_audit.json    |     51 -
 .../phase4f_5f/recovery/artifact_inventory.json    |     68 -
 .../recovery/gpu_environment_report.json           |    117 -
 .../phase4f_5f/recovery/gpu_environment_report.txt |    163 -
 .../recovery/phase4f_5f_recovery_report.txt        |    228 -
 .../phase4f_5f/recovery/recovery_manifest.json     |     65 -
 .../reports/phase4f_5f_f1_preparation_report.txt   |    238 -
 .../phase4f_5f_f1_reconciliation_report.txt        |    236 -
 backend/phase4f/phase4f_5f/run_experiment.py       |    977 -
 backend/phase4f/quality_gate.py                    |   1149 -
 .../phase4f/reconciliation/a0_reproduction.json    |     34 -
 .../phase4f/reconciliation/checkpoint_audit.json   |     52 -
 .../cross_phase_evaluation_compatibility.json      |     58 -
 .../reconciliation/dataset_label_audit.json        |     70 -
 .../reconciliation/evaluation_parity_matrix.json   |     99 -
 .../experiment_artifact_inventory.json             |    203 -
 .../failure_taxonomy_reconciliation.json           |     95 -
 .../reconciliation/manual_forensic_traces.json     |    114 -
 .../reconciliation/model_initialization_audit.json |     61 -
 .../phase4f_4r_reconciliation_report.txt           |    312 -
 .../phase4f/reconciliation/token_span_audit.json   |     47 -
 .../training_configuration_audit.json              |     92 -
 backend/phase4f/training/__init__.py               |      1 -
 backend/phase4f/training/configs.py                |     53 -
 backend/phase4f/training/environment.json          |     18 -
 backend/phase4f/training/train.py                  |    302 -
 .../phase4f_qa_architecture_experiment_report.txt  |    307 -
 backend/pytest.ini                                 |     13 +
 backend/reliability/routes.py                      |     70 +
 backend/requirements.txt                           |     39 +
 backend/start_server.py                            |     43 -
 backend/test_browser_flow.py                       |    124 -
 backend/test_document_flow.py                      |    245 -
 backend/test_embedding_flow.py                     |    278 -
 backend/test_phase3d_evaluation.py                 |    684 -
 backend/test_phase3d_upload_integration.py         |    477 -
 backend/test_phase3e_integration.py                |    404 -
 backend/test_phase3e_validation.py                 |    720 -
 backend/test_phase3f_evaluation.py                 |   1062 -
 backend/test_phase4b_evaluation.py                 |    885 -
 backend/test_phase4c_diagnostics.py                |    591 -
 backend/test_phase6_reliability.py                 |    195 -
 backend/test_rag_flow.py                           |    212 -
 backend/test_real_browser.py                       |    425 -
 backend/tests/conftest.py                          |    157 +-
 backend/tests/integration_http.py                  |     63 -
 backend/tests/phase3d_corpus.py                    |    575 -
 backend/tests/phase4b_corpus.py                    |    980 -
 backend/tests/test_answer_span.py                  |    408 -
 backend/tests/test_auth.py                         |    245 -
 backend/tests/test_brain_orchestration.py          |    770 -
 backend/tests/test_brain_types.py                  |    455 -
 backend/tests/test_chat_unit.py                    |    313 -
 backend/tests/test_config_security.py              |     95 -
 backend/tests/test_cors.py                         |    112 -
 backend/tests/test_database_url.py                 |     43 -
 backend/tests/test_file_validation.py              |    419 -
 backend/tests/test_outcomes.py                     |    118 -
 backend/tests/test_phase3d_chunking.py             |    595 -
 backend/tests/test_phase3d_context.py              |    274 -
 backend/tests/test_phase3d_reconciliation.py       |    416 -
 backend/tests/test_phase3e_processing.py           |    311 -
 backend/tests/test_qa_answer_reconstruction.py     |    418 -
 backend/tests/test_real_e2e_validation.py          |    394 -
 backend/tests/test_settings.py                     |    312 -
 backend/tests/test_sql_safety.py                   |     83 -
 backend/tests/test_structured_extraction.py        |    652 -
 backend/tests/test_verification_integrity.py       |    150 -
 backend/verification/routes.py                     |    137 +-
 package-lock.json                                  |     45 -
 package.json                                       |      1 +
 runbooks/README.md                                 |     17 +-
 runbooks/database-failure.md                       |      5 +-
 runbooks/migration-failure.md                      |     34 +-
 src/lib/api.ts                                     |    298 +
 src/pages/ReliabilityPage.tsx                      |    250 +-
 src/pages/VerificationPage.tsx                     |    426 +-
 src/pages/WorkspacePage.tsx                        |    125 +-
 src/types/index.ts                                 |     62 +
 vite.config.ts                                     |     64 +-
 329 files changed, 5150 insertions(+), 694944 deletions(-)
```

### 8.4 Final: git diff --name-status (tracked worktree)

```text
M	.gitignore
M	DOCUMIND_PROJECT_CONTEXT.md
M	backend/brain/__init__.py
M	backend/brain/adapters.py
M	backend/brain/response.py
M	backend/brain/types.py
M	backend/chat/qa_model.py
M	backend/chat/rag.py
M	backend/chat/routes.py
M	backend/documents/models.py
M	backend/documents/processing.py
M	backend/documents/routes.py
M	backend/documents/schemas.py
M	backend/embeddings/model.py
M	backend/embeddings/routes.py
M	backend/evaluation/harness/corpus.py
D	backend/evaluation/harness/evaluator.py
M	backend/main.py
M	backend/migrations/env.py
D	backend/phase3d_evaluation_report.json
D	backend/phase3f_evaluation_report.json
D	backend/phase3f_validation_report.txt
D	backend/phase3g_pipeline_audit.txt
D	backend/phase4a_qa_failure_audit.txt
D	backend/phase4b_evaluation_report.json
D	backend/phase4b_qa_evaluation_report.txt
D	backend/phase4c_failure_matrix.json
D	backend/phase4c_qa_failure_isolation_report.txt
D	backend/phase4d/__init__.py
D	backend/phase4d/__main__.py
D	backend/phase4d/evaluate_candidates.py
D	backend/phase4d/generate_report.py
D	backend/phase4d/oracle_eval.py
D	backend/phase4d/reconciliation.py
D	backend/phase4d/train.py
D	backend/phase4d/training_data.py
D	backend/phase4d_1_reconciliation.json
D	backend/phase4d_1_reconciliation_report.txt
D	backend/phase4d_experiment_results.json
D	backend/phase4d_oracle_baseline_results.json
D	backend/phase4d_qa_model_improvement_report.txt
D	backend/phase4e/__init__.py
D	backend/phase4e/capability_analysis.py
D	backend/phase4e/generate_report.py
D	backend/phase4e_capability_matrix.json
D	backend/phase4e_diagnostic_results.json
D	backend/phase4e_qa_architecture_analysis.txt
D	backend/phase4f/__init__.py
D	backend/phase4f/balance_gate.py
D	backend/phase4f/dataset/__init__.py
D	backend/phase4f/dataset/dataset_manifest.json
D	backend/phase4f/dataset/dataset_manifest_v3.json
D	backend/phase4f/dataset/dataset_manifest_v3_1.json
D	backend/phase4f/dataset/dataset_metadata.json
D	backend/phase4f/dataset/dataset_quality_report.json
D	backend/phase4f/dataset/dataset_quality_report_v3.json
D	backend/phase4f/dataset/dataset_quality_report_v3_1.json
D	backend/phase4f/dataset/expand_and_audit.py
D	backend/phase4f/dataset/generator.py
D	backend/phase4f/dataset/training_data.jsonl
D	backend/phase4f/dataset/training_data_v3.jsonl
D	backend/phase4f/dataset/training_data_v3_1.jsonl
D	backend/phase4f/experiments/evaluate.py
D	backend/phase4f/experiments/experiment_manifest.json
D	backend/phase4f/experiments/final_gpu_package/README_GPU_EXECUTION.md
D	backend/phase4f/experiments/final_gpu_package/dataset/training_data_v3_1.jsonl
D	backend/phase4f/experiments/final_gpu_package/dataset_checksum.txt
D	backend/phase4f/experiments/final_gpu_package/evaluation/evaluate.py
D	backend/phase4f/experiments/final_gpu_package/expected_output_structure.txt
D	backend/phase4f/experiments/final_gpu_package/final_gpu_package_manifest.json
D	backend/phase4f/experiments/final_gpu_package/production_model_checksum.txt
D	backend/phase4f/experiments/final_gpu_package/requirements.txt
D	backend/phase4f/experiments/final_gpu_package/training/experiment_config.json
D	backend/phase4f/experiments/final_gpu_package/training/train.py
D	backend/phase4f/experiments/phase4f_3_results.json
D	backend/phase4f/experiments/phase4f_3_training_report.txt
D	backend/phase4f/experiments/phase4f_3r_freeze_report.txt
D	backend/phase4f/experiments/phase4f_4_controlled_gpu_experiment_report.txt
D	backend/phase4f/experiments/phase4f_4_experiment_manifest.json
D	backend/phase4f/experiments/phase4f_4_results.json
D	backend/phase4f/experiments/phase4f_4e_cuda_environment.json
D	backend/phase4f/experiments/phase4f_4e_cuda_environment_report.txt
D	backend/phase4f/experiments/requirements.txt
D	backend/phase4f/experiments/results/A0/evaluation_results.json
D	backend/phase4f/experiments/results/A0/metadata.json
D	backend/phase4f/experiments/results/A1/checkpoint_best/config.json
D	backend/phase4f/experiments/results/A1/checkpoint_best/tokenizer.json
D	backend/phase4f/experiments/results/A1/checkpoint_best/tokenizer_config.json
D	backend/phase4f/experiments/results/A1/evaluation_results.json
D	backend/phase4f/experiments/results/A1/training_metadata.json
D	backend/phase4f/experiments/results/A2/checkpoint_best/config.json
D	backend/phase4f/experiments/results/A2/checkpoint_best/tokenizer.json
D	backend/phase4f/experiments/results/A2/checkpoint_best/tokenizer_config.json
D	backend/phase4f/experiments/results/A2/evaluation_results.json
D	backend/phase4f/experiments/results/A2/training_metadata.json
D	backend/phase4f/experiments/results/A3/checkpoint_best/config.json
D	backend/phase4f/experiments/results/A3/checkpoint_best/tokenizer.json
D	backend/phase4f/experiments/results/A3/checkpoint_best/tokenizer_config.json
D	backend/phase4f/experiments/results/A3/evaluation_results.json
D	backend/phase4f/experiments/results/A3/training_metadata.json
D	backend/phase4f/experiments/results/all_results.json
D	backend/phase4f/experiments/run_experiment.py
D	backend/phase4f/experiments/train.py
D	backend/phase4f/freeze_gate.py
D	backend/phase4f/phase4f_1_dataset_audit_report.txt
D	backend/phase4f/phase4f_2_dataset_quality_gate_report.txt
D	backend/phase4f/phase4f_2r_dataset_balance_report.txt
D	backend/phase4f/phase4f_4r_manifest.json
D	backend/phase4f/phase4f_5/configs/a1_config.json
D	backend/phase4f/phase4f_5/configs/a2_config.json
D	backend/phase4f/phase4f_5/dataset/data_quality_gate.json
D	backend/phase4f/phase4f_5/dataset/derived_dataset.jsonl
D	backend/phase4f/phase4f_5/dataset/span_alignment_audit.json
D	backend/phase4f/phase4f_5/dataset/truncation_audit.json
D	backend/phase4f/phase4f_5/diagnostics/a0_forensics.json
D	backend/phase4f/phase4f_5/diagnostics/a1_forensics.json
D	backend/phase4f/phase4f_5/diagnostics/a2_forensics.json
D	backend/phase4f/phase4f_5/diagnostics/all_inference_results.json
D	backend/phase4f/phase4f_5/diagnostics/failure_taxonomy.json
D	backend/phase4f/phase4f_5/evaluation/evaluate.py
D	backend/phase4f/phase4f_5/evaluation/evaluation_protocol.json
D	backend/phase4f/phase4f_5/logs/a1_training.json
D	backend/phase4f/phase4f_5/logs/a2_training.json
D	backend/phase4f/phase4f_5/manifests/experiment_manifest.json
D	backend/phase4f/phase4f_5/manifests/final_experiment_manifest.json
D	backend/phase4f/phase4f_5/manifests/source_integrity.json
D	backend/phase4f/phase4f_5/manifests/split_manifest.json
D	backend/phase4f/phase4f_5/prepare_experiment.py
D	backend/phase4f/phase4f_5/reports/phase4f_5a_preparation_report.txt
D	backend/phase4f/phase4f_5/reports/phase4f_5b_training_report.txt
D	backend/phase4f/phase4f_5/results/a0_test.json
D	backend/phase4f/phase4f_5/results/a1_test.json
D	backend/phase4f/phase4f_5/results/a2_test.json
D	backend/phase4f/phase4f_5/results/comparison.json
D	backend/phase4f/phase4f_5/run_experiment.py
D	backend/phase4f/phase4f_5c/em_f1_gap_analysis.json
D	backend/phase4f/phase4f_5c/failure_matrix.json
D	backend/phase4f/phase4f_5c/generate_analysis.py
D	backend/phase4f/phase4f_5c/list_audit.json
D	backend/phase4f/phase4f_5c/long_context_audit.json
D	backend/phase4f/phase4f_5c/normalization_diagnostic.json
D	backend/phase4f/phase4f_5c/numeric_audit.json
D	backend/phase4f/phase4f_5c/per_category_comparison.json
D	backend/phase4f/phase4f_5c/phase4f_5c_manifest.json
D	backend/phase4f/phase4f_5c/production_strengths.json
D	backend/phase4f/phase4f_5c/reports/phase4f_5c_qa_analysis_report.txt
D	backend/phase4f/phase4f_5c/root_cause_analysis.json
D	backend/phase4f/phase4f_5c/table_audit.json
D	backend/phase4f/phase4f_5c/test_composition.json
D	backend/phase4f/phase4f_5c/training_curve_analysis.json
D	backend/phase4f/phase4f_5d/analysis/a0_benchmark_v1.json
D	backend/phase4f/phase4f_5d/analysis/a1_benchmark_v1.json
D	backend/phase4f/phase4f_5d/analysis/a2_benchmark_v1.json
D	backend/phase4f/phase4f_5d/analysis/benchmark_comparison.json
D	backend/phase4f/phase4f_5d/analysis/category_balance.json
D	backend/phase4f/phase4f_5d/analysis/duplicate_audit.json
D	backend/phase4f/phase4f_5d/analysis/gold_span_validation.json
D	backend/phase4f/phase4f_5d/analysis/leakage_audit.json
D	backend/phase4f/phase4f_5d/analysis/test_composition.json
D	backend/phase4f/phase4f_5d/analysis/unanswerable_audit.json
D	backend/phase4f/phase4f_5d/benchmark/benchmark_checksum.txt
D	backend/phase4f/phase4f_5d/benchmark/benchmark_manifest.json
D	backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl
D	backend/phase4f/phase4f_5d/build_benchmark.py
D	backend/phase4f/phase4f_5d/phase4f_5d_manifest.json
D	backend/phase4f/phase4f_5d/reports/phase4f_5d_benchmark_hardening_report.txt
D	backend/phase4f/phase4f_5e/analysis/capability_matrix.json
D	backend/phase4f/phase4f_5e/analysis/confidence_distribution.json
D	backend/phase4f/phase4f_5e/analysis/f1_gain_analysis.json
D	backend/phase4f/phase4f_5e/analysis/next_experiment_matrix.json
D	backend/phase4f/phase4f_5e/analysis/production_vs_experiment.json
D	backend/phase4f/phase4f_5e/analysis/root_cause_matrix.json
D	backend/phase4f/phase4f_5e/analysis/split_category_matrix.json
D	backend/phase4f/phase4f_5e/analysis/threshold_sweep.json
D	backend/phase4f/phase4f_5e/analysis/training_data_audit.json
D	backend/phase4f/phase4f_5e/analysis/unanswerable_audit.json
D	backend/phase4f/phase4f_5e/phase4f_5e_manifest.json
D	backend/phase4f/phase4f_5e/reports/phase4f_5e_qa_capability_audit.txt
D	backend/phase4f/phase4f_5e/run_analysis.py
D	backend/phase4f/phase4f_5f/dataset/experiment_f1_manifest.json
D	backend/phase4f/phase4f_5f/dataset/experiment_f1_quality_report.json
D	backend/phase4f/phase4f_5f/dataset/experiment_f1_split.json
D	backend/phase4f/phase4f_5f/f2/config/f2_config.json
D	backend/phase4f/phase4f_5f/f2/evaluation/f2_benchmark.json
D	backend/phase4f/phase4f_5f/f2/evaluation/f2_holdout.json
D	backend/phase4f/phase4f_5f/f2/evaluation/f2_validation.json
D	backend/phase4f/phase4f_5f/f2/logs/f2_training.json
D	backend/phase4f/phase4f_5f/f2/manifests/f2_dataset_ids.json
D	backend/phase4f/phase4f_5f/f2/manifests/f2_manifest.json
D	backend/phase4f/phase4f_5f/f2/reconciliation/f2_baseline_comparison.json
D	backend/phase4f/phase4f_5f/f2/reconciliation/f2_data_balance_audit.json
D	backend/phase4f/phase4f_5f/f2/reconciliation/f2_label_audit.json
D	backend/phase4f/phase4f_5f/f2/reconciliation/f2_no_answer_logic_audit.json
D	backend/phase4f/phase4f_5f/f2/reconciliation/f2_prediction_audit.json
D	backend/phase4f/phase4f_5f/f2/reconciliation/f2_root_cause_analysis.json
D	backend/phase4f/phase4f_5f/f2/reports/phase4f_5f_f2_final_report.txt
D	backend/phase4f/phase4f_5f/f2/reports/phase4f_5f_f2_reconciliation_report.txt
D	backend/phase4f/phase4f_5f/f2/reports/phase4f_5f_g_threshold_report.txt
D	backend/phase4f/phase4f_5f/f2/run_f2.py
D	backend/phase4f/phase4f_5f/f2/threshold_experiment/benchmark_result.json
D	backend/phase4f/phase4f_5f/f2/threshold_experiment/holdout_result.json
D	backend/phase4f/phase4f_5f/f2/threshold_experiment/margin_sweep.json
D	backend/phase4f/phase4f_5f/f2/threshold_experiment/raw_prediction_audit.json
D	backend/phase4f/phase4f_5f/f2/threshold_experiment/raw_predictions_benchmark.json
D	backend/phase4f/phase4f_5f/f2/threshold_experiment/raw_predictions_holdout.json
D	backend/phase4f/phase4f_5f/f2/threshold_experiment/raw_predictions_validation.json
D	backend/phase4f/phase4f_5f/f2/threshold_experiment/run_threshold_experiment.py
D	backend/phase4f/phase4f_5f/f2/threshold_experiment/stability_analysis.json
D	backend/phase4f/phase4f_5f/f2/threshold_experiment/threshold_experiment_manifest.json
D	backend/phase4f/phase4f_5f/f2/threshold_experiment/threshold_sweep.json
D	backend/phase4f/phase4f_5f/f2/threshold_experiment/validation_calibration.json
D	backend/phase4f/phase4f_5f/h/audits/duplicate_audit.json
D	backend/phase4f/phase4f_5f/h/audits/leakage_audit.json
D	backend/phase4f/phase4f_5f/h/audits/quality_gate_failures.json
D	backend/phase4f/phase4f_5f/h/audits/semantic_audit.json
D	backend/phase4f/phase4f_5f/h/candidates/all_candidates.jsonl
D	backend/phase4f/phase4f_5f/h/generate_h_candidates.py
D	backend/phase4f/phase4f_5f/h/manifests/h_manifest.json
D	backend/phase4f/phase4f_5f/h/pools/h10.jsonl
D	backend/phase4f/phase4f_5f/h/pools/h20.jsonl
D	backend/phase4f/phase4f_5f/h/pools/h30.jsonl
D	backend/phase4f/phase4f_5f/h/reports/phase4f_5f_h_dataset_design_report.txt
D	backend/phase4f/phase4f_5f/h1/config/f1_reconciled_ids.json
D	backend/phase4f/phase4f_5f/h1/config/h1_config.json
D	backend/phase4f/phase4f_5f/h1/evaluation/h1_benchmark.json
D	backend/phase4f/phase4f_5f/h1/evaluation/h1_holdout.json
D	backend/phase4f/phase4f_5f/h1/evaluation/h1_null_analysis.json
D	backend/phase4f/phase4f_5f/h1/evaluation/h1_validation.json
D	backend/phase4f/phase4f_5f/h1/logs/h1_training.json
D	backend/phase4f/phase4f_5f/h1/manifests/h1_manifest.json
D	backend/phase4f/phase4f_5f/h1/reports/phase4f_5f_h1_final_report.txt
D	backend/phase4f/phase4f_5f/h1/run_h1.py
D	backend/phase4f/phase4f_5f/h1_reconciliation/H1_RECONCILIATION_REPORT.md
D	backend/phase4f/phase4f_5f/h1_reconciliation/README.md
D	backend/phase4f/phase4f_5f/h1_reconciliation/checksums.txt
D	backend/phase4f/phase4f_5f/h1_reconciliation/h1_count_reconciliation.json
D	backend/phase4f/phase4f_5f/h1_reconciliation/h1_label_integrity.json
D	backend/phase4f/phase4f_5f/h1_reconciliation/h1_metric_recalculation.json
D	backend/phase4f/phase4f_5f/h1_reconciliation/h1_no_answer_analysis.json
D	backend/phase4f/phase4f_5f/h1_reconciliation/h1_null_score_analysis.json
D	backend/phase4f/phase4f_5f/h1_reconciliation/h1_overlap_report.json
D	backend/phase4f/phase4f_5f/h1_reconciliation/h1_protocol_audit.json
D	backend/phase4f/phase4f_5f/h1_reconciliation/h1_reconciled_comparison.json
D	backend/phase4f/phase4f_5f/phase4f_5f_f1_reconciliation_manifest.json
D	backend/phase4f/phase4f_5f/reconciliation/dataset_reconciliation.json
D	backend/phase4f/phase4f_5f/reconciliation/final_holdout_ids.json
D	backend/phase4f/phase4f_5f/reconciliation/final_training_ids.json
D	backend/phase4f/phase4f_5f/reconciliation/final_validation_ids.json
D	backend/phase4f/phase4f_5f/reconciliation/invalid_span_audit.json
D	backend/phase4f/phase4f_5f/reconciliation/training_protocol_audit.json
D	backend/phase4f/phase4f_5f/recovery/artifact_inventory.json
D	backend/phase4f/phase4f_5f/recovery/gpu_environment_report.json
D	backend/phase4f/phase4f_5f/recovery/gpu_environment_report.txt
D	backend/phase4f/phase4f_5f/recovery/phase4f_5f_recovery_report.txt
D	backend/phase4f/phase4f_5f/recovery/recovery_manifest.json
D	backend/phase4f/phase4f_5f/reports/phase4f_5f_f1_preparation_report.txt
D	backend/phase4f/phase4f_5f/reports/phase4f_5f_f1_reconciliation_report.txt
D	backend/phase4f/phase4f_5f/run_experiment.py
D	backend/phase4f/quality_gate.py
D	backend/phase4f/reconciliation/a0_reproduction.json
D	backend/phase4f/reconciliation/checkpoint_audit.json
D	backend/phase4f/reconciliation/cross_phase_evaluation_compatibility.json
D	backend/phase4f/reconciliation/dataset_label_audit.json
D	backend/phase4f/reconciliation/evaluation_parity_matrix.json
D	backend/phase4f/reconciliation/experiment_artifact_inventory.json
D	backend/phase4f/reconciliation/failure_taxonomy_reconciliation.json
D	backend/phase4f/reconciliation/manual_forensic_traces.json
D	backend/phase4f/reconciliation/model_initialization_audit.json
D	backend/phase4f/reconciliation/phase4f_4r_reconciliation_report.txt
D	backend/phase4f/reconciliation/token_span_audit.json
D	backend/phase4f/reconciliation/training_configuration_audit.json
D	backend/phase4f/training/__init__.py
D	backend/phase4f/training/configs.py
D	backend/phase4f/training/environment.json
D	backend/phase4f/training/train.py
D	backend/phase4f_qa_architecture_experiment_report.txt
M	backend/pytest.ini
M	backend/reliability/routes.py
M	backend/requirements.txt
D	backend/start_server.py
D	backend/test_browser_flow.py
D	backend/test_document_flow.py
D	backend/test_embedding_flow.py
D	backend/test_phase3d_evaluation.py
D	backend/test_phase3d_upload_integration.py
D	backend/test_phase3e_integration.py
D	backend/test_phase3e_validation.py
D	backend/test_phase3f_evaluation.py
D	backend/test_phase4b_evaluation.py
D	backend/test_phase4c_diagnostics.py
D	backend/test_phase6_reliability.py
D	backend/test_rag_flow.py
D	backend/test_real_browser.py
M	backend/tests/conftest.py
D	backend/tests/integration_http.py
D	backend/tests/phase3d_corpus.py
D	backend/tests/phase4b_corpus.py
D	backend/tests/test_answer_span.py
D	backend/tests/test_auth.py
D	backend/tests/test_brain_orchestration.py
D	backend/tests/test_brain_types.py
D	backend/tests/test_chat_unit.py
D	backend/tests/test_config_security.py
D	backend/tests/test_cors.py
D	backend/tests/test_database_url.py
D	backend/tests/test_file_validation.py
D	backend/tests/test_outcomes.py
D	backend/tests/test_phase3d_chunking.py
D	backend/tests/test_phase3d_context.py
D	backend/tests/test_phase3d_reconciliation.py
D	backend/tests/test_phase3e_processing.py
D	backend/tests/test_qa_answer_reconstruction.py
D	backend/tests/test_real_e2e_validation.py
D	backend/tests/test_settings.py
D	backend/tests/test_sql_safety.py
D	backend/tests/test_structured_extraction.py
D	backend/tests/test_verification_integrity.py
M	backend/verification/routes.py
M	package-lock.json
M	package.json
M	runbooks/README.md
M	runbooks/database-failure.md
M	runbooks/migration-failure.md
M	src/lib/api.ts
M	src/pages/ReliabilityPage.tsx
M	src/pages/VerificationPage.tsx
M	src/pages/WorkspacePage.tsx
M	src/types/index.ts
M	vite.config.ts
```

### 8.5 Final: git status --short --untracked-files=all (root cwd)

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

## 9. Completion-review continuation — 2026-10-12

### 9.1 Verdict and participation

**PARTIALLY COMPLETE — security acceptance BLOCKED. PostgreSQL verification remains NO-GO.** This addendum supersedes broader safety claims in sections 2, 3 and 7: central guards and documented main entry points refuse, but not every callable destructive helper is guarded.

Only Coordinator execution occurred. Available tools provide no specialist dispatch. The Coordinator performed the authorization, target-binding, test-side-effect and evidence reviews; SECURITY_AGENT, DATABASE_AGENT, TEST_AGENT and VERIFIER did not execute independently. Independent reviews remain outstanding. EVALUATION_AGENT remediation is requested below; no implementation/test ownership boundary was crossed in this continuation.

Only this report is intentionally changed by this continuation. A temporary addendum assembly artifact is moved outside the repository after incorporation. No production or test source was edited. Existing tracked and untracked work was preserved.

### 9.2 Current-state correction and latest failure

The latest saved failed draft run (`/tmp/s16k_unit_eval3.txt`) reports two metrics tests failing with `RuntimeError: There is no current event loop in thread 'MainThread'`, not a remaining lifecycle exception-expectation failure. Current lifecycle tests already expect `UnsafeEvaluationTarget`, justified because the guards explicitly raise that subclass of RuntimeError. No assertion correction is necessary or made.

`DisposalProof` is currently inert compatibility data. `_proof_is_live` always returns false, `record_created_database` always raises, and `release_database_proof` always raises. There is no live-lifecycle registry and no autouse registry-reset fixture. The previously reported 566 tests and successful lifecycle closure do not establish current implementation behavior.

### 9.3 Security findings and invariant disposition

**F-K1 — HIGH, unresolved: direct cleanup helpers bypass main-entry authorization.** Ordinary direct invocation with a caller-supplied session does not require monkeypatching the guard. Row ownership predicates narrow deletes but do not establish lifecycle authorization or engine identity. Source evidence:

| File under `backend/evaluation/experiments/` | Function / definition line | Observed behavior |
| --- | --- | --- |
| `run_phase3d_upload_integration.py` | `cleanup_harness_rows`, 118 | caller session and user id; four execute calls, no authorization |
| `run_phase3d_evaluation.py` | `cleanup_harness_rows`, 549 | caller session/user ids; deletes without authorization |
| `run_phase3e_integration.py` | `cleanup_harness_rows`, 83 | same missing function-level gate |
| `run_phase3e_validation.py` | `cleanup_harness_rows`, 82 | same missing function-level gate |
| `run_phase3f_evaluation.py` | `cleanup_harness_rows`, 718 | same missing function-level gate |
| `run_phase4b_evaluation.py` | `cleanup_harness_rows`, 698 | same missing function-level gate |
| `run_dual_path_ablation.py` | `_delete_user_data`, 861 | caller session; query followed by scoped deletes; no authorization |
| `run_table_evidence_measurement.py` | `teardown`, 479 | caller session; deletes user by email and commits; no authorization |

`run_table_evidence_measurement.run_once(engine, ...)` (640) is an additional alternate engine-taking entry: it creates a session factory and calls `teardown` without authorizing the supplied engine. Structure-runner `run_once` functions also lack local authorization; their globals ordinarily start unbound, but configured/caller-supplied globals are not an authorization boundary. These paths were read/parsed only, never invoked. This finding contradicts an unqualified statement that all row cleanup is blocked.

**F-K2 — operational lifecycle absent, unresolved.** Creation permission is separate from evidence in the API, but both refuse. Constructed, copied, differently targeted and repeated claims cannot obtain permission through the tested guards. No successful lifecycle can open or close, so post-closure reuse and created-by-corresponding-lifecycle drop are not positively established. Existing-name refusal is checked with a pure supplied boolean and source order, not a database existence probe.

**F-K3 — actual target/engine identity not established.** `assert_engine_matches_target` reads only `engine.url`; it makes no connection. Actual server/database identity, restricted-role enforcement and lifecycle ownership are absent. `run_full_validation` has an unconditional row-authorization gate before engine imports/creation and a configured-engine gate before session construction. With intact functions, an alternate caller of that function cannot pass its first guard. This is source evidence and pure guard behavior, not invocation or a sandbox against arbitrary same-process code. The configured engine gate's docstring describes proof-first order, but the implementation checks engine URL first; both ultimately refuse. No actual-connection verification is claimed.

**F-K4 — stale documentation.** Some module/function docstrings still describe valid proofs, drop/recreate and enabled provisioning. Executable gates supersede those descriptions; the comments must not be used as authorization. This report records the inconsistency without unrelated source edits.

Nine directly gated runner sources are covered by the contract tests: phase3d evaluation/upload, phase3e integration/validation, phase3f, phase4b, dual-path ablation, table evidence and structure element. RRF calibration and structure confirmation use the shared guard. Main entry-point gates remain intact; the eight helper gaps above remain unresolved. These are distinct claims.

Application-name protection remains intact in the central/fixture guards, including aliases and case/encoding checks. It is not enforced inside the ungated helper functions. No test-registry reset can weaken production safeguards because no registry/reset exists; this is absence, not successful test-state-reset verification.

### 9.4 Approved tests and exact results

Before execution, inspected test sources, imports, parent conftest fixtures, fixture resolvers and called guards. Approved tests exercise pure URL/proof guards, source ordering, in-memory callback metrics, and poison/stubbed structure binding. The structure-binding tests deliberately replace disposal authorization only for binding-order tests; their separate refusal test restores the real guard. Such tests are not evidence of successful authorization.

Commands run from `backend`, each redirected to its log, followed by `result=$?; cat LOG; printf '\npytest_exit=%s\n' "$result"; exit "$result"` so printing did not mask status:

```bash
PYTHONDONTWRITEBYTECODE=1 ./venv/Scripts/python.exe -B -m pytest -q tests/unit/evaluation/test_lifecycle_authorization.py -p no:cacheprovider > /tmp/s16k_review_lifecycle.txt 2>&1
```

**34 passed in 0.15s; exit 0.**

```bash
PYTHONDONTWRITEBYTECODE=1 ./venv/Scripts/python.exe -B -m pytest -q tests/unit/evaluation/test_disposable_database_authorization.py tests/unit/evaluation/test_disposal_authorization_contract.py tests/unit/evaluation/test_phase3_runner_target_order.py tests/unit/evaluation/test_isolation_guard_identity.py tests/unit/evaluation/test_metrics.py tests/unit/evaluation/test_unsupported_answer_denominator.py tests/unit/evaluation/test_structure_runner_guard_order.py -p no:cacheprovider > /tmp/s16k_review_approved.txt 2>&1
```

**236 passed, 1 warning in 0.72s; exit 0.** Total across the two nonoverlapping runs: **270 passed**. Existing pytest-asyncio notices about the default loop scope and redefined event_loop were not suppressed. No test failed in this continuation. Tests/assertions were not modified, skipped or weakened to obtain these results.

Compilation ran via `./venv/Scripts/python.exe -B -` from backend with this body (S16K_TMP set to Git Bash `/tmp` converted using `cygpath -w`):

```python
from pathlib import Path
import os, py_compile
out = Path(os.environ['S16K_TMP']) / 's16k_review_compile'
out.mkdir(exist_ok=True)
paths = [Path('evaluation/isolation.py'), Path('tests/fixtures/integration_db.py'),
         Path('tests/integration/rag/test_real_e2e_validation.py'),
         Path('tests/unit/evaluation/conftest.py'),
         *sorted(Path('tests/unit/evaluation').glob('test_*.py'))]
for i, path in enumerate(paths):
    py_compile.compile(str(path), cfile=str(out / f'{i}.pyc'), doraise=True)
```

**27 files compiled, exit 0.** Bytecode was written outside the repository; this did not import or execute those files. Compilation is not static typechecking.

### 9.5 Checks deliberately not run / side-effect restrictions

The entire evaluation test directory is **NOT approved as a database-free command**. Six cleanup-scope files use SQLite db_session and invoke cleanup and main; legacy-runner tests invoke main; test_evaluation_isolation can fall back to real settings and read `.env`; heading-corpus tests use TemporaryDirectory cleanup; artifact/report/corpus tests perform temporary writes or overwrite files, and some import production modules. Runner-pre-engine tests launch subprocess imports and include settings paths. Those files were excluded from execution, not marked passing or programmatically skipped. Even SQLite access violates this task's no-database rule. The narrowed tests do not fulfill a claim that the full directory passed.

NOT RUN: any database connection/probe (including SQLite), provisioning fixture/context manager, CREATE/DROP, migration/Alembic, evaluation main/amain/run_once, E2E or cleanup function; no filesystem deletion was invoked. No `.env` secrets were read/printed. No reset, clean, stash, revert, stage, commit or push was run. Subprocesses explicitly run were Git, Python compilation/source inspection, and pytest, not database tools or runner execution. No frontend build/static typecheck was needed for this report-only continuation. The prior repository whitespace failure remains historical; it was not repaired or rerun without relevant changes.

### 9.6 Diff and preservation evidence

Initial/final HEAD: `6baaa2a0773df66e5fb26814afbe67647fb43435`. Both root-relative ordinary status listings contain 384 entries; expanded listings contain 1136. Full expanded initial/final path listings follow. Their byte-for-byte comparison is equal. This does NOT establish unchanged content: this untracked report changes without changing its status entry.

Initial/final full tracked binary diff snapshots were saved to `/tmp/s16k_review_initial_tracked.diff` and `/tmp/s16k_review_final_tracked.diff`; byte-for-byte comparison is equal. The tracked worktree diff is pre-existing; no tracked edit was introduced. Relevant current untracked implementation/test contents were inspected directly, not inferred from Git's omission of untracked files.

Additionally SHA-256 compared 40 current source files (central contract, fixture, E2E module, evaluation-test Python files, and experiment `run_*.py`) before/after verification: **zero source content changes**. This is bounded content evidence, not a claim about all untracked repository content or historical changes for which no initial byte snapshot exists. Initial and final snapshots below include the already-existing report path. Appending the addendum itself does not alter a status/path classification.

### 9.7 HELP REQUEST — remediation blocked on owning agent

Task: Finish lifecycle authorization and close direct cleanup bypasses.
Blocked by: No EVALUATION_AGENT dispatch and Coordinator does not own implementation; enforceable authority/actual connection identity is absent.
Files: Eight helpers listed in F-K1, table/structure alternate run_once paths, `backend/evaluation/isolation.py`; follow-on tests belong to TEST_AGENT.
Current behavior: Main entry gates refuse, but session-taking cleanup helpers issue SQL without local authorization.
Expected behavior: Every destructive operation refuses independently before SQL unless bound to an approved authority and actual engine/target; keep all positive paths disabled meanwhile.
Why current ownership is insufficient: Coordinator owns append-only evidence, not evaluation source/tests.
Proposed change: EVALUATION_AGENT gates each destructive callable at its boundary (default refusal until enforceable authority is approved); TEST_AGENT adds source-only coverage now and separately approved execution tests later. Database/security agents review actual connection binding and DDL target consistency before any enablement.
Risk: Direct calls can affect any caller-supplied database session; merely enabling a registry would not repair identity/authority or helper bypasses.
Validation still needed: Owning-agent remediation, approved no-I/O regression coverage, independent SECURITY_AGENT/DATABASE_AGENT/VERIFIER review. No PostgreSQL execution is authorized.

**Final acceptance: PARTIALLY COMPLETE, not COMPLETE. PostgreSQL verification remains NO-GO.**


### 9.8 Initial expanded Git status

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


### 9.9 Final expanded Git status

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
