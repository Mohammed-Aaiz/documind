"""Start backend server in background, wait for readiness, then verify.

The readiness budget must be larger than the real cold-start time.  Startup is
dominated by importing the ML stack (torch / transformers /
sentence-transformers, pulled in by chat/qa_model.py and embeddings/model.py)
plus the Alembic upgrade that ``main.py`` runs inside its lifespan; measured at
roughly 27s on a warm cache.  The previous fixed 20s wait was therefore shorter
than a normal start, so it killed servers that were still booting and reported
them as startup failures.

Usage:
    cd backend && python scripts/start_server.py
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

HOST = '0.0.0.0'
PORT = 8000
HEALTH_URL = f'http://localhost:{PORT}/api/health'

# Cold start is ~27s (imports ~19s + Alembic migration ~7s).  Keep a wide
# margin so a first run with cold OS/bytecode caches is not mistaken for a
# failure.
READY_TIMEOUT_SECONDS = 120

# Generous per-request timeout: the first /api/health call also triggers the
# lazy QA-model load, so it is slower than every later one.
HEALTH_REQUEST_TIMEOUT_SECONDS = 10

# This script lives in scripts/; uvicorn must start from the backend package
# root so ``main:app`` is importable.  ``__file__`` may be relative, so resolve
# it to an absolute path before walking up two levels.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Running a file inside scripts/ puts only scripts/ on sys.path, so the backend
# package root (which holds scripts/, auth/, storage/, ...) must be added
# explicitly before importing the shared cleanup helpers.
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import scripts.cleanup_path as cleanup_path  # noqa: E402

os.chdir(_BACKEND_DIR)


def _port_in_use() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(('127.0.0.1', PORT)) == 0


# Starting a second server against an occupied port fails at bind time, and the
# failure surfaces only after the whole import+migration startup has run.  Catch
# it up front instead of mistaking whatever already owns the port for our own
# server.
if _port_in_use():
    print(f"Port {PORT} is already in use -- another server is already running.")
    print("Stop it first (or use it directly); refusing to start a second one.")
    sys.exit(1)

# Clear all pyc (STEP 1.6AA, finding C).  This used to be
# ``shutil.rmtree(..., ignore_errors=True)`` on every ``__pycache__`` name found
# while walking the CWD: no containment check, no reparse-point check, and every
# failure swallowed.  A ``__pycache__`` replaced by a junction was therefore
# recursed into and its target emptied, silently.  It now goes through the shared
# boundary helper, which removes only a real directory inside the backend tree,
# refuses (never follows) links and reparse points, and reports each refusal
# instead of hiding it.
_pruned, _refused = cleanup_path.prune_pycache_beneath(_BACKEND_DIR)
print(f"Cleared {_pruned} __pycache__ directory(ies)")
for _entry in _refused:
    print(f"  skipped: {_entry}")

proc = subprocess.Popen(
    [sys.executable, '-B', '-m', 'uvicorn', 'main:app', '--host', HOST, '--port', str(PORT)],
    cwd='.'
)
print(f"Server started with PID {proc.pid}")
print(f"Waiting up to {READY_TIMEOUT_SECONDS}s for {HEALTH_URL} ...")


def _fetch_health() -> dict:
    with urllib.request.urlopen(HEALTH_URL, timeout=HEALTH_REQUEST_TIMEOUT_SECONDS) as resp:
        return json.loads(resp.read())


started = time.monotonic()
data = None
last_error = None

while time.monotonic() - started < READY_TIMEOUT_SECONDS:
    # Fail fast rather than burning the full budget: a server process that has
    # already exited (bad config, migration failure, occupied port) will never
    # become healthy.
    if proc.poll() is not None:
        print(f"Server process exited with code {proc.returncode} before becoming ready")
        print("See the server output above for the underlying error")
        sys.exit(1)

    try:
        data = _fetch_health()
        break
    except (urllib.error.URLError, OSError, ValueError) as exc:
        last_error = exc
        time.sleep(1)

if data is None:
    print(f"Server failed to become healthy within {READY_TIMEOUT_SECONDS}s")
    if last_error is not None:
        print(f"Last health request error: {last_error}")
    proc.kill()
    sys.exit(1)

elapsed = time.monotonic() - started
print(f"Health check OK after {elapsed:.1f}s: "
      f"qa_model available={data.get('qa_model', {}).get('available')}")
print(f"Final health: {json.dumps(data, indent=2)}")
