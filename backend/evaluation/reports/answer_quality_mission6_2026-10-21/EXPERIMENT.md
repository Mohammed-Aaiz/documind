# EXPERIMENT — DocuMind answer quality, Mission 6 (2026-10-21)

All runs are in `backend/evaluation/reports/`. Every run verified the frozen benchmark
SHA-256 before inference; none overwrote a historical artifact.

## 1. Runs

| Purpose | Run id |
|---|---|
| Previous state (read, not regenerated) | `generation_benchmark_2026-10-18_m5_post_v1_r2` |
| Mission 6, 10-mark, primary | `generation_benchmark_2026-10-21_m6_post_v1` |
| Mission 6, 10-mark, repeat (determinism) | `generation_benchmark_2026-10-21_m6_post_v1_r2` |
| Mission 6, 5-mark | `generation_benchmark_2026-10-21_m6_fmt5` |
| Mission 6, 15-mark | `generation_benchmark_2026-10-21_m6_fmt15` |
| Ledger | `answer_quality_mission6_2026-10-21/` |

Command (from `backend/`):

```
venv/Scripts/python.exe -m evaluation.experiments.run_generation_benchmark \
    --format 10 --run-id generation_benchmark_2026-10-21_m6_post_v1
venv/Scripts/python.exe -m evaluation.experiments.build_answer_quality_ledger \
    --run-id answer_quality_mission6_2026-10-21
```

Metric definitions are unchanged (`evaluation/qa_metrics.py`: lowercase + whitespace
collapse, token-set F1). The benchmark, its gold answers and the claim dataset are
byte-identical to the runs they are compared with.

## 2. Batches, each measured separately

The three behaviour changes were designed together but verified as one generation run
because the pipeline is single-pass and the changes are in disjoint layers (evidence
resolution → gate → answer formatting). The row-level attribution below shows which
change produced which row, so the batch boundary is auditable.

| Batch | Change | Rows it touched |
|---|---|---|
| 1 | deterministic table grounding (`generation/tables.py` + service hook) | 40 |
| 2 | stopword-claim verification (`support_ratio`) | 1 |
| 3 | analysis-elaboration filter + prompt-echo strip | table rows + 6 partially-supported rows |
| 4 | fiscal-year gate normalisation | 2 |

## 3. Result: 10-mark, 140 answerable / 42 unanswerable

| Metric | M5 | M6 | Δ |
|---|---:|---:|---:|
| Answerable answered | 100/140 | 109/140 | +9 |
| Exact match | 0.1500 | **0.4500** | +0.3000 |
| Token F1 | 0.3103 | **0.5621** | +0.2518 |
| Lead-answer EM | 0.1500 | 0.4500 | +0.3000 |
| Incorrect answers | 73 | 46 | −27 |
| Empty / abstained | 40 | 31 | −9 |
| Gate refusals (answerable) | 13 | 11 | −2 |
| Withheld after generation (answerable) | 27 | 20 | −7 |
| Withheld (all rows) | 33 | 26 | −7 |
| Unanswerable spurious answers | 2/42 | 2/42 | 0 |
| Claims / supported / unsupported | 143 / 112 / 31 | 132 / 114 / 18 | |
| Unsupported-claim rate | 0.2168 | **0.1364** | −0.0804 |
| Citation accuracy | 0.7832 | **0.8636** | +0.0804 |
| Verified rate (all 182) | 0.5275 | 0.6099 | +0.0824 |
| Empty rate (all 182) | 0.4396 | 0.3901 | −0.0495 |
| p50 / p95 latency | 317 / 1456 ms | 236 / 1103 ms | −81 / −353 ms |

`p50`/`p95` are taken from `m6_post_v1_r2`; the primary run was executed while the
machine was otherwise busy and reports 534 / 3014 ms. The two runs produce
**byte-identical answers** (0 differing rows), so only latency differs.

Unsupported-claim count fell from 31 to 18 even though 9 more questions are answered,
because the appended table-header claims (6 rows) are gone and table answers carry one
verifiable claim each.

## 4. Answer-level diff vs Mission 5 (all 182 rows inspected)

| Class | Count | Detail |
|---|---:|---|
| Newly correct | **42** | 33 answers changed text, 9 went from withheld to answered |
| Newly incorrect | **0** | |
| Correct answers that became withheld | **0** | |
| Newly spurious on unanswerable | **0** | |
| Newly withheld | **0** | |
| Changed but still wrong | **0** | |
| Unchanged | 140 | |

Producer mix after the change (answerable rows): deterministic table **40**,
model-generated with an answer **69**, withheld **20**, gate refusal **11**.

The 42 newly correct rows, by kind: 24 `TABLE_CELL`, 16 `TABLE_ROW`, 2 `NUMERIC`
(fiscal-year gate). Spot-checks of the semantically odd ones:

- `tc_a7432939` "How much is the payment schedule of Q2 2025?" → `Q2 2025`. The
  resolver reads cell (row `Q2 2025`, column `Payment Schedule`), which *is* the gold
  value. The question itself conflates the schedule's label with its amount; the
  table's first column holds the label. Recorded as a benchmark artifact, not as an
  improvement in comprehension.
- `tc_479dca78` "what is the division for Enterprise Solutions?" → `Enterprise
  Solutions`; `tc_5f43398e` "what variable value does Temperature show?" →
  `Temperature`. Here cell 0 *is* the named attribute column, so the row label is the
  correct cell value.
- `unans_*` rows: identical answers to M5, both pre-existing spurious answers retained
  (kept deliberately — see §7).

## 5. Mark-extent runs (5 and 15 marks)

| Format | EM | F1 | Unanswerable spurious | Unsupported rate |
|---|---:|---:|---:|---:|
| 5 | 0.4429 | 0.5379 | 2/42 | 0.1538 |
| 10 | 0.4500 | 0.5621 | 2/42 | 0.1364 |
| 15 | 0.3571 | 0.4801 | **4/42** | 0.1631 |

At 15 marks two further unanswerable rows produce an answer. This is **not** a
Mission 6 regression: generation was reproduced directly at both marks for
`unans_d7480687` and `unans_a603100e` and the *decoder output itself* differs (the
per-format depth cue changes decoding; both have 0 supported claims at 10 marks). The
effect is pre-existing mark-extent behaviour and is recorded as a known limitation.

## 6. Trade-offs accepted

- Table answers do not receive mark-aware elaboration. A cell/row **is** the complete
  answer at every extent; padding it with further evidence sentences was measured to
  reduce correctness. `answer_generatively` returns it unchanged for 5/10/15.
- Table answers carry their citation in `sources`/warnings rather than as an inline
  `[n]`, because the cell is quoted verbatim from the cited block. The claim is still
  attributed to that block by the verifier (`citationAccuracy` 1.0 on all 40).
- Latency improves because 40 rows no longer call the model at all.

## 7. Known limitation retained

The 2 spurious answers on unanswerable rows are `unans_7b46d69d` (`100`) and
`unans_03d364a3` (`$52,000`) — the same two rows with the same answers as Mission 5.
They were not touched: closing them would require tightening the gate, which the
Mission 4/5 evidence shows costs answerable coverage, and no targeted rule was found
that closes them alone. `unans_7b46d69d` ("maximum concurrent connection limit" vs
"maximum of 100 concurrent connections") is arguably a mislabelled row rather than a
system error; that is a benchmark-review question, not a code change.
