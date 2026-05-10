"""Logical section detection on parsed documents (headers, trip curves, test tables, etc.)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "DEFAULT_TARGET_SECTIONS",
    "SectionTable",
    "extract_contact_resistance_from_markdown",
    "extract_contact_resistance_section_dict",
    "extract_ct_ratio_test_dict",
    "extract_ct_ratio_test_from_markdown",
    "extract_pipe_tables_from_markdown_fragment",
    "extract_relay_section_tables",
    "extract_tables_between_lines",
    "process_motor_feeder_markdown",
    "process_motor_feeder_markdown_dict",
]

if TYPE_CHECKING:
    from relay_report_audit.sections.motor_feeder_report import (
        process_motor_feeder_markdown,
        process_motor_feeder_markdown_dict,
    )
    from relay_report_audit.sections.contact_resistance_extract import (
        extract_contact_resistance_from_markdown,
        extract_contact_resistance_section_dict,
    )
    from relay_report_audit.sections.ct_ratio_extract import (
        extract_ct_ratio_test_dict,
        extract_ct_ratio_test_from_markdown,
    )
    from relay_report_audit.sections.markdown_table_extractor import (
        DEFAULT_TARGET_SECTIONS,
        SectionTable,
        extract_pipe_tables_from_markdown_fragment,
        extract_relay_section_tables,
        extract_tables_between_lines,
    )


def __getattr__(name: str) -> Any:
    if name in ("DEFAULT_TARGET_SECTIONS", "SectionTable", "extract_relay_section_tables"):
        from relay_report_audit.sections import markdown_table_extractor

        return getattr(markdown_table_extractor, name)
    if name in ("extract_contact_resistance_from_markdown", "extract_contact_resistance_section_dict"):
        from relay_report_audit.sections import contact_resistance_extract

        return getattr(contact_resistance_extract, name)
    if name in ("extract_ct_ratio_test_from_markdown", "extract_ct_ratio_test_dict"):
        from relay_report_audit.sections import ct_ratio_extract

        return getattr(ct_ratio_extract, name)
    if name in ("extract_pipe_tables_from_markdown_fragment", "extract_tables_between_lines"):
        from relay_report_audit.sections import markdown_table_extractor

        return getattr(markdown_table_extractor, name)
    if name in ("process_motor_feeder_markdown", "process_motor_feeder_markdown_dict"):
        from relay_report_audit.sections import motor_feeder_report

        return getattr(motor_feeder_report, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
