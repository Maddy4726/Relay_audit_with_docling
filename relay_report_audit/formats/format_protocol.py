"""
Protocol / ABC for a relay report format plugin (vendor A PDF, vendor B scan+OCR, etc.).

Each format supplies: detection signals, section segmentation hints, and optional extraction overrides.
"""

from __future__ import annotations

from typing import Any, Protocol


class RelayReportFormat(Protocol):
    """Structural contract for future multi-format support."""

    @property
    def format_id(self) -> str:
        """Stable slug used in ``ReportPayload.format_id`` and registry lookups."""
        ...

    def match_score(self, _document_ir: Any) -> float:
        """Return 0..1 confidence that this format applies to the parsed document."""
        ...
