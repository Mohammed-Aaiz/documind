# Claim verification evaluation — lexical baseline vs relation-aware verifier

- Run: `claim_verification_2026-10-17` (`test` split)
- Started: 2026-10-17T18:35:43.822975+00:00
- Dataset: `evaluation/datasets/claim_verification_v1.py` — 52 examples (29 dev / 23 test), synthetic
- Latency per claim (after a 10542.9815 ms one-off embedder load): baseline 0.0796 ms, relations 5.7533 ms (max 23.3985 ms)

## Claim-level metrics

| Metric | Lexical baseline | Relation verifier |
|---|---|---|
| Support precision | 0.333 | 1.000 |
| Support recall | 0.444 | 0.778 |
| Support F1 | 0.381 | 0.875 |
| Contradiction precision | n/a | 1.000 |
| Contradiction recall | 0.000 | 0.750 |
| Contradiction F1 | 0.000 | 0.857 |
| False-accept rate | 0.571 | 0.000 |
| False-reject rate | 0.556 | 0.222 |
| Insufficient-evidence correct (of 6) | 0 | 6 |
| Wrong citations detected (of 1) | 1 | 1 |

## Per category (correct / examples)

| Category | Baseline | Relation |
|---|---|---|
| A | 0/3 | 2/3 |
| B | 0/2 | 0/2 |
| C | 2/2 | 2/2 |
| D | 0/2 | 2/2 |
| E | 0/1 | 1/1 |
| F | 0/2 | 2/2 |
| G | 0/2 | 2/2 |
| H | 0/2 | 2/2 |
| I | 1/2 | 2/2 |
| J | 0/2 | 1/2 |
| K | 1/1 | 1/1 |
| M | 0/2 | 2/2 |

## Mismatches (first 25)

- `A03` (A) gold `SUPPORTED` · baseline `UNSUPPORTED` · relations `SUPPORTED` — A technician spends roughly two hours on manual calibration.
- `A04` (A) gold `SUPPORTED` · baseline `UNSUPPORTED` · relations `SUPPORTED` — The reference target supplied by the manufacturer is used for lidar calibration.
- `A06` (A) gold `SUPPORTED` · baseline `UNSUPPORTED` · relations `INSUFFICIENT_EVIDENCE` — Lidar needs recalibrating once a month.
- `B03` (B) gold `CONTRADICTED` · baseline `SUPPORTED` · relations `INSUFFICIENT_EVIDENCE` — Repeated failures on the same axis cause a worn bearing.
- `B04` (B) gold `CONTRADICTED` · baseline `UNSUPPORTED` · relations `INSUFFICIENT_EVIDENCE` — Calibration records are kept for the warranty period of five years.
- `D03` (D) gold `CONTRADICTED` · baseline `SUPPORTED` · relations `CONTRADICTED` — Calibration records are retained for five months.
- `D04` (D) gold `CONTRADICTED` · baseline `SUPPORTED` · relations `CONTRADICTED` — Net income was $142.6 billion.
- `E03` (E) gold `SUPPORTED` · baseline `UNSUPPORTED` · relations `SUPPORTED` — Automated calibration is performed by the docking station.
- `F03` (F) gold `INSUFFICIENT_EVIDENCE` · baseline `SUPPORTED` · relations `INSUFFICIENT_EVIDENCE` — The sensor array requires calibration every 30 days.
- `F04` (F) gold `CONTRADICTED` · baseline `SUPPORTED` · relations `CONTRADICTED` — The lidar array requires calibration every 90 days.
- `G03` (G) gold `CONTRADICTED` · baseline `SUPPORTED` · relations `CONTRADICTED` — The system stores raw audio.
- `G04` (G) gold `CONTRADICTED` · baseline `SUPPORTED` · relations `CONTRADICTED` — Lidar calibration requires the reference target.
- `H03` (H) gold `INSUFFICIENT_EVIDENCE` · baseline `UNSUPPORTED` · relations `INSUFFICIENT_EVIDENCE` — Parking on a level pad prevents calibration drift.
- `H04` (H) gold `INSUFFICIENT_EVIDENCE` · baseline `UNSUPPORTED` · relations `INSUFFICIENT_EVIDENCE` — The five-year retention policy exists to satisfy auditors.
- `I04` (I) gold `INSUFFICIENT_EVIDENCE` · baseline `UNSUPPORTED` · relations `INSUFFICIENT_EVIDENCE` — Manual calibration is always more accurate than automated calibration.
- `J03` (J) gold `SUPPORTED` · baseline `UNSUPPORTED` · relations `INSUFFICIENT_EVIDENCE` — Lidar is calibrated every 30 days, but calibration cannot repair physical damage.
- `J04` (J) gold `INSUFFICIENT_EVIDENCE` · baseline `UNSUPPORTED` · relations `INSUFFICIENT_EVIDENCE` — Lidar calibration is required every 30 days because the records are kept for five years.
- `M03` (M) gold `INSUFFICIENT_EVIDENCE` · baseline `UNSUPPORTED` · relations `INSUFFICIENT_EVIDENCE` — The retention policy is 30 days.
- `M04` (M) gold `CONTRADICTED` · baseline `SUPPORTED` · relations `CONTRADICTED` — The lidar calibration interval is 30 days.

## Notes

- The dataset is synthetic; these numbers are not real-world accuracy, and the
  paraphrase cases share more vocabulary than real paraphrases typically do.
- Contradiction recall for the baseline is structurally zero: it reports only
  'supported' vs 'not supported', with one wrong-entity special case.
- The relation verifier is deterministic apart from the paraphrase fallback:
  similarity is only consulted when the head term and numbers/units already
  agree, and then must clear 0.80. It adds
  5.674 ms per claim on this
  machine (the first call includes loading the shared embedder).
