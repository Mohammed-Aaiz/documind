# Generation benchmark — extractive vs. local generative

- Run: `generation_benchmark_2026-10-21_m7_fmt15`
- Started: 2026-10-21T13:14:25.793899+00:00
- Benchmark: `phases\phase4f\phase4f_5d\benchmark\qa_benchmark_v1.jsonl`
- SHA-256: `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` (matches expected: True)
- Examples: 182 (140 answerable / 42 unanswerable)
- Generative format: 15-mark
- Retrieval: not measured — benchmark rows are self-contained (context supplied with the row)

## Metrics

| Metric | Extractive baseline | Local generative |
|---|---|---|
| Exact match (answerable) | 0.157 | 0.493 |
| Token F1 (answerable) | 0.387 | 0.601 |
| Lead-answer EM (answerable) | — | 0.471 |
| Lead-answer F1 (answerable) | — | 0.598 |
| Abstention on unanswerable | 0.000 | 0.905 |
| Spurious answer on unanswerable | 1.000 | 0.095 |
| Empty answer rate (all) | — | 0.341 |
| Unsupported-claim rate | — | 0.0979 |
| Citation accuracy (lexical) | — | 0.9021 |
| Verified rate (all) | — | 0.648 |
| Answerability-gate abstentions | — | 45 |
| Withheld (unattributable) | — | 17 |

### Answer-level verification status (generative)

| Status | Count |
|---|---|
| INSUFFICIENT_EVIDENCE | 62 |
| PARTIALLY_SUPPORTED | 2 |
| SUPPORTED | 118 |

## Latency (generative, CPU)

- p50: 0.0 ms
- p95: 1295.8 ms
- max: 3004 ms

## Failure categories (answerable rows)

- `empty_or_abstained`: 24
- `incorrect_answer`: 46
- `none`: 69
- `partially_supported`: 1

## Notes

- EM/F1 are computed only on answerable rows, using the project's normalise/EM/token-F1 functions.
- The extractive model has no no-answer head, so its abstention is only ever an empty span; the production evidence gate is NOT part of this measurement.
- Faithfulness is measured by the deterministic verifier (lexical attribution), not by human or entailment judging.
