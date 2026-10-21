# Mark-depth evaluation — 5 vs 10 vs 15 marks

- Run: `mark_depth_2026-10-17`
- Started: 2026-10-17T18:49:23.242406+00:00
- Model: `google/flan-t5-base`
- Fixture: field-robotics-manual.pdf (synthetic, 6 sections)
- Questions: 5 (definition, factual, process, comparison, explanation)
- Every question is asked at every format; key facts are hand-labelled in the evaluation script.

## Aggregate by format

| Format | Mean words | Mean sentences | Key-fact recall | Distinct sources | Max redundancy | SUPPORTED rate | Latency p50 |
|---|---|---|---|---|---|---|---|
| 5 | 17 | 1.4 | 0.617 | 0 | 0.222 | 1.000 | 1809 ms |
| 10 | 49.4 | 4 | 0.767 | 1.6 | 0.222 | 1.000 | 1859 ms |
| 15 | 73.4 | 6 | 0.933 | 2.4 | 0.238 | 1.000 | 2424 ms |

## Per question

| Question | 5 marks | 10 marks | 15 marks |
|---|---|---|---|
| What is calibration and why is it required? | 16w / facts 0.50 / SUPPORTED | 48w / facts 0.50 / SUPPORTED | 86w / facts 1.00 / SUPPORTED |
| How often is the lidar array calibrated? | 3w / facts 1.00 / SUPPORTED | 25w / facts 1.00 / SUPPORTED | 25w / facts 1.00 / SUPPORTED |
| What are the steps of the calibration procedure? | 40w / facts 0.75 / SUPPORTED | 83w / facts 1.00 / SUPPORTED | 121w / facts 1.00 / SUPPORTED |
| Compare manual and automated calibration. | 17w / facts 0.50 / SUPPORTED | 40w / facts 1.00 / SUPPORTED | 70w / facts 1.00 / SUPPORTED |
| What happens when a calibration check fails, and what are the limits of calibration? | 9w / facts 0.33 / SUPPORTED | 51w / facts 0.33 / SUPPORTED | 65w / facts 0.67 / SUPPORTED |

## Verdict

- Word counts strictly increase with marks: **True**
- Key-fact recall does not decrease with marks: **True**

Depth is produced by adding further evidence sentences with their own citations (see `generation/planning.py`), not by asking the model to write more. A point is only added when it is relevant to the question, does not restate the direct answer, and (for numeric points) mentions the question's own entity.
