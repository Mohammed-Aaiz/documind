# Student RAG evaluation commands

Run from `backend/` with the existing Python environment. These commands never
create, reset, reindex or delete database rows. Report files use exclusive create
and must have a new name for every run.

## Isolated embedding comparison

```
venv/Scripts/python.exe -m evaluation.production_rag embeddings --model minilm=sentence-transformers/all-MiniLM-L6-v2 --model bge=embeddings/assets/bge-small-en-v1.5 --output evaluation/reports/embedding_comparison_NEW.json
```

Models load local files/cache only, with CPU and normalized dense vectors. Missing
assets are reported `unavailable`; they are never downloaded. No model is promoted
to production, and no vectors from different models enter a common index. Reports
include dimensions, encoder length, available model revision, dataset/runner hashes,
retrieval metrics and cold model-load/corpus-encoding costs separately from query
latency. The included six-query synthetic teaching fixture is a smoke check, not
evidence of general academic quality or a meaningful model-selection benchmark.

For the BGE model's documented query instruction, additionally pass
`--query-prefix "bge=Represent this sentence for searching relevant passages: "`.
The prefix is applied only to queries and is recorded in the report. Corpus text
is unchanged. A provisioned local `documind_manifest.json` can record the pinned
checkpoint revision; model spaces remain isolated even when dimensions match.

## Read-only production variants

Create a separate qrels JSON using **existing chunk UUIDs belonging to one owner**:

```json
{
  "version": "course-material-v1",
  "queries": [
    {"id": "q1", "question": "Explain the calibration reference.",
     "relevant_ids": ["EXISTING-CHUNK-UUID"],
     "keypoints": {"5": ["reference rig"], "10": ["reference rig", "geometric frame"],
                   "15": ["reference rig", "geometric frame", "field bench"]}},
    {"id": "q2", "question": "An unanswered question", "relevant_ids": []}
  ]
}
```

```
venv/Scripts/python.exe -m evaluation.production_rag pipeline --owner OWNER-UUID --dataset evaluation/datasets/YOUR_QRELS.json --variant dense --variant hybrid --variant rerank --variant graph --variant topic --variant production --output evaluation/reports/pipeline_NEW.json
```

Every transaction starts `READ ONLY`. All nonempty qrels are checked against that
owner before retrieval. The owner flag is an operator-selected scope, not a login
or authorization bypass in the application. This is a local administrative tool.
The dense baseline disables index scans locally so installing HNSW cannot silently
turn that baseline into approximate search. Reranker warmup is recorded separately.

`production` runs the actual router, graph fusion, reranker and topic expansion.
The router can send the question to Groq. Other variants isolate each stage.
Add `--generate` explicitly to send evidence to Groq and evaluate all 5/10/15 mark
formats. Answer results include the actual answer, supplied-source count,
verification, warnings, abstention and generation p50/p95 by mark format.

Precision/Recall/MRR/nDCG use only answerable questions. Expanded evidence recall is separate
from top-k recall. Unanswerable prompts use abstention rate. Keypoint coverage is
literal normalized phrase coverage, not a semantic judge or a grade. Human grading
and LLM judge scores remain `not measured` unless explicitly supplied below; no Ragas score is synthesized. Use a
representative course corpus with reviewed qrels/rubrics and repeated warm/cold
runs before selecting models or publishing production p95 claims.

## Optional semantic judge

```
venv/Scripts/python.exe -m evaluation.production_rag pipeline --owner OWNER-UUID --dataset evaluation/datasets/YOUR_QRELS.json --variant production --generate --judge --output evaluation/reports/judged_NEW.json
```

`--judge` requires `--generate` and makes additional Groq calls for each nonempty
answer. It sends the question, answer and exact evidence excerpts actually
supplied to the answer model. Returned claim/source IDs, booleans, score ranges
and finite numbers are validated. Invalid, unavailable, truncated or over-budget
judgements are `not_measured`, never substituted with zero. Summaries average only
measured judgements. Supported-claim fraction and relevance are model estimates,
not verified truth or Ragas scores. Using the same model/provider for generation
and judging creates correlated-error bias. A judge can omit claims or make mistakes.

## Human review

```
venv/Scripts/python.exe -m evaluation.production_rag review-export --report evaluation/reports/judged_NEW.json --output evaluation/reports/review_NEW.csv
venv/Scripts/python.exe -m evaluation.production_rag review-summary --ratings evaluation/reports/review_NEW.csv --output evaluation/reports/human_summary_NEW.json
```

The export includes question, answer, rubric keypoints and exact supplied evidence.
Untrusted text cells are escaped to prevent spreadsheet formula execution. A human
reviewer fills `reviewer`, `score`, `accuracy_notes` and `rubric_notes`; scores must
be finite, at least zero and no greater than the row's 5/10/15 marks. Blank scores
remain pending and contribute no grade. Multiple reviewers can add distinct rows;
duplicate rows for the same reviewer/question/format are rejected. The summarizer
reports actual entered scores and pending counts; it does not invent a grade,
verify reviewer expertise or establish agreement between raters.

The new `datasets/student_rag_v2.json` fixture adds explicitly labelled table,
multi-hop and conflicting-revision examples to the original synthetic fixture.
Its short passages and hand-authored rubrics are smoke checks, not expert-reviewed
course marks. The original v1 dataset and earlier reports remain unchanged.

Minimal runnable check:

```
venv/Scripts/python.exe -m evaluation.production_rag self-check
```
