# Incident: API down — DocuMind backend unreachable

## Purpose
Recover when the FastAPI backend (`backend/main.py`) is not responding at all,
taking every feature down: login, documents, chat/RAG, reliability, settings.

## Impact
Complete outage of the product. All frontend pages fail because every call in
`src/lib/api.ts` hits `/api/*` on this service.

## Symptoms
- `GET /api/health` fails (connection refused / timeout / non-200).
- Frontend shows network errors on login ("Request failed (…)") or hanging
  requests; browser console shows failed `fetch` to `/api/*`.
- Dev proxy (`vite.config.ts`) surfaces 500/ECONNREFUSED when backend:8000 is down.

## Severity
P0

## Immediate Actions
1. Confirm scope: `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health`
   (run from the host that should be serving the API).
2. Check whether the process is running:
   `uvicorn main:app --host 0.0.0.0 --port 8000` should be active in `backend/`
   (see `backend/start_server.py` for the expected invocation).
3. Do not change environment variables, config, or code yet — diagnose first.

## Diagnosis
1. **Process alive?** Check the uvicorn process/terminal. `start_server.py`
   waits up to 20s for `/api/health` and reports "Server failed to start" on failure.
2. **Startup errors?** Restarting in the foreground shows the traceback. Common
   causes visible at import time:
   - `config.py` cannot load `.env` (malformed env file).
   - `storage/database.py` — engine creation itself does not connect, so a bad
     `DATABASE_URL` will not fail startup; failures appear on first request.
3. **Port conflict?** Another process holding 8000 makes uvicorn fail with
   "address already in use" in its output.
4. **Dependency mismatch?** Compare installed packages with `backend/requirements.txt`
   (pinned versions, e.g. `fastapi==0.115.6`, `uvicorn[standard]==0.34.0`).
5. **CORS errors only?** If the browser shows CORS errors but `/api/health`
   responds via curl, check `CORS_ORIGINS` — it must include the frontend origin
   (defaults: `http://localhost:3000`, `http://localhost:5173`).

## Recovery
1. Fix the underlying cause found above (port conflict → stop the conflicting
   process; bad env → correct the value with the owner's approval).
2. Restart the backend:
   ```
   cd backend
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
3. Verify `GET /api/health` returns `"status": "healthy"`.

## Validation
- `GET /api/health` → 200 with `"status": "healthy"`.
- Login works from the frontend (POST `/api/auth/login` returns a token).
- One document list call succeeds (POST-protected routes hit the database).

## Rollback
No verified rollback mechanism found. There are no deployment tooling, images,
or release artifacts in the repository; recovery is restart-in-place after
fixing the cause.

## Escalation
- If uvicorn crashes on startup with a traceback you cannot resolve, stop and
  involve the developer who owns `backend/` — do not pin different dependency
  versions ad hoc.
- If the database also appears down, run the database runbook first
  ([database-failure.md](database-failure.md)) — login and all data endpoints fail there.

## Do Not
- Do not change `JWT_SECRET_KEY` or `DATABASE_URL` to "get things working" —
  that breaks all existing tokens/data. **REQUIRES HUMAN APPROVAL.**
- Do not run with a modified copy of `main.py` or ad-hoc dependency installs.
- Do not disable CORS middleware to make the frontend "work".

## Root Cause Follow-Up
- If startup depended on a transient condition, add a supervised start method
  (the repo currently has none).
- If a dependency mismatch caused it, re-pin `requirements.txt` deliberately and
  run `backend/tests/` after any change.
