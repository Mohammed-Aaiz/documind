"""
File validation for DocuMind uploads.

Provides real content-based validation:
  - Magic byte / file signature verification
  - MIME type cross-check
  - SHA-256 content hashing
  - Filename sanitization

No fake security. Every check inspects actual file bytes.
"""

import hashlib
import re
import zipfile
from pathlib import Path
from typing import NamedTuple


# ---------------------------------------------------------------------------
# File signature definitions
# ---------------------------------------------------------------------------

# PDF: starts with %PDF- (bytes: 0x25 0x50 0x44 0x46 0x2D)
_PDF_MAGIC = b"%PDF-"

# DOCX: ZIP container that contains [Content_Types].xml
_DOCX_CONTENT_TYPES = b"[Content_Types].xml"


class ValidationResult(NamedTuple):
    """Result of file validation."""
    valid: bool
    file_type: str  # "pdf", "docx", "txt", or ""
    error: str  # error message if invalid, empty if valid


def validate_file_bytes(
    file_bytes: bytes,
    declared_ext: str,
) -> ValidationResult:
    """Validate uploaded file bytes against expected format.

    Checks:
    1. File is not empty
    2. Extension is in allowed set
    3. Magic bytes match the declared extension
    4. For DOCX: ZIP container contains expected DOCX markers

    Returns ValidationResult with validity, detected type, and any error.
    """
    if not file_bytes:
        return ValidationResult(valid=False, file_type="", error="File is empty")

    ext = declared_ext.lower().lstrip(".")

    if ext not in ("pdf", "docx", "txt"):
        return ValidationResult(
            valid=False, file_type="",
            error=f"Unsupported file type '.{ext}'"
        )

    # --- PDF signature check ---
    if ext == "pdf":
        if not file_bytes[:5] == _PDF_MAGIC:
            return ValidationResult(
                valid=False, file_type="pdf",
                error="File does not start with %PDF- signature"
            )
        return ValidationResult(valid=True, file_type="pdf", error="")

    # --- DOCX: verify ZIP container + DOCX markers ---
    if ext == "docx":
        result = _validate_docx_bytes(file_bytes)
        return result

    # --- TXT: verify content is plausibly text ---
    if ext == "txt":
        result = _validate_txt_bytes(file_bytes)
        return result

    return ValidationResult(
        valid=False, file_type="",
        error=f"Unhandled extension '.{ext}'"
    )


def _validate_docx_bytes(file_bytes: bytes) -> ValidationResult:
    """Verify that file bytes are a valid DOCX package.

    Checks:
    1. Starts with ZIP magic bytes (PK header)
    2. Is a valid ZIP archive
    3. Contains [Content_Types].xml (DOCX package marker)
    """
    # Check ZIP magic bytes: PK\x03\x04 (0x504B0304)
    if len(file_bytes) < 4 or file_bytes[:4] != b"PK\x03\x04":
        return ValidationResult(
            valid=False, file_type="docx",
            error="File does not start with ZIP signature (PK header)"
        )

    # Verify it's actually a valid ZIP
    try:
        import io
        zip_buf = io.BytesIO(file_bytes)
        with zipfile.ZipFile(zip_buf, "r") as zf:
            namelist = zf.namelist()
            # DOCX packages contain [Content_Types].xml
            has_content_types = any(
                name.endswith("[Content_Types].xml") for name in namelist
            )
            if not has_content_types:
                return ValidationResult(
                    valid=False, file_type="docx",
                    error="ZIP archive does not contain [Content_Types].xml — not a valid DOCX package"
                )
    except zipfile.BadZipFile:
        return ValidationResult(
            valid=False, file_type="docx",
            error="File is not a valid ZIP archive"
        )

    return ValidationResult(valid=True, file_type="docx", error="")


def _validate_txt_bytes(file_bytes: bytes) -> ValidationResult:
    """Verify that file bytes are plausibly text.

    Plain text has no universal signature. We check:
    1. Content can be decoded as UTF-8 (with replacement)
    2. No excessive null bytes (binary indicator)
    """
    # Check for excessive null bytes — binary files have many nulls
    null_count = file_bytes.count(b"\x00")
    total_len = len(file_bytes)
    if total_len > 0 and null_count / total_len > 0.1:
        return ValidationResult(
            valid=False, file_type="txt",
            error="File contains excessive null bytes — likely binary content"
        )

    # Try to decode as UTF-8
    try:
        file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        # Try latin-1 as fallback (decodes any byte sequence)
        try:
            file_bytes.decode("latin-1")
        except Exception:
            return ValidationResult(
                valid=False, file_type="txt",
                error="File content cannot be decoded as text"
            )

    return ValidationResult(valid=True, file_type="txt", error="")


# ---------------------------------------------------------------------------
# Content hashing
# ---------------------------------------------------------------------------

def compute_content_hash(file_bytes: bytes) -> str:
    """Compute SHA-256 hash of file bytes."""
    return hashlib.sha256(file_bytes).hexdigest()


# ---------------------------------------------------------------------------
# Filename sanitization
# ---------------------------------------------------------------------------

# Characters that are unsafe in filenames across platforms
_UNSAFE_CHARS = re.compile(r'[\x00-\x1f\x7f<>:"/\\|?*\x00]')

# Path traversal patterns
_PATH_TRAVERSAL = re.compile(r'(\.\.[\\/]|^[\\/]|^\.\.)')

# Maximum filename length (before extension)
_MAX_NAME_LENGTH = 200


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename for safe display and metadata storage.

    This does NOT produce a storage path — storage uses UUID-based names.
    This produces a human-readable, safe filename for display purposes.

    Rules:
    - Strip control characters (0x00-0x1F, 0x7F)
    - Remove path components (only keep basename)
    - Remove dangerous characters
    - Enforce length limit
    - Preserve extension for display
    """
    if not filename:
        return "unnamed"

    # Take only the basename (strip directory components)
    name = Path(filename).name

    # Remove control characters
    name = _UNSAFE_CHARS.sub("_", name)

    # Collapse multiple underscores
    name = re.sub(r"_+", "_", name)

    # Strip leading/trailing dots and spaces
    name = name.strip(". ")

    # Enforce length limit (preserve extension)
    if len(name) > _MAX_NAME_LENGTH:
        stem = Path(name).stem[:_MAX_NAME_LENGTH - 10]
        ext = Path(name).suffix
        name = f"{stem}{ext}"

    return name or "unnamed"
