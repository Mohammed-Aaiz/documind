# Mission 7 checkpoint (2026-10-21)

Persistent state so an interrupted run can resume without re-deriving it.

## Repository state at start

- HEAD `6baaa2a0773df66e5fb26814afbe67647fb43435`; 401 pre-existing working-tree
  entries, all untracked/modified before this mission and preserved.
- `backend/generation/`, `backend/evaluation/`, `backend/tests/unit/generation/`,
  `backend/architecture/` are untracked trees from Missions 3–6.
- No commit, staging, push or deployment this mission.

## Agent contracts and delegation capability

- Collection: `agents/agentic-coding-agents/` — 92 role files plus
  `AGENT-CONTRACT.md`. The 13 specialist files requested by the mission
  (17, 25, 33, 35, 36, 39, 51, 52, 57, 59, 60, 79, 82) have an **identical body**
  (`sha256` prefix `b228947fadff` of lines 6–53); only the role line differs.
- No runtime binds those identities. The available delegation mechanism spawns
  generic parallel workers (`spawn_agents` → `base3-fast-worker-deepseek-flash`,
  `code-searcher`), which are not the specialist personas.
- Therefore the contracts were **applied directly by the orchestrator**, and no
  claim of independent agent invocation is made. Repository ownership rules from
  `AGENTS.md` (`generation/`, `evaluation/`, `tests/` = BACKEND/AI/EVALUATION/
  TEST agents) were followed by the single orchestrator.

## Baseline hashes and metrics

- Benchmark `1166bf4f…a41d0`, 182 rows (140/42), verified before every run.
- Claim dataset `answer_claims_v2`, `f06795eb…`, unchanged.
- Mission 6 baseline `generation_benchmark_2026-10-21_m6_post_v1`: EM 0.4500,
  F1 0.5621, answered 109/140, gate 11 (answerable), withheld 20, spurious 2/42,
  unsupported-claim rate 0.1364, citation 0.8636.

## Failure inventory (verified)

18 list-ordinal rows non-exact (11 wrong / 7 withheld); 13 withheld others;
11 gate refusals; 11 reference-format variants (not defects); 8 ambiguous
references (not deterministically fixable); 7 section-title annotation artifacts;
2/42 spurious. Full detail: `ERROR_LEDGER.jsonl`.

## Chosen interventions

1. `generation/lists.py` — deterministic positional/content list reader.
2. `generation/verification.py::_list_entity_alignment` — membership semantics.
3. Evaluation: `generative_model` recorded per row; ledger schema extended.

## Rejected hypotheses (with measurements)

Boundary reader (no consistent rule); withhold digit-free quantity answers
(0 EM, −0.0036 F1, hides the defect); strip `$`/units (gaming); return section
headings (annotation artifact); regenerate claim dataset (fabrication).

## Completed work

- [x] list resolver + service wiring + verifier fix + tokenizer export
- [x] 32 new tests; `tests/unit/generation` 229 passed
- [x] full unit suite 1643 passed / 23 skipped / 0 failed; `compileall` exit 0
- [x] benchmark `m7_post_v1`, repeat `m7_post_v1_r2`, pre-review `m7_post_v2`
      (identical answers; EM 0.5786 / F1 0.6637)
- [x] claim evaluation replay byte-identical to Mission 5
- [x] independent review (7 findings, all fixed and pinned by tests)
- [x] post-review run `m7_reviewed` (answers identical; 36 records differ only
      in warning text) and ledger rebuilt from it
- [x] claim replay repeated after the review (`..._m7_reviewed`, F1 0.8889)
- [x] 5-mark and 15-mark runs recorded in `EXPERIMENT.md`
- [x] 182-row ledger, 38 fields
- [x] `FINAL_REPORT.md`, architecture record, `DOCUMIND_PROJECT_CONTEXT.md`
      §0.8.12, `CONTEXT.md`

## Remaining work

None for this mission. Known limitations are listed in `FINAL_REPORT.md` §6 and
are open across missions, not unfinished work here:

- production PostgreSQL / live-server / browser paths were not exercised;
- `tests/integration` fails on an Alembic `JSONB`-under-SQLite revision owned by
  the database agent (pre-existing, untouched by this mission);
- the claim annotation dataset was not regenerated, so its F1 does not describe
  this mission's answers.
