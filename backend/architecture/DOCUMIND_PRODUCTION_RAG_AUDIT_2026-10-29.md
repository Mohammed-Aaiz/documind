# Production student RAG audit — 2026-10-29

Status: inspected current code and local PostgreSQL; recommendations below are
design decisions, not measured quality claims. Owner requested Context7 research,
an audit, and implementation to begin afterwards. This record adds to the prior
Groq-only decision. Frozen evaluations and uploaded files remain protected.

## Verified findings

- The database contains 131 chunks, all `chunk-v1-legacy-chars-1000-200`, with no
  nonempty heading paths. Existing full-topic claims cannot rely on these rows.
- The selectable structure-v2 chunker already preserves headings/pages and
  uses approximately 200-token children under the 256-token encoder ceiling;
  the configured default was still legacy at inspection.
- MiniLM-L6-v2 is a 384-dimensional dense encoder. Its default 256-wordpiece
  truncation makes embedding a whole long topic a poor substitute for retrieval
  of small children followed by recovery of their parent section.
- Product generation had an arbitrary eight-source prompt cut, a previous
  1200-character passage cut, and N+1 section queries limited to 24 chunks.
- Selection used rank plus lexical overlap, not a trained cross-encoder.
- PostgreSQL pgvector is version 0.8.6 locally. document_chunks has primary key
  and document-ID B-tree indexes, no vector ANN or full-text GIN index.
- Entity/relation extraction, quote provenance and bounded recursive graph
  retrieval exist in code. Index build coverage and graph answer accuracy are
  separate from implementation presence.
- Groq GPT-OSS-20B supports 131072 context tokens according to its current model
  card; DocuMind budgeted 8192 at inspection (now 16384). More input also costs
  latency and account token quota. The application's byte estimate is not the
  actual Groq tokenizer.

## Recommended architecture and implementation order

| Area | Decision and practical reason | Delivery status |
|---|---|---|
| Chunking | Structure/sentence-aware token chunking; headings, paragraphs, lists and tables retain boundaries. Index small children, recover complete contiguous parent topics for generation. No fixed topic word count. | Parent expansion and prompt repair are this implementation stage; structure-v2 already exists. |
| Embeddings | Keep existing float dense MiniLM vectors as baseline; benchmark BGE-small-en-v1.5 for English as a replacement candidate. Larger/multilingual encoders only after subject/language evaluation and CPU/RAM measurements. | No model replacement or re-embedding in this stage. |
| Embedding migration | Record model ID/version/dimension, tokenizer limit and normalization policy. A replacement requires a separately versioned index and full re-embedding; equal dimension does not mean equal embedding space. | Required before any model switch. |
| Context | Full passages first, coherent topic order, source IDs/pages retained, reserved output budget, explicit partial-coverage warnings. Mark-dependent effective input budgets within operator limit. | Implementing now. |
| Search | Owner-filtered dense + PostgreSQL full text, fuse separate ranks with RRF. FTS handles literal names/codes; dense handles semantic similarity. PostgreSQL ts_rank_cd is not BM25. | Implementing bounded exact hybrid baseline now. |
| Vector DB | Retain PostgreSQL + pgvector and common transaction/ownership boundaries. Exact cosine is the initial correctness baseline; add HNSW cosine only after recall/latency comparison at realistic corpus sizes. | No database replacement. |
| Indexes | Add matching full-text expression GIN, document/chunk-order B-tree, and eventually HNSW with Alembic. Inspect EXPLAIN and recall under authenticated filters; use pgvector iterative scans if ANN filtering loses candidates. | Follow-on database-owned migration, not claimed deployed. |
| Reranking | CrossEncoder on a bounded candidate pool, e.g. 20–40 small chunks, before parent expansion. Candidate: cross-encoder/ms-marco-MiniLM-L6-v2, local CPU with explicit assets and timeout/concurrency limits. | Research recommendation; no pretrained neural reranker claimed installed. |
| GraphRAG | Combine semantic/lexical candidates with query-relevant entity paths (at most three hops), exact supporting quotes and cited original chunks. Namespaced entities, quote validation and extraction versioning prevent unsupported graph assertions. Avoid graph routing/extraction calls when unnecessary. | Preserve existing code; evaluate independently against hybrid-only. |
| Query rewriting | Optional history-based standalone-question rewrite; add multi-query or HyDE only for measured recall failures because they add calls and can drift from source intent. | Deferred behind ablations. |
| Evaluation | Versioned qrels plus answer rubrics, retrieval Recall@k/MRR/nDCG, topic coverage, citation correctness, unsupported claims, unanswerable abstention, mark-specific completeness and p50/p95 warm/cold latency. | Existing retrieval metric functions remain; new topic regressions added here. |
| RAG judges | Ragas context precision/recall, faithfulness and relevancy as supplementary signals. Human review of subject accuracy and mark rubrics remains necessary; lexical verification is not entailment. | Evaluation design, no judge score fabricated. |

## Answer depth policy

- 5 marks: focused definition and essential supported concepts; input target up
  to 8192 tokens, output allowance 320 tokens.
- 10 marks: organized explanations and supported examples/connections; input
  target up to 12288 tokens, output allowance 640 tokens.
- 15 marks: broader synthesis, mechanisms/comparison/limitations when asked and
  supported; input target up to 16384 tokens, output allowance 1024 tokens.

These are token allowances, not a grading guarantee or a fixed word-count rubric.
The configured context ceiling always wins. This implementation raises the
default to 16384, enabling these mark-dependent caps; an explicit environment
override can still lower them. For sources exceeding a
single window, use question-focused retrieval and explicit partial coverage;
bounded multi-pass source synthesis is a later measured option, not an unlimited
context promise.

## Release checks

Keep semantic-only and hybrid-only baselines. Compare parent expansion separately
from reranking and graph expansion. Include questions whose required evidence
occurs at the end of a long topic, repeated headings, tables, OCR and scanned
pages, conflicting sources, cross-document relationships and unanswerable prompts.
Report evidence-recall and output-depth improvements separately from latency.

Existing legacy documents need an explicit derived-index rebuild to gain true
section boundaries. Reprocessing can change chunk IDs referenced by historical
answers; preserve snapshots/version references before a bulk rebuild. Merely
changing the default chunker does not upgrade already indexed documents.

## Primary sources consulted through Context7 and official pages

- LlamaIndex HierarchicalNodeParser / AutoMergingRetriever: https://github.com/run-llama/llama_index/blob/main/docs/src/content/docs/framework/module_guides/loading/node_parsers/modules.md
- Sentence Transformers retrieve and rerank: https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html
- Sentence Transformers retrieval/reranking evaluation: https://github.com/huggingface/sentence-transformers/blob/main/docs/cross_encoder/training_overview.md
- pgvector hybrid search, HNSW filtering and recall checks: https://github.com/pgvector/pgvector
- MiniLM encoder limit: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
- BGE candidate: https://huggingface.co/BAAI/bge-small-en-v1.5
- Cross-encoder candidate: https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2
- Ragas metrics: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/
- Groq context capacity: https://console.groq.com/docs/model/openai/gpt-oss-20b

## Implementation and verification results

CONFIRMED in this working tree: bounded dense/FTS RRF candidate retrieval;
batched topic expansion; request-time topic completeness metadata; full-passage
prompt assembly without an eight-block cutoff; sentence-boundary overflow;
new-upload structure-v2 default; 16384 default context ceiling with mark caps.

97 focused unit tests passed (43 retrieval/topic/prompt/provenance and 54
chunking/config). A live read-only PostgreSQL CTE test executed the real section
query against 30 synthetic chunks without writing database rows: full range,
repeated-heading boundaries, JSON null and ownership isolation passed. Live FTS
found three Kestrel matches.

Existing Kestrel retrieval returned 11 source chunks, correctly reporting partial
topic coverage because all its persisted chunks lack section metadata. One live
5-mark stateless draft abstained; 10/15-mark drafts returned cited answers passing
the lexical verifier. These are smoke samples, not marks-quality evaluation.
An existing legacy chat test cannot start because it mocks a removed
`chat.routes.get_model_status` symbol; this unrelated obsolete test needs updating
in the provider-retirement workstream. Do not present the entire suite as passing.

Neural reranking, alternate embeddings, GIN/HNSW migrations, safe versioned
reindexing of old documents, multi-hop quality measurements and human-scored
mark rubrics are follow-on work. Production readiness is not established by this
first implementation stage.
