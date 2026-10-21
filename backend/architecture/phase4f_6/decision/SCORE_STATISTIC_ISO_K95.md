# Fixed-K=95 Score-Statistic Stability (F2 and A0, frozen predictions)

> **PROVENANCE (2026-09-28) - PRE-RECONSTRUCTION-FIX answer text.** EM/F1 below
> and the `original_correct` rate are pre-fix; the five statistics' rankings and the abstention sets are NOT affected.
> The input predictions' answer TEXT came from `tokenizer.decode()`, which re-inserts spaces at subword
> boundaries and corrupted split values (`142.6 million` -> `142. 6 million`). Logit/score-derived signals are
> unaffected: span and score are bit-identical before vs after. On the same 182 examples, same checkpoints,
> same spans, only the decoder changed: F2 answerable EM 2.86% -> 14.29%, F1 16.92% -> 28.91%.
> Leaked population; not a generalization result. Full record: `E0_PREDICTION_PROVENANCE_2026-09-28.md`.

- Fixed budget **K = 95** (52.2%), reference K = 47. Pre-specified, not searched or tuned; no threshold used.
- Only variable changed versus K=47: the abstention budget. Same frozen predictions, same five statistics, same directions, same tie-break.
- Random reference: a random 95-example set contains ~21.92 unanswerable of 42 (formula 95 / 182 x 42); at K=47 the same reference was ~10.85.
- K=47 abstention sets reconstructed for composition comparison and verified against the recorded artifact: {'F2': True, 'A0': True}

## Task 2/3 — metrics at K=95

| Model | Statistic | K | True abstention | False abstention | Spurious | EM | F1 | Answerable coverage | Conditional EM | Conditional F1 | Abstention precision |
|---|---|--:|---|---|--:|--:|--:|--:|--:|--:|--:|
| F2 | null_score | 95 | 20/42 | 75/140 | 22 | 0.71 | 12.47 | 46.43 | 1.54 | 26.86 | 0.2105 |
| F2 | best_answer_score | 95 | 33/42 | 62/140 | 9 | 1.43 | 7.4 | 55.71 | 2.56 | 13.29 | 0.3474 |
| F2 | cls_start | 95 | 20/42 | 75/140 | 22 | 1.43 | 8.87 | 46.43 | 3.08 | 19.11 | 0.2105 |
| F2 | cls_end | 95 | 18/42 | 77/140 | 24 | 2.14 | 14.59 | 45.0 | 4.76 | 32.41 | 0.1895 |
| F2 | margin | 95 | 32/42 | 63/140 | 10 | 2.14 | 9.7 | 55.0 | 3.9 | 17.64 | 0.3368 |
| A0 | null_score | 95 | 22/42 | 73/140 | 20 | 2.86 | 12.16 | 47.86 | 5.97 | 25.41 | 0.2316 |
| A0 | best_answer_score | 95 | 20/42 | 75/140 | 22 | 1.43 | 11.6 | 46.43 | 3.08 | 24.98 | 0.2105 |
| A0 | cls_start | 95 | 22/42 | 73/140 | 20 | 2.86 | 11.92 | 47.86 | 5.97 | 24.91 | 0.2316 |
| A0 | cls_end | 95 | 22/42 | 73/140 | 20 | 2.86 | 12.16 | 47.86 | 5.97 | 25.41 | 0.2316 |
| A0 | margin | 95 | 25/42 | 70/140 | 17 | 2.14 | 13.13 | 50.0 | 4.29 | 26.25 | 0.2632 |

## Task 4 — deltas versus K=47

| Model | Statistic | Δtrue | Δfalse | Δspurious | ΔEM | ΔF1 | Δcond F1 | Δprecision |
|---|---|--:|--:|--:|--:|--:|--:|--:|
| F2 | null_score | 12 | 36 | -12 | -2.15 | -4.45 | 3.4 | 0.0403 |
| F2 | best_answer_score | 12 | 36 | -12 | -1.43 | -8.01 | -5.63 | -0.0994 |
| F2 | cls_start | 16 | 32 | -16 | -0.71 | -6.1 | -2.5 | 0.1254 |
| F2 | cls_end | 13 | 35 | -13 | -0.72 | -3.5 | 6.57 | 0.0831 |
| F2 | margin | 12 | 36 | -12 | -0.72 | -5.92 | -1.71 | -0.0887 |
| A0 | null_score | 16 | 32 | -16 | -2.14 | -6.16 | -0.49 | 0.1039 |
| A0 | best_answer_score | 9 | 39 | -9 | -0.71 | -5.43 | 2.05 | -0.0235 |
| A0 | cls_start | 16 | 32 | -16 | -2.14 | -6.16 | -0.65 | 0.1039 |
| A0 | cls_end | 17 | 31 | -17 | -2.14 | -6.06 | -0.62 | 0.1252 |
| A0 | margin | 18 | 30 | -18 | -1.43 | -4.23 | 1.94 | 0.1143 |

## Task 5 — stability and set composition

| Model | Statistic | Δtrue rate (pp) | Δfalse rate (pp) | Δprecision | Δretained F1 | intersection K47∩K95 | Jaccard | newly abstained |
|---|---|--:|--:|--:|--:|--:|--:|--:|
| F2 | null_score | 28.6 | 25.7 | 0.0403 | -4.45 | 47 | 0.4947 | 48 |
| F2 | best_answer_score | 28.6 | 25.7 | -0.0994 | -8.01 | 47 | 0.4947 | 48 |
| F2 | cls_start | 38.1 | 22.9 | 0.1254 | -6.1 | 47 | 0.4947 | 48 |
| F2 | cls_end | 31.0 | 25.0 | 0.0831 | -3.5 | 47 | 0.4947 | 48 |
| F2 | margin | 28.6 | 25.7 | -0.0887 | -5.92 | 47 | 0.4947 | 48 |
| A0 | null_score | 38.1 | 22.8 | 0.1039 | -6.16 | 47 | 0.4947 | 48 |
| A0 | best_answer_score | 21.4 | 27.9 | -0.0235 | -5.43 | 47 | 0.4947 | 48 |
| A0 | cls_start | 38.1 | 22.8 | 0.1039 | -6.16 | 47 | 0.4947 | 48 |
| A0 | cls_end | 40.5 | 22.1 | 0.1252 | -6.06 | 47 | 0.4947 | 48 |
| A0 | margin | 42.8 | 21.4 | 0.1143 | -4.23 | 47 | 0.4947 | 48 |

## Task 6 — category abstention counts (abstained / n) at K=95, plus K47→K95 additions

### F2

| statistic | DIRECT_SPAN | NUMERIC | TABLE_CELL | TABLE_ROW | LIST_ITEM | SECTION_SPECIFIC | MULTI_CHUNK | LONG_CONTEXT | largest additional allocation |
|---|---|---|---|---|---|---|---|---|---|
| null_score | 11/24 | 0/20 | 14/24 | 6/16 | 9/20 | 16/16 | 9/10 | 10/10 | TABLE_CELL, DIRECT_SPAN, TABLE_ROW |
| best_answer_score | 8/24 | 18/20 | 4/24 | 4/16 | 14/20 | 7/16 | 2/10 | 5/10 | NUMERIC, DIRECT_SPAN, LONG_CONTEXT |
| cls_start | 18/24 | 8/20 | 2/24 | 0/16 | 11/20 | 16/16 | 10/10 | 10/10 | DIRECT_SPAN, NUMERIC, LIST_ITEM |
| cls_end | 1/24 | 0/20 | 22/24 | 14/16 | 10/20 | 13/16 | 7/10 | 10/10 | SECTION_SPECIFIC, TABLE_ROW, LIST_ITEM |
| margin | 6/24 | 11/20 | 4/24 | 4/16 | 14/20 | 11/16 | 3/10 | 10/10 | SECTION_SPECIFIC, DIRECT_SPAN, LIST_ITEM |

### A0

| statistic | DIRECT_SPAN | NUMERIC | TABLE_CELL | TABLE_ROW | LIST_ITEM | SECTION_SPECIFIC | MULTI_CHUNK | LONG_CONTEXT | largest additional allocation |
|---|---|---|---|---|---|---|---|---|---|
| null_score | 12/24 | 10/20 | 18/24 | 16/16 | 7/20 | 0/16 | 9/10 | 1/10 | TABLE_CELL, TABLE_ROW, MULTI_CHUNK |
| best_answer_score | 10/24 | 3/20 | 11/24 | 14/16 | 14/20 | 6/16 | 8/10 | 9/10 | LIST_ITEM, LONG_CONTEXT, DIRECT_SPAN |
| cls_start | 13/24 | 10/20 | 17/24 | 16/16 | 7/20 | 0/16 | 9/10 | 1/10 | TABLE_CELL, MULTI_CHUNK, TABLE_ROW |
| cls_end | 12/24 | 10/20 | 18/24 | 16/16 | 7/20 | 0/16 | 9/10 | 1/10 | TABLE_CELL, MULTI_CHUNK, TABLE_ROW |
| margin | 13/24 | 6/20 | 16/24 | 16/16 | 9/20 | 0/16 | 8/10 | 2/10 | TABLE_CELL, DIRECT_SPAN, NUMERIC |

## Task 7 — classification at K=95 under the pre-specified rule

| Model | Statistic | K=47 class | K=95 class | changed? | Δtrue | Δfalse | ΔF1 |
|---|---|---|---|---|---|--:|--:|--:|
| F2 | null_score | SIMILAR_TO_NULL | SIMILAR_TO_NULL | False | 0 | 0 | 0.0 |
| F2 | best_answer_score | MORE_INFORMATIVE_THAN_NULL | MORE_INFORMATIVE_THAN_NULL | False | 13 | -13 | -5.07 |
| F2 | cls_start | LESS_INFORMATIVE_THAN_NULL | INSUFFICIENT_DIFFERENCE | True | 0 | 0 | -3.6 |
| F2 | cls_end | LESS_INFORMATIVE_THAN_NULL | INSUFFICIENT_DIFFERENCE | True | -2 | 2 | 2.12 |
| F2 | margin | MORE_INFORMATIVE_THAN_NULL | MORE_INFORMATIVE_THAN_NULL | False | 12 | -12 | -2.77 |
| A0 | null_score | SIMILAR_TO_NULL | SIMILAR_TO_NULL | False | 0 | 0 | 0.0 |
| A0 | best_answer_score | MORE_INFORMATIVE_THAN_NULL | SIMILAR_TO_NULL | True | -2 | 2 | -0.56 |
| A0 | cls_start | SIMILAR_TO_NULL | SIMILAR_TO_NULL | False | 0 | 0 | -0.24 |
| A0 | cls_end | SIMILAR_TO_NULL | SIMILAR_TO_NULL | False | 0 | 0 | 0.0 |
| A0 | margin | SIMILAR_TO_NULL | MORE_INFORMATIVE_THAN_NULL | True | 3 | -3 | 0.97 |

## Task 8/9 — signal and stability verdict

- random reference at K=95: 21.92 unanswerable of 42
- classification agreement: 4/8
- true-abstention ordering preserved per checkpoint: {'F2': False, 'A0': False}
- ordering at K=95: `{'F2': ['best_answer_score', 'margin', 'cls_start', 'null_score', 'cls_end'], 'A0': ['margin', 'cls_end', 'cls_start', 'null_score', 'best_answer_score']}`
- ordering at K=47: `{'F2': ['best_answer_score', 'margin', 'null_score', 'cls_end', 'cls_start'], 'A0': ['best_answer_score', 'margin', 'cls_start', 'null_score', 'cls_end']}`

**VERDICT: UNSTABLE**

### Pre-specified stability rule

- **inputs**: classification agreement across the 8 non-null (model, statistic) pairs + preservation of the per-model ordering of statistics by true abstention
- **STABLE**: classification agreement == 8/8 AND the true-abstention ordering of the five statistics is preserved for BOTH checkpoints
- **PARTIALLY_STABLE**: classification agreement in 5..7 of 8, OR ordering preserved for exactly one checkpoint
- **UNSTABLE**: classification agreement <= 4 of 8, OR ordering preserved for neither checkpoint

## Interpretation boundary

- No inference, no model loading, no training, no database, no retrieval was used.
- K=95 was fixed before evaluation and was neither searched nor tuned; no threshold is used.
- The K=47 abstention sets were reconstructed only to measure set composition and were verified against the recorded K=47 artifact.
- Classifications are descriptive comparisons to null_score under the pre-specified rule; no statistic is declared universally superior.
- No causal or architectural claim (H-A..H-E) is made.
