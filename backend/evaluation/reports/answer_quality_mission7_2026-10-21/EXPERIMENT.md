# EXPERIMENT — DocuMind answer quality, Mission 7 (2026-10-21)

Every run below verified the frozen benchmark SHA-256 before inference and wrote a
new directory; no historical artifact was overwritten.

## 1. Runs

| Purpose | Run id |
|---|---|
| Baseline (read, not regenerated) | `generation_benchmark_2026-10-21_m6_post_v1` |
| Mission 7, 10-mark, first | `generation_benchmark_2026-10-21_m7_post_v1` |
| Mission 7, 10-mark, repeat (determinism) | `generation_benchmark_2026-10-21_m7_post_v1_r2` |
| Mission 7, 10-mark, pre-review reported run (records the producer) | `generation_benchmark_2026-10-21_m7_post_v2` |
| Mission 7, 10-mark, **reported run** (shipped code, after the independent review) | `generation_benchmark_2026-10-21_m7_reviewed` |
| Mission 7, 5-mark | `generation_benchmark_2026-10-21_m7_fmt5`; post-review `…_m7_reviewed_fmt5` |
| Mission 7, 15-mark | `generation_benchmark_2026-10-21_m7_fmt15`; post-review `…_m7_reviewed_fmt15` |
| Ledger | `answer_quality_mission7_2026-10-21/` (built from `m7_reviewed`) |
| Claim replay | `answer_claim_evaluation_2026-10-21_m7_v2`, `answer_claim_evaluation_2026-10-21_m7_reviewed` |

Commands (from `backend/`):

```
venv/Scripts/python.exe -m evaluation.experiments.run_generation_benchmark \
    --format 10 --run-id generation_benchmark_2026-10-21_m7_post_v2
venv/Scripts/python.exe -m evaluation.experiments.run_generation_benchmark \
    --run-id generation_benchmark_2026-10-21_m7_reviewed
venv/Scripts/python.exe -m evaluation.experiments.build_answer_quality_ledger \
    --run-id answer_quality_mission7_2026-10-21 \
    --previous-run generation_benchmark_2026-10-21_m6_post_v1 \
    --current-run  generation_benchmark_2026-10-21_m7_reviewed --force
venv/Scripts/python.exe -m evaluation.experiments.run_answer_claim_evaluation \
    --dataset v2 --run-id answer_claim_evaluation_2026-10-21_m7_v2
venv/Scripts/python.exe -m evaluation.experiments.run_answer_claim_evaluation \
    --run-id answer_claim_evaluation_2026-10-21_m7_reviewed
```

Metric definitions are unchanged (`evaluation/qa_metrics.py`). The benchmark, its
gold answers and the claim dataset are byte-identical to Mission 6.

## 2. Result: 10-mark, 140 answerable / 42 unanswerable

| Metric | M6 | M7 | Δ |
|---|---:|---:|---:|
| Answerable answered | 109/140 | **118/140** | +9 |
| Exact match | 0.4500 | **0.5786** | +0.1286 |
| Token F1 | 0.5621 | **0.6637** | +0.1016 |
| Lead-answer EM | 0.4500 | 0.5571 | +0.1071 |
| Incorrect answers | 46 | 35 | −11 |
| Empty / abstained | 31 | 24 | −7 |
| Gate refusals (answerable) | 11 | 11 | 0 |
| Withheld (answerable) | 20 | 13 | −7 |
| Withheld (all rows) | 26 | 19 | −7 |
| Unanswerable spurious | 2/42 | 2/42 | 0 |
| Claims / supported / unsupported | 132 / 114 / 18 | 134 / 123 / 11 | |
| Unsupported-claim rate | 0.1364 | **0.0821** | −0.0543 |
| Citation accuracy | 0.8636 | **0.9179** | +0.0543 |
| Verified rate (182) | 0.6099 | 0.6484 | +0.0385 |
| p50 / p95 latency | 236 / 1103 ms | 0 / 617 ms | |

Producers on the 140 answerable rows: deterministic table **40**, deterministic
list **20**, model **56**, withheld **13**, gate refusal **11**.

`p50` is 0 ms because 60 of the 182 rows (40 table + 20 list) are answered without
loading or running the model. `lead EM` is below full EM because the lead splitter
truncates a few model answers at the first sentence boundary.

## 3. Answer-level diff vs Mission 6 (all 182 rows inspected)

| Class | Count |
|---|---:|
| Previously wrong → now correct | **11** |
| Previously withheld → now correct | **7** |
| Previously correct → now wrong | 0 |
| Previously correct → now withheld | 0 |
| Previously withheld → still withheld | 13 |
| Previously wrong → different wrong answer | 0 |
| Previously unanswerable → still abstained | 40 |
| Previously unanswerable → now answered spuriously | 0 |
| Reference-answer ambiguity (unchanged) | 8 |
| Unchanged | 164 |

The 18 improvements are the whole `LIST_ITEM` family: 20 rows, of which 2 were
already exact in Mission 6. Each is a complete list item returned verbatim, e.g.
`COO: Elena Vasquez (since June 2021)` replacing the truncated `Elena Vasquez`, and
`Journal of Climate Data, 12(3), 45-67. DOI: 10.1234/jcd.2025.0123` replacing the
first citation for a "third" question. No other row changed.

## 4. Repeatability

`m7_post_v1`, `m7_post_v1_r2`, `m7_post_v2` and `m7_reviewed` produce
**byte-identical answers** (0 differing rows across all 182). Latency and the newly
recorded `generative_model` field differ. The decoding path is deterministic
(`num_beams=4`, no sampling), so this is expected; it also confirms that the
producer classification added in `v2` is the only schema change.

`m7_reviewed` was run after the independent review and its fixes (truncation
guard, ambiguous-ordinal abstention, heading recognition, verifier narrowing).
Compared with `m7_post_v2`, 36 of 182 records differ and **every difference is in
`generative_warnings`**: the list warning now names the heading and the item
position, and the table warning no longer prints `of the table in evidence`. No
answer, EM/F1 flag, producer or verification status changed — the reviewed fixes
close production failure modes that the frozen benchmark does not contain (its
evidence blocks are never truncated and its list questions never carry two
ordinals), which is why the measured aggregate is unchanged.

## 5. Mark-extent runs

| Format | EM | F1 | Unanswerable spurious | Unsupported-claim rate | p95 |
|---|---:|---:|---:|---:|---:|
| 5 | 0.5786 | 0.6518 | 2/42 | 0.0985 | 613 ms |
| 10 | 0.5786 | 0.6637 | 2/42 | 0.0821 | 617 ms |
| 15 | 0.4929 | 0.6007 | **4/42** | 0.0979 | 1268 ms |

The 5- and 15-mark runs were repeated after the review (`…_m7_reviewed_fmt5`,
`…_m7_reviewed_fmt15`): **0 of 182 answers differ and 0 EM flags differ** at either
format, and every metric above is reproduced exactly; only latency moved. The
5-mark p95 quoted above is from the post-review repeat, the 15-mark one from the
post-review repeat as well.

The 5-mark run gains the full table/list benefit because neither structured
reader is mark-elaborated. The 15-mark drop is the pre-existing mark-extent
effect reported in Mission 6 (the longer depth cue changes decoding on two
unanswerable rows); it was reproduced there by direct generation and is not caused
by this mission.

## 6. Claim-evaluation comparability

`answer_claims_v2` was annotated against the **Mission 5** answers, so its F1 is
**not** a measurement of Mission 7 answers and is not reported as one.

Two valid measurements were made instead:

1. **Verifier unchanged on the annotated population.** Re-running the claim
   evaluation with the Mission 7 verifier (`..._m7_v2`, and again with the
   post-review verifier in `..._m7_reviewed`) reproduces Mission 5 exactly —
   lexical support F1 **0.8889** (P 0.9333 / R 0.8485), relations **0.9767**,
   false accepts 4 / 0, false rejects 10 / 3, non-claim acceptance 28/28 and
   20/28. The `_list_entity_alignment` addition therefore changes nothing on the
   frozen annotated claims.
2. **Production-verifier claim counts on the new answers** — claims 134,
   supported 123, unsupported 11, citation accuracy 0.9179. These are the same
   deterministic verifier definitions the benchmark has always reported; they are
   not human-annotated.

No `answer_claims_v3` was created: labelling new claims requires a human
annotator, and generating the labels from the model under test would be
fabrication.

## 7. Rejected interventions (measured)

| Candidate | Measurement | Decision |
|---|---|---|
| Deterministic boundary reader for the 8 boundary refusals + 1 wrong answer | in 6 of 9 rows the second named section is absent from the evidence; in the rest the reference is the last value before the heading twice and the first value after it once | REJECTED — no consistent rule |
| Withhold answers containing no digit when the question asks for a quantity | 4 rows would become abstentions (3 `revenue` for "what value is given for metric", 1 `percent`); 0 EM gained, 0.0036 F1 lost; the 3 correct rows it would touch are table answers | REJECTED — hides a generation failure |
| Strip `$`/unit from answers to match reference strings | 11 rows would flip to exact with no change in meaning | REJECTED — metric gaming |
| Return the section heading for the 7 section-title rows | matches an inconsistent reference | REJECTED |
| Regenerate claim annotations | requires human annotation | REJECTED — fabrication |
