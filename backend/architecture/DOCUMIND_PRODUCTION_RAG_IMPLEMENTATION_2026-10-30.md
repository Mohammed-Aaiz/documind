# Production RAG implementation — 2026-10-30

Owner authorized the recommended audit approach and a GitHub push after checks.
Ponytail full was applied: reuse PostgreSQL, installed Sentence Transformers,
the existing reprocess transaction and existing evaluation metrics.

## Implemented

- Structure-v2 token chunking, dense/FTS RRF and batched topic recovery from
  the previous stage remain the shared retrieval foundation.
- Pinned CPU CrossEncoder `cross-encoder/ms-marco-MiniLM-L6-v2`, revision
  `233902d25c440f23af6f7d6e94d2946bac0bee0a`, scores a bounded pool before
  topic expansion. Its learned order survives later source selection. Raw
  cosine scores and citations are preserved. One worker, nonqueued admission,
  deadline and honest unavailable/busy states bound inference load.
- The model is explicitly provisioned with `python -m embeddings.provision_reranker`.
  Runtime never downloads it. Startup warms the local checkpoint before serving.
- Alembic 016 installs matching full-text GIN, document/chunk-order B-tree and
  HNSW cosine indexes. Product vector search uses transaction-local iterative
  strict ordering and ef_search 100; the planner can choose exact search.
- Alembic 017 adds owner-bound index revision archives. Reprocessing captures
  old chunks/vectors, structure, tables, pages, visual and graph evidence before
  replacement. Archive and replacement commit together; failure restores the
  previous active index. Owner-filtered archive endpoints expose citable fields
  without vectors or internal paths. Concurrent rebuilds use a document lock.
- A read-only evaluator compares dense, hybrid, reranked, graph, topic and full
  production retrieval, with optional 5/10/15-mark Groq generation. It records
  recall/MRR/nDCG, topic coverage, citation verification, unanswerable abstention,
  latency and explicitly heuristic rubric phrase coverage. Human grading and
  semantic judge metrics are not fabricated.
- Isolated MiniLM/BGE comparisons load local checkpoints only, normalize vectors,
  record versions and query prefixes, and never mix or promote embedding spaces.

## Observed checks

- 78 focused backend tests passed, covering ranking, context fitting, source
  provenance, archive ownership and successful/failed replacement.
- Frontend typecheck and 62 frontend tests passed.
- Live reranker warm two-passage sample took 14ms after a separate ~12s cold load.
  A later actual 20-candidate query took 237ms; neither sample establishes p95.
- All three new indexes are valid. EXPLAIN exercised both GIN and forced HNSW.
  Ten stored query-vector diagnostic samples recalled the exact top ten with
  recall 1.0, including self matches; this is not a relevance benchmark.
- The two current reports were reprocessed through the real server handler:
  warehouse 30 legacy chunks -> 12 structured chunks; Kestrel 78 -> 34.
  Both have one archived prior index and their original file hashes are unchanged.
- Warehouse graph extraction completed: 12 chunks, 21 relations. Kestrel graph
  extraction is partial: 5 chunks, 4 relations, upstream provider unavailable.
  Its semantic and topic retrieval remain searchable.
- Live Kestrel query recovered six chunks in four complete topic groups,
  347 source words, with the neural reranker ready. 5/10-mark drafts passed
  citation checks; the next 15-mark request encountered Groq HTTP 429.
  Citation checks do not establish subject accuracy or mark completeness.
- MiniLM and BGE were compared on the versioned synthetic smoke fixture. This
  small check does not justify a production embedding switch; MiniLM is retained.

## Operational limits

Groq account quota can limit generation and graph extraction. The graph is
explicitly partial when bounded extraction or upstream failure leaves gaps.
Context is finite, coverage is reported, and no answer is guaranteed a grade.
Old frozen evaluations are preserved. HyDE/multi-query, extra graph services,
Ragas dependencies and a model switch were not added without evidence of need.

The previous retired-extractive-route test mocks a removed symbol; historical
tests are not represented as a passing full regression suite. Deployment, voice
audio quality, large-corpus load and human-scored exam rubrics remain separate
verification work. No claim of complete production readiness is made.

## Final verification before GitHub push

An additional 112 affected backend checks passed (chunking, generation, graph,
visual retrieval and voice), bringing the focused total to 190. Typecheck,
62 frontend tests and the Vite production build passed; build output was directed
to a new temporary folder outside the protected `dist/` path.

After the upstream rate window cleared, the live 15-mark Kestrel request returned
a cited 1336-character answer passing the lexical verifier in 1540ms generation
time. Its reranker was ready and topic coverage reported four complete groups.
This supplements the earlier successful 5/10-mark samples; it does not remove
the account-quota limitation or imply a human marking result.

Runtime checks reported healthy Groq configuration and frontend HTTP 200. The
staged product source was checked against the configured secret values; none
were found, and environment files, uploads and provisioned model assets were
excluded. Unrelated local research/agent edits were left unstaged.
