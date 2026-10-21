# Generation configuration sweep — flan-t5-base

- Run: `generation_config_sweep_2026-10-17`
- Started: 2026-10-17T17:42:38.370289+00:00
- Benchmark: `phases\phase4f\phase4f_5d\benchmark\qa_benchmark_v1.jsonl`
- SHA-256: `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` (matches: True)
- Rows: 182, format: 5-mark
- Model: `google/flan-t5-base` (unchanged; no candidate download in this run)

| Variant | EM | F1 | Lead EM | Empty (answerable) | Abstain (unanswerable) | Spurious | Unsupported | p50 | p95 |
|---|---|---|---|---|---|---|---|---|---|
| `v0_current` | 0.121 | 0.216 | 0.121 | 0.614 | 0.976 | 0.024 | 0.4149 | 220 ms | 1173 ms |
| `v1_greedy` | 0.129 | 0.231 | 0.129 | 0.593 | 0.976 | 0.024 | 0.3789 | 133 ms | 1253 ms |
| `v2_short_answer` | 0.136 | 0.248 | 0.136 | 0.593 | 0.976 | 0.024 | 0.3895 | 223 ms | 946 ms |
| `v3_context_first` | 0.114 | 0.222 | 0.114 | 0.586 | 0.952 | 0.048 | 0.3814 | 205 ms | 663 ms |

## Pairwise against the production config (answerable rows)

| Variant | Correct only in variant | Correct only in v0 |
|---|---|---|
| `v1_greedy` | 2 | 1 |
| `v2_short_answer` | 3 | 1 |
| `v3_context_first` | 3 | 4 |

A one-or-two-answer difference on 140 answerable rows is inside noise; the pairwise columns are the honest way to read these totals.

## Variant definitions

- `v0_current` — beams=4, no_repeat_ngram=3 (production default)
- `v1_greedy` — beams=1 (greedy)
- `v2_short_answer` — beams=4, prompt asks for a short answer phrase
- `v3_context_first` — beams=4, context placed before the question

Every variant uses the production `answer_generatively` path (answerability gate, withholding, verification, mark elaboration), so the only difference is the swept parameter. No benchmark row was edited and no candidate model was downloaded.
