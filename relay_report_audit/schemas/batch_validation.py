"""
Structured results for batch PDF relay report validation harness.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ReportBatchStatus = Literal["succeeded", "failed", "partial_review"]


class DiagnosticRecord(BaseModel):
    """Single deterministic diagnostic flag with traceable context."""

    model_config = ConfigDict(extra="forbid")

    type: str
    section_slug: str | None = None
    heading_normalized: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class CommonFailureAggregate(BaseModel):
    """Roll-up of repeated failure/diagnostic kinds across the batch."""

    model_config = ConfigDict(extra="forbid")

    type: str
    count: int = Field(ge=1)


class SingleReportBatchResult(BaseModel):
    """Outcome for one PDF after the deterministic pipeline."""

    model_config = ConfigDict(extra="forbid")

    stem: str
    pdf_path: str
    status: ReportBatchStatus
    duration_seconds: float = Field(ge=0.0)
    error_type: str | None = None
    error_message: str | None = None
    markdown_path: str | None = None
    json_path: str | None = None
    log_path: str | None = None
    document_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    section_count: int = Field(ge=0, default=0)
    audit_overall: str | None = None
    audit_fail_findings: int = Field(ge=0, default=0)
    audit_warn_findings: int = Field(ge=0, default=0)
    audit_review_findings: int = Field(ge=0, default=0)
    diagnostics: list[DiagnosticRecord] = Field(default_factory=list)
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-blocking issues (e.g. low confidence) still recorded for operators.",
    )


class BatchValidationSummary(BaseModel):
    """Aggregate across a folder of PDF reports."""

    model_config = ConfigDict(extra="forbid")

    total_reports: int = Field(ge=0)
    successful: int = Field(ge=0, description="Completed with PASS audit and no blocking diagnostics.")
    partial_review: int = Field(
        ge=0,
        default=0,
        description="Completed but WARN/REVIEW audit or blocking diagnostics present.",
    )
    failed: int = Field(ge=0, description="Parse/build exception or audit FAIL.")
    common_failures: list[CommonFailureAggregate] = Field(
        default_factory=list,
        description="Sorted by descending count, then type name.",
    )
    reports: list[SingleReportBatchResult] = Field(default_factory=list)
    output_dir: str = Field(description="Root output directory for this batch run.")


__all__ = [
    "BatchValidationSummary",
    "CommonFailureAggregate",
    "DiagnosticRecord",
    "ReportBatchStatus",
    "SingleReportBatchResult",
]
