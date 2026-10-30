# DocuMind Benchmark Specification v1.0

Date: 2026-10-30. Status: DECIDED research direction; PROPOSED experimental
protocol until the annotation pilot and preregistration are complete. No results
are asserted. This records the owner's Research Framework v1.0 and supersedes
feature accumulation as the research priority. Production availability and
historical research conclusions retain their separately recorded status.

**Research title:** Evidence-Complete and Context-Efficient Retrieval-Augmented
Generation for Long, Multi-Topic Educational Documents — Using Structure-Aware
Hierarchical Retrieval and Knowledge Graphs.

## 1. Scope and acceptance of this deliverable

Optimize three distinct outcomes: required evidence completeness, independently
graded academic answer quality, and useful evidence per context token. Do not
collapse them into a generic RAG accuracy score. Hypotheses remain unconfirmed
until executed, reviewed experiments support them. Existing hierarchy and graph
techniques are established approaches, not novelty claims by themselves.

This first deliverable defines annotations, comparisons, metrics, controls,
statistics, failure analysis and a reproducibility protocol. Companion offline
manifest tooling and a synthetic annotation template support preparation. It is
not a claim that 360 questions exist, that seven controlled adapters work, that
human reviewers have graded answers, or that a research contribution is proved.
No production retrieval, prompt or provider behavior is changed for this step.

Acceptance: freeze the current source/model/configuration identities honestly;
define the evidence denominator without reference to retrieved chunks; specify
all seven comparisons without hidden component changes; distinguish tool-ready
work from pending annotation, adapters and experimental execution.

## 2. Objectives, hypotheses and primary contrasts

| Objective | Primary outcome | Hypothesis and prespecified comparison |
|---|---|---|
| A: evidence completeness | Required Evidence Recall (RER), measured after prompt fitting | H1: Full DocuMind versus DocuMind without topic expansion, paired on answerable questions. Conventional fixed-chunk dense/hybrid comparisons provide external baselines, not a single-factor causal attribution. |
| A: relational completeness | RER on the independently labelled relational subset | H2: Full DocuMind versus DocuMind without entity-relation graph, with identical non-graph stages. |
| B: academic quality | Normalized Human Rubric Score (NHRS), separately for 5/10/15 marks | H3: Full DocuMind versus Hybrid RAG under a common generator and blinded independent grading; report paired RER/NHRS changes and their association. Association alone does not prove evidence completeness caused the grading difference. |
| C: context efficiency | Evidence units covered per 1,000 context tokens (ECT1000), alongside RER | H4: a future question-aware assembler versus indiscriminate parent expansion, holding the candidate pool and all other stages constant. This arm is not implemented or credited as existing merely because passages are reranked. |

H4 algorithm development begins only after baseline failures identify excess
context or lost evidence. Freeze its definition before the held-out comparison.
Do not use gold evidence, reference answers or rubrics to select runtime context.

## 3. Corpus and proposed 360-question design

Target 24 independent document bundles across four subject areas, six bundles
per area and approximately 15 questions per bundle. A bundle contains the
educational source material necessary for its questions; prefer genuinely long,
multi-topic lecture notes, chapters or course reports, not concatenated unrelated
snippets. Record actual pages, topic counts, tokens, document lengths, language,
source permissions and subject coverage. This target is a design, not collected
data. Start with English; other languages require a separate declared stratum.

| Exclusive primary category | Total | Development | Held-out test | Operational rule |
|---|---:|---:|---:|---|
| Localized single-topic | 60 | 10 | 50 | One topic; complete minimal evidence fits within a 256-token annotated source window. |
| Distributed single-topic | 90 | 15 | 75 | One topic; the required evidence cannot all fit in one such window. |
| Multi-topic synthesis | 90 | 15 | 75 | At least two topic IDs are necessary, without an indispensable entity-relation chain. |
| Relational / multi-hop | 60 | 10 | 50 | Requires an explicit chain of at least two source-supported relations across at least two topics. Annotate all required edges; aim to split single-document and cross-document cases equally. |
| Unanswerable | 60 | 10 | 50 | The corpus does not supply a necessary answer requirement; reviewers agree what is missing and why. |
| **Total** | **360** | **60** | **300** | One primary category per question. |

Apply classification in this order: unanswerable, relational, multi-topic,
distributed single-topic, localized. Category decisions concern the question's
required evidence, not whether a particular retriever succeeded. The 256-token
category window uses one frozen benchmark tokenizer and is not a word count.

Assign one designated mark format per question: 120 each of 5, 10 and 15 marks
overall; 20 each in development and 100 each in test. Balance formats within
categories. A shared-question, cross-mark subset can be a separately registered
sensitivity study; do not silently treat three answer formats as independent
questions. Label difficulty independently using a written subject rubric.

Use overlapping diagnostic tags for tables, scanned/OCR pages, repeated headings,
conflicting revisions, page-crossing topics, formulas and cross-document facts.
Aim for at least 30 reviewed examples for each required layout/conflict tag;
overlap is allowed and actual counts must be reported. Tags are not additional
exclusive categories. Insufficient tag coverage limits the corresponding claim.

Development/test separation is by document bundle, not random question. Allocate
one development and five test bundles per subject. Revisions, near duplicates,
shared passages and cross-document question dependencies must stay in the same
bundle; merge connected bundles before splitting and revise counts transparently
if necessary. Test source documents may be indexed, but test labels/reference
answers remain unavailable to developers and runtime components during tuning.

## 4. Annotation contract

Keep evidence identities independent of chunk IDs and database reprocessing.
Each dataset release records version, split, source rights, raw-file SHA256,
canonical page-text SHA256, extraction/OCR version and manual correction history.
Freeze canonical text as UTF-8 with explicit newline rules; offsets are zero-based
Unicode code points with an exclusive end. PDF page numbers are one-based file
page numbers; printed labels are additional metadata. Do not silently normalize
whitespace after annotation. A span carries exact quote, document revision,
page, start/end offsets and topic IDs. Tables include the necessary row/column
headers, units and cells. Diagram-only requirements also need page regions and
reviewed transcription/description; report their mapping method separately.

Each question records:

- Stable ID, bundle/split, question text, primary category, diagnostic tags,
  designated marks, difficulty and answerability.
- Independently authored reference answer and rubric, not copied from a tested
  system's answer; allowable alternative explanations and revision assumptions.
- Required evidence units: minimal independently meaningful requirements needed
  to answer this question, each with a stable ID and plain-language statement.
- For each unit, one or more alternative sufficient **bundles** of source spans.
  All spans within a bundle are required (AND); any complete alternative bundle
  is sufficient (OR). Deduplicate repeated statements into alternatives rather
  than adding denominator units. Retain negation, entity binding and conditions.
- Topic/page mapping and relation-path requirements, annotation reviewer IDs,
  independent initial decisions, adjudication notes and final release status.
- Mark criteria whose maxima sum exactly to 5, 10 or 15. Each criterion records
  content requirements, partial-credit anchors, error policy and relevant unit
  IDs. Allocate separate accuracy, coverage and organization credit explicitly;
  do not award marks merely for length, headings or citation count.

Example: a comparison requiring a value for material A and a value for material B
needs both relevant cells plus their labels/units. A retrieved table title alone
does not cover it. A multi-hop requirement may need two source spans in different
topics; one relation is insufficient. Preserve conflicting revisions together
when resolving the conflict is part of the question. Missing or unmapped spans
are not inferred from a matching passage ID or from a model's fluent claim.

Two qualified subject reviewers independently annotate evidence sufficiency and
rubrics. Pilot 20 development questions, refine the guide, then redo pilot labels
under the frozen guide. A third reviewer resolves material disagreement. Record
qualifications privately and publish pseudonymous reviewer identities. Adjudicated
gold has two completed reviews; blank template fields are not reviewed labels.
Freeze annotations before baseline scoring. LLM suggestions may assist annotation
but cannot count as an independent human review.

Fully unanswerable items have no complete gold evidence set and no RER/ECT value.
Record their missing requirements and grade safe abstention using an explicit
negative-question rubric. If partly answerable items are later added, label them
separately; available-evidence recall and missing requirements must not be mixed
into a denominator that pretends absent corpus evidence was retrievable.

## 5. Seven systems and fair comparison

All systems use the same source corpus, canonical evidence map, query IDs,
designated marks, embedding checkpoint, cross-encoder, generation model, prompt
template, context accounting, output allowances and failure policy. Runtime
components never see gold labels. Candidate depth and retrieval/index parameters
are fixed from development data, then hashed in a per-system manifest.

| System ID | Retrieval before common prompt fitting | Research role |
|---|---|---|
| dense | Dense vector candidates, common cross-encoder, no graph/parent expansion | Semantic baseline; also report raw dense ranking as a secondary diagnostic. |
| hybrid | Same dense candidates plus lexical ranks fused with RRF; common cross-encoder | Lexical contribution; PostgreSQL full text is not labelled BM25. |
| parent | Hybrid seeds with common reranker, then standard fixed parent recovery in full | Indiscriminate parent baseline; freeze parent boundaries and ordering. |
| graph | Hybrid plus quote-backed entity-relation traversal, common reranker, no topic expansion or document-structure traversal | Local graph-assisted baseline; not equivalent to Microsoft GraphRAG global/community summarization. |
| documind_no_topic | Full DocuMind with only topic/paragraph expansion disabled | H1 single-factor ablation. |
| documind_no_graph | Full DocuMind with only entity-relation graph path disabled | H2 single-factor ablation; document-structure traversal remains active. |
| documind_full | Frozen production structural retrieval, routing, graph assistance, reranking and topic assembly | Combined system. |

In matched-index experiments all seven share the existing structure-v2 child
index. This isolates retrieval/context mechanisms but **is not a fixed-chunk
baseline**. Add a conventional-baseline block using dense/hybrid/fixed-parent
systems on identical fixed windows of at most 200 MiniLM tokens with 32-token
overlap; parent windows target 1,024 tokens, bounded to one document. Use the same
canonical text, encoder, budgets and reranker. These separately versioned research
indexes must never overwrite the production index. Comparing that block against
production changes chunking as well as retrieval; describe it as an end-to-end
comparison. The matched-index no-topic contrast supplies the isolated test of H1.

Use exact cosine for the primary quality comparison; assess HNSW recall/latency
separately against that exact reference. Keep graph index, graph extraction model,
source coverage, traversal depth, entity normalization, fusion weights, routing
policy and failure state frozen across arms that use them. The no-graph arm must
not fall back into graph search. Log actual routing: a full system choosing the
semantic route on relational questions is a result to analyze, not permission
to inject an oracle route. Diagnostic forced-route runs must be labelled separately.

The frozen production system's table/visual/15-mark neighbor paths remain part
of its measured end-to-end behavior. Single-factor DocuMind ablations retain them
unchanged. In the strictly controlled text comparison hold those enrichments off
for every arm or identical for every arm, and label that experiment separately
from production behavior. Do not attribute a visual-parser gain to topic expansion.

Reference candidates: LlamaIndex HierarchicalNodeParser/AutoMergingRetriever and
Microsoft GraphRAG local search. Pin versions/configuration and use parity fixtures
before comparison. Library defaults may change embeddings, chunking or generation;
such runs are external-system comparisons, not controlled ablations. Neither
reference implementation is added as a production dependency in this step.

## 6. Primary metric definitions

For answerable question q, let Uq be its reviewed required evidence units. Let
Cq be the exact context excerpts surviving final prompt assembly. For each unit,
coverage is 1 only when Cq contains every required span in at least one accepted
alternative bundle. Join adjacent/overlapping intervals from the same immutable
source revision when testing coverage; an uncovered gap is not covered. Unit IDs
are counted once. No credit for a small lexical overlap, source-name match, graph
edge without its original supporting spans, or invented/paraphrased quotation.
Human-reviewed semantic equivalence can amend gold alternatives in a new blinded
dataset release, never selectively after identifying a losing system.

**RER(q) = covered required units / |Uq|.** Primary aggregate is macro mean over
answerable test questions. Report micro totals and per-category/mark distributions
secondarily. Also record retrieval-stage RER before fitting and candidate-pool RER:
their differences locate losses caused by ranking, expansion and truncation.
Ingestion/OCR failures still count against end-to-end RER; provide a separate
retriever-only diagnostic conditioned on correctly extracted evidence. Do not
exclude extraction failures to inflate the primary score.

**NHRS(q,s,r) = reviewer marks / designated maximum marks.** Grade each system's
answer independently using the same question-specific rubric. Primary question
score is the mean of two independent reviewers' normalized scores, before
adjudication; report adjudicated scores secondarily. Report means and uncertainty
separately for 5/10/15 marks, with category breakdowns. Keep fully unanswerable
questions' safe-abstention scores separate from answerable academic-quality NHRS.
Never substitute lexical verification, phrase coverage, an LLM judge or the
reference answer's similarity for a human grade.

**ECT1000(q) = 1000 × covered required units / context_tokens(Cq).** Use the same
frozen generation-compatible tokenizer for all systems and count the final
serialized evidence context, including source labels/headings/graph text and
duplicate text actually sent. Do not count the MiniLM embedding tokenizer as
Groq's tokenizer. Exclude shared instructions/question/history from this specific
denominator, but separately report full provider input/output/reasoning usage
and costs. Primary ECT is the macro mean over answerable questions with exact,
positive token counts; additionally report pooled covered units / pooled tokens.

An empty context has RER=0 but ECT undefined; report its count, do not drop its RER
or call empty output infinitely efficient. Unanswerable questions have undefined
RER/ECT. Approximate byte counts can be reported as diagnostic estimates only;
they cannot support a primary ECT result. If the exact tokenizer/serialization
is unavailable, mark ECT not measured and block an efficiency claim. Retrieval
duplicates cannot increase covered units but do increase tokens when actually
sent. Provider-reported total prompt usage alone does not identify context-only
tokens. Never silently subtract an estimated instruction count and call it exact.

Always pair ECT with absolute RER, complete-question fraction (RER=1), context
length and NHRS. Plot the RER/ECT/latency trade-off; a tiny relevant fragment
cannot justify an overall improvement when required evidence is missing.

## 7. Independent grading and agreement

Randomize anonymous answer IDs and presentation order; remove system names and
backend reliability scores. Preserve identical citation display rules. Reviewers
receive question, source material, rubric and answer, but not other reviewers'
scores or system outputs side by side. Dataset authors do not grade their own
items where feasible. Record and disclose conflicts or incomplete independence.

Target two qualified independent graders for all 300 held-out questions across
seven systems: 2,100 answers / 4,200 grading events. If resources restrict grading,
freeze a stratified random subset of 90 test questions before seeing outputs,
balanced across marks and categories: 630 answers / 1,260 grading events. Report
that subset's NHRS only; do not imply all 300 were human graded. Keep the same
questions across all systems, with no selection by which answers look strongest.

Report quadratic-weighted Cohen kappa separately by mark format for the two
fixed graders, plus raw agreement, mean absolute normalized disagreement and
95% intervals. Constant-rating/insufficient-data cases are undefined, not perfect
agreement. Resolve disagreements greater than 20% of maximum marks or factual
correctness/answerability conflicts with a third reviewer; preserve both original
ratings. If grader assignments change, revise the agreement method before grading
rather than treating unrelated rater pairs as one fixed pair.

## 8. Freeze, execution, latency and cost

The source baseline is commit `8f5926280cd30e3a64be662cf121fdcb0da74ef1`.
It is a code baseline, not a clean full-workspace/runtime snapshot: unrelated local
research edits exist. Record hashes of the actual sources used and distinguish
dirty working-tree contents from committed contents. Do not silently include
unrelated experimental code or environment secrets in the research release.

Freeze raw/canonical source hashes, dataset and label release hashes, production
and adapter commits, dependency distributions/locks, DB migration head/index
definitions/pgvector version, model revisions/checksums, OCR/layout settings,
prompts and parser/chunker policies. Record OS/CPU/RAM/GPU, threads, cold/warm
status, concurrency, routing caches, search depth, fusion weights and all timeouts.
The source/default manifest alone cannot establish effective runtime settings or
database state; unresolved fields prevent a publishable run.

Current source identities to verify at execution:

- Encoder: MiniLM-L6-v2, revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`,
  384 dimensions, 256-token ceiling, normalized vectors.
- Cross-encoder: ms-marco-MiniLM-L6-v2, revision
  `233902d25c440f23af6f7d6e94d2946bac0bee0a`, CPU, at most 32 candidates.
- Generator/router: Groq `openai/gpt-oss-20b` source default, temperature 0.2,
  low reasoning effort. Record the actual served model ID and provider changes;
  a hosted alias is not an immutable weight checksum and determinism is not promised.
- Source context caps: 8192/12288/16384 for 5/10/15 marks, visible output allowances
  320/640/1024 plus the provider's recorded reasoning allowance. The actual configured
  ceiling may be smaller. Freeze common per-mark settings for every comparison.
- Primary research candidate pool: 32 and retained seed count: 8 where the method
  uses ranked seeds; all exceptions and parent/graph budgets are preregistered.
  These are proposed controlled-adapter settings, not claims about every current CLI variant.

All prompt fitting uses the same frozen assembler in the initial benchmark.
Save exact ordered candidates, source intervals, expansion results, final excerpts,
serialized prompts, answer, verification/trimming/abstention, routing and failures.
Distinguish raw draft from the final user-visible answer; grade the latter.
Generation is single-turn with no chat history. Never reuse generated answers or
judge scores as retrieval annotations. Separate extraction/index build costs from
query costs, including amortized graph construction at stated query volumes.

Quality runs use one preregistered generation replicate, with randomized balanced
system order. No best-of retries. On a frozen stratified subset of 30 test items,
run three generation replicates to diagnose hosted-model variability; do not count
them as independent questions or select the highest-scoring answer. Unsupported
seed control is recorded as unavailable, not replaced with a determinism claim.

Time three warm retrieval runs per query/system and report median per query, then
p50/p95 over those query medians; measure cold model/index startup separately.
Report end-to-end time to first token, final answer and all routing/reranking time
where instrumentation exists. Record cache hits, provider wait, request failures
and account rate limits. Balance interleaved run order to reduce time-of-day bias.
Do not run uncontrolled concurrency against the API quota. Report quota-limited
trials separately from successful-only latency; they remain availability failures.

On a provider failure, preserve the scheduled run and missing NHRS, show its failure
rate and a separately labelled service-inclusive score treating no delivered answer
as zero. A later operational retry is a new replicate, not a replacement hidden
inside the primary sample. For paired statistical analysis report the common valid
pairs and excluded failures, plus sensitivity bounds; do not compare unequal samples
without disclosure. Retrieval failures with no evidence have operational RER=0.

Record actual provider token usage and dated prices/currency, not invented costs;
absence of billing data means cost not measured. Include router, correction and
graph-extraction calls. A proposed efficiency acceptance rule is at least equal
RER with improved ECT, and no more than 25% higher warm retrieval p95 or query cost
than the declared comparator. This tolerance is provisional: validate feasibility
on development data and freeze it before test access. If it fails, report a trade-off
rather than retrospectively changing what counts as acceptable.

## 9. Statistics and failure analysis

Pre-register H1–H4, contrasts, subsets, tolerance margins, sample sizes and exclusion
rules after the development pilot and before opening test labels. Analyze per-question
paired differences, not independent-system means. Resample whole document bundles
with replacement, preserving all within-bundle questions, formats, raters and system
pairs; use 10,000 paired cluster-bootstrap replicates, seed 20261030, and percentile
95% intervals. Record too-few/degenerate cluster warnings rather than precise-looking
intervals. With the proposed split there are 20 independent test bundles.

For the confirmatory difference test, flip paired system labels at the independent
bundle level, using a two-sided permutation test with 10,000 randomized draws
(exact enumeration if fewer assignments), the +1 Monte Carlo correction, and Holm
adjustment across the four primary hypothesis tests. If H4 is not implemented, mark
it not tested and report the remaining prespecified family transparently. NHRS is
reported by marks even when the H3 primary contrast averages balanced per-mark means.
Additional comparisons, correlations and subgroup analyses are exploratory unless
registered beforehand. An ordinary question-level paired bootstrap does not account
for shared-document clustering; do not apply it blindly just because a library offers it.

Report absolute differences and relative improvements with intervals. Relative change
from a zero baseline is undefined. Do not adopt illustrative 0.70/0.84 values as results.
The 360-item design is not a power calculation: estimate variability and bundle
dependence from development, document a minimum meaningful effect, and calculate
feasible power/sample requirements before the final test freeze.

Assign failure codes at ingestion, mapping, candidate retrieval, ranking, graph
coverage/routing, topic expansion, prompt fitting, unsupported generation, rubric
coverage and provider availability. Inspect long-topic tails, irrelevant neighbors,
repeated headings, dropped table headers, negation, conflicts, missed relation edges
and incomplete 15-mark explanations. Review a preregistered random sample and all
material pairwise regressions; publish counts, examples and reviewer attribution.

## 10. Existing tooling versus next work

`evaluation.production_rag` already offers dense/hybrid/rerank/topic/graph/production
diagnostics, chunk-ID metrics, optional generation, a supplementary model judge and
human review export. It is useful for smoke checks but is **not** this benchmark:
its graph arm is graph-only, not the graph-assisted baseline above; reranking and
candidate pools differ across arms; production retrieval is currently called with
15-mark depth before generating other formats. It has no gold evidence-interval
coverage, exact generation-context token accounting, all seven matched adapters,
blinded grading allocation or paired cluster inference. Do not rename existing
numbers RER, NHRS or ECT. Its literal keypoint score is not a human grade.

Delivered preparation tools, from `backend/`:

```powershell
venv/Scripts/python.exe -m evaluation.research_manifest self-check
venv/Scripts/python.exe -m evaluation.research_manifest validate-template
venv/Scripts/python.exe -m evaluation.research_manifest freeze --output evaluation/reports/research_snapshot_NEW.json
```

`research_manifest.py` uses the standard library and static source inspection,
without importing the app, accessing environment files, loading models or
connecting to the database. It inventories the working source hashes, declared
model identities, installed dependencies and public source defaults. Optional
`--settings PUBLIC.json` accepts only an explicit allowlisted public configuration;
it remains operator-supplied/unverified, not automatically measured runtime state.
Existing output paths are refused.

The final preparation snapshot is
`backend/evaluation/reports/research_baseline_manifest_v1_2026-10-30_r2.json`, SHA256
`e91f64502b5f90d06436c7175f4b9e92b240a64552fb56de75a00d36b3842ecc`.
It identifies baseline commit 8f59262 plus the actual working-tree hashes.
Runtime configuration, database/index state and availability remain explicitly
unverified in this offline artifact. The prior preparation snapshot is preserved.

`backend/evaluation/datasets/research_dataset_template_v1.json` contains two
synthetic, unreviewed format examples, not two collected benchmark items. The
template-integrity validator checks hashes/offsets, identities, page/topic/bundle
references and rubric totals. It is not a certification of scientific annotation
quality or a general validator for the future full dataset schema. Self-checks
exercise quote corruption, compensated negative rubric marks, secret-setting
rejection and overwrite refusal. These checks and the existing production
evaluation self-check passed; no production behavior was altered.

Execution sequence and gates:

1. **Now:** freeze source identities; review this specification and synthetic
   annotation template. No claim of benchmark execution.
2. **Dataset:** acquire permitted educational sources, prepare frozen canonical
   pages/topics, run the 20-question annotation pilot, recruit qualified reviewers,
   then freeze 60 development and 300 test questions with independent labels.
3. **Adapters:** implement research-only controlled baselines, exact tokenizer
   accounting, source-interval coverage and blinded grading export. Verify parity,
   no graph leakage into ablations and correct per-mark retrieval. Keep production
   unchanged and existing evaluations immutable.
4. **Pilot and preregistration:** test instrumentation on development, finalize
   budgets/tolerances/power, freeze all run settings and hold test labels separately.
5. **Baseline benchmark:** execute the seven matched systems and conventional block;
   collect reviewed answers, costs and failure traces. Publish measured tables with
   intervals and an explicit missing-data/availability table.
6. **Contribution:** select a demonstrated failure, implement only its targeted fix,
   freeze the H4 arm if relevant, run ablations/statistics and investigate regressions.
7. **Paper:** methodology, established baselines, evidence-backed contribution,
   released artifacts/rights, independent grading, negative results and limits.

## 11. Research sources

Context7 was used for current implementation documentation on 2026-10-30.

- [LlamaIndex hierarchy and AutoMergingRetriever](https://github.com/run-llama/llama_index/blob/main/docs/src/content/docs/framework/module_guides/loading/node_parsers/modules.md): parent-child linking and threshold-based merging are existing reference mechanisms.
- [Ragas context recall](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/): model-estimated reference-claim attribution is a useful supplementary measure, distinct from reviewed source-span RER.
- [SciPy bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html) and [paired permutation tests](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html): paired sampling preserves correspondence; bundle clustering still requires the protocol above.
- [RAPTOR, ICLR 2024](https://proceedings.iclr.cc/paper_files/paper/2024/hash/8a2acd174940dbca361a6398a4f9df91-Abstract-Conference.html): hierarchical retrieval already addresses document-level context; its summary-tree method differs from literal source-topic recovery.
- [Microsoft GraphRAG local search](https://microsoft.github.io/graphrag/query/local_search/) and [original GraphRAG paper](https://arxiv.org/abs/2404.16130): local entity/text retrieval and global community summarization are distinct methods; this project must name its actual baseline accurately.
