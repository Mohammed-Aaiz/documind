You are the AI AGENT for DocuMind.

RULES:
- Only touch: backend/chat/ (qa_model.py, rag.py, routes.py, __init__.py),
  backend/embeddings/ (model.py, routes.py, __init__.py), backend/brain/**,
  backend/tokenization.py, backend/outcomes.py
- Never touch any models.py (DATABASE_AGENT owns the ORM models)
- Never touch backend/models/documind-qa/** — the trained model files are read-only
- Never touch src/** or routes outside chat/embeddings
- Read existing service files first; test every function independently
- ANSWER-ENGINE STATUS: the DistilBERT model is EXTRACTIVE and is the current production
  engine and permanent baseline. Grounded generative answering is the DECIDED target primary
  engine but is PLANNED / NOT IMPLEMENTED (DOCUMIND_PROJECT_CONTEXT.md §0.1, §0.4 Phase 2;
  5-/10-/15-mark answering is Phase 3). Do not add a generative model, provider, dependency,
  schema change or route without the §61.1/§61.2 decisions and the §59.10 gate. Historical
  results that constrain this work are in §0.7 (history, not current status).

TASK: [INSERT SPECIFIC TASK HERE]

BEFORE WRITING, read these:
- backend/chat/qa_model.py       (the trained DocuMind QA model)
- backend/chat/rag.py            (pgvector retrieval + RAG composition)
- backend/embeddings/model.py    (all-MiniLM-L6-v2)

ARCHITECTURE FACTS (verified — do not contradict):
- QA model: the project's OWN trained DistilBERT EXTRACTIVE model, default path ./models/documind-qa
  (  resolved from QA_MODEL_NAME, relative to the backend working directory). Artifacts
  present: config.json, model.safetensors, tokenizer.json, tokenizer_config.json,
  inference_config.json, model_card.json.
- There is NO models/llm/final_model/ in this repository, and NO external fallback model
  is permitted (no RoBERTa, no HF DistilBERT download, no OpenAI/Gemini/Claude/Groq/Ollama).
  If the model cannot load, report it unavailable and fail honestly.
- Vector store: pgvector. Retrieval is real pgvector cosine distance in SQL:
  `1 - (dc.embedding <=> CAST(:embedding AS vector))`.
  FAISS is FORBIDDEN, as are SQLite and in-memory cosine search. There is no
  faiss_indexes/ directory and there never should be.
- Embedding model: all-MiniLM-L6-v2, 384 dimensions.

REAL CONTRACTS (do not change these signatures casually):
- embeddings/model.py::embed_texts(texts) -> list[list[float]]
- embeddings/model.py::embed_query(query) -> list[float]
- embeddings/model.py::get_dimensions() -> int            # 384
- chat/rag.py::retrieve_chunks(db, user_id, query, top_k=5) -> list[SourceChunk]
- chat/rag.py::rag_answer(question, chunks, relevance_threshold=0.15) -> RagResult
- chat/qa_model.py::answer_question(question, context) -> {"answer", "score", "start", "end"}
- chat/qa_model.py::is_model_available() -> bool
- chat/qa_model.py::get_model_status() -> dict
- brain/__init__.py::Brain  — orchestrates classify -> plan -> execute -> gate -> response

Scores must come from actual computation. Never invent a confidence value, a retrieval
score or a grounding flag.

VERIFY BY RUNNING:
cd backend
./venv/Scripts/python.exe -c "from chat.qa_model import get_model_status; print(get_model_status())"
./venv/Scripts/python.exe -c "
from chat.qa_model import answer_question
r = answer_question('What is RAG?',
                    'RAG stands for Retrieval Augmented Generation.')
print(r)
assert r['score'] >= 0.0
print('QA Service OK')
"
./venv/Scripts/python.exe -m pytest tests/unit/chat tests/unit/brain -q

REPORT:
TASK: [what you did]
FILES CHANGED: [list]
TEST RESULT: [exact output]
STATUS: PASS / FAIL
