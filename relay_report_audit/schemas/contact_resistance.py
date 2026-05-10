"""
Typed models for CONTACT RESISTANCE TEST measurements (Docling markdown → validation).

All resistance values are normalized to **micro-ohms** (μΩ) for downstream audit rules.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ContactResistanceMeasurement(BaseModel):
    """One validated phase reading after deterministic parsing."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    phase: str = Field(
        min_length=1,
        max_length=64,
        description="Phase, pole, or circuit label (e.g. R, Y, B, A–B).",
    )
    resistance_micro_ohm: float = Field(
        gt=0.0,
        lt=1e9,
        description="Measured contact resistance stored as true micro-ohms (μΩ), not milliohms.",
    )


class ContactResistanceSectionResult(BaseModel):
    """Validated bundle for the CONTACT RESISTANCE TEST section."""

    model_config = ConfigDict(extra="forbid")

    section: Literal["CONTACT RESISTANCE TEST"] = "CONTACT RESISTANCE TEST"
    confidence: float = Field(ge=0.0, le=1.0, description="Aggregate extraction confidence.")
    measurements: list[ContactResistanceMeasurement] = Field(
        default_factory=list,
        description="Successfully validated rows; invalid rows are omitted with log warnings.",
    )


__all__ = [
    "ContactResistanceMeasurement",
    "ContactResistanceSectionResult",
]
