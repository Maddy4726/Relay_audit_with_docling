"""
Engineering validation results for protection trip tables vs normalized settings.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CheckStatus = Literal["PASS", "FAIL", "WARN", "SKIP"]
AggregateStatus = Literal["PASS", "FAIL", "WARN", "SKIP"]


class ProtectionEngineeringCheck(BaseModel):
    """One deterministic engineering check with evidence for audit traceability."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(description="Machine-readable check identifier.")
    status: CheckStatus
    message: str | None = Field(default=None, description="Human-readable outcome detail.")
    evidence: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw numeric values, column indices, row excerpts used in the check.",
    )
    tolerance: dict[str, Any] | None = Field(
        default=None,
        description="Applied tolerances (relative fractions, absolute seconds, etc.).",
    )


class ProtectionOperationValidationResult(BaseModel):
    """Aggregate validation for one protection section."""

    model_config = ConfigDict(extra="forbid")

    status: AggregateStatus
    checks: list[ProtectionEngineeringCheck] = Field(default_factory=list)


__all__ = [
    "AggregateStatus",
    "CheckStatus",
    "ProtectionEngineeringCheck",
    "ProtectionOperationValidationResult",
]
