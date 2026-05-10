"""
Bundle model for full motor-feeder style test reports (Docling markdown → sections).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MotorFeederSectionRecord(BaseModel):
    """One processed section between consecutive report headers."""

    model_config = ConfigDict(extra="forbid")

    order_index: int = Field(ge=0)
    header_line_1based: int = Field(ge=1, description="Source markdown line of the header (1-based).")
    header_kind: str = Field(description="atx | list | numbered | caps | preamble")
    raw_header: str
    normalized_title: str
    section_slug: str
    extractor_id: str = Field(
        description="contact_resistance | ct_ratio | generic_tables | preamble",
    )
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    parent_section_slug: str | None = Field(
        default=None,
        description="Inferred parent heading slug (outline prefix or nearest caps banner).",
    )
    payload: dict = Field(default_factory=dict)


class MotorFeederReportBundle(BaseModel):
    """All sections in document order."""

    model_config = ConfigDict(extra="forbid")

    source_line_count: int = Field(ge=0)
    sections: list[MotorFeederSectionRecord] = Field(default_factory=list)


__all__ = ["MotorFeederReportBundle", "MotorFeederSectionRecord"]
