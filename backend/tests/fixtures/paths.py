"""Canonical filesystem anchors for the test suite.

Several tests inspect production source files (SQL-safety scans, Brain-type
import scans, frontend fabrication scans).  They used to derive those paths with
``Path(__file__).resolve().parent.parent``, which silently pointed at the wrong
directory the moment the suite was split into ``unit/``, ``integration/`` and
``e2e/`` sub-packages.

Derive the anchors once, here, so a future directory move cannot break them
again — and so a broken anchor fails loudly instead of reading the wrong file.

Owned by the test layer; never imported by production code.
"""

from __future__ import annotations

from pathlib import Path

# tests/fixtures/paths.py -> tests/fixtures -> tests -> backend
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent

assert (BACKEND_DIR / "main.py").is_file(), f"backend anchor is wrong: {BACKEND_DIR}"
assert (REPO_ROOT / "src").is_dir(), f"repo-root anchor is wrong: {REPO_ROOT}"
