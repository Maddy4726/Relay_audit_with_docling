"""
Motor feeder / LCP style test report: thin wrapper around ``report_document_extract``.

Prefer ``build_report_document`` / ``build_report_document_dict`` for the canonical
JSON schema with ``outline`` and ``parent_section_slug`` on each heading.
"""

from __future__ import annotations

from relay_report_audit.schemas.motor_feeder_report import (
    MotorFeederReportBundle,
    MotorFeederSectionRecord,
)
from relay_report_audit.schemas.report_document import ReportSectionJson
from relay_report_audit.sections.report_document_extract import (
    build_report_document,
    build_report_document_dict,
)


def _to_motor_record(s: ReportSectionJson) -> MotorFeederSectionRecord:
    payload: dict = {}
    if s.typed_payload is not None:
        payload.update(s.typed_payload)
    payload["tables"] = [t.model_dump() for t in s.tables]
    payload["table_count"] = len(s.tables)
    if s.outline is not None:
        payload["outline"] = s.outline
    return MotorFeederSectionRecord(
        order_index=s.ordinal,
        header_line_1based=s.source_line_1based,
        header_kind=s.heading_kind,
        raw_header=s.heading_raw,
        normalized_title=s.heading_normalized,
        section_slug=s.section_slug,
        extractor_id=s.extractor_id,
        confidence=s.confidence,
        parent_section_slug=s.parent_section_slug,
        payload=payload,
    )


def process_motor_feeder_markdown(markdown: str) -> MotorFeederReportBundle:
    """Backward-compatible bundle; see ``build_report_document`` for full JSON schema."""
    doc = build_report_document(markdown)
    sections = [_to_motor_record(s) for s in doc.sections]
    return MotorFeederReportBundle(source_line_count=doc.markdown_line_count, sections=sections)


def process_motor_feeder_markdown_dict(markdown: str) -> dict:
    return process_motor_feeder_markdown(markdown).model_dump()


__all__ = [
    "build_report_document",
    "build_report_document_dict",
    "process_motor_feeder_markdown",
    "process_motor_feeder_markdown_dict",
]
