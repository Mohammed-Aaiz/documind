"""Shared HTTP helpers for the standalone integration-test harnesses.

Owned by the test layer. Used by ``backend/test_*.py``, which drive a live
FastAPI server over HTTP (through the Vite proxy or directly). Deliberately
stdlib-only (``urllib``) so those scripts stay runnable without extra deps.

These helpers perform real network calls against a running server; they are
not usable as unit-test fixtures.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid

DEFAULT_BASE = "http://localhost:3000"


def api_call(method: str, path: str, token: str | None = None,
             body: dict | None = None, base: str = DEFAULT_BASE):
    """Call ``base + path`` and return ``(status, parsed_json_body)``.

    HTTP error responses are returned as ``(status_code, body)`` rather than
    raised, which is what the integration harnesses assert against.
    """
    url = f"{base}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def multipart_upload(url: str, token: str | None, filepath, filename: str):
    """POST a file as ``multipart/form-data`` and return ``(status, body)``.

    ``url`` is the fully-qualified endpoint (not a path).
    """
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
