# Pilot evidence scoring and blinded review

This is research preparation, not a claim of independently validated educational
results. Production retrieval and existing evaluation artifacts are unchanged.

From `backend/`:

```powershell
venv/Scripts/python.exe -m evaluation.research_scoring self-check
venv/Scripts/python.exe -m evaluation.research_scoring validate --dataset evaluation/pilot_v1/dataset.json
venv/Scripts/python.exe -m evaluation.research_scoring score --dataset evaluation/pilot_v1/dataset.json --run RUN.json --output NEW_SCORES.json --tokenizer evaluation/assets/gpt-oss-tokenizer --tokenizer-id openai/gpt-oss-20b@6cee5e81ee83917806bbde320786a8fb61efebee
venv/Scripts/python.exe -m evaluation.research_scoring review-export --dataset evaluation/pilot_v1/dataset.json --run ANSWER_RUN.json --output NEW_REVIEW.csv --mapping NEW_PRIVATE_MAP.json
venv/Scripts/python.exe -m evaluation.research_scoring review-summary --ratings REVIEWER_A.csv REVIEWER_B.csv --mapping NEW_PRIVATE_MAP.json --output NEW_HUMAN_SUMMARY.json
```

Every output must be a new path. Share copies of the anonymous review CSV with
two qualified independent graders; keep its private mapping away from graders.
Only reviewer, score and notes are editable. Altered question, answer, rubric,
evidence or marks are rejected (display line-ending changes are tolerated).
No generated answers means no review export; absent or single-grader scores do
not contribute to primary NHRS. Unanswerable grading is reported separately.
Reviewer qualifications and independence need external confirmation.

## Run contract

```json
{"records": [{
  "question_id": "question-id", "system_id": "system-id", "replicate": 0,
  "context_format": "jsonl_evidence",
  "context_text": "{\"source\": 1, \"page\": 1, \"text\": \"Exact source text.\"}",
  "excerpts": [{"document_id": "document-id", "page": 1,
    "start_char": 0, "end_char": 18, "text": "Exact source text.", "context_source": 1}],
  "answer": "Optional actual generated answer"
}]}
```

Offsets are Unicode code points, zero-based and end-exclusive, in the immutable
canonical page text. The illustrative offset above must be replaced with the
actual source interval. `context_text` is the final serialized evidence after
prompt fitting, including labels, graph fields and duplicated text actually
sent. JSONL decoding checks only `text` fields for excerpt presence; metadata
does not count as evidence. Set `context_source` to its numbered source for
unambiguous mapping. Plain serialized text is also accepted with
`context_format: "plain"`. Text-only source mapping must be unique on its
declared page; otherwise explicit offsets are required.

RER uses OR alternatives of ALL-required spans and merges adjacent/overlapping
retrieved intervals; gaps are uncovered. Chunk-ID matches and paraphrases receive
no evidence credit. Repeated context cannot increase covered units. Primary ECT
is absent without a verified exact model-tokenizer counter; byte estimates and
the embedding tokenizer are never substituted. Empty context has RER zero for
answerable questions and undefined ECT. Unanswerable RER/ECT are undefined.
Reports retain dataset/run/scorer hashes, annotation status, exact counter
identity and missing counts. Draft annotation measurements are diagnostic even
if individual review slots have been filled. The reviewed measurement label
requires both the explicit dataset release status `reviewed_frozen_benchmark`
and two distinct approved independent annotation reviewers for every scored
question. Software checks these declarations; it cannot certify the reviewers
or the external release/adjudication process.

## Tokenizer provisioning

Explicit one-time provisioning, separate from all offline scoring:

```powershell
venv/Scripts/python.exe evaluation/assets/gpt-oss-tokenizer/provision.py
```

This downloads only four tokenizer/configuration files from the official
`openai/gpt-oss-20b` repository at revision
`6cee5e81ee83917806bbde320786a8fb61efebee`, under Apache-2.0. No model weights,
API credential or stored Hugging Face token is used. JSON assets are ignored by
Git; the source/checksum manifest and provisioning helper are versioned. Existing
files are checked, never overwritten. Runtime verifies all manifest hashes and
uses `local_files_only=True`, `trust_remote_code=False`, `truncation=False` and
`add_special_tokens=False` on the complete serialized context. The measured ECT
is exact under this frozen official model tokenizer; equivalence with a changing
hosted provider alias remains an explicitly recorded external limitation.

Observed local counter checks: Unicode input, empty context (zero), and an
80,000-character string yielding 40,001 tokens without truncation. These are
token-accounting checks, not evidence of educational answer quality.
