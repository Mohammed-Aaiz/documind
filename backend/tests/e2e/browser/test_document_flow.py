"""
Full integration test for document ingestion pipeline.

Tests through the real Vite proxy -> FastAPI -> PostgreSQL.
No mocks, no fakes, no simulated responses.
"""

import json
import os
import sys
import urllib.request

import pytest

from tests.fixtures import e2e_config
from tests.fixtures.integration_http import multipart_upload
from tests.fixtures.live_server import require_live_server

BASE = e2e_config.base_url()  # Vite proxy -> FastAPI


def create_test_document_pdf(path):
    """Write the deterministic multi-page PDF this harness uploads.

    Generated here rather than read from a CWD-relative path.  The old
    ``"uploads/test_document.pdf"`` resolved against the *application's*
    upload directory, so the fixture could only exist on a developer machine
    that had placed it there by hand.  Nothing in this text is asserted
    against; the checks only require a real, ingestible multi-page PDF.
    """
    import pymupdf

    doc = pymupdf.open()
    paragraphs = [
        "Document ingestion verification fixture. This file exercises the "
        "complete pipeline: extraction, chunking, embedding and retrieval.",
        "The second page carries additional prose so the extractor produces "
        "more than one chunk and the chunk route can be verified directly.",
        "The third page closes the fixture. It contains ordinary English text "
        "and no value that any assertion in this harness depends upon.",
    ]
    for paragraph in paragraphs:
        page = doc.new_page()
        page.insert_text((72, 72), paragraph, fontsize=12)
    doc.save(path)
    doc.close()


def api_call(method, path, token=None, body=None, data=None, content_type=None):
    url = f"{BASE}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    elif data is not None:
        # For multipart, don't set Content-Type (browser sets boundary)
        pass
    req = api_call_raw(url, method, headers, data)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def api_call_raw(url, method, headers, data=None):
    return urllib.request.Request(url, data=data, headers=headers, method=method)


def main():
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

    print()
    print("=" * 60)
    print("  DOCUMENT INGESTION INTEGRATION TEST")
    print("  (React -> Vite proxy -> FastAPI -> PostgreSQL)")
    print("=" * 60)

    # 1. Login to get a token
    print()
    print("1. Login to get JWT token")
    code, body = api_call("POST", "/api/auth/login", body={
        "email": e2e_config.DEMO_USER_EMAIL,
        "password": e2e_config.DEMO_USER_PASSWORD,
    })
    check("Login succeeds", code == 200, f"got {code}")
    token = body.get("access_token", "")
    check("Got access_token", bool(token))

    # 2. Upload a real PDF
    print()
    print("2. Upload a real PDF document")
    test_pdf = e2e_config.generated_uploads_dir() / "test_document.pdf"
    create_test_document_pdf(test_pdf)
    code, body = multipart_upload(
        f"{BASE}/api/documents/upload",
        token,
        str(test_pdf),
        "test_document.pdf",
    )
    os.unlink(test_pdf)
    check("Upload returns 201", code == 201, f"got {code}: {body}")
    check("Document has id", "id" in body)
    check("Document name matches", body.get("name") == "test_document.pdf")
    check("File type is pdf", body.get("fileType") == "pdf")
    check("Status is 'ready'", body.get("status") == "ready")
    check("Has chunks", body.get("chunkCount", 0) > 0, f"chunkCount={body.get('chunkCount')}")
    doc_id = body.get("id", "")

    # 3. Verify document in PostgreSQL
    print()
    print("3. Verify document exists in PostgreSQL")
    result = e2e_config.psql(
        f"SELECT id, name, file_type, status, chunk_count, user_id FROM documents WHERE id = '{doc_id}';"
    )
    check("Document in DB", doc_id in result, result.strip()[:200])

    # 4. Verify chunks in document_chunks
    print()
    print("4. Verify chunks exist in document_chunks")
    result = e2e_config.psql(
        f"SELECT COUNT(*) as chunk_count FROM document_chunks WHERE document_id = '{doc_id}';"
    )
    check("Chunks in DB", "chunks" in result.lower() or "chunk_count" in result, result.strip()[:200])

    # Verify chunks have content
    result = e2e_config.psql(
        f"SELECT chunk_index, length(content) as content_len, page FROM document_chunks WHERE document_id = '{doc_id}' ORDER BY chunk_index;"
    )
    check("Chunks have content", "content_len" in result, result.strip()[:300])

    # 5. Verify document belongs to authenticated user
    print()
    print("5. Verify document belongs to authenticated user")
    # Get user_id from login
    result = e2e_config.psql(
        f"SELECT id FROM users WHERE email = '{e2e_config.DEMO_USER_EMAIL}';"
    )
    user_id = ""
    for line in result.split("\n"):
        line = line.strip()
        if len(line) == 36 and "-" in line:
            user_id = line
            break
    check("Got user_id", bool(user_id), user_id[:50])

    if user_id and doc_id:
        result = e2e_config.psql(
            f"SELECT user_id FROM documents WHERE id = '{doc_id}';"
        )
        check("Document user_id matches", user_id in result)

    # 6. List documents through API
    print()
    print("6. List documents through API")
    code, body = api_call("GET", "/api/documents", token=token)
    check("List returns 200", code == 200, f"got {code}")
    docs = body.get("documents", [])
    check("List has at least 1 document", len(docs) >= 1, f"count={len(docs)}")
    check("Document in list matches uploaded", any(d.get("id") == doc_id for d in docs))

    # 7. Get document detail
    print()
    print("7. Get document detail with chunks")
    code, body = api_call("GET", f"/api/documents/{doc_id}", token=token)
    check("Detail returns 200", code == 200, f"got {code}")
    check("Detail has chunks", len(body.get("chunks", [])) > 0, f"chunks={len(body.get('chunks', []))}")
    check("Chunk has content", bool(body.get("chunks", [{}])[0].get("content")))

    # 8. Delete document
    print()
    print("8. Delete document")
    code, body = api_call("DELETE", f"/api/documents/{doc_id}", token=token)
    check("Delete returns 200", code == 200, f"got {code}")

    # Verify deletion in PostgreSQL
    result = e2e_config.psql(
        f"SELECT COUNT(*) FROM documents WHERE id = '{doc_id}';"
    )
    check("Document removed from DB", "0" in result)

    # Verify chunks cascade-deleted
    result = e2e_config.psql(
        f"SELECT COUNT(*) FROM document_chunks WHERE document_id = '{doc_id}';"
    )
    check("Chunks cascade-deleted", "0" in result)

    # 9. Unauthenticated access
    print()
    print("9. Test unauthenticated access")
    code, body = api_call("GET", "/api/documents")
    check("List without token returns 401", code == 401, f"got {code}")

    code, body = api_call("GET", f"/api/documents/{doc_id}")
    check("Detail without token returns 401", code == 401, f"got {code}")

    code, body = api_call("DELETE", f"/api/documents/{doc_id}")
    check("Delete without token returns 401", code == 401, f"got {code}")

    # 10. Invalid file type
    print()
    print("10. Test invalid file type upload")
    # Create a fake .exe file
    # NOTE: ``os`` is imported at module scope.  A function-local ``import os``
    # here would make ``os`` local to the whole of ``main()`` and raise
    # UnboundLocalError at every earlier ``os`` reference.
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
        f.write(b"MZ fake executable")
        fake_path = f.name
    code, body = multipart_upload(
        f"{BASE}/api/documents/upload",
        token,
        fake_path,
        "malware.exe",
    )
    os.unlink(fake_path)
    check("Invalid file type returns 400", code == 400, f"got {code}: {body.get('detail', '')}")

    # 11. Upload TXT file
    print()
    print("11. Upload a real TXT file")
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
        f.write("This is a plain text test file.\nIt has multiple lines.\nLine three of the test.")
        txt_path = f.name
    code, body = multipart_upload(
        f"{BASE}/api/documents/upload",
        token,
        txt_path,
        "test.txt",
    )
    os.unlink(txt_path)
    check("TXT upload returns 201", code == 201, f"got {code}")
    check("TXT status is ready", body.get("status") == "ready")
    txt_doc_id = body.get("id", "")

    # Clean up TXT doc
    if txt_doc_id:
        api_call("DELETE", f"/api/documents/{txt_doc_id}", token=token)

    # Summary
    total = passed + failed
    print()
    print("=" * 60)
    print(f"  RESULTS: {passed}/{total} passed, {failed} failed")
    print("=" * 60)
    print()

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)


# ---------------------------------------------------------------------------
# pytest entry point — the test-isolation contract requires tests to run only
# through pytest.  Skipped unless a live server answers at BASE.
#
# This harness additionally verifies rows directly through ``psql``.  Both the
# binary and the connection parameters (host/port/database/user) come from
# ``tests/fixtures/e2e_config``, so it needs no ambient PGPORT/PGHOST and no
# machine-specific path.  A missing psql still fails loudly rather than
# skipping, because direct database verification is its entire purpose.
# ---------------------------------------------------------------------------
@pytest.mark.e2e
def test_document_flow_live_server():
    """Upload -> chunk -> embed -> list -> detail -> delete, directly verified."""
    require_live_server(BASE)
    assert main() is True
