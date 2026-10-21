# FreeBuff Agent Directory

  Agent              Responsibility
  ------------------ ------------------------------------------------
  COORDINATOR        planning, delegation, documentation, ownership
  DATABASE_AGENT     schema, ORM, migrations, DB scripts
  BACKEND_AGENT      FastAPI/backend behavior, dependency declarations
  AI_AGENT           embeddings, retrieval, QA, Brain, graph
  FRONTEND_AGENT     React/TypeScript UI
  TEST_AGENT         pytest tests + pytest.ini
  EVALUATION_AGENT   research datasets, experiments, metrics, phase archive
  SECURITY_AGENT     independent security audit
  VERIFIER           independent read-only truth check

## Context (read before acting)

1. `DOCUMIND_PROJECT_CONTEXT.md` **Part 0 (§0)** — agreed product objective and the
   permanent **Phase 0–9** roadmap. §0.7 is the **historical** research record and is
   never current status. Then the sections §0 cites: §54, §55, §59–§62.
2. `CONTEXT.md` — short verified index (real tree, endpoints, honest status).
3. `AGENTS.md` — the operating contract; then your own file in this directory.

Use the status labels in §63. Do not restate a requirement from another context file as
`CONFIRMED`; only inspected implementation or authoritative evidence supports that label.
`PRD.md`, `ARCHITECTURE.md`, `DESIGN.md` and `README.md` hold detailed requirements and must
not be duplicated into the agent files.

## Recommended flow

``` text
COORDINATOR
    ↓
inspect + plan
    ↓
specialized agent(s)
    ↓
TEST_AGENT / EVALUATION_AGENT
    ↓
SECURITY_AGENT when relevant
    ↓
VERIFIER
    ↓
COORDINATOR closes documentation
```

One file has one implementation owner. Cross-boundary work is decomposed
by the Coordinator.
