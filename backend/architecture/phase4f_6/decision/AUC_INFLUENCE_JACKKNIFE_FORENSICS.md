# Answerability AUC Influence + Jackknife Forensics

**Date:** 2026-09-23T21:09:07.083560+05:30 · **Population:** 182 = 140 answerable + 42 unanswerable · **pairs per statistic:** 5,880

**Primary question:** why is A0 margin AUC 0.5432 close to chance while F2 margin AUC is 0.7338, and is the difference a distributed property of the 182-example ordering or driven by a few influential examples?

Direction convention: HIGHER oriented score = MORE LIKELY UNANSWERABLE (margin +1, best_answer_score -1)

Bounded mathematical re-analysis of the frozen prediction artifact. No model loading, no inference, no training, no GPU, no database, no retrieval, no threshold fitting, no K search, no subset optimization, no new or combined score.

## 1. Input integrity

- F2 rows 182 / A0 rows 182; ids+order match: True; labels match: True; 140/42
- prediction artifact sha256 `d7d9d65e944488ac26a0e197df589fbb4955aafe635fac82f52d2c6e4a649fa9`
- pairs per statistic = 5880

## 2. Pairwise decomposition (5,880 pairs each)

| Model | Statistic | positive wins | ties | negative wins | sum check | AUC from pairs | previously reported | match |
| --- | --- | --: | --: | --: | --: | --: | --: | --- |
| F2 | `margin` | 4315 | 0 | 1565 | 5880 | 0.733844 | 0.7338 | True |
| A0 | `margin` | 3194 | 0 | 2686 | 5880 | 0.543197 | 0.5432 | True |
| F2 | `best_answer_score` | 4263 | 0 | 1617 | 5880 | 0.725000 | 0.725 | True |
| A0 | `best_answer_score` | 2972 | 0 | 2908 | 5880 | 0.505442 | 0.5054 | True |

## 3. Per-unanswerable influence (42 examples)

| Model | Statistic | mean | median | std | min | max | q05 | q95 |
| --- | --- | --: | --: | --: | --: | --: | --: | --: |
| F2 | `margin` | +0.233844 | +0.267857 | 0.280004 | -0.500000 | +0.500000 | -0.344286 | +0.499643 |
| A0 | `margin` | +0.043197 | +0.110714 | 0.244791 | -0.500000 | +0.500000 | -0.420357 | +0.411071 |
| F2 | `best_answer_score` | +0.225000 | +0.328571 | 0.293565 | -0.492857 | +0.500000 | -0.350000 | +0.492500 |
| A0 | `best_answer_score` | +0.005442 | -0.039286 | 0.272923 | -0.500000 | +0.500000 | -0.428571 | +0.421429 |

## 4. Per-answerable influence (140 examples)

| Model | Statistic | mean | median | std | min | max | q05 | q95 |
| --- | --- | --: | --: | --: | --: | --: | --: | --: |
| F2 | `margin` | +0.233844 | +0.309524 | 0.218260 | -0.428571 | +0.476190 | -0.166667 | +0.476190 |
| A0 | `margin` | +0.043197 | +0.095238 | 0.338308 | -0.476190 | +0.476190 | -0.453571 | +0.452381 |
| F2 | `best_answer_score` | +0.225000 | +0.333333 | 0.225467 | -0.452381 | +0.500000 | -0.285714 | +0.476190 |
| A0 | `best_answer_score` | +0.005442 | -0.071429 | 0.311230 | -0.476190 | +0.476190 | -0.452381 | +0.452381 |

## 5. Influence concentration (share of absolute influence)

| Model | Statistic | Class | Top-1 | Top-3 | Top-5 | Top-10 | Top-20 | Top-25% | Top-50% |
| --- | --- | --- | --: | --: | --: | --: | --: | --: | --: |
| F2 | `margin` | UNANSWERABLE | 0.0365 | 0.1094 | 0.1819 | 0.3616 | 0.6826 | 0.3976 | 0.7087 |
| F2 | `margin` | ANSWERABLE | 0.0119 | 0.0356 | 0.0593 | 0.1175 | 0.2303 | 0.3911 | 0.7139 |
| A0 | `margin` | UNANSWERABLE | 0.0571 | 0.1664 | 0.2659 | 0.4698 | 0.7137 | 0.5024 | 0.7349 |
| A0 | `margin` | ANSWERABLE | 0.0111 | 0.0333 | 0.0555 | 0.1110 | 0.2181 | 0.3696 | 0.6859 |
| F2 | `best_answer_score` | UNANSWERABLE | 0.0344 | 0.1028 | 0.1702 | 0.3310 | 0.6134 | 0.3610 | 0.6385 |
| F2 | `best_answer_score` | ANSWERABLE | 0.0121 | 0.0353 | 0.0584 | 0.1157 | 0.2256 | 0.3684 | 0.6530 |
| A0 | `best_answer_score` | UNANSWERABLE | 0.0535 | 0.1583 | 0.2538 | 0.4664 | 0.7752 | 0.5023 | 0.8012 |
| A0 | `best_answer_score` | ANSWERABLE | 0.0121 | 0.0362 | 0.0603 | 0.1194 | 0.2340 | 0.3890 | 0.6960 |

Top-25% / Top-50% column widths: F2 UNANSWERABLE specs [1, 3, 5, 10, 20, 11, 21]; F2 ANSWERABLE specs [1, 3, 5, 10, 20, 35, 70].

## 6/7. Jackknife (182 leave-one-out runs per target)

| Model | Statistic | Original AUC | JK min | JK max | JK mean | JK std | AUC>0.5 % | AUC<0.5 % | Near-0.5(±0.02) % | Stability | Trigger |
| --- | --- | --: | --: | --: | --: | --: | --: | --: | --: | --- | --- |
| F2 | `margin` | 0.7338 | 0.7274 | 0.7517 | 0.7338 | 0.003530 | 100.00 | 0.00 | 0.00 | BROAD_DISTRIBUTED_SIGNAL | no flips, delta_max < 0.05, |AUC - 0.5| > 0.05 |
| A0 | `margin` | 0.5432 | 0.5321 | 0.5564 | 0.5432 | 0.003553 | 100.00 | 0.00 | 0.00 | NEAR_CHANCE_STABLE | no flips, delta_max < 0.05, |AUC - 0.5| <= 0.05, jackknife distance <= 0.10 |
| F2 | `best_answer_score` | 0.7250 | 0.7183 | 0.7425 | 0.7250 | 0.003692 | 100.00 | 0.00 | 0.00 | BROAD_DISTRIBUTED_SIGNAL | no flips, delta_max < 0.05, |AUC - 0.5| > 0.05 |
| A0 | `best_answer_score` | 0.5054 | 0.4934 | 0.5178 | 0.5054 | 0.003727 | 93.41 | 6.59 | 100.00 | FEW_EXAMPLES_DRIVE_SIGNAL | side_flip: 12 leave-one-out run(s) crossed 0.5 |

Pre-declared stability rule:

- `evaluation_order`: ['FEW_EXAMPLES_DRIVE_SIGNAL', 'BROAD_DISTRIBUTED_SIGNAL', 'NEAR_CHANCE_STABLE', 'INCONCLUSIVE']
- `FEW_EXAMPLES_DRIVE_SIGNAL`: any leave-one-out AUC crosses 0.5 (side flip) OR delta_max >= 0.05
- `BROAD_DISTRIBUTED_SIGNAL`: no side flip AND delta_max < 0.05 AND side_rate > 0.5 AND |AUC_original - 0.5| > 0.05
- `NEAR_CHANCE_STABLE`: no side flip AND delta_max < 0.05 AND |AUC_original - 0.5| <= 0.05 AND jackknife_distance_from_chance <= 0.10

- **F2|margin**: delta_max 0.017899, side flips 0, JK distance from chance 0.251742 → `BROAD_DISTRIBUTED_SIGNAL`
  - removal increases AUC most: `unans_29bba51a` (UNANSWERABLE) → 0.7517 (+0.017899)
  - removal decreases AUC most: `unans_ecebc88c` (UNANSWERABLE) → 0.7274 (-0.006492)
  - analytic jackknife equals brute-force recomputation: True
- **A0|margin**: delta_max 0.013249, side flips 0, JK distance from chance 0.056446 → `NEAR_CHANCE_STABLE`
  - removal increases AUC most: `unans_ee310eea` (UNANSWERABLE) → 0.5564 (+0.013249)
  - removal decreases AUC most: `unans_520918ca` (UNANSWERABLE) → 0.5321 (-0.011142)
  - analytic jackknife equals brute-force recomputation: True
- **F2|best_answer_score**: delta_max 0.017509, side flips 0, JK distance from chance 0.242509 → `BROAD_DISTRIBUTED_SIGNAL`
  - removal increases AUC most: `unans_29bba51a` (UNANSWERABLE) → 0.7425 (+0.017509)
  - removal decreases AUC most: `unans_ecebc88c` (UNANSWERABLE) → 0.7183 (-0.006707)
  - analytic jackknife equals brute-force recomputation: True
- **A0|best_answer_score**: delta_max 0.012328, side flips 12, JK distance from chance 0.017770 → `FEW_EXAMPLES_DRIVE_SIGNAL`
  - removal increases AUC most: `unans_ee310eea` (UNANSWERABLE) → 0.5178 (+0.012328)
  - removal decreases AUC most: `unans_520918ca` (UNANSWERABLE) → 0.4934 (-0.012062)
  - analytic jackknife equals brute-force recomputation: True

## 8. Signed influence curve (examples ordered by |contribution| descending)

| Model | Statistic | Class | total signed influence | 25% at | 50% at | 75% at | 90% at |
| --- | --- | --- | --: | --: | --: | --: | --: |
| F2 | `margin` | UNANSWERABLE | +9.821429 | 7 ex | 12 ex | 20 ex | 27 ex |
| F2 | `margin` | ANSWERABLE | +32.738095 | 18 ex | 39 ex | 61 ex | 76 ex |
| A0 | `margin` | UNANSWERABLE | +1.814286 | 1 ex | 17 ex | 20 ex | 21 ex |
| A0 | `margin` | ANSWERABLE | +6.047619 | 4 ex | 35 ex | 43 ex | 117 ex |
| F2 | `best_answer_score` | UNANSWERABLE | +9.450000 | 7 ex | 15 ex | 21 ex | 33 ex |
| F2 | `best_answer_score` | ANSWERABLE | +31.500000 | 19 ex | 51 ex | 75 ex | 97 ex |
| A0 | `best_answer_score` | UNANSWERABLE | +0.228571 | 1 ex | 1 ex | 1 ex | 1 ex *(denominator near zero — marks uninformative)* |
| A0 | `best_answer_score` | ANSWERABLE | +0.761905 | 1 ex | 1 ex | 2 ex | 2 ex *(denominator near zero — marks uninformative)* |

Marks meaningfulness rule: the 25/50/75/90% marks are only reported as informative when the mean signed influence per example is >= 0.01; below that the total signed influence is effectively indistinguishable from zero and the marks are driven by a near-zero denominator

## 9. Category influence (answerable side, 140 examples)

### F2|margin — `BROAD_ACROSS_CATEGORIES` (max category share 0.2285, top-3 share 0.5638)

| Category | n | mean contribution | median contribution | total contribution | absolute contribution | share of absolute influence |
| --- | --: | --: | --: | --: | --: | --: |
| `DIRECT_SPAN` | 24 | +0.329365 | +0.333333 | +7.904762 | 7.904762 | 0.1970 |
| `NUMERIC` | 20 | +0.142857 | +0.238095 | +2.857143 | 5.285714 | 0.1318 |
| `MULTI_CHUNK` | 10 | +0.321429 | +0.333333 | +3.214286 | 3.214286 | 0.0801 |
| `LIST_ITEM` | 20 | +0.092857 | -0.023810 | +1.857143 | 4.285714 | 0.1068 |
| `TABLE_ROW` | 16 | +0.293155 | +0.428571 | +4.690476 | 5.547619 | 0.1383 |
| `LONG_CONTEXT` | 10 | +0.083333 | +0.059524 | +0.833333 | 1.071429 | 0.0267 |
| `TABLE_CELL` | 24 | +0.372024 | +0.404762 | +8.928571 | 9.166667 | 0.2285 |
| `SECTION_SPECIFIC` | 16 | +0.153274 | +0.214286 | +2.452381 | 3.642857 | 0.0908 |

### A0|margin — `BROAD_ACROSS_CATEGORIES` (max category share 0.1637, top-3 share 0.4717)

| Category | n | mean contribution | median contribution | total contribution | absolute contribution | share of absolute influence |
| --- | --: | --: | --: | --: | --: | --: |
| `DIRECT_SPAN` | 24 | +0.024802 | +0.071429 | +0.595238 | 6.595238 | 0.1537 |
| `NUMERIC` | 20 | +0.241667 | +0.357143 | +4.833333 | 5.690476 | 0.1326 |
| `MULTI_CHUNK` | 10 | -0.197619 | -0.345238 | -1.976190 | 2.833333 | 0.0660 |
| `LIST_ITEM` | 20 | +0.059524 | +0.166667 | +1.190476 | 6.476190 | 0.1509 |
| `TABLE_ROW` | 16 | -0.360119 | -0.428571 | -5.761905 | 5.952381 | 0.1387 |
| `LONG_CONTEXT` | 10 | +0.171429 | +0.130952 | +1.714286 | 1.714286 | 0.0400 |
| `TABLE_CELL` | 24 | -0.048611 | +0.000000 | -1.166667 | 7.023810 | 0.1637 |
| `SECTION_SPECIFIC` | 16 | +0.413690 | +0.404762 | +6.619048 | 6.619048 | 0.1543 |

### F2|best_answer_score — `BROAD_ACROSS_CATEGORIES` (max category share 0.2105, top-3 share 0.5130)

| Category | n | mean contribution | median contribution | total contribution | absolute contribution | share of absolute influence |
| --- | --: | --: | --: | --: | --: | --: |
| `DIRECT_SPAN` | 24 | +0.282738 | +0.333333 | +6.785714 | 6.785714 | 0.1648 |
| `NUMERIC` | 20 | +0.042857 | +0.166667 | +0.857143 | 5.047619 | 0.1226 |
| `MULTI_CHUNK` | 10 | +0.366667 | +0.357143 | +3.666667 | 3.666667 | 0.0891 |
| `LIST_ITEM` | 20 | +0.100000 | +0.000000 | +2.000000 | 4.476190 | 0.1087 |
| `TABLE_ROW` | 16 | +0.220238 | +0.333333 | +3.523810 | 5.666667 | 0.1377 |
| `LONG_CONTEXT` | 10 | +0.276190 | +0.285714 | +2.761905 | 2.761905 | 0.0671 |
| `TABLE_CELL` | 24 | +0.331349 | +0.333333 | +7.952381 | 8.666667 | 0.2105 |
| `SECTION_SPECIFIC` | 16 | +0.247024 | +0.333333 | +3.952381 | 4.095238 | 0.0995 |

### A0|best_answer_score — `BROAD_ACROSS_CATEGORIES` (max category share 0.1858, top-3 share 0.5410)

| Category | n | mean contribution | median contribution | total contribution | absolute contribution | share of absolute influence |
| --- | --: | --: | --: | --: | --: | --: |
| `DIRECT_SPAN` | 24 | +0.085317 | +0.238095 | +2.047619 | 7.333333 | 0.1858 |
| `NUMERIC` | 20 | +0.266667 | +0.309524 | +5.333333 | 7.047619 | 0.1785 |
| `MULTI_CHUNK` | 10 | -0.142857 | -0.309524 | -1.428571 | 3.142857 | 0.0796 |
| `LIST_ITEM` | 20 | -0.082143 | -0.166667 | -1.642857 | 4.309524 | 0.1092 |
| `TABLE_ROW` | 16 | -0.305060 | -0.404762 | -4.880952 | 5.642857 | 0.1429 |
| `LONG_CONTEXT` | 10 | -0.109524 | -0.119048 | -1.095238 | 1.904762 | 0.0483 |
| `TABLE_CELL` | 24 | +0.052579 | +0.166667 | +1.261905 | 6.976190 | 0.1767 |
| `SECTION_SPECIFIC` | 16 | +0.072917 | +0.142857 | +1.166667 | 3.119048 | 0.0790 |

## 10. Cross-checkpoint influence agreement

| Statistic | influence Spearman | influence Pearson | top-10 overlap | top-20 overlap | Jaccard-10 | Jaccard-20 | pattern |
| --- | --: | --: | --: | --: | --: | --: | --- |
| `margin` | -0.1370 | -0.1394 | 1/10 | 3/20 | 0.0526 | 0.0811 | DIFFERENT_DRIVERS |
| `best_answer_score` | -0.1428 | -0.1108 | 2/10 | 3/20 | 0.1111 | 0.0811 | DIFFERENT_DRIVERS |

## 11. A0 − F2 influence difference

| Statistic | mean | median | std | q05 | q95 | top-10 share | top-20 share | class ratio | classification |
| --- | --: | --: | --: | --: | --: | --: | --: | --: | --- |
| `margin` | -0.190646 | -0.142857 | 0.420133 | -0.880119 | +0.498810 | 0.139 | 0.2661 | 1.1568 | DISTRIBUTED_DIFFERENCE |
| `best_answer_score` | -0.219558 | -0.190476 | 0.407455 | -0.833333 | +0.498810 | 0.1307 | 0.2493 | 1.0994 | DISTRIBUTED_DIFFERENCE |

## 12. Reconciliation with prior findings

- F2 margin AUC 0.7338 → measured 0.7338; F2 best_answer_score AUC 0.7250 → measured 0.725
- A0 margin AUC 0.5432 → measured 0.5432; A0 best_answer_score AUC 0.5054 → measured 0.5054
- F2 margin↔best_answer_score Spearman −0.9206 → reproduced +0.9141
- null-family paired-bootstrap (previous phase): that earlier result concerns the NULL family; this phase analyses the answer-span family (margin, best_answer_score), whose AUC difference is much larger, and asks whether the remaining difference survives single-example influence analysis
- remaining answer-span difference: margin +0.1906, best_answer_score +0.2196; leave-one-out ranges disjoint: margin True, best_answer_score True

## 14. Answers

- **A_is_A0_margin_broad_or_artifact:** A0 margin AUC 0.5432 is stable and near chance rather than an artifact of a few examples: its jackknife range is [0.5321, 0.5564] with 100.00% of leave-one-out runs above 0.5 and no side flip (classification NEAR_CHANCE_STABLE); the largest single-example removal moves AUC by only 0.0132
- **B_is_F2_margin_distributed:** yes: F2 margin AUC 0.7338 has jackknife range [0.7274, 0.7517] (width 0.0244), 100.00% of leave-one-out runs stay above 0.5 (side flips: 0), the largest single removal changes AUC by 0.0179, and the top 50% of answerable examples carry only 0.7139 of the answerable-side absolute influence
- **C_same_examples_driving_both:** no — cross-checkpoint influence agreement is weak: margin influence Spearman -0.1370 with top-10 overlap 1/10 (Jaccard 0.0526) and top-20 overlap 3/20 (Jaccard 0.0811); best_answer_score influence Spearman -0.1428
- **D_where_the_difference_lives:** margin: DISTRIBUTED_DIFFERENCE (top-10 share 0.139, top-20 share 0.2661, class ratio 1.1568); best_answer_score: DISTRIBUTED_DIFFERENCE (top-10 share 0.1307, top-20 share 0.2493, class ratio 1.0994)
- **E_answer_span_still_stronger:** yes: after influence decomposition the answer-span family remains far stronger than the null family at F2 (margin 0.7338 and best_answer_score 0.7250, both BROAD-distributed across leave-one-out removals), while at A0 both are near chance (margin 0.5432, best_answer_score 0.5054)

## 15. Verdict

**`INFLUENCE_MIXED`**

- F2|margin: `BROAD_DISTRIBUTED_SIGNAL`
- A0|margin: `NEAR_CHANCE_STABLE`
- F2|best_answer_score: `BROAD_DISTRIBUTED_SIGNAL`
- A0|best_answer_score: `FEW_EXAMPLES_DRIVE_SIGNAL`

Mechanistic note: the only target classified A0|best_answer_score has |AUC - 0.5| = 0.0054 (statistically indistinguishable from chance); its 12 side-flipping leave-one-out runs all come from unanswerable removals (12 of 42; answerable removals: 0 of 140), the deepest any single removal pushes the AUC below 0.5 is 0.006620 (jackknife min 0.4934), and the largest single change in AUC is delta_max 0.012328. This is chance-boundary instability of a statistic that sits on 0.5, not evidence that a small subset creates a separation.

Alternative reading: if CONCENTRATED is required to mean that a material separation is produced by a small subset, then no target qualifies: the F2 targets carry |AUC - 0.5| > 0.22 broadly across examples (top-1 example = 1.1-3.7% of absolute influence), and the A0 target that triggered FEW_EXAMPLES sits on 0.5 (|AUC - 0.5| = 0.0054, deepest single-removal excursion below 0.5 only 0.0066). Under that reading every target falls in BROAD_DISTRIBUTED_SIGNAL or NEAR_CHANCE_STABLE, i.e. INFLUENCE_DISTRIBUTED. The applied verdict follows the pre-declared rule mechanically; this alternative is reported so the label is not read as evidence of a concentrated signal that does not exist.

Verdict rules (the applied one is marked):

- `INFLUENCE_DISTRIBUTED`: AUC interpretation remains materially similar after single-example removal and influence is spread broadly
- `INFLUENCE_CONCENTRATED`: a small number of examples materially determine the observed separation
- **`INFLUENCE_MIXED`**: one checkpoint/statistic is broad while another is concentrated
- `INFLUENCE_INCONCLUSIVE`: the influence decomposition cannot distinguish the mechanisms

## Interpretation boundary

- No model loading, no inference, no training, no GPU, no database, no retrieval was used.
- No threshold was fitted, no K searched, no subset optimization, no leave-two-out or combinatorial search, no new or combined score was created.
- Only recorded score fields and labels were re-analysed mathematically; the frozen prediction artifact was not modified.
- Influence and jackknife figures are descriptive decompositions of a rank statistic, not causal effects and not architectural evidence.
- No winner/best/superior language is used; each checkpoint/statistic is reported on its own measurements.

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
| prediction artifact | `d7d9d65e944488ac…` | (this phase's own recording) | — |
