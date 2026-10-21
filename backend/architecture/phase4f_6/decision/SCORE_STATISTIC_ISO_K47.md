# Fixed-K=47 Score-Statistic Ranking (F2 and A0, frozen predictions)

> **PROVENANCE (2026-09-28) - PRE-RECONSTRUCTION-FIX answer text.** EM/F1 below
> and the `original_correct` rate are pre-fix; the five statistics' rankings and the abstention sets are NOT affected.
> The input predictions' answer TEXT came from `tokenizer.decode()`, which re-inserts spaces at subword
> boundaries and corrupted split values (`142.6 million` -> `142. 6 million`). Logit/score-derived signals are
> unaffected: span and score are bit-identical before vs after. On the same 182 examples, same checkpoints,
> same spans, only the decoder changed: F2 answerable EM 2.86% -> 14.29%, F1 16.92% -> 28.91%.
> Leaked population; not a generalization result. Full record: `E0_PREDICTION_PROVENANCE_2026-09-28.md`.

- Fixed abstention budget **K = 47** (25.8% of 182), pre-specified, not searched or tuned.
- Only variable changed: **the ranking statistic** used to pick the abstention set. No threshold is used.
- Tie-break: example_id ascending. Statistics are used exactly as recorded; none reversed or re-derived.
- Chance reference: a random 47-example set contains ~10.85 unanswerable of 42.
- Inputs: `backend/architecture/phase4f_6/e0_diagnostics/diagnostics/model_40min_predictions.json` sha256 `d7d9d65e944488ac...`, benchmark `1166bf4ff38265c2...` (verified). No inference.

## Task 2 — directions (taken from each definition, never silently reversed)

| statistic | direction | justification |
|---|---|---|
| null_score | DESC | cls_start + cls_end; high = the no-answer ([CLS]) score dominates |
| best_answer_score | ASC | best_start_logit + best_end_logit; high = a strong answer span exists, so low values abstain |
| cls_start | DESC | [CLS] start logit; high = no-answer start |
| cls_end | DESC | [CLS] end logit; high = no-answer end |
| margin | DESC | null_score - best_answer_score (definition preserved); high = null dominates the best span |

## Task 4 — core comparison

| Model | Ranking statistic | K | True abstention | False abstention | Spurious | EM | F1 | Conditional F1 |
|---|---|--:|---|---|--:|--:|--:|--:|
| F2 | null_score | 47 | 8/42 | 39/140 | 34 | 2.86 | 16.92 | 23.46 |
| F2 | best_answer_score | 47 | 21/42 | 26/140 | 21 | 2.86 | 15.41 | 18.92 |
| F2 | cls_start | 47 | 4/42 | 43/140 | 38 | 2.14 | 14.97 | 21.61 |
| F2 | cls_end | 47 | 5/42 | 42/140 | 37 | 2.86 | 18.09 | 25.84 |
| F2 | margin | 47 | 20/42 | 27/140 | 22 | 2.86 | 15.62 | 19.35 |
| A0 | null_score | 47 | 6/42 | 41/140 | 36 | 5.0 | 18.32 | 25.9 |
| A0 | best_answer_score | 47 | 11/42 | 36/140 | 31 | 2.14 | 17.03 | 22.93 |
| A0 | cls_start | 47 | 6/42 | 41/140 | 36 | 5.0 | 18.08 | 25.56 |
| A0 | cls_end | 47 | 5/42 | 42/140 | 37 | 5.0 | 18.22 | 26.03 |
| A0 | margin | 47 | 7/42 | 40/140 | 35 | 3.57 | 17.36 | 24.31 |

## Task 5 — abstention quality

| Model | statistic | unanswerable caught /42 | answerable rejected /140 | abstention precision |
|---|---|---|---|---|
| F2 | null_score | 8/42 | 39/140 | 0.1702 |
| F2 | best_answer_score | 21/42 | 26/140 | 0.4468 |
| F2 | cls_start | 4/42 | 43/140 | 0.0851 |
| F2 | cls_end | 5/42 | 42/140 | 0.1064 |
| F2 | margin | 20/42 | 27/140 | 0.4255 |
| A0 | null_score | 6/42 | 41/140 | 0.1277 |
| A0 | best_answer_score | 11/42 | 36/140 | 0.234 |
| A0 | cls_start | 6/42 | 41/140 | 0.1277 |
| A0 | cls_end | 5/42 | 42/140 | 0.1064 |
| A0 | margin | 7/42 | 40/140 | 0.1489 |

## Task 6 — retained answer quality vs the K=47 null_score reference

- reference: F2 null_score K47 = EM 2.86 / F1 16.92; A0 null_score K47 = EM 5.0 / F1 18.32 (reference values, not optimization targets)

| Model | statistic | EM (retained ans.) | F1 (retained ans.) | correct retained | incorrect retained | overlap w/ null_score set |
|---|---|--:|--:|--:|--:|--:|
| F2 | null_score | 3.96 | 23.46 | 4 | 97 | 47/47 |
| F2 | best_answer_score | 3.51 | 18.92 | 4 | 110 | 2/47 |
| F2 | cls_start | 3.09 | 21.61 | 3 | 94 | 38/47 |
| F2 | cls_end | 4.08 | 25.84 | 4 | 94 | 21/47 |
| F2 | margin | 3.54 | 19.35 | 4 | 109 | 9/47 |
| A0 | null_score | 7.07 | 25.9 | 7 | 92 | 47/47 |
| A0 | best_answer_score | 2.88 | 22.93 | 3 | 101 | 14/47 |
| A0 | cls_start | 7.07 | 25.56 | 7 | 92 | 46/47 |
| A0 | cls_end | 7.14 | 26.03 | 7 | 91 | 45/47 |
| A0 | margin | 5.0 | 24.31 | 5 | 95 | 30/47 |

## Task 7 — category abstention counts

### F2

| statistic | category | n | abstained | retained | EM | F1 |
|---|---|--:|--:|--:|--:|--:|
| null_score | DIRECT_SPAN | 24 | 1 | 23 | 12.5 | 46.3 |
| null_score | NUMERIC | 20 | 0 | 20 | 5.0 | 39.8 |
| null_score | TABLE_CELL | 24 | 2 | 22 | 0.0 | 1.2 |
| null_score | TABLE_ROW | 16 | 0 | 16 | 0.0 | 11.1 |
| null_score | LIST_ITEM | 20 | 6 | 14 | 0.0 | 10.8 |
| null_score | SECTION_SPECIFIC | 16 | 13 | 3 | 0.0 | 0.0 |
| null_score | MULTI_CHUNK | 10 | 7 | 3 | 0.0 | 4.0 |
| null_score | LONG_CONTEXT | 10 | 10 | 0 | 0.0 | 0.0 |
| best_answer_score | DIRECT_SPAN | 24 | 0 | 24 | 12.5 | 47.4 |
| best_answer_score | NUMERIC | 20 | 7 | 13 | 5.0 | 25.5 |
| best_answer_score | TABLE_CELL | 24 | 1 | 23 | 0.0 | 0.0 |
| best_answer_score | TABLE_ROW | 16 | 4 | 12 | 0.0 | 3.3 |
| best_answer_score | LIST_ITEM | 20 | 11 | 9 | 0.0 | 6.4 |
| best_answer_score | SECTION_SPECIFIC | 16 | 3 | 13 | 0.0 | 0.7 |
| best_answer_score | MULTI_CHUNK | 10 | 0 | 10 | 0.0 | 21.7 |
| best_answer_score | LONG_CONTEXT | 10 | 0 | 10 | 0.0 | 10.0 |
| cls_start | DIRECT_SPAN | 24 | 8 | 16 | 8.3 | 34.9 |
| cls_start | NUMERIC | 20 | 0 | 20 | 5.0 | 39.8 |
| cls_start | TABLE_CELL | 24 | 0 | 24 | 0.0 | 1.2 |
| cls_start | TABLE_ROW | 16 | 0 | 16 | 0.0 | 11.1 |
| cls_start | LIST_ITEM | 20 | 6 | 14 | 0.0 | 10.8 |
| cls_start | SECTION_SPECIFIC | 16 | 12 | 4 | 0.0 | 0.0 |
| cls_start | MULTI_CHUNK | 10 | 7 | 3 | 0.0 | 4.0 |
| cls_start | LONG_CONTEXT | 10 | 10 | 0 | 0.0 | 0.0 |
| cls_end | DIRECT_SPAN | 24 | 0 | 24 | 12.5 | 47.4 |
| cls_end | NUMERIC | 20 | 0 | 20 | 5.0 | 39.8 |
| cls_end | TABLE_CELL | 24 | 17 | 7 | 0.0 | 1.2 |
| cls_end | TABLE_ROW | 16 | 7 | 9 | 0.0 | 8.5 |
| cls_end | LIST_ITEM | 20 | 4 | 16 | 0.0 | 12.3 |
| cls_end | SECTION_SPECIFIC | 16 | 5 | 11 | 0.0 | 0.7 |
| cls_end | MULTI_CHUNK | 10 | 2 | 8 | 0.0 | 12.7 |
| cls_end | LONG_CONTEXT | 10 | 7 | 3 | 0.0 | 5.0 |
| margin | DIRECT_SPAN | 24 | 0 | 24 | 12.5 | 47.4 |
| margin | NUMERIC | 20 | 6 | 14 | 5.0 | 25.5 |
| margin | TABLE_CELL | 24 | 1 | 23 | 0.0 | 0.0 |
| margin | TABLE_ROW | 16 | 3 | 13 | 0.0 | 6.2 |
| margin | LIST_ITEM | 20 | 8 | 12 | 0.0 | 10.1 |
| margin | SECTION_SPECIFIC | 16 | 4 | 12 | 0.0 | 0.7 |
| margin | MULTI_CHUNK | 10 | 0 | 10 | 0.0 | 21.7 |
| margin | LONG_CONTEXT | 10 | 5 | 5 | 0.0 | 1.0 |

### A0

| statistic | category | n | abstained | retained | EM | F1 |
|---|---|--:|--:|--:|--:|--:|
| null_score | DIRECT_SPAN | 24 | 10 | 14 | 8.3 | 24.9 |
| null_score | NUMERIC | 20 | 5 | 15 | 15.0 | 35.0 |
| null_score | TABLE_CELL | 24 | 8 | 16 | 8.3 | 10.4 |
| null_score | TABLE_ROW | 16 | 9 | 7 | 0.0 | 15.3 |
| null_score | LIST_ITEM | 20 | 6 | 14 | 0.0 | 12.3 |
| null_score | SECTION_SPECIFIC | 16 | 0 | 16 | 0.0 | 21.9 |
| null_score | MULTI_CHUNK | 10 | 3 | 7 | 0.0 | 6.5 |
| null_score | LONG_CONTEXT | 10 | 0 | 10 | 0.0 | 11.2 |
| best_answer_score | DIRECT_SPAN | 24 | 4 | 20 | 4.2 | 31.2 |
| best_answer_score | NUMERIC | 20 | 2 | 18 | 10.0 | 37.7 |
| best_answer_score | TABLE_CELL | 24 | 5 | 19 | 0.0 | 1.5 |
| best_answer_score | TABLE_ROW | 16 | 12 | 4 | 0.0 | 9.1 |
| best_answer_score | LIST_ITEM | 20 | 4 | 16 | 0.0 | 11.9 |
| best_answer_score | SECTION_SPECIFIC | 16 | 1 | 15 | 0.0 | 17.7 |
| best_answer_score | MULTI_CHUNK | 10 | 6 | 4 | 0.0 | 8.0 |
| best_answer_score | LONG_CONTEXT | 10 | 2 | 8 | 0.0 | 10.0 |
| cls_start | DIRECT_SPAN | 24 | 10 | 14 | 8.3 | 24.9 |
| cls_start | NUMERIC | 20 | 6 | 14 | 15.0 | 33.3 |
| cls_start | TABLE_CELL | 24 | 8 | 16 | 8.3 | 10.4 |
| cls_start | TABLE_ROW | 16 | 9 | 7 | 0.0 | 15.3 |
| cls_start | LIST_ITEM | 20 | 6 | 14 | 0.0 | 12.3 |
| cls_start | SECTION_SPECIFIC | 16 | 0 | 16 | 0.0 | 21.9 |
| cls_start | MULTI_CHUNK | 10 | 2 | 8 | 0.0 | 6.5 |
| cls_start | LONG_CONTEXT | 10 | 0 | 10 | 0.0 | 11.2 |
| cls_end | DIRECT_SPAN | 24 | 10 | 14 | 8.3 | 24.9 |
| cls_end | NUMERIC | 20 | 5 | 15 | 15.0 | 35.0 |
| cls_end | TABLE_CELL | 24 | 8 | 16 | 8.3 | 10.4 |
| cls_end | TABLE_ROW | 16 | 10 | 6 | 0.0 | 14.5 |
| cls_end | LIST_ITEM | 20 | 6 | 14 | 0.0 | 12.3 |
| cls_end | SECTION_SPECIFIC | 16 | 0 | 16 | 0.0 | 21.9 |
| cls_end | MULTI_CHUNK | 10 | 3 | 7 | 0.0 | 6.5 |
| cls_end | LONG_CONTEXT | 10 | 0 | 10 | 0.0 | 11.2 |
| margin | DIRECT_SPAN | 24 | 7 | 17 | 8.3 | 28.4 |
| margin | NUMERIC | 20 | 1 | 19 | 15.0 | 41.4 |
| margin | TABLE_CELL | 24 | 8 | 16 | 0.0 | 0.6 |
| margin | TABLE_ROW | 16 | 13 | 3 | 0.0 | 7.4 |
| margin | LIST_ITEM | 20 | 6 | 14 | 0.0 | 12.3 |
| margin | SECTION_SPECIFIC | 16 | 0 | 16 | 0.0 | 21.9 |
| margin | MULTI_CHUNK | 10 | 5 | 5 | 0.0 | 8.0 |
| margin | LONG_CONTEXT | 10 | 0 | 10 | 0.0 | 11.2 |

## Task 8 — answerability ranking signal

| Model | statistic | true abst | false abst | true/false ratio | Δtrue vs null | Δfalse vs null | ΔF1 vs null | classification |
|---|---|--:|--:|--:|--:|--:|--:|---|
| F2 | null_score | 8 | 39 | 0.2051 | 0 | 0 | 0.0 | SIMILAR_TO_NULL |
| F2 | best_answer_score | 21 | 26 | 0.8077 | 13 | -13 | -1.51 | MORE_INFORMATIVE_THAN_NULL |
| F2 | cls_start | 4 | 43 | 0.093 | -4 | 4 | -1.95 | LESS_INFORMATIVE_THAN_NULL |
| F2 | cls_end | 5 | 42 | 0.119 | -3 | 3 | 1.17 | LESS_INFORMATIVE_THAN_NULL |
| F2 | margin | 20 | 27 | 0.7407 | 12 | -12 | -1.3 | MORE_INFORMATIVE_THAN_NULL |
| A0 | null_score | 6 | 41 | 0.1463 | 0 | 0 | 0.0 | SIMILAR_TO_NULL |
| A0 | best_answer_score | 11 | 36 | 0.3056 | 5 | -5 | -1.29 | MORE_INFORMATIVE_THAN_NULL |
| A0 | cls_start | 6 | 41 | 0.1463 | 0 | 0 | -0.24 | SIMILAR_TO_NULL |
| A0 | cls_end | 5 | 42 | 0.119 | -1 | 1 | -0.1 | SIMILAR_TO_NULL |
| A0 | margin | 7 | 40 | 0.175 | 1 | -1 | -0.96 | SIMILAR_TO_NULL |

### Pre-specified classification rule

- **MORE_INFORMATIVE_THAN_NULL**: delta_true >= +3 AND delta_false <= 0
- **LESS_INFORMATIVE_THAN_NULL**: delta_true <= -3 AND delta_false >= 0
- **SIMILAR_TO_NULL**: |delta_true| <= 2 AND |delta_false| <= 2 AND |delta_F1| <= 1.5
- **INSUFFICIENT_DIFFERENCE**: otherwise (mixed/inconsistent movement that crosses none of the above)

## Task 9 — checkpoint comparison at K=47, per statistic

| statistic | F2 true | A0 true | F2 false | A0 false | F2 cond F1 | A0 cond F1 |
|---|---|---|---|---|---|---|
| null_score | 8/42 | 6/42 | 39/140 | 41/140 | 23.46 | 25.9 |
| best_answer_score | 21/42 | 11/42 | 26/140 | 36/140 | 18.92 | 22.93 |
| cls_start | 4/42 | 6/42 | 43/140 | 41/140 | 21.61 | 25.56 |
| cls_end | 5/42 | 5/42 | 42/140 | 42/140 | 25.84 | 26.03 |
| margin | 20/42 | 7/42 | 27/140 | 40/140 | 19.35 | 24.31 |

## Interpretation boundary

- No inference, no model loading, no training, no database, no retrieval was used.
- K=47 was fixed before evaluation and was neither searched nor tuned.
- No threshold is used in this experiment.
- Statistics are used exactly as recorded; none was reversed or re-derived.
- Classifications are descriptive comparisons to null_score under a pre-specified rule; no statistic is declared a winner.
- No architectural claim (H-A..H-E) is made.
