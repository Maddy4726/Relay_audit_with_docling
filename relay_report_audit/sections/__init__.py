"""Logical section detection on parsed documents (headers, trip curves, test tables, etc.)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "DEFAULT_TARGET_SECTIONS",
    "SectionTable",
    "extract_relay_section_tables",
]

if TYPE_CHECKING:
    from relay_report_audit.sections.markdown_table_extractor import (
        DEFAULT_TARGET_SECTIONS,
        SectionTable,
        extract_relay_section_tables,
    )


def __getattr__(name: str) -> Any:
    if name in __all__:
        from relay_report_audit.sections import markdown_table_extractor

        return getattr(markdown_table_extractor, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
