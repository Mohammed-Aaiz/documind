"""Reparse-point, normalization and substitution tests for the deletion policy.

STEP 1.6Y, Workstreams B and C.  The symlink refusal branches could not be
exercised on this host because creating a symlink needs a Windows privilege the
test account does not hold (``WinError 1314``).  Two things close as much of
that gap as the platform allows without weakening anything:

* **NTFS junctions need no elevation.**  On Windows a junction exercises the
  same reparse-point code path the symlink tests would
  (``cleanup_path.is_link_or_reparse_point`` reads the
  ``FILE_ATTRIBUTE_REPARSE_POINT`` bit precisely because
  ``Path.is_symlink()`` returns ``False`` for a junction), so the branch is
  covered here on a host where symlinks cannot be created at all.
* **Substitution tests** replace a candidate, or the root itself, *after* it has
  been validated, and assert that the specific substitution is refused.

What this module deliberately does **not** claim: deletion is race-free.  The
general check-then-use window between validating a path and calling
``unlink()``/``rmdir()`` remains OPEN — Python exposes no handle-bound
``unlink``/``rmdir`` on Windows, and no POSIX runner is available in this
repository (WSL is not installed and there is no CI configuration).  The tests
below prove that the substitutions they perform are refused; they are not
evidence of race-freedom.

Already covered elsewhere, and therefore not repeated here:
``test_cleanup_smoke_safety.py`` covers traversal, absolute-outside values,
adjacent shared-prefix directories, missing paths, non-regular candidates, the
root-as-candidate, prune refusals, refusal-without-side-effect, guard order, and
a file-symlink candidate (privilege-guarded); ``test_cleanup_orphan_uploads.py``
covers the orphan sweep including archive handling and symlinked roots;
``test_file_store_deletion_safety.py`` covers the application helper's
containment, prefix-sibling, traversal, directory, missing and symlink cases.

Every test works inside ``tmp_path``; nothing here touches the real
``backend/uploads/`` tree.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

# This file lives at ``backend/tests/unit/scripts/`` -> parents[3] is ``backend``.
_BACKEND_DIR = Path(__file__).resolve().parents[3]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import scripts.cleanup_path as cleanup_path  # noqa: E402
import scripts.cleanup_smoke as smoke  # noqa: E402
from storage import file_store  # noqa: E402

WINDOWS_ONLY = pytest.mark.skipif(
    sys.platform != "win32",
    reason=(
        "NTFS junctions are Windows-only, and this repository has no POSIX CI "
        "runner (WSL is not installed); the junction branch is NOT covered here"
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _upload_root(tmp_path: Path) -> Path:
    """A throwaway upload root, standing in for ``settings.upload_path``."""
    root = tmp_path / "uploads"
    root.mkdir()
    return root


def _make_junction(link: Path, target: Path) -> None:
    """Create an NTFS junction, or skip naming the actual failure.

    A junction needs no elevation, unlike a symlink, so this is how the
    reparse-point branch is reached on a host without the symlink privilege.
    """
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, tmp_path only
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
        )
    except OSError as exc:  # cmd unavailable
        pytest.skip(f"could not run mklink, junctions unavailable here: {exc!r}")

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        pytest.skip(f"mklink /J failed (rc={result.returncode}): {detail!r}")


def _make_directory_link(link: Path, target: Path) -> None:
    """Point ``link`` at directory ``target``: junction on Windows, symlink otherwise.

    Skips with an explicit reason when the platform cannot make either, so an
    unexercised branch is visible rather than silently green.
    """
    if os.name == "nt":
        _make_junction(link, target)
        return
    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(
            f"cannot create a directory symlink here ({type(exc).__name__}: {exc}); "
            "the symlink branch is NOT covered on this host"
        )


# ---------------------------------------------------------------------------
# Windows reparse points (unprivileged junctions)
# ---------------------------------------------------------------------------


@WINDOWS_ONLY
class TestWindowsReparsePoints:
    def test_junction_is_seen_as_a_reparse_point(self, tmp_path):
        target = tmp_path / "real-target"
        target.mkdir()
        link = tmp_path / "junction"
        _make_junction(link, target)

        assert cleanup_path.is_link_or_reparse_point(link) is True

    def test_junction_candidate_is_refused_by_validate_candidate(self, tmp_path):
        root = _upload_root(tmp_path)
        target = tmp_path / "outside-dir"
        target.mkdir()
        link = root / "linked-dir"
        _make_junction(link, target)

        assert cleanup_path.validate_candidate(root, link, expect="directory") is False

    def test_junction_as_upload_root_is_refused(self, tmp_path):
        real_root = tmp_path / "real-uploads"
        real_root.mkdir()
        link = tmp_path / "uploads"
        _make_junction(link, real_root)

        with pytest.raises(RuntimeError):
            cleanup_path.intended_root(link)
        with pytest.raises(RuntimeError):
            cleanup_path.forbid_symlink_roots(link)

    def test_file_reached_through_a_junction_is_refused_by_delete_upload(self, tmp_path):
        root = _upload_root(tmp_path)
        outside = tmp_path / "outside-dir"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("must survive")

        link = root / "linked-dir"
        _make_junction(link, outside)

        assert file_store.delete_upload(link / "secret.txt", root=root) is False
        assert secret.read_text() == "must survive"

    def test_junction_replacing_a_regular_file_is_refused(self, tmp_path):
        root = _upload_root(tmp_path)
        outside = tmp_path / "outside-dir"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("must survive")

        candidate = root / "victim.txt"
        candidate.write_text("the legitimate upload")
        # It was a legitimate candidate before the substitution.
        assert cleanup_path.validate_candidate(root, candidate, expect="file") is True

        candidate.unlink()
        _make_junction(candidate, outside)

        assert file_store.delete_upload(candidate, root=root) is False
        assert secret.read_text() == "must survive"

    def test_substituted_candidate_is_refused_and_reported(self, tmp_path):
        root = _upload_root(tmp_path)
        user_dir = root / "uid"
        user_dir.mkdir()
        outside = tmp_path / "outside-dir"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("must survive")

        candidate = user_dir / "a.pdf"
        candidate.write_text("a")
        assert cleanup_path.validate_candidate(root, candidate, expect="file") is True

        candidate.unlink()
        _make_junction(candidate, outside)

        deleted, missing, refused = smoke.delete_upload_files(root, ["uploads/uid/a.pdf"])

        assert (deleted, missing, refused) == (0, 0, 1)
        assert secret.read_text() == "must survive"

    def test_replaced_root_is_refused_by_the_root_gate(self, tmp_path):
        real_root = _upload_root(tmp_path)
        (real_root / "f.txt").write_text("x")
        assert cleanup_path.intended_root(real_root) == real_root.resolve()

        # Swap the validated root for a link to a different tree.
        (real_root / "f.txt").unlink()
        real_root.rmdir()
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "f.txt").write_text("x")
        _make_junction(real_root, elsewhere)

        with pytest.raises(RuntimeError):
            cleanup_path.intended_root(real_root)


# ---------------------------------------------------------------------------
# Directory symlinks (needs the symlink privilege on Windows)
# ---------------------------------------------------------------------------


class TestDirectorySymlinksPortable:
    def test_directory_symlink_candidate_is_refused(self, tmp_path):
        root = _upload_root(tmp_path)
        target = tmp_path / "outside-dir"
        target.mkdir()
        link = root / "linked-dir"
        _make_directory_link(link, target)

        assert cleanup_path.validate_candidate(root, link, expect="directory") is False

    def test_symlinked_upload_root_is_refused(self, tmp_path):
        real_root = tmp_path / "real-uploads"
        real_root.mkdir()
        link = tmp_path / "uploads"
        _make_directory_link(link, real_root)

        with pytest.raises(RuntimeError):
            cleanup_path.intended_root(link)

    def test_file_under_a_linked_directory_is_refused_by_delete_upload(self, tmp_path):
        root = _upload_root(tmp_path)
        outside = tmp_path / "outside-dir"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("must survive")

        link = root / "linked-dir"
        _make_directory_link(link, outside)

        assert file_store.delete_upload(link / "secret.txt", root=root) is False
        assert secret.read_text() == "must survive"


# ---------------------------------------------------------------------------
# `..` normalization audit of cleanup_path.py
# ---------------------------------------------------------------------------
#
# ``os.path.abspath``/``normpath`` collapse ``..`` textually and are not
# symlink-aware.  The audit question is whether that lets a ``..`` component
# step out of the sequence ``_has_link_ancestor`` inspects, so that a candidate
# outside the root is accepted or an interior link is skipped.  The tests below
# are the attempts; each one refused or was contained, so no defect was
# reproduced and ``cleanup_path.py`` was left unchanged.


class TestDotDotNormalizationAudit:
    def test_dotdot_candidate_that_resolves_inside_the_root_is_contained(self, tmp_path):
        """A ``..`` that lands back inside names a real in-root file: contained.

        Containment is decided on the *resolved* path, and the file this names
        really is inside the root, so accepting it is the correct outcome (it is
        not a bypass).
        """
        root = _upload_root(tmp_path)
        (root / "sub").mkdir()
        target = root / "x.pdf"
        target.write_text("content")

        assert cleanup_path.validate_candidate(
            root, root / "sub" / ".." / "x.pdf", expect="file"
        ) is True

    def test_dotdot_candidate_that_resolves_outside_is_refused(self, tmp_path):
        root = _upload_root(tmp_path)
        (root / "sub").mkdir()
        victim = tmp_path / "victim.txt"
        victim.write_text("must survive")

        candidate = root / "sub" / ".." / ".." / "victim.txt"

        assert cleanup_path.is_under(root, candidate) is False
        assert cleanup_path.validate_candidate(root, candidate, expect="file") is False

    def test_interior_link_behind_a_dotdot_is_still_seen(self, tmp_path):
        """The lexical walk visits the real prefix paths, ``..`` or not."""
        root = _upload_root(tmp_path)
        (root / "sub").mkdir()
        real = root / "real"
        real.mkdir()
        (real / "f.pdf").write_text("content")
        link = root / "linkdir"
        _make_directory_link(link, real)

        candidate = root / "sub" / ".." / "linkdir" / "f.pdf"

        # The resolved candidate is inside the root, so containment alone would
        # accept it; the interior link is what must refuse it.
        assert cleanup_path.is_under(root, candidate) is True
        assert cleanup_path._has_link_ancestor(root, candidate) is True
        assert cleanup_path.validate_candidate(root, candidate, expect="file") is False

    def test_interior_link_behind_a_dotdot_is_seen_even_when_it_stays_inside(self, tmp_path):
        """A link that redirects *within* the root is refused as well."""
        root = _upload_root(tmp_path)
        (root / "sub").mkdir()
        real = root / "real"
        real.mkdir()
        (real / "f.pdf").write_text("content")
        link = root / "linkdir"
        _make_directory_link(link, real)

        candidate = root / "linkdir" / ".." / "sub" / "f.pdf"
        (root / "sub" / "f.pdf").write_text("content")

        assert cleanup_path._has_link_ancestor(root, candidate) is True
        assert cleanup_path.validate_candidate(root, candidate, expect="file") is False

    def test_is_under_rejects_a_dotdot_escape(self, tmp_path):
        root = _upload_root(tmp_path)
        (root / "sub").mkdir()

        assert cleanup_path.is_under(root, root / "sub" / "..") is True
        assert cleanup_path.is_under(root, root / "..") is False

    def test_link_ancestor_walk_fails_closed_for_a_candidate_outside_the_root(self, tmp_path):
        root = _upload_root(tmp_path)
        outside = tmp_path / "outside.txt"
        outside.write_text("must survive")

        # Not lexically under the root -> the walk must refuse, not crash.
        assert cleanup_path._has_link_ancestor(root, outside) is True

    def test_application_helper_refuses_a_raw_parent_reference(self, tmp_path):
        """The app helper is stricter than the resolved check on purpose.

        ``storage.file_store.delete_upload`` refuses any raw ``..`` component
        even when the path would resolve inside the root, so the refusal cannot
        depend on resolution order or on ``abspath`` collapsing the component
        list the lexical walk inspects.
        """
        root = _upload_root(tmp_path)
        (root / "sub").mkdir()
        target = root / "x.pdf"
        target.write_text("content")

        assert file_store.delete_upload(root / "sub" / ".." / "x.pdf", root=root) is False
        assert target.read_text() == "content"

    def test_dotdot_candidate_is_refused_by_the_smoke_deletion_path(self, tmp_path):
        root = _upload_root(tmp_path)
        (root / "sub").mkdir()
        victim = tmp_path / "victim.pdf"
        victim.write_text("must survive")

        deleted, missing, refused = smoke.delete_upload_files(
            root, ["sub/../../victim.pdf"]
        )

        assert (deleted, missing, refused) == (0, 0, 1)
        assert victim.read_text() == "must survive"


# ---------------------------------------------------------------------------
# Substitution after validation: what is refused, and what is not claimed
# ---------------------------------------------------------------------------


class TestSubstitutionIsRefused:
    def test_candidate_swapped_for_a_link_after_validation_is_refused(self, tmp_path):
        root = _upload_root(tmp_path)
        outside = tmp_path / "outside-dir"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("must survive")

        candidate = root / "a.pdf"
        candidate.write_text("a")
        assert cleanup_path.validate_candidate(root, candidate, expect="file") is True

        candidate.unlink()
        _make_directory_link(candidate, outside)

        assert file_store.delete_upload(candidate, root=root) is False
        assert secret.read_text() == "must survive"

    def test_validated_file_replaced_by_a_directory_is_refused(self, tmp_path):
        root = _upload_root(tmp_path)
        candidate = root / "b.pdf"
        candidate.write_text("b")
        assert cleanup_path.validate_candidate(root, candidate, expect="file") is True

        candidate.unlink()
        candidate.mkdir()

        assert file_store.delete_upload(candidate, root=root) is False
        assert candidate.is_dir()

    def test_root_gate_refuses_a_root_swapped_after_validation(self, tmp_path):
        """A root replaced after it was validated is caught when the gate re-runs.

        The gate is ``cleanup_path.intended_root``; ``cleanup()`` calls it before
        any filesystem side effect (asserted by
        ``test_cleanup_smoke_safety.py::TestGuardOrderInCleanup``).  A root
        swapped *between* that call and the deletion is the residual window and
        is explicitly NOT claimed to be closed.
        """
        real_root = _upload_root(tmp_path)
        (real_root / "f.txt").write_text("x")
        assert cleanup_path.intended_root(real_root) == real_root.resolve()

        (real_root / "f.txt").unlink()
        real_root.rmdir()
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "f.txt").write_text("x")
        _make_directory_link(real_root, elsewhere)

        with pytest.raises(RuntimeError):
            cleanup_path.forbid_symlink_roots(real_root)

    def test_residual_check_then_use_window_is_documented(self):
        """The platform limitation is recorded, not described as fixed.

        A guard against an honesty statement being deleted, not a claim that the
        window is closed: both modules must keep documenting that validation and
        the destructive syscall are separate operations.
        """
        assert "check-then-use" in cleanup_path.__doc__
        assert "check-then-use" in file_store.delete_upload.__doc__
