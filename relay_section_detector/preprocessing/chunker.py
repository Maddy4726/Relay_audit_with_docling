"""Overlapping line-based chunks for LLM calls."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .line_numbering import NumberedDocument, format_numbered_line

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TextChunk:
    """A window of numbered lines with global line indices."""

    chunk_id: int
    start_line: int
    end_line: int
    text: str


def chunk_numbered_document(
    doc: NumberedDocument,
    *,
    chunk_lines: int,
    overlap_lines: int,
) -> list[TextChunk]:
    """
    Build overlapping chunks over a :class:`NumberedDocument`.

    Each chunk contains up to ``chunk_lines`` consecutive lines, including blank
    lines. Windows advance by ``chunk_lines - overlap_lines`` lines. Line numbers
    embedded in ``text`` match the global document numbering.
    """
    if overlap_lines >= chunk_lines:
        msg = "overlap_lines must be less than chunk_lines"
        raise ValueError(msg)

    lines = doc.lines
    if not lines:
        return []

    step = chunk_lines - overlap_lines
    chunks: list[TextChunk] = []
    start_index = 0
    chunk_id = 1

    while start_index < len(lines):
        window = lines[start_index : start_index + chunk_lines]
        start_line = window[0][0]
        end_line = window[-1][0]
        body = "\n".join(
            format_numbered_line(n, text, doc.padding_width) for n, text in window
        )
        chunks.append(
            TextChunk(
                chunk_id=chunk_id,
                start_line=start_line,
                end_line=end_line,
                text=body,
            )
        )
        chunk_id += 1
        start_index += step

    logger.info(
        "Built %s chunks (size=%s overlap=%s)", len(chunks), chunk_lines, overlap_lines
    )
    return chunks
