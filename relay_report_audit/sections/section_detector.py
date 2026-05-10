"""
Detect relay report sections from Docling-derived structure.

Delegates format-specific heuristics to ``relay_report_audit.formats`` so multiple
relay report layouts can coexist behind a single interface.
"""

from __future__ import annotations

from typing import Any


def detect_sections(_document_ir: Any, _format_id: str) -> list[Any]:
    """Placeholder: return ordered logical sections for downstream extraction."""
    return []
