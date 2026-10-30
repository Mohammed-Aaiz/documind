# Groq-only product inference — 2026-10-29

Status: DECIDED by the owner's explicit requests to use Groq exclusively and
make the existing API key work. This supersedes Ollama-first and automatic
provider fallback decisions for the product. Historical evaluation functions
remain available without becoming product answer routes.

## Implementation

- Backend configuration accepts only `groq`; automatic provider fallback is
  rejected. Answers, query routing and LLM graph extraction use the shared Groq
  wrapper. The stateless `/api/generation/answer` route now uses that wrapper.
- The existing credential was stored under `GROQ_API_URL`. Configuration accepts
  that legacy variable as a secret alias; `GROQ_API_KEY` is the preferred name
  and takes precedence within the configuration source. URL values are rejected.
  Neither protected environment file was edited. The destination is fixed to
  Groq's API, and secret values are excluded from settings serialization/repr.
- The selected model is `openai/gpt-oss-20b`. Application context is bounded by
  `groq_context_tokens` (8192 by default). Graph relation metadata uses the actual
  provider/model for each extraction chunk.
- Prompts request citations attached to factual sentences. When a draft mixes
  supported and unsupported claims, complete supported claims can be retained
  with their checked source indices and passed through verification again.
  Omissions are disclosed. Empty, uncited and unsupported outputs still abstain;
  the lexical verifier's thresholds were not relaxed.

Backend and AI owners implemented the initial changes. After specialist workers
became unavailable, the primary agent completed the remaining AI implementation
and TEST_AGENT checks for this owner-requested operation. No frozen evaluation
assets, uploaded documents or model weights were changed in this operation.

## Observed verification

- Live Groq completion with the existing credential returned `GROQ_OK` in 0.81s.
- Authenticated Groq model-inventory probe reported the selected model available.
- 79 focused unit tests passed, covering key loading/precedence, secret handling,
  provider failures/deadlines/cancellation, router isolation, graph retrieval,
  stateless Groq generation, retained citations and rejection of invented numbers.
- A read-only query against the owner's existing Kestrel report retrieved four
  sources and produced a Groq answer. One cold retrieval/generation run took
  12.915s; a subsequent warmed run took 0.826s. These are individual local samples,
  not a benchmark or a promise of general latency. Citation restoration received
  an additional regression check after that sample.
- Existing PostgreSQL schema revision was 015 before startup. No reset or data
  migration was needed. Frontend HTTP returned 200 and backend health reported
  Groq configured with fallback disabled.

The lexical verifier establishes attribution under its rules, not factual
entailment. This operation does not establish production deployment readiness,
full voice quality, or the complete earlier OCR regression status.
