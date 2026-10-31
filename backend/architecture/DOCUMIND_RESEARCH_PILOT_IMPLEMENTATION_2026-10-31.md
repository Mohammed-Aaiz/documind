# Research pilot implementation — 2026-10-31

Status: implementation record for the owner's instruction to execute the next
benchmark-development step. The governing protocol remains
`DOCUMIND_BENCHMARK_SPECIFICATION_V1.md`. H1–H4 are hypotheses, not results.

## Scope and ownership

The Coordinator defines acceptance and records evidence. EVALUATION_AGENT owns
the new pilot pack, measurement module and controlled retrieval adapters under
`backend/evaluation/`; TEST_AGENT owns any new pytest checks; VERIFIER independently
checks the delivered artifacts. Existing production retrieval/provider code,
database schema, user uploads, environment files, old research reports and the
frozen source baseline are outside this change.

Ponytail is applied by reusing current retrieval primitives and installed
libraries. No new production RAG technique, provider or dependency is introduced.
The educational pilot is development material. No template, generated answer or
model opinion substitutes for independent human annotation or grading.

## Acceptance criteria

1. Twenty real-source, explicitly unreviewed draft questions, four per specified
   category, with designated 5/10/15 marks balanced 7/7/6, reference answers,
   source-span offsets, topic/page references, rubrics and two empty reviewer slots.
   Source license, attribution, raw/canonical hashes and extraction provenance
   are recorded. Unsupported layout/conflict coverage is disclosed.
2. Evidence-unit recall evaluates sufficient ALL-span bundles with OR alternatives
   against final context, joining covered source intervals without filling gaps.
   Wrong revisions, ambiguous mappings, missing table labels and uncovered spans
   receive no invented credit. Draft labels yield diagnostic measurements only.
3. Context efficiency uses the complete serialized evidence and an explicitly
   identified local generation tokenizer with no truncation. Token estimates and
   embedding tokenizers never become primary ECT scores. The runtime cannot
   silently download assets or execute remote tokenizer code.
4. Grading exports conceal system identities and keep the assignment map private.
   NHRS requires two distinct completed human ratings per answer; blank ratings
   stay pending. Invalid scores and duplicate reviewer assignments are rejected.
5. Seven research comparison paths share the same relevant controls and preserve
   single-factor ablations. They reuse production primitives, require a read-only
   session for live retrieval, and explicitly identify departures from the full
   production table/visual/neighbor orchestration. Wiring checks do not become
   evidence of comparative retrieval effectiveness.
6. Run meaningful offset/metric/grading/ablation checks, preserve immutable
   outputs, and report limitations before pushing only this task's changes.

## Research documentation consulted

Context7 `/huggingface/transformers` was consulted for offline tokenization:
[AutoTokenizer loading](https://github.com/huggingface/transformers/blob/main/src/transformers/models/auto/tokenization_auto.py)
supports local-only loading and disabling remote code; full evidence token
counting requires truncation disabled. The
[official GPT-OSS-20B tokenizer configuration](https://huggingface.co/openai/gpt-oss-20b/blob/main/tokenizer_config.json)
identifies a fast tokenizer. A pinned tokenizer can count local evidence strings;
that alone does not certify a hosted provider's complete chat serialization or
billing behavior. Provider usage and context-only token counts stay distinct.

## Scientific gates retained

Independent subject review and independent human grading require actual qualified
reviewers. The source pack may be validated mechanically without being reviewed
scientific gold. The proposed 360-question benchmark does not exist merely because
this pilot contains twenty drafts. No statistical improvement, exam grade or
production-readiness conclusion follows from passing software checks.

## Delivered preparation artifacts

- `backend/evaluation/pilot_v1/README.md`: source attribution, extraction limits,
  annotation instructions and commands. The pack contains 20 AI-assisted drafts,
  four per category, with 7/7/6 designated 5/10/15-mark questions, 42 canonical
  source pages and 45 span entries. Two independent annotation worksheets are
  blank. The source is OpenStax *College Physics*, first edition, CC BY 4.0;
  source metadata and PDF copyright page 4 were checked. The original PDF hash
  is `e4e91aa48b4e95ccdbac33ae938dae7e890bc0e123796635052bcafe53301671`.
- `backend/evaluation/research_scoring.py` and its Markdown run guide: exact
  interval RER, OR/ALL support alternatives, frozen-tokenizer ECT, JSONL evidence
  mapping, anonymous grading export and protected human-score import. Reports
  remain diagnostic unless the dataset has the explicit reviewed/frozen release
  status and two distinct completed independent annotation approvals. Primary
  NHRS requires two distinct actual human grades, not annotation approvals.
- `backend/evaluation/research_retrieval.py`: seven controlled text compositions
  reusing existing production retrieval primitives, common controls and prompt
  fitting, with graph/reranker readiness guards. The code exposes `compare()` and
  lazy `production_functions()`; it does not insert this pilot into production.
  Reuse one functions factory across all arms of a run: routing is frozen once
  per exact question in that factory, returned by copy and fingerprinted so
  provider sampling or cache expiry cannot silently reclassify an ablation.
- `backend/evaluation/assets/gpt-oss-tokenizer/`: explicit tokenizer-only
  provisioner and checksum manifest. Pinned repository revision is
  `openai/gpt-oss-20b@6cee5e81ee83917806bbde320786a8fb61efebee`. No weights or
  new dependency were downloaded. Runtime loading verifies hashes and stays
  offline. The four local tokenizer/config assets are ignored by Git.
- `backend/tests/unit/evaluation/test_research_pilot.py`: focused software
  regressions for annotations, metric denominators, blinding, grade integrity,
  immutable routing and the seven comparison paths.

The downloaded 264 MB PDF, inspection renderings and temporary rebuild outputs
are ignored under the pilot's `source_cache/`; they are not publication artifacts.
Private answer-to-system mappings and real reviewer qualification records must
also stay outside the published research artifacts. An ignored local cache path
is available for these files; do not share a private mapping with graders.

## Reproduce the completed checks

From `backend/`, using the existing Python environment:

```powershell
venv/Scripts/python.exe -m evaluation.pilot_v1.build_pilot --check
venv/Scripts/python.exe -m evaluation.research_scoring validate --dataset evaluation/pilot_v1/dataset.json
venv/Scripts/python.exe -m evaluation.research_scoring self-check
venv/Scripts/python.exe -m evaluation.research_retrieval self-check
venv/Scripts/python.exe -m evaluation.research_retrieval configs
venv/Scripts/python.exe -m pytest -q tests/unit/evaluation/test_research_pilot.py
```

The draft dataset validation and both module self-checks passed. The final focused
suite passed 42 tests with no skips; existing pytest fixture deprecation warnings
remain. Source rebuild equality was checked against the hash-verified cached PDF.
Local tokenizer checks counted empty context as zero, a Unicode sample as 11,
and an 80,000-character string as 40,001 tokens without truncation. These are
accounting checks, not educational-quality measurements. The existing production
evaluation self-check also passed, and no production-path diff was observed.

The prompt-to-adapter-to-scorer regression uses real JSONL escaping of newline,
quotes, Unicode and backslash characters. Evidence credit comes from decoded
source text, while the denominator counts the unchanged serialized JSONL. Text
appearing only in metadata is not credited. Human grading imports reject changed
question/answer/rubric/evidence content, invalid scores and duplicate graders.
Draft datasets with filled approval fields still cannot masquerade as a reviewed
release. This last gate and frozen routing were added after independent review.

## Limits before live comparative execution

There are **zero independent human annotations and zero human answer grades**.
The pilot is one electricity bundle, not the proposed multi-subject 360-question
dataset. It has real tables, repeated headings and page-crossing passages but
no genuine scanned pages or conflicting revisions. A table's missing numeric
glyphs were visually transcribed by the coding agent, checked against the PDF
by the software verifier and explicitly left for qualified human review.

The seven paths are a controlled text composition, not a claim of exact full
production parity: table/visual/15-mark neighbor extras are held off in every
arm and common base retrieval runs even when the router predicts graph-only.
The fixed-parent baseline targets 1,024 embedding tokens using indivisible child
buckets; child boundaries can cross that target. Full message-budget checks use
exact text counts plus an explicit chat-overhead proxy, not independently verified
Groq chat serialization. ECT is exact for the pinned local evidence tokenizer;
the hosted model alias's continuing equivalence is externally unverified.

No live seven-system educational benchmark was executed. It requires an isolated,
versioned index of the selected source corpus, source-ID/interval mapping that
matches canonical hashes, frozen graph extraction and a read-only comparison
session. Missing graphs or components block an arm instead of becoming a silent
fallback. Current results establish preparation-tool integrity only. The next
scientific gate is qualified independent annotation of the pilot, followed by
the isolated mapped-index smoke run; no production algorithm change is justified
by these software checks.
