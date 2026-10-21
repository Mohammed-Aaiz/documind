# Claim verification evaluation — lexical baseline vs relation-aware verifier

- Run: `claim_verification_2026-10-17` (`dev` split)
- Started: 2026-10-17T18:21:12.207704+00:00
- Dataset: `evaluation/datasets/claim_verification_v1.py` — 52 examples (29 dev / 23 test), synthetic
- Latency per claim: baseline 1.0847 ms, relations 1.9388 ms

## Claim-level metrics

| Metric | Lexical baseline | Relation verifier |
|---|---|---|
| Support precision | 0.400 | 0.750 |
| Support recall | 0.545 | 0.818 |
| Support F1 | 0.462 | 0.783 |
| Contradiction precision | n/a | 1.000 |
| Contradiction recall | 0.000 | 0.667 |
| Contradiction F1 | 0.000 | 0.800 |
| False-accept rate | 0.500 | 0.167 |
| False-reject rate | 0.455 | 0.182 |
| Insufficient-evidence correct (of 6) | 0 | 5 |
| Wrong citations detected (of 2) | 2 | 2 |

## Per category (correct / examples)

| Category | Baseline | Relation |
|---|---|---|
| A | 0/3 | 1/3 |
| B | 0/3 | 2/3 |
| C | 2/3 | 3/3 |
| D | 0/3 | 3/3 |
| E | 2/2 | 2/2 |
| F | 0/2 | 1/2 |
| G | 0/2 | 2/2 |
| H | 0/2 | 1/2 |
| I | 0/2 | 0/2 |
| J | 1/2 | 2/2 |
| K | 1/2 | 2/2 |
| M | 0/3 | 3/3 |

## Mismatches (first 25)

- `A01` (A) gold `SUPPORTED` · baseline `UNSUPPORTED` · relations `SUPPORTED` — Calibration compares instrument readings to a reference and corrects the deviation.
- `A02` (A) gold `SUPPORTED` · baseline `UNSUPPORTED` · relations `INSUFFICIENT_EVIDENCE` — The robot cannot be dispatched while a calibration failure is unresolved.
- `A05` (A) gold `SUPPORTED` · baseline `UNSUPPORTED` · relations `INSUFFICIENT_EVIDENCE` — Calibration begins by parking the robot on a level pad and mounting the reference target.
- `B01` (B) gold `CONTRADICTED` · baseline `UNSUPPORTED` · relations `CONTRADICTED` — The sensor array is recalibrated every 30 days.
- `B02` (B) gold `CONTRADICTED` · baseline `SUPPORTED` · relations `INSUFFICIENT_EVIDENCE` — The sensor array requires calibration every 30 days.
- `B05` (B) gold `CONTRADICTED` · baseline `UNSUPPORTED` · relations `CONTRADICTED` — The power rail operates at 24 volts.
- `C05` (C) gold `SUPPORTED` · baseline `UNSUPPORTED` · relations `SUPPORTED` — Records are kept for 5 years.
- `D01` (D) gold `CONTRADICTED` · baseline `UNSUPPORTED` · relations `CONTRADICTED` — The lidar array requires calibration every 90 days.
- `D02` (D) gold `CONTRADICTED` · baseline `SUPPORTED` · relations `CONTRADICTED` — The lidar array requires calibration every 30 weeks.
- `D05` (D) gold `CONTRADICTED` · baseline `SUPPORTED` · relations `CONTRADICTED` — The power rail operates at 12 amps.
- `F01` (F) gold `CONTRADICTED` · baseline `UNSUPPORTED` · relations `CONTRADICTED` — Elena Vasquez is the CFO.
- `F02` (F) gold `CONTRADICTED` · baseline `SUPPORTED` · relations `INSUFFICIENT_EVIDENCE` — Automated calibration takes about two hours.
- `G01` (G) gold `CONTRADICTED` · baseline `SUPPORTED` · relations `CONTRADICTED` — Calibration can correct a physically damaged lidar unit.
- `G02` (G) gold `CONTRADICTED` · baseline `SUPPORTED` · relations `CONTRADICTED` — A failed calibration check does not block the robot from dispatch.
- `H01` (H) gold `INSUFFICIENT_EVIDENCE` · baseline `UNSUPPORTED` · relations `INSUFFICIENT_EVIDENCE` — A worn bearing causes repeated failures on the same axis.
- `H02` (H) gold `INSUFFICIENT_EVIDENCE` · baseline `UNSUPPORTED` · relations `SUPPORTED` — Firmware updates cause collisions, so the interval is shortened.
- `I01` (I) gold `CONTRADICTED` · baseline `SUPPORTED` · relations `SUPPORTED` — Manual calibration is cheaper than automated calibration.
- `I02` (I) gold `CONTRADICTED` · baseline `SUPPORTED` · relations `SUPPORTED` — Automated and manual calibration take about the same time.
- `J01` (J) gold `SUPPORTED` · baseline `UNSUPPORTED` · relations `SUPPORTED` — The lidar array is calibrated every 30 days and the records are kept for five years.
- `K03` (K) gold `INSUFFICIENT_EVIDENCE` · baseline `UNSUPPORTED` · relations `INSUFFICIENT_EVIDENCE` — The lidar array requires calibration every 30 days.
- `M01` (M) gold `INSUFFICIENT_EVIDENCE` · baseline `UNSUPPORTED` · relations `INSUFFICIENT_EVIDENCE` — The board met on 12 March.
- `M02` (M) gold `INSUFFICIENT_EVIDENCE` · baseline `SUPPORTED` · relations `INSUFFICIENT_EVIDENCE` — The system uses TensorFlow.
- `M05` (M) gold `INSUFFICIENT_EVIDENCE` · baseline `UNSUPPORTED` · relations `INSUFFICIENT_EVIDENCE` — The chunk overlap is 64 tokens.

## Notes

- The dataset is synthetic; these numbers are not real-world accuracy, and the
  paraphrase cases share more vocabulary than real paraphrases typically do.
- Contradiction recall for the baseline is structurally zero: it reports only
  'supported' vs 'not supported', with one wrong-entity special case.
- The relation verifier is deterministic (no model, no embedding) and adds
  0.854 ms per claim on this machine.
