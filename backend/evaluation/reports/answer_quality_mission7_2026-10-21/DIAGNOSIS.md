# DIAGNOSIS — DocuMind answer quality, Mission 7 (2026-10-21)

Status: **COMPLETE**. Every figure below is read from an artifact in this
repository or computed by a named command; nothing is inferred from a design
document.

## 1. Verified starting state

| Item | Value | How verified |
|---|---|---|
| Git HEAD | `6baaa2a0773df66e5fb26814afbe67647fb43435` | `git rev-parse HEAD` |
| Working tree | 401 entries, all pre-existing and preserved | `git status --porcelain` |
| Frozen benchmark | `phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` | read before/after every run |
| Benchmark SHA-256 | `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` | `sha256` in every run summary |
| Rows | 182 = 140 answerable + 42 unanswerable | benchmark metadata |
| Claim dataset | `answer_claims_v2`, 103 claims / 86 examples, `f06795eb…` | dataset hash in ledger |
| Production verifier | `lexical` (unchanged) | `DOCUMIND_VERIFIER` default |
| Mission 6 baseline run | `generation_benchmark_2026-10-21_m6_post_v1` | read, not regenerated |

Mission 6 baseline as reported and re-verified from that run's `summary.json`:
EM **0.4500**, F1 **0.5621**, answered **109/140**, gate refusals 45 (11 answerable),
withheld 26 (20 answerable), spurious **2/42**, unsupported-claim rate 0.1364,
citation accuracy 0.8636.

## 2. Method

1. Replayed the gate, the verifier and both deterministic readers over all 182
   rows offline, with no model call, to attribute each failure to a code path.
2. Reproduced generation only where the recorded artifact was insufficient to
   explain a failure.
3. Measured every candidate intervention over the full frozen population before
   adopting it, and recorded the rejected ones with their measurements (§6).
4. Classified each row into a failure *family* that separates what code can fix
   (`runtime_defect`) from what only a benchmark review can
   (`ambiguous_reference`, `reference_format_variant`, `annotation_artifact`).

Ledger: `ERROR_LEDGER.jsonl` (one record per row, **38 fields**, unknown values
written as `"unknown"`). The 26-field Mission 6 schema was extended with
`current_producer`, `regression_status`, `failure_family`, `uncertainty`,
`answer_change`, `previous_run`/`current_run`, `claim_annotation_previous_run`,
`citation_alignment`, `claim_count`/`supported_claim_count` and
`fields_not_annotated`. Built from the post-review run
`generation_benchmark_2026-10-21_m7_reviewed`.

## 3. Verified failure inventory (all 140 answerable + 42 unanswerable)

From `summary.json` → `error_categories` (mutually exclusive as assigned):

| Category | Rows | Producer |
|---|---:|---|
| none (table lookup) | 40 | deterministic-table |
| none (list lookup) | 20 | deterministic-list |
| none (model answer, exact) | 21 | flan-t5-base |
| correct abstention | 40 | gate / withholding |
| incorrect answer | 28 | model |
| false abstention or withholding | 13 | model |
| false answerability-gate refusal | 11 | gate |
| metric or annotation artifact | 7 | model |
| spurious answer on unanswerable | 2 | model |

Failure families (the same rows, grouped by what could fix them):

| Family | Rows |
|---|---:|
| no failure | 121 |
| runtime defect | 35 |
| reference format variant | 11 |
| ambiguous reference | 8 |
| annotation artifact | 7 |

The 35 runtime-defect rows decompose into: 18 **page/list-ordinal failures**
(now fixed, §4), 11 gate refusals, 13 withheld answers, and 2 spurious answers
(some rows belong to more than one of these operational groupings; the ledger's
`error_category` is the mutually exclusive total).

## 4. Root cause established by evidence: ordered lists were delegated to the model

20 benchmark questions are `LIST_ITEM`: "What citation is listed second?", "Name
the fifth key financial highlights?", "Which current leadership handles cfo:
robert tanaka?". **Every one** supplies a heading line followed by one item per
line, and the reference answer is that item **verbatim**.

Mission 6's generative path answered **2 of 20** correctly. The two failure
mechanisms, both measured:

1. **Generation** — the model returned the wrong item (`li_938c278e`, third
   citation answered with the first), a *truncated* item (`li_a4253b0c`,
   `Elena Vasquez` for `COO: Elena Vasquez (since June 2021)`), or two
   concatenated items (`li_1cd424f2`, three financial highlights for one).
2. **Verification** — 10 further rows had the **right** item but were withheld.
   The entity check anchors on the sentence containing the question's rarest term.
   In a heading+items block that sentence is the **heading**, so the item was
   judged to belong to a different entity:
   `COO: Elena Vasquez (since June 2021)` was rejected because
   "Current Leadership" does not repeat inside the item.

A third, subtler mechanism: the evidence sentence splitter fragments exactly the
lines a list resolver returns — `R.T. (2025).` becomes two sentences and
`OAuth 2.0 …` is merged with the next item — so a sentence-based membership test
fails even when the item is byte-identical to the claim.

## 5. Other failure families, individually investigated

### 5.1 Reference-format variants (11 rows) — not defects

`$412.5 million` vs the reference `412.5 million`; `9 members` vs `9`;
`50 items` vs `50`; `$245,000 USD` vs `$245,000`. The answer states the same fact
with a currency symbol or its unit. Rewriting the answer to drop the symbol would
match the reference string and make the answer *less* precise. Classified, not
fixed.

### 5.2 Ambiguous references (8 rows) — not deterministically fixable

| Row | Question | Reference | Evidence |
|---|---|---|---|
| `ds_91da3093` | "what is the monetary value for the amount?" | `910 million` | "revenue in the range of **$880 million to $910 million**" |
| `ds_1efed7c7` | "what does the document say about percentage?" | `20.3 percent` | "**1 percent from 20.3 percent**" |
| `lc_430b8915` | "what is the count?" | `650 people` | passage gives 200 employees, 45 employees, 650 people, 8 countries… |
| `lc_a5d50a79` | "what is the financial figure?" | `$4,900` | passage gives $340M, $89,000, $4,900, … |

No lexical cue selects the reference value. A deterministic rule would have to
guess, and guessing is what this mission is meant to remove.

### 5.3 Section-title references (7 rows) — annotation artifacts

The question asks what a section contains and the reference answer is the section
**title** (`Forward Guidance`, `Fees and Payment`, `Dataset Overview`, …). The
returned body text answers the question that was asked. No runtime change was
made to reproduce a heading.

### 5.4 Boundary-located questions (8 gate refusals + 1 wrong answer) — no consistent rule

These were re-examined with a new hypothesis (a deterministic reader could take
the value at a named section boundary) rather than by loosening the gate. It
fails: in 6 of 9 rows the second named section **does not appear in the supplied
evidence at all**, and in the remaining 3 the reference is the *last* quantity
before the heading twice (`mc_98a6aef8`, `mc_c48b3cae`) and the *first* quantity
after it once (`mc_61595d05`). There is no consistent rule, so none was adopted.

### 5.5 Remaining gate refusals (11) — unchanged, measured in Mission 6

Seven boundary questions (see 5.4) and four lexical paraphrase/compound-noun
cases. Mission 6 measured that unblocking the boundary family yields **0 of 7**
correct answers; that result was not contradicted here.

### 5.6 Spurious answers on unanswerable rows (2/42) — unchanged

`unans_7b46d69d` (`maximum concurrent connection limit` → `100`) and
`unans_03d364a3` (`total cost of ownership` → `$52,000`). Both are unchanged from
Missions 5 and 6; closing them needs a gate tightening that Missions 4–5 measured
to cost answerable coverage.

## 6. Candidate interventions measured and rejected

| Candidate | Measurement | Decision |
|---|---|---|
| Deterministic boundary reader for the 8 boundary refusals + 1 wrong answer | no consistent rule exists (§5.4) | **REJECTED** |
| Withhold an answer that contains no digit when the question asks for a quantity | converts 4 wrong answers to 4 abstentions, loses 0.0036 F1, gains 0 EM; the three currently-correct rows affected are table answers and would be excluded | **REJECTED** — hides a generation failure rather than fixing it |
| Strip the `$`/unit from answers to match the reference string | 11 rows would flip to exact with no change in meaning | **REJECTED** — metric gaming, and the answers would become less precise |
| Return the section heading for the 7 section-title rows | would match an inconsistent reference | **REJECTED** |
| Regenerate `answer_claims_v2` against the new answers | requires new human annotation | **REJECTED** — would fabricate labels |

## 7. Priority carried into implementation

1. Deterministic ordered-list resolution (20 rows, evidence-verbatim, mirrors the
   Mission 6 table reader that produced no regressions).
2. List-membership membership rule in the entity check (13 withheld rows).
Nothing else was justified by the evidence, so nothing else was changed.
