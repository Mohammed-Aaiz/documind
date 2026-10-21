"""Filesystem-isolated safety tests for the ``cleanup_smoke.py`` deletion path.

STEP 1.6X, Workstream C.  ``scripts/cleanup_smoke.py`` deletes the files named by
a user's ``documents.stored_path`` values.  Those values are database rows, not
trusted input, and the script previously passed them straight to an unlink with
no containment check and pruned the per-user directory with
``shutil.rmtree(..., ignore_errors=True)``.

These tests exercise the three hardened helpers directly.  All three take an
already-validated upload root explicitly, so every case below runs against a
``tmp_path`` tree: no database is opened (``cleanup()`` itself is never called),
no settings object is patched, and nothing outside ``tmp_path`` is written or
deleted.

What is asserted is the fail-closed contract:

* a recorded value that escapes the root is refused, never deleted;
* a sibling directory that merely shares a string prefix is not "inside" the
  root (the string-prefix bug the component-wise check exists to prevent);
* a link or reparse point is never followed and never itself a candidate;
* a refusal has no side effect anywhere -- the outside sentinel stays
  byte-identical;
* a prune failure is reported (``False``) instead of being swallowed.

The only skip permitted in this module is the platform-symlink guard in the
link case, and it carries an explicit reason: on Windows without the symlink
privilege the case cannot be constructed, and that must be visible rather than
silently green.
"""

from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

import pytest

# The script is imported from the backend package root: this file lives at
# ``backend/tests/unit/scripts/`` -> parents[3] is ``backend``.
_BACKEND_DIR = Path(__file__).resolve().parents[3]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import scripts.cleanup_smoke as smoke  # noqa: E402

#: The real upload tree.  Nothing here may modify it; the tripwire below proves
#: that, even though these tests only ever pass an explicit ``tmp_path`` root.
REAL_UPLOAD_ROOT = (_BACKEND_DIR / "uploads").resolve()


# ---------------------------------------------------------------------------
# Helpers and fixtures
# ---------------------------------------------------------------------------


def _count_real_uploads() -> int:
    if not REAL_UPLOAD_ROOT.is_dir():
        return 0
    return sum(1 for path in REAL_UPLOAD_ROOT.rglob("*") if path.is_file())


def _make_file_link(link: Path, target: Path) -> None:
    """Create a file symlink, or skip with an explicit, visible reason.

    Creating a file symlink needs a privilege on Windows; without it the case
    cannot be constructed at all, so the absence of coverage is reported rather
    than hidden.
    """
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(
            f"file symlink unavailable on this platform ({type(exc).__name__}: {exc}); "
            "the file-link candidate case is NOT covered on this host"
        )


@pytest.fixture(scope="module", autouse=True)
def real_upload_tree_tripwire():
    """Fail the module if any test changes the real upload tree's file count."""
    before = _count_real_uploads()
    yield
    after = _count_real_uploads()
    assert after == before, f"tests modified the real upload tree: {before} -> {after}"


@pytest.fixture
def upload_root(tmp_path: Path) -> Path:
    """A throwaway upload root, standing in for ``settings.upload_path``."""
    root = tmp_path / "uploads"
    root.mkdir()
    return root


# ---------------------------------------------------------------------------
# resolve_stored_path -- what may be considered at all
# ---------------------------------------------------------------------------


class TestResolveStoredPath:
    def test_relative_uploads_prefixed_value_resolves_inside_root(self, upload_root):
        real = upload_root / "uid" / "x.pdf"
        real.parent.mkdir(parents=True)
        real.write_text("content")

        resolved = smoke.resolve_stored_path("uploads/uid/x.pdf", upload_root)

        assert resolved == upload_root / "uid" / "x.pdf"

    def test_relative_dot_slash_prefixed_value_resolves_inside_root(self, upload_root):
        real = upload_root / "uid" / "x.pdf"
        real.parent.mkdir(parents=True)
        real.write_text("content")

        resolved = smoke.resolve_stored_path("./uploads/uid/x.pdf", upload_root)

        assert resolved == upload_root / "uid" / "x.pdf"

    def test_absolute_value_inside_root_is_accepted(self, upload_root):
        real = upload_root / "uid" / "x.pdf"
        real.parent.mkdir(parents=True)
        real.write_text("content")

        resolved = smoke.resolve_stored_path(str(real), upload_root)

        assert resolved == upload_root / "uid" / "x.pdf"

    def test_missing_path_inside_root_is_returned_for_reporting(self, upload_root):
        """A genuinely absent path inside the root is reported, not refused."""
        resolved = smoke.resolve_stored_path("uploads/ghost/c.pdf", upload_root)

        assert resolved == upload_root / "ghost" / "c.pdf"
        assert not resolved.exists()

    def test_empty_value_is_refused(self, upload_root):
        assert smoke.resolve_stored_path("", upload_root) is None
        assert smoke.resolve_stored_path("   ", upload_root) is None

    def test_absolute_value_outside_root_is_refused(self, tmp_path, upload_root):
        outside = tmp_path / "outside.pdf"
        outside.write_text("do not touch")

        assert smoke.resolve_stored_path(str(outside), upload_root) is None

    def test_traversal_out_of_root_is_refused(self, upload_root):
        assert smoke.resolve_stored_path("../../etc/passwd", upload_root) is None
        assert smoke.resolve_stored_path("uploads/ghost/../../evil.pdf", upload_root) is None

    def test_prefix_sibling_directory_is_refused(self, tmp_path, upload_root):
        """``uploads-old`` is not inside ``uploads``; text prefixes must not count."""
        sibling = tmp_path / "uploads-old"
        sibling.mkdir()
        (sibling / "victim.pdf").write_text("must survive")

        assert smoke.resolve_stored_path(str(sibling / "victim.pdf"), upload_root) is None

    def test_directory_candidate_is_refused(self, upload_root):
        (upload_root / "uid-dir").mkdir()

        assert smoke.resolve_stored_path("uploads/uid-dir", upload_root) is None

    def test_root_itself_is_refused(self, upload_root):
        assert smoke.resolve_stored_path(str(upload_root), upload_root) is None


# ---------------------------------------------------------------------------
# delete_upload_files -- the destructive step
# ---------------------------------------------------------------------------


class TestDeleteUploadFiles:
    def test_mixed_batch_reports_deleted_missing_and_refused(self, tmp_path, upload_root):
        (upload_root / "uid").mkdir(parents=True)
        first = upload_root / "uid" / "a.pdf"
        second = upload_root / "uid" / "b.pdf"
        first.write_text("a")
        second.write_text("b")
        outside = tmp_path / "outside.pdf"
        outside.write_text("do not touch")

        deleted, missing, refused = smoke.delete_upload_files(
            upload_root,
            [
                "uploads/uid/a.pdf",
                "uploads/uid/b.pdf",
                str(outside),
                "uploads/ghost/c.pdf",
            ],
        )

        assert (deleted, missing, refused) == (2, 1, 1)
        assert not first.exists()
        assert not second.exists()
        assert outside.read_text() == "do not touch"

    def test_empty_sequence_is_a_no_op(self, upload_root):
        assert smoke.delete_upload_files(upload_root, []) == (0, 0, 0)

    def test_deletion_and_refusal_counts_are_unchanged(self, tmp_path, upload_root):
        """In-root file deleted, outside value refused -- whichever stage runs.

        Step 1.6Z routes the removal through the descriptor-relative helper on
        POSIX and through the pathname flow elsewhere; this asserts the contract
        that must hold in both cases.
        """
        (upload_root / "uid").mkdir(parents=True)
        inside = upload_root / "uid" / "a.pdf"
        inside.write_text("a")
        outside = tmp_path / "outside.pdf"
        outside.write_text("do not touch")

        assert smoke.delete_upload_files(
            upload_root, ["uploads/uid/a.pdf", str(outside)]
        ) == (1, 0, 1)
        assert not inside.exists()
        assert outside.read_text() == "do not touch"

    def test_file_link_inside_root_is_refused_and_its_target_survives(
        self, tmp_path, upload_root
    ):
        secret = tmp_path / "outside-secret.pdf"
        secret.write_text("must survive")

        link = upload_root / "uid" / "linked.pdf"
        link.parent.mkdir(parents=True)
        _make_file_link(link, secret)

        deleted, missing, refused = smoke.delete_upload_files(upload_root, [str(link)])

        assert (deleted, missing, refused) == (0, 0, 1)
        assert secret.read_text() == "must survive", "a link's target must never be deleted"
        assert link.is_symlink(), "the link is not a deletion candidate"


# ---------------------------------------------------------------------------
# prune_user_dir -- the directory prune
# ---------------------------------------------------------------------------


class TestPruneUserDir:
    def test_empty_directory_inside_root_is_removed(self, upload_root):
        user_dir = upload_root / "uid"
        user_dir.mkdir()

        assert smoke.prune_user_dir(upload_root, "uid") is True
        assert not user_dir.exists()

    def test_non_empty_directory_is_left_intact(self, upload_root):
        user_dir = upload_root / "uid"
        user_dir.mkdir()
        keeper = user_dir / "keeper.pdf"
        keeper.write_text("keep")

        assert smoke.prune_user_dir(upload_root, "uid") is False
        assert keeper.read_text() == "keep"

    def test_directory_outside_root_is_refused(self, tmp_path, upload_root):
        outside = tmp_path / "outside-empty"
        outside.mkdir()

        assert smoke.prune_user_dir(upload_root, "..") is False
        assert outside.is_dir(), "a directory outside the root must never be pruned"

    def test_missing_directory_is_refused(self, upload_root):
        assert smoke.prune_user_dir(upload_root, "never-created") is False


# ---------------------------------------------------------------------------
# Refusal must have no side effect anywhere
# ---------------------------------------------------------------------------


class TestRefusalHasNoSideEffects:
    def test_every_refusal_mode_leaves_the_outside_tree_byte_identical(
        self, tmp_path, upload_root
    ):
        sentinel = tmp_path / "sentinel.txt"
        sentinel.write_text("keep me exactly\n")
        (upload_root / "uid").mkdir(parents=True)
        keeper = upload_root / "uid" / "keeper.pdf"
        keeper.write_text("keep")

        deleted, missing, refused = smoke.delete_upload_files(
            upload_root,
            [
                str(sentinel),                      # absolute, outside the root
                "uploads/ghost/../../evil.pdf",     # traversal out of the root
                "",                                 # unusable value
                str(upload_root),                   # the root itself
                "uploads/uid/../uid/missing.pdf",   # inside, absent
            ],
        )

        assert (deleted, missing, refused) == (0, 1, 4)
        assert sentinel.read_text() == "keep me exactly\n"
        assert keeper.read_text() == "keep"
        assert not (tmp_path / "evil.pdf").exists()


# ---------------------------------------------------------------------------
# Guard order -- root validation precedes every side effect
# ---------------------------------------------------------------------------


class TestGuardOrderInCleanup:
    def test_root_is_validated_before_any_filesystem_side_effect(self):
        """The validated root must be established before deletions and prompts.

        A source-level assertion, in the style of the repository's other
        guard-order tests: ``cleanup()`` is not executable without a database, so
        the order of its statements is what can be checked here.
        """
        source = inspect.getsource(smoke.cleanup)

        guard = source.index("cleanup_path.intended_root")
        delete = source.index("delete_upload_files")
        prompt = source.index("input(")

        assert guard < delete, "the root must be validated before any deletion"
        assert guard < prompt, "the root must be validated before the confirmation prompt"


# ---------------------------------------------------------------------------
# Step 1.6Z -- descriptor-relative deletion wiring (fail closed, never retried)
# ---------------------------------------------------------------------------


class TestDescriptorRelativeDeletion:
    """A declined descriptor-relative delete is a refusal, not a retry.

    The descriptor branch is forced on this (Windows) host by patching
    ``open_root_fd`` to return a sentinel descriptor and ``close_root_fd`` to a
    no-op, so no descriptor that was never opened is ever closed.  The pathname
    helper is patched to fail loudly if the code reaches it at all.
    """

    def test_a_declined_descriptor_delete_never_falls_back_to_pathname(
        self, monkeypatch, upload_root
    ):
        (upload_root / "uid").mkdir(parents=True)
        target = upload_root / "uid" / "x.pdf"
        target.write_text("must survive")

        def _unreachable(*args, **kwargs):
            raise AssertionError("the pathname delete must not be reached")

        monkeypatch.setattr(smoke.cleanup_path, "open_root_fd", lambda root: 0)
        monkeypatch.setattr(
            smoke.cleanup_path, "unlink_beneath", lambda fd, relative: "refused"
        )
        monkeypatch.setattr(smoke.cleanup_path, "close_root_fd", lambda fd: None)
        monkeypatch.setattr(smoke, "delete_upload", _unreachable)

        assert smoke.delete_upload_files(upload_root, ["uploads/uid/x.pdf"]) == (0, 0, 1)
        assert target.read_text() == "must survive"

    def test_a_candidate_not_under_the_held_root_is_refused(
        self, monkeypatch, tmp_path, upload_root
    ):
        """A value that cannot be expressed relative to the root is refused.

        The resolver is stubbed so that an outside path reaches the descriptor
        branch, where ``relative_to`` cannot express it; nothing may be deleted
        by either mechanism.
        """
        outside = tmp_path / "elsewhere.pdf"
        outside.write_text("must survive")

        def _unreachable(*args, **kwargs):
            raise AssertionError("no delete may run for a value outside the root")

        monkeypatch.setattr(smoke.cleanup_path, "open_root_fd", lambda root: 0)
        monkeypatch.setattr(smoke.cleanup_path, "close_root_fd", lambda fd: None)
        monkeypatch.setattr(smoke.cleanup_path, "unlink_beneath", _unreachable)
        monkeypatch.setattr(smoke, "delete_upload", _unreachable)
        monkeypatch.setattr(
            smoke, "resolve_stored_path", lambda value, root: outside
        )

        assert smoke.delete_upload_files(upload_root, ["anything"]) == (0, 0, 1)
        assert outside.read_text() == "must survive"

    @pytest.mark.skipif(
        not smoke.cleanup_path.POSIX_DIR_FD_SUPPORTED,
        reason=(
            "requires POSIX dir_fd support (os.unlink in os.supports_dir_fd); "
            "not available on Windows"
        ),
    )
    def test_descriptor_path_removes_an_in_root_file_and_touches_nothing_else(
        self, tmp_path, upload_root
    ):
        """POSIX-only: the real descriptor-relative removal is exercised."""
        (upload_root / "uid").mkdir(parents=True)
        target = upload_root / "uid" / "z.pdf"
        target.write_text("delete me")
        sentinel = tmp_path / "sentinel.txt"
        sentinel.write_text("keep me exactly\n")

        assert smoke.delete_upload_files(upload_root, ["uploads/uid/z.pdf"]) == (1, 0, 0)
        assert not target.exists()
        assert sentinel.read_text() == "keep me exactly\n"


    def test_an_unholdable_root_refuses_every_candidate(
        self, monkeypatch, upload_root
    ):
        """Finding B: failing to hold the root must not lower the guard.

        ``open_root_fd`` returns ``None`` only where the platform cannot do
        descriptor-relative deletion at all; on a platform that can, a root it
        cannot hold raises.  The helper must then refuse every candidate instead
        of falling through to the pathname flow.
        """
        (upload_root / "uid").mkdir(parents=True)
        target = upload_root / "uid" / "x.pdf"
        target.write_text("must survive")

        def _cannot_hold(root):
            raise RuntimeError("simulated: the root could not be held")

        def _unreachable(*args, **kwargs):
            raise AssertionError("no delete may run after a failed root open")

        monkeypatch.setattr(smoke.cleanup_path, "open_root_fd", _cannot_hold)
        monkeypatch.setattr(smoke, "delete_upload", _unreachable)
        monkeypatch.setattr(smoke.cleanup_path, "unlink_beneath", _unreachable)

        assert smoke.delete_upload_files(upload_root, ["uploads/uid/x.pdf"]) == (0, 0, 1)
        assert target.read_text() == "must survive"

    def test_prune_refuses_an_unholdable_root(self, monkeypatch, upload_root):
        """The prune path refuses for the same reason and removes nothing."""
        (upload_root / "uid").mkdir(parents=True)

        def _cannot_hold(root):
            raise RuntimeError("simulated: the root could not be held")

        monkeypatch.setattr(smoke.cleanup_path, "open_root_fd", _cannot_hold)

        assert smoke.prune_user_dir(upload_root, "uid") is False
        assert (upload_root / "uid").is_dir(), "the directory must survive"


# ---------------------------------------------------------------------------
# Platform capability reporting
# ---------------------------------------------------------------------------


class TestPlatformLinkCapability:
    def test_file_link_capability_is_reported_not_silently_skipped(self, tmp_path):
        link = tmp_path / "capability-link.pdf"
        target = tmp_path / "capability-target.pdf"
        target.write_text("x")

        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            if os.name == "posix":
                pytest.fail(
                    f"symlink support is required on POSIX ({exc}); the safety "
                    "suite must not silently degrade to skips"
                )
            pytest.skip(
                f"no file-symlink privilege on this host ({type(exc).__name__}); "
                "the file-link candidate case is reported, not hidden"
            )

        assert link.is_symlink() is True
