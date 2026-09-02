"""
Document text extraction and chunking.

Supports PDF (PyMuPDF), DOCX (python-docx), and TXT.
Each extraction returns a list of (page_number | None, text) tuples.
Chunking splits text into overlapping windows.
"""

from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF
import docx


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

@dataclass
class RawChunk:
    page: int | None  # 1-based page number, None if unavailable
    text: str


def extract_pdf(path: Path) -> list[RawChunk]:
    """Extract text from a PDF, preserving page numbers."""
    doc = fitz.open(str(path))
    chunks: list[RawChunk] = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        if text.strip():
            chunks.append(RawChunk(page=page_num + 1, text=text.strip()))
    doc.close()
    return chunks


def extract_docx(path: Path) -> list[RawChunk]:
    """Extract text from a DOCX file."""
    document = docx.Document(str(path))
    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
    full_text = "\n".join(paragraphs)
    if not full_text.strip():
        return []
    return [RawChunk(page=None, text=full_text.strip())]


def extract_txt(path: Path) -> list[RawChunk]:
    """Extract text from a plain TXT file (UTF-8)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return []
    return [RawChunk(page=None, text=text.strip())]


EXTRACTORS = {
    "pdf": extract_pdf,
    "docx": extract_docx,
    "txt": extract_txt,
}


def extract_text(path: Path, file_type: str) -> list[RawChunk]:
    extractor = EXTRACTORS.get(file_type)
    if extractor is None:
        raise ValueError(f"Unsupported file type: {file_type}")
    return extractor(path)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

CHUNK_SIZE = 1000   # characters per chunk
CHUNK_OVERLAP = 200  # overlap between consecutive chunks


def chunk_text(raw_chunks: list[RawChunk]) -> list[tuple[int | None, str]]:
    """
    Split extracted text into overlapping windows.

    Returns list of (page_number, chunk_text). Page number is preserved
    from the source when available.
    """
    result: list[tuple[int | None, str]] = []

    for raw in raw_chunks:
        text = raw.text
        if len(text) <= CHUNK_SIZE:
            result.append((raw.page, text))
            continue

        # Sliding window over the text
        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE
            chunk = text[start:end]

            # Try to break at a sentence or word boundary
            if end < len(text):
                # Look for the last sentence boundary within the chunk
                last_period = chunk.rfind(".")
                last_newline = chunk.rfind("\n")
                boundary = max(last_period, last_newline)
                if boundary > CHUNK_SIZE // 2:
                    chunk = chunk[: boundary + 1]
                    end = start + boundary + 1

            if chunk.strip():
                result.append((raw.page, chunk.strip()))

            start = end - CHUNK_OVERLAP
            if start >= len(text):
                break

    return result
