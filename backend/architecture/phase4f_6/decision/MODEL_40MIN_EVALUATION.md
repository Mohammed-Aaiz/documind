# Model 40-Minute Evaluation (model-only, frozen P3 benchmark)

> **PROVENANCE (2026-09-28) - PRE-RECONSTRUCTION-FIX answer text.** All EM/F1
> values below are pre-fix. The input predictions' answer TEXT came from `tokenizer.decode()`,
> which re-inserts spaces at subword boundaries and corrupted split values (`142.6 million` -> `142. 6 million`).
> Logit/score-derived signals are unaffected: span and score are bit-identical before vs after.
> On the same 182 examples, same checkpoints, same spans, only the decoder changed:
> F2 answerable EM 2.86% -> 14.29%, F1 16.92% -> 28.91%. Leaked population; not a generalization
> result. Full record: `E0_PREDICTION_PROVENANCE_2026-09-28.md`.

- Date: 2026-09-23T20:35:34.178530+05:30
- Benchmark: `backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` sha256 `1166bf4ff38265c2...` (182 examples: 140 answerable / 42 unanswerable) — hash verified
- No retrieval, no database, no training, no weight/benchmark modification. Offline mode forced.

## Protocol (pinned from the recorded F2 run)

- **source**: pinned from backend/phase4f/phase4f_5f/f2/run_f2.py + threshold_experiment/run_threshold_experiment.py
- **max_length**: 384
- **truncation**: True
- **padding**: max_length
- **max_answer_length**: 50
- **decode**: start=argmax(start_logits with CLS masked to -inf); end=start+argmax(end_logits[start:start+50])
- **null_score**: cls_start_logit + cls_end_logit
- **margin**: null_score - (best_start_logit + best_end_logit)
- **confidence**: (softmax(start)[best_start] + softmax(end)[best_end]) / 2
- **metrics**: EM = normalized string equality; F1 = token-SET F1; normalization = ' '.join(strip().lower().split())
- **thresholds_changed**: False
- **device**: cpu
- **batch**: 16

## Primary — F2 designated checkpoint (`checkpoint_epoch2`)

- checkpoint dir-scope sha256: `416b63642ba80a1c4f11257df9d21f9e36427393533465d0ad3b2a15a0b5fc39`
- model.safetensors sha256: `717463178eeb37ee3a6424063e8666b6586dd15ee50d745c1ab3d16bb4b164b0`
- inference time: 25.56 s on cpu

### Overall metrics

| metric | value | denominator |
|---|---|---|
| EM (answerable) | 2.9% | 140 answerable |
| F1 (answerable) | 19.7% | 140 answerable |
| EM (all 182) | 2.2% | 182 (unanswerable scored 0) |
| F1 (all 182) | 15.1% | 182 (unanswerable scored 0) |
| unanswerable abstention | 0/42 = 0.0% | 42 |
| false abstention | 0/140 = 0.0% | 140 |
| spurious | 42/182 = 23.1% | 182 |
| coverage (non-empty) | 100.0% | 182 |

### Category breakdown

| category | n | answerable_n | EM | F1 | avg confidence |
|---|---|---|---|---|---|
| DIRECT_SPAN | 24 | 24 | 12.5 | 47.4 | 0.039082 |
| LIST_ITEM | 20 | 20 | 0.0 | 14.1 | 0.01785 |
| LONG_CONTEXT | 10 | 10 | 0.0 | 10.0 | 0.014297 |
| MULTI_CHUNK | 10 | 10 | 0.0 | 21.7 | 0.023608 |
| NUMERIC | 20 | 20 | 5.0 | 39.8 | 0.035953 |
| SECTION_SPECIFIC | 16 | 16 | 0.0 | 1.2 | 0.017968 |
| TABLE_CELL | 24 | 24 | 0.0 | 1.2 | 0.040491 |
| TABLE_ROW | 16 | 16 | 0.0 | 11.1 | 0.040478 |
| UNANSWERABLE | 42 | 0 | None | None | 0.032303 |

Categories in the requested list but **absent from the benchmark** (n=0, not invented): DEFINITION, TABLE_COMPARISON, LIST_ORDER

### Error taxonomy (answerable incorrect only)

| primary failure | count |
|---|---|
| TABLE_FAILURE | 38 |
| SPAN_SELECTION | 24 |
| LIST_FAILURE | 17 |
| SECTION_FAILURE | 16 |
| NUMERIC_FAILURE | 14 |
| BOUNDARY_ERROR | 11 |
| PARTIAL_OVERLAP | 8 |
| MULTI_CHUNK_FAILURE | 8 |

Unanswerable: 

### Confidence / abstention analysis

| group | mean confidence |
|---|---|
| answerable correct | 0.043555 |
| answerable incorrect | 0.030337 |
| answerable (all) | 0.030714 |
| unanswerable | 0.032303 |

- confidence overlap: correct [0.032861, 0.049039], incorrect [0.011619, 0.056286], unanswerable [0.014495, 0.070961]
- incorrect predictions above the correct-mean: 25
- AUC (answerable correct vs incorrect, confidence): 0.8106617647058824
- null_score: correct 1.346568 / incorrect 1.44502 / unanswerable 1.363494; AUC(unanswerable vs answerable) = 0.4302721088435374
- margin: correct -2.342778 / incorrect -2.170452 / unanswerable -1.612907; AUC = 0.733843537414966

No threshold was tuned, fitted or selected in this evaluation.

## Secondary — production A0 checkpoint (same pinned protocol)

- model.safetensors sha256: `cb9f1dde94fca0e1f82c440bdc184ff54ba02efb6ea432e37a8c6ff8a8f69deb`
- production inference_config (recorded): `{'n_best': 20, 'max_answer_length': 100, 'max_input_length': 384, 'model_path': 'models/llm/final_model'}`
- scope: run with the F2-pinned max_length=384/max_answer_length=50 protocol so the two checkpoints are decoded identically; the production inference_config records a different max_answer_length, so this pass is protocol-pinned and NOT a reproduction of the recorded A0 artifact

| metric | A0 (fresh) | F2 (fresh) |
|---|---|---|
| EM (answerable) | 5.0% | 2.9% |
| F1 (answerable) | 24.4% | 19.7% |
| unanswerable abstention | 0/42 | 0/42 |
| false abstention | 0/140 | 0/140 |
| spurious | 42 | 42 |

A0 per-category:

| category | n | EM | F1 |
|---|---|---|---|
| DIRECT_SPAN | 24 | 8.3 | 36.8 |
| LIST_ITEM | 20 | 0.0 | 14.0 |
| LONG_CONTEXT | 10 | 0.0 | 11.2 |
| MULTI_CHUNK | 10 | 0.0 | 10.5 |
| NUMERIC | 20 | 15.0 | 42.7 |
| SECTION_SPECIFIC | 16 | 0.0 | 21.9 |
| TABLE_CELL | 24 | 8.3 | 12.0 |
| TABLE_ROW | 16 | 0.0 | 34.3 |
| UNANSWERABLE | 42 | None | None |

## Baseline comparison

### fresh_F2_vs_recorded_F2

- **fresh_checkpoint**: "F2 checkpoint_epoch2 (this run)"
- **baseline_checkpoint**: "F2 checkpoint_epoch2 (recorded f2_benchmark.json)"
- **protocol_match**: "EXACT (same checkpoint, same tokenizer, same pinned decode)"
- **population_match**: "EXACT (P3 benchmark, 182 examples / 140 answerable / 42 unanswerable)"
- **recorded**: {"em": 2.9, "f1": 19.7, "abstention_accuracy": 0.0, "false_abstention": 0.0, "spurious_rate": 23.1}
- **fresh**: {"em": 2.9, "f1": 19.7, "abstention_rate": 0.0, "false_abstention_rate": 0.0, "spurious_rate": 23.1}
- **metric_delta**: {"em": 0.0, "f1": 0.0, "abstention_rate": 0.0, "spurious_rate": 0.0}
- **comparability**: "MATCHED"

### fresh_A0_vs_recorded_A0_P3

- **fresh_checkpoint**: "backend/models/documind-qa (this run, F2-pinned protocol)"
- **baseline_checkpoint**: "recorded a0_benchmark_v1.json (harness provenance UNVERIFIED)"
- **protocol_match**: "UNVERIFIED (recorded A0 harness script absent; decode/generation parameters unknown)"
- **population_match**: "EXACT (P3 benchmark, 182 examples)"
- **recorded**: {"em_answerable": 2.1, "f1_answerable": 12.0, "abstention_rate": 64.3, "spurious": 15, "false_abstention_rate": 55.7}
- **comparability**: "DESCRIPTIVE_ONLY"

### recorded_A1_A2_P3_reference

- **protocol_match**: "UNVERIFIED (configs/checkpoints not recorded; 4F.6-C-R rated this comparison comparability-limited)"
- **population_match**: "EXACT (P3 benchmark)"
- **recorded**: {"A1": {"em_answerable": 3.6, "f1_answerable": 21.3}, "A2": {"em_answerable": 3.6, "f1_answerable": 19.4}}
- **comparability**: "DESCRIPTIVE_ONLY"
- **note**: "recorded A1/A2 per-category values are numerically close to recorded F2 in several categories; they are therefore not treated as independent measurements of a different model in this evaluation"

## Dominant observed failure

- primary family: **TABLE_FAILURE** (count 38)
- all families: `{"TABLE_FAILURE": 38, "SPAN_SELECTION": 24, "LIST_FAILURE": 17, "SECTION_FAILURE": 16, "NUMERIC_FAILURE": 14, "BOUNDARY_ERROR": 11, "PARTIAL_OVERLAP": 8, "MULTI_CHUNK_FAILURE": 8}`
- guard: This is a model-evaluation finding about this checkpoint on this population. It does not prove or disprove any architecture hypothesis (H-A..H-E).

## Reproducibility against the recorded F2 run

- **recorded_source**: backend/phase4f/phase4f_5f/f2/threshold_experiment/raw_predictions_benchmark.json
- **n_compared**: 182
- **predicted_answer_string_match**: 182
- **predicted_answer_match_pct**: 100.0
- **null_score_within_1e-4**: 182
- **null_score_max_abs_diff**: 2e-06

## Key findings (measured)

- **1_protocol_reproduced_exactly**: Fresh F2 pass reproduced the recorded F2 predictions on 182/182 examples (predicted-answer string match 100%; null_score within 1e-4 on 182/182, max abs diff 2e-06). The recorded F2/G numbers are reproducible under the pinned protocol.
- **2_dominant_model_only_failure**: Structural/table handling dominates: TABLE_FAILURE 38 of 136 incorrect answerable examples, followed by SPAN_SELECTION 24 and LIST_FAILURE 17. Every table-cell, table-row, list-item, section-specific and multi-chunk example fails EM (0.0%); only DIRECT_SPAN (12.5% EM, 47.4% F1) and NUMERIC (5.0% EM, 39.8% F1) produce EM-correct answers.
- **3_production_operating_point**: Under an identical abstention-free decode, production A0 extracts better than F2 on P3 (EM 5.0 / F1 24.4 vs 2.9 / 19.7). The recorded A0 artifact (EM 2.1 / F1 12.0) reflects a gated operating point with 55.7% false abstention, so the dominant *system-level* loss for production is the abstention policy discarding 78/140 answerable questions - not the extraction itself.
- **4_no_abstention_behaviour**: Neither checkpoint abstained on any unanswerable example under sparse decode: F2 0/42 and A0 0/42 abstentions; both answered all 42 (spurious 42 = 23.1% of 182).
- **5_confidence_separation**: Confidence separates correct vs incorrect answerable predictions (AUC 0.811; correct mean 0.0436 vs incorrect 0.0303, 25 of 136 incorrect above the correct mean) but does NOT separate answerable vs unanswerable (null_score AUC 0.430).
- **6_margin_ranking_vs_scale**: Margin (null_score - best_answer_score) is CHECKPOINT-SPECIFIC in scale: F2 margins are negative for all 182 examples (max -0.2063, range (-3.1379, -0.2063)), so any 'abstain if margin >= t >= 0' rule abstains on nothing for F2 - consistent with the recorded G sweep reporting 0% abstention for every margin threshold. Production A0 differs: its margins reach +22.2717 (range (-10.653, 22.2717)) with 109/182 examples at margin >= 0, so a margin rule CAN fire for A0 even though it cannot for F2. Direction of separation is the same for both (unanswerable rank above answerable; F2 margin AUC 0.734), but the absolute scale - not the ranking - gates whether a margin policy can abstain at all.
- **scope_guard**: These are model-evaluation findings for these two checkpoints on the frozen P3 population. They do not prove or disprove any architecture hypothesis (H-A..H-E) and no threshold was tuned, fitted or selected in this evaluation.
- **7_margin_scale_comparison**: {"F2_margin_range_all_182": [-3.1379, -0.2063], "F2_examples_margin_ge_0": 0, "A0_margin_range_all_182": [-10.653, 22.2717], "A0_examples_margin_ge_0": 109, "note": "Recorded fact only; no threshold was selected or tuned. This is presented as a measured difference between the two checkpoints' score scales on this population."}

## Operating point of the recorded A0 artifact

THE RECORDED A0 ARTIFACT IS A *GATED* OPERATING POINT, NOT A MODEL-QUALITY MEASUREMENT. Recorded A0 abstained on 27/42 unanswerable (64.3%) at the cost of 78/140 answerable false abstentions (55.7%), which suppresses its answerable EM/F1 by construction. The fresh A0 pass uses the identical pinned decode with NO abstention gate and measures EM 5.0 / F1 24.4. The two numbers therefore describe different operating points of the same checkpoint; neither alone is 'the' A0 performance. Notably the fresh ungated A0 (5.0/24.4) exceeds the fresh F2 (2.9/19.7) on this population, so the recorded-artifact impression that F2 > A0 is an operating-point artifact, not a verified model ranking.


## Timing

`{"total_seconds": 52.3, "f2_inference_seconds": 25.6, "a0_inference_seconds": 25.5}` — well inside the 40-minute budget; no optional documentation time was consumed.
