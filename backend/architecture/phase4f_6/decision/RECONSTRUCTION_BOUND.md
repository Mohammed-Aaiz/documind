# Reconstruction Bound — answer-text reconstruction only

> **This is a reconstruction experiment, not a model result.** The measured
> quantity is the effect of removing the `tokenizer.decode()` spacing artefact
> from the recorded answer strings. It is *not* model performance, *not*
> generalization, and *not* an accuracy claim.

## Method

- Changed variable: **answer text only** (decoded span → reconstructed source text).
- Held fixed: benchmark, checkpoints, selected spans, logits, scores, thresholds,
  metric definitions and normalization.
- **No model was loaded, no inference was run, no dataset was created, nothing was fitted.**
- Repair rules (delete the spaces `decode()` inserted *inside* one value): `(?<=\d) (?=[.,]\d)`, `(?<=[.,$]) (?=\d)`, `(?<=\d) (?=%)`, `(?<=\d) (?=[-\u2013]\d)`, `(?<=[-\u2013]) (?=\d)`

## Limitations

- The recorded artifact stores only the post-decode string; the source context and the tokenizer offsets are absent, so the real fix cannot be re-applied here. The measured quantity is a documented string repair of the decode artefact.
- The population is fully leaked (every example is present in training_data.jsonl / training_data_v3.jsonl), so this is a training-set quantity with no generalization meaning.
- The repair is a heuristic approximation, not the fix, so it is not authoritative on its own. It was validated against a real re-run: this script gives F2 UNGATED answerable EM 21/140, and the fixed decoder measured directly on the same benchmark also gives 21/140 ungated (15.0%) - the estimate matches the measurement exactly. The 14.29% quoted from phase4f_5f/f2/threshold_experiment is the SAME run with the abstention gate ON, not a different quantity. The re-run remains authoritative.
- No model improvements were made. Span selection, scoring and confidence are unchanged by the reconstruction fix.

## Inputs

- predictions: `backend/architecture/phase4f_6/e0_diagnostics/diagnostics/model_40min_predictions.json` sha256 `d7d9d65e944488ac...` (MATCH)
- benchmark: `backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` sha256 `1166bf4ff38265c2...` (VERIFIED)

## Results

### F2_primary

- predictions: 182 (140 answerable, 42 unanswerable)
- answerable EM before (as recorded): **2.86%** (4/140)
- answerable EM after repair: **15.0%** (21/140)
- answerable F1: 19.69% → 31.45%
- predictions changed by the repair: 123 (EM +17 / -0)
- gold answers containing a decimal/thousands separator: 70 (EM 0 → 16)

| category | n | answerable | EM before | EM after | changed |
|---|---|---|---|---|---|
| DIRECT_SPAN | 24 | 24 | 12.5% | 66.67% | 18 |
| NUMERIC | 20 | 20 | 5.0% | 15.0% | 13 |
| TABLE_CELL | 24 | 24 | 0.0% | 4.17% | 20 |
| TABLE_ROW | 16 | 16 | 0.0% | 0.0% | 12 |
| LIST_ITEM | 20 | 20 | 0.0% | 0.0% | 12 |
| SECTION_SPECIFIC | 16 | 16 | 0.0% | 0.0% | 11 |
| MULTI_CHUNK | 10 | 10 | 0.0% | 10.0% | 8 |
| LONG_CONTEXT | 10 | 10 | 0.0% | 0.0% | 10 |
| UNANSWERABLE | 42 | 0 | 0.0% | 0.0% | 19 |

### A0_secondary

- predictions: 182 (140 answerable, 42 unanswerable)
- answerable EM before (as recorded): **5.0%** (7/140)
- answerable EM after repair: **15.71%** (22/140)
- answerable F1: 24.44% → 38.07%
- predictions changed by the repair: 83 (EM +15 / -0)
- gold answers containing a decimal/thousands separator: 70 (EM 0 → 12)

| category | n | answerable | EM before | EM after | changed |
|---|---|---|---|---|---|
| DIRECT_SPAN | 24 | 24 | 8.33% | 12.5% | 18 |
| NUMERIC | 20 | 20 | 15.0% | 70.0% | 14 |
| TABLE_CELL | 24 | 24 | 8.33% | 16.67% | 8 |
| TABLE_ROW | 16 | 16 | 0.0% | 0.0% | 7 |
| LIST_ITEM | 20 | 20 | 0.0% | 0.0% | 6 |
| SECTION_SPECIFIC | 16 | 16 | 0.0% | 0.0% | 4 |
| MULTI_CHUNK | 10 | 10 | 0.0% | 10.0% | 6 |
| LONG_CONTEXT | 10 | 10 | 0.0% | 0.0% | 5 |
| UNANSWERABLE | 42 | 0 | 0.0% | 0.0% | 15 |

