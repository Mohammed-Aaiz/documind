# Phase 4F.5-H1-R — Reconciliation Audit

**Purpose:** Read-only audit of the Phase 4F.5-H1 experiment before accepting or rejecting its scientific conclusions.

**Status:** VALID_WITH_LIMITATIONS

## Files

| File | Description |
|---|---|
| `H1_RECONCILIATION_REPORT.md` | Full reconciliation report with all 15 sections |
| `h1_protocol_audit.json` | Protocol as intended vs as executed |
| `h1_count_reconciliation.json` | Expected vs actual dataset counts |
| `h1_overlap_report.json` | Data leakage and overlap analysis |
| `h1_label_integrity.json` | Token span labeling verification |
| `h1_no_answer_analysis.json` | No-answer decision mechanism audit |
| `h1_metric_recalculation.json` | Independent metric verification |
| `h1_null_score_analysis.json` | Null-score distribution analysis |
| `h1_reconciled_comparison.json` | Comparison table (A0/A1/A2/F2/H1) |
| `checksums.txt` | SHA-256 checksums of this directory |

## Key Findings

1. **Benchmark results are valid** — EM 0.0%, F1 11.0%, abstention 45.2%, spurious 54.8%
2. **Holdout discrepancy (22 vs 14)** is explained by a split-index mismatch; does not affect benchmark
3. **No data leakage** between training and any evaluation set
4. **Labels are correct** — all answerable have valid spans, all unanswerable use CLS
5. **Model collapsed** — the H20 negatives caused catastrophic performance degradation
6. **CLS/no-answer signal is random** — null margins near zero, distributions overlap completely

## Integrity

- No production code modified
- No frozen datasets modified
- No production model modified
- No commits made
- All artifact hashes verified
