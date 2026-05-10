"""Typed configuration loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the section segmentation pipeline."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    pdf_path: Path = Field(
        default=Path("samples/report.pdf"),
        validation_alias=AliasChoices("RELAY_PDF_PATH", "RELAY_PDF"),
        description="Input PDF path.",
    )
    samples_dir: Path = Field(
        default=Path("samples"),
        validation_alias="RELAY_SAMPLES_DIR",
    )
    output_dir: Path = Field(
        default=Path("output"),
        validation_alias="RELAY_OUTPUT_DIR",
    )

    line_number_padding: int = Field(
        default=4,
        ge=1,
        le=12,
        validation_alias="RELAY_LINE_PAD",
        description="Minimum width for zero-padded line labels like [0001].",
    )
    chunk_lines: int = Field(
        default=200,
        ge=10,
        validation_alias="RELAY_CHUNK_LINES",
    )
    chunk_overlap_lines: int = Field(
        default=40,
        ge=0,
        validation_alias="RELAY_CHUNK_OVERLAP",
    )

    llm_api_key: str = Field(
        ...,
        validation_alias=AliasChoices(
            "RELAY_LLM_API_KEY",
            "OPENAI_API_KEY",
        ),
        description="API key for the OpenAI-compatible endpoint.",
    )
    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias="RELAY_LLM_BASE_URL",
    )
    llm_model: str = Field(
        default="gpt-4o-mini",
        validation_alias="RELAY_LLM_MODEL",
    )
    llm_temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        validation_alias="RELAY_LLM_TEMPERATURE",
    )
    llm_max_tokens: int = Field(
        default=4096,
        ge=256,
        validation_alias="RELAY_LLM_MAX_TOKENS",
    )

    def validate_chunk_geometry(self) -> None:
        """Ensure overlap is smaller than chunk size."""
        if self.chunk_overlap_lines >= self.chunk_lines:
            msg = "chunk_overlap_lines must be strictly less than chunk_lines"
            raise ValueError(msg)


def load_config() -> Settings:
    """Load settings from the environment and optional ``.env`` file."""
    settings = Settings()
    settings.validate_chunk_geometry()
    return settings
