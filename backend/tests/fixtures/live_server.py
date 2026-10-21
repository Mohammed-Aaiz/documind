"""Live-server helpers for the end-to-end browser harnesses.

The harnesses in ``tests/e2e/browser/`` drive a **real** running server
(React dev proxy on :3000, or the backend directly on :8000) against a real
PostgreSQL database.  They are marked ``e2e`` and must skip themselves — never
pass — when nothing is listening, so that a plain ``pytest -q`` run stays honest.

Owned by the test layer; not part of production.
"""

from __future__ import annotations

import urllib.error
import urllib.request


def server_available(base: str, timeout: float = 1.5) -> bool:
    """True when something answers ``GET {base}/api/health``.

    Any HTTP response (including an error status) means a server is listening.
    Connection failures and timeouts mean it is not.
    """
    try:
        urllib.request.urlopen(f"{base}/api/health", timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def require_live_server(base: str) -> None:
    """``pytest.skip`` unless a live server answers at ``base``."""
    import pytest

    if not server_available(base):
        pytest.skip(f"live server not reachable at {base} (e2e harness)")


def optional_import(module: str, *, reason: str = ""):
    """Import an optional e2e dependency or skip the test.

    ``playwright`` and friends are not part of ``requirements.txt``; a missing
    optional dependency must produce a skip, not a collection error.
    """
    import importlib

    import pytest

    try:
        return importlib.import_module(module)
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"{module} unavailable: {exc}" + (f" ({reason})" if reason else ""))
