# Workspace and answer-provider rebuild — 2026-10-27

Status: DECIDED by the owner's explicit request in this chat; implementation and measurements remain UNVERIFIED until recorded below.

## Decision and scope

The owner requested a product rebuild after feedback about voice latency, weak answers, frontend architecture and an unstructured codebase. The owner explicitly selected Ollama for local inference and Groq for hosted inference, separate Student and Research workspaces, separate chats, and 5/10/15-mark Student answers. This supersedes earlier prohibitions on replacing the default custom QA engine and using a hosted answer provider for this scope. Trained weights and frozen evaluations remain untouched as historical comparison assets. No hosted call is made merely because local inference fails.

Use one configured answer-provider interface, with Ollama and Groq adapters. Keep authentication, pgvector retrieval and source provenance. Default local candidate: `llama3.2:3b`, context 2048 and four CPU threads; hosted candidate: `openai/gpt-oss-20b`. These are configurable candidates, not a measured model-selection result. No model downloads or claims of low latency / zero OOM are implied. Groq credentials stay server-side; the UI must identify hosted inference and evidence egress.

Add a persisted `workspace` discriminator (`student` or `research`) to SQL chat sessions, assigning existing sessions to Student. Filter and validate sessions using JWT identity and workspace on the server. Conversation memory uses the validated session; switching the interface alone is not isolation. No destructive migrations or reassignment of existing messages.

Student tools: 5/10/15-mark answers, explanations, revision and practice prompts with cited evidence. Research tools: source synthesis, comparison, critical appraisal and gap exploration, explicitly constrained to uploaded evidence. Both expose document upload, chat history, source inspection and voice. Keep the existing five top-level pages, with two modes within Workspace. Prefer reusable feature modules and a restrained, accessible responsive interface.

Improve perceived voice latency with bounded turns, cancellation and streaming where the actual transport supports it. Measure time to first text/audio separately from total generation. Do not claim WebRTC works on a stateless hosted runtime without verification. Vercel frontend deployment and a separately reachable persistent FastAPI/voice backend is an acceptable deployment topology; a Groq key alone does not provision storage, OCR, embeddings, databases or voice.

Preserve dense + document-structure retrieval and its evidence. Improve evidence selection within existing contracts. Entity-relation GraphRAG and visual patch retrieval in the owner's diagram are requested target capabilities, not existing functionality; do not represent hierarchy edges or OCR as these capabilities. Introduce new schemas for these only with concrete implementation and evaluation, not empty scaffolding.

## Task ownership

Existing ownership remains. Previously unassigned production paths are assigned according to their existing function: AI_AGENT owns `backend/generation/**` and `backend/orchestration/**`; BACKEND_AGENT owns `backend/conversation/**`, `backend/session/**`, `backend/voice.py`, `backend/voice_vad.py`, and `backend/voice_webrtc.py`. DATABASE_AGENT owns SQL models and migrations. TEST_AGENT owns tests. FRONTEND_AGENT owns frontend implementation. Coordinator owns this record and product/agent documentation. No agent may overwrite another agent's active edits.

## Acceptance criteria

1. Student and Research sessions are independently listed and server-validated; switching preserves each mode's active chat and draft without response leakage.
2. Ollama is the default product answer path; Groq is explicit server configuration with no automatic fallback or exposed key. Provider failures are honest unavailable states.
3. Student mark formats and Research task instructions reach the answer service, with real citations and no invented reliability scores.
4. Cancellation, loading, empty/error states and keyboard navigation work; expensive decoration is absent from the main reading surface.
5. Voice uses the same validated workspace/session and provider as text; resources are stopped on switch/disconnect. Latency improvements are described only to the extent verified.
6. Frontend typecheck/build and focused backend regression tests pass. Build output uses a temporary directory outside forbidden `dist/`. No live database reset or automatic runtime startup migration is performed as a test.
7. Verification distinguishes mocked provider tests, local live inference, live PostgreSQL and browser checks. Missing credentials/models/infrastructure are reported without fabricated success.

## Research and rollback

Official provider contracts: https://docs.ollama.com/api/chat and https://console.groq.com/docs/api-reference . Deployment constraints must be checked against https://vercel.com/docs/functions/limitations . No papers or model popularity are treated as DocuMind performance evidence. Compare answer quality, source accuracy, abstention, time to first output, total latency and resource usage on separately versioned examples; retain the frozen benchmark unchanged. Rollback is configuration plus reverting the new product-path code, retaining existing weights and historical routes. The workspace migration adds a defaulted discriminator and does not delete user data.

**Hosted model update, 2026-10-27:** Groq deprecated `llama-3.1-8b-instant` on 2026-08-16 for developer-tier use and lists `openai/gpt-oss-20b` as its replacement. The configured default was updated accordingly. This model was not live-probed because no Groq key is configured. [Groq model deprecation notice](https://console.groq.com/docs/deprecations) and [current model card](https://console.groq.com/docs/model/openai/gpt-oss-20b).

## Results

Implementation and verification in progress. No runtime or deployment result is asserted by this decision record.

## Subsequent owner instruction — custom model removal

The owner explicitly requested: "run it and show me also delete the previous custom llm".
This supersedes weight preservation for `backend/models/documind-qa/` only. The new
product route uses the configured provider; ingestion tokenization uses the embedding
model tokenizer. Historical evaluation code may remain but its removed custom-model
baseline cannot be rerun without separately restoring those artifacts. Other models,
uploads and frozen evaluation results must not be deleted.
