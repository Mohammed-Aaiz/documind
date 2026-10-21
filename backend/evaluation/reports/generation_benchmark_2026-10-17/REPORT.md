# Generation benchmark — extractive vs. local generative

- Run: `generation_benchmark_2026-10-17`
- Started: 2026-10-17T16:32:55.130880+00:00
- Benchmark: `phases\phase4f\phase4f_5d\benchmark\qa_benchmark_v1.jsonl`
- SHA-256: `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` (matches expected: True)
- Examples: 182 (140 answerable / 42 unanswerable)
- Generative format: 10-mark
- Retrieval: not measured — benchmark rows are self-contained (context supplied with the row)

## Metrics

| Metric | Extractive baseline | Local generative |
|---|---|---|
| Exact match (answerable) | 0.157 | 0.071 |
| Token F1 (answerable) | 0.387 | 0.141 |
| Abstention on unanswerable | 0.000 | 1.000 |
| Spurious answer on unanswerable | 1.000 | 0.000 |
| Empty answer rate (all) | — | 0.802 |
| Unsupported-claim rate | — | 0.52 |
| Citation accuracy (lexical) | — | 0.48 |
| Verified rate (all) | — | 0.192 |
| Answerability-gate abstentions | — | 108 |
| Withheld (unattributable) | — | 38 |

### Answer-level verification status (generative)

| Status | Count |
|---|---|
| INSUFFICIENT_EVIDENCE | 146 |
| PARTIALLY_SUPPORTED | 1 |
| SUPPORTED | 35 |

## Latency (generative, CPU)

- p50: 0.0 ms
- p95: 1321.1 ms
- max: 4249 ms

## Failure categories (answerable rows)

- `empty_or_abstained`: 104
- `incorrect_answer`: 25
- `none`: 10
- `partially_supported`: 1

## Notes

- EM/F1 are computed only on answerable rows, using the project's normalise/EM/token-F1 functions.
- The extractive model has no no-answer head, so its abstention is only ever an empty span; the production evidence gate is NOT part of this measurement.
- Faithfulness is measured by the deterministic verifier (lexical attribution), not by human or entailment judging.
