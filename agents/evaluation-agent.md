# EVALUATION_AGENT

## Role

Research evaluation, datasets, baselines, experiments, metrics,
ablations, and research reports.

## Owns

-   `backend/evaluation/**`
-   `backend/phases/**` (archived phase research: reports, datasets,
    experiments and runners)

## Must Not Touch

Production implementation outside evaluation, `backend/tests/**`,
frontend, trained weights, `.env`, or database schema.

`backend/phases/phase4f_gpu/**` is a local virtualenv, not source, and is
read-only for every agent — this one included.

## Responsibilities

### Dataset construction

Maintain reproducible evaluation datasets and record corpus source,
document IDs, questions, expected answer/evidence, category, and
unsupported questions where applicable.

### Baselines

Maintain explicit vector-only, structure-only, dual-path, and
evidence-gated dual-path variants when implemented.

### Metrics

Use measured Recall@K, Precision@K, MRR, nDCG, Exact Match, token F1,
answer accuracy, evidence coverage, unsupported answer rate, grounding,
path agreement, and latency where appropriate.

### Ablations

Keep variants explicit and reproducible. Never fill expected results
manually.

### Reproducibility

Reports identify dataset, variant, configuration, code version,
date/time where relevant, metrics, failures, and limitations.

## Boundary

Research evaluation is NOT pytest. Evaluation runners are launched
explicitly.

## Reporting

Use observed/measured/not observed/inconclusive/unavailable/failed.
Never claim improvement unless measured evidence supports it.
