# Generation benchmark — extractive vs. local generative

- Run: `generation_benchmark_2026-10-17_fmt10_relations_verifier`
- Started: 2026-10-17T18:23:25.120218+00:00
- Benchmark: `phases\phase4f\phase4f_5d\benchmark\qa_benchmark_v1.jsonl`
- SHA-256: `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` (matches expected: True)
- Examples: 8 (4 answerable / 4 unanswerable)
- Generative format: 10-mark
- Retrieval: not measured — benchmark rows are self-contained (context supplied with the row)

## Metrics

| Metric | Extractive baseline | Local generative |
|---|---|---|
| Exact match (answerable) | 0.250 | 0.000 |
| Token F1 (answerable) | 0.435 | 0.000 |
| Lead-answer EM (answerable) | — | 0.000 |
| Lead-answer F1 (answerable) | — | 0.000 |
| Abstention on unanswerable | 0.000 | 1.000 |
| Spurious answer on unanswerable | 1.000 | 0.000 |
| Empty answer rate (all) | — | 0.625 |
| Unsupported-claim rate | — | 0.0 |
| Citation accuracy (lexical) | — | 1.0 |
| Verified rate (all) | — | 0.375 |
| Answerability-gate abstentions | — | 5 |
| Withheld (unattributable) | — | 0 |

### Answer-level verification status (generative)

| Status | Count |
|---|---|
| INSUFFICIENT_EVIDENCE | 5 |
| SUPPORTED | 3 |

## Latency (generative, CPU)

- p50: 0.0 ms
- p95: 529.8 ms
- max: 555 ms

## Failure categories (answerable rows)

- `empty_or_abstained`: 1
- `incorrect_answer`: 3

## Notes

- EM/F1 are computed only on answerable rows, using the project's normalise/EM/token-F1 functions.
- The extractive model has no no-answer head, so its abstention is only ever an empty span; the production evidence gate is NOT part of this measurement.
- Faithfulness is measured by the deterministic verifier (lexical attribution), not by human or entailment judging.
