# RAG grounding handoff — 2026-10-27

Status: IMPLEMENTED LOCALLY; focused regression suite and local reproduction passed. Authenticated end-to-end request against the owner's uploaded document was not run in this session.

## Observed failure

The reported Kestrel query retrieved four passages via the existing semantic/structural hybrid path. The answer layer then withheld the draft because the configured local model omitted numbered citations. A local replay with the same visible excerpts also produced unsupported details about the inertial measurement unit and lidar array. The account-level entity graph status was empty; that did not prevent dense/structural retrieval from finding evidence.

## Change

`backend/orchestration/service.py` retains the existing pgvector dense search, structural RRF, table evidence and optional entity-relation candidate retrieval. If provider output is uncited, has invalid references, abstains despite directly relevant evidence, or fails the configured verifier, the service now builds a bounded fallback from exact source sentences in the already-prepared evidence blocks. If the configured provider is unavailable, it also serves that fallback when relevant excerpts exist. Each excerpt keeps its actual evidence block citation. It does not paraphrase model claims or infer missing references. The fallback must pass the answer verifier and citation-reference check or the service abstains.

Provider deltas are buffered until the final answer passes this gate. This prevents unsupported draft claims from appearing in chat or voice before validation; the verified answer is emitted as one final delta, so token-by-token answer streaming is not retained on this path.

## Semantic and graph retrieval status

Dense semantic retrieval already embeds the query and orders owner-scoped document chunks by pgvector cosine distance in `backend/chat/rag.py`. The workspace service also merges the enabled document-structure path and optional table/knowledge-graph evidence. Existing documents without graph status can use the authenticated per-document **Build entity graph** action in the Source Library. Ingestion extracts graph relations for new documents when local Ollama is available. This account's graph was not rebuilt in this run; the UI's prior `empty` status remains accurate until that action succeeds.

## Verification evidence

- `backend/venv/Scripts/python.exe -B -m py_compile orchestration/service.py` — passed.
- `backend/venv/Scripts/python.exe -B -m pytest -q tests/unit/generation tests/unit/orchestration` — 291 passed; one pre-existing pytest-asyncio deprecation warning.
- Local source-excerpt fallback replay on the Kestrel passages — 3 cited claims, verifier passed; unsupported IMU/lidar function claims absent.
- Local services: PostgreSQL port 55433, Ollama port 11434 with `llama3.2:3b`, FastAPI health `healthy` on 8000, Vite HTTP 200 on 3000.
- No authenticated request was sent against the stored user document, so graph rebuild completion and account-specific retrieval remain unverified.

## Limits

The verifier remains lexical and does not establish entailment. The extractive fallback uses exact sentence text to avoid relying on paraphrase checks. If passages do not share a question term or are truncated before a complete relevant sentence, it correctly abstains. Ollama generation remains locally configured; no Groq request was made.
