"""Checkout reproducibility for the frozen benchmark — the bytes, not the numbers.

A pinned benchmark digest is only meaningful if the bytes survive the trip
through Git.  ``qa_benchmark_v1.jsonl`` is pinned at
``1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0``, which is
the digest of its **CRLF** rendition, while this repository is checked out with
``core.autocrlf=true``.  Without an explicit ``-text`` rule ``git add`` stores
the LF rendition, and a Linux checkout then hashes ``5dff5aaa…`` even though
nobody touched the file.

These tests pin the attribute rule, and the trap that lets the rule be lost
silently: a CRLF-converted ``.gitattributes`` keeps the trailing ``\\r`` as part
of the pattern, so every rule inside it stops matching.  The file therefore
pins itself as well.
"""

from __future__ import annotations

from pathlib import Path

from evaluation import artifacts

#: ``backend/tests/unit/evaluation/<this file>`` -> ``backend/tests/unit`` ->
#: ``backend/tests`` -> ``backend`` -> repository root.
REPO_ROOT = Path(__file__).resolve().parents[4]
ATTRIBUTES = REPO_ROOT / ".gitattributes"

BENCHMARK = "backend/phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl"
BENCHMARK_RULE = f"{BENCHMARK} -text"
SELF_RULE = ".gitattributes -text"


def _rules() -> list[str]:
    """The effective (non-comment, non-blank) rules, read as text."""
    return [
        line
        for line in ATTRIBUTES.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_the_benchmark_is_declared_binary_for_filtering_purposes():
    assert ATTRIBUTES.is_file(), (
        "the repository has no .gitattributes, so the CRLF-pinned benchmark "
        "digest cannot survive a checkout on another platform"
    )

    assert BENCHMARK_RULE in _rules()


def test_the_attributes_file_pins_itself():
    """A converted attributes file stops matching — so it must not convert."""
    assert SELF_RULE in _rules()

    raw = ATTRIBUTES.read_bytes()
    assert b"\r" not in raw, (
        "the attributes file contains CR bytes; git keeps a trailing \\r in the "
        "pattern, which silently disables every rule in it"
    )


def test_the_loader_resolves_exactly_that_path():
    """The pinned attribute must describe the file the loader actually opens."""
    expected = (REPO_ROOT / BENCHMARK).resolve()

    assert Path(artifacts.FROZEN_BENCHMARK).resolve() == expected
    assert expected.is_file(), f"the frozen benchmark is missing at {expected}"
