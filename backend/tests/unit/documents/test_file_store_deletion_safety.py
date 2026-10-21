"""STEP 1.6X: deletion containment for ``storage.file_store.delete_upload``.

``delete_upload`` is the shared helper the application uses to remove a stored
upload (``documents/routes.py::delete_document``) and that
``scripts/cleanup_smoke.py`` calls after it has validated a root.  Before the
STEP 1.6X remediation its body was ``if stored_path.exists(): unlink()`` -- no
containment check at all -- so a caller-supplied or corrupted ``stored_path``
could delete a file anywhere on the machine.

These tests pin the guard that replaced it: a deletion succeeds only for a
regular file that resolves inside the root, and every escape route -- an
absolute path outside the root, a sibling that merely shares a string prefix,
``..`` traversal, a symlink to an outside file, a directory, a missing path --
is refused without touching anything.  A refusal must be a ``False`` return,
never an exception and never a partial deletion.

Everything runs inside ``tmp_path``; no test here points at a real upload tree.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from storage import file_store

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: bytes) -> Path:
    """Create ``path`` (and its parents) with ``content`` and return it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _symlink_or_skip(link: Path, target: Path) -> None:
    """Create a symlink, skipping the test when the platform refuses.

    Windows needs either Developer Mode or elevation to create one, so the
    skip is a genuine platform limitation rather than a hidden failure.
    """
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError) as exc:  # pragma: no cover - platform
        pytest.skip(f"this platform cannot create a symlink here: {exc!r}")


# ---------------------------------------------------------------------------
# The property the guard exists for: a real upload inside the root is deleted
# ---------------------------------------------------------------------------


class TestDeletionInsideTheRoot:
    def test_regular_file_inside_root_is_deleted(self, tmp_path):
        target = _write(tmp_path / "user-1" / "f.txt", b"payload")

        assert file_store.delete_upload(target, root=tmp_path) is True
        assert not target.exists()

    def test_only_the_named_file_is_removed(self, tmp_path):
        target = _write(tmp_path / "user-1" / "f.txt", b"payload")
        neighbour = _write(tmp_path / "user-1" / "keep.txt", b"neighbour")

        assert file_store.delete_upload(target, root=tmp_path) is True

        assert not target.exists()
        assert neighbour.exists()
        assert neighbour.read_bytes() == b"neighbour"

    def test_nested_path_inside_root_is_deleted(self, tmp_path):
        target = _write(tmp_path / "a" / "b" / "c" / "f.txt", b"deep")

        assert file_store.delete_upload(target, root=tmp_path) is True
        assert not target.exists()


# ---------------------------------------------------------------------------
# Every escape route is refused, and nothing is touched
# ---------------------------------------------------------------------------


class TestRefusals:
    def test_sibling_sharing_a_string_prefix_is_refused(self, tmp_path):
        """``uploads`` must not authorise deleting from ``uploads-old``.

        A string-prefix comparison would accept this; component-wise
        containment must not.
        """
        root = tmp_path / "uploads"
        root.mkdir()
        outside = _write(tmp_path / "uploads-old" / "f.txt", b"keep me")

        assert file_store.delete_upload(outside, root=root) is False
        assert outside.read_bytes() == b"keep me"

    def test_absolute_path_outside_root_is_refused(self, tmp_path):
        root = tmp_path / "uploads"
        root.mkdir()
        outside = _write(tmp_path / "elsewhere" / "f.txt", b"keep me")

        assert file_store.delete_upload(outside, root=root) is False
        assert outside.read_bytes() == b"keep me"

    def test_traversal_out_of_the_root_is_refused(self, tmp_path):
        root = tmp_path / "uploads"
        root.mkdir()
        outside = _write(tmp_path / "outside.txt", b"keep me")

        assert file_store.delete_upload(root / ".." / "outside.txt", root=root) is False
        assert outside.read_bytes() == b"keep me"

    def test_symlink_inside_root_is_refused_and_target_survives(self, tmp_path):
        root = tmp_path / "uploads"
        root.mkdir()
        target = _write(tmp_path / "victim.txt", b"keep me")
        link = root / "link.txt"
        _symlink_or_skip(link, target)

        assert file_store.delete_upload(link, root=root) is False
        assert target.read_bytes() == b"keep me"

    def test_directory_at_the_candidate_path_is_refused(self, tmp_path):
        root = tmp_path / "uploads"
        directory = root / "user-1"
        directory.mkdir(parents=True)

        assert file_store.delete_upload(directory, root=root) is False
        assert directory.is_dir()

    def test_missing_file_returns_false_without_raising(self, tmp_path):
        root = tmp_path / "uploads"
        root.mkdir()

        assert file_store.delete_upload(root / "user-1" / "missing.txt", root=root) is False

    def test_refusal_is_a_false_return_not_an_exception(self, tmp_path):
        """Refusing must never raise and must never delete anything."""
        root = tmp_path / "uploads"
        root.mkdir()
        sentinels = {
            _write(tmp_path / "uploads-old" / "a.txt", b"a"): b"a",
            _write(tmp_path / "outside.txt", b"b"): b"b",
        }

        (root / "user-1").mkdir()
        refusing_inputs = [
            tmp_path / "uploads-old" / "a.txt",
            root / ".." / "outside.txt",
            root / "no-such-file.txt",
            root / "user-1",
        ]

        for candidate in refusing_inputs:
            assert file_store.delete_upload(candidate, root=root) is False, candidate

        for sentinel, content in sentinels.items():
            assert sentinel.read_bytes() == content, sentinel


# ---------------------------------------------------------------------------
# The default root: settings.upload_path when no root is passed
# ---------------------------------------------------------------------------


class TestDefaultRoot:
    def test_configured_root_is_used_when_root_is_omitted(self, tmp_path, monkeypatch):
        """The positional call in ``documents/routes.py`` keeps its contract."""
        root = tmp_path / "uploads"
        root.mkdir()
        monkeypatch.setattr(file_store, "settings", SimpleNamespace(upload_path=root))
        inside = _write(root / "user-1" / "f.txt", b"payload")
        outside = _write(tmp_path / "not-ours.txt", b"keep me")

        assert file_store.delete_upload(inside) is True
        assert not inside.exists()

        assert file_store.delete_upload(outside) is False
        assert outside.read_bytes() == b"keep me"

    def test_explicit_root_overrides_the_configured_one(self, tmp_path, monkeypatch):
        """``cleanup_smoke`` passes the root it already validated."""
        configured = tmp_path / "configured"
        configured.mkdir()
        monkeypatch.setattr(
            file_store, "settings", SimpleNamespace(upload_path=configured)
        )
        validated_root = tmp_path / "validated"
        target = _write(validated_root / "user-1" / "f.txt", b"payload")

        assert file_store.delete_upload(target, root=validated_root) is True
        assert not target.exists()
