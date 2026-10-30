# Entity-relation GraphRAG implementation — 2026-10-27

Status: **CONFIRMED implemented in the local product path** for the exact scope below. This is an implementation record, not a claim that all deployment, quality, or latency gates have passed.

## Product behavior

- Alembic revision 013 adds owner-scoped canonical entities, per-document and per-chunk mentions, typed relations, exact supporting quotes, extractor/model versions, and per-document extraction status. It is additive; existing documents are not backfilled by migration.
- Ingestion extracts relations through the configured loopback Ollama service only. It accepts a relation only when both endpoints occur in the source quote and that exact quote is a substring of the source chunk. Extraction is bounded to 24 chunks per run and six relations per chunk. An unavailable or invalid local result is recorded as `partial` or `unavailable`; vector and structural ingestion remain usable.
- Entity linking is exact normalized name and type within one authenticated owner. There is no fuzzy resolution, confidence field, or automatic cross-owner linking.
- Query retrieval seeds exact normalized entities from the question, traverses relations in either direction for at most three edges, and returns original source chunks with their source document, relation path, hop count, predicate, and evidence quote. The evidence quote must still occur in the returned excerpt. Graph evidence does not receive a fabricated vector similarity score.
- Dense vector and document-structure retrieval remain active. Empty or unavailable KG retrieval falls back to those paths and is reported as such.
- The source library exposes a user-triggered graph build/rebuild action for previously uploaded documents. The UI shows only server-reported extraction status and counts. It does not pretend old documents were processed by migration 013.
- KG path, hop, predicate, and quote are preserved in streamed answers and PostgreSQL-backed chat history, including after reload. Student and Research sessions remain isolated.

## Verification evidence

- Local database migration head: 013. The migration was applied to the local PostgreSQL cluster without a reset or backfill.
- Local API `/api/health`: healthy; configured provider `ollama`, model `llama3.2:3b`; legacy QA model reports unavailable/retired.
- Local UI at `http://127.0.0.1:3000/`: HTTP 200. API at `http://127.0.0.1:8000`.
- Official Ollama Windows installer and `llama3.2:3b` model were installed locally. A direct loopback `/api/chat` probe returned the exact expected four-token response in 4.32 seconds. This is a short first-use model probe, not an end-to-end RAG latency benchmark.
- Frontend: `npm run typecheck` passed; `npm run test` passed (57 tests); temporary-directory Vite production build passed.
- Backend: focused graph, generation, and orchestration suite passed (376 tests); the exact-evidence/entity graph and SQLite type suite passed (10 tests); graph rebuild plus stream/history integration checks passed (5 tests). Runs reported an existing pytest-asyncio deprecation warning.

## Remaining release gates

- No versioned corpus evaluation yet compares answer quality, evidence precision/recall, abstention, latency, or resource use against the frozen baseline. Do not call quality or retrieval improvements measured.
- Existing documents require the explicit source-library graph build action. No automatic full-library graph backfill ran.
- The direct Ollama probe does not measure the full upload → extraction → retrieval → answer or voice-to-voice path. Groq live credentials and a Vercel deployment were not available for verification.
- Exact normalized-name linking can merge same-name, same-type entities belonging to the same owner. Ambiguous identity resolution is not claimed.
- The local host has very little free disk after installing the app runtime and model; model download is not a viable deployment procedure for a similarly constrained machine without first planning storage.
