#!/usr/bin/env python3
"""Find (and optionally delete) uploaded files with no row in the database.

Usage:
    python scripts/cleanup_orphan_uploads.py                      # DRY RUN — report only
    python scripts/cleanup_orphan_uploads.py --delete             # delete orphans (prompts)
    python scripts/cleanup_orphan_uploads.py --delete --yes
    python scripts/cleanup_orphan_uploads.py --delete --yes \
        --archive orphaned_uploads_2026-09-28.zip         # archive first, then delete

The authoritative reference set is `documents.stored_path`, plus
`verification_results.stored_path`. Any file under UPLOAD_DIR whose path is not
in that set is an orphan: the application can never serve it again because no
row points at it.

Safety properties:
    * Dry run by default. Nothing is deleted without --delete.
    * If the database cannot be read, the script ABORTS. It never treats an
      unreachable database as "everything is an orphan".
    * The upload root is validated BEFORE anything is archived or deleted: it
      must not be a symlink/reparse point, and its lexical absolute form must
      identify the same directory as its resolved form. An unsafe root is a
      refusal (exit 1), never a warning.
    * Traversal never follows directory links, links are never deletion
      candidates, and every deletion and every directory prune is re-validated
      against the established root immediately before it runs.
    * --archive writes the orphans into a zip and VERIFIES it (entry count + CRC)
      before a single file is deleted. If the archive cannot be verified, the
      script aborts and deletes nothing.
    * --delete removes orphans and then prunes the directories they leave empty.

Requires the .env file to be configured with DATABASE_URL.

Residual risk (documented, not eliminated): validating a path and then acting on
it are separate operations, so a process that can rewrite the upload tree
concurrently can still win a race. Closing that window needs handle-bound
deletion (O_NOFOLLOW / dir_fd), which is not available for unlink/rmdir on
Windows. The sweep narrows the window to the shortest possible interval and
refuses anything it cannot validate.
"""

import argparse
import asyncio
import os
import sys
import zipfile
from pathlib import Path
from typing import NamedTuple

# Running a file inside scripts/ puts only scripts/ on sys.path, so the backend
# package root (which holds auth/, storage/, ...) must be added explicitly.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from sqlalchemy import select

# Import all models so SQLAlchemy resolves relationships before the first query.
from auth.models import User  # noqa: F401
from chat.models import ChatMessage, ChatSession  # noqa: F401
from documents.models import Document, DocumentChunk  # noqa: F401
from reliability.models import ReliabilityLog, SourceRef  # noqa: F401
from user.models import UserSettings  # noqa: F401
from verification.models import VerificationResult  # noqa: F401

from config import get_settings
from storage.database import async_session

import scripts.cleanup_path as cleanup_path

settings = get_settings()


class _Scan(NamedTuple):
    """Result of a link-safe walk of the upload root."""

    files: list[Path]
    entries: list[Path]
    directories: list[Path]
    skipped_links: list[Path]


def _key(path: str | Path) -> str:
    """Normalise a path to a `user_id/filename` key relative to UPLOAD_DIR.

    Handles Windows separators and a leading ``uploads/`` or ``./`` prefix, so
    ``uploads\\abc\\x.txt`` and ``uploads/abc/x.txt`` compare equal.
    """
    s = str(path).replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    if s.startswith("uploads/"):
        s = s[len("uploads/"):]
    return s.strip("/")


async def _referenced_keys() -> set[str]:
    """Return every path the database still points at."""
    async with async_session() as session:
        doc_paths = (
            await session.execute(select(Document.stored_path))
        ).scalars().all()
        ver_paths = (
            await session.execute(select(VerificationResult.stored_path))
        ).scalars().all()

    keys = {_key(p) for p in [*doc_paths, *ver_paths] if p}
    keys.discard("")
    return keys


def _scan_uploads(root: Path) -> _Scan:
    """Walk ``root`` without following links, returning files, entries and dirs.

    ``followlinks=False`` keeps traversal inside the intended tree; links and
    reparse points are reported separately instead of being silently ignored or
    treated as candidates, so a planted link can never redirect the sweep.
    """
    files: list[Path] = []
    entries: list[Path] = []
    directories: list[Path] = []
    skipped: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        if current == root:
            entries = [current / name for name in sorted([*dirnames, *filenames])]

        kept: list[str] = []
        for name in dirnames:
            child = current / name
            if cleanup_path.is_link_or_reparse_point(child):
                skipped.append(child)
            else:
                kept.append(name)
                directories.append(child)
        dirnames[:] = kept

        for name in filenames:
            child = current / name
            if cleanup_path.is_link_or_reparse_point(child):
                skipped.append(child)
            else:
                files.append(child)

    return _Scan(files, entries, directories, skipped)


def _is_empty_dir(path: Path) -> bool:
    """True if ``path`` is a directory with no entries at all."""
    try:
        return not any(path.iterdir())
    except OSError:
        return False


def _archive_orphans(orphans: list[Path], root: Path, archive: Path) -> bool:
    """Write orphans into a zip and verify it. Returns True only if verified.

    Verification re-opens the finished archive and runs `testzip()` (CRC check
    over every entry) and compares the entry count. Deletion must depend on a
    verified archive, so a failure here returns False and nothing is removed.
    ``root`` is the already-validated intended root.
    """
    if archive.exists():
        print(f"\nABORT: archive already exists, refusing to overwrite: {archive}")
        return False

    if cleanup_path.is_link_or_reparse_point(archive):
        print(f"\nABORT: archive path is a symlink or reparse point: {archive}")
        return False

    if cleanup_path.is_under(root, archive):
        print(f"\nABORT: archive must not be written inside the upload directory: {archive}")
        return False

    unsafe = [
        path for path in orphans
        if not cleanup_path.validate_candidate(root, path, expect="file")
    ]
    if unsafe:
        print(
            f"\nABORT: {len(unsafe)} candidate(s) failed validation; refusing to "
            "archive or delete anything from an unvalidated tree."
        )
        for path in unsafe[:10]:
            print(f"  unsafe  {path}")
        return False

    archive.parent.mkdir(parents=True, exist_ok=True)
    print(f"\nArchiving {len(orphans)} file(s) -> {archive}")

    # STEP 1.6Z: the refusal above is a *check*, and a check is not an exclusive
    # create.  Mode "w" truncates, so a destination planted or substituted in the
    # window between the check and the open was silently replaced and the sweep
    # still deleted its orphans.  The exclusive "x+b" makes the creation itself
    # the refusal -- an existing path, or one that appeared since the check, raises
    # FileExistsError and nothing is archived or deleted -- and, unlike "xb", it
    # leaves the handle readable so the archive can be verified through the very
    # same object that was written.
    try:
        archive_handle = open(archive, "x+b")
    except FileExistsError:
        print(
            f"\nABORT: archive appeared before it could be created, refusing to "
            f"overwrite: {archive}"
        )
        print("Nothing was deleted.")
        return False
    except OSError as exc:
        print(f"\nABORT: cannot create the archive: {archive}: {exc!r}")
        print("Nothing was deleted.")
        return False

    try:
        with zipfile.ZipFile(archive_handle, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(orphans):
                zf.write(path, arcname=str(path.relative_to(root)))
        archive_handle.flush()
        # STEP 1.6Z (E/D): verify through the *same* open handle.  The archive
        # that is verified is then provably the object that was written, whereas
        # re-opening by pathname could name a different file substituted in
        # between.  Creating and verifying through one handle also removes the
        # need for a pathname delete of a failed archive (see below).
        archive_handle.seek(0)
        with zipfile.ZipFile(archive_handle) as zf:
            bad = zf.testzip()
            if bad is not None:
                print(f"ABORT: archive failed CRC verification at entry: {bad}")
                print("Nothing was deleted.")
                return False
            entries = len(zf.namelist())
    except (OSError, zipfile.BadZipFile) as exc:
        # ``BadZipFile`` is caught as well: a corrupt archive must abort with
        # nothing deleted, not propagate after a crash-fragment archive exists.
        print(f"\nABORT: archive write/verification failed: {exc!r}")
        # The archive this process created is incomplete by definition and is
        # deliberately NOT removed.  The only deletion primitive reachable here
        # is a pathname unlink, and an unlink-by-pathname after a failed write is
        # precisely the check-then-use operation this step removes.  Leaving it
        # also makes a silent re-run impossible: the next sweep refuses an
        # existing archive (exit 3) until an operator inspects and removes it.
        print(
            "An incomplete archive is left in place for the operator to "
            f"inspect and remove by hand: {archive}"
        )
        print("Nothing was deleted.")
        return False
    finally:
        archive_handle.close()

    if entries != len(orphans):
        print(f"ABORT: archive has {entries} entries, expected {len(orphans)}")
        return False

    print(f"Archive verified: {entries} entries, {archive.stat().st_size:,} bytes")
    return True


async def run_sweep(delete: bool, assume_yes: bool, archive: Path | None = None) -> int:
    root = settings.upload_path
    print(f"Upload directory: {root}")

    try:
        referenced = await _referenced_keys()
    except Exception as exc:  # noqa: BLE001 - abort rather than mass-delete
        print(f"\nABORT: could not read the database reference set: {exc!r}")
        print("Refusing to treat an unreadable database as 'all files are orphans'.")
        return 2

    print(f"Referenced by the database: {len(referenced)} path(s)")
    for key in sorted(referenced):
        print(f"  ref  {key}")
    if not referenced:
        print("  (the database references no uploaded files at all)")

    if not root.exists():
        print("\nUpload directory does not exist. Nothing to do.")
        return 0

    # --- validate the intended root BEFORE any archive or deletion ----------
    try:
        root = cleanup_path.intended_root(root)
    except RuntimeError as exc:
        print(f"\nABORT: refusing to sweep an unsafe upload root: {exc}")
        print("Nothing was archived and nothing was deleted.")
        return 1

    scan = _scan_uploads(root)

    orphans = [p for p in scan.files if _key(p.relative_to(root)) not in referenced]
    kept = [p for p in scan.files if _key(p.relative_to(root)) in referenced]
    orphan_bytes = sum(p.stat().st_size for p in orphans)

    empty_entries = [d for d in scan.directories if _is_empty_dir(d)]

    print(f"\nOn disk: {len(scan.files)} file(s) in {len(scan.entries)} top-level entr(ies)")
    print(f"  referenced: {len(kept)}")
    print(f"  ORPHANED:   {len(orphans)}  ({orphan_bytes:,} bytes, "
          f"{orphan_bytes / 1024 / 1024:.2f} MB)")
    print(f"  empty dirs: {len(empty_entries)}")
    if scan.skipped_links:
        print(f"  skipped links/reparse points (never deleted): {len(scan.skipped_links)}")
        for path in scan.skipped_links[:10]:
            print(f"    link  {path}")

    if orphans:
        print("\nOrphaned files:")
        for p in sorted(orphans):
            print(f"  orphan  {_key(p.relative_to(root))}  ({p.stat().st_size:,} B)")

    if not delete:
        print("\nDRY RUN — nothing was deleted. Re-run with --delete to remove the orphans.")
        return 0

    if not orphans and not empty_entries:
        print("\nNothing to delete.")
        return 0

    if not assume_yes:
        answer = input(
            f"\nDelete {len(orphans)} orphaned file(s) "
            f"({orphan_bytes / 1024 / 1024:.2f} MB) and prune empty directories? [y/N] "
        ).strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted. Nothing was deleted.")
            return 1

    if archive is not None and orphans:
        if not _archive_orphans(orphans, root, archive):
            print("Nothing was deleted.")
            return 3

    # Final re-validation of the root immediately before the destructive phase.
    try:
        cleanup_path.forbid_symlink_roots(root)
    except RuntimeError as exc:
        print(f"\nABORT: upload root is no longer safe: {exc}")
        print("Nothing was deleted.")
        return 1

    # STEP 1.6Z: on POSIX, hold a descriptor to the validated root so every
    # deletion is bound to the *directory object* instead of being re-resolved by
    # pathname.  A parent or the root swapped between validation and the delete
    # can then no longer redirect the operation.  Windows offers no such
    # primitive, so ``root_fd`` is None there and the pathname flow below keeps
    # its documented check-then-use residual.
    #
    # A root that cannot be held on a platform that supports holding one is an
    # abort, never a silent fall back to pathname deletes: that is exactly the
    # situation (root swapped, permissions changed, I/O error) in which the
    # guard must stay up.
    try:
        root_fd = cleanup_path.open_root_fd(root)
    except RuntimeError as exc:
        print(f"\nABORT: cannot hold the validated upload root: {exc}")
        print("Refusing to fall back to pathname deletions.")
        print("Nothing was deleted.")
        return 1

    deleted = 0
    freed = 0
    refused = 0
    for path in orphans:
        # Never leave the upload root, never follow a link, never touch a
        # referenced file.  Re-validated per candidate, immediately before use.
        if not cleanup_path.validate_candidate(root, path, expect="file"):
            print(f"  SKIP (failed containment validation): {path}")
            refused += 1
            continue
        if _key(path.relative_to(root)) in referenced:
            print(f"  SKIP (referenced): {path}")
            continue
        try:
            size = path.stat().st_size
            relative = path.relative_to(root)
        except (OSError, ValueError) as exc:
            print(f"  SKIP (cannot measure candidate): {path}: {exc!r}")
            refused += 1
            continue

        outcome = (
            cleanup_path.unlink_beneath(root_fd, relative)
            if root_fd is not None
            else "unsupported"
        )
        if outcome == "unsupported":
            # No descriptor-relative primitive on this platform: the pathname
            # flow, which is the documented residual of this step.
            try:
                path.unlink()
            except OSError as exc:
                print(f"  SKIP (unlink failed): {path}: {exc!r}")
                refused += 1
                continue
        elif outcome != "unlinked":
            # "refused" (fail closed) or "failed": never fall back to a
            # pathname delete after the descriptor-relative attempt declined.
            print(f"  SKIP (descriptor-relative delete {outcome}): {path}")
            refused += 1
            continue
        deleted += 1
        freed += size

    # Prune directories that are now empty, deepest first.  Each directory is
    # validated individually: pruning has its own containment check.
    pruned = 0
    for path in sorted(scan.directories, key=lambda p: len(p.parts), reverse=True):
        if not cleanup_path.validate_candidate(root, path, expect="directory"):
            print(f"  SKIP (not a safe prune candidate): {path}")
            refused += 1
            continue
        try:
            if any(path.iterdir()):
                continue
            relative = path.relative_to(root)
        except (OSError, ValueError) as exc:
            print(f"  SKIP (cannot inspect prune candidate): {path}: {exc!r}")
            continue

        outcome = (
            cleanup_path.rmdir_beneath(root_fd, relative)
            if root_fd is not None
            else "unsupported"
        )
        if outcome == "unlinked":
            pruned += 1
            continue
        if outcome == "unsupported":
            try:
                path.rmdir()
                pruned += 1
            except OSError as exc:
                print(f"  SKIP (rmdir failed): {path}: {exc!r}")
            continue
        print(f"  SKIP (descriptor-relative prune {outcome}): {path}")

    cleanup_path.close_root_fd(root_fd)

    print(f"\nDeleted {deleted} file(s), freed {freed:,} bytes "
          f"({freed / 1024 / 1024:.2f} MB). Pruned {pruned} empty director(ies).")
    if refused:
        print(f"Refused {refused} unsafe candidate(s); see the SKIP lines above.")

    # Verify.
    remaining = _scan_uploads(root)
    remaining_orphans = [
        p for p in remaining.files if _key(p.relative_to(root)) not in referenced
    ]
    print(f"Verification: {len(remaining.files)} file(s) remain, "
          f"{len(remaining_orphans)} still orphaned.")
    return 0 if not remaining_orphans and not refused else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep orphaned uploads")
    parser.add_argument(
        "--delete", action="store_true", help="Actually delete orphans (default: dry run)"
    )
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    parser.add_argument(
        "--archive",
        type=Path,
        default=None,
        help="Zip the orphans here and verify it BEFORE deleting (recommended)",
    )
    args = parser.parse_args()

    raise SystemExit(asyncio.run(run_sweep(args.delete, args.yes, args.archive)))


if __name__ == "__main__":
    main()
