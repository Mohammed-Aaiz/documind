# DocuMind — CONTEXT (short orientation)

This file is a **short, factual index** of the repository. It exists so an agent can
orient itself in a minute.

> **The authoritative long-form project context is
> [`DOCUMIND_PROJECT_CONTEXT.md`](./DOCUMIND_PROJECT_CONTEXT.md).** Read that file too
> before making any architectural change. This file must never contradict it; if they
> disagree, `DOCUMIND_PROJECT_CONTEXT.md` wins and this file is the one to fix.

Everything below is verified against the working tree. Do not restate these facts from
memory — re-check the files if a change is being planned.

---

> **CURRENT DIRECTION (2026-10-17).** The agreed product objective, the permanent
> implementation roadmap (**Phase 0–9**, with §57's Phase 0–7 numbering mapped by §0.4.1) and the
> research-to-implementation decision rule are in
> [`DOCUMIND_PROJECT_CONTEXT.md`](./DOCUMIND_PROJECT_CONTEXT.md) **Part 0 (§0)**. Read §0 first.
> **Nothing in Part 0 is authorization to implement anything**: §59 gates, §55 status and §61 open
> decisions still bind, and the architecture gate is **NOT OPEN**.
>
> **DIRECTION RESET (2026-10-09).** The lecturer feedback, capability matrix and the original
> Phase 0–7 roadmap remain preserved in **Part II (§50–§63)** and are extended — not replaced — by
> Part 0. **Historical research results** (populations P1/P2/P3, H1 metrics, F2/G/H1/H1-R/E0) are
> preserved in **§0.7** and are HISTORICAL, not current measurements.

---

## 1. What DocuMind is

A multimodal AI document-intelligence workspace. Pipeline:

```
UPLOAD → EXTRACT → CHUNK → EMBED → RETRIEVE → UNDERSTAND → ANSWER → EVIDENCE → RELIABILITY
```

**Non-negotiable rule: never fabricate functionality.** No fake answers, metrics,
confidence scores, retrieval results, embeddings, vector search, media verification or
processing states. If something is not implemented, keep it unavailable and say so
honestly.

## 2. Repository layout (real)

```
(repository root)/
├── src/                     # React + TypeScript + Vite frontend  (NOT "frontend/")
│   ├── pages/               # exactly 5 pages (see §4)
│   ├── components/{3d,common}
│   ├── context/
│   ├── lib/api.ts           # the ONLY backend API client
│   ├── types/
│   ├── App.tsx, main.tsx, index.css, vite-env.d.ts
├── backend/                 # FastAPI backend
│   ├── main.py              # app, CORS, lifespan (runs migrations), /api/health
│   ├── config.py            # Settings (pydantic-settings) + get_settings()
│   ├── tokenization.py      # exact token counting via the QA tokenizer
│   ├── outcomes.py          # Outcome enum + outcome_from_rag()
│   ├── storage/             # database.py (engine/Base/get_db) + file_store.py
│   ├── auth/                # routes.py, models.py, schemas.py, deps.py
│   ├── documents/           # routes, models, schemas, processing, chunking, validation
│   ├── embeddings/          # model.py (all-MiniLM-L6-v2), routes.py
│   ├── chat/                # qa_model.py (DocuMind DistilBERT), rag.py, routes.py, models.py
│   ├── generation/          # additive local Flan-T5 path: planning, engine, verification, routes
│   ├── brain/               # planner, executor, adapters, gate, classifier, response, types
│   ├── reliability/         # routes.py, models.py   (/api/reliability/last-query)
│   ├── verification/        # routes.py, models.py   (local ViT image classifier; not forensic proof)
│   ├── settings/            # routes.py              (/api/settings)
│   ├── user/                # models.py + __init__.py ONLY — /api/user/* routes REMOVED (404)
│   ├── migrations/          # alembic env.py + versions/000..008
│   ├── alembic.ini, requirements.txt, pytest.ini
│   ├── scripts/             # setup_db.py, create_test_user.py, cleanup_smoke.py, start_server.py
│   ├── tests/               # pytest suite (SQLite-backed, no Postgres needed)
│   ├── models/documind-qa/  # TRAINED MODEL WEIGHTS — never edit
│   ├── uploads/             # runtime upload storage (gitignored)
│   └── architecture/        # phase 4F.6 audit + evidence records
├── runbooks/                # incident runbooks
├── prompts/                 # agent prompt templates (this directory)
├── AGENTS.md, CONTEXT.md    # agent definitions / this file
├── DOCUMIND_PROJECT_CONTEXT.md  # AUTHORITATIVE long-form context
└── package.json, vite.config.ts, tailwind.config.js, index.html
```

The tree above shows the packages that make up the running product; the repository also
contains research/evaluation directories not part of the request path —
`backend/phases/phase4d/`, `backend/phases/phase4e/`, `backend/phases/phase4f/`,
`backend/phases/phase4f_gpu/`, `backend/evaluation/`, `backend/models/experiments/`,
plus operational scripts in `backend/scripts/` and the relocated phase-3/4 measurement
harnesses in `backend/evaluation/experiments/` (`run_*.py`). Historical phase paths are
translated by `backend/architecture/PATH_MIGRATION.md`.

**Paths that do NOT exist** (older prompts referenced them — they were wrong):
`frontend/`, `backend/api/`, `backend/services/`, `backend/core/`, `backend/models/llm/`,
`models/llm/final_model/`, `faiss_indexes/`.

`backend/models/` is **model artifacts only**: `documind-qa/` (trained QA weights — read-only),
`media-verification/`, `whisper/`, `experiments/` and a README. It is **not** the SQLAlchemy models
directory — ORM models are `backend/<feature>/models.py`. `backend/user/` now holds only
`models.py` + `__init__.py` (ORM); it registers **no** routes — the four `/api/user/*` paths were removed and
return 404 (identity: `GET /api/auth/me`; settings: `GET/PATCH /api/settings`).

## 3. Stack (real)

**Backend** — Python 3.11 venv (`backend/venv`), FastAPI 0.115.6, SQLAlchemy 2.0.36
(async), asyncpg 0.30.0, Alembic 1.14.1, pgvector 0.5.0, sentence-transformers
(`all-MiniLM-L6-v2`, 384-dim), Hugging Face Transformers + PyTorch (local DistilBERT QA),
python-jose (JWT HS256), passlib/bcrypt, PyMuPDF, python-docx, pytest 8.3.4 +
pytest-asyncio + aiosqlite.

**Frontend** — React 18, TypeScript 5.7, Vite 6, Tailwind CSS 3, Three.js.

**Database** — PostgreSQL with the **pgvector** extension (server-side).
Vector similarity is real pgvector cosine distance: `1 - (embedding <=> CAST(:e AS vector))`.
FAISS, SQLite and in-memory cosine search are **forbidden substitutes**.

## 4. Pages and real endpoints

Exactly five pages: `src/pages/LoginPage.tsx`, `src/pages/WorkspacePage.tsx`,
`src/pages/VerificationPage.tsx`, `src/pages/ReliabilityPage.tsx`,
`src/pages/SettingsPage.tsx`.

| Method | Path | Status |
|---|---|---|
| GET | `/api/health` | real (does **not** touch the DB) |
| POST | `/api/auth/login` | real |
| POST | `/api/auth/logout` | real |
| GET | `/api/auth/me` | real |
| POST | `/api/documents/upload` | real (201) |
| GET | `/api/documents` | real |
| GET | `/api/documents/{id}` | real |
| DELETE | `/api/documents/{id}` | real |
| POST | `/api/documents/{id}/reprocess` | real |
| POST | `/api/embeddings/generate` | real |
| POST | `/api/embeddings/search` | real |
| POST | `/api/chat/ask` | real (RAG + custom QA, extractive default) |
| POST | `/api/generation/answer` | real — additive local Flan-T5 generative path with verification (5/10/15 marks; depth not yet differentiated) |
| GET/POST | `/api/chat/sessions` | real |
| GET/POST | `/api/chat/sessions/{id}/messages` | real |
| GET | `/api/reliability/last-query` | real |
| GET/PATCH | `/api/settings` | real |
| GET | `/api/documents/{id}/insights` | real (stored-data-only structure/embedding/graph insights) |
| POST | `/api/verification/analyze` | real — local ViT image classifier (classification, **not** forensic proof) |
| POST | `/api/voice/transcribe` | real — local Whisper STT |
| POST | `/api/voice/synthesize` | real — gTTS TTS (external network service) |

There is **no signup endpoint** — create users with `python scripts/create_test_user.py`.

The declared `/api/user/{profile,preferences}` routes were **removed**, not implemented:
identity is served by `GET /api/auth/me` and persisted settings by `GET/PATCH /api/settings`.

## 5. Implementation status (honest)

> The authoritative, label-complete capability matrix is `DOCUMIND_PROJECT_CONTEXT.md`
> Part II §55 (labels defined in §63). Consult it before asserting any status.

- **IMPLEMENTED — VERIFIED:** authentication, document ingestion (PDF/DOCX/TXT),
  structure extraction + persistence (sections/paragraphs/tables/rows/blocks),
  embeddings, pgvector vector search, document-native structure graph, dual-path RRF
  fusion (0.70/0.30, k=60), RAG with the trained DocuMind DistilBERT **extractive** QA
  model, reliability/evidence, chat sessions, settings, document insights, the frontend,
  the research evaluation harness.
- **Grounded generative answering (PARTIALLY IMPLEMENTED, additive — 2026-10-17):** local,
  offline `google/flan-t5-base` behind `POST /api/generation/answer`, with evidence-only prompt,
  deterministic claim/citation verification and a withhold-on-unattributable policy. Owner decision
  recorded in `DOCUMIND_PROJECT_CONTEXT.md` §0.8 (resolves §61.1/§61.2 for the local scope only).
  **Limits that must be stated:** the 10/15-mark depth requirement is **not met** (5/10/15 output
  measured, not differentiated by mark depth), the P3 benchmark and mark-depth evaluations **have
  been run** (2026-10-17), and the production verifier remains **lexical**, not entailment.  The relation-aware candidate is opt-in: after question-to-attribute binding it has better support
  F1 (0.977 vs 0.880) and no false accepts (0/9 vs 4/9), but still raises 2 false contradictions
  and is ~70× slower, so the production default is unchanged (`DOCUMIND_PROJECT_CONTEXT.md`
  §0.8.6, `backend/architecture/DOCUMIND_ANSWER_CLAIM_EVALUATION_2026-10-18.md` §12). Claim
  extraction is now abbreviation-aware (`Dr.`, `U.S.`, `e.g.`, initials); the corrected population
  is the versioned `answer_claims_v2` (103 claims), while `answer_claims_v1` stays frozen and
  reproducible via `--dataset v1` (§0.8.7, architecture §13). Evidence segmentation uses the same
  rule, which resolved the `Dr. Sarah Chen` false reject and raised v2 relation support recall to
  .955 (§0.8.8, architecture §14). Answer coverage was then diagnosed: 75/140 answerable questions
  produced an answer, 49 refused by the answerability gate, and 44 of those refusals were caused by
  document-structure words (`section`, `content`, `near`, `boundary`, `table`, …) being treated as
  topic terms. Excluding those words (ordinals deliberately kept) raised answer coverage to 99/140,
  exact match 0.129 → **0.150** and token F1 0.257 → **0.309**, with unanswerable spurious unchanged
  at 2/42 (§0.8.9, `backend/architecture/DOCUMIND_ANSWER_QUALITY_2026-10-18.md`). Mission 5 then fixed
  the dominant withholding defect: in a pipe table the entity check anchored on the header, so correct
  cells (`1,000 req/min`, `+4.2%`) were withheld. The table-aware check binds the asked column from the
  header and keeps wrong-column/compound values withheld; answered 99 → **100/140**, token F1 0.309 →
  **0.310**, lexical claim F1 0.880 → **0.889**, unanswerable spurious unchanged at 2/42, and one wrong
  multi-column answer is no longer returned (§0.8.10,
  `backend/architecture/DOCUMIND_TABLE_ENTITY_ALIGNMENT_2026-10-18.md`). The Mission 4 unsupported/citation
  "regression" is a verified metric artifact: rejected claims from withheld answers are counted while
  returned answers carry the same 5 unsupported claims. Still open: 13 gate refusals, section-body and
  over-wide list withholding, 28 non-claims and 9 supported but off-target claims (needing question
  attribute reasoning). The DistilBERT
  extractive model remains the **default** engine and the baseline.
  Mission 6 (2026-10-21) fixed the dominant remaining defect: a table lookup was delegated to the
  seq2seq model, which answered **0 of 40** table questions correctly. A deterministic table reader now
  resolves the requested row (and column, for a cell) from the evidence, returns that cell/row verbatim,
  and is still judged by the unchanged verifier; it is reported as `model: "deterministic-table"`.
  Three smaller fixes ship with it: a one-word answer that is a stopword (`Other`) is verifiable, a table
  header render is no longer appended as a mark-depth "supporting point", and a copied `[n] (label)`
  prompt marker is stripped from answers. On the unchanged 182-row benchmark: answered 100 → **109/140**,
  exact match 0.150 → **0.450**, token F1 0.310 → **0.562**, unsupported-claim rate 0.217 → **0.136**,
  citation accuracy 0.783 → **0.864**, unanswerable spurious unchanged at 2/42; 42 newly correct and 0
  regressions at 10 marks (§0.8.11, `backend/architecture/DOCUMIND_TABLE_GROUNDING_2026-10-21.md`).
  Mission 7 (2026-10-21) applied the same rule to ordered lists: 20 benchmark questions supply a
  heading plus one item per line and the reference is that item verbatim, yet the model answered
  **2 of 20** correctly, and the verifier withheld 13 more rows whose item was correct because its
  entity check anchored on the heading. A deterministic list reader now returns the requested item
  (by ordinal position, or by the item the question names) verbatim, still judged by the unchanged
  verifier, reported as `model: "deterministic-list"`, and never mark-elaborated; a position is
  refused when the evidence excerpt was truncated. On the unchanged 182-row benchmark: answered
  109 → **118/140**, exact match 0.450 → **0.579**, token F1 0.562 → **0.664**, withheld 20 → **13**,
  unsupported-claim rate 0.136 → **0.082**, citation accuracy 0.864 → **0.918**, unanswerable
  spurious unchanged at 2/42; 18 newly correct and 0 regressions. 60 of 182 rows are now answered
  without running the model (p50 0 ms). An independent review of the change found and fixed seven
  defects (truncated-excerpt positions, heading recognition, two-ordinal abstention, verifier
  symmetry, a vacuous test), none reachable on the frozen benchmark. Still open: 11 gate refusals,
  13 withheld, 35 wrong-attribute prose answers, 7 section-title annotation artifacts, 2/42
  spurious (§0.8.12, `backend/architecture/DOCUMIND_LIST_GROUNDING_2026-10-21.md`).
- **IMPLEMENTED (limited / accuracy unverified):** image media verification (local ViT
  classifier — a classification, not forensic proof), voice STT (local Whisper) and TTS
  (gTTS — external network service).
- **Document status contract (Phase 1a, 2026-10-15):** `ready` = every page produced usable
  content (or the format has no pages); `partial` = searchable, but at least one page produced
  no usable text; `error` = no page produced usable content, or a pipeline step raised.
  `partial` is never `ready` and is never rendered as success. Verified **with limitations**.
  The page-usability threshold (`MIN_USABLE_CHARS = 4` in `backend/documents/processing.py`,
  approved by the owner 2026-10-15), the measured threshold evidence, the unresolved
  reprocessing data-loss risk and the isolated OCR benchmark results are recorded in
  [`backend/architecture/DOCUMIND_PHASE1A_DECISION_RECORD_2026-10-15.md`](./backend/architecture/DOCUMIND_PHASE1A_DECISION_RECORD_2026-10-15.md);
  **do not change that value, the verdict rule or the `error` reason set without owner approval.**
- **HISTORICAL RESEARCH (not current results):** the Phase 3D–4F record is preserved in
  `DOCUMIND_PROJECT_CONTEXT.md` §0.7 — evaluation populations P1 918 / P2 221 (UNVERIFIED) / P3 182,
  H1 (EM 0.0%, F1 11.0%, abstention 45.2%, spurious 54.8%), the H1-R split-index audit (holdout 22 vs
  14, 12 unused negatives), and F2/G/H/E0. Do not cite these as fresh measurements.
- **NOT IMPLEMENTED — must report honestly:** OCR / scanned-document support (no OCR engine is
  installed in `backend/venv` and none is selected — an isolated benchmark measured RapidOCR for
  readiness only; a scanned-only document is reported `error` / `no_text_layer_ocr_disabled` and its
  pages as unaccounted), chart
  understanding, document-manipulation detection, **a complete** grounded generative answer engine
  (the additive path is partial — see §0.8), **mark-differentiated** exam answers (5/10/15 are
  accepted but not yet differentiated), mathematical reasoning, knowledge-graph
  (entity–relation) retrieval / GraphRAG. The `/api/user/*` profile/preferences routes were
  **removed** — identity: `GET /api/auth/me`; persisted settings: `GET/PATCH /api/settings`.

## 6. Quality gates before saying "done"

```bash
# Backend — unit/integration tests (SQLite-backed, no Postgres required)
cd backend && ./venv/Scripts/python.exe -m pytest tests -q

# Backend — static Alembic graph (must be a single head)
cd backend && ./venv/Scripts/python.exe -m alembic heads

# Frontend — typecheck + production build (run from the repo root)
npm run build
```

Genuine end-to-end verification additionally requires a reachable PostgreSQL + pgvector
database via `backend/.env`; the SQLite test suite does not exercise pgvector, the real
QA model or migrations. Never report an SQLite pass as proof of an end-to-end pass.

One test is expected to **error** rather than pass: `tests/integration/rag/test_real_e2e_validation.py`
is refused by the fail-closed create-authorization gate before it opens a socket, so a
reachable PostgreSQL does not make the suite error-free (Step 1.6K).
