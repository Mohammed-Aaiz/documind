# Stateful conversation: LangGraph turn, Redis memory, streaming voice

**Date:** 2026-10-22
**Status:** IMPLEMENTED (Phase C/D). Limits in §7 are part of the record.
**Supersedes:** nothing. The extractive DistilBERT path and the existing
Flan-T5 generative path remain unchanged and remain the defaults.

---

## 1. Decision

The product needs a conversation, not isolated questions. This change adds:

1. **Conversation memory** — one structured message array per (user, session),
   shared by the text API and the voice socket.
2. **A LangGraph state machine** for one turn: load history → resolve follow-up
   → retrieve → rerank → generate → remember.
3. **A role reassignment** — the fine-tuned DistilBERT QA model becomes the
   retrieval **reranker** (cross-encoder relevance judge), not the generator.
4. **An opt-in instruct generator** (`Qwen2.5-*-Instruct` family) behind
   `DOCUMIND_CONVERSATION_MODEL`, off by default.
5. **Full-duplex voice** over one WebSocket, with barge-in.

Not changed: `POST /api/chat/ask` (extractive default),
`POST /api/generation/answer`, table/list deterministic readers, the verifier,
retrieval (pgvector + dual structural path + gated table band), and the frozen
benchmark.

## 2. Files

| File | Role |
|---|---|
| `backend/session/store.py` | Redis list per user/session; TTL, trim, honest in-process fallback |
| `backend/orchestration/state.py` | `ConversationState` contract |
| `backend/orchestration/followup.py` | Deterministic follow-up resolution |
| `backend/orchestration/rerank.py` | DistilBERT span-probability reranking |
| `backend/orchestration/graph.py` | The LangGraph state machine |
| `backend/orchestration/service.py` | API boundary (validation, typed result) |
| `backend/conversation/routes.py` | REST conversation endpoints |
| `backend/conversation/stream.py` | `WS /api/voice/stream` |
| `backend/conversation/auth.py` | JWT query-param + Origin validation for the socket |
| `backend/generation/causal.py` | Opt-in instruct generator (chat template, CPU/CUDA device report) |
| `backend/generation/service.py` | `answer_generatively(..., generator=, history=)` — same gate/verifier for both engines |
| `src/lib/voiceStream.ts` | WebSocket client, MediaRecorder capture, MP3 playback, barge-in, metering |
| `src/components/common/VoiceStreamButton.tsx` | Streaming control + analyser-driven bars |
| `src/context/WorkspaceContext.tsx` | Renders the server's history; conversation-mode sends use the stateful endpoint |
| `compose.yaml` | `redis` service (internal only) + `REDIS_URL` |
| `backend/evaluation/lifecycle_authority.py` | Connection-bound create/drop/use authority (server privileges) |
| `backend/evaluation/triad.py` | Faithfulness / answer relevance / context precision, deterministic |
| `backend/scripts/provision_local_eval_cluster.py` | Operator act: cluster, `documind_eval` role, `CONNECT` revoked on the app DB |
| `backend/scripts/check_eval_db_authorization.py` | Reports the authority's verdict without running a lifecycle |
| `backend/tests/integration/rag/test_triad_measurement.py` | Measures the triad through the production pipeline |
| `backend/evaluation/reports/triad_2026-10-23/` | The measured triad run (§6c) |

## 3. Turn semantics

```
START → load_history → resolve_query → retrieve ─┬→ rerank_evidence → generate ─┐
                                                 └→ abstain ──────────────────────┴→ remember → END
```

* `retrieve` calls `generation.service.retrieve_evidence` — the production
  pipeline. There is no parallel retrieval implementation.
* `rerank_evidence` orders passages by the QA model's own span probability for
  that passage. Ordering only: nothing is dropped and `SourceChunk.score` keeps
  its pgvector meaning.
* `generate` calls the unchanged `answer_generatively`, so the answerability
  gate, claim verification, mark-depth planning and withholding policy have one
  implementation. The engine is injected: instruct model when configured and
  loadable, otherwise the provisioned Flan-T5.
* `remember` appends the user turn and any produced answer, then persists the
  reliability record. An abstention stores the question only — an empty
  assistant message is not memory.
* `abstain` runs when retrieval returns nothing; no model is called.

Follow-up resolution is deterministic: a question of ≤ 6 words, or one starting
with a continuation cue, is retrievable only after prefixing the previous user
question. It widens retrieval; it never becomes a fact source.

## 4. State, isolation, failure

* Key: `documind:conversation:{user_id}:{session_id}`; both identifiers are
  validated against `^[A-Za-z0-9_-]{1,64}$` before use, and `user_id` always
  comes from the JWT. A client cannot address another user's conversation.
* Redis writes are `RPUSH` + `LTRIM` + `EXPIRE` (three atomic commands), so
  concurrent appends cannot lose each other's messages.
* TTL and history length come from `CONVERSATION_TTL_SECONDS` /
  `CONVERSATION_HISTORY_LIMIT`. Per-message content is capped at 8000 chars.
* **Redis unreachable → process-local store, reported.** `memoryBackend` is
  `"redis"` only when `PING` succeeded; otherwise it is `"memory"` with the
  connection error. This is the state of the current workspace (§6).
* Socket authentication also validates `Origin` against the CORS allowlist
  (cross-site WebSocket hijacking), and accepts a missing `Origin` for
  non-browser clients.

## 5. Voice protocol

Client → server: `session`, `audio_start`, binary frames, `audio_end`, `text`,
`barge_in`, `end`.
Server → client: `ready`, `status`, `transcript`, `answer`, `audio_start`,
binary MP3, `audio_end`, `interrupted`, `error`.

Barge-in cancels the running turn task; the client receives `interrupted` and
no further frames for that turn. Audio is written to an OS-generated temporary
file for Whisper and deleted on every path. Audio bytes per turn are capped at
the same upload limit as REST.

## 6. Measured evidence

Environment: Windows, `backend/venv` (Python 3.11). Sections 6a and 6b below
were measured at different times and their torch builds differ:
**6b (2026-10-22, CUDA)** used `torch 2.13.0+cu126` (`cuda.is_available() == True`,
RTX 3050 Laptop, 4096 MiB, `bitsandbytes` 0.50.2, `accelerate` 1.15.0), which
replaced the CPU-only build used for 6a. At the time of 6a/6b no Redis server,
no Docker and no PostgreSQL server were running in this workspace (ports 6379
and 55433 refused). The PostgreSQL cluster on 55433 was provisioned later, for
§6c (`scripts/provision_local_eval_cluster.py`); Redis remains absent.

| Check | Result |
|---|---|
| `pytest -q tests/unit` | **1681 passed, 23 skipped** |
| `pytest -q tests/integration` | **310 passed**, 1 pre-existing error (`tests/integration/rag/test_real_e2e_validation.py` refused by the fail-closed create-authorization gate before any I/O). **Superseded by §6c:** that test now passes against an authorized disposable database |
| Conversation REST + socket protocol tests | **25 passed** (`tests/integration/conversation/`) |
| Memory + graph tests | **46 passed** (`tests/unit/session/`, `tests/unit/orchestration/`) |
| `npm run typecheck`, `npm test`, `npm run build` | clean; **38 tests passed** (12 new for the voice client) |
| LangGraph smoke run | `StateGraph` + `MemorySaver` compile and `ainvoke` |
| Instruct generation (real, CPU) | `Qwen/Qwen2.5-0.5B-Instruct`, float32, 10-mark answer in **2884 ms**: `"The lidar calibration interval is 6 months. This is specified in the maintenance.pdf [1] at page 4."`; verifier returned `PARTIALLY_SUPPORTED` (1 of 2 claims supported) — the honest outcome, not a pass |
| Memory footprint (RSS, CPU) | baseline 189 MiB → **2169 MiB after load** (0.5B × fp32) → 2377 MiB process peak during generation |

At the time of 6a, `Qwen/Qwen2.5-1.5B-Instruct` was not in the HF cache and no
VRAM number could be produced because that torch build could not reach the GPU.
Both limits were removed in 6b.

### 6b. Phase F — 4-bit 1.5B on the GPU (2026-10-22, measured)

`backend/generation/causal.py:plan_loading()` chose `kind="4bit"`,
`device="cuda"`, `dtype="float16"`, `device_map="auto"` (reason: *CUDA is
available and bitsandbytes is importable*). Weights: `Qwen/Qwen2.5-1.5B-Instruct`
from the local HF cache, NF4 with double quantisation, fp16 compute. Command:
`./venv/Scripts/python.exe scripts/measure_conversation_vram.py --model
Qwen/Qwen2.5-1.5B-Instruct --marks 10`.

| Measurement | Value |
|---|---|
| Load time (weights from local cache) | **16.8 s** |
| `torch.cuda.max_memory_allocated()` after generation | **1155 MiB** |
| `nvidia-smi` used before load / after load / after generation | 0 / **1218** / **1276 MiB** |
| Budget | < 3.5 GB — met with ~2.2 GB to spare (tightened to a hard 3000 MiB on 2026-10-24, see §6d) |
| 10-mark generation, prompt with 1 block + 2 history turns | **3.9 s** (`max_new_tokens=384`) |
| Answer | grounded, cites `[1]`, no invented values |

Two defects were found by that run and fixed in the same step, neither by
relaxing a verifier threshold:

1. **The prompt no longer carries the block's provenance label.** With
   `[1] (maintenance.pdf, page 4, section: Calibration) …` in the evidence line,
   the 1.5B model copied the label into its answer ("… every 6 months, as stated
   in maintenance.pdf [1], page 4"). "page 4" is a value the cited block does
   not contain, so the verifier rejected a correct answer. The label is still
   returned to the user from `blocks` metadata; the model now sees the number
   and the quotable text only.
2. **A claim may quote the provenance of the block it cites.**
   `generation/verification.attributable_text()` appends the block's own label
   to the text support is checked against. The model still names the document
   when an earlier turn did (chat history is replayed), and that mention is
   evidence metadata, not an outside fact. Thresholds (`SUPPORT_RATIO`,
   `NUMERIC_SUPPORT_RATIO`) are unchanged.

After both changes the same 10-mark question returned `PARTIALLY_SUPPORTED`
(1 of 2 claims supported): the warranty claim was rejected by
`numeric_entity_alignment` because the evidence's "… 60 C. Warranty: …"
boundary is read as an abbreviation, so the anchor and value sentences differ.
That is a pre-existing splitter/entity limitation on a multi-part question, not
a 4-bit or 1.5B-specific result, and it is reported rather than papered over.
Tests after the change: `pytest -q tests/unit/generation tests/unit/chat
tests/unit/orchestration` → **431 passed**.

Prior measured context that still applies: Qwen2.5-0.5B as a *single-shot*
generator scored EM 0.093 vs 0.129 for Flan-T5-base and was 8.7× slower
(`DOCUMIND_MODEL_SELECTION_2026-10-17.md`). This change does not overturn that:
the instruct engine is opt-in, and the conversation path inherits the same
verifier and answerability gate.

### 6c. Phase G — authorized disposable database, measured triad (2026-10-23)

**The guard changed, the policy did not.** Step 1.6K refused every create, drop
and row cleanup because no *enforceable* authority existed. That is still true
of every declaration a caller can make — a URL, a database name, an environment
variable, a `DisposalProof` object. What now exists is a boundary the server
enforces: `backend/evaluation/lifecycle_authority.py` asks PostgreSQL, on the
connection that will do the work, and authorizes only when all of the
following hold:

1. `current_database()` is the database the DSN names (a `use` probe runs
   inside it; create/drop probe `postgres`);
2. the role is neither `SUPERUSER` nor `CREATEROLE`;
3. the role is denied `CONNECT` on the application database
   (`has_database_privilege`);
4. `create` additionally needs `CREATEDB`; `drop`/`use` additionally need
   ownership (`pg_database.datdba` matches the connected role).

Every failure — no server, bad credentials, timeout, empty answer — refuses and
returns the failed check by name. `scripts/provision_local_eval_cluster.py` is
the operator act that creates the `documind_eval` role and revokes `CONNECT`
on the application database from `PUBLIC` and from that role. The fixture's DDL
now runs on **that role's own credentials** (`psql_value(dsn, ...)`), so the
server applies the same ownership rule the gate checked; it previously borrowed
the application's superuser connection.

| Check | Result |
|---|---|
| `pytest tests/integration/rag/test_real_e2e_validation.py` | **1 passed in 100.87 s**; steps 4-7 all PASS; database created, migrated to `008`, pgvector 0.8.6, 14 tables, then dropped |
| `pytest -q tests/unit` | **1731 passed, 23 skipped** |
| `pytest -q tests/integration` (authorized disposable DB) | **325 passed, 1 failed**: `test_voice_stream.py::TestHandshake::test_session_is_acknowledged_with_real_backend_state` — order-dependent ("did not receive 'ready'; got ['ready']"); it passes alone and the whole `tests/integration/conversation` module passes (25 passed). Not caused by this change and not fixed by weakening it |
| `pytest tests/unit/evaluation` | **783 passed, 10 skipped** |
| Guard with no verifiable connection | every gate refuses; `scripts/check_eval_db_authorization.py` reports the same |
| Application role (superuser) pointed at the disposable database | refused: *"role 'documind' is a superuser"* |

**Triad (Phase G, measured 2026-10-23).** `evaluation/triad.py` computes the
three quantities from what the pipeline produced; `evaluation/reports/triad_2026-10-23/`
holds the run. Six questions over a three-document corpus ingested into the
disposable database, through the production `Brain` + retriever + extractive QA
model (`top_k=5`):

| Metric | Value | Definition |
|---|---|---|
| Faithfulness | **0.60** (3/5 claims) | supported claims / claims, deterministic verifier |
| Answer relevance | **0.2659** | `cosine(embed(question), embed(answer))` |
| Context precision | **0.5611** | average precision@k over blocks supporting a stated claim |
| Abstention | 1 of 6 | the unanswerable question (`INSUFFICIENT_EVIDENCE`) |

Per question: lidar interval 1.0 / 0.1585 / 0.8056; warranty 1.0 / 0.1252 /
1.0; bolt torque 1.0 / 0.2488 / 1.0; Darwin year 0.0 / 0.3009 / 0.0; France
capital 0.0 / 0.4959 / 0.0; tungsten (abstained). 58 structure-graph edges were
retrieved with the context.

Three limits are part of the result, not footnotes:

1. **These are not Ragas/TruLens scores.** Those libraries judge with an LLM;
   no judge is credentialed here, so the deterministic verifier stands in and
   the substitution is named in the report. A judge-free number must not be
   quoted as a Ragas number.
2. **A bare span is unscoreable.** The two zeros are the answers `"1859"` and
   `"Paris"`; the verifier refuses single-token text ("claim text is not
   sufficiently present in the evidence"), so faithfulness is 0 by definition.
   The reasons are recorded per claim in `summary.json`; this is a limit of the
   judge on bare spans, not evidence that the spans are ungrounded.
3. **The graph retrieved is a structure graph.** Its edges (`NEXT`, `PREV`,
   `SAME_PAGE`, `SAME_SECTION`) join chunks already in the context and carry no
   text, so they are counted and never credited as evidence. There is no
   entity-relation knowledge graph in this repository (§53.6).

The frozen benchmark was **not** regenerated: this measurement is on its own
corpus and reports its own numbers.

### 6d. Strict 3000 MiB ceiling — enforced and re-measured (2026-10-24)

The hardware target was tightened from "under 3.5 GB" to a **hard 3000 MiB ceiling**.
Two things changed, only one of which is a measurement.

**1. The ceiling is now enforced, not merely observed.** `generation/causal.py` exports
`VRAM_CEILING_MIB = 3000.0` and checks the *measured* allocator peak after loading the
weights and again after decoding, raising `VramBudgetExceeded` (a
`GenerationUnavailableError`, so the API answers 503) instead of returning an answer under a
violated budget. The prompt is bounded (`MAX_INPUT_TOKENS`, 6 blocks × 900 chars, 6 history
turns × 600 chars, question capped at `MAX_QUESTION_CHARS`), and the per-format decode budget
is capped at 640 new tokens for a 15-mark answer. `scripts/measure_conversation_vram.py`
judges the **driver** figure against 3000 MiB and exits non-zero (2) when it is exceeded; the
allocator figure is reported next to it because it omits the CUDA context and the
`bitsandbytes` kernels. The model was **not** downgraded to 0.5B: 1.5B NF4 stays the
default because it fits, and the 0.5B comparison already measured as a quality regression.

**2. Measured again on the same machine (RTX 3050 Laptop 4 GB, `torch 2.13.0+cu126`,
`bitsandbytes` 0.50.2, `Qwen/Qwen2.5-1.5B-Instruct` NF4, `device_map="auto"`):**

| Case | Driver peak (`nvidia-smi`) | Allocator peak | Result |
|---|---|---|---|
| Load only | 1217 MiB | 1125 MiB | ok (14.3 s load) |
| 10-mark answer (2026-10-22 run) | 1276 MiB | 1155 MiB | ok |
| 15-mark `--stress` (1440-token prompt, 6 blocks + 12 history turns; answer stopped at ~40 tokens) | **1573 MiB** | 1424 MiB | ok, exit 0, 3.5 s |
| Cap sweep, 640 new tokens forced (`min_new_tokens`) | | | |
| 1440 prompt tokens | 1577 MiB | 1424 MiB | ok |
| 2048 prompt tokens | 1815 MiB | 1690 MiB | ok |
| 2560 prompt tokens | **2129 MiB** | 1983 MiB | ok — this is the shipped cap |
| 3072 prompt tokens | 2481 MiB | 2317 MiB | ok, little headroom |
| 4096 prompt tokens (the old cap) | **3433 MiB** | 3168 MiB | **over the ceiling** — why the cap was lowered |

The gap between allocator and driver peaks is CUDA context + `bitsandbytes` scratch, which
is why the *driver* figure is the one compared against 3000 MiB. The dominant growth is not
the KV cache (~28 KiB/token for this model) but the prefill transient: the LM head materialises
`tokens × 151936` logits, ~1.24 GiB at 4096 tokens. That is why the earlier 4096-token cap
measured 3433 MiB and the shipped cap is 2560 tokens, at which the worst case the code allows
(prompt at the cap plus 640 forced new tokens) is 2129 MiB — ~870 MiB of headroom.

**Unchanged:** no Ollama, no vLLM, no external API; `local_files_only=True` still forces the
load to use the provisioned HF cache; the `documind-qa` DistilBERT weights are untouched.

## 7. Limits (must be stated)

1. Redis is deployed in `compose.yaml` but **not running** in this workspace;
   the verified fallback is process-local, so it is not shared across workers
   and not durable.
2. 4-bit loading is measured on this one machine (RTX 3050 Laptop, 4 GB). On a
   host with CPU-only torch or without `bitsandbytes`, `plan_loading()` falls
   back to **float32 CPU** and says so in `/api/health` and the socket's
   `ready` frame; a 1.5B model in float32 needs ~6 GB RSS and is slow. The
   4-bit figures are an allocator peak plus the driver's own reading — not a
   guarantee for another GPU, driver or context length.
3. The mark-depth requirement (5/10/15 differentiated) remains unmet; the
   conversation path reuses the existing planner unchanged.
4. The evaluation triad is measured on the **real E2E path** (§6c: faithfulness
   0.60, relevance 0.2659, context precision 0.5611 over six questions), not on
   the frozen benchmark, which must not be regenerated. The three limits listed
   in §6c travel with those numbers. The disposable database is authorized only
   for the least-privileged `documind_eval` role; a run pointed at the
   application role is refused as a superuser, and a run with no verifiable
   connection is refused before any socket is opened.
5. Streaming is chunked-after-synthesis: gTTS produces the whole MP3 before
   frames are sent. Token-level streaming TTS is not implemented.
6. The frontend has no browser-level test of microphone capture or audio
   playback (jsdom cannot provide either); the transport, phases, playback and
   barge-in logic are covered by unit tests with stubs.
7. The 3000 MiB ceiling is a measured per-machine figure, not a guarantee: it is
   asserted against the measured peak on this GPU. On a machine with a different
   driver, a larger CUDA context, or CPU-only torch the same code reports its
   actual plan and peak (fp32 CPU fallback is *not* VRAM-bound and reports
   "not measured"). The prompt and decode caps bound the worst case at 2129 MiB
   here, but the enforcement check runs *after* decoding, so a hypothetical
   breach on a different device fails the request rather than shrinking it.
