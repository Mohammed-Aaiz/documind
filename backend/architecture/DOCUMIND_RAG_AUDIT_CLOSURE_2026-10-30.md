# Production RAG audit closure — 2026-10-30

This append-only record reconciles the current production RAG audit of
2026-10-29 and implementation record of 2026-10-30. Historical training,
evaluation-safety and retired-model audits retain their original scope; this
record does not relabel those research results as current product evidence.
The owner requested completion of the recommended implementation and a GitHub
push. The earlier implementation record documents specialist assignments.

## Required engineering work

| Audit area | Current implementation and evidence | Status |
|---|---|---|
| Structure-aware chunking | Structure-v2 token-bounded children preserve headings, lists, tables and page provenance. Long topic recovery is independent of a fixed word count. | CONFIRMED |
| Unheaded paragraphs | Migration 018 persists original element indices. Retrieval groups contiguous children of the same unheaded paragraph. Tests cover 317, 500 and 733 words; unrelated paragraphs remain separate. Existing NULL metadata is not guessed; those documents require explicit reprocessing to gain this mapping. | CONFIRMED |
| Parent context | One owner-filtered SQL query recovers contiguous sections/paragraphs after reranking. Repeated headings remain distinct. The former eight-source and 24-chunk expansion cuts are removed. A 128 KB retrieval bound and finite prompt budget remain explicit. | CONFIRMED |
| Mark-specific context | 5/10/15-mark input caps are 8192/12288/16384, within the configured ceiling, with 320/640/1024 output-token allowances. Partial context is disclosed. These are generation instructions, not a grade guarantee. | CONFIRMED |
| Embedding identity | MiniLM repository/revision, weights, configuration, dimensions, tokenizer window and normalization are verified offline. New index writes record the actual identity. Dense queries accept that identity and explicitly known legacy MiniLM labels, excluding unknown spaces. Runtime never downloads weights. | CONFIRMED |
| Alternate embeddings | Isolated MiniLM/BGE evaluator and a provisioned BGE candidate exist. Smoke evidence is insufficient to replace the baseline; no mixed vector space or speculative production switch. | CONFIRMED implementation; promotion not selected |
| Hybrid retrieval | PostgreSQL dense cosine and full-text ranks fused with RRF, with authenticated owner filters. Full-text rank is not labelled BM25. | CONFIRMED |
| Database indexes | Linear migrations 016–018; GIN full text, document/order B-tree and HNSW cosine indexes installed locally. Iterative scans mitigate owner-filter losses; the evaluator retains an exact baseline. | CONFIRMED |
| Learned reranking | Explicitly provisioned pinned CPU cross-encoder, bounded candidate pool, warmup, one-worker admission and deadline, before parent expansion. Raw similarity and source provenance survive reranking. | CONFIRMED |
| Versioned rebuilds | Migration 017 archives old derived evidence before replacement. Rebuild and archive share a transaction; failed replacement preserves the active index. Owner-filtered archive endpoints retain historical citation material. | CONFIRMED |
| Entity-relation GraphRAG | Groq extraction, explicit quote provenance and at-most-three-hop retrieval are integrated. Extraction resumes a contiguous validated prefix, fingerprints input/configuration and archives incompatible prior graphs. Concurrent rebuilds return 409. Invalid/truncated output and 429 preserve partial status. | CONFIRMED |
| PDF graph evidence | Whitespace-only alignment recovers exact original source slices, including line breaks; short unique anchors can recover their enclosing sentence. Changed words/numbers and ambiguous anchors are rejected. Quote checks are not semantic entailment. | CONFIRMED |
| Retrieval evaluation | Versioned qrels; precision, recall, MRR, nDCG, topic coverage, citation checks, abstention, and warm/cold timing across isolated retrieval variants and the real production path. | CONFIRMED tooling |
| Semantic evaluation | Optional Groq claim-support/relevance judge against the evidence actually supplied. Invalid or unavailable results remain not measured. Two deliberately supported/contradicted live cases distinguished correctly; same-provider bias remains explicit. No Ragas score is invented. | CONFIRMED tooling and smoke |
| Mark rubric review | CSV export supplies question, answer, rubric and evidence; validated human score import preserves blank ratings as pending. Formula injection and duplicate-rating regressions pass. | CONFIRMED tooling; human scores pending |
| Regression repair | Retired-model chat tests now exercise the current provider contract. Affected backend checks cover graph resumption, ownership, paragraph recovery, encoder identity and review workflow. Evaluation self-check passes; the final run is recorded below. | CONFIRMED |

## Deliberate conditional recommendations

HyDE, multi-query fan-out, extra graph services, larger embedding models, a
database replacement and multi-pass generation are not prerequisites in the
selected architecture. They add latency or operational cost and require measured
recall failures or corpus evidence before introduction. Ragas was suggested as
one supplementary judge option; the explicit semantic-judge interface supplies
that measurement workflow without adding a framework dependency. No claim is
made that this custom judge implements the Ragas metrics.

## Verification limits and release gates

The database is at Alembic 018. A real read-only PostgreSQL execution recovered
all five children of a synthetic 500-word unheaded paragraph, including its final
word, excluded the following paragraph and returned no evidence for a wrong
owner. No uploaded file was changed by that check. Existing structured Kestrel
and warehouse indexes were rebuilt and archived in the earlier implementation.

The semantic-judge smoke report and blank human-review sheet are saved under
`backend/evaluation/reports/semantic_judge_*_2026-10-30.*`. The two cases do not
establish course accuracy. Human subject review, representative-course qrels,
large-corpus recall/load measurements and real multi-user p95 remain UNVERIFIED
release evidence. The measurement paths are implemented; evidence that requires
real reviewers or a representative deployment cannot be manufactured in code.
Frontend/voice implementation is outside this RAG closure; prior frontend checks
are recorded in the implementation record, not rerun or relabelled here.

Configured Groq quota remains an external availability constraint. Longer context
cannot remove rate limits. The runtime reports them honestly rather than returning
invented answers or marking an incomplete graph as ready. Production readiness
for every corpus, account limit and deployment has not been established.

## Live graph completion

The current Kestrel report reached `ready`, 34/34 chunks processed, 130 entities
and 68 relations, with no failure code. Its existing validated prefix survived
both HTTP 429 pauses and an invalid ellipsis-based quote. Invalid extraction
receives one bounded correction reminder; a second invalid response still stops
without advancing the cursor. Normal extraction incurs one provider call and
provider failures are not automatically retried by that correction path. All
stored evidence quotes remain exact original-source slices. Graph completion
means extraction ran across the document, not that every relation is exhaustive
or independently judged semantically correct.

## Final affected regression and runtime checks

- 175 backend tests passed in 37.12 seconds across retrieval/reranking, provider
  contracts, topic/paragraph fitting, graph extraction/resumption, embedding
  identity, index preservation and evaluation review workflows. Existing pytest
  fixture and Sentence Transformers API deprecation warnings remain; no tests in
  this selected run failed or were skipped. This is not a full-repository run.
- `python -m evaluation.production_rag self-check` passed.
- Restarted API health returned healthy. Authenticated HTTP generation against
  the current Kestrel report returned 200, non-abstaining answers passing the
  lexical citation verifier for all three formats, each with nine source chunks:
  5 marks 4790 ms/473 answer characters; 10 marks 1662 ms/652 characters;
  15 marks 2030 ms/1315 characters. These are single end-to-end samples, not p95
  measurements or human grades. Partial prompt coverage was disclosed.
- The first 15-mark request hit Groq 429 and returned a sanitized 503; the later
  explicit check succeeded after the rate window cleared. No fallback model or
  fabricated response was used.
- Staged source passed whitespace checks and a scan against configured secret
  values. Environment files, uploaded documents and provisioned assets were
  excluded. Unrelated local research/agent changes remain outside this commit.
