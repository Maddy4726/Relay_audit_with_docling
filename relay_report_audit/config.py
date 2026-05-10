"""
Application configuration: paths, Docling options, Ollama host, and Qwen2.5-VL model id.

Centralize environment-driven settings here so ingestion, parsing, and extraction
stay free of global state and remain easy to test.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditSettings:
    """Placeholder for typed settings loaded from env or a config file."""

    ollama_host: str = "http://127.0.0.1:11434"
    ollama_vl_model: str = "qwen2.5-vl"
