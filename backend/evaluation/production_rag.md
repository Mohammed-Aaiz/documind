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

Recall/MRR/nDCG use only answerable questions. Expanded evidence recall is separate
from top-k recall. Unanswerable prompts use abstention rate. Keypoint coverage is
literal normalized phrase coverage, not a semantic judge or a grade. Human grading
and LLM judge scores remain `not measured`; no Ragas score is synthesized. Use a
representative course corpus with reviewed qrels/rubrics and repeated warm/cold
runs before selecting models or publishing production p95 claims.

Minimal runnable check:

```
venv/Scripts/python.exe -m evaluation.production_rag self-check
```
