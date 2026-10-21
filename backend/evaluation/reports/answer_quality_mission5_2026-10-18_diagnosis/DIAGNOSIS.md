# Mission 5 — answer quality diagnosis and intervention plan (2026-10-18)

Repository HEAD `6baaa2a0773df66e5fb26814afbe67647fb43435`; 401 pre-existing
working-tree entries, nothing staged. `agents/` contains instruction contracts
(`README.md`, `coordinator.md`, `evaluation-agent.md`, `test-agent.md`,
`verifier.md`, `agentic-coding-agents/*`), not executable agents, so they are
applied directly; no agent process was launched or claimed. No skill files or
`/interview` / `/plan` / `/reasoning` commands exist in this environment.

Artifacts: `ledger.jsonl` (182 rows) and `summary.json` in this directory,
produced by `evaluation/experiments/build_answer_error_ledger.py` from the frozen
benchmark and the recorded runs. Each row carries the benchmark id and label,
question, gold, baseline and Mission 4 answers, status, claims and rejected
claims, annotation-based relevance counts, the error category, a root-cause
hypothesis, a proposed action, confidence and severity. Hypotheses are derived
from recorded fields (not adjudicated labels). Benchmark SHA-256
`1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0`; v2 dataset
`f06795eb…`.

## 1. Mission 4 baseline is verified

Recomputed from `results.jsonl` and `claims.jsonl`, not copied from the summary:

| Metric | `m4_baseline` | `m4_post_v2` |
|---|---:|---:|
| Answerable answered | 75 / 140 | 99 / 140 |
| Gate refusals | 49 | 13 |
| Withheld | 16 | 28 |
| Exact match | 18 (0.1286) | 21 (0.1500) |
| Token F1 (mean) | 0.2567 | 0.3091 |
| Empty rate (182) | 0.5769 | 0.4451 |
| Unanswerable spurious | 2 / 42 | 2 / 42 |
| Returned claims / unsupported | 87 / 5 | 113 / 5 |
| Withheld answers / rejected claims inside them | 16 / 14 | 28 / 24 |

The reported unsupported-claim-rate rise (0.1981 → 0.2199) and citation drop
(0.8019 → 0.7801) are **entirely attributable to rejected claims inside withheld
answers**: the answers users actually receive carry the same 5 unsupported
claims in both runs (87 → 113 returned claims). No delivered-answer regression
is present; the metric counts text that is never returned. This is a verified
fact, not an inference. The claim runner was not re-run because it consumes the
recorded `fmt10` answers and would be identical by construction.

## 2. Failure taxonomy (140 answerable + 42 unanswerable)

| Category | Count | Stage | Notes |
|---|---:|---|---|
| Answered, exact | 21 | generation | 3 added by Mission 4 |
| Answered, non-exact | 78 | generation / completeness | 21 added by Mission 4 |
| Gate refusal | 13 | answerability gate | 5 paraphrase/unit/header-stripped; 8 boundary contexts genuinely omit terms |
| Withheld | 28 | lexical verifier | 24 have a rejected claim; 4 empty otherwise |
| Unanswerable answered | 2 | gate + verifier | unchanged from baseline |

Withheld-answer rejection reasons (24 claims): **19 numeric entity mismatch**, 4
"claim text not sufficiently present", 1 "value absent". The entity check is the
dominant withholding cause, so it is the first target.

### 2.1 Off-target claims (9 supported, `answers_question=false`)

Verified records: `lc_430b8915` (2005 count asked as 2010), `lc_dad0e4e6`
(950 vs 1,000), `tc_8faf2be8` (revenue milestone where employees are asked),
`tc_e7eb93d1` (milestone, wrong year), `tc_a7432939` (amount where the gold is
the row label), `tc_e75b3a72` (auth fact for a different method), and three
single-column row answers (`tr_7e68327d`, `tr_b0ffbc0f`, `tr_ddbb3252`).
Taxonomy: 4 wrong attribute/value/time (generation), 5 single-cell row/table
answers (extraction/completeness). The verifiers cannot see the question's
attribute; no small fix exists in this mission.

## 3. Root cause of the largest withholding cluster

`generation.verification.numeric_entity_alignment` finds the question's rarest
term and uses the sentence that contains it as the **anchor**. For a pipe table:

```
Tier | Rate Limit | Burst Limit | Monthly Quota
Premium | 1,000 req/min | 1,500 req/min | 5,000,000 requests
```

the rarest term is a **column name** (`limit`), so the anchor is the header row.
Its subject tokens are `tier, rate`; the value row does not contain them, and the
function returns `mismatch`. Reproduced for `tc_8340538b` (`1,000 req/min`),
`tc_06f5c7e8` (`+4.2%`), `tc_115f3133`, `tc_78ac63a0`, `tc_1658c1fb`,
`tc_479dca78`, `tc_dcc6b88d`, `tc_03298034`. Four of those are correct
rejections (the value is in the wrong column); two are exact gold answers that
are wrongly withheld.

## 4. Selected intervention (single, localized)

**Table column binding in the lexical verifier's entity check.** When the
evidence is a simple pipe table (header row plus equal-width data rows):

1. Treat cell 0 as the row label/table title, not an attribute column.
2. Choose the asked column from the header cell that shares the most raw
   question terms (excluding cell 0).
3. Locate the data row whose label shares a question term.
4. Return `matched` only when every claim number in that row sits in the asked
   column; otherwise `mismatch`.

Fall back to the current behaviour when the evidence is not a table or no asked
column can be identified. This fixes the header-anchor defect, keeps wrong-column
values withheld (`tc_1658c1fb` mean vs min, `tc_479dca78`, `tc_dcc6b88d`,
`tc_03298034`), keeps over-wide multi-column compounds withheld
(`tc_115f3133`, `tc_78ac63a0`), and does not change abstention.

Pre-implementation simulation on every v2 claim: 2 rejected claims become
supported (`tc_8340538b` `1,000 req/min`, `tc_06f5c7e8` `+4.2%`); the off-target
single-column answer `tc_a7432939` stays unchanged because cell 0 is not used for
column inference. The simulation covered annotated claims only, so it did not
predict every full-answer effect: the measured run also withholds one previously
returned wrong answer (`tc_f3617604`, a multi-column dump). Observed row-level
results are in `EXPERIMENT.md` §2; the recovered answers append the table header,
so they add coverage but not exact matches.

Why generalizable: it encodes the table's structure (header/row/column), not any
benchmark ID or gold text; it applies to any pipe table the extractor produces.

Risks: mis-parsed tables (header and data row widths differ → fall back);
questions that name a column only via the table title (→ fall back); claims that
carry values from several columns (→ mismatch, unchanged). Regression tests will
pin the two recoveries, the four intended rejections, and the non-table fallback.

Metrics: answered count, EM/F1, withheld count, rejected-claim count,
unanswerable spurious, plus a row-level diff; same benchmark and annotations.
Planned success bar: +2 answered, no answer lost, no new spurious answer, and no
change to the 4 intended wrong-column rejections.

Observed outcome (`EXPERIMENT.md`): 2 answers added, 1 wrong answer removed (net
+1 answered), exact match unchanged because both new answers append the table
header, unsupported/citation rates improve slightly, and unanswerable spurious
stays at 2/42. The wrong-column rejections are unchanged. The planned "+2 exact"
was not met, and is not claimed.

## 5. Considered and rejected

* **Relaxing support thresholds** for long list/table claims: would surface
  over-wide or wrong-column answers (5+ cases) and weaken grounding.
* **Section-body alignment** (`sec_5e1deffc`, `sec_e95f766d`): correct content
  withheld because the anchor is the section heading; gold is the heading, EM
  would stay false, and the heading/body rule is less crisp than table columns.
  Documented as a follow-up.
* **Off-target attribute binding**: needs question-to-attribute reasoning at
  generation time; out of scope for a localized verifier fix.
* **Claim-extractor redesign** for 28 non-claims: they are excluded from the
  propositional denominator and do not drive the observed quality failures.
