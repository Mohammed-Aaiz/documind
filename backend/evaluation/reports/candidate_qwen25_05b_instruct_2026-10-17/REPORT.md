# Candidate model evaluation — Qwen/Qwen2.5-0.5B-Instruct

- Run: `candidate_qwen25_05b_instruct_2026-10-17`
- Started: 2026-10-17T17:56:09.600605+00:00
- Model: `Qwen/Qwen2.5-0.5B-Instruct` (revision: `7ae557604adf67be50417f59c2c2f167def9a775`)
- Benchmark: `phases\phase4f\phase4f_5d\benchmark\qa_benchmark_v1.jsonl`
- SHA-256: `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` (matches: True)
- Rows: 182 (140 answerable / 42 unanswerable)
- Format: 10-mark, greedy decoding, max_new_tokens=64
- Load time: 2.61 s; peak process RSS: 1699.0 MB

## Results

| Metric | Extractive baseline | Candidate |
|---|---|---|
| Exact match (answerable) | 0.157 | 0.093 |
| Token F1 (answerable) | 0.387 | 0.189 |
| Lead-answer EM | — | 0.093 |
| Abstention on unanswerable | 0.000 | 0.976 |
| Spurious answer on unanswerable | 1.000 | 0.024 |
| Empty answer rate (all) | — | 0.681 |
| SUPPORTED rate (all) | — | 0.280 |
| Unsupported-claim rate | — | 0.1 |
| Withheld (unattributable) | — | 36 |
| Answerability-gate abstentions | — | 83 |
| Model refusals | — | 5 |

## Latency (CPU)

- p50: 1918.0 ms
- p95: 4217.7 ms
- max: 6375 ms

## Notes

- Same frozen rows, same answerability gate, same verifier and same mark elaboration as the production path; only the generating model differs.
- The candidate is a causal chat model evaluated at 10 marks, the same format as the incumbent comparison report.
- EM/F1 are computed on answerable rows only, using the project's metrics.
- This is an experimental evaluation; no production default was changed.
