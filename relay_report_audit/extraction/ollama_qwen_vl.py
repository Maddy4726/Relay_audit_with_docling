"""
Ollama client for local Qwen2.5-VL: multimodal prompts over PDF snippets or rendered images.

Use for low-confidence or visually complex relay sections (e.g. stamped curves, handwritten notes).
"""

from __future__ import annotations

from typing import Any


def extract_with_qwen_vl(_prompt: str, _images_or_pages: list[Any]) -> str:
    """Placeholder: call Ollama chat/generate with the configured VL model; return raw model text."""
    return ""
