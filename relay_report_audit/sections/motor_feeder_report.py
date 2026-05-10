"""
Motor feeder / LCP style test report: thin wrapper around ``report_document_extract``.

Prefer ``build_report_document`` / ``build_report_document_dict`` for the canonical
JSON schema with ``outline`` and ``parent_section_slug`` on each heading.
"""

from __future__ import annotations

from pathlib import Path

from relay_report_audit.schemas.motor_feeder_report import (
    MotorFeederReportBundle,
    MotorFeederSectionRecord,
)
from relay_report_audit.schemas.report_document import ReportSectionJson
from relay_report_audit.sections.report_document_extract import (
    build_report_document,
    build_report_document_dict,
    build_report_document_to_json_file,
    default_report_json_dir,
    write_report_document_json_file,
)


def _to_motor_record(s: ReportSectionJson) -> MotorFeederSectionRecord:
    payload: dict = {}
    if s.typed_payload is not None:
        payload.update(s.typed_payload)
    payload["tables"] = [t.model_dump() for t in s.tables]
    payload["table_count"] = len(s.tables)
    if s.outline is not None:
        payload["outline"] = s.outline
    if s.protection_metadata:
        payload["protection_metadata"] = s.protection_metadata
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


def process_motor_feeder_markdown(
    markdown: str,
    *,
    json_dir: str | Path | None = None,
    output_filename: str | Path | None = None,
    json_stem: str | None = None,
    json_indent: int = 2,
) -> MotorFeederReportBundle:
    """Backward-compatible bundle; optional ``json_dir`` writes ``ReportDocumentJson`` to disk."""
    doc = build_report_document(
        markdown,
        json_dir=json_dir,
        output_filename=output_filename,
        json_stem=json_stem,
        json_indent=json_indent,
    )
    sections = [_to_motor_record(s) for s in doc.sections]
    return MotorFeederReportBundle(source_line_count=doc.markdown_line_count, sections=sections)


def process_motor_feeder_markdown_dict(
    markdown: str,
    *,
    json_dir: str | Path | None = None,
    output_filename: str | Path | None = None,
    json_stem: str | None = None,
    json_indent: int = 2,
) -> dict:
    return process_motor_feeder_markdown(
        markdown,
        json_dir=json_dir,
        output_filename=output_filename,
        json_stem=json_stem,
        json_indent=json_indent,
    ).model_dump()


__all__ = [
    "build_report_document",
    "build_report_document_dict",
    "build_report_document_to_json_file",
    "default_report_json_dir",
    "write_report_document_json_file",
    "process_motor_feeder_markdown",
    "process_motor_feeder_markdown_dict",
]
