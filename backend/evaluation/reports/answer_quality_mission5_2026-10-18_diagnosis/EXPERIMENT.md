# Mission 5 — controlled experiment (2026-10-18)

Benchmark: `phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl`,
SHA-256 `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0`,
182 rows (140 answerable / 42 unanswerable). Dataset v2
`f06795eb5034133d8dc600a4685621dc0999f4a00b71afa0f490731e0aecad88`, unchanged.
Format 10, lexical verifier (production default), one recorded context per row.

Runs: `generation_benchmark_2026-10-18_m4_baseline` (pre-Mission 4),
`generation_benchmark_2026-10-18_m4_post_v2` (Mission 4, pre-Mission 5),
`generation_benchmark_2026-10-18_m5_post_v1` and `..._m5_post_v1_r2` (Mission 5,
repeat). Claim-level: `answer_claim_evaluation_2026-10-18_m4_baseline_v2` and
`..._m5_v2`.

## 1. Verified baseline (recomputed from `results.jsonl`)

| Metric | pre-M4 | M4 (pre-M5) | M5 | Δ vs M4 |
|---|---:|---:|---:|---:|
| Answerable answered | 75 / 140 | 99 / 140 | 100 / 140 | +1 |
| Answered % | 53.6 % | 70.7 % | 71.4 % | +0.7 pp |
| Gate refusals | 49 | 13 | 13 | 0 |
| Withheld answers | 16 | 28 | 27 | −1 |
| Rejected claims (answerable) | 14 | 29 | 29 | 0 |
| Exact match | 0.1286 | 0.1500 | 0.1500 | 0 |
| Token F1 | 0.2567 | 0.3091 | 0.3103 | +0.0012 |
| Empty rate (182) | 0.5769 | 0.4451 | 0.4396 | −0.0055 |
| Unanswerable spurious | 2 / 42 | 2 / 42 | 2 / 42 | 0 |
| Unsupported-claim rate | 0.1981 | 0.2199 | 0.2168 | −0.0031 |
| Citation accuracy | 0.8019 | 0.7801 | 0.7832 | +0.0031 |

Claim-level (v2, all 75 propositional claims): lexical support precision
0.9322 → **0.9333**, recall 0.8333 → **0.8485**, F1 0.8800 → **0.8889**, false
rejects **11 → 10**, false accepts 4 → 4, exact three-way 0.7333 → **0.7467**.
Relation-aware metrics are unchanged (1.000 / 0.9545 / 0.9767).

## 2. Row-level changes (M4 → M5)

Two answers added, one removed, no answer text changed:

| Row | Change | Answer | Gold | Assessment |
|---|---|---|---|---|
| `tc_8340538b` | added | `1,000 req/min. Tier \| Rate Limit \| Burst Limit \| Monthly Quota [1]` | `1,000 req/min` | correct value recovered; table header is noise, so not exact |
| `tc_06f5c7e8` | added | `+4.2%. Division \| Q3 2025 Revenue \| Q3 2024 Revenue \| YoY Growth [1]` | `+4.2%` | correct value recovered; header noise, `PARTIALLY_SUPPORTED` |
| `tc_f3617604` | removed | was `0.0, 127.3, 0.8, 1.2%` | `mm` | wrong multi-column dump; removal is correct |

No other answer changed. Unanswerable rows: still 2 spurious (`unans_7b46d69d`,
`unans_03d364a3`), unchanged.

The `tc_f3617604` removal is the desired precision effect: its claim carried
numbers from Min/Max/Mean/Missing % while the question asks the Unit column, so
the column rule rejects it. The two added rows carry a number in the asked
column of the asked row, so they are accepted.

## 3. The Mission 4 "unsupported/citation regression" is a metric artifact

`generative_unsupported_claim_count` counts rejected claims from answers that
are **withheld** and never returned. Recomputing per answer:

| Run | Returned claims | Returned unsupported | Withheld answers | Rejected claims in withheld answers |
|---|---:|---:|---:|---:|
| pre-M4 | 87 | 5 | 16 | 14 |
| M4 | 113 | 5 | 28 | 24 |
| M5 | 116 | 6 | 27 | 23 |

The delivered-answer unsupported count is unchanged from pre-M4 to M4 (5/87 →
5/113); the rate moves only because the denominator includes withheld text. M5
adds one returned unsupported claim (6/116) from the two newly surfaced answers,
while withholding one fewer answer. This is a verified per-answer calculation,
not an inference. The metric should be read together with the withheld count;
changing its definition is out of scope and would break comparability with
historical reports.

## 4. Repeatability and integrity

* `..._m5_post_v1` and `..._m5_post_v1_r2` have identical metrics and identical
  answers for all 182 rows; only latency differs (132 rows).
* All five runs verify benchmark hash `1166bf4f…`; dataset hashes unchanged.
* No historical report or dataset was modified; each run has a new ID.
* No prompt, model, retrieval, threshold or verifier-default change.

## 5. What did not change

* 13 answerability-gate refusals (5 paraphrase/unit/header-stripped table
  cases, 8 boundary contexts) remain; fixing them requires evidence
  construction, not a verifier rule.
* 8 previously listed false withholdings: 2 recovered here (`tc_8340538b`,
  `tc_06f5c7e8`); the section-body cases (`sec_5e1deffc`, `sec_e95f766d`) and
  the over-wide list/compound cases remain withheld. Section-body alignment was
  considered and rejected for this mission (anchoring a heading to its body is
  less crisp; EM would remain false because the benchmark gold is the heading).
* 9 supported-but-off-target claims remain (4 wrong attribute/value/time, 5
  single-cell row answers); they need question-attribute reasoning at generation
  time.
* EM is flat: the two recovered answers append the table header, so they are not
  exact-string matches. The improvement is coverage and verifier precision, not
  a benchmark-scores rewrite.

## 6. Known limitations

Single annotator, 75 propositional claims, one frozen benchmark; no
integration/E2E/browser/live-server run; no new 15-mark benchmark; generation
remains Flan-T5-base with the same prompt. The table parser handles simple
header + equal-width rows only; anything else falls back to the previous prose
rule.
