"""Docling-based document understanding: PDF → structured intermediate representation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["DoclingPdfParseError", "parse_pdf_to_markdown"]

if TYPE_CHECKING:
    from relay_report_audit.parsing.docling_parser import (
        DoclingPdfParseError,
        parse_pdf_to_markdown,
    )


def __getattr__(name: str) -> Any:
    if name in __all__:
        from relay_report_audit.parsing import docling_parser

        return getattr(docling_parser, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
