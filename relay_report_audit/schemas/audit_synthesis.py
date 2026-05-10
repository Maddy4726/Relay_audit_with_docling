"""
Document-level audit synthesis: aggregates section engineering checks, confidences,
and typed extractors into a single deterministic audit result.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

OverallAuditStatus = Literal["PASS", "WARN", "FAIL", "REVIEW"]
SectionAuditStatus = Literal["PASS", "WARN", "FAIL", "REVIEW"]
FindingSeverity = Literal["FAIL", "WARN", "REVIEW"]


class AuditSummaryCounts(BaseModel):
    """Counts of sections by derived audit status."""

    model_config = ConfigDict(extra="forbid")

    pass_sections: int = Field(ge=0, default=0)
    warn_sections: int = Field(ge=0, default=0)
    fail_sections: int = Field(ge=0, default=0)
    review_sections: int = Field(ge=0, default=0)


class SectionAuditSummary(BaseModel):
    """Per-section rollup for traceability."""

    model_config = ConfigDict(extra="forbid")

    ordinal: int = Field(ge=0)
    section_slug: str
    heading_normalized: str
    extractor_id: str
    status: SectionAuditStatus
    confidence: float = Field(ge=0.0, le=1.0)
    protection_checks: dict[str, int] = Field(
        default_factory=dict,
        description="Counts by check status, e.g. {'PASS': 2, 'WARN': 1, 'FAIL': 0, 'SKIP': 1}.",
    )
    typed_payload_flags: list[str] = Field(
        default_factory=list,
        description="Deterministic flags from typed extractors (e.g. empty measurements).",
    )


class AuditFindingRecord(BaseModel):
    """Prioritized finding with preserved evidence for audit trail."""

    model_config = ConfigDict(extra="forbid")

    severity: FindingSeverity
    priority_rank: int = Field(ge=0, description="Lower value = higher priority in sorted output.")
    section: str = Field(description="Display heading (normalized) for the finding.")
    section_slug: str
    source_line_1based: int | None = Field(default=None, ge=1)
    ordinal: int = Field(ge=0)
    type: str
    message: str | None = None
    evidence: dict[str, Any] = Field(
        default_factory=dict,
        description="Full evidence object from engineering checks or synthesized diagnostics.",
    )


class LowConfidenceSectionRef(BaseModel):
    """Section flagged as statistically weak for extraction quality."""

    model_config = ConfigDict(extra="forbid")

    section_slug: str
    heading_normalized: str
    confidence: float = Field(ge=0.0, le=1.0)
    extractor_id: str
    reason: str


class AuditConfidenceSummary(BaseModel):
    """Aggregate confidence view."""

    model_config = ConfigDict(extra="forbid")

    document_confidence: float = Field(ge=0.0, le=1.0)
    low_confidence_sections: list[LowConfidenceSectionRef] = Field(default_factory=list)


class AuditSynthesisResult(BaseModel):
    """Single-document audit synthesis (deterministic, no LLM)."""

    model_config = ConfigDict(extra="forbid")

    overall_status: OverallAuditStatus
    summary: AuditSummaryCounts
    section_summaries: list[SectionAuditSummary] = Field(default_factory=list)
    findings: list[AuditFindingRecord] = Field(
        default_factory=list,
        description="Prioritized list; preserve full evidence dicts from upstream checks.",
    )
    confidence: AuditConfidenceSummary
    review_recommendations: list[str] = Field(
        default_factory=list,
        description="Deterministic narrative bullets derived from synthesis rules.",
    )


__all__ = [
    "AuditConfidenceSummary",
    "AuditFindingRecord",
    "AuditSummaryCounts",
    "AuditSynthesisResult",
    "FindingSeverity",
    "LowConfidenceSectionRef",
    "OverallAuditStatus",
    "SectionAuditStatus",
    "SectionAuditSummary",
]
