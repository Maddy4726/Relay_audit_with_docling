"""
Thin types and adapters between Docling output and internal section detection.

Isolates Docling API churn from the rest of the codebase (swap versions without touching audit logic).
"""

from __future__ import annotations

from typing import Any


def docling_export_to_ir(_docling_document: Any) -> None:
    """Placeholder: map Docling document to a stable internal representation."""
    pass
