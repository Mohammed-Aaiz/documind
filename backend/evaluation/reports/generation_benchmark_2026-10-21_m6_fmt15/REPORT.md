# Generation benchmark — extractive vs. local generative

- Run: `generation_benchmark_2026-10-21_m6_fmt15`
- Started: 2026-10-21T12:00:31.314460+00:00
- Benchmark: `phases\phase4f\phase4f_5d\benchmark\qa_benchmark_v1.jsonl`
- SHA-256: `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` (matches expected: True)
- Examples: 182 (140 answerable / 42 unanswerable)
- Generative format: 15-mark
- Retrieval: not measured — benchmark rows are self-contained (context supplied with the row)

## Metrics

| Metric | Extractive baseline | Local generative |
|---|---|---|
| Exact match (answerable) | 0.157 | 0.357 |
| Token F1 (answerable) | 0.387 | 0.480 |
| Lead-answer EM (answerable) | — | 0.357 |
| Lead-answer F1 (answerable) | — | 0.480 |
| Abstention on unanswerable | 0.000 | 0.905 |
| Spurious answer on unanswerable | 1.000 | 0.095 |
| Empty answer rate (all) | — | 0.390 |
| Unsupported-claim rate | — | 0.1631 |
| Citation accuracy (lexical) | — | 0.8369 |
| Verified rate (all) | — | 0.599 |
| Answerability-gate abstentions | — | 45 |
| Withheld (unattributable) | — | 26 |

### Answer-level verification status (generative)

| Status | Count |
|---|---|
| INSUFFICIENT_EVIDENCE | 71 |
| PARTIALLY_SUPPORTED | 2 |
| SUPPORTED | 109 |

## Latency (generative, CPU)

- p50: 305.0 ms
- p95: 1881.4 ms
- max: 5320 ms

## Failure categories (answerable rows)

- `empty_or_abstained`: 33
- `incorrect_answer`: 56
- `none`: 50
- `partially_supported`: 1

## Notes

- EM/F1 are computed only on answerable rows, using the project's normalise/EM/token-F1 functions.
- The extractive model has no no-answer head, so its abstention is only ever an empty span; the production evidence gate is NOT part of this measurement.
- Faithfulness is measured by the deterministic verifier (lexical attribution), not by human or entailment judging.
