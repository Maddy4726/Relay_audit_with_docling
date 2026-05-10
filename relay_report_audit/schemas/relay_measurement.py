"""
Per-measurement / per-test-point Pydantic models (pickup, timing, phases, limits).

Extend here as you onboard new relay families; keep field names vendor-neutral where possible.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RelayMeasurement(BaseModel):
    """Placeholder schema for a single extracted measurement row or logical test."""

    name: str = Field(default="", description="Logical test or quantity name")
