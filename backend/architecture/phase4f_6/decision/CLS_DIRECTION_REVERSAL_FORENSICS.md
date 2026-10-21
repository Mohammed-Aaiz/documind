# CLS / NULL Direction-Reversal Forensics

**Date:** 2026-09-23T21:01:39.808680+05:30 · **Population:** 182 = 140 answerable + 42 unanswerable (positive class = UNANSWERABLE)

**Question:** why are null_score / cls_start_logit / cls_end_logit anti-predictive for unanswerability at F2 but weakly positive at A0?

Bounded score-distribution forensics on the frozen prediction artifact. No model loading, no inference, no GPU, no training, no database, no retrieval, no threshold fitting, no K search, no new combined score. Direction convention everywhere: **higher oriented score = more likely unanswerable** (`best_answer_score` sign-reversed as recorded).

## 1. Input integrity

- F2 rows 182 / A0 rows 182; order + identity match: True; labels identical: True
- class counts {'answerable': 140, 'unanswerable': 42}
- **structural categories containing zero unanswerable examples: DIRECT_SPAN, LIST_ITEM, LONG_CONTEXT, MULTI_CHUNK, NUMERIC, SECTION_SPECIFIC, TABLE_CELL, TABLE_ROW**

### Category × answerability (as recorded)

| Category | ANSWERABLE | UNANSWERABLE |
| --- | --: | --: |
| `DIRECT_SPAN` | 24 | 0 |
| `LIST_ITEM` | 20 | 0 |
| `LONG_CONTEXT` | 10 | 0 |
| `MULTI_CHUNK` | 10 | 0 |
| `NUMERIC` | 20 | 0 |
| `SECTION_SPECIFIC` | 16 | 0 |
| `TABLE_CELL` | 24 | 0 |
| `TABLE_ROW` | 16 | 0 |
| `UNANSWERABLE` | 0 | 42 |

## 2. Class-conditional distributions

### F2

| Statistic | class | n | mean | median | std | min | q05 | q25 | q75 | q95 | max | IQR |
| --- | --- | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: |
| `null_score` | answerable | 140 | 1.4422 | 1.4140 | 0.2741 | 0.8649 | 0.9980 | 1.2612 | 1.6070 | 1.9285 | 2.0633 | 0.3458 |
| `null_score` | unanswerable | 42 | 1.3635 | 1.3593 | 0.2016 | 0.9779 | 1.0160 | 1.2219 | 1.5267 | 1.6409 | 1.6891 | 0.3048 |
| `cls_start_logit` | answerable | 140 | 0.7150 | 0.6991 | 0.2340 | 0.1826 | 0.3276 | 0.5501 | 0.9102 | 1.1016 | 1.2563 | 0.3601 |
| `cls_start_logit` | unanswerable | 42 | 0.6619 | 0.6711 | 0.1339 | 0.4004 | 0.4630 | 0.5644 | 0.7554 | 0.8910 | 0.9395 | 0.1910 |
| `cls_end_logit` | answerable | 140 | 0.7272 | 0.7570 | 0.1467 | 0.4032 | 0.4822 | 0.6130 | 0.8302 | 0.9561 | 1.0368 | 0.2172 |
| `cls_end_logit` | unanswerable | 42 | 0.7016 | 0.7076 | 0.1194 | 0.3047 | 0.5644 | 0.6181 | 0.7859 | 0.8782 | 0.9478 | 0.1678 |
| `best_answer_score` | answerable | 140 | -3.6176 | -3.8538 | 0.6467 | -4.5590 | -4.4707 | -4.0354 | -3.3292 | -2.3287 | -1.7267 | 0.7063 |
| `best_answer_score` | unanswerable | 42 | -2.9764 | -2.9925 | 0.8261 | -4.5453 | -4.2363 | -3.5357 | -2.3498 | -1.7533 | -1.2200 | 1.1860 |
| `margin` | answerable | 140 | -2.1754 | -2.2906 | 0.5681 | -3.0954 | -2.9257 | -2.6447 | -1.7858 | -1.2021 | -0.5646 | 0.8589 |
| `margin` | unanswerable | 42 | -1.6129 | -1.6716 | 0.7104 | -3.1379 | -2.7232 | -2.0996 | -1.0125 | -0.5722 | -0.2063 | 1.0872 |
| `confidence` | answerable | 140 | 0.0307 | 0.0318 | 0.0125 | 0.0116 | 0.0135 | 0.0189 | 0.0417 | 0.0499 | 0.0563 | 0.0228 |
| `confidence` | unanswerable | 42 | 0.0323 | 0.0296 | 0.0134 | 0.0145 | 0.0171 | 0.0223 | 0.0375 | 0.0576 | 0.0710 | 0.0152 |

| Statistic | mean Δ (unans−ans) | median Δ | Cohen d | U | ROC-AUC | rank-biserial | KS |
| --- | --: | --: | --: | --: | --: | --: | --: |
| `null_score` | -0.0787 | -0.0547 | -0.3035 | 2530.0 | 0.4303 | -0.1395 | 0.2286 |
| `cls_start_logit` | -0.0531 | -0.0280 | -0.2467 | 2530.0 | 0.4303 | -0.1395 | 0.2381 |
| `cls_end_logit` | -0.0256 | -0.0493 | -0.1816 | 2582.0 | 0.4391 | -0.1218 | 0.2357 |
| `best_answer_score` | +0.6412 | +0.8613 | +0.9270 | 4263.0 | 0.7250 | +0.4500 | 0.4310 |
| `margin` | +0.5625 | +0.6190 | +0.9321 | 4315.0 | 0.7338 | +0.4677 | 0.3833 |
| `confidence` | +0.0016 | -0.0022 | +0.1250 | 3072.0 | 0.5224 | +0.0449 | 0.1500 |

### A0

| Statistic | class | n | mean | median | std | min | q05 | q25 | q75 | q95 | max | IQR |
| --- | --- | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: |
| `null_score` | answerable | 140 | 1.6094 | 1.8968 | 4.6733 | -8.8582 | -6.4760 | -1.8219 | 5.3122 | 8.3568 | 10.4906 | 7.1342 |
| `null_score` | unanswerable | 42 | 2.1709 | 2.2074 | 2.9760 | -2.1398 | -1.5301 | -0.2315 | 4.0211 | 6.5732 | 10.7715 | 4.2525 |
| `cls_start_logit` | answerable | 140 | 0.6694 | 0.6970 | 2.3699 | -4.4236 | -3.3101 | -1.0146 | 2.5824 | 4.0866 | 5.1413 | 3.5971 |
| `cls_start_logit` | unanswerable | 42 | 0.9555 | 1.0209 | 1.5397 | -1.2328 | -0.9965 | -0.3957 | 1.9454 | 3.3797 | 5.4282 | 2.3411 |
| `cls_end_logit` | answerable | 140 | 0.9400 | 1.0690 | 2.3099 | -4.4347 | -3.0431 | -0.7684 | 2.7460 | 4.3167 | 5.3933 | 3.5144 |
| `cls_end_logit` | unanswerable | 42 | 1.2154 | 1.2747 | 1.4452 | -0.9698 | -0.5361 | 0.0355 | 2.0462 | 3.1935 | 5.3433 | 2.0107 |
| `best_answer_score` | answerable | 140 | 0.4481 | 1.0939 | 4.1334 | -10.1258 | -6.5810 | -2.7185 | 3.3354 | 6.5639 | 9.7681 | 6.0539 |
| `best_answer_score` | unanswerable | 42 | 0.5768 | 0.5894 | 4.4894 | -13.9565 | -5.7185 | -1.1514 | 3.2021 | 6.0160 | 12.8282 | 4.3535 |
| `margin` | answerable | 140 | 2.0575 | 1.5338 | 6.3114 | -10.0620 | -6.2618 | -3.2535 | 7.0589 | 12.3224 | 17.6363 | 10.3124 |
| `margin` | unanswerable | 42 | 2.7477 | 3.4925 | 5.7303 | -10.6530 | -5.9603 | -0.5349 | 5.4765 | 10.8590 | 22.2717 | 6.0115 |
| `confidence` | answerable | 140 | 0.2255 | 0.1864 | 0.2175 | 0.0001 | 0.0021 | 0.0253 | 0.3275 | 0.6522 | 0.9168 | 0.3022 |
| `confidence` | unanswerable | 42 | 0.2159 | 0.1242 | 0.2161 | 0.0000 | 0.0045 | 0.0610 | 0.3373 | 0.5573 | 0.9664 | 0.2763 |

| Statistic | mean Δ (unans−ans) | median Δ | Cohen d | U | ROC-AUC | rank-biserial | KS |
| --- | --: | --: | --: | --: | --: | --: | --: |
| `null_score` | +0.5615 | +0.3106 | +0.1292 | 3091.0 | 0.5257 | +0.0514 | 0.2190 |
| `cls_start_logit` | +0.2861 | +0.3239 | +0.1295 | 3051.0 | 0.5189 | +0.0378 | 0.2214 |
| `cls_end_logit` | +0.2754 | +0.2056 | +0.1285 | 3091.0 | 0.5257 | +0.0514 | 0.2476 |
| `best_answer_score` | +0.1287 | -0.5045 | +0.0305 | 2972.0 | 0.5054 | +0.0109 | 0.1095 |
| `margin` | +0.6902 | +1.9587 | +0.1116 | 3194.0 | 0.5432 | +0.0864 | 0.2071 |
| `confidence` | -0.0096 | -0.0622 | -0.0443 | 2935.0 | 0.4991 | -0.0017 | 0.1357 |

## 3. Null-score component decomposition

Recorded identity `null_score = cls_start_logit + cls_end_logit` verified: max abs error 1.0e-06 (F2), 1.0e-06 (A0).

| Checkpoint | mean start (ans) | mean end (ans) | mean null (ans) | mean start (unans) | mean end (unans) | mean null (unans) | Δstart | Δend | Δnull |
| --- | --: | --: | --: | --: | --: | --: | --: | --: | --: |
| F2 | 0.7150 | 0.7272 | 1.4422 | 0.6619 | 0.7016 | 1.3635 | -0.0531 | -0.0256 | -0.0787 |
| A0 | 0.6694 | 0.9400 | 1.6094 | 0.9555 | 1.2154 | 2.1709 | +0.2861 | +0.2754 | +0.5615 |

- Δstart + Δend − Δnull = -0.0e+00 (F2) and 0.0e+00 (A0) → exact algebra holds.
- Median Δstart/Δend/Δnull = -0.0280/-0.0493/-0.0547 (F2), +0.3239/+0.2056/+0.3106 (A0) — descriptive only; `median(start)+median(end)=median(null)` is **not** an algebraic identity and is not asserted.
- **Classification: `BOTH_COMPONENTS`** (both components flip sign between checkpoints)

## 4. Direction reversal

| Statistic | F2 AUC | A0 AUC | ΔAUC | F2 direction | A0 direction | literal reversal | applied classification | ΔAUC 95% CI (paired) |
| --- | --: | --: | --: | --- | --- | --- | --- | --- |
| `null_score` | 0.4303 | 0.5257 | -0.0954 | UNANSWERABLE_LOWER | UNANSWERABLE_HIGHER | True | NEAR_CHANCE_BOTH | [-0.2248, +0.0330] |
| `cls_start_logit` | 0.4303 | 0.5189 | -0.0886 | UNANSWERABLE_LOWER | UNANSWERABLE_HIGHER | True | NEAR_CHANCE_BOTH | [-0.2134, +0.0383] |
| `cls_end_logit` | 0.4391 | 0.5257 | -0.0866 | UNANSWERABLE_LOWER | UNANSWERABLE_HIGHER | True | NEAR_CHANCE_BOTH | [-0.2075, +0.0337] |
| `best_answer_score` | 0.7250 | 0.5054 | +0.2196 | UNANSWERABLE_HIGHER | UNANSWERABLE_HIGHER | False | SAME_DIRECTION_DIFFERENT_STRENGTH | [+0.0833, +0.3486] |
| `margin` | 0.7338 | 0.5432 | +0.1906 | UNANSWERABLE_HIGHER | UNANSWERABLE_HIGHER | False | SAME_DIRECTION_DIFFERENT_STRENGTH | [+0.0560, +0.3155] |
| `confidence` | 0.5224 | 0.4991 | +0.0233 | UNANSWERABLE_HIGHER | UNANSWERABLE_LOWER | True | NEAR_CHANCE_BOTH | [-0.1100, +0.1629] |

Rule: (F2 AUC < 0.5 AND A0 AUC > 0.5) OR (F2 AUC > 0.5 AND A0 AUC < 0.5)

Caveat: the literal sign flip is only called an established reversal when at least one of the two 95% bootstrap AUC CIs excludes 0.50 in the direction of its point estimate; if both CIs include 0.50 the applied classification is NEAR_CHANCE_BOTH

## 5. Distribution crossing

| Checkpoint | Statistic | KS | overlap | Wasserstein | max ECDF diff | quantile consistency | interleaved |
| --- | --- | --: | --: | --: | --: | --- | --- |
| F2 | `null_score` | 0.2286 | 0.6429 | 0.0872 | 0.2286 | 17 / 19 quantiles (UNANSWERABLE_LOWER) | True |
| F2 | `cls_start_logit` | 0.2381 | 0.6000 | 0.0901 | 0.2381 | 14 / 19 quantiles (UNANSWERABLE_LOWER) | True |
| F2 | `cls_end_logit` | 0.2357 | 0.6024 | 0.0444 | 0.2357 | 12 / 19 quantiles (UNANSWERABLE_LOWER) | True |
| F2 | `best_answer_score` | 0.4310 | 0.5119 | 0.6419 | 0.4310 | 19 / 19 quantiles (UNANSWERABLE_HIGHER) | False |
| F2 | `margin` | 0.3833 | 0.4571 | 0.5658 | 0.3833 | 19 / 19 quantiles (UNANSWERABLE_HIGHER) | False |
| F2 | `confidence` | 0.1500 | 0.6500 | 0.0034 | 0.1500 | 11 / 19 quantiles (UNANSWERABLE_HIGHER) | True |
| A0 | `null_score` | 0.2190 | 0.5690 | 1.6140 | 0.2190 | 11 / 19 quantiles (UNANSWERABLE_HIGHER) | True |
| A0 | `cls_start_logit` | 0.2214 | 0.5762 | 0.7814 | 0.2214 | 11 / 19 quantiles (UNANSWERABLE_HIGHER) | True |
| A0 | `cls_end_logit` | 0.2476 | 0.5381 | 0.8254 | 0.2476 | 10 / 19 quantiles (UNANSWERABLE_HIGHER) | True |
| A0 | `best_answer_score` | 0.1095 | 0.6714 | 0.7411 | 0.1095 | 10 / 19 quantiles (UNANSWERABLE_HIGHER) | True |
| A0 | `margin` | 0.2071 | 0.6548 | 1.7924 | 0.2071 | 13 / 19 quantiles (UNANSWERABLE_HIGHER) | True |
| A0 | `confidence` | 0.1357 | 0.6119 | 0.0308 | 0.1357 | 10 / 19 quantiles (UNANSWERABLE_LOWER) | True |

## 6. Rank-order forensics

| Statistic | ρ(F2,A0) all 182 | ρ within answerable | ρ within unanswerable | AUC F2 | AUC A0 | rank-direction agreement |
| --- | --: | --: | --: | --: | --: | --- |
| `null_score` | -0.3138 | -0.4111 | +0.2302 | 0.4303 | 0.5257 | False |
| `cls_start_logit` | -0.3674 | -0.4696 | +0.3372 | 0.4303 | 0.5189 | False |
| `cls_end_logit` | +0.0120 | +0.0166 | +0.1367 | 0.4391 | 0.5257 | False |
| `best_answer_score` | -0.1642 | -0.2662 | +0.0963 | 0.7250 | 0.5054 | True |
| `margin` | -0.1263 | -0.2175 | +0.1574 | 0.7338 | 0.5432 | True |
| `confidence` | -0.1358 | -0.1823 | +0.0837 | 0.5224 | 0.4991 | False |

## 7. Category-stratified reversal

**Flag: `INSUFFICIENT_CATEGORY_SUPPORT`** — 0 of 8 structural categories contain any unanswerable example; all 42 unanswerable examples carry category 'UNANSWERABLE' (42 examples), so class separation and AUC are undefined inside every structural category

| Category | n | answerable | unanswerable | both classes | AUC (null) | direction |
| --- | --: | --: | --: | --- | --- | --- |
| `DIRECT_SPAN` | 24 | 24 | 0 | False | — | UNDEFINED_NO_UNANSWERABLE_EXAMPLES |
| `NUMERIC` | 20 | 20 | 0 | False | — | UNDEFINED_NO_UNANSWERABLE_EXAMPLES |
| `MULTI_CHUNK` | 10 | 10 | 0 | False | — | UNDEFINED_NO_UNANSWERABLE_EXAMPLES |
| `LIST_ITEM` | 20 | 20 | 0 | False | — | UNDEFINED_NO_UNANSWERABLE_EXAMPLES |
| `TABLE_ROW` | 16 | 16 | 0 | False | — | UNDEFINED_NO_UNANSWERABLE_EXAMPLES |
| `LONG_CONTEXT` | 10 | 10 | 0 | False | — | UNDEFINED_NO_UNANSWERABLE_EXAMPLES |
| `TABLE_CELL` | 24 | 24 | 0 | False | — | UNDEFINED_NO_UNANSWERABLE_EXAMPLES |
| `SECTION_SPECIFIC` | 16 | 16 | 0 | False | — | UNDEFINED_NO_UNANSWERABLE_EXAMPLES |

Descriptive answerable-only family mean shift F2 → A0 (NOT class separation):

| Category | Δ null_score | Δ cls_start_logit | Δ cls_end_logit |
| --- | --: | --: | --: |
| `DIRECT_SPAN` | +1.0377 | +0.3534 | +0.6844 |
| `NUMERIC` | +0.8440 | +0.3621 | +0.4819 |
| `MULTI_CHUNK` | +2.3860 | +1.0059 | +1.3800 |
| `LIST_ITEM` | -1.0990 | -0.6771 | -0.4218 |
| `TABLE_ROW` | +4.3340 | +2.2092 | +2.1247 |
| `LONG_CONTEXT` | -3.1898 | -1.7729 | -1.4170 |
| `TABLE_CELL` | +2.2967 | +1.1090 | +1.1877 |
| `SECTION_SPECIFIC` | -7.0513 | -3.9281 | -3.1232 |

## 8. Answer-span score control

Previously measured F2 `margin`↔`best_answer_score` Spearman **-0.9206** → measured this phase **-0.9206** (reproduced: True); A0 = -0.6677

| Statistic | AUC F2 | AUC A0 | ΔAUC | F2 mean Δ | A0 mean Δ | F2 overlap | A0 overlap |
| --- | --: | --: | --: | --: | --: | --: | --: |
| `best_answer_score` | 0.7250 | 0.5054 | +0.2196 | +0.6412 | +0.1287 | 0.5119 | 0.6714 |
| `margin` | 0.7338 | 0.5432 | +0.1906 | +0.5625 | +0.6902 | 0.4571 | 0.6548 |
| `null_score` | 0.4303 | 0.5257 | -0.0954 | -0.0787 | +0.5615 | 0.6429 | 0.5690 |
| `cls_start_logit` | 0.4303 | 0.5189 | -0.0886 | -0.0531 | +0.2861 | 0.6000 | 0.5762 |
| `cls_end_logit` | 0.4391 | 0.5257 | -0.0866 | -0.0256 | +0.2754 | 0.6024 | 0.5381 |

- answer-span family vs null family AUC gap: **+0.2947 at F2**, +0.0175 at A0

## 9. Bootstrapped effect stability (seed 20260923, 10000 stratified resamples)

Scheme compatibility: matches the stored artifact = True. A0 confidence is the only apparent difference: this phase applies the DECLARED direction (higher = unanswerable) uniformly, giving CI [0.4005, 0.5961], whereas the existing artifact used the empirically chosen reversed direction for A0 confidence ([0.4039, 0.5995]); applying the 1-x sign flip to this phase's CI reproduces the stored CI exactly, which confirms the index scheme is identical rather than merely similar

| Checkpoint | Statistic | mean Δ | mean Δ 95% CI | AUC | AUC 95% CI | KS | KS 95% CI |
| --- | --- | --: | --- | --: | --- | --: | --- |
| F2 | `null_score` | -0.0787 | [-0.1536, -0.0036] | 0.4303 | [0.3378, 0.5257] | 0.2286 | [0.1714, 0.3214] |
| F2 | `cls_start_logit` | -0.0531 | [-0.1079, +0.0024] | 0.4303 | [0.3474, 0.5148] | 0.2381 | [0.1762, 0.3667] |
| F2 | `cls_end_logit` | -0.0256 | [-0.0699, +0.0166] | 0.4391 | [0.3517, 0.5262] | 0.2357 | [0.1500, 0.3810] |
| F2 | `best_answer_score` | +0.6412 | [+0.3748, +0.9042] | 0.7250 | [0.6270, 0.8167] | 0.4310 | [0.3048, 0.6000] |
| F2 | `margin` | +0.5625 | [+0.3336, +0.7885] | 0.7338 | [0.6398, 0.8202] | 0.3833 | [0.2762, 0.5595] |
| F2 | `confidence` | +0.0016 | [-0.0028, +0.0062] | 0.5224 | [0.4267, 0.6160] | 0.1500 | [0.1310, 0.3190] |
| A0 | `null_score` | +0.5615 | [-0.5939, +1.7391] | 0.5257 | [0.4400, 0.6088] | 0.2190 | [0.1905, 0.3452] |
| A0 | `cls_start_logit` | +0.2861 | [-0.3031, +0.8858] | 0.5189 | [0.4332, 0.6037] | 0.2214 | [0.1833, 0.3262] |
| A0 | `cls_end_logit` | +0.2754 | [-0.2950, +0.8561] | 0.5257 | [0.4403, 0.6087] | 0.2476 | [0.2024, 0.3667] |
| A0 | `best_answer_score` | +0.1287 | [-1.4147, +1.6516] | 0.5054 | [0.4078, 0.6043] | 0.1095 | [0.1024, 0.2976] |
| A0 | `margin` | +0.6902 | [-1.2723, +2.7626] | 0.5432 | [0.4508, 0.6388] | 0.2071 | [0.1405, 0.3548] |
| A0 | `confidence` | -0.0096 | [-0.0823, +0.0675] | 0.4991 | [0.4005, 0.5961] | 0.1357 | [0.1167, 0.3095] |

## 10. Hard decision tables

| Checkpoint | Statistic | AUC | CI | Mean Δ | Median Δ | KS | Overlap | Direction |
| --- | --- | --: | --- | --: | --: | --: | --: | --- |
| F2 | `null_score` | 0.4303 | [0.3378, 0.5257] | -0.0787 | -0.0547 | 0.2286 | 0.6429 | UNANSWERABLE_LOWER |
| F2 | `cls_start_logit` | 0.4303 | [0.3474, 0.5148] | -0.0531 | -0.0280 | 0.2381 | 0.6000 | UNANSWERABLE_LOWER |
| F2 | `cls_end_logit` | 0.4391 | [0.3517, 0.5262] | -0.0256 | -0.0493 | 0.2357 | 0.6024 | UNANSWERABLE_LOWER |
| F2 | `best_answer_score` | 0.7250 | [0.6270, 0.8167] | +0.6412 | +0.8613 | 0.4310 | 0.5119 | UNANSWERABLE_HIGHER |
| F2 | `margin` | 0.7338 | [0.6398, 0.8202] | +0.5625 | +0.6190 | 0.3833 | 0.4571 | UNANSWERABLE_HIGHER |
| F2 | `confidence` | 0.5224 | [0.4267, 0.6160] | +0.0016 | -0.0022 | 0.1500 | 0.6500 | UNANSWERABLE_HIGHER |
| A0 | `null_score` | 0.5257 | [0.4400, 0.6088] | +0.5615 | +0.3106 | 0.2190 | 0.5690 | UNANSWERABLE_HIGHER |
| A0 | `cls_start_logit` | 0.5189 | [0.4332, 0.6037] | +0.2861 | +0.3239 | 0.2214 | 0.5762 | UNANSWERABLE_HIGHER |
| A0 | `cls_end_logit` | 0.5257 | [0.4403, 0.6087] | +0.2754 | +0.2056 | 0.2476 | 0.5381 | UNANSWERABLE_HIGHER |
| A0 | `best_answer_score` | 0.5054 | [0.4078, 0.6043] | +0.1287 | -0.5045 | 0.1095 | 0.6714 | UNANSWERABLE_HIGHER |
| A0 | `margin` | 0.5432 | [0.4508, 0.6388] | +0.6902 | +1.9587 | 0.2071 | 0.6548 | UNANSWERABLE_HIGHER |
| A0 | `confidence` | 0.4991 | [0.4039, 0.5995] | -0.0096 | -0.0622 | 0.1357 | 0.6119 | UNANSWERABLE_LOWER |

| Statistic | F2 mechanism | A0 mechanism | Reversal type | Component driver |
| --- | --- | --- | --- | --- |
| `null_score` | MIXED | WEAK_SEPARATION | NEAR_CHANCE_BOTH | BOTH_COMPONENTS |
| `cls_start_logit` | MIXED | WEAK_SEPARATION | NEAR_CHANCE_BOTH | COMPONENT_OF_NULL_SCORE |
| `cls_end_logit` | WEAK_SEPARATION | WEAK_SEPARATION | NEAR_CHANCE_BOTH | COMPONENT_OF_NULL_SCORE |
| `best_answer_score` | MIXED | BROAD_OVERLAP | SAME_DIRECTION_DIFFERENT_STRENGTH | NOT_APPLICABLE_COMPONENT |
| `margin` | MIXED | WEAK_SEPARATION | SAME_DIRECTION_DIFFERENT_STRENGTH | NOT_APPLICABLE_COMPONENT |
| `confidence` | BROAD_OVERLAP | BROAD_OVERLAP | NEAR_CHANCE_BOTH | NOT_APPLICABLE_COMPONENT |

Mechanism reading caveat: the per-checkpoint mechanism label is defined on the KS statistic and on the standardized mean separation |mean delta| / pooled_sd; the standardized ratio is scale-sensitive, so a checkpoint with a much wider score spread can receive WEAK_SEPARATION while having a LARGER absolute mean separation. The scale-invariant ROC-AUC column is the primary separation measure and the mechanism column must be read alongside it, not instead of it.

Cross-checkpoint shift attribution:

| Statistic | shift answerable | shift unanswerable | separation change | attribution |
| --- | --: | --: | --: | --- |
| `null_score` | +0.1672 | +0.8074 | +0.6402 | UNANSWERABLE_SHIFT |
| `cls_start_logit` | -0.0455 | +0.2936 | +0.3392 | UNANSWERABLE_SHIFT |
| `cls_end_logit` | +0.2128 | +0.5138 | +0.3010 | UNANSWERABLE_SHIFT |
| `best_answer_score` | +4.0657 | +3.5532 | -0.5125 | MIXED |
| `margin` | +4.2329 | +4.3606 | +0.1277 | MIXED |
| `confidence` | +0.1948 | +0.1836 | -0.0112 | MIXED |

## 11. Research questions

- **A_why_null_score_reverses:** the recorded null_score is the exact sum of the two [CLS] components (max identity error 1.0e-06 at F2 and 1.0e-06 at A0); delta_null flips sign (-0.0787 -> +0.5615) because both delta_start (-0.0531 -> +0.2861) and delta_end (-0.0256 -> +0.2754) flip sign between checkpoints (classification: BOTH_COMPONENTS)
- **B_which_component_drives:** both components flip: delta_start -0.0531 -> +0.2861 and delta_end -0.0256 -> +0.2754; neither component alone explains the sign change
- **C_is_signal_in_answer_span:** yes at F2: answer-span family AUC 0.7338 vs null family 0.4391 (gap +0.2947), and the recorded F2 margin~best_answer_score Spearman of -0.9206 shows margin carries almost the same ordering as the answer-span score; at A0 the same gap is +0.0175
- **D_what_the_checkpoint_difference_is:** ranking/order, not scale: ROC-AUC is invariant to any monotone rescaling, so the AUC differences cannot be produced by additive or multiplicative score scaling; the measured Spearman similarities and the paired delta-AUC CIs localise the difference to the ordering of examples

## 12. Verdict

**`REVERSAL_PARTIALLY_EXPLAINED`**

- literal sign flip present for the null family: True
- statistically established sign flip (at least one CI excludes 0.50 in its own direction): False
- paired delta-AUC CI excludes 0 for any null-family statistic: False
- component classification: BOTH_COMPONENTS
- the sign change itself is arithmetically fully accounted for (delta_null = delta_start + delta_end holds to 1e-6 and both components flip sign), but the AUC magnitudes remain chance-compatible in both checkpoints, so the reversal is not established as a reliable property

- Literal alternative: under a purely component-arithmetic reading the sign change is fully accounted for, which would satisfy REVERSAL_EXPLAINED; the applied verdict is the lower tier because the reversal is not statistically established

## Interpretation boundary

- No model loading, no inference, no GPU, no training, no database, no retrieval was used.
- No threshold was fitted, no K searched, no classifier fitted, no combined score created.
- Only recorded score fields were read; the frozen prediction artifact was not modified.
- AUC is monotone-scale invariant, so no threshold-free AUC difference is attributed to score scaling.
- These are score-distribution measurements of the CURRENT recorded outputs; they are not causal claims and not architecture evidence.
- The category-stratified question is not answerable from this benchmark: every structural category contains answerable examples only.

## Integrity

| Artifact | Recorded | Expected | Match |
| --- | --- | --- | --- |
| benchmark | `1166bf4ff38265c2…` | `1166bf4ff38265c2…` | MATCH |
| dataset | `a517530354fc9bca…` | `a517530354fc9bca…` | MATCH |
| production model | `cb9f1dde94fca0e1…` | `cb9f1dde94fca0e1…` | MATCH |
| F2 model | `717463178eeb37ee…` | `717463178eeb37ee…` | MATCH |
| F2 checkpoint (dir scope) | `416b63642ba80a1c…` | `416b63642ba80a1c…` | MATCH |
| source corpus fingerprint | `3ec81cc5868f29a0…` | `3ec81cc5868f29a0…` | MATCH |
| chunk corpus fingerprint | `e6965cdad6684c65…` | `e6965cdad6684c65…` | MATCH |
