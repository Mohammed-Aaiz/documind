# Isolated live pilot diagnostics

This is an executed development diagnostic, **not a reviewed benchmark or proof
of H1–H4**. It uses the twenty unreviewed OpenStax pilot questions and canonical
source pages. Human annotation correctness and NHRS remain unmeasured.

## Isolation and reproducibility

`run.py` cannot create, migrate, drop or reset a database. The database owner must
first provision the separate local `documind_pilot_20261101` target at Alembic 018,
with the exact database comment `documind-isolated-pilot-20261101`. The runner
rejects a product configuration with that database name, including loopback host
aliases. It requires an explicitly supplied `DOCUMIND_PILOT_DATABASE_URL`; never
save or print that credential. The database owner's
`scripts.local_database_ops.pilot_database_url()` helper can supply it in memory.

The `seed` command accepts only an empty marked target. It creates an inactive
research account and imports only the openly licensed pilot's 42 canonical pages.
No production account, upload or index is modified. Source paragraphs and actual
heading text are imported deterministically; annotations, reference answers,
required evidence and gold topic IDs are never used to construct the index.
Production structure-v2 chunking, the pinned MiniLM encoder, parser persistence
and document-graph primitives build the index. This is a **canonical-text
retriever study**, not an end-to-end PDF/OCR study. The known AI table correction
and extraction limits remain those disclosed in `pilot_v1/README.md`.

The index contains 151 real vector children, 536 paragraph elements, 30 section
elements and 952 chunk-level structural edges. There are no persisted
structure-element edges, matching the production ingestion primitive used here.
150 children have nonempty heading/section metadata; all 151 retain source-element
membership. The immutable index manifest maps 717 chunk/element identities to
exact canonical source intervals, retaining the dataset hash and encoder identity.

Source license: OpenStax *College Physics*, first edition, Paul Peter Urone and
Roger Hinrichs / Rice University, 2020, CC BY 4.0. Access for free at openstax.org.
Source attribution is included in the parent pilot pack and must be preserved.

## Explicit operations

From `backend/`, after the isolated URL is supplied privately:

```powershell
venv/Scripts/python.exe -m evaluation.pilot_live.run seed --output evaluation/pilot_live/INDEX_NEW.json
venv/Scripts/python.exe -m evaluation.pilot_live.run graph-batch
venv/Scripts/python.exe -m evaluation.pilot_live.run status --output evaluation/pilot_live/STATUS_NEW.json
venv/Scripts/python.exe -m evaluation.pilot_live.run run --index evaluation/pilot_live/index_20261101.json --output evaluation/pilot_live/RUN_NEW.json.gz --scores evaluation/pilot_live/SCORES_NEW.json
```

Every artifact path must be new. The seed is not repeatable against a populated
target and never replaces an existing index. Each graph batch uses the existing
bounded, resumable Groq extractor on source chunks, never on gold annotations.
An HTTP 429 preserves the validated prefix; wait for the account's rate window
before issuing another explicit batch. Do not use an automatic hot retry loop or
mark a partial graph as ready. The `run` command uses a read-only transaction,
exact cosine baseline, common cross-encoder, frozen per-question router decisions,
the official pinned GPT-OSS tokenizer and the seven controlled text compositions.
Missing graph coverage blocks dependent arms instead of silently disabling them.

An optional repeated `--system` limits a diagnostic run, for example `--system
dense --system hybrid --system parent`. Those three arms make no Groq calls.
The controlled compositions hold visual/table/15-mark neighbor extras off in
every arm and are explicitly not identical to full product orchestration.

## Mapping and score interpretation

The seed records source body offsets separately from repeated heading prefixes.
The final excerpts are mapped only after retrieval and prompt fitting. Unchanged
content maps to its exact canonical interval; a heading prefix alone does not
claim an absent paragraph. If the production fitter changes whitespace while
joining retained sentences, only literal monotonic fragments are credited and
the record is marked `exact_fragment_lower_bound`. Changed gaps are not filled,
and ambiguous snippets receive no source credit. The full original serialized
context remains in the token denominator, including uncredited text and labels.
Reports expose mapping caveats rather than silently relaxing gold-span rules.

RER and ECT use the draft labels, so all scores remain diagnostic. Four pilot
questions are unanswerable and therefore have undefined RER/ECT. No generated
answers or human grades are invented. Routing decisions are frozen within each
comparison factory instance; new runs have new provider sampling history. Single
passes do not establish warm/cold p95, statistical significance or general course
quality. Graph extraction quota is an external availability constraint.

## Artifacts

- `index_20261101.json`: source-index mapping and source/model identities.
- `status_seed_20261101.json`: measured index metadata and early graph coverage.
- `baseline_20261101.json.gz`: actual read-only 60-record dense/hybrid/parent run,
  twenty queries per arm, with no failed records.
- `baseline_scores_20261101.json`: draft diagnostic scores for that run. Nine
  records have explicitly conservative fitter-fragment mappings. These earlier
  immutable artifacts are retained even if a later full comparison is added.

The compressed raw run preserves actual contexts, stage traces and configuration
fingerprints. Decode it with Python's standard `gzip` and `json` modules. This
directory contains no database URL or key; model/tokenizer weights are not copied
into research artifacts. Independent subject review and a later frozen reviewed
release are still necessary before publishing research conclusions.
