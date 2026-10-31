# Educational annotation pilot v1 — draft

This pack contains **20 AI-assisted annotation drafts**, not an independently
reviewed benchmark. There are four questions in each category and 7/7/6 questions
designated for 5/10/15 marks. All independent review fields are empty. No human
marks, retrieval scores or performance improvement have been measured.

## Real source and attribution

The source is **College Physics, first edition**, Paul Peter Urone and Roger
Hinrichs, OpenStax/Rice University, 2020. Access for free at openstax.org.

- Official book: https://openstax.org/details/books/college-physics
- Official publisher metadata: https://openstax.org/apps/cms/api/books/college-physics/
- Pinned PDF: https://assets.openstax.org/oscms-prodcms/media/documents/College_Physics-WEB_2s5sHvR.pdf
- License: **CC BY 4.0**, https://creativecommons.org/licenses/by/4.0/
- Raw PDF SHA256: `e4e91aa48b4e95ccdbac33ae938dae7e890bc0e123796635052bcafe53301671`
- Raw source: 264,102,523 bytes, 1,568 PDF pages; downloaded 2026-10-31.

The official metadata and PDF copyright page 4 both state CC BY 4.0 for this
first edition. Do not substitute the currently differently licensed second
edition. `source_catalog.json` preserves the relevant publisher metadata.
OpenStax trademarks and third-party art have separate rights; no images are
redistributed in this pack. Source extracts and the disclosed table transcription
are distributed with the above attribution and CC BY 4.0 license. Any display or
export of a canonical source page must retain its `attribution` field, including
“Access for free at openstax.org.” This source license does not relabel the
application's code license.

The pilot corpus consists only of the **42 selected PDF pages** in `dataset.json`:
862–884, 906–919 and 937–941. File page numbers are one-based; printed textbook
labels are 18 lower. Other parts of the complete textbook are not available to
pilot retrieval or used to decide whether a question is answerable in this pack.
This is one development bundle, not the proposed multi-subject benchmark.

## Extraction and evidence identity

PyMuPDF `get_text(sort=True)` extracts the born-digital pages. Before annotations,
horizontal whitespace is folded to one space, lines are trimmed and runs of blank
lines reduced. Each resulting canonical page has a SHA256. Source intervals are
zero-based Unicode code-point offsets in that frozen page text, with exclusive
ends. Exact quotes and quote hashes are included. Do not edit canonical text after
review; any change creates a new dataset release and requires remapped spans.

The PDF text layer omits many mathematical glyphs and numeric table cells. This is
an observed extraction limitation, not scanned-page OCR. The silver/copper rows,
units and temperature in Table 20.1 were visually transcribed from original PDF
page 871 by the coding agent and appended as an explicitly marked **draft visual
transcription**. Its page-region provenance and correction history are recorded.
It still requires the two independent subject reviews. Other missing formulas
were not silently repaired; questions avoid depending on their lost glyphs.

Required evidence units contain alternatives. A unit is covered only when **all
spans in one complete alternative** are available. An incomplete relation chain
or a table heading without the relevant values does not count. Questions spanning
the end of one page and start of another keep both spans. This pack contains 45
annotated span entries; these are draft requirements, not adjudicated gold.

## Independent annotation workflow

Use the two blank `reviewer_1.csv` and `reviewer_2.csv` worksheets. They are
**annotation worksheets, not answer-grading or NHRS ratings**.

1. Recruit two qualified physics/electrical subject reviewers. Record qualifications
   privately and use pseudonymous reviewer IDs in released artifacts. The coding
   agent is not a qualified independent reviewer and fills neither slot.
2. In the first pass, each reviewer works independently from the questions and
   the attributed source PDF/pages. Keep the AI draft reference answers, evidence
   and rubrics closed. Independently propose answerability, category, evidence
   spans, reference answer and marking criteria in the worksheet fields.
3. Reviewers then compare their initial annotations with the AI drafts. Check
   every unit for sufficiency, entity binding, negation and conditions; check table
   values against the rendered original. Confirm category labels and the
   256-token window rule with the frozen benchmark tokenizer. Proposed categories
   and difficulty labels are not validated by format checks alone.
4. For distributed single-topic questions, check that complete required evidence
   truly cannot fit in one allowed window. For multi-topic synthesis, confirm two
   topics are necessary. For relational items, confirm at least two indispensable
   explicit relations across topics; these drafts use electrical causal chains,
   which may need revision if the final graph-question definition is narrower.
5. For unanswerable items, explicitly identify the absent information within the
   selected corpus. Do not import outside textbook chapters or prior knowledge
   to manufacture source support. Approve a safe-abstention rubric separately.
6. Confirm criterion maxima sum to the designated marks and that partial-credit
   and factual-error rules are clear. Mark labels are expectations for grading,
   not a promise that every draft already meets an examiner's standard.
7. Preserve both initial annotations. A third qualified reviewer adjudicates
   material disagreement. Record all revisions and rerun integrity checks before
   freezing a reviewed release. Merely filling two names is not independent review.

The future answer-quality study must use separately randomized anonymous generated
answer IDs, two independent graders, agreement measurement and no system labels.
Those ratings must not be confused with this annotation pilot's blank worksheets.

## Checks and reproducibility

From `backend/`:

```powershell
venv/Scripts/python.exe -m evaluation.pilot_v1.build_pilot --check
venv/Scripts/python.exe -m evaluation.research_scoring validate --dataset evaluation/pilot_v1/dataset.json
```

The first check validates counts, page/quote hashes, end-exclusive offsets, rubric
totals, answerability consistency and blank review status. It does not certify
scientific annotation quality. The second command uses the shared research
dataset validator when that tool is present.

The existing `dataset.json` is the released draft snapshot. To reconstruct it in a
fresh directory, `build_pilot.py --acquire` can download the pinned official PDF
and extract it; it refuses a changed source hash and never overwrites an existing
dataset. Without `--acquire`, building requires the existing local PDF and has no
network activity. Re-extraction depends on the recorded PyMuPDF version; compare
canonical page hashes, not just a successful command exit.

With the cached PDF present, rebuild safely into a new ignored file and check it:

```powershell
venv/Scripts/python.exe -m evaluation.pilot_v1.build_pilot --output evaluation/pilot_v1/source_cache/rebuilt_NEW.json
venv/Scripts/python.exe -m evaluation.pilot_v1.build_pilot --check --output evaluation/pilot_v1/source_cache/rebuilt_NEW.json
```

Every rebuild verifies the full PDF SHA256 before extraction. A changed source
requires a new reviewed release; the helper will not silently accept it. The
published draft and a rebuild must match as decoded JSON; formatting/newline bytes
of the outer JSON container are not canonical page content.

`source_cache/` is ignored and contains the 264 MB original PDF, temporary text
inspection files and two rendered verification pages. It is not committed or
uploaded as application data. The production database, user uploads, model weights,
environment files and previous evaluation artifacts are untouched.

## Known coverage gaps

- One electricity bundle is not representative of four subjects or 24 independent
  source bundles. It supports development/pilot preparation only.
- Real tables, repeated running headings/subheadings, formulas and page-crossing
  topics occur in the source. Numeric table transcription needs independent review.
- **No scanned pages or conflicting revisions** occur in the selected corpus;
  those required broader-benchmark strata remain unfilled. No simulated image or
  invented conflicting claim is labelled real educational evidence.
- Questions, reference answers, evidence units, difficulty and rubrics remain
  unreviewed drafts. They cannot support confirmatory RER, NHRS or ECT claims.
