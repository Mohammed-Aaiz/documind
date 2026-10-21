# DocuMind — claim-level verification on actual generated answers (2026-10-18)

Status: **EVALUATED — production default unchanged (lexical retained)**.
Owner of the record: COORDINATOR. Evaluation artifacts: EVALUATION_AGENT.
Production code changed by this mission: **none**.

> **Current run:** `answer_claim_evaluation_2026-10-18_r2` (corrected methodology;
> see the addendum in §11). §3–§10 record the first pass and are preserved; §11
> supersedes the lexical contradiction row and documents the corrected protocol.

## 1. Mission and verdict

The synthetic claim evaluation (2026-10-17) could not answer the question that
matters: do the verifiers judge the claims the generator *actually emits*? This
mission builds that measurement on the frozen benchmark, annotates every claim
the generator produced, scores both verifiers against the same reference labels,
and measures the generation-level consequences from the already-recorded runs.

**Verdict: complete, with one material limitation — the reference labels come
from a single annotator (this coding agent), not from adjudicated human
annotation.** The numbers are reproducible and internally checked; they are not
a claim of human-agreement ground truth.

**Decision: RETAIN the lexical verifier as the production default.** The
relation-aware verifier has better support recall/F1, but on real generated
claims it accepts **7 of 9** unsupported claims versus **4 of 9** for the lexical
verifier (on the 59 claims both runs emitted: 3 vs 2), detects **0 of 5**
contradictions, and adds 3 false contradictions. For a faithfulness gate, a false
accept is the safety-critical error, so higher F1 does not justify enabling it.
This is consistent with — and now explains — the recorded token-F1 regression
(0.257 → 0.230). The counts are small and the confidence intervals overlap; the
decision is to keep the default, not to declare the candidate proven worse.

## 2. Population and dataset

| Item | Value |
|---|---|
| Frozen benchmark | `backend/phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` (182 rows, 140 answerable) |
| SHA-256 before and after | `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` (matches expected) |
| Answer source | recorded 10-mark runs `generation_benchmark_2026-10-17_fmt10` (lexical) and `..._fmt10_relations_r5` (relation-aware) |
| Claims | **104** unique claims over **86** questions (union of both runs; 74 in both, 14 lexical-only, 16 relations-only) |
| Propositional claims scored | **75** over **74** questions (66 SUPPORTED, 5 CONTRADICTED, 2 INSUFFICIENT, 2 PARTIALLY_SUPPORTED); 12 questions produced only fragments |
| Non-claim fragments | **29** (22 table renders, 7 fragments/headings) — excluded from truth metrics, reported separately |
| Evidence per claim | the benchmark row's `context`, one block — exactly what the generator saw; retrieval not measured |
| Annotation protocol | `backend/evaluation/datasets/answer_claims_v1.py` (frozen; three-way labels + partial + not-a-claim) |
| Reference file | `backend/evaluation/datasets/answer_claims_v1.jsonl` |
| Runner | `backend/evaluation/experiments/run_answer_claim_evaluation.py` |
| Report (first pass; superseded by §11) | `backend/evaluation/reports/answer_claim_evaluation_2026-10-18/` |
| Tests | `backend/tests/unit/evaluation/test_answer_claim_evaluation.py` (24; first pass had 20) |

Annotation rules, in brief: judge only against the row context; read a value-only
answer as `<question attribute> = <value>`; a different specific value for the
same entity/attribute is CONTRADICTED, a missing fact is INSUFFICIENT; a compound
with a wrong element is PARTIALLY_SUPPORTED; a header/render/token with no
proposition is NOT_A_CLAIM; record `answers_question` separately from truth.
Ambiguity is recorded (17 low, 2 moderate), not forced away.

## 3. Claim-level results (75 propositional claims)

| Metric | Lexical (production) | Relation-aware |
|---|---:|---:|
| Support precision | 0.932 (95% CI 0.838–0.973) | 0.900 (0.808–0.951) |
| Support recall | 0.833 (0.726–0.904) | **0.955** (0.875–0.984) |
| Support F1 | 0.880 | **0.926** |
| False-accept rate | **0.444** (4/9; CI 0.189–0.733) | 0.778 (7/9; CI 0.453–0.937) |
| False-reject rate | 0.167 (11/66; CI 0.096–0.274) | **0.045** (3/66; CI 0.016–0.125) |
| Binary decision accuracy | 0.800 | **0.867** |
| Contradiction P / R / F1 | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.000 |
| Contradiction false positives | 6 | 3 |
| Insufficient-evidence correct | 0/2 | 0/2 |
| Partially-supported accepted | 2/2 | 0/2 |
| Exact 3-way labels | 0.733 | 0.840 |
| Mean latency per claim | 0.10 ms | 6.0 ms (max 30.4 ms) |

The support F1 difference is **recall**, not precision: the lexical verifier
rejects 11 supported claims (bare units such as `km.`, `hPa.`, `2.1.`, `+4.2%`,
and long compound sentences), while the relation verifier accepts them but also
accepts 7 unsupported claims. Neither verifier gets a single contradiction right:
the lexical verifier has no contradiction label (of its 6 "contradictions", 5 are
supported multi-entity sentences and 1 is an insufficient-evidence claim), and the
relation verifier's number check accepts every wrong-value answer in this set.

Two sensitivity checks are recorded in `summary.json`. Excluding the 19 ambiguous
annotations: lexical P 0.978 / R 0.865 / F1 0.918, FA 1; relation P 0.926 /
R 0.962 / F1 0.943, FA 4. Restricted to the 59 claims both runs emitted (so the
answer-set difference cannot drive the result): lexical P 0.963 / R 0.929 /
F1 0.946, FA 2; relation P 0.949 / R 1.000 / F1 0.974, FA 3. The relation
advantage shrinks and the false-accept gap narrows to 3 vs 2, but it does not
reverse; the 0/5 contradiction result is unchanged.

## 4. Error analysis — the failure modes that dominate

### 4.1 All seven relation false accepts are value-only claims

The relation verifier scores a bare value as supported whenever the passage
contains that number/unit in **any** role. The question *is* passed and is used
by `_claimed_entity_ok` for value-only attribution, but that check binds only the
**entity**, not the **attribute**: `0.0` as the mean, `m/s` as the variable and
`$412.5M` as the division all pass because the row's entity (Wind Speed,
Enterprise Solutions) is present. For the remaining cases (`$3`, `$2`, `1`, `4`)
the entity check fails and the numeric/overlap fallback accepts anyway. In this
benchmark that is exactly the dominant error:

| Claim | Evidence | Reference | Relation | Why |
|---|---|---|---|---|
| `$3` | Net income $142.6 million, or $3. | CONTRADICTED | SUPPORTED | $3 is the start of a per-share figure, not the reported monetary value |
| `1` | 1 percent from 20.3 percent | CONTRADICTED | SUPPORTED | the metric value is 20.3; 1 is a change |
| `4` | 4 percent … 4.2 percent increase | CONTRADICTED | SUPPORTED | the asked rate is 4.2, not the adjacent 4 |
| `$2` | $118.2 million, or $2. | CONTRADICTED | SUPPORTED | per-share fragment, not the reported value |
| `0.0.` | Mean 4.2; Min 0.0 | CONTRADICTED | SUPPORTED | value taken from the wrong column |
| `m/s.` | Variable Wind Speed; Unit m/s | INSUFFICIENT | SUPPORTED | unit offered as the asked variable |
| `$412.5M` | Division Enterprise Solutions, revenue $412.5M | INSUFFICIENT | SUPPORTED | revenue offered as the asked division |

The lexical verifier rejects three of these (`$3`, `$2`, `0.0.`) for the wrong
reason (low overlap), which still avoids the false accept; it accepts `1`, `4`
and both partial compounds. Low overlap is not a correctness signal, but here it
happens to be safer than any-number matching.

### 4.2 False contradictions on table-derived sentences

The relation verifier marks 3 supported/partial claims CONTRADICTED: two
garbled table-row sentences (`… 280 IPO on NASDAQ`, `… 45 First telecom
contracts`) and `/auth/token, Obtain access token.`. Declaring a supported answer
"contradicted" is worse for trust than calling it unsupported, so this is a real
regression, not a label quibble: the user is told the document says otherwise.

### 4.3 Neither verifier checks answer relevance

9 fully supported claims do **not** answer the question (the 2005 headcount
instead of 2010, a milestone instead of the employees, an auth flag instead of
the method). The lexical verifier accepts 7/9 and the relation verifier 9/9.
Both use the question only narrowly — lexical for numeric entity alignment,
relations for value-only attribution — and neither asks whether the claim fills
the requested slot. This is a larger source of wrong answers than unsupported
claims in this population.

### 4.4 Generation defects, not verification defects

- **29 of 104 emitted claims (28%) are not claims**: table headers/rows rendered
  as prose (`Variable | Unit | Min | Max | Mean | Missing %`), bare units, a
  heading. The lexical verifier accepts all 29; the relation verifier 21.
- Only **75 of 140 answerable questions (53.6%)** produce a non-empty answer;
  49 are answerability-gate abstentions and 16 are withheld as unattributable.
  The relation verifier answers **one fewer** (74) and emits two more claims.
- The 12 answers only the lexical run produced carry F1 0.347; the 11 answers
  only the relation run produced carry F1 0.040. The candidate verifier removes
  more useful content than it adds.

## 5. Generation-level consequences (recorded runs, unchanged benchmark)

| Metric | Lexical | Relation-aware |
|---|---:|---:|
| Answer coverage (of 140) | 75 (0.536) | 74 (0.529) |
| Claims emitted | 88 | 90 |
| Exact match | 0.129 | 0.129 |
| Token F1 | **0.257** | 0.230 |
| Unsupported-claim rate | 0.198 | **0.165** |
| Citation accuracy | 0.802 | **0.835** |
| Abstention / spurious (42 unanswerable) | 0.952 / 0.048 | 0.952 / 0.048 |

The unsupported-claim rate falls because the relation verifier withholds or
rejects more claims — including supported ones. It does not improve answer
quality, removes a small amount of useful content, and **reduces answer coverage
by one** (75 → 74 of 140). No generation was re-run for this mission; these are
the recorded runs, and their answers are deterministic.

## 6. What this changes in the prior conclusion

The synthetic held-out numbers (false-accept 0.571 → 0.000) **do not transfer**.
On real answers the direction reverses: lexical 0.444, relation 0.778. The
synthetic set was built from deliberately constructed claim/evidence pairs with
one relevant passage; it did not contain value-only answers whose number appears
elsewhere in the passage, nor table renders. Those are precisely the real
population (49/75 value-only; 29 non-claims). The earlier decision to keep the
candidate opt-in was correct, and this measurement now supplies the missing
mechanism rather than a lower benchmark number alone.

## 7. Decision

1. **RETAIN** `generation/verification.py` as the production default.
2. Keep `DOCUMIND_VERIFIER=relations` experimental and opt-in.
3. Do **not** tune the relation verifier's thresholds on this dataset: the labels
   are single-annotator and the set is small; that would trade one overfit for
   another.
4. Do **not** change the model (out of scope; no new model downloaded).
5. Next improvement target: **integration — question-aware verification of
   value-only claims**, not retrieval and not another model. The relation
   verifier already accepts a `question` argument; binding a bare value to the
   asked attribute would address 7/7 of its false accepts. The generation side
   needs the complementary fix (emit attributed sentences, not table renders),
   but that is a larger change and must not be bundled with a verifier switch.

**Single safest next action:** extend the experimental relation verifier's
question binding from the entity check to the asked **attribute** (a bare value
must be the value of the asked column/relation, not merely a value in the same
row), and make the numeric/overlap fallback subject to it; add regression tests
for the seven cases above, then re-run `run_answer_claim_evaluation.py` and the
frozen benchmark before any enablement discussion.

## 8. Validation and integrity

Commands (from `backend/`, this machine, 2026-10-18):

| Command | Result |
|---|---|
| `./venv/Scripts/python.exe -m evaluation.experiments.run_answer_claim_evaluation` | exit 0; report written; benchmark hash verified |
| `./venv/Scripts/python.exe -m pytest -q tests/unit/evaluation/test_answer_claim_evaluation.py` | 20 passed, exit 0 |
| `./venv/Scripts/python.exe -m pytest -q tests/unit` (first pass) | **1518 passed, 23 skipped, exit 0** (77.6 s; the 23 skips are the pre-existing environmental skips) |
| `./venv/Scripts/python.exe -m compileall -q evaluation` | exit 0 |

**Independent audit correction.** A separate read-only reviewer (a different
model instance, not a second annotator) checked the artifacts and found that the
runner's relation-verifier call initially omitted the `question` argument, while
production passes it (`generation/verification.py` → `verify_answer_claims`).
The defect was fixed, the runner re-run, and **the metrics were unchanged**: the
question-aware value branch is bypassed by the numeric/overlap branches for all
seven cases, which is itself part of the finding above. The same audit found the
stale latency figures, the "coverage unchanged" wording, the wrong-column rule
ambiguity and the off-by-taxonomy fragment description; all were corrected, and
the ambiguity sensitivity is now part of `summary.json`.

Integrity: benchmark SHA-256 unchanged before/after; historical reports and the
prior claim-verification artifacts untouched; no database access, no migration,
no model download, no network service, no production code change, nothing
committed or pushed. Git HEAD was `6baaa2a` before and after. New files:
the dataset (`.py` + `.jsonl`), the runner, the tests, this record, the report
directory, and an appended section in `backend/evaluation/README.md` plus
`DOCUMIND_PROJECT_CONTEXT.md` §0.8.6.

## 9. Limitations

- **Single annotator, no independent adjudication.** 19 claims carry explicit
  uncertainty; 2 are moderate (temporal ambiguity of "the count"). The five
  CONTRADICTED labels are the crux of the relation verifier's false-accept gap:
  if a second annotator reclassified them as INSUFFICIENT the false-accept count
  would be unchanged (both are negatives), but if they were treated as SUPPORTED
  the relation false-accept count would fall from 7 to 2 and lexical from 4 to 2
  (a tie). That reclassification would contradict the evidence (each states a
  value the passage does not give for the asked attribute), but it is the
  sensitivity a second annotator must check.
- **86 of 140 answerable questions** produced claims — the other 54 abstained or
  were withheld, so claim-level metrics say nothing about them.
- **One evidence block per row.** Citation attribution and multi-passage support
  cannot be measured; only 1 of 75 propositional claims even states a citation.
- **Answer population is short and value-heavy** (49 value-only): these results
  describe Flan-T5-base's 10-mark output on this benchmark, not rich academic
  prose or the 15-mark path.
- **Both verifiers ran against already-recorded answers**, with no new
  generation; deterministic decoding makes this reproducible, but it does not
  test a future model.
- **No independent Verifier agent executed.** The repository's agents are
  instruction files, not executable orchestrators. The VERIFIER role was applied
  by the same coding agent; the only independent check was a read-only
  consistency auditor (a different model instance), which is not a second
  annotator and does not satisfy an independent human review.

## 10. Agent execution record (honest)

| Repository agent | Contract | What actually happened |
|---|---|---|
| COORDINATOR | plan, ownership, docs | scoped the mission, kept production untouched, wrote this record and §0.8.6 |
| EVALUATION_AGENT | datasets, runners, reports | built `answer_claims_v1`, the runner and the report; verified benchmark hash |
| VERIFIER | read-only truth check | applied by the same agent (not independent): integrity checks fail closed, labels checked against recorded answers |
| AI_AGENT | generation/verification analysis | diagnosed value-only acceptance (the question is passed, but numeric/overlap branches bypass its binding) and the table-render population; proposed no production change |
| BACKEND_AGENT | integration/config | inspected only; no backend change was necessary or made |
| TEST_AGENT | tests | added 20 regression tests for dataset integrity, metric honesty and the question-passing invocation contract |
| SECURITY_AGENT | untrusted text / artifacts | reviewed that context text is used only as data (no execution/logging), no secrets or user documents are in the artifacts, and no new egress |
| DATABASE_AGENT | DB access | not used: the benchmark path is file-based and no persistence was touched |
| FRONTEND_AGENT | UI | not used: no frontend requirement was demonstrated |

No separate agent process was launched; claiming otherwise would be false.

## 11. Addendum — corrected-methodology run (2026-10-18_r2)

This addendum is append-only; it does not rewrite the first pass. The mission's
review required four methodology corrections, all of which were applied and
re-measured. The first-pass report (`answer_claim_evaluation_2026-10-18`) is
preserved for comparison; the current report is
`answer_claim_evaluation_2026-10-18_r2`.

### 11.1 What changed

1. **Equivalent inputs are now structural, not conventional.** A single
   `verify_both(claim, context, question)` builds **one** evidence list and
   passes that same object to `check_claim` and `verify_claim`. A regression test
   monkeypatches both production functions and asserts the claim, question and
   evidence-block object are identical (`is`) across the two calls. The runner
   still calls the production functions, not test doubles.
2. **The lexical verifier is no longer given an invented contradiction label.**
   Its output is binary (SUPPORTED / not-supported). The native "different entity"
   reason fired 6 times (5 on SUPPORTED gold, 1 on INSUFFICIENT gold); it is
   reported as `lexical_entity_signals`, not mapped to CONTRADICTED. Its
   contradiction precision and F1 are therefore `n/a` (no positive predictions),
   and recall is 0/5.
3. **Undefined metrics are undefined.** Any rate with a zero denominator and any
   F1 whose precision or recall is undefined is emitted as `None`/`n/a`, never
   `0.0`. A `denominators` block in `summary.json` states every population
   (support positives 66, negatives 9, contradicted 5, insufficient 2, partial 2,
   non-claims 29, answerable 140, non-empty answers 75/74, unique claims 88/90,
   questions with claims 75/74, cited claims 1). The report defines every formula.
4. **Claim-extraction defects were reproduced, not patched mid-evaluation.**
   `split_claims` splits after honorifics/initials (`Dr. Sarah Chen` -> `Dr.` +
   `Sarah Chen`; `U.S.`/`e.g.` likewise). This affected exactly **1 of 86
   questions and 2 of 104 claims** (the `li_ab55f3c4` answer). Two strict `xfail`
   tests pin the desired behavior and will fail loudly when fixed. The splitter
   was **not** changed because that would alter the frozen claim population and
   require re-annotation; it is deferred to `answer_claims_v2`.

### 11.2 Corrected claim-level results (75 propositional claims)

| Metric | Lexical | Relation-aware |
|---|---:|---:|
| Support precision | 0.932 (0.838–0.973) | 0.900 (0.808–0.951) |
| Support recall | 0.833 (0.726–0.904) | **0.955** (0.875–0.984) |
| Support F1 | 0.880 | **0.926** |
| False-accept rate | **0.444** (4/9) | 0.778 (7/9) |
| False-reject rate | 0.167 (11/66) | **0.045** (3/66) |
| Binary decision accuracy | 0.800 | **0.867** |
| Contradiction precision | n/a (no positive predictions) | 0.000 (0/3) |
| Contradiction recall | 0.000 (0/5) | 0.000 (0/5) |
| Contradiction F1 | n/a | 0.000 |
| Exact 3-way labels | 0.733 | 0.840 |
| Insufficient-evidence correct | 0/2 | 0/2 |
| Partially-supported accepted | 2/2 | 0/2 |
| Non-claim fragments accepted | 29/29 | 21/29 |
| Mean latency per claim | ≈0.10–0.11 ms | ≈6–7 ms (run max 26–66 ms across reruns; report has the measured run) |
| Answerability-gate abstentions | 49 | 49 |
| Withheld (unattributable) | 16 | 17 |

Native lexical entity signals: 6 (5 on supported claims, 1 on an insufficient
claim). This is *not* a contradiction verdict; it is reported separately, as the
mission requires. All other figures — including the 7/9 vs 4/9 false-accept gap,
the 3 vs 2 gap on the 59 shared claims, the 0/5 contradiction recall, and the
generation-level consequences (coverage 75→74/140, EM 0.129 = 0.129, token F1
0.257→0.230) — are unchanged from §3–§5.

### 11.3 Decision after correction

**RETAIN the lexical verifier as the production default.** The corrected mapping
removes a label the lexical verifier never emitted; it does not change support
accuracy, false accepts, false rejects, coverage, EM or F1. The relation-aware
verifier still: accepts 7/9 negatives (3/2 on the shared 59), detects 0/5
contradictions, raises 3 false contradictions, reduces coverage by one, and
lowers token F1 by 0.027. It remains **experimental / opt-in**.

### 11.4 Validation

| Command | Result |
|---|---|
| `pytest -q tests/unit/evaluation/test_answer_claim_evaluation.py tests/unit/generation/test_generation_planning.py` | **42 passed, 2 xfailed**, exit 0 (24 evaluation + 18 planning tests) |
| `pytest -q tests/unit` | **1525 passed, 23 skipped, 2 xfailed**, exit 0 |
| `compileall -q evaluation` | exit 0 |
| corrected runner | exit 0; new report directory; benchmark hash verified |

Historical reports and the first-pass annotation set are untouched. The two
`xfail` tests are the only non-passing results; they record a confirmed splitter
defect and are not suppressed passing tests.

### 11.5 Remaining risks specific to this addendum

- The annotation set is unchanged, so the `Dr.`/`Sarah Chen` split remains one
  artificial extra claim in the 104; it affects one question and does not move
  the verifier ordering (both verifiers accept `Sarah Chen`; the fragment `Dr.`
  was a non-claim accepted by both).
- The 6 lexical entity signals are evidence that its wrong-entity heuristic
  fires on supported long sentences; this is a known lexical weakness, not a
  contradiction capability.
- No new generation was run, so these results still describe the recorded
  Flan-T5-base answers only.

---

# 12. Addendum (2026-10-18, later) — question-to-attribute binding in the experimental verifier

## 12.1 Mission and status

**Completed for the experimental verifier; production default unchanged.** The
relation-aware candidate now binds a value-only claim to the attribute the
question asks for, and it distinguishes *wrong attribute* from *contradiction*.
The lexical verifier (`generation/verification.py`) is untouched and remains the
production default (`DOCUMIND_VERIFIER` unset → `lexical`, verified in a fresh
process).

## 12.2 Problem and evidence

§11 recorded the failure precisely: the relation-aware verifier's 7 false accepts
were all value-only claims, and 5 of them were *wrong-attribute* accepts that the
frozen reference labels `CONTRADICTED`:

| Claim | Question asks | Evidence states | Reference |
|---|---|---|---|
| `$3` | reported monetary value | net income `$142.6 million, or $3` | CONTRADICTED (per-share derivative) |
| `$2` | monetary value | `$118.2 million, or $2` | CONTRADICTED (per-share derivative) |
| `1` | percentage | `1 percent from 20.3 percent` | CONTRADICTED (change, not the base) |
| `4` | percentage for the metric | `4.2 percent increase` | CONTRADICTED |
| `0.0` | mean for Wind Speed | table row: min `0.0`, mean `4.2` | CONTRADICTED (wrong column) |

Supporting a value because it appears *somewhere* in the passage is the defect;
the question, not the passage, decides which attribute the value must match.

## 12.3 Change

`generation/verification_relations.py` (experimental only):

1. **Table binding.** `_table_rows` parses the benchmark's pipe-table rendering.
   `_asked_column` picks the asked column from header/question overlap; a value
   question (`how much`, `amount`, `value`, `mean`, …) prefers a single
   value-typed column, because the row-key header can otherwise outscore it
   (`Payment Schedule` vs `Amount (USD)`). Ties and zero matches abstain.
2. **Two outcomes, not one.** If the claim's value sits in another column:
   * the asked column states its own different numeric value → `CONTRADICTED`
     (`0.0` offered as the mean, whose cell says `4.2`);
   * it does not → `INSUFFICIENT_EVIDENCE` with an explicit wrong-attribute
     reason (`m/s` offered as the variable, `$412.5M` offered as the division).
   The frozen annotation protocol (§2 of the dataset docstring, rules 4–5) draws
   exactly this line, so the verifier follows it rather than turning every
   misbinding into a contradiction.
3. **Prose binding.** `_prose_attribute_binding` handles the two readable prose
   structures behind the remaining reference contradictions: a derivative amount
   after `or` (`… $142.6 million, or $3`) and a percentage-change sentence
   (`1 percent from 20.3 percent`, `4.2 percent increase`). These *do* state a
   competing value for the asked attribute, so they emit `CONTRADICTED`.
4. **Table cells are not prose negation.** `_is_table_render` stops the negation
   rule from reading an `Auth Required = No` cell as denying the endpoint row,
   which had made `/auth/token, Obtain access token.` a false contradiction
   against the row that supports it.

No prompt, retrieval, model, migration, frontend or production-verifier file was
changed. The frozen benchmark and `answer_claims_v1` are untouched.

## 12.4 Results (same frozen inputs; new run directory)

`evaluation/reports/answer_claim_evaluation_2026-10-18_r4/`. r2 is the corrected
baseline from §11, r3 an intermediate that classified every misbinding as a
contradiction, r4 the final rule set.

| Metric (75 propositional claims) | Lexical (production) | Relations r2 | Relations r3 | Relations r4 |
|---|---:|---:|---:|---:|
| Support precision | 0.932 | 0.900 | 1.000 | **1.000** |
| Support recall | 0.833 | 0.955 | 0.924 | **0.955** |
| Support F1 | 0.880 | 0.926 | 0.961 | **0.977** |
| Support false accepts | 4 | 7 | 0 | **0** |
| Support false rejects | 11 | 3 | 5 | **3** |
| Contradiction precision | n/a | 0.000 | 0.417 | **0.714** |
| Contradiction recall | 0.000 | 0.000 | 1.000 | **1.000** |
| Contradiction F1 | n/a | n/a | 0.588 | **0.833** |
| Exact 3-way labels | 0.733 | 0.840 | 0.880 | **0.933** |
| Mean latency per claim | 0.085 ms | 7.06 ms | 5.91 ms | **5.91 ms** |

All 5 reference contradictions are now found. The 2 remaining false
contradictions are the two `PARTIALLY_SUPPORTED` compound claims (`2006 … $52.1M
and 280 IPO`, `… $8.3M and 45 contracts`); they come from the pre-existing
value-conflict rule, not from binding, and were also false contradictions in r2.

Binding block in `summary.json`:

- 49 value-only claims scored; 3 held back as bound to another attribute
  (2 reference `INSUFFICIENT_EVIDENCE`, 1 reference `SUPPORTED`);
- 1 contradiction established by table binding, 4 by the prose patterns.

Generation-level consequences are unchanged because no generation was re-run:
coverage 75/140 → 74/140, EM 0.129 = 0.129, token F1 0.257 → 0.230,
unsupported-claim 0.198 → 0.165 (recorded runs).

## 12.5 Tests

| Command | Result |
|---|---|
| `pytest -q tests/unit/generation/test_verification_relations.py` | **44 passed**, exit 0 (8 new binding tests) |
| `pytest -q tests/unit/generation tests/unit/evaluation` | **858 passed, 10 skipped, 2 xfailed**, exit 0 |
| `pytest -q tests/unit` | **1533 passed, 23 skipped, 2 xfailed**, exit 0 |
| `compileall -q generation evaluation tests` | exit 0 |
| runner `--run-id …_r4` | exit 0; benchmark SHA-256 `1166bf4f…` verified |

The new tests cover: the asked column holding the value (supported); a value in
another column with a competing value (contradicted); the same without one
(insufficient, wrong-attribute reason); a value question selecting the amount
column; derivative-amount and percentage-change contradictions; and the table
`No` cell not acting as prose negation. The 2 `xfail` results remain the
confirmed `Dr.`/`U.S.` splitter defect from §11 — still open, unchanged.

## 12.6 Remaining limitations

- Binding is a heuristic over readable structures (pipe tables, two prose
  patterns), not a general table/attribute parser; it abstains when the column is
  ambiguous, so recall is deliberately capped.
- The frozen reference labels disagree for unit-only cells: `m/s` offered as the
  asked variable is `INSUFFICIENT_EVIDENCE`, while `hPa` offered as the asked
  minimum is `SUPPORTED`. The verifier follows the protocol and holds both back,
  so `hPa` is one of the 3 false rejects. The dataset is frozen; the label
  conflict is recorded, not edited.
- The 3 support false rejects are `hPa.`, `growth 9.7 percent` and a compound
  cash/debt/dividend fragment; none is a wrong-attribute acceptance.
- Single annotator; 19 uncertain records; one evidence block per row; answers are
  short value-heavy Flan-T5-base output. Confidence intervals remain wide
  (contradiction precision 0.71, 95 % CI 0.36–0.92).
- No 15-mark benchmark run, no integration/E2E/browser/live-DB run; process
  memory and CPU were not instrumented.

## 12.7 Decision

**Do not promote the relation-aware verifier.** Its claim-level behaviour on this
set is now strictly better than r2 and its false-accept rate is 0/9, but the
sample is 75 claims from one annotator, the verifier still false-contradicts two
partially supported compounds, it is ~70× slower than lexical, and no
representative end-to-end evidence ties the gain to user-visible answer quality.
The lexical verifier remains the production default; the relation-aware verifier
remains opt-in (`DOCUMIND_VERIFIER=relations`) and experimental.

Next single action: fix the abbreviation-aware claim splitter (Priority 2) as a
separate change under a new dataset version, then re-run this evaluation — the
`Dr.`/`U.S.` defect currently adds an artificial claim to the frozen population
and makes claim counts incomparable across versions.

---

# 13. Addendum (2026-10-18, mission 2) — abbreviation-aware claim extraction and dataset v2

## 13.1 Mission and status

**Completed.** The production claim splitter no longer treats honorifics,
initialisms and Latin abbreviations as sentence ends. `answer_claims_v1` is
byte-for-byte unchanged and remains reproducible through a frozen copy of its
extractor; the corrected population is versioned as `answer_claims_v2` and scored
in a new report. The production verifier default (lexical) and the opt-in status
of the relation-aware verifier are unchanged. Priority 3 was not started.

## 13.2 Reproduced defect

`generation.planning.split_claims` split on every `(?<=[.!?])\s+` boundary.
Measured on the current code before the fix:

| Input | Output before the fix |
|---|---|
| `Dr. Sarah Chen is the CEO.` | `["Dr.", "Sarah Chen is the CEO."]` |
| `Dr. Sarah Chen joined the organization. She later became its CEO.` | `["Dr.", "Sarah Chen joined the organization.", "She later became its CEO."]` |
| `The U.S. team completed the review.` | `["The U.S.", "team completed the review."]` |
| `The system uses U.S. standards. The report describes the results.` | `["The system uses U.S.", "standards.", "The report describes the results."]` |
| `J. Smith led the audit. It closed in May.` | `["J.", "Smith led the audit.", "It closed in May."]` |
| `Acme Inc. filed the report. It was late.` | `["Acme Inc.", "filed the report.", "It was late."]` |
| `m/s. Variable \| Unit \| … [1]` | split after `m/s.` (correct, must be preserved) |

The defect created an artificial claim (`Dr.`) in the frozen reference set and
inflated the claim count of the affected answer. It did not change any label of
a genuine claim, but it made claim counts incomparable across splitter versions.

## 13.3 Fix

`generation/planning.py` now evaluates each boundary instead of splitting
unconditionally (`_is_non_terminal_boundary`):

1. a trailing **capital single letter** standing alone is an initial (`J. Smith`);
2. titles, initialisms and Latin abbreviations (`Dr.`, `Mr.`, `U.S.`, `U.K.`,
   `e.g.`, `i.e.`, …) never close a sentence;
3. any other dotted abbreviation followed by a **lower-case word or a digit**
   does not close a sentence (`Acme Inc. filed`, `e.g. 3.5`);
4. when the next word is capitalised the boundary stands, so `etc.` / `Inc.`
   still end a sentence (`… checked, etc. Nothing failed.` → two claims).

Numeric forms are untouched because they have no whitespace after the dot
(`3.5`, `$142.6 million`, `20.3 percent`), and a lower-case unit suffix is not an
initial (`m/s. Variable …` still splits). The splitter remains deterministic,
order-preserving and dependency-free; list markers, newlines, citation-only
filtering and the public signature are unchanged.

## 13.4 Dataset versioning

`answer_claims_v1` is preserved (SHA-256 `b419eaa1416890d145e82084ccdbec894575914b16a1c1a239c1004528fa2f4a`).
Its module now imports `evaluation/datasets/legacy_split.py`, a frozen copy of the
pre-fix splitter, so v1 reports stay reproducible.

`answer_claims_v2` re-extracts the claims from the same two recorded 10-mark runs
with the corrected splitter. Exactly one recorded answer changes, in both runs:

| v1 | v2 |
|---|---|
| `Dr.` (NOT_A_CLAIM, fragment) + `Sarah Chen` (SUPPORTED, value_only) | `Dr. Sarah Chen` (SUPPORTED, value_only, answers the question) |

- 2 records removed, 1 added; the merged record is **re-annotated**, not copied:
  the question asks for the CEO and the passage assigns it to Dr. Sarah Chen.
- 102 records are carried over unchanged, keeping their `claim_id`s.
- Totals: **103 claims / 86 questions**, 75 propositional (66 SUPPORTED, 5
  CONTRADICTED, 2 INSUFFICIENT, 2 PARTIALLY_SUPPORTED) and 28 non-claims.
- The mapping is declared in `answer_claims_v2.CHANGES`; the new ID is
  `ac_` + SHA-1(`example_id|claim`)[:10], checked against v1 for collisions.

The runner now takes `--dataset v1|v2` and uses each module's `split_claims`, so a
version is always scored on the extraction it was annotated against.

## 13.5 Evaluation (same frozen benchmark and recorded answers)

| Metric | v1 (`r4`) | v2 | Change |
|---|---:|---:|---|
| Claims / propositional / non-claims | 104 / 75 / 29 | **103 / 75 / 28** | −1 non-claim |
| Lexical support P / R / F1 | .932 / .833 / .880 | .932 / .833 / .880 | none |
| Lexical false rejects | 11/66 | 11/66 | none |
| Relations support P / R / F1 | 1.000 / .955 / .977 | 1.000 / **.939 / .969** | −1 TP |
| Relations false rejects | 3/66 | **4/66** | +1 |
| Relations contradiction P / R / F1 | .714 / 1.000 / .833 | .714 / 1.000 / .833 | none |
| Exact 3-way labels | .933 | .920 | −.013 |
| Claims emitted (lexical run) | 88 | **87** | −1 |
| Claims emitted (relations run) | 90 | **89** | −1 |
| Questions with claims | 75 | 75 | none |

**The metric change is a population change, not a verifier improvement.** The
merged `Dr. Sarah Chen` claim is gold SUPPORTED; the lexical verifier supports it,
the relation-aware verifier returns INSUFFICIENT_EVIDENCE. Root cause, measured:
the evidence-side sentence splitter (`generation.verification.split_sentences`)
has the *same* abbreviation defect, so `CEO: Dr. Sarah Chen (since January 2022)`
is split into `CEO: Dr.` and `Sarah Chen (since January 2022)`. The claim's head
(`dr`) is then absent from the second sentence, `_head_present` fails, and the
paraphrase fallback misses by a narrow margin (cosine 0.778 < 0.80). This is a
verifier defect exposed by the corrected extraction, not caused by the dataset
annotation.

That evidence-side splitter was **not** changed in this mission: it alters
verification for every claim and would break v1 reproducibility. It is the next
recommended action.

## 13.6 Reproduction of v1

`--dataset v1 --run-id answer_claim_evaluation_2026-10-18_v1_repro` reproduces
`r4` exactly (lexical, relations, binding, denominators, generation impact, and
dataset statistics all compare equal). The report is kept as evidence.

## 13.7 Tests

| Command | Result |
|---|---|
| `pytest -q tests/unit/generation/test_generation_planning.py` | **29 passed**, exit 0 |
| `pytest -q tests/unit/evaluation/test_answer_claim_evaluation.py` | **33 passed**, exit 0 (9 new versioning tests) |
| `pytest -q tests/unit` | **1553 passed, 23 skipped, 0 xfailed**, exit 0 |
| `compileall -q generation evaluation tests` | exit 0 |
| v1 runner (`--dataset v1`) | exit 0; all metric blocks equal to `r4` |
| v2 runner (`--dataset v2`) | exit 0 twice; deterministic metric blocks |

The two former strict xfails now pass as normal tests; the defect they recorded is
fixed. The unit suite no longer contains expected failures.

## 13.8 Compatibility and limitations

- `split_claims` is used by the production lexical verifier, the relation-aware
  verifier and the evaluation runner; all three now see the corrected boundaries.
  A smoke check shows `Dr. Sarah Chen is the CEO.` verified as one SUPPORTED claim.
- Historical reports (`…2026-10-18`, `_r2`, `_r3`, `_r4`) and both datasets are
  retained. No benchmark, label in v1, production default, prompt, model or
  frontend file was modified.
- The v1 ↔ v2 comparison is **not** a like-for-like sample: one non-claim was
  removed and two claims were merged into one. Only claim-level counts and the
  affected answer are directly comparable; all other metrics are unchanged
  because the other 102 records are identical.
- The guard has two conservative edge cases: a sentence genuinely ending in a
  capital single letter (`The grade is A. It passed.`) is not split, and an
  abbreviation before a capital is treated as a sentence end (`Acme Inc. The …`).
  Both err toward keeping text together rather than dropping a claim.
- No integration, E2E, browser, database or server test was run; no new generation
  was run; the 15-mark benchmark remains unavailable. Annotations are still from a
  single annotator.

---

# 14. Addendum (2026-10-18, mission 3) — evidence-side abbreviation boundaries and re-baselining

## 14.1 Mission and status

**Completed.** `generation.verification.split_sentences` now uses the same
abbreviation rule as the claim splitter. Both datasets were re-evaluated under new
run IDs. The only verdict that changed is the target case: the relation-aware
verifier now supports `Dr. Sarah Chen`. The production default remains `lexical`,
the datasets and old reports are untouched, and Priority 3 was not started.

This section **supersedes** §13.5/§13.8 only on the status of the evidence-side
defect: §13 correctly recorded it as unresolved at that time, and it is fixed here.

## 14.2 Reproduced defect

`split_sentences` cut at every `(?<=[.!?])\s+` or newline, so evidence was
fragmented at titles and initialisms:

| Evidence | Fragments before the fix |
|---|---|
| `CEO: Dr. Sarah Chen (since January 2022)` | `CEO: Dr.` / `Sarah Chen (since January 2022)` |
| `The U.S. team completed the review. It passed.` | `The U.S.` / `team completed the review.` / `It passed.` |
| `J. Smith led the audit. It closed in May.` | `J.` / `Smith led the audit.` / `It closed in May.` |
| `Acme Inc. filed the report. It was late.` | `Acme Inc.` / `filed the report.` / `It was late.` |

Measured consequence: for the v2 claim `Dr. Sarah Chen`, the entity was split
across two sentences, so `_head_present` failed and cosine similarity was 0.778
against the threshold 0.80. Gold label SUPPORTED; verdict INSUFFICIENT_EVIDENCE.

## 14.3 Boundary rules (documented before implementation)

The claim and evidence splitters share `generation/sentence_boundaries.py`:

1. a trailing **capital single letter** standing alone is an initial (`J. Smith`);
2. titles, initialisms and Latin abbreviations never close a sentence (`Dr.`,
   `Mr.`, `U.S.`, `U.K.`, `e.g.`, `i.e.`, …);
3. any other dotted abbreviation before a **lower-case word or digit** continues
   the sentence (`Acme Inc. filed`, `e.g. 3.5`);
4. a capitalised next word is a real boundary (`Acme Inc. The …`, `etc. Nothing`);
5. an ellipsis always closes the sentence (`Wait... what?`);
6. a lower-case unit suffix is not an initial (`m/s.` ends the sentence);
7. in evidence, a **newline is always a boundary** — evidence lines and table rows
   are structural, and a paragraph break is not an abbreviation.

Implementations remain separate where their responsibilities differ: `split_claims`
works line by line, strips list markers and drops citation-only fragments;
`split_sentences` first joins line-wrapped lower-case continuations, then scans the
same boundaries. The legacy v1 claim extractor stays frozen and does not import
the shared rule.

## 14.4 Change

- **New** `generation/sentence_boundaries.py` — `NON_TERMINAL_ABBREVIATIONS` and
  `is_non_terminal_boundary(before, after)`, no imports from verification or
  planning (no cycle).
- `generation/planning.py` — uses the shared predicate; the local copy and
  abbreviation list are removed. Behavior is unchanged (29 splitter tests pass).
- `generation/verification.py` — `split_sentences` scans boundaries, skips only
  non-terminal abbreviations across spaces, and always splits on newlines.
  `_SENTENCE_SPLIT_RE` is unchanged; empty input returns `[]`; no text is dropped.

## 14.5 Evaluation (same frozen benchmark and recorded answers)

Run IDs (all new; nothing overwritten):

| Dataset | Pre-change | Post-change |
|---|---|---|
| v1 (frozen legacy extractor) | `answer_claim_evaluation_2026-10-18_m3_pre_v1` | `answer_claim_evaluation_2026-10-18_m3_v1` |
| v2 (corrected claim extractor) | `answer_claim_evaluation_2026-10-18_m3_pre_v2` | `answer_claim_evaluation_2026-10-18_m3_v2` |

| Metric | v1 pre | v1 post | v2 pre | v2 post |
|---|---:|---:|---:|---:|
| Claims / propositional | 104 / 75 | 104 / 75 | 103 / 75 | 103 / 75 |
| Lexical support P / R / F1 | .932/.833/.880 | .932/.833/.880 | .932/.833/.880 | .932/.833/.880 |
| Lexical false accepts / rejects | 4 / 11 | 4 / 11 | 4 / 11 | 4 / 11 |
| Relations support P / R / F1 | 1.000/.955/.977 | 1.000/.955/.977 | 1.000/.939/.969 | **1.000/.955/.977** |
| Relations false accepts / rejects | 0 / 3 | 0 / 3 | 0 / 4 | **0 / 3** |
| Relations contradiction P / R / F1 | .714/1.000/.833 | .714/1.000/.833 | .714/1.000/.833 | .714/1.000/.833 |
| Exact 3-way | .933 | .933 | .920 | **.933** |
| Mean relations latency | 6.11 ms | 5.98 ms | 5.90 ms | 6.24 ms |

Benchmark SHA-256 `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0`
verified in all four runs. Coverage, attribute binding, answer relevance, citation
metrics and generation-impact EM/F1 are identical pre/post; only the claim-level
verdict below moved. Latency differences are run-to-run noise (~6 ms, embedder
warm).

## 14.6 Regression analysis

A claim-by-claim diff of `claims.jsonl` pre/post:

- **v1:** 0 label flips (104 claims). The v1 population splits `Dr.` / `Sarah Chen`,
  so the merged claim is not part of it.
- **v2:** exactly 1 flip — `ac_c411173a36` `Dr. Sarah Chen`, relations
  `INSUFFICIENT_EVIDENCE` → `SUPPORTED`, gold SUPPORTED. Lexical was already
  SUPPORTED and is unchanged.

No new false accepts, no new false rejects, no contradiction changes. The v2
improvement is therefore directly attributable to evidence segmentation, not to a
population change (§13 already documented the v1→v2 population effect).

Limits of this evidence: 75 propositional claims, single-annotator labels, one
benchmark (10-mark), no end-to-end user-facing measurement. The relation-aware
verifier remains **opt-in**; the lexical default is unchanged.

## 14.7 Tests

| Command | Result |
|---|---|
| `pytest -q tests/unit/generation/test_evidence_sentence_splitting.py tests/unit/generation/test_generation_planning.py tests/unit/generation/test_verification_relations.py` | **95 passed**, exit 0 (20 new evidence tests, 2 new verifier regression tests) |
| `pytest -q tests/unit` | **1575 passed, 23 skipped, 0 failed**, exit 0 |
| `compileall -q generation evaluation tests` | exit 0 |
| `--dataset v1 --run-id …_m3_v1` | exit 0; rerun deterministic |
| `--dataset v2 --run-id …_m3_v2` | exit 0; rerun deterministic |

The new tests cover titles, country initialisms, initials, `Inc.` before
lower-case and before a capital, `e.g.`/`i.e.`, ordinary boundaries, `etc.` at a
sentence end, decimals/currency/percentages/units, table rows, line wrapping,
empty/whitespace input, text/order preservation, determinism, and the real
`Dr. Sarah Chen` evidence and verdict.

## 14.8 Integrity and remaining limitations

- `answer_claims_v1.jsonl` SHA-256 `b419eaa1416890d145e82084ccdbec894575914b16a1c1a239c1004528fa2f4a`
  and `answer_claims_v2.jsonl` SHA-256 `f06795eb5034133d8dc600a4685621dc0999f4a00b71afa0f490731e0aecad88`
  are unchanged. The frozen legacy extractor is untouched.
- Historical reports (`r2`, `r3`, `r4`, `…_v2`, `…_v1_repro`, `m3_pre_*`) are
  preserved; no historical report was rewritten.
- Newline handling is deliberately conservative: an abbreviation at a line break
  still splits (`Dr.\nSarah`), because a newline is structural in this corpus. No
  benchmark row exercises it.
- A sentence genuinely ending in a capital single letter (`The grade is A. It
  passed.`) is not split; an abbreviation before a capital is treated as a
  sentence end (`Acme Inc. The …`). Both are documented heuristic limits.
- No integration, E2E, browser, database or server test; no new generation; no
  15-mark run. The lexical default remains in force.

## 14.9 Next priority

With extraction and both splitters now consistent, the largest remaining measured
quality gaps are answer relevance and coverage: only 75/140 answerable questions
produce claims, 28% of emitted claims are non-claims, and 9 supported claims do
not answer the question. That is Priority 3; it was not started here.
