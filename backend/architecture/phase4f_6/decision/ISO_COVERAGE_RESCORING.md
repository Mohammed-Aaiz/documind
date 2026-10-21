# Iso-Coverage Abstention Re-scoring (F2 vs A0 at identical abstention counts)

> **PROVENANCE (2026-09-28) - PRE-RECONSTRUCTION-FIX answer text.** EM/F1 below
> and the `original_correct` rate are pre-fix; the `null_score` ranking and the abstention sets are NOT affected.
> The input predictions' answer TEXT came from `tokenizer.decode()`, which re-inserts spaces at subword
> boundaries and corrupted split values (`142.6 million` -> `142. 6 million`). Logit/score-derived signals are
> unaffected: span and score are bit-identical before vs after. On the same 182 examples, same checkpoints,
> same spans, only the decoder changed: F2 answerable EM 2.86% -> 14.29%, F1 16.92% -> 28.91%.
> Leaked population; not a generalization result. Full record: `E0_PREDICTION_PROVENANCE_2026-09-28.md`.

- compare F2 and A0 at the SAME abstention aggressiveness, removing the checkpoint-specific threshold-scale effect found when the single constant 1.5705 was applied to both
- Method: null_score DESC, example_id ASC (deterministic tie-break); exactly the top K examples per checkpoint, ranked independently.
- K fixed before evaluation: **A = 47/182** (F2 recorded G point), **B = 95/182** (A0 recorded G point). Not fitted, not tuned, not searched. No threshold is used.
- Inputs: `backend/architecture/phase4f_6/e0_diagnostics/diagnostics/model_40min_predictions.json` sha256 `d7d9d65e944488ac...`, benchmark `1166bf4ff38265c2...` (verified). No inference was run.

## Task 3 — metrics at fixed abstention counts

| Model | K | Abstention % | EM | F1 | True abstention | False abstention | Spurious | Answerable coverage | Overall non-empty coverage |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|
| F2 | 47 | 25.8% | 2.86 | 16.92 | 8/42 = 19.0% | 39/140 = 27.9% | 34 = 18.7% | 72.14% | 74.18% |
| F2 | 95 | 52.2% | 0.71 | 12.47 | 20/42 = 47.6% | 75/140 = 53.6% | 22 = 12.1% | 46.43% | 47.8% |
| A0 | 47 | 25.8% | 5.0 | 18.32 | 6/42 = 14.3% | 41/140 = 29.3% | 36 = 19.8% | 70.71% | 74.18% |
| A0 | 95 | 52.2% | 2.86 | 12.16 | 22/42 = 52.4% | 73/140 = 52.1% | 20 = 11.0% | 47.86% | 47.8% |

## Task 4 — retained-answer quality vs removed answers

| Model | K | correct retained | incorrect retained | abstained CORRECT | abstained incorrect | conditional EM (retained ans.) | conditional F1 (retained ans.) |
|---|---:|---:|---:|---:|---:|---:|---:|
| F2 | 47 | 4 | 97 | 0 | 39 | 3.96 | 23.46 |
| F2 | 95 | 1 | 64 | 3 | 72 | 1.54 | 26.86 |
| A0 | 47 | 7 | 92 | 0 | 41 | 7.07 | 25.9 |
| A0 | 95 | 4 | 63 | 3 | 70 | 5.97 | 25.41 |

## Task 5 — category effects

### F2 @ K=47

| category | n | abstained_n | retained_n | EM | F1 |
|---|---:|---:|---:|---:|---:|
| DIRECT_SPAN | 24 | 1 | 23 | 12.5 | 46.3 |
| NUMERIC | 20 | 0 | 20 | 5.0 | 39.8 |
| TABLE_CELL | 24 | 2 | 22 | 0.0 | 1.2 |
| TABLE_ROW | 16 | 0 | 16 | 0.0 | 11.1 |
| LIST_ITEM | 20 | 6 | 14 | 0.0 | 10.8 |
| SECTION_SPECIFIC | 16 | 13 | 3 | 0.0 | 0.0 |
| MULTI_CHUNK | 10 | 7 | 3 | 0.0 | 4.0 |
| LONG_CONTEXT | 10 | 10 | 0 | 0.0 | 0.0 |

### F2 @ K=95

| category | n | abstained_n | retained_n | EM | F1 |
|---|---:|---:|---:|---:|---:|
| DIRECT_SPAN | 24 | 11 | 13 | 0.0 | 24.9 |
| NUMERIC | 20 | 0 | 20 | 5.0 | 39.8 |
| TABLE_CELL | 24 | 14 | 10 | 0.0 | 1.2 |
| TABLE_ROW | 16 | 6 | 10 | 0.0 | 8.5 |
| LIST_ITEM | 20 | 9 | 11 | 0.0 | 8.0 |
| SECTION_SPECIFIC | 16 | 16 | 0 | 0.0 | 0.0 |
| MULTI_CHUNK | 10 | 9 | 1 | 0.0 | 2.9 |
| LONG_CONTEXT | 10 | 10 | 0 | 0.0 | 0.0 |

### A0 @ K=47

| category | n | abstained_n | retained_n | EM | F1 |
|---|---:|---:|---:|---:|---:|
| DIRECT_SPAN | 24 | 10 | 14 | 8.3 | 24.9 |
| NUMERIC | 20 | 5 | 15 | 15.0 | 35.0 |
| TABLE_CELL | 24 | 8 | 16 | 8.3 | 10.4 |
| TABLE_ROW | 16 | 9 | 7 | 0.0 | 15.3 |
| LIST_ITEM | 20 | 6 | 14 | 0.0 | 12.3 |
| SECTION_SPECIFIC | 16 | 0 | 16 | 0.0 | 21.9 |
| MULTI_CHUNK | 10 | 3 | 7 | 0.0 | 6.5 |
| LONG_CONTEXT | 10 | 0 | 10 | 0.0 | 11.2 |

### A0 @ K=95

| category | n | abstained_n | retained_n | EM | F1 |
|---|---:|---:|---:|---:|---:|
| DIRECT_SPAN | 24 | 12 | 12 | 8.3 | 23.5 |
| NUMERIC | 20 | 10 | 10 | 10.0 | 23.7 |
| TABLE_CELL | 24 | 18 | 6 | 0.0 | 0.0 |
| TABLE_ROW | 16 | 16 | 0 | 0.0 | 0.0 |
| LIST_ITEM | 20 | 7 | 13 | 0.0 | 10.1 |
| SECTION_SPECIFIC | 16 | 0 | 16 | 0.0 | 21.9 |
| MULTI_CHUNK | 10 | 9 | 1 | 0.0 | 0.0 |
| LONG_CONTEXT | 10 | 1 | 9 | 0.0 | 11.2 |

## Task 7 — comparison with previous measured results

Label: **OPERATING_POINT_ANALYSIS** (the OFF rows are MODEL_ONLY).

| Measurement | Policy | EM | F1 |
|---|---|---:|---:|
| F2 off | no gate | 2.86 | 19.69 |
| F2 on | G 1.5705 (K=47) | 2.86 | 16.92 |
| F2 on | iso K=47 | 2.86 | 16.92 |
| F2 on | iso K=95 | 0.71 | 12.47 |
| A0 off | no gate | 5.0 | 24.44 |
| A0 on | G 1.5705 (K=95) | 2.86 | 12.16 |
| A0 on | iso K=47 | 5.0 | 18.32 |
| A0 on | iso K=95 | 2.86 | 12.16 |

iso-coverage rows are directly comparable across checkpoints because the abstention count is identical; the 1.5705 rows are not, because the constant fires at different rates per checkpoint.

## Interpretation boundary

- No inference, no training, no retrieval, no database was used.
- K values were fixed before evaluation and were neither fitted, tuned, nor searched.
- No operating point is claimed to be optimal.
- No architectural claim (H-A..H-E) is made from this experiment.
- Answerable and unanswerable analyses are reported with explicit separate denominators.
