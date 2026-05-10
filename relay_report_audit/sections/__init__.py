"""Logical section detection on parsed documents (headers, trip curves, test tables, etc.)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "DEFAULT_TARGET_SECTIONS",
    "SectionTable",
    "extract_contact_resistance_from_markdown",
    "extract_contact_resistance_section_dict",
    "extract_relay_section_tables",
]

if TYPE_CHECKING:
    from relay_report_audit.sections.contact_resistance_extract import (
        extract_contact_resistance_from_markdown,
        extract_contact_resistance_section_dict,
    )
    from relay_report_audit.sections.markdown_table_extractor import (
        DEFAULT_TARGET_SECTIONS,
        SectionTable,
        extract_relay_section_tables,
    )


def __getattr__(name: str) -> Any:
    if name in ("DEFAULT_TARGET_SECTIONS", "SectionTable", "extract_relay_section_tables"):
        from relay_report_audit.sections import markdown_table_extractor

        return getattr(markdown_table_extractor, name)
    if name in ("extract_contact_resistance_from_markdown", "extract_contact_resistance_section_dict"):
        from relay_report_audit.sections import contact_resistance_extract

        return getattr(contact_resistance_extract, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
