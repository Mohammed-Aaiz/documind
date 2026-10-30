# DocuMind --- FreeBuff Agent Operating Rules

> **2026-10-30 production RAG implementation:** The owner's later instruction
> selects Groq as the sole product LLM. The implemented retrieval/index/archive
> changes and measured limits are recorded in
> `backend/architecture/DOCUMIND_PRODUCTION_RAG_IMPLEMENTATION_2026-10-30.md`.
> This supersedes older default-provider descriptions for this scope. Specialist
> dispatch was used for implementation; the primary agent completed remaining
> role-scoped checks after specialist execution became unavailable.

> **2026-10-27 owner-authorized rebuild:** For the current workspace/provider rebuild,
> `backend/architecture/DOCUMIND_WORKSPACE_REBUILD_2026-10-27.md` records the explicit
> owner override permitting Ollama as the default answer engine and explicitly configured
> Groq for hosted answers, with separate Student/Research sessions. It supersedes the
> older model/provider prohibition below for that scope only. Frozen evaluations,
> trained weights, user data, authentication and evidence integrity remain protected.
> Previously unassigned generation/orchestration paths belong to AI_AGENT;
> conversation/session and voice paths belong to BACKEND_AGENT, as listed in the record.
> The owner subsequently explicitly requested deletion of the previous custom LLM.
> Removal of `backend/models/documind-qa/` is authorized for this task, superseding
> the forbidden-path and weight-preservation rule for that directory only. No other
> model, uploaded document, evaluation asset or environment is authorized for deletion.

## 01. PURPOSE

This is the master operating contract for every FreeBuff agent working
on DocuMind.

The system uses specialized agents with explicit ownership boundaries.

Current agents: 1. COORDINATOR 2. DATABASE_AGENT 3. BACKEND_AGENT 4.
AI_AGENT 5. FRONTEND_AGENT 6. TEST_AGENT 7. EVALUATION_AGENT 8.
SECURITY_AGENT 9. VERIFIER

The Coordinator orchestrates. The Verifier independently checks.
Execution agents modify only files they own.

## 02. BEFORE WE START --- WHAT TO DO

Every agent must: 1. Read `DOCUMIND_PROJECT_CONTEXT.md`. 2. Read
`CONTEXT.md`. 3. Read `AGENTS.md`. 4. Read its own `agents/*.md`
contract. 5. Inspect current implementation before changing anything. 6.
Identify exact files required. 7. Confirm files are inside its Owns
list. 8. If a required file is outside ownership, request the owning
agent. 9. Define acceptance criteria before implementation. 10. Make the
smallest coherent change. 11. Validate with the appropriate command. 12.
Report exact evidence.

Never start by coding.

``` text
UNDERSTAND → INSPECT → PLAN → IMPLEMENT → VALIDATE → REPORT
```

### Context map --- what to read, and which file wins

Read in this order; do not duplicate their content into new files:

1. `DOCUMIND_PROJECT_CONTEXT.md` **Part 0 (§0)** --- the current agreed product
   objective and the permanent **Phase 0–9** roadmap. Read §0.1–§0.6 before any
   planning. §0.7 is the **historical** research record (populations P1/P2/P3, H1
   metrics, F2/G/H1/H1-R/E0) --- history, never current status. Then consult the
   sections §0 points to: §54 (measured limitations), §55 (capability matrix),
   §59/§60 (gates), §61 (open decisions), §62 (documentation discrepancies).
   **Part II (§50–§63) is preserved as the 2026-10-09 reset record; §57's Phase
   0–7 numbering is superseded by the §0.4.1 mapping only.**
2. `CONTEXT.md` --- short verified index of the real tree, endpoints and status.
   It must never contradict `DOCUMIND_PROJECT_CONTEXT.md`; that file wins.
3. `AGENTS.md` (this contract) and `agents/<your-role>.md`; `prompts/` mirrors the
   same ownership boundaries.
4. `PRD.md` (requirements), `ARCHITECTURE.md` (decisions and boundaries),
   `DESIGN.md` (UX rules), `README.md` (overview, API table, verification limits).
5. `backend/architecture/**` --- append-only evidence. Read the decision record
   that governs any behaviour you are about to change.

Use the status labels defined in §63 (`CONFIRMED`, `DECIDED`, `PROPOSED`,
`HISTORICAL`, `UNVERIFIED`, `BLOCKED`, `SUPERSEDED`). An item is not `CONFIRMED`
because another document repeats it, and a design document is not evidence that a
capability exists.

## 03. GENERAL RULES

### Truthfulness

Never fabricate answers, metrics, confidence, embeddings, retrieval
results, processing states, tests, model availability, deployment
status, or feature completion.

### Ownership

If a file is not in your Owns list: - do not edit it; - do not move
it; - do not delete it; - request the owning agent.

### Minimal change

Reuse existing architecture before introducing new abstractions. Do not
perform unrelated cleanup or speculative rewrites.

### Production/research separation

Production: `backend/` Tests: `backend/tests/` Research evaluation:
`backend/evaluation/`, plus the archived phase research under
`backend/phases/` — both owned by EVALUATION_AGENT

Production code must never import from tests.

### Forbidden paths

No agent may write:

``` text
backend/models/documind-qa/**
backend/venv/**
backend/phases/phase4f_gpu/**
backend/uploads/**
backend/.env
.env
dist/
node_modules/
```

`backend/architecture/**` is append-only evidence and Coordinator-owned.

## 04. CODE GUIDELINES

### Python

Use existing conventions, preserve async boundaries, use established
type hints, keep functions focused, avoid hidden global state, do not
swallow exceptions, and preserve API contracts unless explicitly
approved.

### FastAPI

Preserve router prefixes, validate input, scope resources to
authenticated users, return honest status codes, and do not expose
internal exception details.

### Database

PostgreSQL + pgvector is production truth. Alembic is the schema
migration path. Keep migrations linear. Never reset production data.

### Frontend

Use TypeScript and `src/lib/api.ts`. Do not hardcode backend data.
Represent loading, empty, error and unavailable states. Reuse
components.

### AI/Retrieval

Use the project QA model. Use pgvector. Preserve retrieval provenance.
Do not substitute FAISS, SQLite, external fallback models, or hardcoded
answers.

The implemented engine is the project's DistilBERT **extractive** QA model; it is
the current production behaviour and the permanent comparison baseline.
**Grounded generative AI is the DECIDED target primary answer engine but is
PLANNED, NOT IMPLEMENTED and not authorized** (§0.1, §0.4 Phase 2–3). Do not add
a generative provider, model, dependency, schema change or route without the
§61.1/§61.2 decisions and the §59.10 gate, and never describe the generative or
5-/10-/15-mark path as working.

### Tests

Tests live only under `backend/tests/`.

Never run:

``` bash
python tests/test_x.py
python test_x.py
```

Use:

``` bash
python -m pytest ...
```

## 05. SECURITY AND BEST PRACTICES

-   never expose secrets;
-   never commit `.env`;
-   never trust client-supplied ownership identifiers;
-   verify JWT-derived ownership server-side;
-   validate file types and sizes;
-   prevent path traversal;
-   use parameterized DB access;
-   avoid unsafe shell execution;
-   avoid arbitrary code execution;
-   validate external inputs;
-   do not leak stack traces or credentials;
-   treat uploaded documents as untrusted input;
-   preserve least privilege;
-   audit security-sensitive changes;
-   never disable security controls just to make tests pass.

Security remediation belongs to the agent owning the affected
implementation.

## 06. USEFUL COMMANDS

### Backend

``` powershell
cd backend
.env\Scripts\python.exe -m compileall .
```

### Tests

``` powershell
cd backend
.env\Scripts\python.exe -m pytest -q tests/unit
.env\Scripts\python.exe -m pytest -q tests/integration
.env\Scripts\python.exe -m pytest -q tests/e2e
.env\Scripts\python.exe -m pytest -q
```

### Database

``` powershell
cd backend
.env\Scripts\python.exe -m alembic heads
.env\Scripts\python.exe -m alembic history
.env\Scripts\python.exe scripts/setup_db.py
```

Never downgrade/reset/drop/recreate a live database without explicit
permission.

### Frontend

``` powershell
npm run build
```

### Git inspection

``` powershell
git status
git diff
git log --oneline -10
```

### Server smoke test

``` powershell
cd backend
.env\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Then:

``` powershell
curl http://127.0.0.1:8000/api/health
```

## 07. NEED HELP!

Stop and request help when: - a required file belongs to another
agent; - requirements conflict; - implementation contradicts
documentation; - a migration could damage data; - a security boundary is
unclear; - a model/data contract is unclear; - production changes may
invalidate research results; - required infrastructure is unavailable; -
destructive operations appear necessary; - ownership boundaries would
need to change.

### Handoff format

``` text
HELP REQUEST

Task:
Blocked by:
File(s):
Current behavior:
Expected behavior:
Why current ownership is insufficient:
Proposed change:
Risk:
Validation still needed:
```

Do not bypass ownership to finish faster.

## 08. AGENT EXECUTION PROTOCOL

Every task prompt should contain:

``` text
TASK
ROADMAP PHASE
OBJECTIVE
FIRST — INSPECT
IMPLEMENT
VALIDATE
ACCEPTANCE CRITERIA
DO NOT
FINAL REPORT
```

Final report:

``` text
Changed:
Files:
Tests:
Commands:
Observed results:
Remaining limitations:
Security considerations:
Handoff/next agent:
```

## 09. MASTER DEFINITION OF DONE

A task is complete only if requirements are understood, ownership is
respected, implementation is real, appropriate validation was executed,
failures are reported honestly, security was considered,
documentation/contracts are updated when necessary, and no unrelated
files were changed.
