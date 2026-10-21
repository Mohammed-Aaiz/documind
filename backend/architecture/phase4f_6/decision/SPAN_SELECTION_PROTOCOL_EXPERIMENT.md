# Span-Selection Protocol Experiment — argmax chain → joint-score selection

> The recorded Phase 4F runner protocol selects spans with a greedy chain
> (`argmax(start)`, then `argmax(end)` in a 50-token window). This experiment
> measures what changes if it instead maximises `start_logit + end_logit` — the
> standard extractive-QA rule, and the rule production already uses.
> **Every variant reads the same logits. Leaked population — not a
> generalization result.**

## Result (before → after)

| before (recorded) | after (joint, window 50) | checkpoint | EM before | EM after | F1 before → after | answers changed | EM +/− |
|---|---|---|---|---|---|---|---|
| `S0_recorded_argmax_nomask50` | `S1_joint_logit50` | A0 | 11/140 (7.86%) | 22/140 (15.71%) | 18.86% → 38.71% | 79 | +11 / -0 |
| `S0_recorded_argmax_nomask50` | `S1_joint_logit50` | F2 | 21/140 (15.0%) | 22/140 (15.71%) | 32.99% → 34.56% | 15 | +1 / -0 |
| `S0c_recorded_argmax_clsmask50` | `S1_joint_logit50` | A0 | 22/140 (15.71%) | 22/140 (15.71%) | 39.57% → 38.71% | 3 | +0 / -0 |
| `S0c_recorded_argmax_clsmask50` | `S1_joint_logit50` | F2 | 21/140 (15.0%) | 22/140 (15.71%) | 32.99% → 34.56% | 15 | +1 / -0 |
| `S4_recorded_argmax_nomask100` | `S2_joint_logit100` | A0 | 11/140 (7.86%) | 22/140 (15.71%) | 18.86% → 38.71% | 79 | +11 / -0 |
| `S4_recorded_argmax_nomask100` | `S2_joint_logit100` | F2 | 21/140 (15.0%) | 22/140 (15.71%) | 33.63% → 34.41% | 8 | +1 / -0 |

## The recorded fleet was not uniform

The recorded runner fleet is not uniform. 9 of the 10 runners call torch.argmax(start_logits) unmasked; only phase4f_5f/f2/threshold_experiment/run_threshold_experiment.py masks [CLS] (masked_start[0] = -inf).

- Unmasked `argmax(start_logits)`: `phase4f/experiments/run_experiment.py`, `phase4f/experiments/evaluate.py`, `phase4f/experiments/final_gpu_package/evaluation/evaluate.py`, `phase4f/phase4f_5/run_experiment.py`, `phase4f/phase4f_5/evaluation/evaluate.py`, `phase4f/phase4f_5e/run_analysis.py`, `phase4f/phase4f_5f/run_experiment.py`, `phase4f/phase4f_5f/f2/run_f2.py`, `phase4f/phase4f_5f/h1/run_h1.py`
- `[CLS]`-masked: `phase4f/phase4f_5f/f2/threshold_experiment/run_threshold_experiment.py`

Both variants are measured above, so the before/after is against the protocol
that actually produced each recorded number.

## Method

- Changed: **span-selection rule only**.
- Held fixed: benchmark, checkpoints, logits, tokenization, metric definitions,
  and the Experiment-1 answer-text reconstruction.
- No training, no weight change, no threshold change, no fitting.
- Benchmark sha256 `1166bf4ff38265c2...` (VERIFIED).

## Variants

- `S0_recorded_argmax_nomask50` — majority recorded runner protocol (9 of 10 runners): unmasked argmax(start), then argmax(end) in a 50-token window; answer text via reconstruct_answer incl. its decode fallback
- `S0b_recorded_argmax_nomask50_strict` — identical selection; answer text via strict context mapping (shows what the decode fallback adds)
- `S0c_recorded_argmax_clsmask50` — threshold_experiment protocol: [CLS]-masked argmax chain, window 50
- `S4_recorded_argmax_nomask100` — majority recorded rule with the window widened to 100
- `S1_joint_logit50` — joint max(s_logit + e_logit) via answer_span.select_joint_span, window 50
- `S2_joint_logit100` — joint max(s_logit + e_logit) via answer_span.select_joint_span, window 100
- `S3_production_nbest100_prob` — live production rule: 20x20 n-best, softmax_s * softmax_e, window 100

## All variants (EM / F1 over the 140 answerable examples)

| variant | A0 EM | A0 F1 | F2 EM | F2 F1 | A0 off-ctx starts | A0 fallback answers |
|---|---|---|---|---|---|---|
| `S0_recorded_argmax_nomask50` | 11/140 (7.86%) | 18.86% | 21/140 (15.0%) | 32.99% | 107 | 2 |
| `S0b_recorded_argmax_nomask50_strict` | 11/140 (7.86%) | 18.6% | 21/140 (15.0%) | 32.99% | 107 | 0 |
| `S0c_recorded_argmax_clsmask50` | 22/140 (15.71%) | 39.57% | 21/140 (15.0%) | 32.99% | 0 | 0 |
| `S4_recorded_argmax_nomask100` | 11/140 (7.86%) | 18.86% | 21/140 (15.0%) | 33.63% | 107 | 2 |
| `S1_joint_logit50` | 22/140 (15.71%) | 38.71% | 22/140 (15.71%) | 34.56% | 0 | 0 |
| `S2_joint_logit100` | 22/140 (15.71%) | 38.71% | 22/140 (15.71%) | 34.41% | 0 | 0 |
| `S3_production_nbest100_prob` | 22/140 (15.71%) | 38.71% | 22/140 (15.71%) | 34.41% | 0 | 0 |

## Limitations

- Population is fully leaked (all 182 examples appear in training_data.jsonl / training_data_v3.jsonl); no generalization claim is possible.
- n = 140 answerable examples, so 1 example = 0.71pp; 1-2 example differences are noise and are reported as counts.
- Inference is CPU-only against the recorded checkpoints; no training and no weights changed.
- Joint selection maximises the MODEL'S own score, not accuracy, so the EM change is an empirical outcome — the EM gained/lost flips are reported alongside it.
- This is an offline protocol comparison. Applying it to the runners is a frozen-protocol change and is recorded as a decision, not performed silently.

## Findings

### DC1_recorded_fleet_is_not_uniform

- **Claim:** The recorded argmax chain was implemented differently across runners.
- **Result:** CONFIRMED — and it changes the result by ~8pp on A0.
- **Evidence:** A0 unmasked chain 11/140 (EM 7.86%, F1 18.86%) vs [CLS]-masked chain 22/140 (EM 15.71%, F1 39.57%); F2 21/140 (EM 15.0%, F1 32.99%) vs 21/140 (EM 15.0%, F1 32.99%). Off-context starts: A0 107 -> 0; F2 4 -> 4 (of 182).

### H1_selection_rule_is_weaker_than_joint

- **Claim:** The recorded argmax chain is a weaker selector than joint-score selection on identical logits.
- **Result:** SUPPORTED for the majority (unmasked) protocol; REFUTED for the [CLS]-masked protocol on A0.
- **Evidence:** A0 unmasked chain 11/140 (EM 7.86%, F1 18.86%) -> joint 22/140 (EM 15.71%, F1 38.71%) (+11 / -0); A0 [CLS]-masked chain 22/140 (EM 15.71%, F1 39.57%) -> joint 22/140 (EM 15.71%, F1 38.71%). F2 unmasked chain 21/140 (EM 15.0%, F1 32.99%) -> joint 22/140 (EM 15.71%, F1 34.56%) (+1 / -0).
- **Mechanism:** On A0 the recorded chain's weakness is dominated by its UNMASKED start, not by the greedy-vs-joint distinction: the argmax start lands off the context (on [CLS]/question tokens) for 107/182 examples, and the decode fallback then returns question text. Joint selection cannot pick such a span (it requires context-mappable tokens), which is most of the improvement. On F2 the model's start is already on the context, so the gap is 1/140 — noise.

### H2_window_vs_rule

- **Claim:** The 50-token window, not the greedy rule, is what suppresses EM.
- **Result:** REFUTED — widening 50 -> 100 changes no EM at all.
- **Evidence:** Recorded rule at window 100: A0 11/140 (EM 7.86%, F1 18.86%), F2 21/140 (EM 15.0%, F1 33.63%). Joint at window 50: A0 22/140 (EM 15.71%, F1 38.71%), F2 22/140 (EM 15.71%, F1 34.56%). Joint at window 100: A0 22/140 (EM 15.71%, F1 38.71%), F2 22/140 (EM 15.71%, F1 34.41%).

### H3_joint_equals_production

- **Claim:** Joint-logit selection already matches the live production rule.
- **Result:** SUPPORTED
- **Evidence:** A0 joint/window100 22/140 (EM 15.71%, F1 38.71%) vs production 22/140 (EM 15.71%, F1 38.71%); F2 22/140 (EM 15.71%, F1 34.41%) vs 22/140 (EM 15.71%, F1 34.41%).
- **Implication:** Upgrading the runners to joint selection aligns the research protocol with production; it is not a new method.

### H4_decode_fallback

- **Claim:** The decode fallback in reconstruct_answer silently emits text from the question sequence when the recorded chain selects an off-context span.
- **Result:** MEASURED
- **Evidence:** decode_fallback_answers: A0 2 -> 0 ([CLS]-masked) -> 0 (joint); F2 5 -> 0. Strict-mapping non-empty predictions: A0 75/182 vs 77/182 with the fallback.

### decision_on_applying

- **Options:**
  - A. Leave the runners as-is; keep this as a measurement only.
  - B. Upgrade all runners to joint selection as an explicitly labelled protocol v2, re-run the eval-only runners, and keep the v1 recorded numbers labelled as v1 (never overwritten).
- **Recommendation:** B. The upgrade never loses an example on any comparison measured here, removes the off-context/decode-fallback failure mode, aligns the research protocol with the live production rule, and is already implemented and tested in answer_span.select_joint_span. It must be a labelled protocol change with before/after recorded, not a silent edit.
- **Not done here:** No runner was modified by this experiment. The recorded v1 metrics remain the recorded v1 metrics.

- **verdict:** Joint selection is a non-regressing protocol improvement on identical logits. Against the majority (unmasked) recorded runner protocol: A0 11/140 -> 22/140 (+7.86pp, 11 gained / 0 lost), F2 21/140 -> 22/140 (+0.71pp, 1 gained / 0 lost). Against the [CLS]-masked threshold_experiment protocol: A0 EM unchanged at 22/140 (F1 -0.86pp, 3 answers differ), F2 +1 example. It also removes the off-context/decode-fallback failure mode entirely (A0 107 -> 0 off-context starts) and reproduces the live production rule exactly. The window (50 vs 100) is not a factor. Because it is a PROTOCOL change, every recorded Phase 4F EM/F1 becomes non-comparable until re-run under the new rule; it is recorded as a decision above and was NOT applied silently. No generalization claim is possible on this leaked population.

## Before/after flips

### majority recorded runner protocol (unmasked chain) -> joint selection, window 50

`S0_recorded_argmax_nomask50` → `S1_joint_logit50`

**A0** — gained 11, lost 0

_Gained: 11_

| example_id | kind | gold | before | after |
|---|---|---|---|---|
| `tc_e7eb93d1` | TABLE_CELL | 2010 |  | 2010 |
| `ds_9e3b4897` | DIRECT_SPAN | 48.7 percent |  | 48.7 percent |
| `num_2b054635` | NUMERIC | $178 million |  | $178 million |
| `num_1ae85d6b` | NUMERIC | $1.24 billion |  | $1.24 billion |
| `ds_9e814812` | DIRECT_SPAN | 30 days |  | 30 days |
| `num_b5827831` | NUMERIC | $4,900 |  | $4,900 |
| `num_6b7e6d26` | NUMERIC | 12.4 percent |  | 12.4 percent |
| `num_4c6d491a` | NUMERIC | $425 million |  | $425 million |
| `num_930d8bfe` | NUMERIC | 120 |  | 120 |
| `tc_78ac63a0` | TABLE_CELL | $0.0M |  | $0.0M |
| `tc_e8b586d5` | TABLE_CELL | 2001 |  | 2001 |

_Lost: 0_

**F2** — gained 1, lost 0

_Gained: 1_

| example_id | kind | gold | before | after |
|---|---|---|---|---|
| `tc_0ddace85` | TABLE_CELL | $178.0M | 150M | $178.0M |

_Lost: 0_

### threshold_experiment protocol ([CLS]-masked chain) -> joint selection, window 50

`S0c_recorded_argmax_clsmask50` → `S1_joint_logit50`

**A0** — gained 0, lost 0

_Gained: 0_

_Lost: 0_

**F2** — gained 1, lost 0

_Gained: 1_

| example_id | kind | gold | before | after |
|---|---|---|---|---|
| `tc_0ddace85` | TABLE_CELL | $178.0M | 150M | $178.0M |

_Lost: 0_

### unmasked chain at window 100 -> joint at window 100

`S4_recorded_argmax_nomask100` → `S2_joint_logit100`

**A0** — gained 11, lost 0

_Gained: 11_

| example_id | kind | gold | before | after |
|---|---|---|---|---|
| `tc_e7eb93d1` | TABLE_CELL | 2010 |  | 2010 |
| `ds_9e3b4897` | DIRECT_SPAN | 48.7 percent |  | 48.7 percent |
| `num_2b054635` | NUMERIC | $178 million |  | $178 million |
| `num_1ae85d6b` | NUMERIC | $1.24 billion |  | $1.24 billion |
| `ds_9e814812` | DIRECT_SPAN | 30 days |  | 30 days |
| `num_b5827831` | NUMERIC | $4,900 |  | $4,900 |
| `num_6b7e6d26` | NUMERIC | 12.4 percent |  | 12.4 percent |
| `num_4c6d491a` | NUMERIC | $425 million |  | $425 million |
| `num_930d8bfe` | NUMERIC | 120 |  | 120 |
| `tc_78ac63a0` | TABLE_CELL | $0.0M |  | $0.0M |
| `tc_e8b586d5` | TABLE_CELL | 2001 |  | 2001 |

_Lost: 0_

**F2** — gained 1, lost 0

_Gained: 1_

| example_id | kind | gold | before | after |
|---|---|---|---|---|
| `tc_0ddace85` | TABLE_CELL | $178.0M | 150M | $178.0M |

_Lost: 0_

