"""Path-containment helpers for operational cleanup scripts.

These functions are used by ``scripts/cleanup_orphan_uploads.py`` so that
orphan sweeping stays inside the configured upload root, never follows
symlink escape, and refuses to operate on files it cannot place under the
upload root.

They are filesystem helpers.  The inspection helpers never delete anything.
The descriptor-relative helpers added in Step 1.6Z
(:func:`unlink_beneath`, :func:`rmdir_beneath`) remove exactly one named entry
beneath an already-open root descriptor, bind that removal to the directory
object they opened, and never fall back to a pathname delete.  None of these
functions opens a database connection.

Remediation notes (unified safety remediation):

* ``forbid_symlink_roots`` previously compared ``root.resolve(strict=False)``
  with a value assigned from that same expression, so the two operands were
  always equal and the refusal could never fire.  It now derives the intended
  root from two *independent* values -- the lexical absolute form
  (``os.path.abspath``) and the resolved filesystem form -- and refuses when
  they disagree, when the root is itself a link or reparse point, or when the
  root cannot be resolved.
* ``filesystem_supports_relative_symlinks`` was removed.  It returned a
  constant ``True`` and the sweep never uses relative symlinks, so the
  import-time gate built on it could only ever be decorative (and made
  importing the module environment-dependent).
* ``is_under`` decides containment component-wise on resolved paths instead of
  comparing resolved text with a string prefix.
* ``validate_candidate`` is the single containment check applied immediately
  before *every* deletion and *every* directory prune.

Platform limits are documented rather than papered over: resolving paths and
re-checking each candidate narrows, but cannot eliminate, a check-then-use
window against a concurrent process.  Closing it needs handle-bound
operations (``O_NOFOLLOW`` / ``dir_fd``), which the standard library does not
expose for ``unlink``/``rmdir`` on Windows.

Step 1.6Z addition -- descriptor-relative deletion (POSIX only):

* **What it closes.**  :func:`unlink_beneath` and :func:`rmdir_beneath` descend
  from an already-opened root descriptor one component at a time, opening every
  intermediate directory with ``O_NOFOLLOW``, and then call
  ``os.unlink(name, dir_fd=...)`` / ``os.rmdir(name, dir_fd=...)``.  The delete
  is bound to the *directory object* that was opened, so neither the root nor
  any parent directory can be redirected elsewhere between validation and the
  syscall.  A pathname-based check followed by a pathname-based delete cannot
  make that claim.
* **What it does NOT close.**  The final *name* can still be swapped for a
  different object **inside that same, already-validated directory** between the
  caller's validation and this call, because the standard library exposes no
  primitive that binds a name to an earlier ``lstat``.  The consequence is
  bounded to that directory -- it is not an escape from the root -- and it is
  documented here rather than claimed fixed.
* **Availability.**  This requires POSIX dir-fd support
  (``os.unlink in os.supports_dir_fd``).  Windows exposes no equivalent
  primitive, so the scripts keep their pathname-based flow with the residual
  above; that is why unattended destructive cleanup remains NO-GO on both
  platforms until a platform-verified mitigation exists.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

#: Windows file-attribute bit set on reparse points (symlinks *and* junctions).
#: ``Path.is_symlink()`` reports NTFS junctions as ``False``, so the attribute
#: bit is the only way to see them on Windows.
FILE_ATTRIBUTE_REPARSE_POINT = 0x0400


def is_link_or_reparse_point(path: Path) -> bool:
    """Return True if ``path`` is a symlink or a reparse point (e.g. a junction).

    A path that does not exist, or that cannot be inspected, returns ``False``
    here.  Callers that must fail closed also require the path to exist and to
    be of the expected type -- :func:`validate_candidate` does both.
    """
    try:
        if path.is_symlink():
            return True
        info = path.lstat()
    except (OSError, ValueError):
        return False

    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & FILE_ATTRIBUTE_REPARSE_POINT)


def _normalized(path: Path) -> str:
    """Platform-normalized absolute form, used for identity comparison only."""
    return os.path.normcase(os.path.normpath(str(path)))


def intended_root(root: Path | str) -> Path:
    """Establish the single intended cleanup root, or refuse.

    Three values are kept strictly distinct:

    * the *configured* path, exactly as supplied;
    * its *lexical absolute* form -- ``os.path.abspath``, which performs no
      filesystem access and follows no link;
    * its *resolved* form -- the real directory that traversal would touch.

    The root is accepted only when it is not a link or reparse point, its
    lexical absolute form and its resolved form identify the same directory,
    and it exists as a directory.  That comparison is meaningful because the
    two operands come from different operations; comparing one derivation with
    itself -- the previous behaviour -- could never reject anything.

    A missing or unresolvable root is a refusal, not a pass: the destructive
    path must never treat "cannot tell" as "safe".

    Raises ``RuntimeError`` for every refusal so callers fail closed.
    """
    configured = Path(root)

    try:
        absolute = Path(os.path.abspath(configured))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"cannot make upload root absolute: {configured!r}") from exc

    if is_link_or_reparse_point(configured) or is_link_or_reparse_point(absolute):
        raise RuntimeError(
            f"upload root is a symlink and cannot be used safely: {configured!r}"
        )

    try:
        resolved = configured.resolve(strict=True)
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"cannot resolve upload root: {configured!r}") from exc

    if _normalized(absolute) != _normalized(resolved):
        raise RuntimeError(
            "upload root is a symlink (or resolves elsewhere) and cannot be used "
            f"safely: {configured!r} resolves to {resolved!r}"
        )

    if not resolved.is_dir():
        raise RuntimeError(f"upload root is not a directory: {configured!r}")

    return resolved


def forbid_symlink_roots(root: Path) -> None:
    """Refuse to operate on an upload root that is itself a symlink.

    A symlinked upload root can point outside the intended directory tree, so
    ``cleanup_orphan_uploads.py`` calls this before it touches any files.  The
    public name is preserved; the work is delegated to :func:`intended_root` so
    exactly one implementation validates a root.
    """
    intended_root(root)


def is_under(root: Path, path: Path) -> bool:
    """Return True if ``path`` resolves to ``root`` itself or something inside it.

    Containment is decided on resolved paths, component by component, and any
    ``..`` component is rejected.  A string-prefix comparison on resolved text
    is not sufficient: distinct paths can share a prefix (``/srv/root`` and
    ``/srv/root-sibling``) without either containing the other.
    """
    try:
        root_resolved = root.resolve(strict=False)
        path_resolved = path.resolve(strict=False)
    except (OSError, ValueError):
        return False

    try:
        relative = path_resolved.relative_to(root_resolved)
    except ValueError:
        return False

    return ".." not in relative.parts


def _has_link_ancestor(root: Path, candidate: Path) -> bool:
    """True if any directory between ``root`` and ``candidate`` is a link.

    Walks the *lexical* path from ``root`` downwards, so a link that redirects
    the traversal is seen even though the resolved candidate has already left
    the root.  Fails closed when the candidate is not lexically under ``root``.
    """
    try:
        relative_parent = candidate.parent.relative_to(root)
    except ValueError:
        return True

    current = root
    for part in relative_parent.parts:
        current = current / part
        if is_link_or_reparse_point(current):
            return True
    return False


def validate_candidate(root: Path, candidate: Path, *, expect: str = "file") -> bool:
    """True only if ``candidate`` is a real file/directory safely inside ``root``.

    Called immediately before every destructive operation.  Every failure mode
    returns ``False`` (fail closed): outside the root, reached through a link,
    a link or reparse point itself, missing, unreadable, or of the wrong type.

    ``expect`` selects the required type: ``"file"`` requires ``S_ISREG``
    (deletion) and ``"directory"`` requires ``S_ISDIR`` (pruning).
    """
    if expect not in ("file", "directory"):
        raise ValueError(f"unsupported candidate expectation: {expect!r}")

    if not is_under(root, candidate):
        return False
    if is_link_or_reparse_point(candidate):
        return False
    if _has_link_ancestor(root, candidate):
        return False

    try:
        info = candidate.lstat()
    except (OSError, ValueError):
        return False

    if expect == "file":
        return stat.S_ISREG(info.st_mode)
    return stat.S_ISDIR(info.st_mode)


# ---------------------------------------------------------------------------
# Descriptor-relative deletion (POSIX)
# ---------------------------------------------------------------------------
# These helpers exist to remove the gap between "validate this path" and "delete
# this path".  They never fall back to a pathname delete: when the platform or
# the descriptor is unavailable they report "unsupported" and delete nothing.

#: True only where the standard library can unlink/rmdir relative to a directory
#: descriptor.  ``rmdir`` and ``open`` support are re-checked at call time.
POSIX_DIR_FD_SUPPORTED: bool = (
    os.name == "posix"
    and hasattr(os, "supports_dir_fd")
    and os.unlink in os.supports_dir_fd
)


def open_root_fd(root: Path) -> int | None:
    """Hold the validated root as a directory descriptor.

    Returns ``None`` **only** when the platform cannot provide a
    descriptor-relative delete at all (Windows, or a POSIX build without
    ``dir_fd`` support); the caller then uses the pathname flow, whose residual
    risk is documented in the module docstring.

    When the platform *does* support it, a root that cannot be held raises
    ``RuntimeError`` instead of returning ``None``.  Collapsing "unsupported"
    and "the root could not be opened" into one value let a caller fall back to
    a pathname delete after the safe root had become unopenable (a root swapped
    for a symlink between validation and this call, or a permission change): the
    guard would have been lowered exactly when the tree looked wrong.  Callers
    must refuse in that case, never retry by pathname.

    ``O_DIRECTORY`` rejects a non-directory and ``O_NOFOLLOW`` refuses a root
    that is a symlink at the moment of opening, so the descriptor refers to the
    real directory.
    """
    if not POSIX_DIR_FD_SUPPORTED:
        return None
    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        return None

    try:
        return os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        raise RuntimeError(
            "cannot hold the upload root for descriptor-relative deletion: "
            f"{root!r}: {exc!r}"
        ) from exc


def prune_pycache_beneath(root: Path | str) -> tuple[int, list[str]]:
    """Remove every real ``__pycache__`` directory inside ``root``; never follow a link.

    Returns ``(removed, refused)``: the number of ``__pycache__`` directories that
    were actually removed, and one message per refusal.  A candidate is removed
    only when :func:`validate_candidate` proves it is a real directory inside
    ``root`` (contained, not a link or reparse point, not reached through one), and
    the removal itself walks the tree refusing any link or reparse point it finds.
    Nothing outside ``root`` is ever touched.

    This replaces an ``shutil.rmtree(..., ignore_errors=True)`` sweep that had
    none of those properties: it recursed wherever the name pointed (a
    ``__pycache__`` replaced by a junction was followed and its target emptied)
    and swallowed every failure.  STEP 1.6AA, finding C.

    The root itself is established with :func:`intended_root`, so a missing root,
    a root that is a link or reparse point, and a root whose lexical and resolved
    forms disagree are all refusals (``RuntimeError``) rather than a sweep of
    whatever the name points at.  ``Path.is_dir()`` alone would have followed a
    linked root into its target.
    """
    root = intended_root(root)

    refused: list[str] = []

    def _remove_validated_tree(directory: Path) -> bool:
        """Depth-first removal; every entry is classified from a single ``lstat``.

        The type *and* the reparse attribute come from one ``lstat``, so the entry
        that is classified is the entry that is acted on, and a directory link is
        refused rather than traversed.  A ``rename`` that swaps an entry after that
        ``lstat`` and before the ``unlink``/``rmdir`` is still possible -- the same
        residual the module documents for every pathname delete, not a guarantee.
        """
        try:
            entries = sorted(directory.iterdir())
        except OSError as exc:
            refused.append(f"{directory}: cannot list: {exc!r}")
            return False
        for entry in entries:
            try:
                info = os.lstat(entry)
            except OSError as exc:
                refused.append(f"{entry}: cannot inspect: {exc!r}")
                return False
            if stat.S_ISLNK(info.st_mode) or (
                getattr(info, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT
            ):
                refused.append(f"{entry}: link or reparse point, not followed")
                return False
            try:
                if stat.S_ISDIR(info.st_mode):
                    if not _remove_validated_tree(entry):
                        return False
                else:
                    os.unlink(entry)
            except OSError as exc:
                refused.append(f"{entry}: {exc!r}")
                return False
        try:
            os.rmdir(directory)
        except OSError as exc:
            refused.append(f"{directory}: {exc!r}")
            return False
        return True

    removed = 0
    for dirpath, dirnames, _files in os.walk(root, topdown=True, followlinks=False):
        if "__pycache__" not in dirnames:
            continue
        candidate = Path(dirpath) / "__pycache__"
        # Never descend into it through os.walk: the removal below is the one that
        # proves what it is removing.
        dirnames.remove("__pycache__")
        if not validate_candidate(root, candidate, expect="directory"):
            refused.append(
                f"{candidate}: failed containment or link/reparse-point validation"
            )
            continue
        if _remove_validated_tree(candidate):
            removed += 1

    return removed, refused


def close_root_fd(fd: int | None) -> None:
    """Close a descriptor from :func:`open_root_fd`, ignoring an already-closed fd."""
    if fd is None:
        return
    try:
        os.close(fd)
    except OSError:
        pass


def _relative_parts(relative: Path) -> tuple[str, ...] | None:
    """Split a root-relative value into plain components, or return ``None``.

    ``None`` means refuse: an empty value, an absolute or drive-rooted path
    (``/etc/passwd``, ``C:\\x``, a UNC root), any ``..`` component, or a
    component carrying a drive marker or NUL.  The result can therefore be
    used as a sequence of single path components below a directory descriptor,
    on any platform -- which is what makes the refusal logic testable on
    Windows even though the deletion itself is not.
    """
    raw = str(relative).replace("\\", "/").strip()
    if not raw:
        return None

    candidate = Path(raw)
    try:
        rooted = bool(candidate.root)
        absolute = candidate.is_absolute()
    except (OSError, ValueError):
        return None
    if rooted or absolute:
        return None

    parts = tuple(part for part in raw.split("/") if part not in ("", "."))
    if not parts:
        return None
    if any(part == ".." or ":" in part or "\x00" in part for part in parts):
        return None
    return parts


def _descend_to_parent(root_fd: int, parts: tuple[str, ...]) -> tuple[int, str] | None:
    """Open the final parent directory below ``root_fd``; return ``(fd, name)``.

    Every intermediate component is opened relative to the previous descriptor
    with ``O_NOFOLLOW``, so a component that has already been opened is never
    re-resolved from a pathname.  The returned descriptor is **always owned by
    the caller** (the root descriptor is duplicated when there is nothing to
    descend), and ``None`` means the descent was refused -- the caller must not
    fall back to a pathname delete.
    """
    current_fd: int | None = None
    try:
        current_fd = os.dup(root_fd)
        for part in parts[:-1]:
            try:
                next_fd = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=current_fd,
                )
            except (OSError, ValueError, TypeError):
                close_root_fd(current_fd)
                return None
            close_root_fd(current_fd)
            current_fd = next_fd
        return current_fd, parts[-1]
    except (OSError, ValueError, TypeError):
        close_root_fd(current_fd)
        return None


def unlink_beneath(root_fd: int | None, relative: Path) -> str:
    """Unlink ``relative`` beneath an already-open root descriptor.

    Every component below the root is opened with ``O_NOFOLLOW`` relative to the
    previous descriptor, and the final ``os.unlink`` is descriptor-relative, so
    the operation cannot be redirected by replacing the root or a parent
    directory after validation.  There is no pathname-based unlink in this
    function and no fallback to one.

    Returns exactly one of:

    * ``"unlinked"`` -- the name was removed from the held directory;
    * ``"unsupported"`` -- no descriptor or no dir-fd support; nothing was done;
    * ``"refused"`` -- the value was unsafe, a component was a link or not a
      directory, or the name was already gone (fail closed, nothing deleted);
    * ``"failed"`` -- the syscall itself failed (for example the name is a
      directory, or permissions forbid it); nothing else was touched.

    Residual, documented rather than fixed: the final *name* may still have been
    swapped for a different object inside the same held directory, because no
    standard-library primitive binds a name to an earlier ``lstat``.  The
    consequence stays inside the validated directory.
    """
    if root_fd is None or not POSIX_DIR_FD_SUPPORTED:
        return "unsupported"

    parts = _relative_parts(relative)
    if parts is None:
        return "refused"

    descended = _descend_to_parent(root_fd, parts)
    if descended is None:
        return "refused"

    parent_fd, name = descended
    try:
        os.unlink(name, dir_fd=parent_fd)
    except FileNotFoundError:
        return "refused"
    except OSError:
        return "failed"
    finally:
        close_root_fd(parent_fd)
    return "unlinked"


def rmdir_beneath(root_fd: int | None, relative: Path) -> str:
    """Remove the empty directory ``relative`` beneath an open root descriptor.

    The same component-wise descent and the same descriptor-relative final
    operation as :func:`unlink_beneath`, ending in ``os.rmdir(name, dir_fd=...)``.
    A non-empty directory is reported as ``"failed"`` and is never recursed
    into.  Return values are exactly those of :func:`unlink_beneath`.
    """
    if root_fd is None or not POSIX_DIR_FD_SUPPORTED:
        return "unsupported"
    if not hasattr(os, "rmdir") or os.rmdir not in getattr(os, "supports_dir_fd", set()):
        return "unsupported"

    parts = _relative_parts(relative)
    if parts is None:
        return "refused"

    descended = _descend_to_parent(root_fd, parts)
    if descended is None:
        return "refused"

    parent_fd, name = descended
    try:
        os.rmdir(name, dir_fd=parent_fd)
    except FileNotFoundError:
        return "refused"
    except OSError:
        return "failed"
    finally:
        close_root_fd(parent_fd)
    return "unlinked"
