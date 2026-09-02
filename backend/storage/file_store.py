import uuid
from pathlib import Path

from config import get_settings

settings = get_settings()


def save_upload(file_bytes: bytes, original_name: str) -> Path:
    ext = Path(original_name).suffix.lower()
    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest = settings.upload_path / safe_name
    dest.write_bytes(file_bytes)
    return dest


def delete_upload(stored_path: Path) -> bool:
    if stored_path.exists():
        stored_path.unlink()
        return True
    return False
