"""
Pydantic shapes for deterministic protection-setting metadata (DTOC / IDMT / etc.).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProtectionMetadataBlock(BaseModel):
    """One contiguous prose block (e.g. one stage) with raw text and normalized fields."""

    model_config = ConfigDict(extra="forbid")

    raw_metadata_text: str = Field(description="Verbatim prose slice that was parsed.")
    normalized: dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted numeric and categorical fields (keys vary by block).",
    )


__all__ = ["ProtectionMetadataBlock"]
