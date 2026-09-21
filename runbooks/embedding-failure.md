# Incident: Embedding generation or vector retrieval failure

## Purpose
Recover when embeddings cannot be generated (upload path) or pgvector semantic
search fails/returns nothing — RAG answers become empty ("insufficient
context") or uploads report embedding errors.

## Impact
- New uploads may finish chunking but end with `embedding_status: "error"`
  (`backend/documents/routes.py`).
- `/api/embeddings/search` and `/api/chat/ask` retrieval return empty or 500;
  RAG flags `insufficientContext: true`.
- Login and document management still work.

## Symptoms
- Document detail shows `embeddingStatus: "error"` (or stuck `"processing"`).
- `/api/chat/ask` returns 200 but `answer: ""` with
  `insufficientContext: true` and zero/low retrieval scores
  (`backend/chat/rag.py`).
- `/api/embeddings/generate` returns 500 with
  `Embedding generation failed: <error>` (`backend/embeddings/routes.py`).
- Retrieval SQL errors mentioning `vector`, `<=>`, or the `vector` cast —
  pgvector extension issue in the retrieval query
  (`backend/chat/rag.py`, `backend/embeddings/routes.py`).

## Severity
P1

## Immediate Actions
1. Identify which half is broken: embedding **generation**
   (`embed_texts` via sentence-transformers) vs **retrieval** (pgvector SQL).
2. Do not re-upload documents repeatedly — the failure mode is usually
   environmental, and each upload re-runs the full pipeline.

## Diagnosis
1. **Embedding model load?** `backend/embeddings/model.py` loads
   `all-MiniLM-L6-v2` lazily on first use. On a fresh host the first call
   downloads weights from Hugging Face; if the host has no internet access or
   the HF cache is unreadable, generation fails. Check the uvicorn log for the
   underlying exception (the upload route swallows the traceback and sets
   `embedding_status = "error"`).
2. **pgvector extension installed?** Retrieval SQL uses `dc.embedding <=> '...'::vector`
   and filters `d.embedding_status = 'ready'`. If the extension is missing or
   the column type is wrong, the query raises a database error (visible in the
   500 detail or uvicorn log).
3. **Documents actually embedded?** Retrieval only considers chunks where the
   parent document has `embedding_status = 'ready'` **and**
   `dc.embedding IS NOT NULL`. If uploads failed embedding, search legitimately
   returns nothing — check `GET /api/documents/{id}` for status.
4. **Negative similarity values?** pgvector cosine similarity can be negative;
   code clamps scores to [0,1] (`chat/routes.py`, `chat/rag.py`). A bug here
   would show as confidence anomalies, not outages — do not "fix" data.

## Recovery
1. **Generation failure (no internet / HF download blocked):** pre-populate the
   Hugging Face cache on the host (e.g. run the model download on a connected
   machine and copy the cache), or allow the egress needed for the one-time
   model download. Restart the backend afterwards — the failed lazy-load state
   is cached in-process.
2. **pgvector missing/wrong:** install/enable the pgvector extension in the
   PostgreSQL instance and ensure the `embedding` column is `vector(384)`.
   **REQUIRES HUMAN APPROVAL** — this is a database change.
3. **Documents stuck in `error`:** after the underlying cause is fixed, re-run
   embedding for affected documents via `POST /api/embeddings/generate`
   (body `{"documentId": "<id>"}`) — it is safe/idempotent per document.
4. Restart the backend if model state was cached mid-failure.

## Validation
- `POST /api/embeddings/generate` returns 200 with `chunksEmbedded > 0`.
- `POST /api/embeddings/search` with a phrase from a known document returns
  that document's chunk with a plausible similarity score.
- `POST /api/chat/ask` returns a non-empty answer with
  `insufficientContext: false` for a question answerable from the corpus.
- Affected documents show `embeddingStatus: "ready"`.

## Rollback
No verified rollback mechanism found. Recovery actions are additive (model
cache, extension enable, re-embedding); undo by reversing the specific change.

## Escalation
- If the pgvector column/index appears corrupted (errors persist with the
  extension correctly installed), stop and involve the database owner —
  **REQUIRES HUMAN APPROVAL** for any data repair.

## Do Not
- Do not replace pgvector search with keyword search or another embedding
  model (`all-MiniLM-L6-v2` 384-dim is the verified configuration).
- Do not bulk-update `embedding_status` manually in the database to "ready";
  rows without real embeddings would break retrieval silently.
- Do not regenerate embeddings for every document "just in case" — target only
  affected documents.

## Root Cause Follow-Up
- If offline hosts are common, consider vendoring the embedding model weights
  (project decision — not part of this runbook).
- Upload currently embeds inline during the request; large documents tie up
  request workers. Track as a known limitation if timeouts appear.
