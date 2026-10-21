# Claim-level verification on actual generated answers

- Run: `answer_claim_evaluation_2026-10-18_m3_pre_v2`
- Started: 2026-10-18T15:54:51.943980+00:00
- Benchmark: `phases\phase4f\phase4f_5d\benchmark\qa_benchmark_v1.jsonl`
- SHA-256: `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` (matches expected: True)
- Dataset: `evaluation/datasets/answer_claims_v2.jsonl` (answer_claims_v2) — 103 claims over 86 questions (75 propositional / 28 non-claim fragments)
- Extraction: generation.planning.split_claims (abbreviation fix 2026-10-18)
- Claim-level metrics below cover 74 questions; a further 12 produced only fragments.
- Evidence: one block per row: the benchmark row's context (what the generator saw)

## Dataset version change

- `answer_claims_v2` supersedes `answer_claims_v1`: 2 records removed, 1 added (li_ab55f3c4 — splitter no longer treats 'Dr.' as a sentence end).
- Removed: `ac_0344c2a5d5` "Dr." (NOT_A_CLAIM); `ac_17daf46833` "Sarah Chen" (SUPPORTED)
- Added: `ac_c411173a36` "Dr. Sarah Chen" (SUPPORTED)

## Annotation protocol (frozen before scoring)

1. Judge only against the benchmark row's `context`; outside knowledge never supports a claim.
2. Read a value-only answer as `<question attribute> = <value>`; the question supplies the attribute.
3. SUPPORTED = the context asserts the claim (paraphrase and elliptical extraction allowed).
4. CONTRADICTED = the context asserts a different specific value for the same entity/attribute; a missing fact is never contradicted.
5. INSUFFICIENT_EVIDENCE = the context neither asserts nor contradicts it; PARTIALLY_SUPPORTED = a compound with at least one wrong element; NOT_A_CLAIM = no proposition.
6. Ambiguity is recorded (17 low, 2 moderate), never forced into a confident label. Annotations are by a single annotator; see the dataset docstring and the architecture record.

## Label distribution

| Label | Count |
|---|---:|
| CONTRADICTED | 5 |
| INSUFFICIENT_EVIDENCE | 2 |
| NOT_A_CLAIM | 28 |
| PARTIALLY_SUPPORTED | 2 |
| SUPPORTED | 66 |

| Category | Count |
|---|---:|
| compound | 5 |
| fragment | 6 |
| heading | 1 |
| sentence | 16 |
| table_render | 22 |
| value_list | 4 |
| value_only | 49 |

Ambiguous annotations: 19 (17 low, 2 moderate).

## Claim-level metrics (propositional claims only)

| Metric | Lexical | Relation-aware |
|---|---:|---:|
| Support precision | 0.932 (0.838–0.973) | 1.000 (0.942–1.000) |
| Support recall | 0.833 (0.726–0.904) | 0.939 (0.854–0.976) |
| Support F1 | 0.880 | 0.969 |
| False-accept rate | 0.444 (0.189–0.733) | 0.000 (0.000–0.299) |
| False-reject rate | 0.167 (0.096–0.274) | 0.061 (0.024–0.146) |
| Binary decision accuracy | 0.800 | 0.947 |
| Contradiction precision | n/a | 0.714 |
| Contradiction recall | 0.000 (0.000–0.434) | 1.000 (0.566–1.000) |
| Contradiction F1 | n/a | 0.833 |
| Exact 3-way labels | 0.733 | 0.920 |

| Insufficient-evidence correct (of 2) | 0 | 2 |
| Partially-supported claims accepted (of 2) | 2 | 0 |
| Claims scored | 75 | 75 |

**Lexical is binary.** It emits SUPPORTED / not-supported; its native wrong-entity reason fired 6 times (gold: 5 supported, 0 contradicted, 1 insufficient, 0 partial). It is not mapped to CONTRADICTED, so lexical contradiction precision/recall are reported as undefined where no positive predictions exist.

### Denominators

| Population | Count |
|---|---:|
| claims_scored | 75 |
| support_positives | 66 |
| support_negatives | 9 |
| gold_contradicted | 5 |
| gold_insufficient | 2 |
| gold_partial | 2 |
| non_claims | 28 |
| answerable_questions | 140 |
| nonempty_answers_lexical | 75 |
| nonempty_answers_relations | 74 |
| unique_claims_lexical | 87 |
| unique_claims_relations | 89 |
| questions_with_claims_lexical | 75 |
| questions_with_claims_relations | 74 |
| claims_with_stated_citation | 1 |

Support precision = TP / (TP + FP), recall = TP / (TP + FN), false-accept = FP / all non-SUPPORTED claims, false-reject = FN / all SUPPORTED claims. PARTIALLY_SUPPORTED counts as not fully supported. A rate with a zero denominator, and an F1 whose precision or recall is undefined, is reported as `n/a`.

### Sensitivity to ambiguous annotations

Excluding the 19 ambiguous claims (56 remain): lexical P 0.978 / R 0.865 / F1 0.918, false accepts 1; relation-aware P 1.000 / R 0.923 / F1 0.960, false accepts 0.

On the 59 claims both runs emitted (removing the answer-set difference from the comparison): lexical P 0.963 / R 0.929 / F1 0.946, false accepts 2; relation-aware P 1.000 / R 0.964 / F1 0.982, false accepts 0.

## Per category (claims / support F1 / false accepts)

| Category | Claims | Lexical F1 | Relations F1 | Lexical FA | Relations FA |
|---|---:|---:|---:|---:|---:|
| compound | 5 | 0.571 | 0.857 | 1 | 0 |
| fragment | 1 | 1.000 | 1.000 | 0 | 0 |
| sentence | 16 | 0.857 | 0.966 | 1 | 0 |
| value_list | 4 | 1.000 | 1.000 | 0 | 0 |
| value_only | 49 | 0.900 | 0.976 | 2 | 0 |

## Per question type (propositional claims)

| Question kind | Claims | Lexical F1 | Relations F1 | Lexical FA | Relations FA |
|---|---:|---:|---:|---:|---:|
| DIRECT_SPAN | 20 | 0.941 | 0.968 | 2 | 0 |
| LIST_ITEM | 6 | 1.000 | 0.800 | 0 | 0 |
| LONG_CONTEXT | 3 | 0.800 | 1.000 | 0 | 0 |
| NUMERIC | 13 | 1.000 | 1.000 | 0 | 0 |
| SECTION_SPECIFIC | 6 | 0.800 | 1.000 | 0 | 0 |
| TABLE_CELL | 19 | 0.609 | 0.963 | 2 | 0 |
| TABLE_ROW | 8 | 0.933 | 1.000 | 0 | 0 |

## Question-to-attribute binding

- Value-only claims scored: 49
- Values held back as bound to another attribute: 3 ({'SUPPORTED': 1, 'CONTRADICTED': 0, 'INSUFFICIENT_EVIDENCE': 2, 'PARTIALLY_SUPPORTED': 0})
- Contradictions established by table binding (the asked column states its own value): 1; by the prose patterns (derivative amount, percentage change): 4
- A value found under a different attribute is abstained on rather than labelled CONTRADICTED unless the asked attribute states its own value. Column choice uses question/header overlap and abstains on ties.

## Answer relevance (what a support verdict cannot see)

- Propositional claims that answer the gold question: 57 of 75
- Claims that do not answer the gold question: 18 (lexical accepted 11, relation-aware accepted 9)
- Fully supported but off-target claims: 9 (lexical accepted 7, relation-aware accepted 9)
- Neither verifier checks whether the claim answers the question: the lexical verifier uses the question only for numeric entity alignment, the relation verifier to attribute and bind a value-only claim. Both accept these off-target claims.

| Off-target example | Gold |
|---|---|
| 200 employees | SUPPORTED |
| 950 | SUPPORTED |
| Revenue exceeds $150M | SUPPORTED |
| $61,250. | SUPPORTED |
| Auth required POST. | SUPPORTED |
| Revenue exceeds $150M. | SUPPORTED |
| Document details | SUPPORTED |
| Auth required. | SUPPORTED |

## Failure classes

- **Generation:** 28 of 103 emitted claims are not claims; 9 fully supported claims do not answer the question; only 75/140 answerable questions receive an answer.
- **Retrieval/evidence:** not measured — every row supplies its context; the 65 empty answers are 49 gate abstentions and 16 withheld answers, not retrieval failures.
- **Verification:** lexical accepts 4/9 negatives and rejects 11/66 positives; relation-aware accepts 0/9 and rejects 4/66, with 5/5 contradictions found and 2 false contradictions.
- **Integration:** corrected; both verifiers now receive the same claim, question and evidence list, and a regression test asserts it.
- **Annotation:** 19 records carry uncertainty; the labels come from a single annotator, so the five CONTRADICTED cases remain the largest uncertainty.

## Non-propositional fragments (excluded from the metrics above)

- 28 table renders / headers / bare tokens were emitted as answers.
- Lexical accepted 28 (1.000); relation-aware accepted 20 (0.714).
- Accepting these is not a truth error (they assert nothing), but it is a generation-quality
  failure: the user receives a table header instead of an answer.

## Citation attribution

- Claims with a stated citation: 1 (of 75 propositional claims)
- Attribution correct: 1 (1.000)
- The benchmark supplies one evidence block per row, so any stated [1] is correct and any other index is not.  This measures whether the generator cites, not whether retrieval supplied the right passage.

## Generation-level consequences (recorded runs, not re-generated)

| Metric | Lexical (production) | Relation-aware |
|---|---:|---:|
| Answer coverage (of 140 answerable) | 75 (0.536) | 74 (0.529) |
| Claims emitted | 87 | 89 |
| Unique claims | 87 | 89 |
| Questions with claims | 75 | 74 |
| Claims per answer | 1.160 | 1.203 |
| Answerability-gate abstentions | 49 | 49 |
| Withheld (unattributable) | 16 | 17 |
| Exact match | 0.129 | 0.129 |
| Token F1 | 0.257 | 0.230 |
| Unsupported-claim rate | 0.198 | 0.165 |
| Citation accuracy | 0.802 | 0.835 |
| Abstention on unanswerable | 0.952 | 0.952 |
| Spurious answer on unanswerable | 0.048 | 0.048 |

- Answers identical in both runs: 117
- Both answered differently: 0
- Only lexical answered: 12 (EM 0.000, F1 0.347)
- Only relation-aware answered: 11 (EM 0.000, F1 0.040)

## Disagreements with the reference labels

| Claim | Gold | Lexical | Relations | ID |
|---|---|---|---|---|
| $3 | CONTRADICTED | UNSUPPORTED | CONTRADICTED | `ac_a4d2fdfed9` |
| 1 | CONTRADICTED | SUPPORTED | CONTRADICTED | `ac_f8ffa771f0` |
| 4 | CONTRADICTED | SUPPORTED | CONTRADICTED | `ac_35b60b3e71` |
| $2 | CONTRADICTED | UNSUPPORTED | CONTRADICTED | `ac_b89c21fb46` |
| growth 9.7 percent | SUPPORTED | SUPPORTED | INSUFFICIENT_EVIDENCE | `ac_1d17c44c4d` |
| 950 | SUPPORTED | UNSUPPORTED | SUPPORTED | `ac_b42c678017` |
| Cash and Equivalents: $2.1 billion Total Debt: $1.8 billion Dividend:  | SUPPORTED | SUPPORTED | INSUFFICIENT_EVIDENCE | `ac_2695a487cf` |
| Dr. Sarah Chen | SUPPORTED | SUPPORTED | INSUFFICIENT_EVIDENCE | `ac_c411173a36` |
| The mean elevation of stations is 342 meters above sea level | SUPPORTED | UNSUPPORTED | SUPPORTED | `ac_c3b8b6d7d4` |
| Licensee shall pay Licensor an annual license fee of $245,000 USD, pay | SUPPORTED | UNSUPPORTED | SUPPORTED | `ac_a91d9a76c3` |
| +4.2%. | SUPPORTED | UNSUPPORTED | SUPPORTED | `ac_a81ea9c816` |
| 100 req/min, 150 requ/min and 500,000 requests. | SUPPORTED | UNSUPPORTED | SUPPORTED | `ac_10e790c73c` |
| 0.0. | CONTRADICTED | UNSUPPORTED | CONTRADICTED | `ac_4b2fdadadf` |
| m/s. | INSUFFICIENT_EVIDENCE | UNSUPPORTED | INSUFFICIENT_EVIDENCE | `ac_c43c696353` |
| 2.1. | SUPPORTED | UNSUPPORTED | SUPPORTED | `ac_e9fa5e40dc` |
| $412.5M | INSUFFICIENT_EVIDENCE | UNSUPPORTED | INSUFFICIENT_EVIDENCE | `ac_285e372f61` |
| 2006 was a year with revenue of $52.1 million and 280 IPO on NASDAQ. | PARTIALLY_SUPPORTED | SUPPORTED | CONTRADICTED | `ac_365da68a6f` |
| $0.0M and $1.6M. | SUPPORTED | UNSUPPORTED | SUPPORTED | `ac_67d36872fb` |
| 1,000 req/min. | SUPPORTED | UNSUPPORTED | SUPPORTED | `ac_01dba26693` |
| km. | SUPPORTED | UNSUPPORTED | SUPPORTED | `ac_baeb3485c8` |
| Year Revenue (USD) was $8.3 million and 45 First telecom contracts. | PARTIALLY_SUPPORTED | SUPPORTED | CONTRADICTED | `ac_33b96b148c` |
| hPa. | SUPPORTED | UNSUPPORTED | INSUFFICIENT_EVIDENCE | `ac_aa241aae9b` |
| Auth required. | SUPPORTED | UNSUPPORTED | SUPPORTED | `ac_79aa6fd173` |

## Latency

- Embedder cold start (one-off): 10805.57 ms
- Lexical: mean 0.0876 ms, max 0.4788 ms per claim
- Relation-aware: mean 5.9005 ms, max 34.2504 ms per claim

## Limitations

- Single annotator (the coding agent); labels are a reference set, not adjudicated human ground truth.
- 86 of 140 answerable questions produced claims; the rest abstained or were withheld, so claim-level metrics do not cover them.
- The benchmark provides one evidence block per row, so citation attribution and multi-passage support cannot be measured.
- Claims are dominated by short value answers (49 value-only, 29 non-propositional fragments), so the set under-represents academic prose.
- The two recorded runs regenerate answers from the same frozen benchmark; no new generation was run for this evaluation.
- Claim extraction is versioned: v1 uses the frozen pre-fix splitter (legacy_split) and keeps the artificial 'Dr.' fragment; v2 uses the corrected production splitter. Population counts and metrics are not sample-comparable across versions.
- The evidence-side sentence splitter (generation.verification.split_sentences) still treats 'Dr.' as a sentence end, which makes the merged v2 claim 'Dr. Sarah Chen' a false rejection for the relation-aware verifier; changing it would alter verification for both datasets.
- No 15-mark relation-verifier benchmark run exists, so the 5/10/15-mark comparison is not available for verifier choice.
- Attribute binding is a heuristic over readable structures only (pipe tables and two prose patterns). It abstains when the asked column cannot be identified; it is not a general table parser.
- The two frozen labels for unit-only table cells disagree with each other: 'm/s' offered as the asked variable is INSUFFICIENT_EVIDENCE, while 'hPa' offered as the asked minimum is SUPPORTED. The verifier follows the protocol and holds both back, so one is counted as a false rejection.
- Latency and the one-off embedder load are measured; process memory and CPU were not instrumented.
