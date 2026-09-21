# Incident: Mass authentication failures (JWT verification / secret mismatch)

## Purpose
Recover when all users are logged out or every request returns 401 — typically
caused by a changed/rotated `JWT_SECRET_KEY`, clock skew, or an inactive user
flag incident.

## Impact
All authenticated features fail. Login itself may still succeed (new tokens
work); previously issued tokens fail verification. If the secret was rotated,
every existing session is invalidated at once.

## Symptoms
- Every API call returns **401 "Invalid token"** or "Not authenticated"
  (`backend/auth/dependencies.py`).
- Login endpoint itself returns **401 "Invalid email or password"** when the
  problem is credentials/database, vs succeeding when only token verification
  is broken.
- Frontend shows the login page repeatedly; `AuthContext` clears state on 401.

## Severity
P1

## Immediate Actions
1. Determine the failure boundary:
   - `POST /api/auth/login` fails → database/credential problem (see
     [database-failure.md](database-failure.md)).
   - Login succeeds but other endpoints 401 → token verification problem
     (this runbook).
2. Capture one failing request's `Authorization: Bearer` behavior via the
   health check baseline: `curl http://localhost:8000/api/health` should be 200
   (health is unauthenticated).
3. Do not rotate or change `JWT_SECRET_KEY` during diagnosis.

## Diagnosis
1. **Was `JWT_SECRET_KEY` changed or rotated recently?** Tokens are HS256-signed
   with the current value of `settings.jwt_secret_key`
   (`backend/config.py`, `backend/auth/dependencies.py`). Any change to the
   value invalidates all previously issued tokens immediately. There is no
   server-side session store to invalidate — stateless JWTs only expire.
2. **Token lifetime?** `JWT_EXPIRE_MINUTES` (default 1440 = 24h). A value
   drastically reduced in `.env` makes tokens expire quickly for everyone.
3. **Clock skew?** `exp` is validated against server UTC time
   (`auth/routes.py`); a host with wrong time rejects fresh tokens.
4. **Algorithm mismatch?** `JWT_ALGORITHM` (default HS256) must match the
   algorithm used to sign outstanding tokens.
5. **Single user only?** Then it is not a secret problem: check the user's
   `is_active` flag — inactive users get 403 "User account is inactive"
   (login) / 403 (token use). Deactivation is a data change in the `users` table.
6. **401 vs 403 distinction:** 401 = missing/invalid token; 403 = token valid
   but user inactive.

## Recovery
1. If `JWT_SECRET_KEY` was changed unintentionally: restore the previous value
   in `backend/.env` (owner approval) and restart the backend — previously
   issued tokens become valid again within their lifetime.
2. If the rotation was intentional: users simply log in again; no server action
   is needed (stateless JWT). Confirm login works and the incident is expected
   behavior, then communicate the re-login requirement.
3. If clock skew: correct the host clock, restart nothing (verification is
   stateless).
4. If a user is wrongly inactive: re-enable via the `users` table
   (`is_active`), **REQUIRES HUMAN APPROVAL** — direct production data change.

## Validation
- `POST /api/auth/login` returns 200 with a token.
- `GET /api/auth/me` with that token returns the profile (200).
- Previously failing frontend sessions recover after the user logs in again.
- Unrelated check: `GET /api/health` stays 200.

## Rollback
No verified rollback mechanism found. Recovery is reverting the specific
env/config change that caused the mismatch (keep a change record of
`backend/.env` outside git — the file is gitignored).

## Escalation
- If you suspect the secret leaked, stop and escalate before rotating:
  **REQUIRES HUMAN APPROVAL** — rotation logs out every user and must be a
  deliberate, coordinated action (also treat the leak as a security incident).
- Escalate to the auth owner if `auth/dependencies.py` behavior itself seems
  wrong; do not patch verification logic ad hoc.

## Do Not
- Do not rotate `JWT_SECRET_KEY` "to test" — it invalidates every session.
- Do not disable token verification or loosen `algorithms` to make requests pass.
- Do not issue tokens manually or extend `exp` claims by hand.
- Do not modify the `users` table without ownership approval.

## Root Cause Follow-Up
- `backend/.env` is gitignored and unversioned; keep an auditable change log
  for auth-related env changes so mismatches are diagnosable.
- If accidental rotation recurs, consider provisioning the secret through a
  managed store rather than a local file (project decision).
