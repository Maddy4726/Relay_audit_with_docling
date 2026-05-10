"""
Routing policy: which sections go to Docling-only parsing vs Qwen2.5-VL via Ollama.

Centralizes thresholds and safety rules (e.g. never send credentials pages to the model).
"""

from __future__ import annotations

from typing import Any


def should_use_vl_extraction(_section: Any) -> bool:
    """Placeholder: return True when the section should be handed to ``ollama_qwen_vl``."""
    return False
