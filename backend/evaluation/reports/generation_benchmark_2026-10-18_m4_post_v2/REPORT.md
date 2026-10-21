# Generation benchmark — extractive vs. local generative

- Run: `generation_benchmark_2026-10-18_m4_post_v2`
- Started: 2026-10-18T16:16:08.610504+00:00
- Benchmark: `phases\phase4f\phase4f_5d\benchmark\qa_benchmark_v1.jsonl`
- SHA-256: `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` (matches expected: True)
- Examples: 182 (140 answerable / 42 unanswerable)
- Generative format: 10-mark
- Retrieval: not measured — benchmark rows are self-contained (context supplied with the row)

## Metrics

| Metric | Extractive baseline | Local generative |
|---|---|---|
| Exact match (answerable) | 0.157 | 0.150 |
| Token F1 (answerable) | 0.387 | 0.309 |
| Lead-answer EM (answerable) | — | 0.150 |
| Lead-answer F1 (answerable) | — | 0.297 |
| Abstention on unanswerable | 0.000 | 0.952 |
| Spurious answer on unanswerable | 1.000 | 0.048 |
| Empty answer rate (all) | — | 0.445 |
| Unsupported-claim rate | — | 0.2199 |
| Citation accuracy (lexical) | — | 0.7801 |
| Verified rate (all) | — | 0.527 |
| Answerability-gate abstentions | — | 47 |
| Withheld (unattributable) | — | 34 |

### Answer-level verification status (generative)

| Status | Count |
|---|---|
| INSUFFICIENT_EVIDENCE | 81 |
| PARTIALLY_SUPPORTED | 5 |
| SUPPORTED | 96 |

## Latency (generative, CPU)

- p50: 329.5 ms
- p95: 1506.2 ms
- max: 4179 ms

## Failure categories (answerable rows)

- `empty_or_abstained`: 41
- `incorrect_answer`: 73
- `none`: 21
- `partially_supported`: 5

## Notes

- EM/F1 are computed only on answerable rows, using the project's normalise/EM/token-F1 functions.
- The extractive model has no no-answer head, so its abstention is only ever an empty span; the production evidence gate is NOT part of this measurement.
- Faithfulness is measured by the deterministic verifier (lexical attribution), not by human or entailment judging.
