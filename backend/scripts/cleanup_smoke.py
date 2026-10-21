#!/usr/bin/env python3
"""Remove a test user, their documents/chunks and their uploaded files.

Usage:
    python scripts/cleanup_smoke.py
    python scripts/cleanup_smoke.py --email smoke@test.com
    python scripts/cleanup_smoke.py --email smoke@test.com --yes

Deletes, in order:
    1. the uploaded files referenced by the user's ``documents.stored_path``
    2. the user's ``documents`` rows (chunks cascade via FK)
    3. the ``users`` row (chat sessions/messages, settings, reliability
       logs and verification results cascade via FK)

Rows belonging to other users are never touched. Requires the .env file to
be configured with DATABASE_URL.

Safety properties (applied through ``scripts.cleanup_path``, the same policy
``cleanup_orphan_uploads.py`` uses):

    * The upload root is validated BEFORE any filesystem side effect -- and
      before the confirmation prompt -- by ``cleanup_path.intended_root``: it
      must not be a symlink or reparse point, and its lexical absolute form
      must identify the same directory as its resolved form.  An unsafe root
      is a refusal (exit non-zero); no file and no row is touched.
    * A recorded ``stored_path`` is not trusted input.  It is resolved inside
      the validated root, and every candidate is re-validated immediately
      before it is deleted: nothing outside the root, and no link or reparse
      point, is ever followed or deleted.  A value that escapes the root is
      refused and reported, never deleted.
    * The per-user upload directory is validated as a directory inside the
      root and is pruned only when it is empty.  A failed prune is reported
      rather than silently swallowed (the previous ``rmtree(ignore_errors=
      True)`` could not distinguish success from failure).
    * Refusals and partial failures are counted, printed, and make the script
      exit non-zero instead of reporting a clean success.
    * On POSIX the removal and the prune are performed relative to a descriptor
      held on the validated root (``cleanup_path.unlink_beneath`` /
      ``rmdir_beneath``), so replacing the root or a parent directory between
      validation and the syscall can no longer redirect them.  Where no such
      primitive exists (Windows) the pathname flow is used, and a
      descriptor-relative attempt that declines is reported as a refusal rather
      than retried by pathname.

Residual risk (documented, not eliminated): validating a path and then acting
on it are separate operations, so a process that can rewrite the upload tree
concurrently can still win a check-then-use race.  On POSIX that window is
narrowed to the final *name* inside the already-opened directory -- bounded to
the validated directory, and not escaped -- because the standard library
exposes no primitive binding a name to an earlier ``lstat``.  On Windows the
pathname flow is unchanged: the standard library does not expose handle-bound
``unlink``/``rmdir`` there at all.  See ``scripts/cleanup_path.py``.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Sequence

# Running a file inside scripts/ puts only scripts/ on sys.path, so the backend
# package root (which holds auth/, storage/, ...) must be added explicitly.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from sqlalchemy import delete, func, select

# Import all models so SQLAlchemy resolves relationships
from auth.models import User  # noqa: F401
from documents.models import Document, DocumentChunk  # noqa: F401
from chat.models import ChatSession, ChatMessage  # noqa: F401
from verification.models import VerificationResult  # noqa: F401
from reliability.models import ReliabilityLog, SourceRef  # noqa: F401
from user.models import UserSettings  # noqa: F401
from storage.database import async_session
from storage.file_store import delete_upload
from config import get_settings

import scripts.cleanup_path as cleanup_path

settings = get_settings()


def resolve_stored_path(stored_path: str, root: Path) -> Path | None:
    """Resolve a recorded ``stored_path`` to a location safely inside ``root``.

    ``stored_path`` values are written by ``storage.file_store.save_upload`` as
    ``uploads/<user_id>/<uuid>.<ext>``, relative to the process working
    directory (``backend/``), but a database row is not trusted input: it can
    hold an absolute path, an ``uploads/``-prefixed value, or something that
    escapes the root through ``..`` or a planted link.

    Returns the candidate inside ``root`` when it is safe to consider: either
    an existing regular file that passes ``cleanup_path.validate_candidate``,
    or a path inside ``root`` that does not exist at all (the caller reports
    that as "already absent").  Returns ``None`` -- never a path to act on --
    when the recorded value resolves outside ``root``, when it is reached
    through a symlink or reparse point, or when it exists as something other
    than a regular file.

    ``root`` must already have been validated by ``cleanup_path.intended_root``.

    Example: with ``root=Path("/srv/uploads")``, ``"uploads/ab/x.pdf"`` and
    ``"./uploads/ab/x.pdf"`` both resolve to ``/srv/uploads/ab/x.pdf``, while
    ``"/etc/passwd"`` and ``"../../etc/passwd"`` resolve to ``None``.
    """
    raw = str(stored_path).replace("\\", "/").strip()
    if not raw:
        return None

    recorded = Path(raw)
    if recorded.is_absolute():
        candidate = recorded
    else:
        while raw.startswith("./"):
            raw = raw[2:]
        if raw.startswith("uploads/"):
            raw = raw[len("uploads/"):]
        candidate = root / raw

    if not cleanup_path.is_under(root, candidate):
        return None

    if cleanup_path.validate_candidate(root, candidate, expect="file"):
        return candidate

    # Not an existing regular file.  Only a genuinely absent path may be
    # returned; a link, a directory, a special file, or anything whose
    # resolved form leaves the root is refused.
    if candidate.exists() or not cleanup_path.is_under(root, candidate):
        return None
    return candidate


def delete_upload_files(root: Path, stored_paths: Sequence[str]) -> tuple[int, int, int]:
    """Delete the files named by ``stored_paths``, inside ``root`` only.

    Returns ``(deleted, missing, refused)``.  ``root`` must already have been
    validated by ``cleanup_path.intended_root``.  Each value is resolved by
    :func:`resolve_stored_path` and the deletion itself re-validates the
    candidate against the held root immediately before the unlink, so a value
    that escapes the root -- or a candidate that has been replaced by a link
    since it was scanned -- is refused rather than deleted.

    On POSIX the removal is performed by ``cleanup_path.unlink_beneath`` against
    a descriptor opened on the validated root, so a parent directory or the root
    swapped between validation and the delete can no longer redirect it.  Where
    that primitive does not exist (Windows) the pathname flow below is used, with
    its documented check-then-use residual.  A descriptor-relative attempt that
    declines is never retried by pathname: the candidate is reported as refused.
    """
    deleted = 0
    missing = 0
    refused = 0

    try:
        root_fd = cleanup_path.open_root_fd(root)
    except RuntimeError as exc:
        # The platform offers descriptor-relative deletion but the validated root
        # could not be held.  Falling back to a pathname delete here would lower
        # the guard exactly when the tree looks wrong, so every candidate is
        # refused instead and nothing is deleted.
        print(f"  REFUSED (cannot hold the validated upload root): {exc}")
        return 0, 0, len(stored_paths)

    for stored_path in stored_paths:
        resolved = resolve_stored_path(stored_path, root)
        if resolved is None:
            print(f"  SKIP (failed containment validation): {stored_path!r}")
            refused += 1
            continue
        if not resolved.exists():
            missing += 1
            print(f"File already absent: {resolved}")
            continue

        if root_fd is None:
            outcome = "unsupported"
        else:
            try:
                relative = resolved.relative_to(root)
            except ValueError:
                # Cannot be expressed relative to the held root: refuse rather
                # than fall through to a pathname delete.
                outcome = "refused"
            else:
                outcome = cleanup_path.unlink_beneath(root_fd, relative)

        if outcome == "unsupported":
            # No descriptor-relative primitive on this platform: the pathname
            # flow, which is the documented residual of this step.
            if delete_upload(resolved, root=root):
                deleted += 1
                print(f"Deleted file: {resolved}")
            else:
                refused += 1
                print(f"  SKIP (refused by the upload-root guard): {resolved}")
        elif outcome == "unlinked":
            deleted += 1
            print(f"Deleted file: {resolved}")
        else:
            # "refused" (fail closed) or "failed".  Never retry by pathname.
            refused += 1
            print(f"  SKIP (descriptor-relative delete {outcome}): {resolved}")

    cleanup_path.close_root_fd(root_fd)
    return deleted, missing, refused


def prune_user_dir(root: Path, user_id) -> bool:
    """Remove the per-user upload directory, if it is safe and empty.

    Returns True only when the directory was validated inside ``root``, proved
    empty, and removed.  A directory that is missing, not empty, outside the
    root, a link or reparse point, or that cannot be removed returns False so
    the caller can report the failure instead of swallowing it.

    As in :func:`delete_upload_files`, POSIX removes the directory relative to a
    descriptor held on the validated root -- so a swapped parent or root cannot
    redirect the ``rmdir`` -- and Windows uses the pathname call with its
    documented residual.
    """
    user_dir = root / str(user_id)
    if not cleanup_path.validate_candidate(root, user_dir, expect="directory"):
        return False

    try:
        root_fd = cleanup_path.open_root_fd(root)
    except RuntimeError as exc:
        # Same rule as delete_upload_files: a root that cannot be held on a
        # platform that supports holding one is a refusal, not a pathname retry.
        print(f"  SKIP (cannot hold the validated upload root): {exc}")
        return False

    try:
        if any(user_dir.iterdir()):
            return False

        if root_fd is not None:
            try:
                relative = user_dir.relative_to(root)
            except ValueError:
                return False
            return cleanup_path.rmdir_beneath(root_fd, relative) == "unlinked"

        user_dir.rmdir()
        return True
    except OSError:
        return False
    finally:
        cleanup_path.close_root_fd(root_fd)


async def cleanup(email: str, assume_yes: bool) -> int:
    # --- the upload root is validated BEFORE any filesystem side effect ------
    try:
        upload_root = cleanup_path.intended_root(settings.upload_path)
    except RuntimeError as exc:
        print(f"ABORT: refusing to delete files under an unsafe upload root: {exc}")
        print("Nothing was deleted.")
        return 1

    async with async_session() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()

        if user is None:
            print(f"No user found with email {email!r}. Nothing to clean up.")
            return 0

        user_id = user.id

        documents = (
            await session.execute(
                select(Document).where(Document.user_id == user_id)
            )
        ).scalars().all()

        doc_ids = [doc.id for doc in documents]
        stored_paths = [doc.stored_path for doc in documents]

        chunk_count = 0
        if doc_ids:
            chunk_count = (
                await session.execute(
                    select(func.count())
                    .select_from(DocumentChunk)
                    .where(DocumentChunk.document_id.in_(doc_ids))
                )
            ).scalar_one()

        print(f"User:      {email} (id={user_id})")
        print(f"Upload root (validated): {upload_root}")
        print(f"Documents: {len(documents)}")
        print(f"Chunks:    {chunk_count}")
        for doc in documents:
            print(f"  - {doc.name} (id={doc.id}, path={doc.stored_path})")

        if not assume_yes:
            answer = input("Delete these rows and files? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                print("Aborted. Nothing was deleted.")
                return 1

        # 1. Files first — the DB rows are the only record of where they live.
        #    Every candidate is re-validated against `upload_root` right before
        #    it is deleted; see delete_upload_files.
        deleted_files, missing_files, refused_files = delete_upload_files(
            upload_root, stored_paths
        )

        # 2. Documents (chunks cascade via FK).
        if doc_ids:
            await session.execute(
                delete(Document).where(Document.id.in_(doc_ids))
            )

        # 3. User (everything else cascades via FK).
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()

        print(f"\nDeleted {len(doc_ids)} document row(s), {chunk_count} chunk row(s), 1 user row.")
        print(
            f"Deleted {deleted_files} file(s); {missing_files} already absent; "
            f"{refused_files} refused (outside the upload root or replaced by a link)."
        )
        if refused_files:
            print("WARNING: some stored files were refused and were NOT deleted.")

    # 4. Drop the now-empty per-user upload directory, if it is safe to.
    user_dir = upload_root / str(user_id)
    if prune_user_dir(upload_root, user_id):
        print(f"Removed empty upload directory: {user_dir}")
    elif user_dir.exists():
        print(f"Left upload directory in place (not an empty, safe directory): {user_dir}")

    # 5. Verify the smoke data is gone.
    async with async_session() as session:
        remaining_user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        remaining_docs = (
            await session.execute(
                select(func.count())
                .select_from(Document)
                .where(Document.user_id == user_id)
            )
        ).scalar_one()
        remaining_chunks = (
            await session.execute(
                select(func.count())
                .select_from(DocumentChunk)
                .where(DocumentChunk.document_id.in_(doc_ids or []))
            )
        ).scalar_one()

    print("\nVerification:")
    print(f"  user rows remaining:     {0 if remaining_user is None else 1}")
    print(f"  document rows remaining: {remaining_docs}")
    print(f"  chunk rows remaining:    {remaining_chunks}")

    if (
        remaining_user is None
        and remaining_docs == 0
        and remaining_chunks == 0
        and not refused_files
    ):
        print("\nCleanup complete.")
        return 0

    if refused_files:
        print(
            f"\nWARNING: {refused_files} stored file(s) were refused by the "
            "upload-root guard and were NOT deleted — inspect manually."
        )
    if remaining_user is not None or remaining_docs or remaining_chunks:
        print("\nWARNING: residual rows detected — inspect manually.")
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean up a test user and their data")
    parser.add_argument("--email", default="smoke@test.com", help="User email")
    parser.add_argument(
        "--yes", action="store_true", help="Skip the confirmation prompt"
    )
    args = parser.parse_args()

    raise SystemExit(asyncio.run(cleanup(args.email, args.yes)))


if __name__ == "__main__":
    main()
