# DocuMind — Architecture Migration Gate (Phase 4F.6-B)

## 1. Purpose

Defines the explicit criteria that must be satisfied before DocuMind moves from research into implementation of the target architecture. This gate is a research decision artifact: **no implementation is authorized by this document.**

---

## 2. The Ten Gate Criteria

Each criterion must be demonstrable with evidence produced under the controls in `EXPERIMENT_CONTROL_MATRIX.md`, on the frozen P3 benchmark (182 / 140 / 42, hash `1166bf4f...50a41d0`) unless a separate diagnostic population is explicitly declared.

| # | Criterion | Pass condition | Evidence required | Current status |
|---|---|---|---|---|
| 1 | Direct factual QA remains supported | DIRECT_SPAN and SECTION_SPECIFIC categories produce answers through the default extractive path with no regression vs the C1 (F2) corrected baseline | Per-category P3 results tagged P3, compared only to P3 controls | **NOT MET** — per-category P3 attribution not yet measured (E0 pending) |
| 2 | Structured questions have an explicit representation | TABLE_CELL, TABLE_ROW, LIST_ITEM, NUMERIC questions map to an explicit representation (element types exist) and an explicit workflow in the Question Workflow Matrix, not to a default span fall-through | Structure extraction output + workflow mapping test through the seam | **NOT MET** — flat chunk model in production (CURRENT_ARCHITECTURE §5.4) |
| 3 | Unanswerable questions can produce honest abstention | On P3: unanswerable abstention > 50%, false abstention < 20% (ADR Gate 2), with a **pre-registered, stable threshold** (threshold perturbation must not reproduce G's ±0.1 → 25-point shift — measured on P3-validation 85 answerable + 8 unanswerable, `stability_analysis.json`: `max_abstention_shift: 25.0`, `stable: false`; tag the stability population whenever cited) | E2 results tagged P3, threshold stability report | **NOT MET** — F2 0%, G unstable, H1 collapsed (0% EM) |
| 4 | Multi-step reasoning is bounded | Any multi-chunk/long-context workflow has an explicit bound (max evidence pieces, max hops) and an abstention condition when the bound is exceeded | Workflow specification + test through the seam | **NOT MET** — no synthesis workflow exists |
| 5 | Answers remain evidence-grounded | Every answer's content is traceable to retrieved evidence; grounding check runs on 100% of answers | Grounding check results per answer | **NOT MET** — no verification exists |
| 6 | Provenance is preserved | Every answer carries the full chain: Answer → Evidence (retrieval info) → Chunk (offsets) → Element → DocumentVersion → Document | Provenance chain exercised in a test through the seam | **NOT MET** — no provenance tracking (DOMAIN_MODEL §3.2 is design-only) |
| 7 | Verification occurs before final answer acceptance | The verification gate runs before any answer reaches the user and can return VERIFIED / PARTIAL / ABSTAIN | Pipeline test showing acceptance blocked without verification | **NOT MET** — verification module is a stub |
| 8 | Existing production behavior can be preserved during migration | Router-default / new-module steps produce output identical to control behavior (behavioral equivalence on P3 vs C1, and vs C0 once C0-P3 is measured) | Equivalence test: baseline outputs reproduced bit-for-bit or metric-for-metric (note: A0·P3 **aggregate** results were incorporated in 4F.6-C-R — EM 2.1 / F1 12.0, abstention 64.3%, false abstention 55.7%, spurious 15, `phase4f_5d/analysis/` — but **per-example C0·P3 outputs do not exist and run-level provenance is unrecorded**: bit-for-bit equivalence still requires a declared run capturing per-example outputs with hashes re-verified; C1 remains the interim P3 control) | **NOT MET** — no migration steps executed yet |
| 9 | Each new module has a clear seam | Every new module (retrieval, answerability, answer engine routes, verification, structure extraction) exposes exactly one documented interface as defined in MODULE_SEAMS §4, with allowed/forbidden dependencies enforced | Interface contracts present and dependency rules checked | **PARTIALLY MET** — seams are designed in 4F.6-A; no code exists |
| 10 | Tests can exercise the system through those seams | Each seam has tests that drive it without touching internals (unit + integration per MODULE_SEAMS §8.2 target table) | Test suite passing through the seam interfaces | **NOT MET** — seam tests cannot exist before the seams do |

**Gate rule: implementation may begin only when criteria 1–10 are all demonstrated, or when a criterion is explicitly waived in writing with its risk recorded in the ADR.**

---

## 3. Relationship to Existing ADR Decision Gates

The ten criteria above are the architecture-level gate. They compose with the existing operational gates in `ARCHITECTURE_DECISION_RECORD.md` §17:

| ADR gate | Criteria | Threshold | Blocks |
|---|---|---|---|
| Gate 1 — Retrieval quality | Recall@10 > 70% answerable, > 50% unanswerable | Unmeasured (E0 pending) | Answer-engine work (E1/E3) |
| Gate 2 — Answerability separation | Classifier accuracy > 80%, abstention > 50%, false abstention < 20% | Not met (F2 0%, G unstable, H1 collapsed) | Verification work |
| Gate 3 — Structure extraction | Table > 90%, list > 90%, section > 95% detection recall | Unmeasured | Table/list answer engines (E3) |
| Gate 4 — Production readiness | P3 EM > 10%, abstention > 60%, false abstention < 15%, verification pass > 90%, latency < 2s | Not met (F2 EM 2.9%) | Deployment |

No gate may be passed by inference from another gate's result or from a different evaluation population.

---

## 4. Migration Principle

The future architecture is introduced **incrementally**, one route at a time, each route only after it has its own evidence and tests.

### Step 1 — Introduce Question Understanding in front of the existing path (behavior unchanged)

```text
Current RAG
    │
    ▼
Question Understanding
    │
    ▼
Existing QA path
```

At this step the system must be behaviorally equivalent to the control (gate criterion 8). Classification happens, but everything still routes to the existing extractive QA.

### Step 2 — Enable routes one at a time, each with evidence and tests

```text
Question Understanding
    │
    ├── Direct span ───────► Existing extractive QA      (default; always on)
    ├── Table ─────────────► Structured table handler    (only after Gate 3 + E3 evidence)
    ├── Numeric ───────────► Numeric reasoning           (only after E3 evidence)
    ├── List ──────────────► List handler                (only after E3 evidence)
    ├── Multi-chunk ───────► bounded evidence workflow   (only after bound is specified + tested)
    └── Complex synthesis ─► grounded synthesis          (only after E4 evaluation design passes)
```

### Step 3 — Answerability and verification apply to every route

```text
Any route output
    │
    ▼
Answerability gate (independent; E2 evidence)
    │
    ▼
Verification gate (grounding + provenance + citation)
    │
    ├── VERIFIED ──► Final answer (with provenance chain)
    ├── PARTIAL ───► Final answer flagged / degraded
    └── ABSTAIN ───► Honest abstention with reason
```

### Route introduction checklist (all required before a route is enabled)

1. The route addresses a failure class confirmed by **E0 attribution** (not assumed).
2. The route has its own experiment evidence under the frozen benchmark controls.
3. The route passes its applicable ADR gate (1/2/3 as relevant).
4. Seam tests exist for the route interface (criterion 10).
5. Default-path regression: all other categories show no degradation vs C1 on P3.
6. Provenance chain works end-to-end for the route's answers (criteria 5–6).
7. Rollback: disabling the route restores baseline behavior exactly (criterion 8).

---

## 5. Current Gate Status

```text
STATUS: ARCHITECTURE_MIGRATION_GATE = NOT OPEN

Criteria met:      0 of 10 fully met (criterion 9 partially designed, no code)
Blocking evidence: E0 not run; Gate 1 unmeasured; Gate 2 unmet; Gate 3 unmeasured;
                   no seams implemented; no verification; no provenance
Authorized now:    research decision artifacts only (this phase)
Not authorized:    implementation, training, benchmark change, production change
```

---

## 6. Scope Constraints Carried Into Implementation

When the gate eventually opens, implementation inherits these constraints from the 4F.6 decision set:

- Modular monolith; no microservices, no autonomous agents.
- Every answer carries provenance; every answer passes verification.
- Answerability is decided by the independent gate, not implicitly by the extractive QA model (ADR DECIDED on H1/F2/G evidence — a design decision on indirect evidence: the underlying claim H-B2, that a *separately implemented* module is required, remains UNVERIFIED until E2 supplies direct evidence; H-B1, that answerability is a distinct unresolved problem, is SUPPORTED).
- Media verification remains a separate pipeline (currently a stub; unavailable until genuinely implemented).
- The frozen benchmark and production model checksum remain unchanged; new capability tests run through seams, not around them.

---

*Phase 4F.6-B decision artifact. Planning only. No production code changed. No model changed. No benchmark changed. No commit. No push.*
