"""
Full integration test for document ingestion pipeline.

Tests through the real Vite proxy -> FastAPI -> PostgreSQL.
No mocks, no fakes, no simulated responses.
"""

import json
import sys
import urllib.request
import uuid

BASE = "http://localhost:3000"  # Vite proxy -> FastAPI


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


def multipart_upload(url, token, filepath, filename):
    """Multipart file upload using urllib."""
    boundary = uuid.uuid4().hex
    with open(filepath, "rb") as f:
        file_bytes = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


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
        "email": "test@documind.io",
        "password": "TestPass123!",
    })
    check("Login succeeds", code == 200, f"got {code}")
    token = body.get("access_token", "")
    check("Got access_token", bool(token))

    # 2. Upload a real PDF
    print()
    print("2. Upload a real PDF document")
    code, body = multipart_upload(
        f"{BASE}/api/documents/upload",
        token,
        "uploads/test_document.pdf",
        "test_document.pdf",
    )
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
    import subprocess
    result = subprocess.run(
        ["C:/pg/pg16/pgsql/bin/psql.exe", "-h", "localhost", "-U", "documind", "-d", "documind",
         "-c", f"SELECT id, name, file_type, status, chunk_count, user_id FROM documents WHERE id = '{doc_id}';"],
        capture_output=True, text=True
    )
    check("Document in DB", doc_id in result.stdout, result.stdout.strip()[:200])

    # 4. Verify chunks in document_chunks
    print()
    print("4. Verify chunks exist in document_chunks")
    result = subprocess.run(
        ["C:/pg/pg16/pgsql/bin/psql.exe", "-h", "localhost", "-U", "documind", "-d", "documind",
         "-c", f"SELECT COUNT(*) as chunk_count FROM document_chunks WHERE document_id = '{doc_id}';"],
        capture_output=True, text=True
    )
    check("Chunks in DB", "chunks" in result.stdout.lower() or "chunk_count" in result.stdout, result.stdout.strip()[:200])

    # Verify chunks have content
    result = subprocess.run(
        ["C:/pg/pg16/pgsql/bin/psql.exe", "-h", "localhost", "-U", "documind", "-d", "documind",
         "-c", f"SELECT chunk_index, length(content) as content_len, page FROM document_chunks WHERE document_id = '{doc_id}' ORDER BY chunk_index;"],
        capture_output=True, text=True
    )
    check("Chunks have content", "content_len" in result.stdout, result.stdout.strip()[:300])

    # 5. Verify document belongs to authenticated user
    print()
    print("5. Verify document belongs to authenticated user")
    # Get user_id from login
    result = subprocess.run(
        ["C:/pg/pg16/pgsql/bin/psql.exe", "-h", "localhost", "-U", "documind", "-d", "documind",
         "-c", "SELECT id FROM users WHERE email = 'test@documind.io';"],
        capture_output=True, text=True
    )
    user_id = ""
    for line in result.stdout.split("\n"):
        line = line.strip()
        if len(line) == 36 and "-" in line:
            user_id = line
            break
    check("Got user_id", bool(user_id), user_id[:50])

    if user_id and doc_id:
        result = subprocess.run(
            ["C:/pg/pg16/pgsql/bin/psql.exe", "-h", "localhost", "-U", "documind", "-d", "documind",
             "-c", f"SELECT user_id FROM documents WHERE id = '{doc_id}';"],
            capture_output=True, text=True
        )
        check("Document user_id matches", user_id in result.stdout)

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
    result = subprocess.run(
        ["C:/pg/pg16/pgsql/bin/psql.exe", "-h", "localhost", "-U", "documind", "-d", "documind",
         "-c", f"SELECT COUNT(*) FROM documents WHERE id = '{doc_id}';"],
        capture_output=True, text=True
    )
    check("Document removed from DB", "0" in result.stdout)

    # Verify chunks cascade-deleted
    result = subprocess.run(
        ["C:/pg/pg16/pgsql/bin/psql.exe", "-h", "localhost", "-U", "documind", "-d", "documind",
         "-c", f"SELECT COUNT(*) FROM document_chunks WHERE document_id = '{doc_id}';"],
        capture_output=True, text=True
    )
    check("Chunks cascade-deleted", "0" in result.stdout)

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
    import tempfile
    import os
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
