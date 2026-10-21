"""STEP 1.6AB — the transient PDF copy must never decide the parse outcome.

``parse_pdf`` adapts byte input through a ``NamedTemporaryFile`` because the
extractor is path-based.  Removing that copy used to be a bare ``os.unlink`` in a
``finally``, so a cleanup failure — an antivirus scanner or a search indexer
holding the handle is enough on Windows — replaced a *successful* parse with an
exception, and would equally have replaced the extractor's own error.  The
cleanup is now best effort: it is logged rather than silently swallowed, and the
parse outcome is unaffected (``voice.py`` treats its temp audio file the same
way).  The defect was latent rather than user-visible: every production caller
passes a path (``documents/routes.py``), so only the byte-input branch was
exposed.

These tests are the execution evidence for that change and for the cleanup that
was already expected to work.  They monkeypatch ``os.unlink`` for ``.pdf`` paths
only, restore it in a ``finally``, and delete every temporary copy they leave
behind — nothing here touches a repository path or a real upload.

Known residual, recorded not hidden: only ``OSError`` is tolerated, so a
non-``OSError`` raised from ``os.unlink`` would still mask the parse result.
``tmp_path`` is always a ``Path``, so no realistic trigger exists, and widening
the handler would start swallowing programming errors.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

import documents.parser as parser
from documents.parser import ParsedDocument, parse_pdf
from tests.fixtures.pdf_layout import add_text, new_pdf, new_page

_WARNING_LOGGER = "documents.parser"
_WARNING_MESSAGE = "Failed to remove the temporary PDF copy"


def _pdf_bytes() -> bytes:
    doc = new_pdf()
    page = new_page(doc)
    add_text(page, 50, 60, "Pump Specifications", size=16)
    add_text(page, 50, 110, "Pump A delivers 42 L/s.", size=11)
    data = doc.tobytes()
    doc.close()
    return data


def _is_temp_pdf_copy(path) -> bool:
    """True for a transient ``.pdf`` copy: the parser's own temp files only.

    The suffix test is deliberately the whole filter.  Narrowing it further (for
    example to ``tempfile.gettempdir()``) makes the helper depend on the
    interpreter's temp directory staying the same between the parser's call and
    the check, which is not something this test should rely on.  Nothing else in
    these tests unlinks a ``.pdf``.
    """
    try:
        return Path(path).suffix.lower() == ".pdf"
    except TypeError:
        return False


def test_a_failed_temp_copy_unlink_does_not_fail_the_parse(caplog) -> None:
    """A cleanup failure is logged, and the parse still returns its document."""
    real_unlink = os.unlink
    leftovers: list[Path] = []

    def refuse_the_copy(path, *args, **kwargs):
        if _is_temp_pdf_copy(path):
            # Recorded and refused instead of removed, so the leftover can be
            # cleaned up below rather than leaking into the OS temp directory.
            leftovers.append(Path(path))
            raise PermissionError(13, "simulated: the file is held open")
        return real_unlink(path, *args, **kwargs)

    os.unlink = refuse_the_copy
    try:
        with caplog.at_level(logging.WARNING, logger=_WARNING_LOGGER):
            document = parse_pdf(_pdf_bytes())
    finally:
        os.unlink = real_unlink
        for leftover in leftovers:
            try:
                real_unlink(leftover)
            except OSError:  # already gone, or never created
                pass

    assert isinstance(document, ParsedDocument)
    assert document.page_count == 1
    assert document.elements, "the parse must still produce elements"
    assert any(
        record.levelno == logging.WARNING
        and record.name == _WARNING_LOGGER
        and _WARNING_MESSAGE in record.getMessage()
        for record in caplog.records
    ), "the failed cleanup must be logged with its own message, not swallowed"
    assert leftovers, "the test only means something if the copy was refused"


def test_the_temp_copy_is_removed_on_the_success_path() -> None:
    """The cleanup that is expected to work still runs, and runs once."""
    real_unlink = os.unlink
    removed: list[Path] = []

    def recording_unlink(path, *args, **kwargs):
        if _is_temp_pdf_copy(path):
            removed.append(Path(path))
        return real_unlink(path, *args, **kwargs)

    os.unlink = recording_unlink
    try:
        document = parse_pdf(_pdf_bytes())
    finally:
        os.unlink = real_unlink

    assert document.page_count == 1
    assert len(removed) == 1, f"exactly one transient copy is removed, saw {removed}"
    assert not removed[0].exists(), "the transient copy is gone from disk"


def test_extractor_failure_still_propagates_and_the_copy_is_still_removed(
    monkeypatch,
) -> None:
    """A real parse error is not swallowed, and the copy is still cleaned up."""
    real_unlink = os.unlink
    removed: list[Path] = []

    def recording_unlink(path, *args, **kwargs):
        if _is_temp_pdf_copy(path):
            removed.append(Path(path))
        return real_unlink(path, *args, **kwargs)

    def boom(path):
        raise RuntimeError("simulated extractor failure")

    monkeypatch.setattr(parser, "extract_pdf", boom)
    os.unlink = recording_unlink
    try:
        with pytest.raises(RuntimeError, match="simulated extractor failure"):
            parse_pdf(_pdf_bytes())
    finally:
        os.unlink = real_unlink

    assert len(removed) == 1, "the transient copy must still be removed on failure"
    assert not removed[0].exists()
