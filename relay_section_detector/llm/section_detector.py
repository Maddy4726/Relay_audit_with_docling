"""OpenAI-compatible LLM client for semantic section detection."""

from __future__ import annotations

import json
import logging
import re
from typing import Protocol

from openai import OpenAI
from pydantic import BaseModel, Field, model_validator

from llm.prompts import (
    FEW_SHOT_ASSISTANT_1,
    FEW_SHOT_ASSISTANT_2,
    FEW_SHOT_USER_1,
    FEW_SHOT_USER_2,
    SECTION_SYSTEM_PROMPT,
    build_user_prompt,
)

logger = logging.getLogger(__name__)


class SectionPrediction(BaseModel):
    """One semantic section span inside the report."""

    section_type: str = Field(
        ...,
        description="Canonical or best-effort semantic label for the section.",
    )
    detected_title: str = Field(
        ...,
        description="Verbatim or lightly normalised heading text from the excerpt.",
    )
    start_line: int = Field(..., ge=1)
    end_line: int = Field(..., ge=1)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _ordered_lines(self) -> SectionPrediction:
        if self.end_line < self.start_line:
            msg = "end_line must be >= start_line"
            raise ValueError(msg)
        return self


class LLMClient(Protocol):
    """Protocol for swapping providers while keeping call sites stable."""

    def complete_sections(self, numbered_chunk_text: str) -> list[SectionPrediction]:
        """Return validated section predictions for a single chunk."""


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[: cleaned.rfind("```")].strip()
    return cleaned


def _parse_sections_payload(content: str) -> list[SectionPrediction]:
    """Parse model output into structured predictions."""
    payload = json.loads(_strip_code_fence(content))
    if isinstance(payload, list):
        raw_sections = payload
    elif isinstance(payload, dict) and "sections" in payload:
        raw_sections = payload["sections"]
    else:
        msg = "Model JSON must be a list or contain a 'sections' array"
        raise ValueError(msg)

    if not isinstance(raw_sections, list):
        msg = "'sections' must be a JSON array"
        raise ValueError(msg)

    return [SectionPrediction.model_validate(item) for item in raw_sections]


class OpenAICompatibleSectionDetector:
    """Semantic section detector using an OpenAI-compatible chat completion API."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> None:
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    def complete_sections(self, numbered_chunk_text: str) -> list[SectionPrediction]:
        user_prompt = build_user_prompt(numbered_chunk_text)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": SECTION_SYSTEM_PROMPT},
            {"role": "user", "content": FEW_SHOT_USER_1},
            {"role": "assistant", "content": FEW_SHOT_ASSISTANT_1},
            {"role": "user", "content": FEW_SHOT_USER_2},
            {"role": "assistant", "content": FEW_SHOT_ASSISTANT_2},
            {"role": "user", "content": user_prompt},
        ]

        logger.debug("Calling LLM model=%s for chunk", self._model)
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            messages=messages,
            response_format={"type": "json_object"},
        )

        choice = response.choices[0].message.content or ""
        predictions = _parse_sections_payload(choice)
        logger.info("LLM returned %s section spans", len(predictions))
        return predictions
