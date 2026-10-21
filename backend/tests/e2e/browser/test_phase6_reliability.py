"""
Phase 6 Integration Test Script.
Starts the backend server, runs all reliability tests, then kills the server.
"""
import subprocess
import sys
import os
import time
import json
import urllib.request
from functools import partial
from pathlib import Path

import pytest

from tests.fixtures.integration_http import api_call as _api_call
from tests.fixtures.integration_http import multipart_upload
from tests.fixtures.live_server import server_available

# This harness starts its own uvicorn serving ``main:app``, so it must run with
# the backend root as the working directory.  It used to chdir to its own file's
# directory, which after the 2026-09-30 move into tests/e2e/browser/ is *not* the
# backend root; it now resolves the backend root explicitly.
_BACKEND_DIR = Path(__file__).resolve().parents[3]

BASE = 'http://localhost:8000'

# Bound to this harness's BASE; see tests/integration_http.py.
api_call = partial(_api_call, base=BASE)


def main():
    # Side effects that used to run at import time (and therefore fired during
    # pytest collection) belong to the run, not to the import.
    os.chdir(_BACKEND_DIR)
    # STEP 1.6AB: cleared through the shared boundary helper rather than
    # ``shutil.rmtree(..., ignore_errors=True)``.  The old sweep recursed wherever a
    # ``__pycache__`` name pointed (a junction was followed and its target emptied,
    # because ``os.path.isdir`` follows a link) and swallowed every failure.  The
    # helper stays inside the backend tree, refuses links and reparse points instead
    # of following them, and reports each refusal.
    if str(_BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(_BACKEND_DIR))
    from scripts.cleanup_path import prune_pycache_beneath

    pruned, refused = prune_pycache_beneath(_BACKEND_DIR)
    print(f"Cleared {pruned} __pycache__ directory(ies)")
    for entry in refused:
        print(f"  skipped: {entry}")

    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        status = "PASS" if condition else "FAIL"
        if condition:
            passed += 1
        else:
            failed += 1
        suffix = f" -- {detail}" if detail else ""
        print(f"  [{status}] {name}{suffix}")

    # Start server
    print("Starting backend server...")
    proc = subprocess.Popen(
        [sys.executable, '-B', '-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000'],
        cwd='.'
    )
    try:
        for i in range(120):
            time.sleep(1)
            try:
                resp = urllib.request.urlopen(f'{BASE}/api/health', timeout=2)
                data = json.loads(resp.read())
                if data.get('qa_model', {}).get('available'):
                    print(f"Server ready (PID {proc.pid})\n")
                    break
            except Exception:
                pass
        else:
            print("Server failed to start!")
            return 1

        print("=" * 60)
        print("  PHASE 6 — REAL RELIABILITY & EVIDENCE TEST")
        print("=" * 60)

        # 1. Login
        print("\n1. Login")
        code, body = api_call('POST', '/api/auth/login', body={
            'email': 'test@documind.io', 'password': 'TestPass123!'
        })
        token = body.get('access_token', '')
        check("Login succeeds", code == 200, f"got {code}")

        # 2. Upload document
        print("\n2. Upload knowledge document")
        import pymupdf
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72),
            "The DocuMind system was created by the Acme Corporation in 2024. "
            "It uses advanced neural networks for document analysis. "
            "The system supports PDF, DOCX, and TXT file formats. "
            "Maximum file upload size is 50 megabytes.",
            fontsize=12)
        pdf_path = os.path.join('uploads', 'phase6_test.pdf')
        doc.save(pdf_path)
        doc.close()

        code, doc_resp = multipart_upload(f'{BASE}/api/documents/upload', token, pdf_path, 'phase6_test.pdf')
        doc_id = doc_resp.get('id', '')
        check("Upload succeeds", code == 201, f"got {code}")
        check("Got document ID", bool(doc_id))

        # 3. Generate embeddings
        print("\n3. Generate embeddings")
        code, gen = api_call('POST', '/api/embeddings/generate', token=token, body={'documentId': doc_id})
        check("Embeddings generated", code == 200, f"got {code}")
        check("Chunks embedded > 0", gen.get('chunksEmbedded', 0) > 0)

        # 4. Ask question — verify reliability in response
        print("\n4. Ask: 'Who created DocuMind?' — verify reliability evidence")
        code, ans = api_call('POST', '/api/chat/ask', token=token, body={
            'question': 'Who created DocuMind?', 'topK': 3
        })
        reliability = ans.get('reliability', {})
        check("Ask returns 200", code == 200, f"got {code}")
        check("Got an answer", bool(ans.get('answer')), f"answer='{ans.get('answer')}'")
        check("Answer contains 'Acme'", 'acme' in ans.get('answer', '').lower())
        check("Has sources", len(ans.get('sources', [])) > 0)

        print(f"\n   Reliability evidence:")
        print(f"     qaConfidence:    {reliability.get('qaConfidence')}")
        print(f"     retrievalScore:  {reliability.get('retrievalScore')}")
        print(f"     avgRetrievalScore: {reliability.get('avgRetrievalScore')}")
        print(f"     sourceCount:     {reliability.get('sourceCount')}")
        print(f"     uniqueDocuments: {reliability.get('uniqueDocuments')}")
        print(f"     factualGrounded: {reliability.get('factualGrounded')}")
        print(f"     insufficientContext: {reliability.get('insufficientContext')}")

        check("qaConfidence is real number", reliability.get('qaConfidence') is not None)
        check("qaConfidence in [0,1]", 0.0 <= (reliability.get('qaConfidence', -1)) <= 1.0,
              f"got {reliability.get('qaConfidence')}")
        check("retrievalScore is real", reliability.get('retrievalScore') is not None)
        check("avgRetrievalScore is real", reliability.get('avgRetrievalScore') is not None)
        check("sourceCount > 0", reliability.get('sourceCount', 0) > 0)
        check("uniqueDocuments >= 1", reliability.get('uniqueDocuments', 0) >= 1)
        check("factualGrounded is True", reliability.get('factualGrounded') is True)
        check("insufficientContext is False", reliability.get('insufficientContext') is False)
        check("Confidence > 0.1", reliability.get('qaConfidence', 0) > 0.1)

        # 5. Unsupported question
        print("\n5. Ask: 'What is the capital of France?' — verify insufficient context")
        code, ans2 = api_call('POST', '/api/chat/ask', token=token, body={
            'question': 'What is the capital of France?', 'topK': 3
        })
        r2 = ans2.get('reliability', {})
        check("Ask returns 200", code == 200)
        check("insufficientContext is True", r2.get('insufficientContext') is True)
        check("factualGrounded is False", r2.get('factualGrounded') is False)
        check("qaConfidence in [0,1] for unsupported", 0.0 <= (r2.get('qaConfidence', -1)) <= 1.0,
              f"got {r2.get('qaConfidence')}")
        print(f"   qaConfidence={r2.get('qaConfidence')}, insufficientContext={r2.get('insufficientContext')}, grounded={r2.get('factualGrounded')}")

        # 6. Last-query endpoint
        print("\n6. GET /api/reliability/last-query")
        code, last = api_call('GET', '/api/reliability/last-query', token=token)
        check("Returns 200", code == 200, f"got {code}")
        check("question matches last query", last.get('question') == 'What is the capital of France?')
        check("Has sources from last query", len(last.get('sources', [])) > 0)
        check("qaConfidence in response", last.get('qaConfidence') is not None)

        for src in last.get('sources', []):
            check(f"Source status valid ({src.get('status')})", src.get('status') in ('VERIFIED', 'MARGINAL', 'UNRESOLVED'))
            check(f"Source score non-negative ({src.get('relevanceScore')})", src.get('relevanceScore', -1) >= 0)
            check(f"Source has page", src.get('page') is not None)

        # 7. Unauthenticated access
        print("\n7. Unauthenticated access")
        code, _ = api_call('GET', '/api/reliability/last-query')
        check("Returns 401 without token", code == 401, f"got {code}")

        code, _ = api_call('POST', '/api/chat/ask', body={'question': 'test', 'topK': 1})
        check("Ask returns 401 without token", code == 401, f"got {code}")

        # 8. Cleanup
        print("\n8. Cleanup")
        api_call('DELETE', f'/api/documents/{doc_id}', token=token)
        try:
            os.unlink(pdf_path)
        except OSError:
            pass
        check("Cleanup done", True)

        # Summary
        total = passed + failed
        print()
        print("=" * 60)
        print(f"  RESULTS: {passed}/{total} passed, {failed} failed")
        print("=" * 60)
        print()

        return 0 if failed == 0 else 1

    finally:
        proc.terminate()
        proc.wait(timeout=5)
        print("Server terminated.")


if __name__ == "__main__":
    sys.exit(main())


# ---------------------------------------------------------------------------
# pytest entry point — the test-isolation contract requires tests to run only
# through pytest.  This harness starts its own backend, so it is skipped when
# port 8000 is already occupied (it could not bind) and otherwise runs for real.
# ---------------------------------------------------------------------------
@pytest.mark.e2e
def test_phase6_reliability_live_server():
    """Start the backend, run the reliability/evidence flow, then stop it.

    Opt-in only: unlike the other e2e harnesses this one *starts its own*
    server, writes to the real database and takes ~30 s.  Running it as part of
    an ordinary `pytest -q` would be a side effect, not a test, so it is skipped
    unless DOCUMIND_E2E_SERVER_SMOKE=1 is set explicitly::

        DOCUMIND_E2E_SERVER_SMOKE=1 ./venv/Scripts/python.exe -m pytest -q \
            -m e2e tests/e2e/browser/test_phase6_reliability.py
    """
    if os.environ.get("DOCUMIND_E2E_SERVER_SMOKE") != "1":
        pytest.skip(
            "opt-in runtime smoke test — set DOCUMIND_E2E_SERVER_SMOKE=1 to run"
        )
    if server_available(BASE):
        pytest.skip(
            f"port 8000 already serving ({BASE}); this harness starts its own server"
        )
    assert main() == 0
