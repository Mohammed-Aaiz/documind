What DocuMind actually is
Product vision
Exactly 5 pages
Current architecture
Current tech stack
Actual trained model and where it lives
RAG pipeline
Database/vector architecture
Completed phases
Current implementation status
Frontend/design rules
Hard "DO NOT" rules
How future features must be implemented
Testing requirements
What is real vs what is planned

# DOCUMIND PROJECT CONTEXT
## Source of Truth for All Development Work

> IMPORTANT:
> This file is the authoritative project context for DocuMind.
> Before making ANY code, architecture, UI, backend, database, AI/ML,
> testing, or deployment change, READ THIS FILE FIRST.

---

# 1. PROJECT IDENTITY

Project Name: DocuMind

Product Type:
Multimodal AI Document Intelligence Workspace

Core Concept:

DocuMind allows users to upload documents, understand their content,
ask questions about them, receive evidence-backed answers, inspect
the supporting sources, and evaluate the reliability of those answers.

The product is NOT simply a PDF chatbot.

The core pipeline is:

UPLOAD
→ EXTRACT
→ CHUNK
→ EMBED
→ RETRIEVE
→ UNDERSTAND
→ ANSWER
→ PROVIDE EVIDENCE
→ MEASURE RELIABILITY

---

# 2. PRODUCT VISION

DocuMind should feel like a real AI knowledge workspace.

The user should be able to:

1. Authenticate
2. Upload supported documents
3. Process documents into searchable knowledge
4. Ask questions about their documents
5. Receive answers generated from retrieved evidence
6. See supporting sources
7. Inspect reliability/evidence signals
8. Verify potentially manipulated/generated media
9. Manage account and application settings

The system must prioritize:

- Evidence
- Traceability
- Reliability
- Real AI processing
- Real data
- Security
- Clean UX
- Production-oriented architecture

---

# 3. NON-NEGOTIABLE RULE

## NEVER FABRICATE FUNCTIONALITY

Every implemented feature must be REAL and FUNCTIONAL.

DO NOT create:

- Fake API responses
- Mock AI answers
- Hardcoded metrics
- Fake confidence scores
- Fake retrieval results
- Fake document processing
- Fake embeddings
- Fake vector search
- Fake media verification
- Fake authentication
- Fake database operations
- Fake security
- Simulated processing states presented as real
- Hardcoded "success" responses
- Placeholder AI outputs presented as actual results
- Fictional model capabilities
- Fake analytics
- Fake reliability measurements

If a feature is not implemented yet:

DO NOT pretend it works.

Instead:

- Keep it unavailable
- Show an honest "not available" state
- Or leave the feature unexposed until implemented

Accuracy is more important than making the UI look complete.

---

# 4. EXACT PRODUCT PAGES

DocuMind has EXACTLY FIVE pages.

Do NOT create additional pages unless explicitly approved.

### PAGE 1 — LOGIN

Purpose:
Authentication.

Requirements:

- Email/password login
- Real backend authentication
- JWT authentication
- Real error handling
- 3D cinematic visual background

---

### PAGE 2 — HOME / AI WORKSPACE

This is the primary product workspace.

Responsibilities:

- Upload documents
- Display user's documents
- Process documents
- Delete documents
- Ask questions
- Show answers
- Show supporting evidence
- Show relevant sources
- Access AI interaction
- Contextual reliability information

The workspace should remain centered and spacious.

Do not turn it into a traditional enterprise dashboard.

The conversation/chat interface should remain secondary to the main workspace.

---

### PAGE 3 — MEDIA VERIFICATION

Purpose:

Analyze uploaded image/video media for manipulation or AI-generated content.

Important:

Media verification must use an ACTUAL implemented model/pipeline.

Never fabricate:

- Authenticity score
- Synthetic score
- Lip-sync score
- Blink rate
- Detection confidence
- Manipulation probability

If the real detector is not implemented, report that honestly.

---

### PAGE 4 — RELIABILITY CENTER

Purpose:

Provide evidence and reliability information for document-based answers.

This page must use REAL backend data.

It should show information such as:

- Answer confidence
- Factual grounding
- Retrieved sources
- Retrieval relevance
- Source document
- Page
- Evidence status
- Reliability/evidence pathway

Do not hardcode values.

---

### PAGE 5 — SETTINGS / ACCOUNT

Purpose:

Simple application and account configuration.

May contain:

- Profile
- Security settings
- AI settings
- Environment/display preferences

Do not invent unnecessary enterprise features.

Do not add:

- Billing
- Teams
- Admin dashboards
- Enterprise management
- Fake security systems
- Quantum security
- "Neural ID"
- Fictional AI controls
- Fake analytics

---

# 5. CURRENT TECH STACK

## Frontend

- React 18
- TypeScript
- Vite
- Tailwind CSS
- Three.js
- Material Symbols / existing UI assets where appropriate

Frontend source:

src/

Important existing areas:

src/
├── components/
├── context/
├── lib/
├── pages/
├── types/
├── App.tsx
├── main.tsx
└── index.css

---

# 6. FRONTEND DESIGN SYSTEM

The current visual direction is:

Dark premium cinematic AI workspace.

Primary visual characteristics:

- Deep black / navy background
- Electric violet
- Cyber cyan
- Glassmorphism
- 3D depth
- Subtle particles
- Cinematic lighting
- Smooth transitions
- Minimal typography
- Spacious composition
- Premium AI-product aesthetic

Existing design document:

cinematic_intelligence/DESIGN.md

READ IT before making major UI changes.

---

# 7. FRONTEND UX RULES

The product should NOT look like a generic SaaS admin dashboard.

Avoid:

- Excessive sidebars
- Dense tables everywhere
- Too many cards
- Fake statistics
- Excessive badges
- Unnecessary pages
- Excessive controls
- Decorative UI that has no purpose

The main Home workspace should feel like a central intelligence workspace.

The interface should prioritize the actual user task.

---

# 8. 3D DESIGN

DocuMind intentionally uses a 3D visual identity.

The project contains a Three.js-based cinematic background/core.

3D should represent:

Documents
→ Knowledge
→ Retrieval
→ Evidence
→ Answer
→ Reliability

Do not replace the 3D experience with a generic flat dashboard unless explicitly instructed.

However:

3D must not negatively impact usability or performance.

---

# 9. CURRENT BACKEND STACK

Backend:

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy async
- Alembic
- pgvector
- PyMuPDF
- python-docx
- sentence-transformers
- Hugging Face Transformers
- JWT
- bcrypt/password hashing
- Local file storage for MVP

Backend structure:

backend/
├── auth/
├── chat/
├── documents/
├── embeddings/
├── reliability/
├── verification/
├── user/
├── storage/
├── models/
├── migrations/
├── main.py
├── config.py
└── requirements.txt

---

# 10. DATABASE

PostgreSQL is the primary database.

The current schema contains these major tables:

1. users
2. documents
3. document_chunks
4. chat_sessions
5. chat_messages
6. source_refs
7. verification_results
8. user_settings

Document chunks contain:

- Document relationship
- Content
- Page information
- Embedding
- Embedding status

pgvector is used for vector similarity search.

---

# 11. AUTHENTICATION

Authentication is REAL.

Current implementation:

- Email/password
- Password hashing
- JWT
- Protected routes
- User ownership checks
- `/api/auth/login`
- `/api/auth/logout`
- `/api/auth/me`

JWT uses HS256.

Default token lifetime is 24 hours unless configured otherwise.

Do not replace real authentication with mock authentication.

Do not create fake login success.

---

# 12. DOCUMENT INGESTION

Document ingestion is REAL.

Currently supported:

- PDF
- DOCX
- TXT

Processing pipeline:

DOCUMENT
→ TEXT EXTRACTION
→ CHUNKING
→ DATABASE STORAGE
→ EMBEDDING

PDF processing uses PyMuPDF.

DOCX processing uses python-docx.

TXT processing uses UTF-8 text reading.

Current chunking:

- approximately 1000 characters
- approximately 200 character overlap

PDF page numbers are preserved.

---

# 13. DOCUMENT API

Current document functionality includes:

- Upload
- List
- Retrieve
- Delete

Documents are scoped to the authenticated user.

Default maximum upload size:

50 MB unless configured otherwise.

Stored filenames use UUID-based naming.

---

# 14. EMBEDDING SYSTEM

DocuMind currently uses:

Model:

all-MiniLM-L6-v2

Embedding dimension:

384

Vector database:

PostgreSQL + pgvector

Current functionality:

POST /api/embeddings/generate

POST /api/embeddings/search

Similarity search uses real pgvector cosine similarity.

Search results contain real:

- chunk ID
- document ID
- document name
- content
- page
- similarity score

Do NOT replace this with keyword search unless explicitly requested.

---

# 15. CUSTOM QA MODEL

DocuMind has its OWN TRAINED QA MODEL.

This is extremely important.

Do NOT silently replace it with an external API or external model.

Model architecture:

DistilBertForQuestionAnswering

Model location:

backend/models/documind-qa

Important files include:

- config.json
- model.safetensors
- tokenizer.json
- tokenizer_config.json
- model_card.json
- inference_config.json

Model size:

Approximately 66.36M parameters.

---

# 16. QA MODEL TRAINING HISTORY

The model was trained in three phases.

### Phase 1

Dataset:

SQuAD 2.0

Samples:

87,599

Purpose:

Initial question-answering capability.

---

### Phase 2

Combined datasets:

- SQuAD 2.0
- HotpotQA
- CoQA
- NewsQA
- TriviaQA

Total:

414,057 examples

---

### Phase 3

Custom academic QA dataset.

50 custom QA pairs.

Training:

15 epochs

5 topics.

---

### TOTAL TRAINING DATA

414,107 training examples across the training phases.

---

# 17. QA MODEL RULE

There is NO external fallback model.

If:

backend/models/documind-qa

is unavailable or cannot load:

DO NOT automatically download or use:

- RoBERTa
- DistilBERT from Hugging Face
- OpenAI
- Gemini
- Claude
- Groq
- Ollama
- Any external LLM

unless explicitly instructed to change the architecture.

Instead:

Report the model as unavailable.

The system should fail honestly.

---

# 18. CURRENT RAG PIPELINE

The current RAG pipeline is:

USER QUESTION

↓

QUESTION EMBEDDING

↓

PGVECTOR SEARCH

↓

RELEVANT DOCUMENT CHUNKS

↓

CUSTOM QA MODEL

↓

ANSWER

↓

RELIABILITY / EVIDENCE SIGNALS

The system uses retrieved document context.

Answers must be grounded in retrieved evidence.

---

# 19. RAG BEHAVIOR

The RAG system tracks real signals including:

- QA confidence
- Retrieval scores
- Average retrieval score
- Best retrieval score
- Factual grounding
- Source count
- Unique documents
- Insufficient-context detection

Scores must come from actual processing.

Never invent a confidence percentage just to make the UI look good.

---

# 20. RELIABILITY CENTER

Reliability data currently comes from actual RAG execution.

Current evidence information includes:

- Answer confidence
- Factual grounding
- Retrieval relevance
- Source count
- Document information
- Page number
- Source status

Source statuses are derived from actual retrieval scores.

Current status concepts include:

VERIFIED
MARGINAL
UNRESOLVED

These must remain based on real data.

---

# 21. IMPORTANT RELIABILITY RULE

Reliability is NOT decoration.

Do not display:

"94.2% confidence"

or similar values unless the backend actually produced that value.

Every reliability metric must have a real computational origin.

If a metric cannot currently be calculated:

Do not fake it.

---

# 22. CURRENT VERIFIED TESTING STATUS

The project has already passed extensive real tests.

Authentication:

13/13 backend tests passed.

Authentication integration:

20/20 passed.

Document ingestion integration:

28/28 passed.

Embedding/vector retrieval:

30/30 passed.

RAG integration:

29/29 passed.

Reliability:

38/38 passed.

TypeScript:

0 errors.

Vite production build:

Successful.

These tests were executed against real PostgreSQL and real document/model processing.

Do not assume the project is still static/mock.

---

# 23. IMPORTANT PREVIOUS BUG FIX

A reliability bug occurred because pgvector cosine similarity can legitimately return negative values.

An early RAG path used a raw retrieval score as confidence.

This was fixed by clamping confidence/relevance values to:

0.0 → 1.0

The final Reliability tests reached:

38/38 PASS.

Do not reintroduce raw negative retrieval values into UI confidence fields.

---

# 24. CURRENT KNOWN ARCHITECTURAL CAVEAT

The current Reliability Center's "last query" state is held in memory/cache.

This means:

- It is lost on server restart.
- Multiple backend workers would not share the same state.
- User-scoping must be maintained carefully.

This is a known limitation.

If improving this later, prefer a database-backed reliability/query history design.

Do not silently introduce a global shared state that can leak another user's reliability data.

---

# 25. FRONTEND ↔ BACKEND RULE

The frontend must represent the actual backend state.

For example:

If backend says:

processing

Frontend should say:

Processing

If backend says:

error

Frontend should show:

Error

If backend has no model:

Frontend should not pretend the model worked.

If backend returns no reliability data:

Frontend should show an empty/unavailable state.

Never fake backend success.

---

# 26. API RULES

Before creating a new API:

1. Check whether an existing endpoint already handles the requirement.
2. Reuse existing architecture where possible.
3. Follow existing authentication patterns.
4. Follow existing user ownership rules.
5. Validate inputs.
6. Return meaningful HTTP errors.
7. Add tests.
8. Update frontend API functions if needed.

Do not create duplicate APIs unnecessarily.

---

# 27. SECURITY RULES

Every user-owned resource must be scoped to the authenticated user.

Never allow:

User A

to access:

User B's documents
User B's chat
User B's sources
User B's reliability data
User B's verification results

Do not trust IDs supplied by the frontend.

Validate ownership on the backend.

---

# 28. TESTING RULE

Every real backend feature must have tests.

At minimum:

- Happy path
- Invalid input
- Authentication failure
- Ownership/security case
- Relevant failure case

For AI/ML features:

Test with actual models and actual data whenever practical.

Do not write tests that simply assert a hardcoded fake response.

---

# 29. TESTING COMMAND PRINCIPLE

Before declaring a task complete:

Run the relevant tests.

Then run:

- TypeScript check
- Production build

when frontend code was changed.

Do not say:

"Done"

until the implementation has actually been verified.

---

# 30. FILE / ARCHITECTURE RULE

Before creating a new file:

Check the existing project structure.

Before creating a new component:

Check whether an existing component can be reused.

Before creating a new context/service:

Check existing contexts and API utilities.

Avoid unnecessary abstraction.

Prefer simple architecture that fits the current project.

---

# 31. DO NOT OVERENGINEER

DocuMind is a real product, but this does not mean every feature needs enterprise complexity.

Do not add:

- Microservices without a reason
- Event buses without a reason
- Kubernetes without a reason
- Complex distributed systems
- Unnecessary message queues
- Excessive abstraction
- Huge dependency additions
- Features that were not requested

Prefer the minimum practical production architecture.

---

# 32. DO NOT INVENT PRODUCT FEATURES

Do not invent features such as:

- Quantum security
- Neural identity
- Cognitive authentication
- AI consciousness
- Fictional intelligence scores
- Fake enterprise analytics
- Fake compliance
- Fake biometric security
- Fake "deep neural mode"
- Fictional processing metrics

If a feature sounds impressive but does not have a real technical implementation:

DO NOT ADD IT.

---

# 33. MEDIA VERIFICATION RULE

Media verification is a serious ML feature.

Only expose metrics that are actually generated by the implemented detector.

Possible future architecture may include:

Image:
→ preprocessing
→ detector
→ probability
→ explanation/evidence

Video:
→ frame sampling
→ detector
→ temporal analysis
→ aggregation

But this is only a planned architecture until actually implemented.

Never simulate detector output.

---

# 34. VOICE FEATURES

DocuMind's intended multimodal interaction includes:

Voice → Text
Voice → Voice
Text → Voice
Text → Text

Potential technology:

Whisper for speech-to-text.

gTTS for text-to-speech.

However:

If voice functionality is not currently implemented in the production code:

DO NOT pretend it exists.

Implement it only when explicitly tasked.

---

# 35. PRODUCT SCOPE

Current major product capabilities:

1. Authentication
2. Document ingestion
3. Embeddings
4. Vector retrieval
5. Custom QA model
6. RAG
7. Evidence/reliability
8. Media verification
9. Voice interaction
10. Settings/account

But implementation status matters.

A planned capability is NOT the same as an implemented capability.

Always distinguish:

IMPLEMENTED
PARTIALLY IMPLEMENTED
PLANNED
NOT IMPLEMENTED

---

# 36. CURRENT IMPLEMENTATION STATUS

## IMPLEMENTED

Authentication:
REAL

Document ingestion:
REAL

PDF extraction:
REAL

DOCX extraction:
REAL

TXT extraction:
REAL

Chunking:
REAL

PostgreSQL:
REAL

pgvector:
REAL

Embeddings:
REAL

Vector search:
REAL

Custom QA model:
REAL

RAG:
REAL

Reliability/evidence:
REAL

Frontend:
REAL

Frontend/backend authentication integration:
REAL

---

## PARTIALLY IMPLEMENTED / NEEDS HARDENING

Reliability "last query" persistence is currently in-memory.

Production deployment hardening is still required.

Media verification implementation must be verified before claiming completion.

Voice implementation must be verified before claiming completion.

---

# 37. STITCH DESIGN FILES

The project contains Stitch-generated visual references.

Directories include:

stitch_documind_futuristic_3d_ui/
documind_ai_workspace_desktop/
media_verification_desktop/
reliability_center_desktop/
documind_login_desktop/
documind_settings_desktop/

These contain:

- code.html
- screen.png

These are design references.

Do not blindly copy Stitch HTML into the production React architecture.

Use them as visual references.

---

# 38. DESIGN SOURCE OF TRUTH

For visual/design decisions:

1. Existing production React implementation
2. cinematic_intelligence/DESIGN.md
3. Stitch visual references

Do not introduce a completely different visual language.

---

# 39. WHEN RECEIVING A NEW TASK

Before changing anything:

STEP 1:
Read this file.

STEP 2:
Inspect the existing implementation.

STEP 3:
Determine the current implementation status.

STEP 4:
Identify the smallest correct architectural change.

STEP 5:
Implement the real functionality.

STEP 6:
Connect frontend/backend if required.

STEP 7:
Add/update tests.

STEP 8:
Run tests.

STEP 9:
Run TypeScript/build checks when applicable.

STEP 10:
Report exactly what was implemented and verified.

---

# 40. TASK EXECUTION RULE

Do not blindly execute the user's latest sentence without understanding its relationship to the existing system.

Example:

If asked:

"Add reliability"

Do not immediately create a new reliability system.

First inspect:

- existing RAG
- existing reliability routes
- existing database models
- existing frontend
- existing API utilities

Then extend the existing architecture.

---

# 41. CHANGE SAFETY

Before modifying existing code:

Understand why it exists.

Do not delete working functionality merely to simplify a task.

Do not replace a real implementation with a mock.

Do not downgrade a real ML implementation to a simpler placeholder.

Do not introduce breaking changes unless explicitly required.

---

# 42. DEPENDENCY RULE

Before adding a dependency:

Ask:

1. Is it actually necessary?
2. Is there already a dependency that solves the problem?
3. Does it significantly increase bundle/install complexity?
4. Is it compatible with the existing architecture?

Avoid unnecessary dependencies.

---

# 43. ENVIRONMENT RULE

Secrets must NOT be committed.

Use:

.env

for local development.

Use:

.env.example

for documented configuration.

Never hardcode:

- JWT secrets
- API keys
- passwords
- database credentials

---

# 44. REAL VS PLANNED

This distinction is critical.

### REAL

A feature is REAL only if:

- Code exists
- It executes
- It uses real data/model/database
- It has been tested
- The frontend accurately reflects its state

### PLANNED

A feature is PLANNED if:

- Architecture has been discussed
- UI exists as a placeholder/reference
- No actual implementation exists

Never describe PLANNED as REAL.

---

# 45. PRODUCT QUALITY STANDARD

The goal is not:

"Make the demo look impressive."

The goal is:

"Build a technically credible AI product."

Prioritize:

1. Correctness
2. Real functionality
3. Evidence
4. Security
5. Reliability
6. Maintainability
7. UX
8. Visual polish

Visual polish must never hide missing functionality.

---

# 46. CURRENT DEVELOPMENT PHASE

The project has completed:

PHASE 1:
Backend foundation

PHASE 2:
Real authentication

PHASE 2B:
Frontend/backend authentication integration

PHASE 3:
Real document ingestion

PHASE 4:
Real embeddings + pgvector retrieval

PHASE 5:
Real RAG + custom trained QA model

PHASE 6:
Reliability + evidence

Future work should continue from this architecture.

Do not restart the project or rebuild completed phases unless explicitly instructed.

---

# 47. MASTER DEVELOPMENT PRINCIPLE

Always think:

"What would a real user expect this feature to actually do?"

Then implement that behavior.

Do not think:

"What can I make the UI appear to do?"

The system must be truthful.

---

# 48. REQUIRED RESPONSE FORMAT AFTER TASK COMPLETION

After implementing a task, report:

## Implemented

List the actual changes.

## Files Changed

List relevant files.

## Verification

List actual tests/checks run and results.

## Known Limitations

Only mention real limitations.

## Next Step

Only suggest the logical next development step.

Do not claim functionality that was not tested.

---

# 49. FINAL INSTRUCTION

Before EVERY task:

READ THIS FILE.

Then inspect the existing code.

Treat this document as the project's architectural memory.

Never assume DocuMind is a blank project.

Never replace real functionality with mocks.

Never fabricate AI results.

Never fabricate metrics.

Never invent product capabilities.

Never add pages without approval.

Never expand scope unnecessarily.

Build DocuMind as a real, evidence-driven multimodal AI product.

END OF PROJECT CONTEXT