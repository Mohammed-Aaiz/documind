"""
File storage for DocuMind uploads.

Storage layout:
    uploads/{user_id}/{uuid}.{ext}

Features:
    - User-scoped subdirectories
    - UUID-based filenames (no path traversal)
    - Orphan cleanup on failure
    - Root-contained deletion (refuses links and paths outside the upload root)
"""

import os
import stat
import uuid
from pathlib import Path

from config import get_settings

settings = get_settings()


def _user_upload_dir(user_id: str) -> Path:
    """Get or create the upload directory for a specific user."""
    user_dir = settings.upload_path / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def save_upload(file_bytes: bytes, original_name: str, user_id: str) -> Path:
    """Save uploaded file to user-scoped directory.

    Layout: uploads/{user_id}/{uuid}.{validated_ext}

    The filename is always UUID-based. The extension is preserved only
    after validation has confirmed the file type.

    Args:
        file_bytes: Raw file content
        original_name: Original filename (used only for extension extraction)
        user_id: Authenticated user's UUID (from JWT, never from client)

    Returns:
        Path to the saved file
    """
    ext = Path(original_name).suffix.lower()
    safe_name = f"{uuid.uuid4().hex}{ext}"
    user_dir = _user_upload_dir(user_id)
    dest = user_dir / safe_name
    dest.write_bytes(file_bytes)
    return dest


# ---------------------------------------------------------------------------
# Deletion containment
# ---------------------------------------------------------------------------
# This is the application-runtime counterpart of the operational policy in
# ``scripts/cleanup_path.py``: the same intent (only ever delete something that
# is provably inside the upload root, never through a link) enforced where the
# application itself deletes a stored upload.  The primitives are deliberately
# not imported from there -- production code must not depend on the operational
# ``scripts/`` package -- so keep the two implementations in step by hand.
#
# One deliberate difference: ``cleanup_path.intended_root`` also refuses an
# upload root that is itself a symlink or reparse point, because an unattended
# sweep must not operate on a tree it cannot name.  Here the root comes from
# operator configuration rather than from untrusted input, and refusing a
# symlinked ``UPLOAD_DIR`` would break a legitimate deployment, so these helpers
# police the candidate and every ancestor below the root and leave root
# provenance to the operator.  Deletion still lands inside the tree
# ``save_upload`` writes to.

#: Windows file-attribute bit set on reparse points (symlinks *and* junctions).
#: ``Path.is_symlink()`` reports NTFS junctions as ``False``, so the attribute
#: bit is the only way to see them on Windows.
_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400


def _is_link_or_reparse_point(path: Path) -> bool:
    """True if ``path`` is a symlink or a reparse point (e.g. an NTFS junction).

    An unreadable or missing path returns ``False`` here; callers that must fail
    closed also require the path to exist and to be a regular file.
    """
    try:
        if path.is_symlink():
            return True
        info = path.lstat()
    except (OSError, ValueError):
        return False

    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & _FILE_ATTRIBUTE_REPARSE_POINT)


def _resolved_within(root: Path, candidate: Path) -> Path | None:
    """Resolve ``candidate`` and return it only if it sits inside ``root``.

    Containment is decided component-wise on resolved paths, so a sibling that
    merely shares a string prefix (``uploads`` and ``uploads-old``) is not
    accepted.  Returns ``None`` (fail closed) when either path cannot be
    resolved or when the candidate escapes the root.
    """
    try:
        root_resolved = root.resolve(strict=False)
        candidate_resolved = candidate.resolve(strict=False)
        relative = candidate_resolved.relative_to(root_resolved)
    except (OSError, ValueError):
        return None

    if ".." in relative.parts:
        return None
    return candidate_resolved


def _has_link_ancestor(lexical_root: Path, lexical_candidate: Path) -> bool:
    """True if any directory between the root and the candidate is a link.

    Walks the *lexical* absolute path downwards, so a link that would redirect
    the traversal is seen even though the resolved candidate has already left
    the root.  Fails closed when the candidate is not lexically under the root.
    """
    try:
        relative_parent = lexical_candidate.parent.relative_to(lexical_root)
    except ValueError:
        return True

    current = lexical_root
    for part in relative_parent.parts:
        current = current / part
        if _is_link_or_reparse_point(current):
            return True
    return False


def delete_upload(stored_path: Path, *, root: Path | None = None) -> bool:
    """Delete a stored upload file, but only inside the upload root.

    ``root`` is the intended upload root and defaults to the configured one
    (``settings.upload_path``), so existing positional callers are unchanged
    while a caller that has already validated a root can pass it explicitly.

    Defensive: errors are caught rather than raised, so this never masks the
    original application error.  Returns ``True`` only when the file was
    actually deleted, and ``False`` otherwise -- including every deliberate
    refusal.

    A ``False`` return is a *refusal*, not a licence to try harder: deletion is
    refused, and nothing is touched, unless the candidate resolves inside the
    root, is not itself a symlink or reparse point, is not reached through one,
    and ``lstat()`` reports a regular file.  The worst a refusal can do is leave
    an orphan file behind; it can never delete outside the root.  The remaining
    check-then-use window is the same platform limit documented in
    ``scripts/cleanup_path.py`` -- Python exposes no handle-bound
    ``unlink``/``rmdir`` on Windows.
    """
    try:
        candidate = Path(stored_path)
        base = Path(root) if root is not None else settings.upload_path
    except (OSError, TypeError, ValueError):
        return False

    # A stored upload path never legitimately contains a parent reference.  It is
    # refused explicitly rather than left to normalization: ``os.path.abspath``
    # collapses ``..`` textually (it is not symlink-aware), so a ``..`` component
    # would step out of the component sequence the lexical link-ancestor walk
    # below inspects.  The resolved check already contains such a path, but this
    # makes the refusal unconditional and independent of resolution order.
    if ".." in candidate.parts:
        return False

    resolved = _resolved_within(base, candidate)
    if resolved is None:
        return False
    if _is_link_or_reparse_point(candidate) or _is_link_or_reparse_point(resolved):
        return False

    try:
        lexical_root = Path(os.path.abspath(base))
        lexical_candidate = Path(os.path.abspath(candidate))
    except (OSError, ValueError):
        return False
    if _has_link_ancestor(lexical_root, lexical_candidate):
        return False

    try:
        info = candidate.lstat()
    except (OSError, ValueError):
        return False
    if not stat.S_ISREG(info.st_mode):
        return False

    try:
        candidate.unlink()
        return True
    except OSError:
        return False


def cleanup_new_file(file_path: Path, *, root: Path | None = None) -> None:
    """Clean up a newly-created file after DB commit failure.

    This is a defensive cleanup — if it fails, we log but don't raise,
    because the original DB error is more important.

    Unlike the pre-1.6X revision, this no longer unlinks whatever path it is
    handed: it is subject to the same containment rule as :func:`delete_upload`,
    so the file is removed only when it is provably inside the upload root (the
    configured one unless ``root`` says otherwise) and is not a link or reparse
    point.  A refusal leaves an orphan file behind, which is the right failure
    for a rollback helper, and it never deletes outside the root.
    """
    delete_upload(file_path, root=root)
