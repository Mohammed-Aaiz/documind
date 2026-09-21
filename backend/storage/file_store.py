"""
File storage for DocuMind uploads.

Storage layout:
    uploads/{user_id}/{uuid}.{ext}

Features:
    - User-scoped subdirectories
    - UUID-based filenames (no path traversal)
    - Orphan cleanup on failure
    - Defensive deletion
"""

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


def delete_upload(stored_path: Path) -> bool:
    """Delete a stored upload file.

    Defensive: catches errors silently to avoid masking the original
    application error. Returns True if file was deleted, False otherwise.
    """
    try:
        if stored_path.exists():
            stored_path.unlink()
            return True
    except OSError:
        pass
    return False


def cleanup_new_file(file_path: Path) -> None:
    """Clean up a newly-created file after DB commit failure.

    This is a defensive cleanup — if it fails, we log but don't raise,
    because the original DB error is more important.
    """
    try:
        if file_path.exists():
            file_path.unlink()
    except OSError:
        # Cleanup failure is non-fatal; the original error propagates
        pass
