"""Text extraction helpers.

These helpers turn PDFs and plain-text files into the extracted content used by
the Onyx adapter. They are the content-extraction layer below the job facade.
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


def extract_pdf_text(path: Path) -> str:
    """Extract text from each PDF page for the document-ingestion flow."""
    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text)
    return "\n\n".join(parts).strip()


def extract_text(path: Path) -> str:
    """Dispatch to the correct extraction strategy for the file type."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_text(path)
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    raise ValueError(f"Unsupported file type: {path}")
