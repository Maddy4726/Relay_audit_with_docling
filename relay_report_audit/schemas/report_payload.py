"""
Top-level extracted JSON shape passed to validation and the audit engine.

Aggregates measurements, metadata, and provenance so rules can reference stable paths.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from relay_report_audit.schemas.relay_measurement import RelayMeasurement


class ReportPayload(BaseModel):
    """Placeholder: full document extraction result prior to business-rule checks."""

    format_id: str = Field(description="Registered format handler id, e.g. vendor-specific slug")
    measurements: list[RelayMeasurement] = Field(default_factory=list)
