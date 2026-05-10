"""
Run Docling conversion pipelines on relay PDFs (layout, tables, reading order).

Produces a normalized document object consumed by ``sections``; vendor specifics stay out of here.
"""

from __future__ import annotations


def convert_pdf_to_document(_pdf_bytes: bytes) -> None:
    """Placeholder: invoke Docling DocumentConverter and return a document handle or IR."""
    pass
