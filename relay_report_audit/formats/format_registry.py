"""
Registry of ``RelayReportFormat`` implementations.

At runtime, score candidates after Docling IR is available and pick the best handler
(or ask the operator when ambiguous).
"""

from __future__ import annotations

from typing import Any


class FormatRegistry:
    """Placeholder: hold format plugins and resolve the active one per document."""

    def __init__(self) -> None:
        self._formats: list[Any] = []

    def register(self, fmt: Any) -> None:
        """Register a format handler instance."""
        self._formats.append(fmt)
