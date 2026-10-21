"""Database-free and filesystem-isolated tests for ``cleanup_orphan_uploads.py``.

These tests fixture a real upload tree and a real ``.env``, but they never touch
a PostgreSQL database and they never delete anything outside the fixture
directory.  They assert the fail-closed behaviour: the script aborts when the DB
reference set is unreadable, ignores unlinked DB references, refuses to write
archive files back into the upload tree, refuses an unsafe (symlinked or
reparse-point) upload root before anything is archived or deleted, never follows
links out of the tree, and re-validates every deletion and prune candidate.

Exit codes are *returned* by ``run_sweep``; only ``main()`` converts them into
``SystemExit``.  These tests assert the returned codes directly.

CRITICAL ISOLATION NOTE
=======================
``config.get_settings`` is ``lru_cache``-wrapped, so it is a C-level wrapper
object with no instance dictionary: ``monkeypatch.setattr(get_settings,
"upload_path", ...)`` raises ``AttributeError`` and can never retarget the
sweep.  An earlier revision of this module did exactly that, which is why the
suite could not run at all.  Patching the cached ``Settings`` *instance* would
retarget the sweep at whatever that patch names -- including the real
``backend/uploads`` tree.  These tests therefore replace the module global
``orphan.settings``, an autouse fixture refuses to run with the real tree as the
active root, and a session tripwire fails the run if the real tree's file count
changes.

No production file or other checkout path is deleted.  No runner, migration, or
integration test is executed.
"""

from __future__ import annotations

import builtins
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

# The script is imported from the backend package root, so make sure that is on
# the path for this test module only.  This file lives at
# ``backend/tests/unit/scripts/`` -> parents[3] is ``backend``.
_BACKEND_DIR = Path(__file__).resolve().parents[3]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import scripts.cleanup_orphan_uploads as orphan  # noqa: E402
import scripts.cleanup_path as cleanup_path  # noqa: E402
from config import get_settings  # noqa: E402

DATABASE_URL = "postgresql+asyncpg://u:p@localhost:5432/db"

#: The real upload tree this suite must never modify.
REAL_UPLOAD_ROOT = (_BACKEND_DIR / "uploads").resolve()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeSettings:
    """Stand in for the cached ``Settings`` instance the script holds."""

    def __init__(self, upload_path: Path, database_url: str):
        self.upload_path = upload_path
        self.database_url = database_url

    def __repr__(self):
        return f"FakeSettings(upload={self.upload_path!r}, database={self.database_url!r})"


class _DBReferenceUnavailable(Exception):
    """Used to simulate unreadable database references."""


class _SessionRaises:
    """Minimal async context manager that raises on ``__aenter__``."""

    def __init__(self, exception_factory):
        self.exception_factory = exception_factory

    async def __aenter__(self):
        raise self.exception_factory()

    async def __aexit__(self, *args):
        return False


def _seed_root(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "user-1").mkdir(parents=True, exist_ok=True)
    (root / "user-2").mkdir(parents=True, exist_ok=True)
    (root / "user-1" / "report.pdf").write_text("keep this")
    (root / "user-1" / "notes.txt").write_text("keep this")
    (root / "user-1" / "orphan.pdf").write_text("should be flagged")
    (root / "user-2" / "other.pdf").write_text("different owner")
    return root


SEEDED_REFERENCES = {"user-1/report.pdf", "user-1/notes.txt", "user-2/other.pdf"}


def _all_keys(root: Path) -> set[str]:
    return {orphan._key(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


def _make_dir_link(link: Path, target: Path) -> str:
    """Create a directory link, returning the mechanism used.

    Prefers ``symlink_to``.  On Windows without the symlink privilege, falls
    back to an NTFS junction (``mklink /J``), which is a reparse point and is
    *not* reported by ``Path.is_symlink()`` -- exactly the case the guard must
    still catch.  Skips with an explicit reason only if both are unavailable.
    """
    try:
        link.symlink_to(target, target_is_directory=True)
        return "symlink"
    except (OSError, NotImplementedError):
        pass

    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and link.exists():
            return "junction"

    pytest.skip(
        "no directory-link mechanism available (symlink privilege missing and "
        "junction creation failed); the essential link-root regression case is "
        "NOT covered on this host"
    )


def _make_file_link(link: Path, target: Path) -> None:
    """Create a file symlink or skip with an explicit reason."""
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(
            f"file symlink unavailable on this platform ({type(exc).__name__}: {exc}); "
            "the file-link candidate case is NOT covered on this host"
        )


def _count_real_uploads() -> int:
    if not REAL_UPLOAD_ROOT.is_dir():
        return 0
    return sum(1 for p in REAL_UPLOAD_ROOT.rglob("*") if p.is_file())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def real_upload_tree_tripwire():
    """Fail the run if any test changes the real upload tree's file count."""
    before = _count_real_uploads()
    yield
    after = _count_real_uploads()
    assert after == before, f"tests modified the real upload tree: {before} -> {after} file(s)"


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    """Point the script at a throwaway root for every test in this module."""
    root = _seed_root(tmp_path / "uploads")
    monkeypatch.setattr(orphan, "settings", FakeSettings(root, DATABASE_URL))
    return root


@pytest.fixture
def referenced(monkeypatch):
    """Make the DB reference set a harmless constant."""

    def _install(keys: set[str] = SEEDED_REFERENCES):
        async def _referenced_keys():
            return set(keys)

        monkeypatch.setattr(orphan, "_referenced_keys", _referenced_keys)
        return keys

    return _install


# ---------------------------------------------------------------------------
# Harness isolation (regression for the historical defect)
# ---------------------------------------------------------------------------


class TestHarnessIsolation:
    def test_patching_the_get_settings_function_cannot_retarget_the_sweep(
        self, monkeypatch, tmp_path
    ):
        """The historical harness target could never work -- it raises instead."""
        with pytest.raises(AttributeError):
            monkeypatch.setattr(get_settings, "upload_path", tmp_path)

    def test_active_root_is_never_the_real_upload_tree(self):
        active = Path(orphan.settings.upload_path).resolve()
        assert active != REAL_UPLOAD_ROOT
        assert REAL_UPLOAD_ROOT not in active.parents

    def test_real_upload_tree_exists_and_is_not_empty(self):
        assert REAL_UPLOAD_ROOT.is_dir()
        assert _count_real_uploads() > 0


# ---------------------------------------------------------------------------
# Import behaviour
# ---------------------------------------------------------------------------


class TestImportDoesNotRunCleanup:
    def test_importing_the_script_does_not_start_the_sweep(self):
        assert orphan.main is not None
        assert orphan.__name__ != "__main__"


# ---------------------------------------------------------------------------
# Database failure must abort before any filesystem side effect
# ---------------------------------------------------------------------------


class TestAbortWhenDatabaseUnreadable:
    async def test_unreadable_reference_set_aborts_before_deletion(
        self, monkeypatch, isolated_settings
    ):
        before = _all_keys(isolated_settings)

        def unavailable():
            return _DBReferenceUnavailable("simulated unreadable database")

        monkeypatch.setattr(orphan, "async_session", lambda: _SessionRaises(unavailable))

        code = await orphan.run_sweep(delete=True, assume_yes=True)

        assert code == 2
        assert _all_keys(isolated_settings) == before, "no file may be touched"


# ---------------------------------------------------------------------------
# Dry run and deletion authorization
# ---------------------------------------------------------------------------


class TestDryRunAndAuthorization:
    async def test_dry_run_deletes_nothing(self, isolated_settings, referenced):
        referenced(set())
        before = _all_keys(isolated_settings)

        code = await orphan.run_sweep(delete=False, assume_yes=False, archive=None)

        assert code == 0
        assert _all_keys(isolated_settings) == before

    async def test_refusing_the_prompt_deletes_nothing(self, monkeypatch, isolated_settings, referenced):
        referenced(set())
        monkeypatch.setattr(builtins, "input", lambda *a, **k: "n")
        before = _all_keys(isolated_settings)

        code = await orphan.run_sweep(delete=True, assume_yes=False)

        assert code == 1
        assert _all_keys(isolated_settings) == before


# ---------------------------------------------------------------------------
# Sweep behaviour
# ---------------------------------------------------------------------------


class TestSweepDeletesOnlyOrphans:
    async def test_orphan_removed_and_referenced_files_kept(self, isolated_settings, referenced):
        root = isolated_settings
        referenced(SEEDED_REFERENCES)

        code = await orphan.run_sweep(delete=True, assume_yes=True)

        assert code == 0
        assert not (root / "user-1" / "orphan.pdf").exists()
        assert (root / "user-1" / "report.pdf").exists()
        assert (root / "user-1" / "notes.txt").exists()
        assert (root / "user-2" / "other.pdf").exists()

    async def test_nested_orphan_removed_and_empty_directories_pruned(self, isolated_settings, referenced):
        root = isolated_settings
        nested = root / "user-3" / "deep" / "deeper"
        nested.mkdir(parents=True)
        (nested / "orphan.pdf").write_text("orphan")
        referenced(SEEDED_REFERENCES)

        code = await orphan.run_sweep(delete=True, assume_yes=True)

        assert code == 0
        assert not (nested / "orphan.pdf").exists()
        assert not (root / "user-3").exists(), "empty directories must be pruned"
        assert (root / "user-2").is_dir(), "directories that still hold files must survive"


# ---------------------------------------------------------------------------
# Root validation
# ---------------------------------------------------------------------------


class TestRootValidation:
    def test_normal_directory_root_is_accepted(self, tmp_path):
        root = tmp_path / "plain"
        root.mkdir()
        assert cleanup_path.intended_root(root) == root.resolve()

    def test_missing_root_is_refused_by_the_guard(self, tmp_path):
        with pytest.raises(RuntimeError):
            cleanup_path.intended_root(tmp_path / "does-not-exist")

    def test_forbid_symlink_roots_rejects_linked_root(self, tmp_path):
        real_root = _seed_root(tmp_path / "real")
        link = tmp_path / "linked-root"
        mechanism = _make_dir_link(link, real_root)

        with pytest.raises(RuntimeError, match="symlink"):
            cleanup_path.forbid_symlink_roots(link)

        assert mechanism in ("symlink", "junction")
        assert (real_root / "user-1" / "orphan.pdf").exists(), "the target must be untouched"

    def test_is_link_or_reparse_point_distinguishes_link_from_real_directory(self, tmp_path):
        real_root = _seed_root(tmp_path / "real")
        link = tmp_path / "linked-root"
        _make_dir_link(link, real_root)

        assert cleanup_path.is_link_or_reparse_point(link) is True
        assert cleanup_path.is_link_or_reparse_point(real_root) is False

    async def test_sweep_refuses_linked_root_before_archiving_or_deleting(
        self, monkeypatch, isolated_settings, referenced, tmp_path
    ):
        real_root = _seed_root(tmp_path / "outside-real")
        link = tmp_path / "linked-uploads"
        _make_dir_link(link, real_root)
        monkeypatch.setattr(orphan.settings, "upload_path", link)
        referenced(set())

        archive = tmp_path / "orphans.zip"
        before = _all_keys(real_root)

        code = await orphan.run_sweep(delete=True, assume_yes=True, archive=archive)

        assert code == 1, "an unsafe root must be refused"
        assert not archive.exists(), "nothing may be archived before root validation"
        assert _all_keys(real_root) == before, "no file in the link target may be deleted"

    async def test_missing_root_is_a_no_op_not_a_deletion(self, monkeypatch, tmp_path, referenced):
        missing = tmp_path / "never-created"
        monkeypatch.setattr(orphan, "settings", FakeSettings(missing, DATABASE_URL))
        referenced(set())

        code = await orphan.run_sweep(delete=True, assume_yes=True)

        assert code == 0
        assert not missing.exists()


# ---------------------------------------------------------------------------
# Link candidates must never be followed
# ---------------------------------------------------------------------------


class TestLinkedCandidates:
    async def test_linked_directory_is_not_traversed_or_deleted(
        self, isolated_settings, referenced, tmp_path
    ):
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "outside-orphan.pdf").write_text("must survive")

        link = isolated_settings / "user-9"
        _make_dir_link(link, outside)
        referenced(SEEDED_REFERENCES)

        code = await orphan.run_sweep(delete=True, assume_yes=True)

        assert (outside / "outside-orphan.pdf").exists(), "a linked directory must not be traversed"
        assert link.exists(), "the link itself is not a deletion candidate"
        assert code == 0

    def test_linked_directory_is_not_a_prune_candidate(self, tmp_path):
        outside = tmp_path / "outside-empty"
        outside.mkdir()
        link = tmp_path / "linked-empty"
        _make_dir_link(link, outside)

        assert cleanup_path.validate_candidate(link, link, expect="directory") is False
        assert outside.is_dir()

    async def test_file_link_inside_root_is_not_deleted(self, isolated_settings, referenced, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        secret = outside / "secret.pdf"
        secret.write_text("must survive")

        link = isolated_settings / "user-1" / "linked.pdf"
        _make_file_link(link, secret)
        referenced(SEEDED_REFERENCES)

        code = await orphan.run_sweep(delete=True, assume_yes=True)

        assert secret.exists(), "deleting a link must never delete its target"
        assert link.exists(), "the link is not a deletion candidate"
        assert code == 0


# ---------------------------------------------------------------------------
# Archive handling
# ---------------------------------------------------------------------------


class TestArchiveHandling:
    async def test_archive_inside_upload_root_is_rejected(self, isolated_settings, referenced):
        referenced(set())
        archive_inside = isolated_settings / "archive.zip"
        before = _all_keys(isolated_settings)

        code = await orphan.run_sweep(delete=True, assume_yes=True, archive=archive_inside)

        assert code == 3
        assert not archive_inside.exists()
        assert _all_keys(isolated_settings) == before

    async def test_existing_archive_path_deletes_nothing(self, isolated_settings, referenced, tmp_path):
        referenced(set())
        archive = tmp_path / "already-there.zip"
        archive.write_text("occupied")
        before = _all_keys(isolated_settings)

        code = await orphan.run_sweep(delete=True, assume_yes=True, archive=archive)

        assert code == 3
        assert _all_keys(isolated_settings) == before

    async def test_archive_verification_failure_deletes_nothing(
        self, monkeypatch, isolated_settings, referenced, tmp_path
    ):
        referenced(set())
        monkeypatch.setattr(zipfile.ZipFile, "testzip", lambda self: "corrupt-entry")
        archive = tmp_path / "bad.zip"
        before = _all_keys(isolated_settings)

        code = await orphan.run_sweep(delete=True, assume_yes=True, archive=archive)

        assert code == 3
        assert _all_keys(isolated_settings) == before, "a failed archive must block deletion"

    async def test_archive_write_failure_deletes_nothing(
        self, monkeypatch, isolated_settings, referenced, tmp_path
    ):
        """An archive that cannot be written aborts before any deletion.

        STEP 1.6Z: the failure is reported as a refusal (exit 3) instead of
        escaping as a traceback, and no file is deleted, because deletion
        depends on a verified archive.  The incomplete archive is deliberately
        left in place: removing it would need a pathname unlink, which is the
        very operation this step removes, and a leftover archive blocks a
        silent re-run (the next sweep refuses an existing archive).
        """
        referenced(set())
        archive = tmp_path / "write-fails.zip"
        before = _all_keys(isolated_settings)

        def _boom(self, *args, **kwargs):
            raise OSError("simulated archive write failure")

        monkeypatch.setattr(zipfile.ZipFile, "write", _boom)

        code = await orphan.run_sweep(delete=True, assume_yes=True, archive=archive)

        assert code == 3, "a failed archive must be reported as a refusal"
        assert _all_keys(isolated_settings) == before, (
            "a failed archive must block deletion"
        )
        assert archive.exists(), (
            "the incomplete archive is left for the operator to remove by hand"
        )

    async def test_verified_archive_is_written_before_deletion(self, isolated_settings, referenced, tmp_path):
        root = isolated_settings
        referenced(SEEDED_REFERENCES)
        archive = tmp_path / "orphans.zip"

        code = await orphan.run_sweep(delete=True, assume_yes=True, archive=archive)

        assert code == 0
        assert archive.exists()
        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
        assert names == ["user-1/orphan.pdf"]
        assert not (root / "user-1" / "orphan.pdf").exists()


# ---------------------------------------------------------------------------
# Step 1.6Z -- an unholdable root refuses the sweep instead of degrading
# ---------------------------------------------------------------------------


class TestUnholdableRootRefusesCleanup:
    async def test_sweep_aborts_when_the_validated_root_cannot_be_held(
        self, monkeypatch, isolated_settings, referenced
    ):
        """Finding B: "unsupported platform" and "cannot open the root" differ.

        ``open_root_fd`` raises when the platform supports descriptor-relative
        deletion but the validated root cannot be held (the root swapped for a
        symlink, permissions changed, an I/O error).  The sweep must abort with
        nothing deleted instead of falling back to pathname deletes, which is
        exactly the state the guard exists to refuse.
        """
        referenced(SEEDED_REFERENCES)
        before = _all_keys(isolated_settings)

        def _cannot_hold(root):
            raise RuntimeError("simulated: the root could not be held")

        monkeypatch.setattr(orphan.cleanup_path, "open_root_fd", _cannot_hold)

        code = await orphan.run_sweep(delete=True, assume_yes=True)

        assert code == 1, "an unholdable root must abort the sweep"
        assert _all_keys(isolated_settings) == before, "nothing may be deleted"


# ---------------------------------------------------------------------------
# Containment helpers
# ---------------------------------------------------------------------------


class TestContainmentHelpers:
    def test_is_under_rejects_paths_outside_root(self):
        assert not cleanup_path.is_under(Path("/tmp/root"), Path("/tmp/outside.txt"))

    def test_is_under_accepts_direct_child(self):
        assert cleanup_path.is_under(Path("/tmp/root"), Path("/tmp/root/file.txt"))

    def test_is_under_rejects_prefix_sibling(self):
        assert not cleanup_path.is_under(Path("/tmp/root"), Path("/tmp/root-sibling/file.txt"))

    def test_is_under_rejects_traversal_out_of_root(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        escape = root / ".." / "outside.txt"
        escape.write_text("outside")
        assert not cleanup_path.is_under(root, escape)

    def test_validate_candidate_accepts_a_real_file_inside_root(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        candidate = root / "file.txt"
        candidate.write_text("x")
        assert cleanup_path.validate_candidate(root, candidate, expect="file") is True

    def test_validate_candidate_requires_the_expected_type(self, tmp_path):
        root = tmp_path / "root"
        child = root / "sub"
        child.mkdir(parents=True)
        file_in_root = root / "file.txt"
        file_in_root.write_text("x")

        assert cleanup_path.validate_candidate(root, child, expect="directory") is True
        assert cleanup_path.validate_candidate(root, child, expect="file") is False
        assert cleanup_path.validate_candidate(root, file_in_root, expect="directory") is False

    def test_validate_candidate_rejects_missing_and_outside_paths(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("x")

        assert cleanup_path.validate_candidate(root, root / "missing.txt") is False
        assert cleanup_path.validate_candidate(root, outside) is False

    def test_validate_candidate_rejects_a_linked_directory(self, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        link = tmp_path / "link"
        _make_dir_link(link, outside)

        assert cleanup_path.validate_candidate(tmp_path, link, expect="directory") is False

    def test_validate_candidate_rejects_an_unknown_expectation(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        with pytest.raises(ValueError):
            cleanup_path.validate_candidate(root, root, expect="device")


# ---------------------------------------------------------------------------
# Platform capability reporting
# ---------------------------------------------------------------------------


class TestLinkCapabilityReporting:
    def test_link_capability_is_reported_not_silently_skipped(self, tmp_path):
        """On POSIX, link support is required; elsewhere the skip must be visible."""
        link = tmp_path / "capability-link"
        target = tmp_path / "capability-target"
        target.mkdir()

        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            if os.name == "posix":
                pytest.fail(
                    f"symlink support is required on POSIX ({exc}); the security "
                    "suite must not silently degrade to skips"
                )
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                pytest.skip(
                    f"no symlink privilege ({type(exc).__name__}) and no junction "
                    "support; the link-root regression case cannot run here "
                    "(reported, not hidden)"
                )
            assert cleanup_path.is_link_or_reparse_point(link) is True, (
                "an NTFS junction is a reparse point and must be detected even "
                "though Path.is_symlink() reports False"
            )
            assert link.is_symlink() is False, (
                "documents the platform hazard this guard exists to cover"
            )
            return

        assert link.is_symlink() is True
        assert cleanup_path.is_link_or_reparse_point(link) is True
