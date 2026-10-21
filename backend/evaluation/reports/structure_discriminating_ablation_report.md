# Structure-discriminating ablation — A/B/C/D synthesis

- Corpus: `structure-discriminating-v1`
- Synthesis version: `structure-discriminating-synthesis-v1`
- Source: the established production-aligned runner (`ablation_structure_discriminating_A.json`, `ablation_structure_discriminating_B.json`, `ablation_structure_discriminating_C.json`, `ablation_structure_discriminating_D.json`).
- Method: re-aggregation of recorded per-question measurements by pre-registered population; no retrieval was re-run.

## 1. Purpose

Test whether structure-aware retrieval (**C**) improves retrieval, answer or grounding performance over semantic-only retrieval (**A**) on genuinely structure-discriminating questions, using the production-aligned A/B/C/D runner and the established denominator methodology.

## 2. Population definitions

| population | definition |
|---|---|
| DISCRIMINATING | pre-registered primary structural subset (answerable) |
| WEAKLY_DISCRIMINATING | weak subset (answerable), reported separately |
| NOT_DISCRIMINATING | semantic controls (answerable) |
| ALL_ANSWERABLE | every answerable question |
| UNANSWERABLE | every unanswerable question (unsupported-answer metric) |

Retrieval / answer / evidence metrics are reported over the **answerable** questions of each population; `unsupported_answer` is reported over the **unanswerable** population only (`null` when empty). `answer_accuracy` uses the documented threshold F1 ≥ 0.5. `section_grounding` is not emitted by the production-aligned runner.

## 3. Primary table — full answerable population

| Metric | A Semantic | B Structure-Only | C Structure-Aware | D Fused |
|---|---:|---:|---:|---:|
| Recall@5 | 0.9498 | 0.0000 | 0.9498 | 0.9498 |
| Precision@5 | 0.2562 | 0.0000 | 0.2562 | 0.2562 |
| MRR | 0.6771 | 0.0000 | 0.6763 | 0.6763 |
| NDCG@5 | 0.7416 | 0.0000 | 0.7384 | 0.7384 |
| Exact Match | 0.2500 | 0.0000 | 0.2812 | 0.2812 |
| Token F1 | 0.5185 | 0.0000 | 0.4934 | 0.4909 |
| Answer Accuracy | 0.6562 | 0.0000 | 0.6250 | 0.6250 |
| Evidence Coverage | 1.0000 | 1.0000 | 1.0000 | 0.9688 |
| Path Agreement | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| Factual Grounded | 1.0000 | 0.0000 | 1.0000 | 0.9688 |
| Unsupported Answer Rate | n/a | n/a | n/a | n/a |
| Section Grounding | n/a | n/a | n/a | n/a |

Population size: n = 64.

## 4. Primary hypothesis test — DISCRIMINATING subset

| Metric | A Semantic | B Structure-Only | C Structure-Aware | D Fused |
|---|---:|---:|---:|---:|
| Recall@5 | 0.9531 | 0.0000 | 0.9531 | 0.9531 |
| Precision@5 | 0.2625 | 0.0000 | 0.2625 | 0.2625 |
| MRR | 0.7214 | 0.0000 | 0.7214 | 0.7214 |
| NDCG@5 | 0.7711 | 0.0000 | 0.7661 | 0.7661 |
| Exact Match | 0.2812 | 0.0000 | 0.2812 | 0.2812 |
| Token F1 | 0.5413 | 0.0000 | 0.5029 | 0.4979 |
| Answer Accuracy | 0.5938 | 0.0000 | 0.5938 | 0.5938 |
| Evidence Coverage | 1.0000 | 1.0000 | 1.0000 | 0.9688 |
| Path Agreement | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| Factual Grounded | 1.0000 | 0.0000 | 1.0000 | 0.9688 |
| Unsupported Answer Rate | n/a | n/a | n/a | n/a |
| Section Grounding | n/a | n/a | n/a | n/a |

Population size: n = 32.

## 5. Effect deltas

### DISCRIMINATING subset

| Metric | C − A | D − A | D − C | B − A |
|---|---:|---:|---:|---:|
| Recall@5 | 0.0000 | 0.0000 | 0.0000 | -0.9531 |
| Precision@5 | 0.0000 | 0.0000 | 0.0000 | -0.2625 |
| MRR | 0.0000 | 0.0000 | 0.0000 | -0.7214 |
| NDCG@5 | -0.0050 | -0.0050 | 0.0000 | -0.7711 |
| Exact Match | 0.0000 | 0.0000 | 0.0000 | -0.2812 |
| Token F1 | -0.0384 | -0.0434 | -0.0050 | -0.5413 |
| Answer Accuracy | 0.0000 | 0.0000 | 0.0000 | -0.5938 |
| Evidence Coverage | 0.0000 | -0.0312 | -0.0312 | 0.0000 |
| Path Agreement | 1.0000 | 1.0000 | 0.0000 | 0.0000 |
| Factual Grounded | 0.0000 | -0.0312 | -0.0312 | -1.0000 |
| Unsupported Answer Rate | n/a | n/a | n/a | n/a |
| Section Grounding | n/a | n/a | n/a | n/a |

### Full answerable population

| Metric | C − A | D − A | D − C | B − A |
|---|---:|---:|---:|---:|
| Recall@5 | 0.0000 | 0.0000 | 0.0000 | -0.9498 |
| Precision@5 | 0.0000 | 0.0000 | 0.0000 | -0.2562 |
| MRR | -0.0008 | -0.0008 | 0.0000 | -0.6771 |
| NDCG@5 | -0.0032 | -0.0032 | 0.0000 | -0.7416 |
| Exact Match | 0.0312 | 0.0312 | 0.0000 | -0.2500 |
| Token F1 | -0.0251 | -0.0276 | -0.0025 | -0.5185 |
| Answer Accuracy | -0.0312 | -0.0312 | 0.0000 | -0.6562 |
| Evidence Coverage | 0.0000 | -0.0312 | -0.0312 | 0.0000 |
| Path Agreement | 1.0000 | 1.0000 | 0.0000 | 0.0000 |
| Factual Grounded | 0.0000 | -0.0312 | -0.0312 | -1.0000 |
| Unsupported Answer Rate | n/a | n/a | n/a | n/a |
| Section Grounding | n/a | n/a | n/a | n/a |

## 6. Weak subset — WEAKLY_DISCRIMINATING

| Metric | A Semantic | B Structure-Only | C Structure-Aware | D Fused |
|---|---:|---:|---:|---:|
| Recall@5 | 0.9286 | 0.0000 | 0.9286 | 0.9286 |
| Precision@5 | 0.2667 | 0.0000 | 0.2667 | 0.2667 |
| MRR | 0.5868 | 0.0000 | 0.5847 | 0.5847 |
| NDCG@5 | 0.6732 | 0.0000 | 0.6713 | 0.6713 |
| Exact Match | 0.1667 | 0.0000 | 0.2083 | 0.2083 |
| Token F1 | 0.4194 | 0.0000 | 0.4022 | 0.4022 |
| Answer Accuracy | 0.6250 | 0.0000 | 0.5833 | 0.5833 |
| Evidence Coverage | 1.0000 | 1.0000 | 1.0000 | 0.9583 |
| Path Agreement | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| Factual Grounded | 1.0000 | 0.0000 | 1.0000 | 0.9583 |
| Unsupported Answer Rate | n/a | n/a | n/a | n/a |
| Section Grounding | n/a | n/a | n/a | n/a |

Population size: n = 24.

## 7. Controls — NOT_DISCRIMINATING

| Metric | A Semantic | B Structure-Only | C Structure-Aware | D Fused |
|---|---:|---:|---:|---:|
| Recall@5 | 1.0000 | 0.0000 | 1.0000 | 1.0000 |
| Precision@5 | 0.2000 | 0.0000 | 0.2000 | 0.2000 |
| MRR | 0.7708 | 0.0000 | 0.7708 | 0.7708 |
| NDCG@5 | 0.8289 | 0.0000 | 0.8289 | 0.8289 |
| Exact Match | 0.3750 | 0.0000 | 0.5000 | 0.5000 |
| Token F1 | 0.7244 | 0.0000 | 0.7292 | 0.7292 |
| Answer Accuracy | 1.0000 | 0.0000 | 0.8750 | 0.8750 |
| Evidence Coverage | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Path Agreement | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| Factual Grounded | 1.0000 | 0.0000 | 1.0000 | 1.0000 |
| Unsupported Answer Rate | n/a | n/a | n/a | n/a |
| Section Grounding | n/a | n/a | n/a | n/a |

Population size: n = 8.

## 8. Unanswerable population

| Metric | A Semantic | B Structure-Only | C Structure-Aware | D Fused |
|---|---:|---:|---:|---:|
| Recall@5 | n/a | n/a | n/a | n/a |
| Precision@5 | n/a | n/a | n/a | n/a |
| MRR | n/a | n/a | n/a | n/a |
| NDCG@5 | n/a | n/a | n/a | n/a |
| Exact Match | n/a | n/a | n/a | n/a |
| Token F1 | n/a | n/a | n/a | n/a |
| Answer Accuracy | n/a | n/a | n/a | n/a |
| Evidence Coverage | n/a | n/a | n/a | n/a |
| Path Agreement | n/a | n/a | n/a | n/a |
| Factual Grounded | 1.0000 | 0.0000 | 1.0000 | 0.0000 |
| Unsupported Answer Rate | 1.0000 | 0.0000 | 1.0000 | 0.0000 |
| Section Grounding | n/a | n/a | n/a | n/a |

Population size: n = 8.

### Unsupported-answer rate by variant

- A: 1.0000
- B: 0.0000
- C: 1.0000
- D: 0.0000

## 9. Category-level analysis (DISCRIMINATING)

| category | C>A | A>C | tie |
|---|---:|---:|---:|
| multi_hop_structural | 0 | 0 | 8 |
| page_crossing | 0 | 0 | 8 |
| section_heading | 0 | 0 | 3 |
| structural_distractor | 0 | 0 | 8 |
| table_row_cell | 0 | 0 | 5 |

(Comparison on Precision@5 per question, the framework's ranking metric.)

## 10. Research questions answered

1. **Did C outperform A on the DISCRIMINATING subset?** No. Recall@5 was no measurable difference (A=0.9531, C=0.9531); Precision@5 no measurable difference; nDCG@5 measured decrease of 0.0050; token F1 measured decrease of 0.0384; answer accuracy no measurable difference.
2. **By which metrics?** Only `path_agreement` moves positively (measured increase of 1.0000), which is true by construction because C uses the dual path. Retrieval rank metrics are ties or slightly lower for C; token F1 is lower for C.
3. **Consistent across structural categories?** Yes — every DISCRIMINATING question tied on Precision@5 (see §9); no category showed a C>A win.
4. **Did D outperform C?** No. D−C on the DISCRIMINATING subset was no measurable difference (Recall@5) and measured decrease of 0.0050 (token F1); D additionally abstains on unanswerable questions.
5. **Did the controls behave as expected?** The NOT_DISCRIMINATING controls showed no structural advantage; C−A path_agreement measured increase of 1.0000, recall no measurable difference. Controls are consistent with a null structure effect.
6. **Unanswerable questions?** A/C answered all 8 (unsupported rate 1.0000 / 1.0000); D abstained on all 8 (0.0000). The gate's abstention behaviour is the one clear measured effect.
7. **What does the experiment support?** The evidence-gate abstention benefit on unanswerable questions, and preserved retrieval provenance (path_agreement). Nothing about the structure-aware retrieval advantage.
8. **What does it not support?** Any retrieval, answer-quality or grounding advantage of structure-aware retrieval (C) over semantic-only retrieval (A) on the pre-registered DISCRIMINATING subset.
9. **Parser/chunker limitations?** The PDF parser emits only section/paragraph/table/text_block (no persisted table_row/table_cell), and the production `legacy` chunker does not populate heading_path/section, so heading/section seeding is inert and the only live structural signal is the element stream.
10. **Next research decision?** Investigate whether the element-level structural stream is reachable for these questions (parser coverage / chunker configuration) before enlarging the corpus; only then is a larger evaluation likely to be informative.

**Verdict:** NO STRUCTURE BENEFIT OBSERVED. Key C−A deltas: `{"answer_accuracy": 0.0, "ndcg@5": -0.005038, "precision@5": 0.0, "recall@5": 0.0, "token_f1": -0.038417}`.

The primary subset was fixed before the experiment; no subset was chosen after looking at outcomes. No statistical significance and no causal claim is made: the framework's paired bootstrap exists but was not applied here.

## 11. Limitations

- The current PDF parser emits only `section`, `paragraph`, `table` and `text_block`; persisted `table_row` / `table_cell` nodes do not exist, so row/cell gold is not resolved natively in the production graph.
- The production default chunker is `legacy`, which does not populate `heading_path`/`section`; heading/section seeding is therefore inert and the live structural signal is the element-level stream.
- Corpus is synthetic (authored PDFs), 72 questions; results are specific to this corpus and configuration.
- Latency is reported by the runner but is not part of the effect analysis.

## 12. Recommended next research decision

If the DISCRIMINATING result shows no measurable C−A difference, the structure hypothesis remains unsupported on this corpus and the next step is to investigate whether the element-level structural stream is actually reachable for these questions (parser coverage / chunker configuration) before enlarging the corpus. If an effect is observed, replicate on a larger corpus and apply the framework's paired bootstrap before drawing conclusions.
