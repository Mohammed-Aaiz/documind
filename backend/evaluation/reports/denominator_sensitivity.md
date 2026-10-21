# Denominator sensitivity analysis

- Analysis version: denominator-sensitivity-v1
- Nature: re-aggregation of frozen production-aligned per-question results; no experiment was re-run and no production-aligned report was modified.

## 1. Purpose

The production-aligned A–D runner aggregates every metric over **all** measured questions. The repository's earlier runners aggregate retrieval, answer and evidence metrics over the **answerable** population. This analysis quantifies how much the reported numbers move under those established populations. It is a **sensitivity analysis**, not a replacement for the production-aligned evaluation.

## 2. Population definitions

| population | definition | source |
|---|---|---|
| all measured questions | every question in the run (current runner) | `runner._aggregate` |
| gold-bearing questions | carry gold retrieval evidence; == answerable here | `run_phase3d/3f/4b`; corpus contract |
| answerable questions | corpus marks the question answerable | `qa_metrics.answer_accuracy`; earlier runners |
| unanswerable questions | corpus marks the question unanswerable | `qa_metrics.unsupported_answer_rate`; `runner.UNANSWERABLE_ONLY_METRICS` |

## 3. phase3d table

### Variant A

- source: `ablation_A.json`
- populations: all=42, gold-bearing=39, answerable=39, unanswerable=3

| metric | current (all) | sensitivity | population | Δ | excluded |
|---|---|---|---|---|---|
| recall@5 | 0.7738 | 0.8333 | gold-bearing questions (39) | 0.0595 | 3 |
| precision@5 | 0.1905 | 0.2051 | gold-bearing questions (39) | 0.0147 | 3 |
| mrr | 0.7417 | 0.7987 | gold-bearing questions (39) | 0.0571 | 3 |
| ndcg@5 | 0.7268 | 0.7827 | gold-bearing questions (39) | 0.0559 | 3 |
| exact_match | 0.5238 | 0.5641 | answerable questions (39) | 0.0403 | 3 |
| token_f1 | 0.6296 | 0.6781 | answerable questions (39) | 0.0484 | 3 |
| evidence_coverage | 0.9905 | 0.9897 | answerable questions (39) | -0.0007 | 3 |

### Variant B

- source: `ablation_B.json`
- populations: all=42, gold-bearing=39, answerable=39, unanswerable=3

| metric | current (all) | sensitivity | population | Δ | excluded |
|---|---|---|---|---|---|
| recall@5 | 0.0000 | 0.0000 | gold-bearing questions (39) | 0.0000 | 3 |
| precision@5 | 0.0000 | 0.0000 | gold-bearing questions (39) | 0.0000 | 3 |
| mrr | 0.0000 | 0.0000 | gold-bearing questions (39) | 0.0000 | 3 |
| ndcg@5 | 0.0000 | 0.0000 | gold-bearing questions (39) | 0.0000 | 3 |
| exact_match | 0.0000 | 0.0000 | answerable questions (39) | 0.0000 | 3 |
| token_f1 | 0.0000 | 0.0000 | answerable questions (39) | 0.0000 | 3 |
| evidence_coverage | 1.0000 | 1.0000 | answerable questions (39) | 0.0000 | 3 |

### Variant C

- source: `ablation_C.json`
- populations: all=42, gold-bearing=39, answerable=39, unanswerable=3

| metric | current (all) | sensitivity | population | Δ | excluded |
|---|---|---|---|---|---|
| recall@5 | 0.7738 | 0.8333 | gold-bearing questions (39) | 0.0595 | 3 |
| precision@5 | 0.1905 | 0.2051 | gold-bearing questions (39) | 0.0147 | 3 |
| mrr | 0.7440 | 0.8013 | gold-bearing questions (39) | 0.0572 | 3 |
| ndcg@5 | 0.7295 | 0.7856 | gold-bearing questions (39) | 0.0561 | 3 |
| exact_match | 0.4762 | 0.5128 | answerable questions (39) | 0.0366 | 3 |
| token_f1 | 0.6189 | 0.6665 | answerable questions (39) | 0.0476 | 3 |
| evidence_coverage | 0.9905 | 0.9897 | answerable questions (39) | -0.0007 | 3 |

### Variant D

- source: `ablation_D.json`
- populations: all=42, gold-bearing=39, answerable=39, unanswerable=3

| metric | current (all) | sensitivity | population | Δ | excluded |
|---|---|---|---|---|---|
| recall@5 | 0.7738 | 0.8333 | gold-bearing questions (39) | 0.0595 | 3 |
| precision@5 | 0.1905 | 0.2051 | gold-bearing questions (39) | 0.0147 | 3 |
| mrr | 0.7440 | 0.8013 | gold-bearing questions (39) | 0.0572 | 3 |
| ndcg@5 | 0.7295 | 0.7856 | gold-bearing questions (39) | 0.0561 | 3 |
| exact_match | 0.4762 | 0.5128 | answerable questions (39) | 0.0366 | 3 |
| token_f1 | 0.6121 | 0.6592 | answerable questions (39) | 0.0471 | 3 |
| evidence_coverage | 0.8714 | 0.9385 | answerable questions (39) | 0.0670 | 3 |

## 4. heading table

### Variant A

- source: `ablation_heading_A.json`
- populations: all=23, gold-bearing=20, answerable=20, unanswerable=3

| metric | current (all) | sensitivity | population | Δ | excluded |
|---|---|---|---|---|---|
| recall@5 | 0.8478 | 0.9750 | gold-bearing questions (20) | 0.1272 | 3 |
| precision@5 | 0.1826 | 0.2100 | gold-bearing questions (20) | 0.0274 | 3 |
| mrr | 0.7319 | 0.8417 | gold-bearing questions (20) | 0.1098 | 3 |
| ndcg@5 | 0.7567 | 0.8702 | gold-bearing questions (20) | 0.1135 | 3 |
| exact_match | 0.4783 | 0.5500 | answerable questions (20) | 0.0717 | 3 |
| token_f1 | 0.7470 | 0.8590 | answerable questions (20) | 0.1120 | 3 |
| evidence_coverage | 1.0000 | 1.0000 | answerable questions (20) | 0.0000 | 3 |

### Variant B

- source: `ablation_heading_B.json`
- populations: all=23, gold-bearing=20, answerable=20, unanswerable=3

| metric | current (all) | sensitivity | population | Δ | excluded |
|---|---|---|---|---|---|
| recall@5 | 0.0000 | 0.0000 | gold-bearing questions (20) | 0.0000 | 3 |
| precision@5 | 0.0000 | 0.0000 | gold-bearing questions (20) | 0.0000 | 3 |
| mrr | 0.0000 | 0.0000 | gold-bearing questions (20) | 0.0000 | 3 |
| ndcg@5 | 0.0000 | 0.0000 | gold-bearing questions (20) | 0.0000 | 3 |
| exact_match | 0.0000 | 0.0000 | answerable questions (20) | 0.0000 | 3 |
| token_f1 | 0.0000 | 0.0000 | answerable questions (20) | 0.0000 | 3 |
| evidence_coverage | 1.0000 | 1.0000 | answerable questions (20) | 0.0000 | 3 |

### Variant C

- source: `ablation_heading_C.json`
- populations: all=23, gold-bearing=20, answerable=20, unanswerable=3

| metric | current (all) | sensitivity | population | Δ | excluded |
|---|---|---|---|---|---|
| recall@5 | 0.8478 | 0.9750 | gold-bearing questions (20) | 0.1272 | 3 |
| precision@5 | 0.1826 | 0.2100 | gold-bearing questions (20) | 0.0274 | 3 |
| mrr | 0.7319 | 0.8417 | gold-bearing questions (20) | 0.1098 | 3 |
| ndcg@5 | 0.7579 | 0.8715 | gold-bearing questions (20) | 0.1137 | 3 |
| exact_match | 0.4348 | 0.5000 | answerable questions (20) | 0.0652 | 3 |
| token_f1 | 0.6749 | 0.7762 | answerable questions (20) | 0.1012 | 3 |
| evidence_coverage | 1.0000 | 1.0000 | answerable questions (20) | 0.0000 | 3 |

### Variant D

- source: `ablation_heading_D.json`
- populations: all=23, gold-bearing=20, answerable=20, unanswerable=3

| metric | current (all) | sensitivity | population | Δ | excluded |
|---|---|---|---|---|---|
| recall@5 | 0.8478 | 0.9750 | gold-bearing questions (20) | 0.1272 | 3 |
| precision@5 | 0.1826 | 0.2100 | gold-bearing questions (20) | 0.0274 | 3 |
| mrr | 0.7319 | 0.8417 | gold-bearing questions (20) | 0.1098 | 3 |
| ndcg@5 | 0.7579 | 0.8715 | gold-bearing questions (20) | 0.1137 | 3 |
| exact_match | 0.4348 | 0.5000 | answerable questions (20) | 0.0652 | 3 |
| token_f1 | 0.6749 | 0.7762 | answerable questions (20) | 0.1012 | 3 |
| evidence_coverage | 0.9130 | 1.0000 | answerable questions (20) | 0.0870 | 3 |

## 5. Unsupported-answer confirmation

`unsupported_answer` is already population-correct (unanswerable denominator); this is a confirmation, not a new methodology.

| corpus | variant | reported | human-readable | denominator correct |
|---|---|---|---|---|
| phase3d | A | 1.0000 | 3/3 | True |
| phase3d | B | 0.0000 | 0/3 | True |
| phase3d | C | 1.0000 | 3/3 | True |
| phase3d | D | 0.0000 | 0/3 | True |
| heading | A | 1.0000 | 3/3 | True |
| heading | B | 0.0000 | 0/3 | True |
| heading | C | 1.0000 | 3/3 | True |
| heading | D | 0.3333 | 1/3 | True |

### Not applicable (no documented alternate population)

| corpus | variant | metric | reason |
|---|---|---|---|
| phase3d | A | factual_grounded | An alternate population is documented (answered questions, per qa_metrics.factual_grounding_rate), but per-question answered-ness is not present in the frozen production-aligned reports (their to_dict omits detail.predicted/insufficient_context). Recomputing it would require re-running the experiment or changing the frozen report schema, so no sensitivity value is produced here. |
| phase3d | A | path_agreement | No alternate population is documented; path_agreement is a per-question binary property of the retrieved source paths that is defined for every question regardless of answerability, so there is no population to switch. |
| phase3d | B | factual_grounded | An alternate population is documented (answered questions, per qa_metrics.factual_grounding_rate), but per-question answered-ness is not present in the frozen production-aligned reports (their to_dict omits detail.predicted/insufficient_context). Recomputing it would require re-running the experiment or changing the frozen report schema, so no sensitivity value is produced here. |
| phase3d | B | path_agreement | No alternate population is documented; path_agreement is a per-question binary property of the retrieved source paths that is defined for every question regardless of answerability, so there is no population to switch. |
| phase3d | C | factual_grounded | An alternate population is documented (answered questions, per qa_metrics.factual_grounding_rate), but per-question answered-ness is not present in the frozen production-aligned reports (their to_dict omits detail.predicted/insufficient_context). Recomputing it would require re-running the experiment or changing the frozen report schema, so no sensitivity value is produced here. |
| phase3d | C | path_agreement | No alternate population is documented; path_agreement is a per-question binary property of the retrieved source paths that is defined for every question regardless of answerability, so there is no population to switch. |
| phase3d | D | factual_grounded | An alternate population is documented (answered questions, per qa_metrics.factual_grounding_rate), but per-question answered-ness is not present in the frozen production-aligned reports (their to_dict omits detail.predicted/insufficient_context). Recomputing it would require re-running the experiment or changing the frozen report schema, so no sensitivity value is produced here. |
| phase3d | D | path_agreement | No alternate population is documented; path_agreement is a per-question binary property of the retrieved source paths that is defined for every question regardless of answerability, so there is no population to switch. |
| heading | A | factual_grounded | An alternate population is documented (answered questions, per qa_metrics.factual_grounding_rate), but per-question answered-ness is not present in the frozen production-aligned reports (their to_dict omits detail.predicted/insufficient_context). Recomputing it would require re-running the experiment or changing the frozen report schema, so no sensitivity value is produced here. |
| heading | A | path_agreement | No alternate population is documented; path_agreement is a per-question binary property of the retrieved source paths that is defined for every question regardless of answerability, so there is no population to switch. |
| heading | B | factual_grounded | An alternate population is documented (answered questions, per qa_metrics.factual_grounding_rate), but per-question answered-ness is not present in the frozen production-aligned reports (their to_dict omits detail.predicted/insufficient_context). Recomputing it would require re-running the experiment or changing the frozen report schema, so no sensitivity value is produced here. |
| heading | B | path_agreement | No alternate population is documented; path_agreement is a per-question binary property of the retrieved source paths that is defined for every question regardless of answerability, so there is no population to switch. |
| heading | C | factual_grounded | An alternate population is documented (answered questions, per qa_metrics.factual_grounding_rate), but per-question answered-ness is not present in the frozen production-aligned reports (their to_dict omits detail.predicted/insufficient_context). Recomputing it would require re-running the experiment or changing the frozen report schema, so no sensitivity value is produced here. |
| heading | C | path_agreement | No alternate population is documented; path_agreement is a per-question binary property of the retrieved source paths that is defined for every question regardless of answerability, so there is no population to switch. |
| heading | D | factual_grounded | An alternate population is documented (answered questions, per qa_metrics.factual_grounding_rate), but per-question answered-ness is not present in the frozen production-aligned reports (their to_dict omits detail.predicted/insufficient_context). Recomputing it would require re-running the experiment or changing the frozen report schema, so no sensitivity value is produced here. |
| heading | D | path_agreement | No alternate population is documented; path_agreement is a per-question binary property of the retrieved source paths that is defined for every question regardless of answerability, so there is no population to switch. |

## 6. Interpretation

Excluding the unanswerable questions raises the retrieval and answer metrics for both corpora; the magnitude is shown per variant above. The production-aligned (all-question) numbers remain the historical/current measurement; the contract-aligned values are a sensitivity view. No statistical significance or causal improvement is claimed.

## 7. Limitations

- Re-aggregation only: it cannot correct the experiment design, only the denominator of the recorded per-question values.
- Gold-bearing is equated with answerable for these corpora from the documented corpus contract; a corpus where answerable questions lack gold would need a different observable.
- `factual_grounded` and `path_agreement` have no computable alternate population from the frozen reports (see the not-applicable table).

## 8. Recommendation

Adopt the contract-aligned populations (retrieval/evidence → gold-bearing/answerable; answer → answerable; unsupported → unanswerable) as the default in a future evaluation revision, and report the all-question view only as an explicit sensitivity, so the historical and contract-aligned numbers are never confused.
