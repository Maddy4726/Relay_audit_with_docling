"""
JSON document schema: one record per detected heading in a Docling markdown report.

Heading text and numbering are **not** fixed (e.g. ``5.0`` may appear under different
chapters); use ``outline`` + ``parent_section_slug`` for structure, not hard-coded keys.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


HeadingKind = Literal["atx", "list", "numbered", "caps", "preamble"]


class SectionTableData(BaseModel):
    """One GFM pipe table extracted from a section body."""

    model_config = ConfigDict(extra="forbid")

    headers: list[str]
    rows: list[list[str]]
    confidence: float = Field(ge=0.0, le=1.0)
    header_depth: int = Field(default=1, ge=1, le=8)
    grouped_headers: list[dict[str, Any]] | None = Field(
        default=None,
        description='Optional nested layout: [{"group": str, "columns": [...]}, ...].',
    )


class ReportSectionJson(BaseModel):
    """Structured slice for a single heading (any test type / any numbering)."""

    model_config = ConfigDict(extra="forbid")

    ordinal: int = Field(ge=0, description="0-based order in the document.")
    source_line_1based: int = Field(ge=1, description="Markdown line number of the heading.")
    section_slug: str
    heading_kind: HeadingKind
    heading_raw: str
    heading_normalized: str
    outline: list[int] | None = Field(
        default=None,
        description="Numeric outline from leading clause (e.g. [4, 2] for 4.2); null for caps/ATX without numbers.",
    )
    parent_section_slug: str | None = Field(
        default=None,
        description="Best-effort parent: longest outline prefix among prior sections, else nearest prior caps banner.",
    )
    extractor_id: Literal["contact_resistance", "ct_ratio", "generic_tables", "preamble"] = "generic_tables"
    body_markdown: str = Field(default="", description="Markdown between this heading and the next.")
    tables: list[SectionTableData] = Field(default_factory=list)
    typed_payload: dict[str, Any] | None = Field(
        default=None,
        description="When routed, structured output (e.g. contact resistance or CT ratio model_dump).",
    )
    protection_metadata: list[dict[str, Any]] | None = Field(
        default=None,
        description="Parsed protection-setting prose blocks (raw + normalized) for DTOC/IDMT-style sections.",
    )
    protection_engineering_validation: dict[str, Any] | None = Field(
        default=None,
        description="Deterministic trip vs settings checks (PASS/WARN/FAIL/SKIP) with evidence.",
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ReportDocumentJson(BaseModel):
    """Full report as an ordered list of heading sections."""

    model_config = ConfigDict(extra="forbid")

    markdown_line_count: int = Field(ge=0)
    sections: list[ReportSectionJson] = Field(default_factory=list)


__all__ = ["ReportDocumentJson", "ReportSectionJson", "SectionTableData"]
