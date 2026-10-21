# DocuMind — Question Workflow Matrix

## Purpose

Define how DocuMind handles different computational classes of questions. Each question type maps to a specific retrieval strategy, answer strategy, verification strategy, and abstention condition.

This matrix demonstrates that DocuMind does NOT force every question through extractive QA. Different question types require different computational workflows.

---

## 1. Question Taxonomy

| Code | Question Type | Description | Example |
|------|---------------|-------------|---------|
| DS | DIRECT_SPAN | Answer is a contiguous text span in the document | "What is the document title?" |
| SS | SECTION_SPECIFIC | Answer requires a specific section | "What does the methodology section say?" |
| NC | NUMERIC | Answer involves numbers or arithmetic | "What is the total revenue?" |
| TC | TABLE_CELL | Answer is a specific table cell | "What is Q3 revenue?" |
| TR | TABLE_ROW | Answer is a complete table row | "Show all Q3 figures" |
| TM | TABLE_COMPARISON | Answer compares values across table cells | "Which quarter had highest revenue?" |
| LI | LIST_ITEM | Answer is a specific list element | "What are the ingredients?" |
| LO | LIST_ORDER | Answer requires list ordering | "What is step 3?" |
| MC | MULTI_CHUNK | Answer spans multiple chunks | "Summarize the full document" |
| MH | MULTI_HOP | Answer requires reasoning across sources | "How does A relate to B?" |
| CP | COMPARISON | Answer compares two entities | "How does X differ from Y?" |
| AG | AGGREGATION | Answer requires combining data | "What is the average?" |
| LC | LONG_CONTEXT | Answer requires full document understanding | "What is the main argument?" |
| SM | SUMMARY | Answer is a synthesis | "Summarize this document" |
| UA | UNANSWERABLE | Evidence insufficient | "What is the CEO's birthday?" |

---

## 2. Workflow Matrix

| Question Type | Retrieval Strategy | Answer Strategy | Verification Strategy | Abstention Condition |
|---------------|-------------------|-----------------|----------------------|---------------------|
| DS | Dense + Lexical, top-5 | Extractive span extraction | Grounding check: span must appear in evidence | No evidence with matching span |
| SS | Dense + Lexical, top-5, section boost | Extractive span extraction with section filter | Grounding check + section verification | No evidence from target section |
| NC | Dense + Lexical, top-5 | Extractive span extraction + number parsing | Grounding check + number verification | No numbers in evidence |
| TC | Dense + Lexical, top-10, table structure query | Table cell extraction | Table structure verification + grounding | No matching table cell |
| TR | Dense + Lexical, top-10, table structure query | Table row extraction | Table structure verification + grounding | No matching table row |
| TM | Dense + Lexical, top-10, table structure query | Table comparison reasoning | Table structure verification + comparison check | Insufficient table data |
| LI | Dense + Lexical, top-5, list structure query | List item extraction | List structure verification + grounding | No matching list item |
| LO | Dense + Lexical, top-5, list structure query | List ordering extraction | List structure verification + position check | No ordered list found |
| MC | Dense + Lexical, top-20 | Multi-chunk synthesis | Cross-chunk consistency check | Evidence too fragmented |
| MH | Dense + Lexical, top-20, sub-query decomposition | Multi-hop reasoning | Source cross-reference check | Insufficient sources |
| CP | Dense + Lexical, top-10 per entity | Comparison extraction | Comparison grounding check | Insufficient comparison data |
| AG | Dense + Lexical, top-10 | Aggregation extraction + arithmetic | Aggregation verification | Insufficient data for aggregation |
| LC | Dense + Lexical, top-30 | Long-context synthesis | Full-document grounding check | Document too short/irrelevant |
| SM | Dense + Lexical, top-20 | Grounded generation | Citation check + grounding | Insufficient evidence for synthesis |
| UA | Dense + Lexical, top-5 | No answer (abstain) | N/A | Evidence sufficiency check fails |

---

## 3. Detailed Workflow Descriptions

### 3.1 DIRECT_SPAN

**Workflow:**
1. Classify question as DIRECT_SPAN
2. Transform query for dense retrieval
3. Run dense + lexical retrieval
4. Rerank candidates
5. Extract answer span from top evidence
6. Verify grounding (span appears in evidence)
7. Return answer with provenance

**Current implementation:** This is the ONLY workflow currently implemented (via `qa_model.py`). All other question types currently fall through to this workflow.

**Phase 4F evidence:** EM ~7% ceiling. The extractive QA model struggles with non-span questions.

---

### 3.2 TABLE_CELL

**Workflow:**
1. Classify question as TABLE_CELL
2. Detect table references in question
3. Transform query for table-aware retrieval
4. Run dense + lexical retrieval with table boost
5. Rerank candidates
6. Extract table cell matching query
7. Verify table structure (row/column alignment)
8. Return cell value with provenance

**Current implementation:** NOT IMPLEMENTED. Currently falls through to DIRECT_SPAN, which cannot handle table structure.

**Phase 4F evidence:** TABLE_CELL category has 0% EM across all experiments. The extractive QA model cannot extract table cells.

---

### 3.3 NUMERIC

**Workflow:**
1. Classify question as NUMERIC
2. Detect numerical operators in question
3. Transform query for number-aware retrieval
4. Run dense + lexical retrieval
5. Rerank candidates
6. Extract numbers from evidence
7. Apply arithmetic if needed
8. Verify number grounding
9. Return result with provenance

**Current implementation:** NOT IMPLEMENTED. Currently falls through to DIRECT_SPAN.

**Phase 4F evidence:** NUMERIC category has low EM. The extractive QA model extracts numbers but cannot perform arithmetic.

---

### 3.4 SUMMARY

**Workflow:**
1. Classify question as SUMMARY
2. Transform query for broad retrieval
3. Run dense + lexical retrieval (high top-K)
4. Rerank candidates
5. Synthesize answer from multiple evidence pieces
6. Verify grounding (each claim traced to evidence)
7. Return summary with citations

**Current implementation:** NOT IMPLEMENTED. Currently falls through to DIRECT_SPAN, which cannot synthesize.

**Phase 4F evidence:** SUMMARY is not a tested category. The current system has no synthesis capability.

---

### 3.5 UNANSWERABLE

**Workflow:**
1. Classify question as UNANSWERABLE
2. Determine evidence sufficiency
3. If insufficient: abstain with explanation
4. If sufficient: route to appropriate answer strategy

**Current implementation:** Partially implemented via confidence threshold and `insufficient_context` flag. However, the mechanism is unreliable.

**Phase 4F evidence:** The H1 experiment showed that the extractive QA model cannot learn answerability. The CLS/null-score mechanism provides no useful signal. Answerability must be a separate concern.

---

## 4. Current vs Target Mapping

| Question Type | Current Behavior | Target Behavior | Gap |
|---------------|-----------------|-----------------|-----|
| DS | Extractive QA | Extractive QA | None (already works) |
| SS | Extractive QA (wrong section) | Section-aware extractive | Medium |
| NC | Extractive QA (no arithmetic) | Extractive + number parsing | Medium |
| TC | Extractive QA (no table structure) | Table cell extraction | High |
| TR | Extractive QA (no table structure) | Table row extraction | High |
| TM | Extractive QA (no comparison) | Table comparison | High |
| LI | Extractive QA (no list structure) | List item extraction | Medium |
| LO | Extractive QA (no ordering) | List ordering extraction | Medium |
| MC | Extractive QA (single chunk) | Multi-chunk synthesis | High |
| MH | Extractive QA (single source) | Multi-hop reasoning | High |
| CP | Extractive QA (no comparison) | Comparison extraction | Medium |
| AG | Extractive QA (no aggregation) | Aggregation extraction | High |
| LC | Extractive QA (limited context) | Long-context synthesis | High |
| SM | Extractive QA (no synthesis) | Grounded generation | High |
| UA | Confidence threshold | Evidence sufficiency | High |

---

## 5. Implementation Priority

Based on Phase 4F evidence and expected impact:

### High Priority (address core limitations)

1. **UNANSWERABLE** — Evidence sufficiency separation (Stage 6)
2. **TABLE_CELL** — Table structure awareness (Stage 8)
3. **MULTI_CHUNK** — Multi-chunk synthesis (Stage 9)

### Medium Priority (improve coverage)

4. **NUMERIC** — Number parsing (Stage 8)
5. **LIST_ITEM** — List structure awareness (Stage 8)
6. **SECTION_SPECIFIC** — Section awareness (Stage 3)

### Lower Priority (enhance quality)

7. **TABLE_ROW** — Row extraction (Stage 8)
8. **TABLE_COMPARISON** — Comparison reasoning (Stage 8)
9. **LIST_ORDER** — Ordering extraction (Stage 8)
10. **COMPARISON** — Entity comparison (Stage 9)
11. **AGGREGATION** — Data aggregation (Stage 9)
12. **LONG_CONTEXT** — Full-document synthesis (Stage 9)
13. **SUMMARY** — Grounded generation (Stage 9)
14. **MULTI_HOP** — Multi-hop reasoning (Stage 9)

---

## 6. Evidence Grounding

### 6.1 Every Answer Requires Evidence

No answer reaches the user without evidence. The evidence contract requires:

- Source document ID
- Document version ID
- Element ID (section, table, list, etc.)
- Page number (if applicable)
- Retrieval strategy used
- Retrieval score
- Verification status

### 6.2 Evidence Quality Gates

| Gate | Description | Fail Action |
|------|-------------|-------------|
| Sufficiency | Enough evidence to answer | Abstain |
| Relevance | Evidence matches question | Abstain |
| Grounding | Answer is in evidence | Abstain |
| Citation | Citations are accurate | Mark as PARTIAL |
| Consistency | Evidence pieces agree | Mark as PARTIAL |

---

## 7. Abstention Reasons

The system must provide clear abstention reasons:

| Reason | Description | User Message |
|--------|-------------|--------------|
| INSUFFICIENT_EVIDENCE | Not enough relevant evidence | "I couldn't find enough information to answer this question." |
| NO_ANSWERABLE_SPAN | Evidence exists but no answer span | "The documents contain relevant information, but I couldn't extract a specific answer." |
| TABLE_NOT_FOUND | Table question but no matching table | "I couldn't find a table containing the requested information." |
| NUMBERS_NOT_FOUND | Numeric question but no numbers | "The documents don't contain the numerical data needed to answer this question." |
| CONFLICTING_EVIDENCE | Evidence pieces contradict | "The documents contain conflicting information on this topic." |
| MULTIPLE_SOURCES_NEEDED | Question requires multiple sources | "This question requires information from multiple sources that I couldn't combine." |
| MODEL_UNAVAILABLE | QA model not loaded | "The question answering model is currently unavailable." |
| VERIFICATION_FAILED | Answer failed verification | "I found a potential answer but couldn't verify its accuracy." |
