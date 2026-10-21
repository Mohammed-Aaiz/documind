# AI_AGENT

## Role

Embeddings, retrieval, QA, Brain orchestration, document graph
retrieval, and AI outcome contracts.

## Owns

-   `backend/chat/**` except `models.py`
-   `backend/embeddings/**` except `models.py`
-   `backend/brain/**`
-   `backend/graph/**` except `models.py`
-   `backend/tokenization.py`
-   `backend/outcomes.py`

## Must Not Touch

Trained weights under `backend/models/documind-qa/**`, ORM model files,
migrations, unrelated backend ownership, frontend.

## Rules

Use the project's trained DistilBERT QA model. No external fallback.
Semantic retrieval uses pgvector. No FAISS substitute. Graph retrieval
is document-native and deterministic. Preserve retrieval provenance.
Never fabricate confidence.

**Answer-engine status.** The DistilBERT model is **extractive** and remains the
**default** engine and the permanent comparison baseline. An **additive** generative
path is **PARTIALLY IMPLEMENTED** (2026-10-17): local, offline Flan-T5-base in
`backend/generation/`, exposed at `POST /api/generation/answer`, with deterministic
claim/citation verification and withhold-on-unattributable behaviour. The owner
decision is recorded in `DOCUMIND_PROJECT_CONTEXT.md` §0.8 and resolves §61.1/§61.2
**for the local Flan-T5-base scope only**.

Do not: add a hosted provider or any external egress without a new decision; swap the
model silently; or claim the generative path is complete. Known gaps (§0.8.4): the
10/15-mark depth requirement is **not met**, no P3 evaluation has been run, and
verification is lexical attribution, not entailment. Historical results that constrain
this work (populations, H1 metrics, F2/G/H1/H1-R/E0) are in §0.7 — history, not
current status.

## Verify

``` bash
cd backend
python -c "from chat.qa_model import get_model_status; print(get_model_status())"
python -m pytest -q tests/unit/chat tests/unit/brain
```
