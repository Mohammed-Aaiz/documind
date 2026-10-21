"""STEP 1.6AA — the ``__pycache__`` sweep must stay inside its root and never follow a link.

``scripts/start_server.py`` cleared bytecode caches at import with
``shutil.rmtree(..., ignore_errors=True)`` on every ``__pycache__`` name it found
while walking the CWD.  Two properties were missing: the sweep was not contained
in any validated tree, and it recursed wherever a name pointed -- a
``__pycache__`` replaced by a junction (or a junction nested inside one) was
followed and its target emptied, with every failure swallowed.

The replacement, ``cleanup_path.prune_pycache_beneath``, removes only a
directory that ``validate_candidate`` proves is a real directory inside the
given root, walks the tree refusing (never following) any link or reparse point,
and returns the refusals so the caller can report them.

These tests execute on this (Windows) host: junctions need no elevation.  On a
POSIX host the same cases run with real directory symlinks, so the behaviour is
covered on both platforms rather than skipped on one.  Every test works inside
``tmp_path``; nothing here touches the real ``backend/`` tree or the uploads
directory.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# This file lives at ``backend/tests/unit/scripts/`` -> parents[3] is ``backend``.
_BACKEND_DIR = Path(__file__).resolve().parents[3]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import scripts.cleanup_path as cleanup_path  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_dir_link(link: Path, target: Path) -> None:
    """Create a directory link: a real symlink on POSIX, a junction on Windows.

    Junctions are used on Windows because symlink creation needs a privilege the
    test account does not hold (``WinError 1314``); the code under test refuses
    both through the same ``FILE_ATTRIBUTE_REPARSE_POINT`` check.
    """
    if sys.platform == "win32":
        try:
            result = subprocess.run(  # noqa: S603 - fixed argv, tmp_path only
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True,
                text=True,
            )
        except OSError as exc:  # cmd unavailable
            pytest.skip(f"could not run mklink, junctions unavailable here: {exc!r}")
        if result.returncode != 0:
            pytest.skip(
                "directory junction unavailable here: "
                f"{(result.stderr or result.stdout).strip()!r}"
            )
        return
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlink unavailable here: {exc!r}")


def _snapshot(root: Path) -> dict[str, bytes]:
    """Byte content of every regular file under ``root``, links not traversed."""
    snapshot: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if cleanup_path.is_link_or_reparse_point(path) or not path.is_file():
            continue
        snapshot[path.relative_to(root).as_posix()] = path.read_bytes()
    return snapshot


# ---------------------------------------------------------------------------
# Containment and link refusal
# ---------------------------------------------------------------------------


class TestPrunePycacheBeneath:
    def test_removes_real_pycache_directories_and_nothing_else(self, tmp_path: Path):
        root = tmp_path / "backend-tree"
        (root / "pkg" / "__pycache__").mkdir(parents=True)
        (root / "pkg" / "__pycache__" / "a.cpython-311.pyc").write_bytes(b"bytecode")
        (root / "pkg" / "nested" / "__pycache__").mkdir(parents=True)
        (root / "pkg" / "nested" / "__pycache__" / "b.pyc").write_bytes(b"bytecode")
        keep = root / "pkg" / "keep.py"
        keep.write_bytes(b"source")

        removed, refused = cleanup_path.prune_pycache_beneath(root)

        assert removed == 2
        assert refused == []
        assert not (root / "pkg" / "__pycache__").exists()
        assert not (root / "pkg" / "nested" / "__pycache__").exists()
        assert keep.read_bytes() == b"source", "sibling source files must survive"
        assert (root / "pkg" / "nested").is_dir(), "only __pycache__ is removed"
        assert root.is_dir()

    def test_a_linked_root_is_a_refusal(self, tmp_path: Path):
        """``Path.is_dir()`` follows a link, so the root must be validated as such.

        A linked root would otherwise be accepted and its *target* swept.  Every
        other destructive entry point in this package refuses a linked root
        (``intended_root``), and this one now does too.  (Reviewer finding F-0.)
        """
        target = tmp_path / "target-tree"
        (target / "pkg" / "__pycache__").mkdir(parents=True)
        (target / "pkg" / "__pycache__" / "a.pyc").write_bytes(b"bytecode")
        linked_root = tmp_path / "linked-root"
        _make_dir_link(linked_root, target)

        with pytest.raises(RuntimeError):
            cleanup_path.prune_pycache_beneath(linked_root)

        assert (target / "pkg" / "__pycache__" / "a.pyc").read_bytes() == b"bytecode", (
            "a linked root must not lead the sweep into its target"
        )

    def test_a_regular_directory_is_removed_where_the_link_is_refused(
        self, tmp_path: Path
    ):
        """Differential non-vacuity: same shape, only the link differs.

        If the link refusal were removed, both candidates would be removed and
        ``refused`` would be empty, so this pair fails whenever the protection
        stops working -- unlike a single positive assertion, which a sweep that
        removed nothing would also satisfy.
        """
        root = tmp_path / "backend-tree"
        (root / "plain" / "__pycache__").mkdir(parents=True)
        (root / "plain" / "__pycache__" / "a.pyc").write_bytes(b"bytecode")
        (root / "linked").mkdir()
        target = tmp_path / "outside-target"
        (target / "inner").mkdir(parents=True)
        precious = target / "inner" / "precious.txt"
        precious.write_bytes(b"precious")
        _make_dir_link(root / "linked" / "__pycache__", target)

        removed, refused = cleanup_path.prune_pycache_beneath(root)

        assert removed == 1, "the real cache directory is still removed"
        assert not (root / "plain" / "__pycache__").exists()
        assert [message for message in refused if "link" in message], (
            "the link candidate must be refused and reported"
        )
        assert precious.read_bytes() == b"precious"

    def test_a_pycache_outside_the_root_is_not_touched(self, tmp_path: Path):
        """Containment by construction (``os.walk`` is rooted at ``root``).

        This one cannot fail if the ``validate_candidate`` gate is removed, so it
        is retained as a regression assertion about reach, not as evidence that
        the gate works -- ``test_a_regular_directory_is_removed_where_the_link_is_
        refused`` and the two link tests carry that evidence.
        """
        root = tmp_path / "backend-tree"
        root.mkdir()
        (root / "pkg").mkdir()
        (root / "pkg" / "__pycache__").mkdir()
        outside = tmp_path / "elsewhere" / "__pycache__"
        outside.mkdir(parents=True)
        sentinel = outside / "must-survive.pyc"
        sentinel.write_bytes(b"untouched")

        removed, refused = cleanup_path.prune_pycache_beneath(root)

        assert removed == 1
        assert sentinel.read_bytes() == b"untouched", "the sweep must stay inside the root"
        assert outside.is_dir()

    def test_a_file_named_pycache_is_never_a_candidate(self, tmp_path: Path):
        """A regular file named ``__pycache__`` is not a cache directory.

        ``os.walk`` lists it under ``filenames``, so it never enters the candidate
        set.  The invariant that matters is that the sweep leaves it alone (the
        old ``rmtree`` would have raised and, with ``ignore_errors=True``, hidden
        even that), which is asserted here.
        """
        root = tmp_path / "backend-tree"
        root.mkdir()
        impostor = root / "__pycache__"
        impostor.write_bytes(b"not a directory")

        removed, refused = cleanup_path.prune_pycache_beneath(root)

        assert removed == 0
        assert refused == []
        assert impostor.read_bytes() == b"not a directory"

    def test_a_missing_root_is_a_refusal_not_a_no_op(self, tmp_path: Path):
        with pytest.raises(RuntimeError):
            cleanup_path.prune_pycache_beneath(tmp_path / "absent")

    def test_a_linked_pycache_is_refused_and_its_target_survives(self, tmp_path: Path):
        """The exact case the old sweep got wrong: a ``__pycache__`` that is a link."""
        root = tmp_path / "backend-tree"
        (root / "pkg").mkdir(parents=True)
        target = tmp_path / "outside-target"
        (target / "inner").mkdir(parents=True)
        precious = target / "inner" / "precious.txt"
        precious.write_bytes(b"precious")
        _make_dir_link(root / "pkg" / "__pycache__", target)
        tree_before = _snapshot(root)

        removed, refused = cleanup_path.prune_pycache_beneath(root)

        assert removed == 0, "a linked directory is never removed"
        assert precious.read_bytes() == b"precious", "the link target must be untouched"
        assert (target / "inner").is_dir()
        assert _snapshot(root) == tree_before
        assert any("link" in message for message in refused), (
            "the refusal must be reported, not silently skipped"
        )

    def test_a_link_nested_inside_a_pycache_is_refused(self, tmp_path: Path):
        """A link *inside* the cache: the old recursive delete followed it."""
        root = tmp_path / "backend-tree"
        cache = root / "pkg" / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "real.pyc").write_bytes(b"bytecode")
        target = tmp_path / "outside-target"
        target.mkdir()
        precious = target / "precious.txt"
        precious.write_bytes(b"precious")
        _make_dir_link(cache / "linked", target)

        removed, refused = cleanup_path.prune_pycache_beneath(root)

        assert precious.read_bytes() == b"precious", "a nested link must not be followed"
        assert not target.joinpath("linked").exists()
        assert any("link or reparse point" in message for message in refused)
        # The linked entry is refused, so the candidate is not removed at all: the
        # operator sees the refusal instead of a half-emptied directory.
        assert removed == 0
        assert cache.is_dir()


# ---------------------------------------------------------------------------
# The caller: start_server.py must use the shared boundary, not a bare rmtree
# ---------------------------------------------------------------------------


class TestStartServerCallSite:
    """Source-read guards, so no server process is ever started here.

    ``scripts/start_server.py`` checks a port and then launches uvicorn at import
    time, so it cannot be imported by a test.  Its source is read as text, the
    same pattern the runner guard-order tests in this repository use.
    """

    @staticmethod
    def _code_lines() -> list[str]:
        """Executable lines only: the fix is documented in comments on purpose."""
        source = (_BACKEND_DIR / "scripts" / "start_server.py").read_text(
            encoding="utf-8"
        )
        return [
            line
            for line in source.splitlines()
            if not line.lstrip().startswith("#")
        ]

    def test_no_bare_recursive_delete_remains(self):
        code = "\n".join(self._code_lines())
        assert "shutil.rmtree" not in code, (
            "the uncontained, link-following rmtree must not come back"
        )
        assert "ignore_errors=True" not in code, (
            "refusals must be reported, never swallowed"
        )
        assert "shutil" not in code, "the shutil import was removed with its only use"

    def test_the_shared_boundary_helper_is_used(self):
        assert "prune_pycache_beneath" in "\n".join(self._code_lines())

    def test_the_prune_happens_before_the_server_starts(self):
        code = "\n".join(self._code_lines())
        prune_at = code.index("prune_pycache_beneath")
        launch_at = code.index("subprocess.Popen")
        assert prune_at < launch_at, (
            "the bytecode cache must be cleared before uvicorn is launched"
        )


class TestE2eHarnessCallSite:
    """STEP 1.6AB: the last unguarded ``__pycache__`` sweep is gone.

    ``tests/e2e/browser/test_phase6_reliability.py`` starts its own uvicorn against
    a live server, so the harness cannot be imported or run here; its source is read
    as text, like the other source-read guards in this repository.  The behaviour it
    now calls is covered by the tests above.
    """

    @staticmethod
    def _code_lines() -> list[str]:
        source = (_BACKEND_DIR / "tests" / "e2e" / "browser" / "test_phase6_reliability.py").read_text(
            encoding="utf-8"
        )
        return [
            line for line in source.splitlines() if not line.lstrip().startswith("#")
        ]

    def test_no_unguarded_recursive_delete_remains(self):
        code = "\n".join(self._code_lines())
        assert "shutil.rmtree" not in code, (
            "the uncontained, link-following rmtree must not come back"
        )
        assert "ignore_errors=True" not in code, (
            "refusals must be reported, never swallowed"
        )

    def test_the_shared_boundary_helper_is_used_on_the_backend_root(self):
        code = "\n".join(self._code_lines())
        assert "prune_pycache_beneath(_BACKEND_DIR)" in code, (
            "the harness must prune the backend root through the shared helper"
        )

    def test_the_bootstrap_precedes_the_import_and_the_prune_precedes_the_server(self):
        """Ordering guards (reviewer F-5): a source-read test cannot show behaviour,
        but it can pin the order the behaviour depends on.
        """
        code = "\n".join(self._code_lines())
        bootstrap_at = code.index("sys.path.insert(0, str(_BACKEND_DIR))")
        import_at = code.index("from scripts.cleanup_path import prune_pycache_beneath")
        prune_at = code.index("prune_pycache_beneath(_BACKEND_DIR)")
        launch_at = code.index("subprocess.Popen")
        assert bootstrap_at < import_at, "the backend root must be importable first"
        assert prune_at < launch_at, (
            "the bytecode cache must be cleared before the harness starts its server"
        )
