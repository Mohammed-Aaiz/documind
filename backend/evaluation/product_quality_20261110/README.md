# Private product-quality development pilot

This is a new development check on one user-supplied course document. It does
not alter the frozen DocuMind research benchmark. Source notes, reference spans,
candidate answers, reviewer packets and ratings belong in ignored `local_run/`.
The source's redistribution rights have not been established; do not publish
those artifacts or assume the project code license covers the notes.

The twelve draft rubrics cover VAWT, HAWT, two-part HAWT/VAWT diagrams with an
alignment comparison, and an unsupported project-specific capacity/date query,
each at 5, 10 and 15 marks. Canonical PDF text and exact evidence offsets are
validated before capture. Rubrics are AI-assisted drafts requiring subject review.

From `backend/`, using the existing environment:

```powershell
venv/Scripts/python.exe -m evaluation.product_quality_20261110.run prepare --source-pdf 'C:/Users/moham/Downloads/module 4.pdf' --annotation-spec evaluation/product_quality_20261110/local_run/annotation_spec.json --output evaluation/product_quality_20261110/local_run/new_dataset.json
```

The private annotation specification contains the independently authored question,
reference-answer and rubric drafts, source identity, evidence spans and pinned
canonical-page hashes. It is supplied separately; the public tool contains no
course-note quotations. `prepare` verifies the original PDF and extraction hashes
and refuses to replace an existing output. The original frozen `dataset.json`
is preserved. This pilot's ignored directory retains the exact capture runner
snapshot and hash separately from later public-tool cleanup.

`capture` runs inside the configured backend container with a copied private
dataset and this runner on `/tmp`. The production image excludes evaluation
code; copy the stdlib-only `evaluation/research_scoring.py` and package
`__init__.py` into `/tmp/documind-eval-tools/evaluation`, then use
`PYTHONPATH=/tmp/documind-eval-tools:/app`. It finds exactly one
ready indexed document matching the pinned raw PDF hash, then calls the product's
stateless retrieval/generation service in a READ ONLY database transaction. It
does not write chats, user data, indexes or schema. Credentials stay in the running
service configuration and are never exported. By default it pauses 30 seconds
between questions; provider errors are recorded, not hot-retried or replaced
with made-up answers. An explicit `--question` subset supports bounded captures.
Every output path is new; checkpoints preserve partial failure evidence.

The captured path is `generation.service.run_generation`, not the browser's SQL
conversation wrapper. It therefore does not establish conversation-memory,
persisted-turn, or voice behavior. Raw empty API answers remain empty in the
run; reviewer packets identify their bracketed display placeholder explicitly
and never treat it as a generated abstention explanation.

```powershell
# Inside the backend container, after copying the runner and dataset to /tmp:
PYTHONPATH=/tmp/documind-eval-tools:/app python /tmp/documind-quality-run.py capture --dataset /tmp/documind-quality-dataset.json --output /tmp/documind-quality-candidates.json --code-commit COMMIT_ID

# Back on the host after copying the run into ignored local_run/:
venv/Scripts/python.exe -m evaluation.product_quality_20261110.run export --dataset evaluation/product_quality_20261110/local_run/dataset.json --run evaluation/product_quality_20261110/local_run/candidates.json --output evaluation/product_quality_20261110/local_run/review
```

Two separately tasked AI reviewers receive only `blind_ai_packet.json`, not the
private mapping or each other's grades. Their criterion totals are checked by:

```powershell
venv/Scripts/python.exe -m evaluation.product_quality_20261110.run ai-summary --packet evaluation/product_quality_20261110/local_run/review/blind_ai_packet.json --reviews evaluation/product_quality_20261110/local_run/review/ai_reviewer_1.json evaluation/product_quality_20261110/local_run/review/ai_reviewer_2.json --output evaluation/product_quality_20261110/local_run/review/ai_summary.json
```

AI normalized rubric scores are labelled as diagnostic and never called NHRS.
Same-family model errors and AI-authored rubric errors remain possible. This
small slice supports failure analysis, not statistical improvement claims.

For human grading, open the two self-contained HTML reviewer files separately.
Each qualified reviewer starts from blank scores, grades independently using
the source/rubric, and downloads their ratings CSV plus attestation JSON. The
HTML uses escaped source text, has no external assets or network calls, and
preserves incomplete answers as pending. Reviewer expertise and independence
require external verification; software does not establish them.

The existing `evaluation.research_scoring review-summary` command can validate
CSV identities and compute scores once both genuine reviews are supplied with
the private mapping. Blank sheets remain `not_measured`. Do not feed AI ratings
into that human-only command. Unanswerable safe-abstention grades remain separate
from answerable academic-quality summaries. No primary RER or ECT1000 result is
claimed here because this runner does not certify canonical retrieval mapping
or exact provider-context token counts.
