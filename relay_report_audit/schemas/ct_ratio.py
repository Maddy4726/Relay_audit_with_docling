"""
Typed models for CT (current transformer) ratio test extraction.

Secondary currents are amperes unless the table header indicates milliamperes.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CTMeasurement(BaseModel):
    """One phase row from a CT ratio injection table."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    phase: str = Field(min_length=1, max_length=64)
    primary_current: float = Field(ge=0.0, description="Injected primary current (A).")
    relay_secondary_current: float | None = Field(
        default=None,
        ge=0.0,
        description="Secondary current measured at / attributed to the relay (A).",
    )
    energy_meter_secondary_current: float | None = Field(default=None, ge=0.0)
    transducer_secondary_current: float | None = Field(
        default=None,
        ge=0.0,
        description="ICT / transducer secondary current (A) when present.",
    )
    ammeter_secondary_current: float | None = Field(default=None, ge=0.0)


class CTRatioTestResult(BaseModel):
    """Structured CT ratio test output."""

    model_config = ConfigDict(extra="forbid")

    section: Literal["CT RATIO TEST"] = "CT RATIO TEST"
    ct_ratio: str = Field(description='Nominal ratio like "150/5".')
    confidence: float = Field(ge=0.0, le=1.0)
    measurements: list[CTMeasurement] = Field(default_factory=list)
    grouped_headers: list[dict[str, Any]] | None = Field(
        default=None,
        description="Optional grouped/subcolumn layout from the primary CT table header.",
    )


__all__ = ["CTMeasurement", "CTRatioTestResult"]
