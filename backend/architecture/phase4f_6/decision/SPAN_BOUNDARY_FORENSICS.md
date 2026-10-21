# Span-Boundary Forensics — is there a principled post-hoc boundary fix?

> **Negative result, honestly reported.** No principled post-hoc selection or
> post-processing change improves span boundaries on the frozen 182-example
> benchmark. Every variant reads the *same logits*; only the selection rule
> differs. **Leaked population — not a generalization result.**

## Method

- Changed: span-selection rule only.
- Held fixed: benchmark, checkpoints, logits, answer-text decoder (fixed in
  Experiment 1), tokenization, metric definitions.
- No training, no weight change, no threshold change, no fitting.
- Benchmark sha256 `1166bf4ff38265c2...` (VERIFIED).

## Limitations

- Population is fully leaked (all 182 examples appear in training_data.jsonl / training_data_v3.jsonl); no generalization claim is possible.
- n = 140 answerable examples, so 1 example = 0.71pp; 1-2 example differences are noise.
- Running inference on CPU with the recorded checkpoints; no training and no weights changed.
- Only post-hoc selection rules are tested. Improving the model's own preference for the right span requires training, which is out of scope here.

## Variants (A0 = production checkpoint, F2 = recorded experiment checkpoint)

| variant | A0 EM | A0 F1 | F2 EM | F2 F1 |
|---|---|---|---|---|
| `R0_recorded_argmax50` | 11/140 (7.86%) | 18.6% | 21/140 (15.0%) | 32.99% |
| `R1_joint_logit50` | 22/140 (15.71%) | 38.71% | 22/140 (15.71%) | 34.56% |
| `R2_joint_logit50_shortest` | 22/140 (15.71%) | 38.71% | 22/140 (15.71%) | 34.56% |
| `R3_joint_logit50_longest` | 22/140 (15.71%) | 38.71% | 22/140 (15.71%) | 34.56% |
| `P0_production_nbest100_prob` | 22/140 (15.71%) | 38.71% | 22/140 (15.71%) | 34.41% |
| `P1_nbest100_logit` | 22/140 (15.71%) | 38.71% | 22/140 (15.71%) | 34.41% |
| `P2_nbest100_logit_shortest` | 22/140 (15.71%) | 38.71% | 22/140 (15.71%) | 34.41% |
| `R4_recorded_argmax50_wholeword` | 11/140 (7.86%) | 18.6% | 21/140 (15.0%) | 32.99% |
| `P4_joint100_wholeword` | 22/140 (15.71%) | 38.71% | 22/140 (15.71%) | 34.41% |

## Boundary taxonomy (A0, 140 answerable)

| variant | EXACT | TOO_LONG | OVERLAP | TOO_SHORT | DISJOINT | EMPTY |
|---|---|---|---|---|---|---|
| `R0_recorded_argmax50` | 11 | 15 | 15 | 4 | 16 | 79 |
| `R1_joint_logit50` | 22 | 28 | 28 | 14 | 48 | 0 |
| `R2_joint_logit50_shortest` | 22 | 28 | 28 | 14 | 48 | 0 |
| `R3_joint_logit50_longest` | 22 | 28 | 28 | 14 | 48 | 0 |
| `P0_production_nbest100_prob` | 22 | 28 | 28 | 14 | 48 | 0 |
| `P1_nbest100_logit` | 22 | 28 | 28 | 14 | 48 | 0 |
| `P2_nbest100_logit_shortest` | 22 | 28 | 28 | 14 | 48 | 0 |
| `R4_recorded_argmax50_wholeword` | 11 | 15 | 15 | 4 | 16 | 79 |
| `P4_joint100_wholeword` | 22 | 28 | 28 | 14 | 48 | 0 |

## Findings (including refuted hypotheses)

### H1_scoring_rule_headroom

- **Claim:** A different principled scoring rule improves span boundaries.
- **Result:** REFUTED
- **Evidence:** For A0, all of R1_joint_logit50, R2_joint_logit50_shortest, R3_joint_logit50_longest, P0_production_nbest100_prob, P1_nbest100_logit, P2_nbest100_logit_shortest produce the identical result (22/140 EM, F1 38.71%, identical taxonomy). The model's argmax pair already maximises every tested score.

### H2_tie_breaking

- **Claim:** Tie-breaking toward shorter/longer spans changes boundaries.
- **Result:** REFUTED — shortest and longest tie-breaks are byte-identical to the untie-broken variant, i.e. ties essentially never occur.

### H3_partial_word_boundaries

- **Claim:** Spans are cut mid-word and can be repaired by whole-word expansion.
- **Result:** REFUTED — 0 partial-word starts (A0) / 0 (F2); 2 spans could be extended at all, with no change in EM, F1 or taxonomy.

### H4_production_headroom

- **Claim:** The production selection rule (20x20 n-best, prob product) leaves boundary quality on the table.
- **Result:** REFUTED — production's rule already matches the exhaustive joint-logit optimum on this benchmark, so production has no selection headroom.

### REAL_FINDING_recorded_protocol

- **Claim:** The recorded Phase 4F runner protocol is a weaker selector than the production rule, on identical logits.
- **Result:** SUPPORTED — but it is a SELECTION fix, not a boundary fix, and it was deliberately NOT applied (see action).
- **Evidence:** A0 recorded argmax chain 11/140 (EM 7.86%, F1 18.6%) vs joint/n-best 22/140 (EM 15.71%, F1 38.71%); F2 21/140 -> 22/140.
- **Action:** NOT applied. Changing the runners' selection rule is a protocol change that would invalidate the comparability of every recorded Phase 4F metric; it needs its own explicit experiment. Production already uses the stronger rule.

- **verdict:** NO_PRINCIPLED_POST_HOC_BOUNDARY_FIX. Boundary quality is set by the model's own logit preference for longer/overlapping spans (TOO_LONG + OVERLAP dominate the non-exact answerable set); no selection or post-processing change tested here moves it. Improving it requires training, which is out of scope.

## Follow-up, 2026-09-28 — the selection experiment this finding asked for

The `REAL_FINDING_recorded_protocol.action` entry above said the runner selection
rule "needs its own explicit experiment". That experiment now exists:
`SPAN_SELECTION_PROTOCOL_EXPERIMENT.{json,md}` (tool:
`e0_diagnostics/tools/span_selection_protocol_experiment.py`).

One clarification, which does not change any number in this file:

- The `R0_recorded_argmax50` variant here uses an **unmasked**
  `argmax(start_logits)`. An audit of all 10 runners showed 9 of them are unmasked,
  so R0 does reproduce the majority recorded protocol (A0 11/140, F2 21/140).
- `phase4f_5f/f2/threshold_experiment/run_threshold_experiment.py` instead masks
  `[CLS]` (`masked_start[0] = -inf`) and is a *different* recorded protocol
  (A0 22/140, F1 39.57%; F2 unchanged at 21/140).
- The `R0` label "recorded runner rule" therefore conflates the two protocols. Both
  are measured side by side in the new experiment, which reports a non-regressing
  before/after for the joint-selection upgrade (A0 11/140 → 22/140, F2 21/140 →
  22/140, 0 examples lost in any comparison).

No number in this file was changed. The variant table and the
`NO_PRINCIPLED_POST_HOC_BOUNDARY_FIX` verdict stand as recorded.
