# Abstention Gate Re-scoring — recorded G rule on existing fresh predictions

> **PROVENANCE (2026-09-28) - PRE-RECONSTRUCTION-FIX answer text.** All EM/F1
> values below are pre-fix; the abstention rule, its threshold and every score statistic are NOT affected.
> The input predictions' answer TEXT came from `tokenizer.decode()`, which re-inserts spaces at subword
> boundaries and corrupted split values (`142.6 million` -> `142. 6 million`). Logit/score-derived signals are
> unaffected: span and score are bit-identical before vs after. On the same 182 examples, same checkpoints,
> same spans, only the decoder changed: F2 answerable EM 2.86% -> 14.29%, F1 16.92% -> 28.91%.
> Leaked population; not a generalization result. Full record: `E0_PREDICTION_PROVENANCE_2026-09-28.md`.

- Rule applied verbatim: **abstain iff `null_score >= 1.5705`** (recorded by Phase 4F.5-G (selected_mode=null_score, selected_value=1.5705)); not fitted, not tuned, not searched here.
- Single changed variable: **abstention policy (null_score rule) OFF vs ON**.
- Held fixed: benchmark (182 frozen P3 examples), predictions (fresh, unchanged), checkpoints (F2 checkpoint_epoch2; production documind-qa), tokenizer, decode protocol (max_length=384, max_answer_length=50), logits and answer spans (re-read, never recomputed).
- Input predictions: `backend/architecture/phase4f_6/e0_diagnostics/diagnostics/model_40min_predictions.json` sha256 `d7d9d65e944488ac...` (benchmark hash verified: `1166bf4ff38265c2...`)
- No model was loaded, no inference was run, no logits or spans were recomputed.

## Gate OFF vs gate ON

| Model | Gate | EM | F1 | Answerable F1 | Unanswerable abstention | False abstention | Spurious | Coverage |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| F2 | OFF | 2.86 | 19.69 | 19.69 | 0/42 = 0.0% | 0/140 = 0.0% | 42 = 23.1% | 100.0% |
| F2 | ON | 2.86 | 16.92 | 16.92 | 8/42 = 19.0% | 39/140 = 27.9% | 34 = 18.7% | 74.2% |
| A0 | OFF | 5.0 | 24.44 | 24.44 | 0/42 = 0.0% | 0/140 = 0.0% | 42 = 23.1% | 100.0% |
| A0 | ON | 2.86 | 12.16 | 12.16 | 22/42 = 52.4% | 73/140 = 52.1% | 20 = 11.0% | 47.8% |

### Deltas (ON − OFF)

| Model | ΔEM | ΔF1 | Δunanswerable abstention | Δfalse abstention | Δspurious | Δcoverage |
|---|---:|---:|---:|---:|---:|---:|
| F2 | 0.0 | -2.77 | 19.0 | 27.9 | -8 | -25.8 |
| A0 | -2.14 | -12.28 | 52.4 | 52.1 | -22 | -52.2 |

## Abstention-rule confusion matrix

**F2 — gate_off**: unanswerable(42) abstained=0 spurious=42; answerable(140) abstained=0 correct=4 incorrect=136
**F2 — gate_on**: unanswerable(42) abstained=8 spurious=34; answerable(140) abstained=39 correct=4 incorrect=97

**A0 — gate_off**: unanswerable(42) abstained=0 spurious=42; answerable(140) abstained=0 correct=7 incorrect=133
**A0 — gate_on**: unanswerable(42) abstained=22 spurious=20; answerable(140) abstained=73 correct=4 incorrect=63

## Threshold behaviour per checkpoint

| Model | examples with null_score >= 1.5705 (answerable) | (unanswerable) | null_score range |
|---|---|---|---|
| F2 | 39/140 | 8/42 | [0.864908, 2.063324] |
| A0 | 73/140 | 22/42 | [-8.858237, 10.771528] |

## Category impact

### F2

| category | n | gate_off EM | gate_on EM | gate_off F1 | gate_on F1 | abstained |
|---|---|---|---|---|---|---|
| DIRECT_SPAN | 24 | 12.5 | 12.5 | 47.4 | 46.3 | 1 |
| NUMERIC | 20 | 5.0 | 5.0 | 39.8 | 39.8 | 0 |
| TABLE_CELL | 24 | 0.0 | 0.0 | 1.2 | 1.2 | 2 |
| TABLE_ROW | 16 | 0.0 | 0.0 | 11.1 | 11.1 | 0 |
| LIST_ITEM | 20 | 0.0 | 0.0 | 14.1 | 10.8 | 6 |
| SECTION_SPECIFIC | 16 | 0.0 | 0.0 | 1.2 | 0.0 | 13 |
| MULTI_CHUNK | 10 | 0.0 | 0.0 | 21.7 | 4.0 | 7 |
| LONG_CONTEXT | 10 | 0.0 | 0.0 | 10.0 | 0.0 | 10 |

### A0

| category | n | gate_off EM | gate_on EM | gate_off F1 | gate_on F1 | abstained |
|---|---|---|---|---|---|---|
| DIRECT_SPAN | 24 | 8.3 | 8.3 | 36.8 | 23.5 | 12 |
| NUMERIC | 20 | 15.0 | 10.0 | 42.7 | 23.7 | 10 |
| TABLE_CELL | 24 | 8.3 | 0.0 | 12.0 | 0.0 | 18 |
| TABLE_ROW | 16 | 0.0 | 0.0 | 34.3 | 0.0 | 16 |
| LIST_ITEM | 20 | 0.0 | 0.0 | 14.0 | 10.1 | 7 |
| SECTION_SPECIFIC | 16 | 0.0 | 0.0 | 21.9 | 21.9 | 0 |
| MULTI_CHUNK | 10 | 0.0 | 0.0 | 10.5 | 0.0 | 9 |
| LONG_CONTEXT | 10 | 0.0 | 0.0 | 11.2 | 11.2 | 1 |

## Cross-check against the recorded G run

- recorded benchmark metrics: `{"em": 2.86, "f1": 16.92, "answerable_total": 140, "answerable_correct": 4, "answerable_coverage": 72.14, "false_abstention": 39, "false_abstention_rate": 27.86, "unanswerable_total": 42, "unanswerable_correct": 8, "abstention_rate": 19.05, "spurious": 34, "spurious_rate": 80.95}`
- re-scored fresh F2 with gate ON: `{"em": 2.86, "f1": 16.92, "answerable_coverage": 74.2, "false_abstention": 39, "false_abstention_rate": 27.9, "abstention_rate_unanswerable_pct": 19.0, "spurious": 34}`
- note: the recorded G manifest applied the same rule to the same F2 checkpoint; the exact agreement on EM, F1, false abstention, abstention and spurious validates the re-scoring implementation.

## Key measured effects

- **1_answerable_removed_by_gate**: `{"F2": "39/140", "A0": "73/140"}`
- **2_unanswerable_correctly_removed**: `{"F2": "8/42", "A0": "22/42"}`
- **3_F1_change**: `{"F2": -2.77, "A0": -12.28, "EM_change": {"F2": 0.0, "A0": -2.14}}`
- **4_threshold_same_value_different_behaviour**: `{"F2_fired_on": "39/140 answerable + 8/42 unanswerable", "A0_fired_on": "73/140 answerable + 22/42 unanswerable", "answerable_fire_ratio_A0_over_F2": 1.87, "unanswerable_fire_ratio_A0_over_F2": 2.75}`
- **5_what_the_threshold_changes**: `{"improves": "abstention behaviour only: spurious drops 42->34 (F2) and 42->20 (A0); correct abstentions rise 0->8 (F2) and 0->22 (A0)", "does_not_improve": "extraction: answerable F1 falls for both (-2.77 F2, -12.28 A0); answerable EM is unchanged for F2 (2.86) but falls for A0 (5.0 -> 2.86), i.e. 3 of A0's 7 EM-correct answers are falsely abstained", "conclusion_scope": "operating-point trade-off measured on this population only; the threshold is not claimed to be optimal"}`

## Comparability

- **F2**: MATCHED - same checkpoint, same predictions, same rule as the recorded G run
- **A0**: DESCRIPTIVE_ONLY for the historical A0 production operating point - the production gate is not the G rule and its threshold/spans are unrecorded; this run is labelled 'A0 + G-recorded-threshold'
- **gate_off_vs_gate_on**: MATCHED - identical predictions and identical denominators; abstention policy is the only changed variable

## Interpretation boundary

- This is an operating-point experiment, not a model comparison study.
- The threshold 1.5705 is used verbatim as recorded; it is not claimed to be optimal.
- No claim is made that the DocuMind architecture is proven or disproven.
- No claim is made that a separate answerability module is proven necessary.
- No claim is made that F2 or A0 is universally superior.
- All metrics carry explicit denominators; answerable and unanswerable analyses are not mixed.
