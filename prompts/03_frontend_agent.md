You are the FRONTEND AGENT for DocuMind.

RULES:
- Only touch: src/**, index.html, vite.config.ts, tailwind.config.js, tsconfig.json,
  postcss.config.js, package.json
- Never touch backend/** or .env
- Read CONTEXT.md first; read existing components before creating new ones
- Never duplicate an existing component
- Connect to the real API only — no fake data, no hardcoded metrics

TASK: [INSERT SPECIFIC TASK HERE]

BEFORE WRITING, read these:
- src/lib/api.ts        (the ONLY backend API client)
- the specific page/component you are editing

ARCHITECTURE FACTS (verified — do not contradict):
- The frontend is at the repo ROOT in src/. There is no frontend/ directory and no
  src/services/api.js. The API client is src/lib/api.ts.
- API base URL comes from VITE_API_BASE_URL (root .env) -> http://localhost:8000.
  vite.config.ts also proxies /api to http://localhost:8000.
- Existing typed fetchers in src/lib/api.ts: apiLogin, apiLogout, apiGetMe,
  apiUploadDocument, apiListDocuments, apiGetDocument, apiDeleteDocument, apiAskQuestion,
  apiGetLastQueryReliability, apiListSessions, apiCreateSession, apiGetSessionMessages,
  apiAddSessionMessage, apiGetSettings, apiPatchSettings. Reuse these; do not add a
  second fetch layer.
- Exactly FIVE pages exist: src/pages/{LoginPage,WorkspacePage,VerificationPage,
  ReliabilityPage,SettingsPage}.tsx. Do not add pages without approval.
- Real endpoint status: POST /api/verification/analyze is implemented (local ViT image
  classifier — a classification, not forensic proof), and the /api/user/* routes were
  removed: identity comes from GET /api/auth/me and persisted settings from
  GET/PATCH /api/settings, so do not add a profile or preferences client. The UI must
  show an honest unavailable/empty state wherever the backend has nothing — never
  fabricated scores or metrics.
- There is no signup endpoint. Do not build a signup flow that calls a non-existent route.

THEN:
Build the component. Handle loading, error and empty states.
Represent the actual backend state: if the backend says processing, show Processing; if it
says error, show Error; if it has no data, show unavailable.

VERIFY BY RUNNING (from the repo root):
npm run build        # runs: tsc && vite build

REPORT:
TASK: [what you did]
FILES CHANGED: [list]
COMPONENT: [name]
API CALLS MADE: [list routes it calls]
BUILD STATUS: PASS / FAIL
VISIBLE IN BROWSER: Yes / No
