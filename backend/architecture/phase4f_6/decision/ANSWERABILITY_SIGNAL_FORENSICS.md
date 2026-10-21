# Answerability Signal Forensics

> **PROVENANCE (2026-09-28) - PRE-RECONSTRUCTION-FIX answer text.** Only
> `empirical_correctness_rate` is affected (it reads the recorded per-example `em` flag, which is text-derived);
> every AUC / discrimination metric here is score-derived and NOT affected. The input predictions' answer TEXT
> came from `tokenizer.decode()`, which re-inserts spaces at subword boundaries and corrupted split values
> (`142.6 million` -> `142. 6 million`). Logit/score-derived signals are unaffected: span and score are
> bit-identical before vs after. Full record: `E0_PREDICTION_PROVENANCE_2026-09-28.md`.

**Date:** 2026-09-23T20:55:02.348115+05:30 · **Population:** 182 = 140 answerable + 42 unanswerable (positive class = UNANSWERABLE, prevalence 0.23077)

Threshold-free measurement of the answerability signal carried by the **already-recorded** extractive-QA scores. No inference, no model loading, no training, no database, no retrieval, no threshold fitting, no classifier, no derived combined score.

**Bootstrap:** seed `20260923`, 10000 stratified resamples, percentile 95% CI.

## Task 2 — Directions

| Statistic | Recorded field | Analysis direction | Sign for analysis only |
| --- | --- | --- | --- |
| `null_score` | `null_score` | HIGHER=UNANSWERABLE | 1.0 |
| `best_answer_score` | `best_answer_score` | REVERSED_FOR_ANALYSIS (LOWER=UNANSWERABLE) | -1.0 |
| `cls_start_logit` | `cls_start_logit` | HIGHER=UNANSWERABLE | 1.0 |
| `cls_end_logit` | `cls_end_logit` | HIGHER=UNANSWERABLE | 1.0 |
| `margin` | `margin` | HIGHER=UNANSWERABLE | 1.0 |
| `confidence` | `confidence` | EMPIRICALLY_TESTED_BOTH_DIRECTIONS | empirical |

## Task 13 — Decisive research table (12 rows)

| Model | Statistic | ROC-AUC | 95% CI | PR-AUC | Prevalence | ΔAUC vs 0.5 | ΔPR vs prev | K47 TP/FP % | K95 TP/FP % |
| --- | --- | --: | --- | --: | --: | --: | --: | --- | --- |
| F2 | `null_score` | 0.4303 | [0.3378, 0.5257] | 0.1974 | 0.23077 | -0.0697 | -0.0334 | 19.0/27.9 | 47.6/53.6 |
| F2 | `best_answer_score` | 0.7250 | [0.6270, 0.8167] | 0.4853 | 0.23077 | +0.2250 | +0.2545 | 50.0/18.6 | 78.6/44.3 |
| F2 | `cls_start_logit` | 0.4303 | [0.3474, 0.5148] | 0.1921 | 0.23077 | -0.0697 | -0.0386 | 9.5/30.7 | 47.6/53.6 |
| F2 | `cls_end_logit` | 0.4391 | [0.3517, 0.5262] | 0.1959 | 0.23077 | -0.0609 | -0.0349 | 11.9/30.0 | 42.9/55.0 |
| F2 | `margin` | 0.7338 | [0.6398, 0.8202] | 0.5492 | 0.23077 | +0.2338 | +0.3185 | 47.6/19.3 | 76.2/45.0 |
| F2 | `confidence` | 0.5224 | [0.4267, 0.6160] | 0.2998 | 0.23077 | +0.0224 | +0.0691 | n/a | n/a |
| A0 | `null_score` | 0.5257 | [0.4400, 0.6088] | 0.2495 | 0.23077 | +0.0257 | +0.0187 | 14.3/29.3 | 52.4/52.1 |
| A0 | `best_answer_score` | 0.5054 | [0.4078, 0.6043] | 0.2557 | 0.23077 | +0.0054 | +0.0249 | 26.2/25.7 | 47.6/53.6 |
| A0 | `cls_start_logit` | 0.5189 | [0.4332, 0.6037] | 0.2479 | 0.23077 | +0.0189 | +0.0171 | 14.3/29.3 | 52.4/52.1 |
| A0 | `cls_end_logit` | 0.5257 | [0.4403, 0.6087] | 0.2372 | 0.23077 | +0.0257 | +0.0065 | 11.9/30.0 | 52.4/52.1 |
| A0 | `margin` | 0.5432 | [0.4508, 0.6388] | 0.2599 | 0.23077 | +0.0432 | +0.0291 | 16.7/28.6 | 59.5/50.0 |
| A0 | `confidence` | 0.5009 | [0.4039, 0.5995] | 0.2458 | 0.23077 | +0.0009 | +0.0150 | n/a | n/a |

## Task 5 — Rank quality and separation

Distribution columns are the RAW recorded field values (not sign-flipped); only AUC / PR-AUC / Mann-Whitney U use the analysis-oriented score.

| Model | Statistic | mean ans | mean unans | median ans | median unans | U | rank-biserial | overlap |
| --- | --- | --: | --: | --: | --: | --: | --: | --: |
| F2 | `null_score` | 1.4422 | 1.3635 | 1.4140 | 1.3593 | 2530.0 | -0.1395 | 0.6429 |
| F2 | `best_answer_score` | 3.6176 | 2.9764 | 3.8538 | 2.9925 | 4263.0 | +0.4500 | 0.5119 |
| F2 | `cls_start_logit` | 0.7150 | 0.6619 | 0.6991 | 0.6711 | 2530.0 | -0.1395 | 0.6000 |
| F2 | `cls_end_logit` | 0.7272 | 0.7016 | 0.7570 | 0.7076 | 2582.0 | -0.1218 | 0.6024 |
| F2 | `margin` | -2.1754 | -1.6129 | -2.2906 | -1.6716 | 4315.0 | +0.4677 | 0.4571 |
| F2 | `confidence` | 0.0307 | 0.0323 | 0.0318 | 0.0296 | 3072.0 | +0.0449 | 0.6500 |
| A0 | `null_score` | 1.6094 | 2.1709 | 1.8968 | 2.2074 | 3091.0 | +0.0514 | 0.5690 |
| A0 | `best_answer_score` | -0.4481 | -0.5768 | -1.0939 | -0.5894 | 2972.0 | +0.0109 | 0.6714 |
| A0 | `cls_start_logit` | 0.6694 | 0.9555 | 0.6970 | 1.0209 | 3051.0 | +0.0378 | 0.5762 |
| A0 | `cls_end_logit` | 0.9400 | 1.2154 | 1.0690 | 1.2747 | 3091.0 | +0.0514 | 0.5381 |
| A0 | `margin` | 2.0575 | 2.7477 | 1.5338 | 3.4925 | 3194.0 | +0.0864 | 0.6548 |
| A0 | `confidence` | 0.2255 | 0.2159 | 0.1864 | 0.1242 | 2945.0 | +0.0017 | 0.6119 |

Overlap: equal-width bins over the combined (answerable + unanswerable) score range; overlap = sum of per-bin min(class densities).

## Task 7 — Checkpoint stability

| Statistic | F2 AUC | A0 AUC | ΔAUC | ΔPR-AUC | F2 CI | A0 CI | Classification |
| --- | --: | --: | --: | --: | --- | --- | --- |
| `null_score` | 0.4303 | 0.5257 | -0.0954 | -0.0521 | [0.3378, 0.5257] | [0.4400, 0.6088] | DIRECTION_CHANGE |
| `best_answer_score` | 0.7250 | 0.5054 | +0.2196 | +0.2296 | [0.6270, 0.8167] | [0.4078, 0.6043] | DIFFERENT_STRENGTH |
| `cls_start_logit` | 0.4303 | 0.5189 | -0.0886 | -0.0558 | [0.3474, 0.5148] | [0.4332, 0.6037] | DIRECTION_CHANGE |
| `cls_end_logit` | 0.4391 | 0.5257 | -0.0866 | -0.0413 | [0.3517, 0.5262] | [0.4403, 0.6087] | DIRECTION_CHANGE |
| `margin` | 0.7338 | 0.5432 | +0.1906 | +0.2893 | [0.6398, 0.8202] | [0.4508, 0.6388] | DIFFERENT_STRENGTH |
| `confidence` | 0.5224 | 0.5009 | +0.0215 | +0.0540 | [0.4267, 0.6160] | [0.4039, 0.5995] | DIFFERENT_STRENGTH |

## Task 8 — K-robustness cross-check (recorded values copied verbatim)

| Statistic | K47 F2 TP/FP | K47 A0 TP/FP | K95 F2 TP/FP | K95 A0 TP/FP | TP rate range (pp) |
| --- | --- | --- | --- | --- | --: |
| `null_score` | 19.0/27.9 | 14.3/29.3 | 47.6/53.6 | 52.4/52.1 | 38.1 |
| `best_answer_score` | 50.0/18.6 | 26.2/25.7 | 78.6/44.3 | 47.6/53.6 | 52.4 |
| `cls_start_logit` | 9.5/30.7 | 14.3/29.3 | 47.6/53.6 | 52.4/52.1 | 42.9 |
| `cls_end_logit` | 11.9/30.0 | 11.9/30.0 | 42.9/55.0 | 52.4/52.1 | 40.5 |
| `margin` | 47.6/19.3 | 16.7/28.6 | 76.2/45.0 | 59.5/50.0 | 59.5 |

## Task 10 — Confidence calibration forensics (raw confidence, not calibrated)

### F2

| Bin | count | mean confidence | empirical correctness | empirical answerable rate |
| --- | --: | --: | --: | --: |
| [0.0,0.1) | 182 | 0.0311 | 0.0220 | 0.7692 |
| [0.1,0.2) | 0 | — | — | — |
| [0.2,0.3) | 0 | — | — | — |
| [0.3,0.4) | 0 | — | — | — |
| [0.4,0.5) | 0 | — | — | — |
| [0.5,0.6) | 0 | — | — | — |
| [0.6,0.7) | 0 | — | — | — |
| [0.7,0.8) | 0 | — | — | — |
| [0.8,0.9) | 0 | — | — | — |
| [0.9,1.0) | 0 | — | — | — |

### A0

| Bin | count | mean confidence | empirical correctness | empirical answerable rate |
| --- | --: | --: | --: | --: |
| [0.0,0.1) | 70 | 0.0317 | 0.0286 | 0.7429 |
| [0.1,0.2) | 27 | 0.1416 | 0.0370 | 0.7407 |
| [0.2,0.3) | 33 | 0.2508 | 0.0303 | 0.8485 |
| [0.3,0.4) | 19 | 0.3466 | 0.0526 | 0.7368 |
| [0.4,0.5) | 12 | 0.4673 | 0.0000 | 0.6667 |
| [0.5,0.6) | 8 | 0.5496 | 0.1250 | 0.8750 |
| [0.6,0.7) | 5 | 0.6471 | 0.0000 | 1.0000 |
| [0.7,0.8) | 4 | 0.7326 | 0.0000 | 0.7500 |
| [0.8,0.9) | 2 | 0.8387 | 0.0000 | 1.0000 |
| [0.9,1.0] | 2 | 0.9416 | 0.5000 | 0.5000 |

## Task 11 — Spearman correlation matrices

### F2

| | `null_score` | `best_answer_score` | `cls_start_logit` | `cls_end_logit` | `margin` | `confidence` |
| --- | --: | --: | --: | --: | --: | --: |
| `null_score` | 1.0000 | 0.5090 | 0.7876 | 0.5720 | -0.1735 | -0.2487 |
| `best_answer_score` | 0.5090 | 1.0000 | 0.2682 | 0.4227 | -0.9206 | 0.4766 |
| `cls_start_logit` | 0.7876 | 0.2682 | 1.0000 | -0.0010 | 0.0108 | -0.3724 |
| `cls_end_logit` | 0.5720 | 0.4227 | -0.0010 | 1.0000 | -0.2313 | -0.0093 |
| `margin` | -0.1735 | -0.9206 | 0.0108 | -0.2313 | 1.0000 | -0.6911 |
| `confidence` | -0.2487 | 0.4766 | -0.3724 | -0.0093 | -0.6911 | 1.0000 |

### A0

| | `null_score` | `best_answer_score` | `cls_start_logit` | `cls_end_logit` | `margin` | `confidence` |
| --- | --: | --: | --: | --: | --: | --: |
| `null_score` | 1.0000 | -0.0395 | 0.9978 | 0.9979 | 0.7331 | -0.5821 |
| `best_answer_score` | -0.0395 | 1.0000 | -0.0331 | -0.0448 | -0.6677 | 0.7440 |
| `cls_start_logit` | 0.9978 | -0.0331 | 1.0000 | 0.9926 | 0.7273 | -0.5717 |
| `cls_end_logit` | 0.9979 | -0.0448 | 0.9926 | 1.0000 | 0.7349 | -0.5889 |
| `margin` | 0.7331 | -0.6677 | 0.7273 | 0.7349 | 1.0000 | -0.9221 |
| `confidence` | -0.5821 | 0.7440 | -0.5717 | -0.5889 | -0.9221 | 1.0000 |

## Task 12 — Category bias (mean unanswerability score / rank percentile)

### F2

| Statistic | DIRECT_SPAN | NUMERIC | TABLE_CELL | TABLE_ROW | LIST_ITEM | SECTION_SPECIFIC | MULTI_CHUNK | LONG_CONTEXT |
| --- | --: | --: | --: | --: | --: | --: | --: | --: |
| `null_score` | 1.363 / 44.7 | 1.148 / 17.4 | 1.384 / 48.3 | 1.261 / 33.4 | 1.457 / 53.9 | 1.726 / 82.9 | 1.665 / 78.1 | 1.943 / 96.5 |
| `best_answer_score` | -3.757 / 42.2 | -3.063 / 68.4 | -3.935 / 30.8 | -3.653 / 40.1 | -3.294 / 56.8 | -3.680 / 43.3 | -4.051 / 25.8 | -3.687 / 46.5 |
| `cls_start_logit` | 0.793 / 64.7 | 0.599 / 37.6 | 0.517 / 23.6 | 0.443 / 15.8 | 0.726 / 54.2 | 0.955 / 83.0 | 0.910 / 78.3 | 1.069 / 94.4 |
| `cls_end_logit` | 0.570 / 18.7 | 0.550 / 15.1 | 0.867 / 81.0 | 0.818 / 70.8 | 0.731 / 51.6 | 0.771 / 59.7 | 0.755 / 57.9 | 0.875 / 84.3 |
| `margin` | -2.394 / 36.1 | -1.915 / 56.8 | -2.551 / 26.8 | -2.392 / 32.7 | -1.837 / 59.0 | -1.955 / 55.8 | -2.385 / 36.7 | -1.744 / 67.4 |
| `confidence` | 0.039 / 69.5 | 0.036 / 62.1 | 0.041 / 73.8 | 0.041 / 73.0 | 0.018 / 18.7 | 0.018 / 19.3 | 0.024 / 35.9 | 0.014 / 7.4 |

### A0

| Statistic | DIRECT_SPAN | NUMERIC | TABLE_CELL | TABLE_ROW | LIST_ITEM | SECTION_SPECIFIC | MULTI_CHUNK | LONG_CONTEXT |
| --- | --: | --: | --: | --: | --: | --: | --: | --: |
| `null_score` | 2.400 / 53.3 | 1.992 / 51.0 | 3.681 / 62.8 | 5.595 / 77.5 | 0.358 / 42.3 | -5.326 / 7.7 | 4.051 / 67.7 | -1.246 / 26.6 |
| `best_answer_score` | -0.135 / 43.3 | -3.516 / 25.4 | -0.186 / 46.1 | 4.833 / 80.7 | 1.383 / 57.2 | 0.159 / 45.4 | 1.699 / 61.8 | 1.624 / 58.6 |
| `cls_start_logit` | 1.146 / 54.0 | 0.961 / 52.5 | 1.626 / 61.8 | 2.652 / 77.2 | 0.049 / 42.1 | -2.973 / 7.2 | 1.916 / 67.8 | -0.704 / 27.8 |
| `cls_end_logit` | 1.254 / 52.2 | 1.032 / 50.1 | 2.054 / 64.2 | 2.943 / 77.9 | 0.309 / 42.5 | -2.353 / 8.0 | 2.135 / 67.6 | -0.542 / 26.0 |
| `margin` | 2.265 / 51.4 | -1.524 / 32.6 | 3.495 / 56.9 | 10.428 / 85.5 | 1.741 / 47.9 | -5.167 / 12.5 | 5.750 / 69.8 | 0.377 / 42.2 |
| `confidence` | -0.250 / 47.1 | -0.473 / 22.0 | -0.181 / 56.8 | -0.033 / 84.7 | -0.160 / 55.9 | -0.288 / 33.2 | -0.126 / 64.6 | -0.215 / 45.2 |

## Task 14 — Answers from measurements only

- **Q-A. Does a stable answerability signal exist in the current extractive outputs?** SIGNAL_PARTIAL
- **Q-B. Signal properties:** checkpoint-stable = False; statistic-stable = False; budget-stable = see table above.
- **Q-C (score scale differences):** measured directly in the recorded same-constant different-behaviour result (the shared recorded constant 1.5705 abstained on 47 examples at F2 and 95 at A0)
- **Q-C (weak ranking signal):** threshold-free AUC range across all 12 combos: 0.4303-0.7338
- **Q-C (checkpoint capability differences):** measured separately: A0 retains more EM-correct answers at equal budget (recorded iso-coverage result)
- **Q-C (category specific uncertainty):** see task_12_category_bias

## Task 15 — Decision boundary

**VERDICT: `SIGNAL_PARTIAL`**

- Literal `SIGNAL_CONFIRMED` threshold-only clause met: **True** (by `F2/best_answer_score`, `F2/margin`)
- Applied tier gate: The given definitions separate SIGNAL_CONFIRMED from SIGNAL_PARTIAL only by whether the statistic is 'not stable across both checkpoints'. The literal threshold-only clause of SIGNAL_CONFIRMED is met by the F2 statistics listed, but the signal does not survive the checkpoint comparison (A0 shows no statistic above 0.5432 and five of six A0 CIs include 0.50, while three statistics reverse direction between checkpoints), so the applied verdict is the lower tier. Both readings are reported rather than resolved silently.
- Statistics reversing direction between checkpoints: `cls_end_logit`, `cls_start_logit`, `null_score`
- Best statistic per checkpoint: F2 = `margin`, A0 = `margin`

- `SIGNAL_CONFIRMED`: at least one statistic AUC > 0.70 with CI clearly above 0.50 AND PR-AUC materially above prevalence
- `SIGNAL_PARTIAL`: at least one statistic AUC > 0.60 with direction supported by the CI but signal not stable across both checkpoints
- `SIGNAL_WEAK`: AUC generally 0.55-0.60, or CIs overlap substantially with 0.50, or PR-AUC improvement is small
- `SIGNAL_ABSENT`: no statistic provides meaningful separation and results remain near random

### Measured structural notes (correlation)

- `F2`: Spearman margin~best_answer_score = -0.9206, margin~null_score = -0.1735, null_score~best_answer_score = +0.5090
- `A0`: Spearman margin~best_answer_score = -0.6677, margin~null_score = +0.7331, null_score~best_answer_score = -0.0395

- Most stable signal: `margin` (statistic with the highest worst-case AUC across the two checkpoints (min of F2/A0 AUC); STABLE_SIGNAL classifications take precedence)
- Smallest checkpoint delta: `confidence` (statistic with the smallest |dAUC| between checkpoints (may be small only because both are near chance))
- Most checkpoint-sensitive signal: `best_answer_score` (statistic with the largest |dAUC| between checkpoints)

## Interpretation boundary

- No inference, no model loading, no training, no database, no retrieval was used.
- No threshold was fitted and no K was searched; every statistic is evaluated threshold-free (AUC/PR-AUC) or at the already-recorded K values.
- No classifier and no derived/combined score were created.
- ROC-AUC and PR-AUC are ranking-quality measurements, not causal effects and not architectural evidence.
- A weak or absent answerability signal measures the CURRENT extractive outputs only; it does not prove anything about a differently designed answerability component.
- No statistic is declared universally superior; results are reported per checkpoint and per budget.

## Integrity

| Artifact | Recorded | Match |
| --- | --- | --- |
| benchmark | `1166bf4ff38265c209614ac2…` / expected `1166bf4ff38265c209614ac2…` | MATCH |
| dataset | `a517530354fc9bcaeef6f1aa…` / expected `a517530354fc9bcaeef6f1aa…` | MATCH |
| production model | `cb9f1dde94fca0e1f82c440b…` / expected `cb9f1dde94fca0e1f82c440b…` | MATCH |
| F2 model | `717463178eeb37ee3a642406…` / expected `717463178eeb37ee3a642406…` | MATCH |
| F2 checkpoint (dir scope) | `416b63642ba80a1c4f11257d…` / expected `416b63642ba80a1c4f11257d…` | MATCH |
| source corpus fingerprint | `3ec81cc5868f29a047409358…` / expected `3ec81cc5868f29a047409358…` | MATCH |
| chunk corpus fingerprint | `e6965cdad6684c65b739a316…` / expected `e6965cdad6684c65b739a316…` | MATCH |
