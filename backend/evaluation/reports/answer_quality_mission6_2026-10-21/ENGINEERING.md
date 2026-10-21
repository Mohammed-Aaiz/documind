# ENGINEERING — DocuMind answer quality, Mission 6 (2026-10-21)

No commit, no staging, no push, no deployment. Repository revision unchanged at
`6baaa2a0773df66e5fb26814afbe67647fb43435`. Pre-existing working-tree changes were
left intact.

## 1. Files changed

| File | Change | Why |
|---|---|---|
| `backend/generation/tables.py` | **new** (214 lines) | deterministic table row/column resolution |
| `backend/generation/service.py` | `_table_answer` + `DETERMINISTIC_TABLE_ENGINE`, called after the gate | use the table answer instead of generating it |
| `backend/generation/verification.py` | `support_ratio` raw-token fallback; `MIN_CLAIM_TOKENS` applied to raw tokens; `_FISCAL_YEAR_RE` / `_normalise_question_term` | stopword-only claims; `FY2024` term normalisation |
| `backend/generation/planning.py` | `is_propositional`, filtered in `plan_support_points` | never append a table render as a "supporting point" |
| `backend/generation/engine.py` | `_EVIDENCE_ECHO_RE` in `_clean_output` | drop a copied prompt marker from the answer |
| `backend/evaluation/experiments/build_answer_quality_ledger.py` | **new** | 182-row question-level ledger for this mission |
| `backend/tests/unit/generation/test_generation_table_answers.py` | **new** (27 tests) | regression cover for every changed behaviour |

Untouched: the production verifier default (`lexical`), `chat/qa_model.py`, `chat/rag.py`,
retrieval, prompts, the frozen benchmark, the claim datasets, the schema, the frontend,
and every threshold (`SUPPORT_RATIO`, `NUMERIC_SUPPORT_RATIO`,
`MAX_MISSING_QUESTION_TERMS`, `MIN_POINT_RELEVANCE`, `ELABORATION_POINTS`).

## 2. Design of the table resolver

`resolve_table_answer(question, blocks) -> TableAnswer | None`

- Table = a header line plus ≥1 equal-width data row, ≥3 cells, parsed line-by-line.
  The existing sentence splitter is **not** used: it deliberately joins a newline
  followed by a digit, which is exactly what a data row looks like (`2010 | $178.0M`).
- Row = the unique data row whose first-cell terms all occur in the question.
  Two matches (e.g. a label contained in a longer label) → abstain.
- Column = the unique header cell with the highest term overlap. A tie → abstain.
- No column and the question asks for "values"/"information"/… → the whole row,
  pipe-joined, verbatim.
- The question must contain a lookup cue (`what`, `which`, `how much/many`, `name`,
  `list`, `give`). "Where is the Premium tier described?" names a header term but is
  not a lookup, and abstains.
- Cell 0 is *not* excluded from column matching (the Mission 5 verifier decision was
  the opposite). In these tables cell 0 is a real attribute column — `Variable`,
  `Division`, `Year`, `Method`, `Tier` — and questions such as "what is the division
  for Enterprise Solutions" have that cell as the gold answer.

The resolved text is then passed through the **unchanged** verifier; an answer the
verifier cannot attribute falls back to generation. So the new path can only return
text that is present in, and attributable to, the cited block.

## 3. Why the answer is not elaborated

`answer_generatively` returns the table answer before `plan_support_points` runs.
Measured reason: 10-mark answers for `tc_6dd05b59`, `tc_8340538b` and `tc_fceaa66a`
were the correct cell followed by the table header, which turned an exact answer into
F1 0.50 and created the 6 `PARTIALLY_SUPPORTED` rows. A cell is a complete answer at
5, 10 and 15 marks; depth is bounded by what the evidence supports, which here is one
cell.

The table answer carries its citation in the reported `sources` and in the warning
text, not as an inline `[n]`, because the cell is quoted verbatim, not paraphrased.

## 4. Verification of the changes

```
venv/Scripts/python.exe -m pytest -q tests/unit/generation        # 197 passed
venv/Scripts/python.exe -m pytest -q tests/unit                   # 1611 passed, 23 skipped
venv/Scripts/python.exe -m compileall -q generation evaluation/experiments   # exit 0
```

1611 = 1584 (Mission 5 recorded) + 27 new tests. No test was skipped, weakened or
removed to make this pass; `test_generation_entity_verification.py` (the Mission 5
table-entity tests) passes unchanged, so the two table mechanisms are consistent.

## 5. Risks and why they are acceptable

| Risk | Bound |
|---|---|
| A table lookup hijacks a question that is not a lookup | unique row + unique column/cue required, plus a lookup-cue requirement; 0 of the 142 non-table answerable rows resolve |
| A wrong row is returned because two labels share a term | unique-match requirement, otherwise abstain |
| The answer is "too literal" (a cell, not prose) | by design; the text is evidence verbatim and the citation is reported |
| Stopword-claim fallback accepts an empty claim | the fallback still requires a raw token that occurs literally in the evidence; absent values are still rejected (test) |
| Fiscal-year normalisation widens the gate | it only rewrites `fy<year>` question terms; verified not to rescue an unrelated question (test) |
| Removing table renders from elaboration loses depth | they assert nothing; prose points are unaffected (existing tests pass) |

## 6. Architecture implications

- The generative path now has a **third** producer, alongside the model and abstention:
  a deterministic, evidence-verbatim table reader. It is reported as
  `model: "deterministic-table"` so no surface implies a language model wrote it.
- The principle generalises: where the evidence already states the answer structurally
  and the question is a lookup, resolve it deterministically and let the verifier judge
  it. It does not extend to prose questions, where generation remains the only path.
- Retrieval, chunking and prompt construction are unchanged; the resolver consumes the
  same `EvidenceBlock` list the generator would have received.
