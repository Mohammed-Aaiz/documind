# Structure-discriminating corpus v1 — dataset audit

- Corpus version: `structure-discriminating-v1`
- Module: `backend/evaluation/datasets/structure_discriminating_v1.py`
- Validator: `./venv/Scripts/python.exe evaluation/datasets/structure_discriminating_v1.py` → prints `VALID`
- Status: **hypothesis not yet tested** — the A/B/C/D ablation has deliberately not been run on this corpus.

---

## 1. Corpus purpose

The production-aligned A–D ablation on the existing `phase3d` and `heading`
corpora produced a null result: semantic-only (**A**) and structure-aware (**C**)
retrieval had identical `recall@5`, negligible `nDCG@5` differences, and no
EM/token-F1 gain. The dominant explanation is corpus composition: nearly every
question could be answered from a single lexically-matching chunk, so the
structural path had nothing to contribute.

This corpus exists to remove that confound. It is a **new, separate** dataset
whose questions are designed so that a semantic-only chunk retriever is expected
to fail or to be at risk of retrieving the wrong structural location. It does
**not** modify `phase3d`, `heading`, any existing report, or any production code.

It provides a better-controlled opportunity to test the hypothesis
("structure-aware retrieval and Dual-Path GraphRAG help answer questions whose
evidence depends on document structure"). It does not demonstrate an advantage.

## 2. Source documents

Four authored PDFs (real PDFs: font-based headings at the sizes
`documents.processing._classify_pdf_heading` uses, body paragraphs, and ruled
tables detected by `page.find_tables`). Each PDF was verified to parse through
`documents.parser.parse_pdf` into real `section` / `paragraph` / `table`
elements.

| document | file | pages | authored elements | answerable questions |
|---|---|---|---|---|
| atlas | `atlas_propulsion.pdf` | 3 | 5 section, 5 paragraph, 2 table (+10 rows, 30 cells) | 22 |
| field | `field_survey.pdf` | 3 | 4 section, 8 paragraph, 2 table (+10 rows, 30 cells) | 17 |
| oslo | `oslo_reactor.pdf` | 3 | 7 section, 2 paragraph, 3 table (+15 rows, 45 cells) | 19 |
| archive | `archive_records.pdf` | 2 | 3 section, 4 paragraph, 1 table (+6 rows, 18 cells) | 6 |

Total: 64 answerable + 8 unanswerable = 72 questions.

Structure is *derived from the same declarative spec the PDF builder renders*, so
a gold structural reference cannot drift from the document that backs it.
Element types and relation names use the production vocabulary
(`graph.models.ELEMENT_TYPES`, `graph.models.STRUCTURE_RELATIONS`); the validator
asserts the vocabulary still matches production.

## 3. Question construction methodology

Every answerable question is authored with: a document, the expected answer and
acceptable paraphrases, **evidence substrings** present in the backing element
(the same gold-derivation convention the ablation runner uses), the gold
structural element ids, the expected structural path, the expected evidence
type, and a discrimination label + rationale. Unanswerable questions carry no
gold and no expected answer.

Table/row/cell questions are generated deterministically from the authored
tables (one question per selected row/column), so their answers are grounded in
the exact cell the PDF renders. Section, page-crossing, multi-hop, distractor
and semantic-control questions are authored explicitly.

## 4. Category distribution

72 questions: 64 answerable, 8 unanswerable.

| category | count | structural | description |
|---|---:|---:|---|
| `table_row_cell` | 20 | yes | value in a specific table row/column |
| `section_heading` | 12 | yes | answer depends on the owning section/subsection |
| `page_crossing` | 8 | yes | heading and answer body on different pages (verified) |
| `multi_hop_structural` | 8 | yes | section → subsection → table → row → cell |
| `structural_distractor` | 8 | yes | same term/count in several structural locations |
| `semantic_control` | 8 | no | distinctive fact, answerable semantically |
| `unanswerable` | 8 | n/a | no supporting evidence anywhere |

Structural questions (the five structural categories): **56**.
Primary structure subset (`DISCRIMINATING`): **32**.

## 5. Structural dependency criteria

A question is *structural* when a semantic retriever can plausibly reach the
right *text* but the wrong *structural location*:

- **table/row/cell** — the answer is a cell; correct reading requires keeping
  the row label and the column header together (the production *legacy* chunker
  splits long tables, and row labels such as `Pump A`–`Pump E` recur across
  tables).
- **section/heading** — the same term (`Kestrel frame`, `Sampling Protocol`)
  appears under more than one heading with different answers; the section
  identity disambiguates.
- **page-crossing** — the heading is on page *N* and the answer body on page
  *N+1*; the continuation chunk does not carry the heading under the legacy
  chunker.
- **multi-hop** — the answer requires combining a section context with a table
  row that also exists under a different parent section (Primary vs Secondary
  Loop both contain `Pump Specifications`).
- **distractor** — identical or near-identical text in several locations, only
  one of which is in the correct structural context.

Each answer's structural requirement is recorded explicitly as
`expected_structural_path` plus the gold element ids, e.g. a table-cell answer is
`document → section → table → table_row → table_cell`.

## 6. Anti-leakage / discrimination gate

Every answerable question was passed through the gate:

> Could a semantic-only chunk retrieval system answer this question correctly
> without knowing the structural relationship?

| label | count | meaning |
|---|---:|---|
| `DISCRIMINATING` | 32 | structural knowledge plausibly required |
| `WEAKLY_DISCRIMINATING` | 24 | structural structure helps but may not be necessary |
| `NOT_DISCRIMINATING` | 8 | semantic control, no structural dependency |

Per category: `page_crossing`, `multi_hop_structural` and
`structural_distractor` are fully `DISCRIMINATING` (8 each); `table_row_cell` is
5 `DISCRIMINATING` / 15 `WEAKLY_DISCRIMINATING`; `section_heading` is 3
`DISCRIMINATING` / 9 `WEAKLY_DISCRIMINATING`; `semantic_control` is
`NOT_DISCRIMINATING`.

Only the 32 `DISCRIMINATING` questions form the **primary** structure subset for
the future experiment. Weak questions are **not deleted** — they are retained
and reported here as excluded/reviewed (see §9) so the pre-registered subset is
explicit.

## 7. Gold annotation policy

- Every answerable question records `document`, `question`, `answer`,
  `answerable=True`, acceptable paraphrases, evidence substrings, gold element
  ids, gold table-cell ids (table questions), the expected structural path, and
  the expected evidence type.
- Gold element ids are authored structural ids using the schema vocabulary. They
  are resolved to persisted elements at scoring time — the retriever is never
  given the gold ids.
- Unanswerable questions carry **no** gold evidence, no expected answer and no
  discrimination label.
- No label is derived from a model or from a retrieval run.

## 8. Validation results

`validate_corpus` returns **VALID** with zero errors. It checks:

- the element-type and relation vocabularies match `graph.models`;
- every element type is in the vocabulary, `page_number ≥ 1`, `sequence_index`
  unique per document;
- every parent exists and stays within the same document; table `cell → row →
  table` chains are valid;
- every gold element and gold table cell exists and belongs to the question's
  document (no cross-document references);
- answerable questions carry answer + acceptable answers + evidence + gold;
  unanswerable questions carry none;
- question ids and texts are unique;
- page-crossing questions' gold actually spans more than one page.

Reported summary:

```
corpus structure-discriminating-v1
  documents: 4
  elements: 210
  questions: 72
  answerable: 64
  unanswerable: 8
  structural: 56
  discriminating: 32
  excludedWeak: 32
  categories: multi_hop_structural 8, page_crossing 8, section_heading 12,
              semantic_control 8, structural_distractor 8, table_row_cell 20,
              unanswerable 8
  discrimination: DISCRIMINATING 32, WEAKLY_DISCRIMINATING 24, NOT_DISCRIMINATING 8
VALID
```

## 9. Excluded questions

The 32 questions not in the primary subset are retained and listed by id in the
validator/`build_corpus` output; they are the `WEAKLY_DISCRIMINATING` (24) and
`NOT_DISCRIMINATING` (8) questions:

- `table_row_cell` weakly discriminating: `at_tbl_1..5`, `ac_tbl_1..5`,
  `fs_tbl_1..5` (15) — unique cell values that a chunk retriever will often get
  right.
- `section_heading` weakly discriminating: `at_sec_1..6`, `os_sec_1`,
  `os_sec_2`, `ar_sec_1` (9).
- `semantic_control` not discriminating: `at_sem_1`, `at_sem_2`, `fs_sem_1`,
  `fs_sem_2`, `ar_sem_1`, `ar_sem_2`, `os_sem_1`, `os_sem_2` (8).

Analysing the primary subset **and** the excluded set separately is required so
that a positive result cannot be manufactured by weak questions, and so that a
null result cannot be hidden by them.

## 10. Known limitations

- **Synthetic documents.** The PDFs are authored programmatically; they are real,
  parseable PDFs but not naturally occurring documents.
- **Parser coverage.** The current PDF parser emits only `section`, `paragraph`,
  `table` and `text_block`. `table_row` / `table_cell` (and `page`, `figure`,
  `list`, `list_item`) are valid schema vocabulary but are **not emitted today**,
  so the persisted structure will not contain row/cell nodes; gold row/cell
  coordinates will have to be resolved from `table.table_data` at scoring time.
- **Discrimination is a design judgement**, not a measured property. The label
  predicts that semantic retrieval is at risk; the future experiment must test
  that prediction rather than assume it.
- **Size.** 72 questions, 4 documents — enough to be non-trivial, not a
  large-scale benchmark.
- The legacy production chunker does not populate `heading_path`/`section`, so
  heading/section seeding is inert; the live structural signal is the
  element-level stream. This corpus cannot by itself change that configuration.

## 11. Why this corpus can test the research hypothesis

Unlike `phase3d`/`heading`, a substantial pre-registered subset (`32`
`DISCRIMINATING`, plus the page-crossing/multi-hop/distractor families) is
constructed so that the correct answer depends on a structural relationship
(table row/column alignment, section identity, page continuation, or
section→subsection→table→row traversal). If structure-aware retrieval helps
anywhere, this corpus gives it a fair, pre-registered opportunity to show it;
if it does not, the null result is stronger than before.

This is an opportunity to test the hypothesis, **not proof of it**. No
improvement is claimed here, and none should be claimed until the A/B/C/D
ablation has been run on this corpus with the established denominator
methodology.
