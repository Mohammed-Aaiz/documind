# DocuMind — E0 Diagnostic Protocol (Phase 4F.6-C)

**Nature:** E0 is a **MEASUREMENT STUDY**. It is not a model-training experiment and not an architecture-selection experiment.
**Population:** P3 frozen benchmark — 182 examples / 140 answerable / 42 unanswerable / 6 holdout documents.
**Benchmark hash (must be preserved byte-for-byte):** `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0`
**Companion files:** `E0_SCHEMA.json` (record schema), `E0_READINESS_CHECK.md` (stop/go status).
**Execution:** this phase produces design only — no execution scripts, no runs, no writes outside `backend/architecture/phase4f_6/decision/`.

---

## 0. Language constraints (correction carried forward from 4F.6-B)

E0 **reduces attribution uncertainty and localizes failure stages**. The following claims are forbidden in this protocol, in E0 outputs, and in any report built on them:

| Forbidden phrasing | Required phrasing |
|---|---|
| "E0 discriminates H-A vs H-C" | "E0 reduces attribution uncertainty relevant to those hypotheses" |
| "E0 isolates H-B1" | "E0 localizes answerable-stage failures and separately characterizes unanswerable behavior" |
| "E0 proves representation is the bottleneck" | "E0 measures representation-preservation failures where measurable" |
| any "E0 shows X architecture is correct/better" | causal and architectural conclusions belong to later controlled experiments |

All E0 outputs are **descriptive measurements over one recorded configuration**. No output is a causal effect, an intervention comparison, or an architecture verdict.

---

## 1. Unit of analysis and traceability identifiers

The unit of analysis is **one benchmark example** (`example_id`), traced through nine identifier slots. Every slot is either `OBSERVED` (present in an existing artifact), `DERIVED` (computed deterministically from observed fields — never invented), or `MISSING` (no local artifact; recorded as `NOT_EXECUTABLE`, never substituted).

| # | Slot | Identifier / location | Status |
|---|---|---|---|
| 1 | Benchmark example | `example_id` (e.g., `tc_e7eb93d1`) in `qa_benchmark_v1.jsonl` | OBSERVED |
| 2 | Gold document | `document_id` ∈ {company_history_eta, financial_report_q3, api_docs_lambda, dataset_desc_mu, legal_contract_epsilon, unanswerable_corpus} | OBSERVED (identifier); **standalone document text: MISSING** (see readiness check) |
| 3 | Gold source element | `element_id` := DERIVED `document_id` + `question_kind` + stable hash of category metadata (`table_headers`+`anchor`/`column`/`row_anchor`, or `heading`/`item_index`, or `boundary_sections`, or `attr`) | DERIVED (flagged `derived: true` in schema; never presented as an observed element key) |
| 4 | Relevant source span | `context` field + `answer_start`/`answer_end` (char offsets into `context`) + `context_sha256` (DERIVED) | OBSERVED (gold_span_validation 182/182 valid; token_span_validation 182/182 valid) |
| 5 | Stored chunk(s) | chunk id + offsets under a declared chunker | **MISSING** — no chunk corpus exists for the 6 holdout documents |
| 6 | Retrieved chunk(s) | chunk id + retrieval rank + retrieval config id | **MISSING** — no retrieval stage exists in the recorded pipeline; no traces exist |
| 7 | Model-input context | token span of the gold answer in the actual input sequence; `sequence_length_after_truncation`; question/context token counts; truncation flag | OBSERVED via deterministic reconstruction (tokenizer + declared params, §12); predicted token indices `predicted_start_idx`/`predicted_end_idx` are OBSERVED in `raw_predictions_benchmark.json` |
| 8 | Model prediction | `predicted_answer`, `predicted_start_idx`, `predicted_end_idx`, `start_logit`, `end_logit` | OBSERVED (`raw_predictions_benchmark.json`, 182/182) |
| 9 | Abstention/spurious outcome | `null_score`, `null_margin`, `cls_start_logit`, `cls_end_logit`, `confidence`; threshold-rule outcome | OBSERVED (`raw_predictions_benchmark.json`; rule artifacts in `f2/threshold_experiment/`) |

**Traceability rule:** an example's trace record may only link slots through observed or deterministically derived identifiers. Missing slots (5, 6) are emitted with `status: "NOT_EXECUTABLE_MISSING_ARTIFACT"`. **Missing provenance is never invented** (§13).

---

## 2. Pipeline reality statement (defines where stages can apply)

Verified from the local record (`run_experiment.py`, `run_f2.py`, `run_h1.py`, `run_threshold_experiment.py`):

```text
RECORDED PIPELINE (all P3 results in the local record):
benchmark example ──► tokenizer(question, context, max_length=384,
                      truncation=True, padding="max_length")
                  ──► extractive model ──► start/end logits ──► prediction
        │
        └── context = the benchmark's own gold `context` field.
            THERE IS NO RETRIEVAL STAGE AND NO CHUNK-CONSTRUCTION STAGE
            IN THE RECORDED PIPELINE.
```

Consequences, stated up front so no measurement pretends otherwise:

1. **Stage A (retrieval) is not exercised by the recorded pipeline.** It is `NOT_APPLICABLE_STRUCTURAL` for recorded results — *not* "passed". Measuring it requires a declared retrieval instrumentation over the 6 holdout documents; that requires traces/chunk-corpus artifacts that **do not exist** (readiness check, blocker B-1/B-2).
2. **Corpus-level context construction does not exist for recorded results.** The only transformation between benchmark `context` and model input is tokenization + truncation at 384 tokens, measured at L4 as the context-construction/loss stage.
3. **Stage C (representation) and Stage D (extraction) are executable from existing artifacts** (benchmark metadata + context serialization + reconstructed model input + recorded predictions).

The protocol below defines the **full corpus-path variant** (A–D) for whenever the missing artifacts exist, and the **recorded-pipeline variant** (B–D) that is partially executable today. Both variants share the same levels, rules, and schema; the applicability map is part of every record.

---

## 3. Evidence-presence hierarchy — L0 provenance/integrity gate + the five evidence levels (L1–L5)

Shared normalization for all levels: **NORM-v1** (§4). Every level emits `status ∈ {PASS, FAIL, NOT_APPLICABLE, NOT_EVALUABLE}` plus `rule_id` and the evidence values used.

**Nomenclature (4F.6-C-R correction):** `L0 = provenance/integrity gate` — it gates and quarantines; it is **not one of the original five evidence levels**. The five evidence levels are: **L1** = correct document/source retrieved · **L2** = structural element identified/preserved · **L3** = evidence text present · **L4** = evidence survives into actual model input · **L5** = extraction succeeds.

### L0 — Provenance/integrity gate: gold evidence exists in the source document *(gate — not counted among the five evidence levels)*
- **What it proves:** the benchmark's gold span is backed by a source beyond the benchmark record itself.
- **What it does not prove:** that any pipeline stored, retrieved, or presented it.
- **False-negative risks:** source document not materialized as an artifact (only per-example context slices exist — the current situation for the 6 holdout documents); document text differs by whitespace/encoding between source and benchmark slice.
- **False-positive risks:** validating the benchmark against its own `context` field is near-tautological (the context *is* the evidence by construction) — L0 against the benchmark field alone must be labeled `BENCHMARK_INTERNAL`, never reported as independent source verification.
- **Required artifact:** standalone source document text per `document_id` (or a deterministically reconstructable document artifact whose slices are validated substring-exact against the hash-verified source dataset `training_data_v3_1.jsonl`).
- **Deterministic rule:** `answer_text ⊆ normalize_NORMv1(source_document_text)` AND `context ⊆ normalize_NORMv1(source_document_text)` (substring under NORM-v1 textual rules), byte-level context hash recorded.

### L1 — Correct document/source identity is retrieved
- **What it proves:** the retrieval stage returned the gold document within top-k.
- **What it does not prove:** that the answering region was retrieved (that is L3), or that the model saw anything.
- **False-negative risks:** document aliasing/version IDs; multiple documents sharing the answer; top-k cut before the correct document.
- **False-positive risks:** right document, wrong region returned (L1 passes, L3 fails — the cascade handles it); retrieval of a near-duplicate document counted as identity match without an alias table.
- **Required artifact:** retrieval trace per example: ordered `[chunk_id, document_id, rank]` under a recorded retrieval configuration. **Currently MISSING.**
- **Deterministic rule:** `L1 = PASS ⟺ document_id ∈ {trace[i].document_id : i < top_k}`, `trace` from the declared configuration; `L1 = NOT_APPLICABLE_STRUCTURAL` for recorded-pipeline records.

### L2 — Correct structural element is represented/retrievable
- **What it proves:** the element (section, table, list, boundary) the question targets exists as an identifiable unit in the stored/retrieved representation, with its identity metadata intact.
- **What it does not prove:** that the element contains the answer (that is L3), or that selection from it succeeds (L5).
- **False-negative risks:** element split across chunk boundaries; ingest-time sectionizer/table-detector failure (itself recorded as an L2 fail — a representation-preservation signal, not an annotation error); derived `element_id` hash mismatch due to metadata formatting.
- **False-positive risks:** an element with matching metadata but the wrong instance (duplicate tables with identical headers) — mitigated by requiring co-occurrence of the question's distinguishing anchor (`anchor`/`row_anchor`/`item_index`/heading) within the element region.
- **Required artifact:** stored-chunk/element records for the 6 holdout documents (element id, kind, offsets, metadata). **Currently MISSING** (no chunk corpus exists); a benchmark-metadata-only fallback exists and is labeled `BENCHMARK_METADATA_ONLY` (it shows what metadata the benchmark carries, not what a pipeline stored).
- **Deterministic rule:** locate the region R in the stored representation where `element_kind` and the anchor predicate both hold (exact string equality on metadata values under NORM-v1 textual rules); PASS iff exactly one such R exists and R ⊆ stored text.

### L3 — Gold evidence is present in stored/retrieved text (normalization-aware)
- **What it proves:** answer-bearing text exists in the text layer being measured (stored corpus, retrieved set, or — recorded-pipeline variant — the benchmark `context` as the supplied text layer), under declared matching class.
- **What it does not prove:** that the model's forward pass saw it (L4), that it was unambiguously locatable, or that the model could interpret structure (§6/C-stage).
- **False-negative risks:** paraphrased gold (gold not verbatim — recorded as `gold_not_verbatim`, never silently counted as absence); offset errors (guarded by the 182/182 gold-span validation); multi-chunk gold split across fragments (handled by the split-span rule, §4.4); numeric formats outside the NORM-v1 numeric table (logged for manual review).
- **False-positive risks:** coincidental occurrence of short/numeric/generic strings elsewhere in the text — mitigated by occurrence counting (`match_occurrences > 1` → `ambiguous: true`, reported as a separate rate, not silently passed) and by structural co-presence requirements for structural answers (§4.3).
- **Required artifact:** the text layer itself + gold offsets. **Available** for the benchmark-context variant; **MISSING** for stored/retrieved variants (blockers B-1/B-2).
- **Deterministic rule:** three separately recorded booleans — `textual_match`, `numeric_match`, `structural_match` (whichever classes apply to the gold, §4) — with `L3 = PASS` iff at least one applicable class matches **at a recorded location** (start/end offsets of the match stored; presence without a located match does not count).

### L4 — Gold evidence survives context construction, truncation, and tokenization into actual model input
- **What it proves:** the gold token span lies inside the actual input sequence the model consumed (within the 384-token, question+context pair, post-truncation).
- **What it does not prove:** fair selection conditions (position, distractors, competing matches) — only presence.
- **False-negative risks:** tokenizer digit-splitting (`91. 4`) breaking char→token mapping — L4 maps the **char span** through the fast-tokenizer offset mapping, then applies NORM-v1 digit reassembly to the tokenized substring, so digit spacing cannot create a false L4 fail; offset-mapping bugs (guarded by token_span_validation 182/182); `truncation=True` longest-first strategy cutting the context tail.
- **False-positive risks:** token-span alignment landing on a coincidental match when gold is a 1-token numeric — mitigated by requiring char-span↔token-span round-trip consistency under NORM-v1.
- **Required artifact:** tokenizer + input-construction params (available: `backend/models/documind-qa/tokenizer.json`; `max_length=384, truncation=True, padding="max_length"` in every harness) and the `context` field. **Available by deterministic reconstruction**; the exact tokenizer artifact used by the recorded run must be pinned by hash at execution (readiness item R-6). Reconstruction is labeled `RECONSTRUCTED`, never `OBSERVED`.
- **Deterministic rule:** encode `(question, context)` with the pinned tokenizer and recorded params; map `[answer_start, answer_end)` char span → `[gold_token_start, gold_token_end]` via offset mapping; `L4 = PASS ⟺` the span maps successfully AND `gold_token_end < sequence_length_after_truncation` (non-special tokens); `span_truncated` recorded when the context was cut before the gold end.

### L5 — Extractive model successfully selects the evidence
- **What it proves:** extraction outcome conditional on everything measured above — the only clean extraction-quality measurement available.
- **What it does not prove:** behavior where L4 is false; generalization to another model/checkpoint; that any change would help.
- **False-negative risks:** scoring strictness — mitigated by triple reporting per example: `em` (protocol normalization: strip/lower/whitespace-collapse), `f1` (token-level), and `scoring_normalizable_match` (NORM-v1 match between prediction and gold). The third value is **reported as a reclassification rate only** — evaluation logic is not changed by E0.
- **False-positive risks:** exact matches by coincidence (negligible for long answers; covered by occurrence ambiguity for 1-token numerics).
- **Required artifact:** per-example prediction + gold. **Available** (`raw_predictions_benchmark.json`, 182/182: predicted answer, token indices, logits, null scores, confidence).
- **Deterministic rule:** compute `em`, `f1`, `scoring_normalizable_match` against gold using the protocol's scoring definitions; `L5 = PASS ⟺ em = 1`; `L5 = NOT_EVALUABLE` when L4 ≠ PASS (attribution precedence, §5).

---

## 4. Normalization rules (NORM-v1) — defined before measuring

NORM-v1 is versioned; the version is recorded in every diagnostic record. Rules produce **recorded comparisons, not destructive rewrites**: the raw strings, the rule id(s) applied, and each class result are all stored. Three matching classes are kept separate: **textual presence**, **numeric-equivalent presence**, **structural presence**.

### 4.1 Textual presence (class: `textual`)
1. Unicode **NFKC** normalize.
2. **Casefold** (not simple lower — handles non-ASCII case).
3. Whitespace collapse: all `\s+` (incl. NBSP after NFKC) → single space; trim ends.
4. Punctuation: unify typographic quotes/dashes (`‘’“”–—` → `' " -`); strip trailing sentence punctuation `. , ; : ! ?` for comparison only; keep interior punctuation (`$`, `%`, `/`, `-` inside tokens such as `CC BY 4.0`).
5. Leading article strip (`a`, `an`, `the`) — SQuAD-style, comparison only.
6. **Digit-tokenized text reassembly:** `(\d+)\s+([.,])\s+(\d+)` → `\1\2\3` (fixes tokenizer-artifact forms `20. 3`, `91. 4`, `7, 500`). Applied only to digit-digit patterns — never to arbitrary spaces.
7. Comparison: equality of processed strings for `em`-class; token-set intersection for `f1`-class (protocol scoring definitions unchanged).

### 4.2 Numeric-equivalent presence (class: `numeric`)
Applicable when gold parses as a number (helped by benchmark `numeric_format` ∈ {CURRENCY, PERCENT, …} and NUMERIC/DIRECT_SPAN kinds).
1. Strip currency symbols `$ € £` (record which was stripped).
2. Strip thousands separators: comma **and** NBSP/space grouping, only when the comma/space is a group separator (digits after it run in 3-groups, e.g. `1,247`), never when it would leave a leading/trailing comma.
3. Decimal handling with **declared locale `en-US`**: `.` is decimal separator; `1,5` is **not** rewritten to `1.5` (ambiguity → `manual_review: true`).
4. Trailing-zero equivalence: `185.0 ≡ 185`, `1,247.00 ≡ 1247` after separator handling.
5. Percent: `%` ≡ `percent` ≡ `pct` (casefolded, whitespace-collapsed). **`%` is NOT equivalent to `percentage points`** — materially different, never merged.
6. Standard magnitude suffixes only: `k/K`=×10³, `M/mn/million`=×10⁶, `B/bn/billion`=×10⁹ — expanded for comparison **only when the expansion matches the other side exactly**; suffix-only matches are flagged `numeric_suffix_expansion: true` (reported, reviewable).
7. **Forbidden:** unit conversions across incompatible scales (MB↔MiB, °C↔°F, %↔pp, currency conversion), rounding of any kind, dropping significant digits. Two numbers that differ after rules 1–6 are **different answers** — numeric match fails, no silent repair.
8. `numeric_match` is computed by parsing both sides under rules 1–6 and comparing exact rational values (decimal strings → integer/fraction compare, no floats).

### 4.3 Structural presence (class: `structural`)
Applicable by category; each check records `dialect` and the per-subcheck booleans:
- **Table cell (TABLE_CELL):** the serialized context must contain a row where (row anchor from `metadata.anchor` co-occurs with `metadata.column` header semantics) — operationally: header row containing `column` (NORM-v1 textual) AND a row containing `anchor` AND the gold value **in that same row**. Pipe dialect (` | `) and multi-row `\n` dialects both handled; dialect recorded. `structural_match = header_row_found ∧ anchor_row_found ∧ value_in_anchor_row`.
- **Table row (TABLE_ROW):** gold is the pipe-joined row itself — `structural_match` = the gold row string present under textual rules AND `metadata.row_anchor` present in it; header row containing row anchor recorded for interpretation.
- **List item (LIST_ITEM):** locate `metadata.heading`; enumerate non-empty lines below it (list body); `item_index` (0-based as recorded) selects the item slot; `structural_match` = body contains ≥ `item_index`+1 items ∧ gold equals (NORM-v1 textual) the item at `item_index` ∧ boundaries intact (no interleaved non-list content mid-body).
- **Section (SECTION_SPECIFIC):** heading string present; gold either equals the heading or lies within the contiguous body from heading to next heading/EOF; `section_hierarchy_intact` recorded (heading level markers `#`/indentation if present).
- **Multi-chunk (MULTI_CHUNK):** every string in `metadata.boundary_sections` present in the text layer; gold presence checked with the **split-span rule** (§4.4).
- **Long context (LONG_CONTEXT):** no structural predicate — presence reduces to textual/numeric classes at full context length (L4 truncation is the operative risk).
- **Numeric (NUMERIC):** structural component = `numeric_format` respected (§4.2) + `metadata.attr` lexical cue present near the match (within the same sentence, recorded as `attr_cue_nearby`, informational only).
- **Direct span (DIRECT_SPAN):** textual class only; `doc_type`/`attr_type` recorded for reporting.

### 4.4 Special-form rules
- **Multi-chunk spans:** the gold may be split across two fragments; `L3` passes when **both fragments** are present in the text layer (contiguity not required) with `span_split: true` recorded; at L4 both fragments must map into the post-truncation sequence.
- **Ambiguity:** `match_occurrences > 1` under the applicable class → `ambiguous: true`; ambiguous matches are reported as a separate rate and never silently counted as clean passes or clean failures.
- **Manual review queue:** any example where match succeeds *only* via numeric suffix expansion (4.2.6), or fails all three classes, or has decimal-comma ambiguity — flagged `manual_review: true` with the rule ids; counts reported; reviewers may not edit the benchmark.

---

## 5. Four-stage failure decomposition and precedence

Stages (definitions as specified):
- **A — RETRIEVAL FAILURE:** correct source exists but supporting evidence is not retrieved.
- **B — CONTEXT-CONSTRUCTION FAILURE:** evidence exists in the source/chunk corpus but is lost or omitted before the model input.
- **C — REPRESENTATION FAILURE:** evidence is present but structure needed to interpret it is lost or inadequately represented (table cell coordinates, row/column identity, list boundaries/order, section hierarchy).
- **D — EXTRACTION FAILURE:** evidence is demonstrably present in actual model input, but the extractive model fails to select the required answer.

**Deterministic precedence (evaluated in order; first failure = `primary_stage`; all later stages then marked `NOT_EVALUATED` for that example):**

```text
S0  L0 FAIL (independent source verification fails)      → QUARANTINE_BENCHMARK_INTEGRITY
      (excluded from stage rates; reported separately;
       never folded into any stage bucket)
S1  applicable retrieval stage executed and L1 FAIL       → A
      [includes right-document/wrong-region: L1 PASS ∧ L3 FAIL in retrieved set → A]
      [recorded-pipeline variant: S1 is skipped — stage A is
       NOT_APPLICABLE_STRUCTURAL, declared per record]
S2  corpus text layer has evidence (corpus-level L3 PASS) ∧
    model-input L4 FAIL                                  → B
      (recorded-pipeline variant: corpus layer = benchmark
       context, so this is tokenization/truncation loss)
S3  L4 PASS ∧ category has a structural predicate ∧
    representation predicate (§4.3) FAIL                 → C
S4  L4 PASS ∧ (no structural predicate ∨ predicate PASS) ∧
    L5 FAIL                                              → D
S5  L4 PASS ∧ L5 PASS                                    → SUCCESS
```

Rules that make the assignment non-contradictory:
1. **Exactly one `primary_stage` per example** — the first failing gate in S0–S5.
2. Downstream stages of the primary failure are `NOT_EVALUATED`, never "passed" or "failed" — this prevents dual attribution (an example is never both "retrieval failure" and "extraction failure").
3. Raw per-stage flags (`flag_A`…`flag_D`) are still recorded wherever a stage was actually evaluated, for the informational co-occurrence matrix — but flags after a `NOT_EVALUATED` gate remain unset.
4. **C before D only when the selection requires the missing structure** (structural predicate exists and fails). If the structural predicate passes, or the category has none, a wrong prediction is D. Structure-presence does not excuse extraction (D remains measurable), and structure absence never gets recorded as an extraction failure (C takes the example).
5. Every record carries `applicability map` (which of A/B are structurally applicable) so the recorded-pipeline variant can never report "retrieval passed".

---

## 6. Answerable vs unanswerable handling (orthogonal analyses)

### 6.1 Answerable (140)
Run L0–L5 and the stage decomposition of §5. Denominators: 140 overall, per-category `n` (§9), per-level pass subsets for conditional metrics (§8).

### 6.2 Unanswerable (42)
- **No gold evidence span exists → L3, L4, L5 and the stage matrix are `NOT_APPLICABLE` for these records.** No span is invented; no stage bucket is ever assigned.
- `analysis_track: "answerability"` — a separate track with its own record branch and its own denominators (42 overall, per-reason/per-subcategory `n` from benchmark `unanswerable_reason` + `metadata.subcategory`).
- Measured instead (all from existing artifacts):
  1. **Outcome:** `abstain` vs `spurious` under the pre-registered threshold rule (rule id + threshold recorded; artifacts in `f2/threshold_experiment/`).
  2. **Score information as recorded:** `null_score`, `null_margin`, `cls_start_logit`, `cls_end_logit`, `confidence`, `best_answer_score` distributions per outcome (from `raw_predictions_benchmark.json`).
  3. **Retrieved-context plausibility:** the recorded pipeline has no retrieval (§2), so the available quantity is a labeled **PROXY**: plausibility of the *supplied* context — (a) does the predicted answer string occur in the supplied context under NORM-v1 (with occurrence count/ambiguity), (b) lexical overlap between question terms and context. Field name `context_plausibility_proxy`, always labeled; a true retrieved-context plausibility measure requires the missing traces (readiness blocker B-1).
  4. Breakdown by `unanswerable_reason` and `subcategory`.
- **Orthogonality rule:** answerability results and stage results are reported in separate tables with separate denominators; no cell, total, or rate mixes the two tracks; the 42 unanswerable examples appear only in the answerability track (except S0 quarantine, which applies to integrity failures regardless of track and is reported on its own denominator).

---

## 7. Representation diagnostics per structural category (P3)

For each category present in P3: what must be present for "representation survived", and what is required to determine it. **Category failure ≠ representation failure** — the diagnostic reports the predicate result; attribution to stage C additionally requires L4 PASS and a failed predicate (§5 S3).

| Category (n) | Representation-survival predicate | Required metadata/provenance | Source |
|---|---|---|---|
| TABLE_CELL (24) | header row + anchor row + value co-location (§4.3) | `table_headers`, `anchor`, `column` | OBSERVED in benchmark metadata |
| TABLE_ROW (16) | full row tuple + row anchor intact | `table_headers`, `row_anchor` | OBSERVED |
| LIST_ITEM (20) | list boundaries under `heading` intact; item at `item_index`; order preserved | `heading`, `item_index`, `list_length` | OBSERVED |
| SECTION_SPECIFIC (16) | heading present; body contiguous to next heading; hierarchy markers intact if present | section heading (in `context`; `metadata` heading when present) | OBSERVED (context-level); hierarchy beyond context: needs source doc (MISSING) |
| NUMERIC (20) | numeric format preserved under NORM-v1; `attr` cue present (informational) | `attr`, `numeric_format` | OBSERVED |
| DIRECT_SPAN (24) | (no structural predicate — textual presence) | `doc_type`, `attr_type` | OBSERVED |
| MULTI_CHUNK (10) | both `boundary_sections` present; split-span fragments intact | `boundary_sections` | OBSERVED |
| LONG_CONTEXT (10) | (no structural predicate — full-length presence; L4 truncation is the operative check) | none beyond context | OBSERVED (context-level) |

Note: predicates evaluate **what the recorded text layer carries**. Whether a *stored chunk representation* (blocker B-2) preserves these is `NOT_EXECUTABLE_MISSING_ARTIFACT` and must not be inferred from context-level results.

---

## 8. Attribution outputs

### 8.1 Aggregate metrics — every metric carries its denominator

| Metric | Numerator | Denominator | Status today |
|---|---|---|---|
| document_retrieval_recall | answerable ex. with gold document in top-k | **140** | `NOT_EXECUTABLE_MISSING_ARTIFACT` (recorded value: `NOT_APPLICABLE_STRUCTURAL` — never reported as 1.0) |
| evidence_retrieval_recall | answerable ex. with evidence-bearing chunk in top-k | **140** | `NOT_EXECUTABLE_MISSING_ARTIFACT` |
| context_presence_rate | answerable ex. with L3 PASS in the supplied text layer | **140** | executable (benchmark-context variant) |
| representation_preservation_rate (per category) | ex. with representation predicate PASS | **category n** (e.g., TABLE_CELL **24**) | executable at context level; `NOT_EXECUTABLE` at stored-chunk level |
| model_input_evidence_presence_rate | answerable ex. with L4 PASS | **140** | executable via `RECONSTRUCTED` inputs |
| conditional_extraction_EM / F1 | EM/F1 over the L4-PASS subset | **|L4 PASS|** (stated as `x / y` every time; the y/140 view reported alongside) | executable |
| scoring_normalization_reclassification_rate | ex. where `em = 0` but `scoring_normalizable_match = 1` | **140** | executable |
| primary-stage distribution | counts per primary_stage (A, B, C, D, SUCCESS, QUARANTINE, NOT_APPLICABLE per variant) | **140** (answerable track) | executable for C, D, SUCCESS, QUARANTINE |
| unanswerable outcome rates | abstain count; spurious count | **42** (answerability track) | executable |
| context_plausibility_proxy rate | unans. ex. whose predicted answer occurs in supplied context (NORM-v1) | **42** | executable, labeled PROXY |
| ambiguity rate; manual_review rate | counts per §4.4 | stated per applicable subset (e.g., 1-token numerics) | executable |

### 8.2 Failure-count matrix (answerable track, denominator 140 in every cell's row)

Two views, both published:

1. **Precedence-assigned primary counts** (mutually exclusive; rows sum with SUCCESS/QUARANTINE to 140):

| primary_stage | A | B | C | D | SUCCESS | QUARANTINE | total |
|---|---|---|---|---|---|---|---|
| count | (A: `NOT_EXECUTABLE` recorded-pipeline) | count | count | count | count | count | **140** |

2. **Raw flag co-occurrence matrix** (informational; only stages actually evaluated carry flags; cells never inflated by NOT_EVALUATED gates):

| flag ↓ / → | A | B | C | D |
|---|---|---|---|---|
| A | n_AA | n_AB | n_AC | n_AD |
| B | — | n_BB | n_BC | n_BD |
| C | — | — | n_CC | n_CD |
| D | — | — | — | n_DD |

Every matrix cell ships with the evaluated-subset denominator it was computed over.

---

## 9. Conditional metrics (descriptive only)

| Metric | Definition | Denominator | Non-causal statement (mandatory in every report) |
|---|---|---|---|
| P(extraction success \| evidence in model input) | EM over L4-PASS examples | \|L4 PASS\| (of 140) | "Conditional frequency over one recorded configuration; **not a causal effect** — no variable was intervened on." |
| P(model-input evidence \| present in supplied/retrieved text) | \|L4 PASS ∧ L3 PASS\| / \|L3 PASS\| | \|L3 PASS\| | Same mandatory statement. (Retrieved-text variant: blocked.) |
| P(retrieved evidence \| correct document) | \|L1 PASS ∧ L3-in-retrieval PASS\| / \|L1 PASS\| | \|L1 PASS\| | `NOT_EXECUTABLE_MISSING_ARTIFACT` — no traces. |

Prohibited interpretations: no "improvement if…", no "gain", no counterfactual phrasing, no cross-configuration claims. Conditionals are computed within P3 only, never against P1/P2 figures.

---

## 10. Category-level diagnostics (per category, P3 answerable; no premature collapsing)

Reported as one row per category with fixed columns:

| Category | N | evidence present in source (L0) | correct document retrieved (L1) | structural element preserved (L2/Lsr) | evidence in retrieved context (L3) | evidence in model input (L4) | extraction EM (L5) | extraction F1 (L5) |
|---|---|---|---|---|---|---|---|---|
| TABLE_CELL | 24 | value + `NOT_EXECUTABLE` split | `NOT_APPLICABLE_STRUCTURAL` / blocked | predicate rate | rate | rate | x/24 + conditional x/\|L4 PASS in cat\| | value |
| TABLE_ROW | 16 | … | … | … | … | … | … | … |
| LIST_ITEM | 20 | | | | | | | |
| SECTION_SPECIFIC | 16 | | | | | | | |
| NUMERIC | 20 | | | | | | | |
| DIRECT_SPAN | 24 | | | | | | | |
| MULTI_CHUNK | 10 | | | | | | | |
| LONG_CONTEXT | 10 | | | | | | | |
| **answerable total** | **140** | | | | | | | |

Rules: every rate prints `numerator / denominator`; `NOT_EXECUTABLE` cells stay empty-flagged (never 0% or 100%); categories are never merged (no "structured" super-category in outputs); DATE/ENTITY/TABLE_COMPARISON/LIST_ORDER/SUMMARY/MULTI_HOP are reported as **absent from P3 — no row, no rate**.

---

## 11. What E0 CAN and CANNOT conclude

**CAN (as measurement):**
- identify measurable retrieval misses *(once traces exist; otherwise report NOT_EXECUTABLE)*
- identify measurable context-loss cases (tokenization/truncation loss into model input)
- identify measurable representation-preservation failures (context-level predicates; stored-chunk level once artifacts exist)
- identify extraction failures conditional on evidence being present (L4 ∧ L5)
- characterize current answerable/unanswerable behavior (outcomes, score distributions, proxy plausibility)

**CANNOT (forbidden to state from E0 outputs):**
- prove a stronger model is better
- prove training-data composition is the cause
- prove a separate answerability module is necessary
- prove structured QA is the correct architecture
- prove grounded generation is better
- prove hybrid routing is better
- establish causal improvement from any intervention

E0 reduces attribution uncertainty; causal and architectural conclusions remain for later controlled experiments under the controls in `EXPERIMENT_CONTROL_MATRIX.md`.

---

## 12. Required diagnostic artifact and reproducibility controls

**Artifact:** `backend/architecture/phase4f_6/decision/diagnostics/e0_trace_v1.jsonl` — one record per benchmark `example_id` (182 records; 42 on the answerability track), schema in `E0_SCHEMA.json`. Keyed to benchmark example IDs; **the frozen benchmark is never edited**; no execution script is created in this phase.

**Reproducibility block (recorded in every diagnostic run header):**

| Control | Value (from local artifacts) |
|---|---|
| benchmark hash | `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` (verified unchanged at design time) |
| source dataset hash | `a517530354fc9bcaeef6f1aa16c3fb9ce92f1967668386bc66781e6e6bbf2e97` — `backend/phase4f/dataset/training_data_v3_1.jsonl`, **recomputed and matches** `benchmark_manifest.json.source_dataset_hash` |
| production model identifier/hashes | directory-scope `df592aa8d0ee1a235489bd3eead44d4cf0861221339226311960697c1c1512ac`; file-scope `model.safetensors` `cb9f1dde94fca0e1f82c440bdc184ff54ba02efb6ea432e37a8c6ff8a8f69deb` |
| checkpoint under measurement (L5 source) | F2/G pipeline artifacts `phase4f_5f/f2/…` (manifest + `raw_predictions_benchmark.json`); exact checkpoint/tokenizer pair pinned by hash at execution |
| retrieval configuration | production defaults recorded from code: `top_k = 5` (`chat/rag.py`, `embeddings/routes.py` `LIMIT :top_k`, evaluation harness `TOP_K = 5`); **not exercised by the recorded P3 pipeline** |
| chunking configuration | `chunker_version = "legacy"` (1000-char chunk / 200-char overlap per `config.py`; `structure-v2` candidate in `documents/chunking.py`); **not exercised for the 6 holdout documents** |
| model-input configuration | `max_length = 384`, `truncation = True`, `padding = "max_length"` (all harnesses); `n_best = 20`, `max_answer_length = 100` (`inference_config.json`) vs `MAX_ANSWER_LENGTH = 50` (`run_threshold_experiment.py`) — **both recorded; the recorded run's value pinned at execution**; DistilBERT config `vocab_size 30522`, `transformers_version 5.13.1` |
| top-k | 5 (production default, above) |
| normalization version | `NORM-v1` (§4) |
| diagnostic schema version | `e0-diagnostic-v1` |
| threshold rule id | `null_score >= 1.5705` (`benchmark_result.json.decision_rule`) for G-outcome reconstruction; any other rule pre-registered by id |
| timestamp | recorded at execution start (UTC ISO-8601) |
| software/environment identifiers | Python, torch, transformers versions + device recorded at execution (values not yet known — recorded then, not guessed now) |
| seed | 42 (harness `SEED`) |

---

## 13. Stop/go criteria and status pointer

E0 execution is **NOT READY** if any of: provenance cannot be resolved reliably; benchmark examples cannot be mapped to source artifacts; retrieval traces are missing; context construction cannot be reconstructed; model-input evidence cannot be inspected; normalization rules remain ambiguous. Missing provenance is never substituted with assumptions.

The evidence-by-evidence evaluation of these criteria, the precise missing-artifact list, and the resulting status live in **`E0_READINESS_CHECK.md`**.

---

*Phase 4F.6-C design artifact. Measurement-study protocol only. No execution scripts. No training. No benchmark or dataset change. No production or model change. No historical artifact modified. No network/GitHub access. No commit. No push.*
