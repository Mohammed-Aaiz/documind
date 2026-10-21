"""STEP 1.6Z: descriptor-relative deletion helpers, and what they do not close.

These helpers delete relative to an open directory descriptor instead of a
pathname, which is the only way to bind the operation to the object that was
validated rather than to whatever the path resolves to later.

They are POSIX-only at runtime.  On Windows they report ``"unsupported"`` and
touch nothing, so the tests split in two:

* the refusal logic, the platform gate and the "no pathname delete" source
  guarantees run everywhere, including on this Windows host;
* the real deletion and substitution behaviour is guarded by
  :data:`posix_only` and SKIPS with an explicit reason where dir-fd support is
  absent.  A skip is never a pass: the substitution tests are the evidence that
  a POSIX host must produce.

Nothing here touches the real upload tree; every filesystem assertion uses
``tmp_path``.
"""

from __future__ import annotations

import ast
import inspect
import os
import sys
import textwrap
from pathlib import Path

import pytest

_BACKEND_DIR = Path(__file__).resolve().parents[3]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import scripts.cleanup_path as cleanup_path  # noqa: E402

POSIX_REASON = (
    "requires POSIX dir_fd support (os.unlink in os.supports_dir_fd); "
    "not available on Windows"
)
posix_only = pytest.mark.skipif(
    not cleanup_path.POSIX_DIR_FD_SUPPORTED, reason=POSIX_REASON
)


# ---------------------------------------------------------------------------
# Runs everywhere: the platform gate and the refusal logic
# ---------------------------------------------------------------------------


class TestPlatformGate:
    def test_support_flag_is_a_bool_and_false_on_windows(self):
        assert isinstance(cleanup_path.POSIX_DIR_FD_SUPPORTED, bool)
        if os.name == "nt":
            assert cleanup_path.POSIX_DIR_FD_SUPPORTED is False, (
                "Windows must not advertise dir-fd deletion support"
            )

    def test_missing_descriptor_reports_unsupported_and_touches_nothing(self, tmp_path):
        victim = tmp_path / "keep.pdf"
        victim.write_text("keep")
        target_dir = tmp_path / "d"
        target_dir.mkdir()

        assert cleanup_path.unlink_beneath(None, Path("keep.pdf")) == "unsupported"
        assert cleanup_path.rmdir_beneath(None, Path("d")) == "unsupported"
        assert victim.read_text(encoding="utf-8") == "keep"
        assert target_dir.is_dir()
        assert sorted(p.name for p in tmp_path.iterdir()) == ["d", "keep.pdf"]

    def test_close_root_fd_accepts_none_on_every_platform(self, tmp_path):
        # Closing None is always safe, on every platform.
        cleanup_path.close_root_fd(None)

        if not cleanup_path.POSIX_DIR_FD_SUPPORTED:
            assert cleanup_path.open_root_fd(tmp_path) is None

    def test_an_unsupported_platform_reports_none_rather_than_refusing(
        self, monkeypatch, tmp_path
    ):
        """``None`` means *this platform cannot do it*, not *this root failed*.

        The platform gate is forced off, so the only difference from the refusal
        test below is the gate itself.
        """
        monkeypatch.setattr(cleanup_path, "POSIX_DIR_FD_SUPPORTED", False)

        assert cleanup_path.open_root_fd(tmp_path) is None

    def test_an_unholdable_root_on_a_supporting_platform_is_a_refusal(
        self, monkeypatch, tmp_path
    ):
        """STEP 1.6Z (finding B): the two failure modes must not collapse.

        Previously an unopenable root *also* returned ``None``, so a caller fell
        back to a pathname delete exactly when the tree looked wrong -- the root
        swapped for a symlink between validation and this call, a permission
        change, or an I/O error.  On a platform that supports holding the root
        that is now a ``RuntimeError``: the caller must refuse, never retry.
        """
        monkeypatch.setattr(cleanup_path, "POSIX_DIR_FD_SUPPORTED", True)
        monkeypatch.setattr(cleanup_path.os, "O_DIRECTORY", 0o200000, raising=False)
        monkeypatch.setattr(cleanup_path.os, "O_NOFOLLOW", 0o400000, raising=False)

        def _refuse_to_open(*args, **kwargs):
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(cleanup_path.os, "open", _refuse_to_open)

        with pytest.raises(RuntimeError):
            cleanup_path.open_root_fd(tmp_path)

    @posix_only
    def test_a_missing_root_refuses_on_a_supporting_host(self, tmp_path):
        """POSIX-only: the same contract against the real ``os.open``."""
        with pytest.raises(RuntimeError):
            cleanup_path.open_root_fd(tmp_path / "absent")


class TestRelativeValueRefusals:
    """The refusal logic is platform-independent, so it is provable here."""

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "   ",
            ".",
            "..",
            "a/..",
            "../escape.pdf",
            "/etc/passwd",
            "a/../../b",
            "sub/../x",
            "C:drive-relative",
            "//server/share/file",
        ],
    )
    def test_unsafe_values_are_refused(self, value):
        assert cleanup_path._relative_parts(Path(value)) is None, value

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("f.pdf", ("f.pdf",)),
            ("u1/f.pdf", ("u1", "f.pdf")),
            ("./u1//f.pdf", ("u1", "f.pdf")),
            ("a/b/c.pdf", ("a", "b", "c.pdf")),
        ],
    )
    def test_plain_relative_values_split_into_components(self, value, expected):
        assert cleanup_path._relative_parts(Path(value)) == expected


class TestNoPathnameDeleteRemains:
    """A pathname delete would silently reopen the window these close."""

    def _deletion_lines(self, func) -> list[str]:
        return [
            line.strip()
            for line in inspect.getsource(func).splitlines()
            if ".unlink(" in line or ".rmdir(" in line
        ]

    def test_every_deletion_call_is_descriptor_relative(self):
        for func in (cleanup_path.unlink_beneath, cleanup_path.rmdir_beneath):
            lines = self._deletion_lines(func)
            assert lines, f"{func.__name__} should issue its own deletion call"
            for line in lines:
                assert "dir_fd=" in line, (func.__name__, line)
                assert "os.unlink(" in line or "os.rmdir(" in line, (
                    func.__name__,
                    line,
                )

    def test_the_refusal_check_precedes_the_deletion_call(self):
        """The refusal must precede the syscall in the CODE, not in the docstring.

        A plain substring search is not enough here: both helpers document their
        syscall in the docstring (``dir_fd=parent_fd``), which appears before the
        body, so a text-order assertion would pass or fail for the wrong reason.
        This walks the parsed function instead and compares statement lines.
        """
        for func, syscall in (
            (cleanup_path.unlink_beneath, "unlink"),
            (cleanup_path.rmdir_beneath, "rmdir"),
        ):
            tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
            guard = delete = None
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = getattr(node.func, "attr", None) or getattr(
                    node.func, "id", None
                )
                if name == "_relative_parts" and guard is None:
                    guard = node.lineno
                elif name == syscall and delete is None:
                    delete = node.lineno

            assert guard is not None, (
                f"{func.__name__} must validate the relative path"
            )
            assert delete is not None, (
                f"{func.__name__} must issue its own deletion call"
            )
            assert guard < delete, (
                f"{func.__name__} must refuse before it touches the filesystem "
                f"(validation at line {guard}, deletion at line {delete})"
            )

    def test_descent_uses_o_nofollow_and_a_descriptor(self):
        source = inspect.getsource(cleanup_path._descend_to_parent)
        assert "O_NOFOLLOW" in source
        assert "dir_fd=current_fd" in source
        assert "os.dup(" in source, (
            "the caller must always own the returned descriptor"
        )


# ---------------------------------------------------------------------------
# POSIX-only: real deletion and substitution behaviour
# ---------------------------------------------------------------------------


@posix_only
class TestDescriptorRelativeDeletionOnPosix:
    def test_file_beneath_the_root_is_unlinked(self, tmp_path):
        root = tmp_path / "uploads"
        (root / "u1").mkdir(parents=True)
        victim = root / "u1" / "f.pdf"
        victim.write_text("inside", encoding="utf-8")

        fd = cleanup_path.open_root_fd(root)
        assert fd is not None
        try:
            assert cleanup_path.unlink_beneath(fd, Path("u1/f.pdf")) == "unlinked"
        finally:
            cleanup_path.close_root_fd(fd)

        assert not victim.exists()
        assert (root / "u1").is_dir(), "only the named file may be removed"

    def test_unsafe_values_are_refused_and_nothing_changes(self, tmp_path):
        root = tmp_path / "uploads"
        root.mkdir()
        keep = root / "keep.pdf"
        keep.write_text("keep", encoding="utf-8")

        fd = cleanup_path.open_root_fd(root)
        assert fd is not None
        try:
            for value in ("", "..", "../keep.pdf", "/etc/passwd", "u1/../keep.pdf"):
                assert cleanup_path.unlink_beneath(fd, Path(value)) == "refused", value
        finally:
            cleanup_path.close_root_fd(fd)

        assert keep.read_text(encoding="utf-8") == "keep"

    def test_a_symlinked_intermediate_component_is_refused(self, tmp_path):
        root = tmp_path / "uploads"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        secret = outside / "secret.pdf"
        secret.write_text("secret", encoding="utf-8")
        (root / "linked").symlink_to(outside, target_is_directory=True)

        fd = cleanup_path.open_root_fd(root)
        assert fd is not None
        try:
            status = cleanup_path.unlink_beneath(fd, Path("linked/secret.pdf"))
        finally:
            cleanup_path.close_root_fd(fd)

        assert status == "refused", (
            "O_NOFOLLOW on the descent must refuse a symlinked component"
        )
        assert secret.read_text(encoding="utf-8") == "secret"

    def test_parent_swapped_for_a_symlink_after_the_fd_is_opened(self, tmp_path):
        """The core claim: a parent swap cannot redirect the delete out of root."""
        root = tmp_path / "uploads"
        (root / "u1").mkdir(parents=True)
        inside = root / "u1" / "f.pdf"
        inside.write_text("inside", encoding="utf-8")

        outside = tmp_path / "outside"
        outside.mkdir()
        outside_file = outside / "f.pdf"
        outside_file.write_text("outside", encoding="utf-8")

        fd = cleanup_path.open_root_fd(root)
        assert fd is not None
        try:
            moved = root / "u1-original"
            (root / "u1").rename(moved)
            (root / "u1").symlink_to(outside, target_is_directory=True)

            status = cleanup_path.unlink_beneath(fd, Path("u1/f.pdf"))
        finally:
            cleanup_path.close_root_fd(fd)

        assert status in ("unlinked", "refused", "failed")
        assert outside_file.read_text(encoding="utf-8") == "outside", (
            "nothing outside the validated root may ever be deleted"
        )
        assert inside.read_text(encoding="utf-8") == "inside", (
            "the renamed original object must survive when the swap is refused"
        )

    def test_parent_replaced_by_a_real_directory_stays_inside_the_root(self, tmp_path):
        """The documented residual: the final name is not bound to its lstat.

        Replacing a parent with another *real* directory is not something
        O_NOFOLLOW can see, so the held directory is the replacement.  The
        consequence must stay inside the root, and the original object must be
        untouched -- this test pins exactly that bound.
        """
        root = tmp_path / "uploads"
        (root / "u1").mkdir(parents=True)
        (root / "u1" / "f.pdf").write_text("original", encoding="utf-8")

        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "f.pdf").write_text("outside", encoding="utf-8")

        fd = cleanup_path.open_root_fd(root)
        assert fd is not None
        try:
            original = root / "u1"
            moved = root / "u1-original"
            original.rename(moved)
            replacement = root / "u1"
            replacement.mkdir()
            (replacement / "f.pdf").write_text("replacement", encoding="utf-8")

            status = cleanup_path.unlink_beneath(fd, Path("u1/f.pdf"))
        finally:
            cleanup_path.close_root_fd(fd)

        assert status in ("unlinked", "refused", "failed")
        assert (outside / "f.pdf").read_text(encoding="utf-8") == "outside"
        assert (moved / "f.pdf").read_text(encoding="utf-8") == "original"
        if status == "unlinked":
            assert not (replacement / "f.pdf").exists()

    def test_directory_removal_requires_an_empty_directory(self, tmp_path):
        root = tmp_path / "uploads"
        (root / "empty").mkdir(parents=True)
        (root / "full").mkdir()
        (root / "full" / "f.pdf").write_text("x", encoding="utf-8")

        fd = cleanup_path.open_root_fd(root)
        assert fd is not None
        try:
            assert cleanup_path.rmdir_beneath(fd, Path("empty")) == "unlinked"
            assert cleanup_path.rmdir_beneath(fd, Path("full")) == "failed"
        finally:
            cleanup_path.close_root_fd(fd)

        assert not (root / "empty").exists()
        assert (root / "full" / "f.pdf").read_text(encoding="utf-8") == "x"

    def test_a_pathname_delete_is_not_a_fallback(self, tmp_path):
        """An unusable descriptor must not silently degrade to a pathname delete."""
        root = tmp_path / "uploads"
        root.mkdir()
        victim = root / "f.pdf"
        victim.write_text("keep", encoding="utf-8")

        assert cleanup_path.unlink_beneath(None, Path("f.pdf")) == "unsupported"
        assert cleanup_path.unlink_beneath(-1, Path("f.pdf")) in (
            "unsupported",
            "refused",
            "failed",
        )
        assert victim.read_text(encoding="utf-8") == "keep"
