# ENGINEERING — DocuMind answer quality, Mission 7 (2026-10-21)

No commit, no staging, no push, no deployment. Repository revision unchanged at
`6baaa2a0773df66e5fb26814afbe67647fb43435`. Every pre-existing working-tree change
preserved.

## 1. Files changed

| File | Change | Why |
|---|---|---|
| `backend/generation/lists.py` | **new** (267 lines) | deterministic ordered-list resolution |
| `backend/generation/service.py` | `_list_answer`, `_structured_answer`, `DETERMINISTIC_LIST_ENGINE`; `EvidenceBlock.truncated` set from the 1200-char cut | use the list answer instead of generating it; refuse a *position* read from a truncated excerpt |
| `backend/generation/types.py` | `EvidenceBlock.truncated` | a silently truncated excerpt cannot establish an ordinal position |
| `backend/generation/verification.py` | `_list_entity_alignment` in `numeric_entity_alignment` | a correct item was rejected because the heading is not inside it |
| `backend/generation/tables.py` | `_subject_terms` → public `subject_terms` | one tokenizer for rows, columns and list headings |
| `backend/evaluation/experiments/run_generation_benchmark.py` | `RowResult.generative_model` recorded | the answer text cannot tell a table answer from a list answer; the ledger must attribute rows to the change that produced them |
| `backend/evaluation/experiments/build_answer_quality_ledger.py` | producer + `failure_family`, `uncertainty`, `regression_status`, format-variant and ambiguous-reference classifiers | Mission 7 ledger schema |
| `backend/tests/unit/generation/test_generation_list_answers.py` | **new** (32 tests) | regression cover for every changed behaviour |

Untouched: the production verifier default (`lexical`), `chat/qa_model.py`,
`chat/rag.py`, retrieval, prompts, the frozen benchmark, the claim datasets, the
schema/migrations, the frontend, and every threshold (`SUPPORT_RATIO`,
`NUMERIC_SUPPORT_RATIO`, `MAX_MISSING_QUESTION_TERMS`, `MIN_POINT_RELEVANCE`,
`ELABORATION_POINTS`). Mission 5's table-entity alignment and Mission 6's table
grounding are unchanged except for the shared tokenizer rename.

## 2. Design of the list resolver

`resolve_list_answer(question, blocks) -> ListAnswer | None`

- A list is a run of **consecutive non-empty lines**: a heading plus at least two
  item lines. Prose paragraphs are separated by blank lines and never form a run;
  a heading may not end in terminal punctuation, may not contain `|`, and may not
  exceed eight words.
- The question must **name the heading** (all heading terms present in the
  question, compared on stems so "the last key financial *highlight*" names "Key
  Financial *Highlights*").
- A heading may not contain `:` — `Revenue: $847.3 million` is a key/value item,
  and treating it as a heading shifts every position by one — and may not be
  longer than the shortest item line, so an intro sentence above a list is not
  mistaken for its heading.
- **Positional** questions ("first", "third", "comes fourth", "listed eighth",
  "last") return the item at that 1-based position, exactly as the evidence
  orders it. A position beyond the list abstains. A question carrying **two**
  ordinals ("the first and third item") abstains rather than degrading to a
  content match, and a position is never read from a **truncated** block: the
  excerpt drops the tail without a marker, so "the eighth item" can no longer
  resolve to the fifth surviving one.
- **Content** questions ("which current leadership handles cfo: robert tanaka",
  "operating margin: 22.1%") return the single item sharing at least two terms,
  and abstain on a tie.
- Nothing is inferred from retrieval rank or block order: position always comes
  from the evidence's own line order.
- The resolved text then passes through the **unchanged** verifier; an answer the
  verifier cannot attribute falls back to generation.

## 3. The verifier defect it exposed

`numeric_entity_alignment` anchors on the sentence containing the question's
rarest term. For heading+items evidence that sentence is the heading, so an item
is judged a different entity. The fix adds `_list_entity_alignment`, which
answers the question the check is actually asking — *does this claim belong to
the entity the question names?* — by testing whether the claim occurs **inside an
item of a list whose heading names the question's focus**.

Testing against items rather than sentences matters: the evidence splitter
fragments exactly the lines a list resolver returns (`R.T. (2025).` → two
sentences; `OAuth 2.0 …` merged with the next item). A sentence-based test fails
on byte-identical items.

Scope is deliberately narrow: the claim must be a substring of an item of the
*matching* list. A value that appears elsewhere in the same block is still
rejected — pinned by `test_value_outside_the_named_list_is_still_rejected`.

## 4. Verification

```
pytest -q tests/unit/generation                      → 229 passed
pytest -q tests/unit                                 → 1643 passed, 23 skipped, 0 failed
compileall generation evaluation/experiments tests/unit/generation → exit 0
pytest -q tests/integration                          → 293 passed, 4 failed, 1 error (pre-existing)
pytest -q tests/e2e                                  → 6 skipped (no live server)
python -m evaluation.experiments.run_answer_claim_evaluation --run-id …_m7_reviewed
    → lexical support F1 0.8889, identical to answer_claim_evaluation_2026-10-18_m5_v2
```

1643 = 1611 (Mission 6) + 32 new tests. No test was skipped, weakened or removed.

The claim-evaluation replay is the check that the verifier change is targeted:
lexical support F1 0.8889 (P 0.9333 / R 0.8485), relations 0.9767, false accepts
4 / 0, false rejects 10 / 3, non-claim acceptance 28/28 and 20/28 — **identical**
to the Mission 5 record. The change fires only on heading+item structures, which
that annotated population does not contain.

## 5. Independent review and hardening

A separate review pass read the change as a whole (resolver, call site, verifier
hook, tests) before it was reported. It found seven defects; all seven were fixed
and each fix is pinned by a test. **None of them is visible on the frozen
benchmark** — its evidence blocks are never truncated, its list questions carry
one ordinal, and its headings start their run — which is why the measured
aggregate did not move.

| # | Severity | Defect | Fix |
|---|---|---|---|
| 1 | HIGH | a positional answer could be read from a **truncated** block (`content[:MAX_BLOCK_CHARS]` drops the tail silently), so "the eighth item" resolved to the fifth surviving one and the verifier confirmed it — it *is* an item of that list | `EvidenceBlock.truncated` set from the cut; positional resolution refuses a truncated block; content matching still allowed (a missing tail cannot change which item contains a phrase) |
| 2 | MEDIUM | the first line of a run was assumed to be the heading, so a label followed by an unpunctuated intro line parsed as heading + items and shifted positions by one | a heading may not contain `:` and may not be longer than the shortest item; pinned by `test_a_label_with_terminal_punctuation_is_not_a_heading` |
| 3 | MEDIUM | a two-ordinal question silently fell through to a **content** match, contradicting the documented abstention | explicit abstention before resolution; pinned by `test_two_positions_in_one_question_abstain` |
| 4 | MEDIUM | `test_content_match_requires_a_unique_best_item` was **vacuous** — the question did not name the heading, so the resolver returned `None` before the tie logic ran | the test now names the heading (`Options` / "which option is internal data") and asserts the heading was actually parsed |
| 5 | LOW | the verifier accepted *any* nearby list when the question had no distinctive term | the list rule returns `None` in that case and the prose rule stays in charge |
| 6 | LOW | the verifier compared headings with stopword-stripped tokens while the resolver keeps them, so a heading could be resolvable but unverifiable | both use raw terms (`_raw_terms`), pinned by test |
| 7 | LOW | `where` was computed and never used in the list warning | the warning now names the heading and the item position |

Re-measured after the fixes: `generation_benchmark_2026-10-21_m7_reviewed` —
81/140 exact, EM 0.5786, F1 0.6637, 2/42 spurious, unsupported-claim rate 0.0821,
identical to `m7_post_v2` on every answer and every metric; 36 of 182 records
differ only in the warning text. Row diff vs Mission 6: **18 gained, 0 lost**. The
ledger in this directory is built from that run, and the claim replay
(`answer_claim_evaluation_2026-10-21_m7_reviewed`) still reproduces lexical
support F1 0.8889 / false accepts 4 / false rejects 10.

## 6. Risks and their bounds

| Risk | Bound |
|---|---|
| A wrapped prose paragraph is read as a list | needs ≥2 item lines in a consecutive run *and* a heading the question names; wrapped prose has no such heading |
| A position is read from a list whose tail was cut | the block is flagged `truncated` when the excerpt is shorter than the chunk, and positional resolution then abstains |
| The wrong item is returned for a position | position is the evidence's own line index; the list must be long enough or the resolver abstains |
| Two lists with similar headings | the heading must be fully named by the question, and the content form requires a unique best item |
| Items are mixed across lists | parsing is per consecutive run; a blank line ends the list |
| The verifier loosening admits wrong values | the claim must occur inside an item of the list whose heading names the question's focus; tested |
| Table behaviour regresses | Mission 6's 40 rows are unchanged (all 40 still deterministic-table and exact) |

## 7. Architecture implications

The generative path now has four producers: the local model, the deterministic
table reader (Mission 6), the deterministic list reader (Mission 7), and
abstention. Both deterministic readers are reported as their own engine name, so
no API surface implies a language model produced a value it did not.

The general principle is now applied twice and should be the default for
structured evidence: *if the answer is a position or a cell in the supplied
evidence, resolve it from the structure and let the verifier judge it; use the
model for prose.* It does not extend to prose selection — §5.2 of the diagnosis
shows why.
