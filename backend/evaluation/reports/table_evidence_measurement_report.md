# Table-Row Evidence Measurement — Phase 4

Production-behaviour measurement of the Phase 3 compact table-row evidence band on the teacher-demo document. **Not** a statistically powered research claim: five questions, one document.

## Experiment

- Control: `DOCUMIND_TABLE_EVIDENCE=0`
- Treatment: `DOCUMIND_TABLE_EVIDENCE=1`
- Teacher-demo PDF: `Field_Robotics_Deployment_and_Maintenance_Report.pdf`
- Questions: Q1, Q2, Q3, Q4, Q5
- Database: isolated local PostgreSQL+pgvector (revision 007)
- Production path: `brain.adapters.retrieval_adapter` → `context_adapter` → `qa_adapter`

## Per-question results

| Q | Gate | Rows | In ctx | Context identical | Control ans | Treatment ans | Exact Δ | Result |
|---|---|---|---|---|---|---|---|---|
| Q1 | CLOSED | 0 | 0 | True | `reference rig` | `reference rig` | +0 | unchanged |
| Q2 | OPEN | 1 | 1 | False | `every 250 operating hours` | `every 250 operating hours` | +0 | unchanged |
| Q3 | CLOSED | 0 | 0 | True | `battery rail` | `battery rail` | +0 | unchanged |
| Q4 | CLOSED | 0 | 0 | True | `four minutes` | `four minutes` | +0 | unchanged |
| Q5 | CLOSED | 0 | 0 | True | `12 metres per second` | `12 metres per second` | +0 | unchanged |

## Retrieval integrity

- RRF (K/weights): 60 / 0.7 / 0.3 (unchanged: True)
- RRF_CHANGED = False
- RANKED_CHUNKS_CHANGED = False
- TABLE_ROWS_ADDED = True
- STRUCTURE_TAIL_CHANGED = False
- table rows in RRF: 0
- provenance gaps: 0
- table rows truncated: False

## Context budget

- Q1: budget 360, ranked 187→187 tok, table row 0 tok, tail 173→173 tok, total 360→360 tok, omitted row tok 0
- Q2: budget 362, ranked 266→266 tok, table row 44 tok, tail 93→50 tok, total 359→360 tok, omitted row tok 0
- Q3: budget 357, ranked 174→174 tok, table row 0 tok, tail 183→183 tok, total 357→357 tok, omitted row tok 0
- Q4: budget 362, ranked 272→272 tok, table row 0 tok, tail 87→87 tok, total 359→359 tok, omitted row tok 0
- Q5: budget 367, ranked 150→150 tok, table row 0 tok, tail 217→217 tok, total 367→367 tok, omitted row tok 0

## Metrics

- Gate-open: 1/5 (0.2)
- Table-row admission: 1/5 (0.2)
- QA-context admission: 1/5 (0.2)
- Avg selected rows: 0.2; avg row tokens: 44.0
- Ranked-chunk identity: 5/5 (1.0)
- Context identity: 4/5 (0.8)
- Exact match: control 5/5, treatment 5/5
- Improvements: 0; regressions: 0; harmful regressions: 0; unchanged: 5

## Determinism

- Run 1 == Run 2: True
- Control SHA-256: `904ef93891032443d4fc0affd06959612d3b10984a5aa2f9ec12d1f3b9d4df79`
- Treatment SHA-256: `c488d89f22ea0ba1fb4b6bc31046e06e1d37fd977c232b2b0496649c4b7e5912`
- Analysis SHA-256: `c2d5ab5ed4d662294adefcc4c7b6128226a232a5cf9d633e9e741ee2e28c8b8c`

## Limitations

- This is a five-question teacher-demo measurement on one document; it is not a statistically powered claim, not evidence of general table reasoning, and not proof of production-wide improvement.
- Measured on an isolated local PostgreSQL+pgvector database with the production schema (migration 007). The remote Timescale database was not migrated and the running backend was not restarted, so this is not a measurement of the live remote stack.
- Q2's decoded answer depends on the local extractive DistilBERT QA model; the Phase 3/4 guarantee is that the compact row reaches the QA *input* whole and within budget, which is measured directly.

## Final status: PASS
