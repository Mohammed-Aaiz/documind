"""STEP 1.6Z Workstream C — deterministic substitution at the syscall boundary.

Every test here forces exactly one substitution with a controlled hook that runs
*once*, at the boundary the module under test actually calls.  There are no
sleeps and no probabilistic stress runs: the substitution happens after
validation and immediately before the destructive operation, which is the window
being examined.

**Every deletion boundary is hooked, on purpose.**  Three of them exist in the
code under test: `Path.unlink` (the sweep's pathname flow),
`cleanup_path.unlink_beneath` (the descriptor-relative flow) and
`storage.file_store.delete_upload` (what the smoke helper deletes through); the
prune path is likewise split between `Path.rmdir` and
`cleanup_path.rmdir_beneath`.  A hook installed on only one boundary would make
the test vacuous on the platform or code path that uses another — it would pass
because the substitution never happened.  The helpers below install one shared
one-shot substitution across all of them, so it takes effect immediately before
whichever deletion actually runs.

**What these tests do and do not prove.**  Each one asserts an invariant about
the *specific substitution it performs*: no deletion outside the permitted root,
no unintended mutation of an unrelated file, and a refusal reported rather than
silently swallowed.  None of them proves race-freedom in general — the
check-then-use window between validation and the ``unlink()``/``rmdir()``
syscall remains OPEN on the pathname flow, as documented in
``scripts/cleanup_path.py``.  A path-based ``unlink``/``rmdir`` is not bound to
the object an earlier ``lstat``/``resolve`` inspected; the descriptor-relative
helpers close that for POSIX parents/roots only, and are unverified here.

Two residual risks are documented rather than asserted, because asserting them
would mean pinning defective behaviour as correct:

1. Inside a held directory the final *name* can still be swapped for a different
   object between the caller's validation and the delete (no stdlib primitive
   binds a name to an earlier ``lstat``).  This is stated in
   ``scripts/cleanup_path.py`` and is exercised by
   ``TestCandidateReplacedByAnotherRegularFile`` only to the extent that no
   boundary is escaped.
2. ``_archive_orphans`` verifies the finished archive by re-opening the
   *destination path*, so the object it verifies is not provably the object it
   wrote.  See this module's test-run notes for the finding;
   an identity check (``os.stat(path)`` vs ``os.fstat(handle)``) or verifying
   through the handle would close it.

**Deliberately not duplicated.**  Scenario 7 of the brief (archive-write failure
with no unintended deletion) is already covered by
``tests/unit/scripts/test_cleanup_orphan_uploads.py::TestArchiveHandling::test_archive_write_failure_deletes_nothing``
(line 461), and a candidate swapped for a link after validation is already
covered by ``tests/unit/scripts/test_reparse_points_and_race_safety.py``.

All filesystem work is confined to ``tmp_path``; the real ``backend/uploads/``
tree is never addressed, and the sweep's database read is replaced with an
in-memory reference set so nothing connects to a database.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

import pytest

import scripts.cleanup_orphan_uploads as orphan
import scripts.cleanup_path as cleanup_path
import scripts.cleanup_smoke as smoke


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeSettings:
    """Minimal stand-in for ``config.Settings`` as the sweep actually uses it."""

    def __init__(self, upload_path: Path) -> None:
        self.upload_path = upload_path


@pytest.fixture
def uploads_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An isolated upload root that the sweep is pointed at instead of the real one."""
    root = tmp_path / "uploads"
    root.mkdir()
    monkeypatch.setattr(orphan, "settings", _FakeSettings(root))
    return root


@pytest.fixture
def referenced(monkeypatch: pytest.MonkeyPatch):
    """Install the sweep's database reference set without touching a database."""

    def install(keys):
        async def _fake() -> set[str]:
            return set(keys)

        monkeypatch.setattr(orphan, "_referenced_keys", _fake)

    return install


def _write(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _snapshot(root: Path) -> dict[str, bytes]:
    """Every regular file under ``root`` (relative posix path -> bytes).

    Links and reparse points are skipped rather than traversed, so a
    substitution that redirects a path outward cannot pull an outside tree into
    the snapshot and mask a change.
    """
    snapshot: dict[str, bytes] = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        kept: list[str] = []
        for name in dirnames:
            child = current / name
            if cleanup_path.is_link_or_reparse_point(child):
                continue
            kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            child = current / name
            if cleanup_path.is_link_or_reparse_point(child):
                continue
            snapshot[child.relative_to(root).as_posix()] = child.read_bytes()
    return snapshot


def _one_shot(
    substitute: Callable[[], None]
) -> tuple[Callable[[], None], dict[str, bool]]:
    """Wrap a substitution so it runs exactly once, before the real operation.

    Returns the guarded callable together with the state dict recording whether
    the substitution actually ran, so a test can never pass without it.
    """
    state = {"done": False}

    def guarded() -> None:
        if not state["done"]:
            state["done"] = True
            substitute()

    return guarded, state


#: One state dict per substitution hook installed through the helpers below.
#: STEP 1.6Z (finding A): a hook that never fires makes its test vacuous -- the
#: asserted invariant then holds simply because no substitution happened, which
#: is precisely how the prune test passed for the wrong reason.  Every installed
#: hook must report that it ran, or the test fails.
_INSTALLED_HOOKS: list[dict[str, bool]] = []


@pytest.fixture(autouse=True)
def _substitution_hooks_must_fire():
    """Fail any test whose installed substitution hook never executed."""
    _INSTALLED_HOOKS.clear()
    yield
    unfired = [state for state in _INSTALLED_HOOKS if not state["done"]]
    _INSTALLED_HOOKS.clear()
    assert not unfired, (
        "a substitution hook was installed but never fired, so the test would "
        "have passed without exercising the race window"
    )


def _hook_delete_boundary(
    monkeypatch: pytest.MonkeyPatch, substitute: Callable[[], None]
) -> None:
    """Install a one-shot substitution at EVERY deletion boundary.

    Three boundaries exist across the code under test, and the platform and the
    code path decide which one runs: ``Path.unlink`` is the sweep's pathname
    flow, ``cleanup_path.unlink_beneath`` is the descriptor-relative flow, and
    ``storage.file_store.delete_upload`` is what the smoke helper deletes
    through.  All three are hooked with the same one-shot guard, so the
    substitution lands immediately before whichever deletion actually runs; a
    hook on only one of them would let the test pass on the other platform
    because the substitution never happened.
    """
    guarded, state = _one_shot(substitute)
    _INSTALLED_HOOKS.append(state)
    real_unlink = Path.unlink
    real_unlink_beneath = cleanup_path.unlink_beneath
    real_delete_upload = smoke.delete_upload

    def hooked_unlink(self, *args, **kwargs):
        guarded()
        return real_unlink(self, *args, **kwargs)

    def hooked_unlink_beneath(root_fd, relative):
        guarded()
        return real_unlink_beneath(root_fd, relative)

    def hooked_delete_upload(candidate, *, root=None):
        guarded()
        return real_delete_upload(candidate, root=root)

    monkeypatch.setattr(Path, "unlink", hooked_unlink)
    monkeypatch.setattr(cleanup_path, "unlink_beneath", hooked_unlink_beneath)
    monkeypatch.setattr(smoke, "delete_upload", hooked_delete_upload)


def _hook_prune_boundary(
    monkeypatch: pytest.MonkeyPatch, substitute: Callable[[], None]
) -> None:
    """Install a one-shot substitution at every prune boundary (both flows)."""
    guarded, state = _one_shot(substitute)
    _INSTALLED_HOOKS.append(state)
    real_rmdir = Path.rmdir
    real_rmdir_beneath = cleanup_path.rmdir_beneath

    def hooked_rmdir(self):
        guarded()
        return real_rmdir(self)

    def hooked_rmdir_beneath(root_fd, relative):
        guarded()
        return real_rmdir_beneath(root_fd, relative)

    monkeypatch.setattr(Path, "rmdir", hooked_rmdir)
    monkeypatch.setattr(cleanup_path, "rmdir_beneath", hooked_rmdir_beneath)


def _make_dir_link(link: Path, target: Path) -> None:
    """Create a directory symlink (POSIX) or a junction (Windows).

    A junction needs no elevation, unlike a Windows symlink, so on Windows this
    exercises the reparse-point branch where a symlink would be refused by
    ``WinError 1314``.  If the platform cannot create either, the test skips with
    the real error rather than passing.
    """
    if os.name == "posix":
        try:
            link.symlink_to(target, target_is_directory=True)
            return
        except OSError as error:
            pytest.skip(f"cannot create a directory symlink here: {error!r}")

    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(
            "mklink /J failed "
            f"(rc={result.returncode}): {result.stdout.strip()} {result.stderr.strip()}"
        )


def _require_directory_links(tmp_path: Path) -> None:
    """Skip the test up front unless this host can create a directory link.

    Probing in the test body keeps the skip out of the syscall hook, where the
    module under test could observe or swallow it.
    """
    target = tmp_path / "_probe_target"
    target.mkdir(exist_ok=True)
    _make_dir_link(tmp_path / "_probe_link", target)


# ---------------------------------------------------------------------------
# 1 — parent directory replaced after validation
# ---------------------------------------------------------------------------


class TestParentDirectoryReplacedAfterValidation:
    def test_parent_redirected_outside_the_root_is_refused(
        self, tmp_path: Path, uploads_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Substitution: the validated parent is displaced and redirected outward.

        The hook runs at the deletion boundary — i.e. after
        ``resolve_stored_path`` has validated the candidate and immediately
        before the deletion.  It renames ``root/uid`` away and replaces its path
        with a link to an outside directory that holds a different ``x.pdf``.

        Invariant asserted: nothing outside the root is deleted, the displaced
        in-root file is byte-identical, and the value is reported as refused
        rather than silently treated as success.  This proves the *specific*
        substitution is caught; it does not prove race-freedom.
        """
        _require_directory_links(tmp_path)
        root_path = uploads_root
        outside = tmp_path / "outside"
        _write(outside / "uid" / "x.pdf", b"outside-secret")
        _write(root_path / "uid" / "x.pdf", b"in-root")
        outside_before = _snapshot(outside)

        def substitute() -> None:
            (root_path / "uid").rename(root_path / "uid-moved")
            _make_dir_link(root_path / "uid", outside / "uid")

        _hook_delete_boundary(monkeypatch, substitute)

        deleted, missing, refused = smoke.delete_upload_files(
            root_path, ["uploads/uid/x.pdf"]
        )

        assert (deleted, missing, refused) == (0, 0, 1)
        assert _snapshot(outside) == outside_before
        assert (root_path / "uid-moved" / "x.pdf").read_bytes() == b"in-root"


# ---------------------------------------------------------------------------
# 2 — candidate replaced by a different regular file
# ---------------------------------------------------------------------------


class TestCandidateReplacedByAnotherRegularFile:
    def test_candidate_swapped_for_a_different_object_cannot_escape(
        self, tmp_path: Path, uploads_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Substitution: the validated file is replaced by a different regular file.

        The hook replaces ``x.pdf`` with a freshly written object under the same
        name, immediately before the deletion.

        Invariant asserted: nothing outside the root is deleted, every unrelated
        sibling is byte-identical, and the reported counts are honest.  This
        proves only that no boundary was escaped — the deletion follows the
        *name*, so the object removed is demonstrably not the one validated (see
        residual 1 in the module docstring).
        """
        root_path = uploads_root
        _write(root_path / "uid" / "x.pdf", b"original")
        _write(root_path / "uid" / "sibling.pdf", b"sibling")
        outside = tmp_path / "outside"
        _write(outside / "sentinel.bin", b"sentinel")
        outside_before = _snapshot(outside)

        def substitute() -> None:
            replacement = root_path / "uid" / "x.pdf.replacement"
            replacement.write_bytes(b"replacement-object")
            os.replace(replacement, root_path / "uid" / "x.pdf")

        _hook_delete_boundary(monkeypatch, substitute)

        deleted, missing, refused = smoke.delete_upload_files(
            root_path, ["uploads/uid/x.pdf"]
        )

        assert (deleted, missing, refused) == (1, 0, 0)
        assert not (root_path / "uid" / "x.pdf").exists()
        assert (root_path / "uid" / "sibling.pdf").read_bytes() == b"sibling"
        assert _snapshot(outside) == outside_before


# ---------------------------------------------------------------------------
# 3 — directory redirected outside the permitted root before the prune
# ---------------------------------------------------------------------------


class TestPrunedDirectoryRedirectedOutsideTheRoot:
    def test_redirected_prune_target_is_not_removed(
        self, tmp_path: Path, uploads_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Substitution: the validated empty directory is swapped for a link outward.

        The hook runs at the prune boundary — after ``prune_user_dir`` validated
        the directory and immediately before the removal.  It removes the
        validated empty directory and replaces its path with a link to an *empty*
        outside directory, so an implementation that followed the link would
        delete the outside directory itself.

        Invariant asserted: the outside directory still exists.  The return value
        is deliberately not asserted: removing a symlink and removing a junction
        differ by platform (``rmdir`` on a POSIX symlink raises ``ENOTDIR``,
        while a Windows junction is removed), so only the invariant is
        deterministic.
        """
        _require_directory_links(tmp_path)
        root_path = uploads_root
        outside_dir = tmp_path / "outside-empty"
        outside_dir.mkdir()
        (root_path / "uid").mkdir()
        (root_path / "unrelated").mkdir()

        def substitute() -> None:
            (root_path / "uid").rmdir()
            _make_dir_link(root_path / "uid", outside_dir)

        _hook_prune_boundary(monkeypatch, substitute)

        smoke.prune_user_dir(root_path, "uid")

        assert outside_dir.is_dir(), "the redirected target must not be removed"
        assert (root_path / "unrelated").is_dir()


# ---------------------------------------------------------------------------
# 4 — two-sweep concurrency simulation
# ---------------------------------------------------------------------------


class TestTwoSweepConcurrencySimulation:
    async def test_two_sweeps_over_the_same_tree_are_deterministic(
        self, tmp_path: Path, uploads_root: Path, referenced
    ) -> None:
        """Sequential simulation of two overlapping cleanups — not true concurrency.

        A second sweep runs over the same tree after an upload appears between
        the two runs, so the second sweep must classify the tree from scratch
        instead of inheriting the first sweep's decisions.

        Invariant asserted: each sweep deletes exactly the files it classified,
        referenced files are byte-identical, no deletion happens outside the
        root, no exception escapes, and both sweeps return an honest exit code.
        A true race between two processes is *not* simulated here.
        """
        root_path = uploads_root
        _write(root_path / "user-1" / "orphan.pdf", b"orphan-1")
        _write(root_path / "user-1" / "report.pdf", b"referenced")
        outside = tmp_path / "outside"
        _write(outside / "sentinel.bin", b"keep")
        outside_before = _snapshot(outside)
        referenced({"user-1/report.pdf"})

        before_first = _snapshot(root_path)
        first = await orphan.run_sweep(delete=True, assume_yes=True)
        after_first = _snapshot(root_path)

        _write(root_path / "user-2" / "late.pdf", b"late")

        before_second = _snapshot(root_path)
        second = await orphan.run_sweep(delete=True, assume_yes=True)
        after_second = _snapshot(root_path)

        assert first == 0
        assert second == 0
        assert set(before_first) - set(after_first) == {"user-1/orphan.pdf"}
        assert set(before_second) - set(after_second) == {"user-2/late.pdf"}
        assert after_second == {"user-1/report.pdf": b"referenced"}
        assert _snapshot(outside) == outside_before


# ---------------------------------------------------------------------------
# 5 — cleanup racing with creation
# ---------------------------------------------------------------------------


class TestCleanupRacingWithCreation:
    async def test_a_file_created_after_the_scan_is_not_deleted(
        self, uploads_root: Path, referenced, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Substitution: a writer lands a new upload mid-way through the deletion loop.

        The hook runs at the deletion boundary — after the scan and the
        classification, immediately before the first deletion — and creates a new
        file in the sweep's tree.

        Invariant asserted: only files the sweep had already classified are
        deleted, the new file is byte-identical afterwards, and the sweep reports
        a non-zero code instead of claiming clean success.
        """
        root_path = uploads_root
        _write(root_path / "user-1" / "orphan.pdf", b"orphan")
        referenced(set())

        def substitute() -> None:
            _write(root_path / "user-1" / "late.pdf", b"late")

        _hook_delete_boundary(monkeypatch, substitute)

        code = await orphan.run_sweep(delete=True, assume_yes=True)

        assert (root_path / "user-1" / "late.pdf").read_bytes() == b"late"
        assert not (root_path / "user-1" / "orphan.pdf").exists()
        assert code == 1, (
            "an orphan the sweep did not classify must be reported, not silently "
            "accepted as a clean run"
        )


# ---------------------------------------------------------------------------
# 6 — archive destination appearing after the existence check
# ---------------------------------------------------------------------------


class TestArchiveDestinationSubstitutedAfterTheCheck:
    async def test_a_file_appearing_after_the_existence_check_is_not_overwritten(
        self,
        tmp_path: Path,
        uploads_root: Path,
        referenced,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Substitution: another actor creates the archive destination after the check.

        Until STEP 1.6Z this window was exploitable: ``_archive_orphans`` checked
        ``archive.exists()`` and then opened the destination with mode ``"w"``,
        which truncates, so a file appearing in between was silently replaced and
        the sweep went on to delete its orphans.  The fix is an exclusive
        ``open(archive, "x+b")``, which makes the creation itself the refusal
        (and stays readable, so the same handle verifies the archive).

        This test simulates the window deterministically on the *check* side:
        ``Path.exists`` is made to report the archive absent even though the
        destination is present by the time creation is attempted, which is
        exactly what the module's pre-check would have seen.  Every other path
        delegates to the real ``Path.exists`` so nothing else in the sweep is
        affected, and the guarantee under test is the exclusive create rather
        than the simulation.

        Invariant asserted: the sweep returns 3 (the archive-refusal code), the
        destination's bytes are byte-identical, and the upload tree is untouched.

        Two falsification guards keep this test from passing vacuously, which it
        otherwise could: if the ``exists`` override below never applied, the sweep
        would abort at its own pre-check and still return 3 with the destination
        untouched.  So the test also asserts that the patched ``exists`` really was
        consulted for the archive, and that the refusal came from the *creation*
        branch (``appeared before it could be created``) rather than the pre-check
        branch (``already exists``).
        """
        root_path = uploads_root
        _write(root_path / "user-1" / "orphan.pdf", b"orphan")
        referenced(set())
        archive = tmp_path / "orphans.zip"
        planted = b"planted-by-another-actor"
        tree_before = _snapshot(root_path)

        # The "other actor" creates the destination after the pre-check ran.
        archive.write_bytes(planted)

        real_exists = Path.exists
        consulted: list[Path] = []

        def lying_exists(self) -> bool:
            consulted.append(Path(self))
            if Path(self) == archive:
                return False
            return real_exists(self)

        monkeypatch.setattr(Path, "exists", lying_exists)

        code = await orphan.run_sweep(delete=True, assume_yes=True, archive=archive)
        captured = capsys.readouterr().out

        assert archive in consulted, (
            "the simulated window did not apply: the archive pre-check was never "
            "consulted through the patched exists, so this test would pass without "
            "exercising the exclusive create"
        )
        assert "appeared before it could be created" in captured, (
            "the refusal must come from the exclusive create, not from the pre-check"
        )
        assert "already exists" not in captured, (
            "the pre-check branch must not be the one that refused"
        )
        assert code == 3, "a destination that appeared after the check is a refusal"
        assert archive.read_bytes() == planted, (
            "the destination that appeared after the check must not be overwritten"
        )
        assert _snapshot(root_path) == tree_before, (
            "nothing may be deleted when the archive could not be created"
        )


# ---------------------------------------------------------------------------
# 8 — repeated cleanup attempts are idempotent
# ---------------------------------------------------------------------------


class TestRepeatedCleanupIsIdempotent:
    async def test_three_sweeps_delete_only_the_first_time(
        self, tmp_path: Path, uploads_root: Path, referenced
    ) -> None:
        """No substitution: three successive sweeps over the same tree.

        Invariant asserted: the first sweep removes exactly the orphan, the later
        sweeps delete nothing, all three return 0, referenced files are never
        touched, and nothing outside the root changes.
        """
        root_path = uploads_root
        _write(root_path / "user-1" / "orphan.pdf", b"orphan")
        _write(root_path / "user-2" / "keep.pdf", b"referenced")
        outside = tmp_path / "outside"
        _write(outside / "sentinel.bin", b"keep")
        outside_before = _snapshot(outside)
        referenced({"user-2/keep.pdf"})

        codes: list[int] = []
        removed: list[set[str]] = []
        previous = _snapshot(root_path)
        for _ in range(3):
            codes.append(await orphan.run_sweep(delete=True, assume_yes=True))
            current = _snapshot(root_path)
            removed.append(set(previous) - set(current))
            previous = current

        assert codes == [0, 0, 0]
        assert removed[0] == {"user-1/orphan.pdf"}
        assert removed[1] == set()
        assert removed[2] == set()
        assert _snapshot(root_path) == {"user-2/keep.pdf": b"referenced"}
        assert _snapshot(outside) == outside_before
