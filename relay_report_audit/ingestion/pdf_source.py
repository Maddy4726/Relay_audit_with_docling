"""
Resolve relay test report PDFs from disk, bytes, or future sources (S3, SFTP).

Keeps Docling and downstream layers agnostic of where the file came from.
"""

from __future__ import annotations

from pathlib import Path


def load_pdf_bytes(path: str | Path) -> bytes:
    """Return raw PDF bytes for the parser stage."""
    return Path(path).read_bytes()
