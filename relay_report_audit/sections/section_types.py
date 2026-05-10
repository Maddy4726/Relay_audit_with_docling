"""
Shared types for detected sections: spans, labels, confidence, and links back to Docling nodes.

Used by both heuristic detectors and VL-assisted extractors.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SectionSpan:
    """Placeholder: character or layout span anchoring a section in the document IR."""

    section_id: str
