"""Convert markdown into stable, zero-padded, line-numbered text."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_LINE_PATTERN = re.compile(r"^\[(\d+)\]\s?(.*)$")


@dataclass(frozen=True)
class NumberedDocument:
    """Markdown split into numbered physical lines (blank lines preserved)."""

    lines: tuple[tuple[int, str], ...]
    padding_width: int

    def as_text(self) -> str:
        """Render the full document with ``[NNNN]`` prefixes for downstream use."""
        return "\n".join(
            format_numbered_line(n, text, self.padding_width) for n, text in self.lines
        )


def _effective_padding(line_count: int, min_width: int) -> int:
    digits = len(str(max(line_count, 1)))
    return max(min_width, digits)


def format_numbered_line(line_no: int, content: str, padding_width: int) -> str:
    """Format a single line as ``[0001] content`` using the configured width."""
    label = str(line_no).zfill(padding_width)
    return f"[{label}] {content}"


def number_markdown_lines(markdown: str, *, padding_width: int = 4) -> NumberedDocument:
    """
    Assign monotonic 1-based line numbers to every logical line of ``markdown``.

    Blank lines are preserved and receive their own line numbers. Original order
    is unchanged. Padding grows automatically if the document exceeds the width
    implied by ``padding_width``.
    """
    raw_lines = markdown.splitlines()
    eff_pad = _effective_padding(len(raw_lines), padding_width)
    numbered = tuple((i + 1, line) for i, line in enumerate(raw_lines))
    logger.info(
        "Numbered %s lines (padding width %s)", len(numbered), eff_pad
    )
    return NumberedDocument(lines=numbered, padding_width=eff_pad)


def parse_numbered_document(numbered_text: str) -> list[tuple[int, str]]:
    """
    Parse text produced by :func:`NumberedDocument.as_text` back into tuples.

    Used by tooling/tests; the chunker works directly on :class:`NumberedDocument`.
    """
    parsed: list[tuple[int, str]] = []
    for raw in numbered_text.splitlines():
        match = _LINE_PATTERN.match(raw)
        if not match:
            msg = f"Line does not match numbered pattern: {raw[:80]!r}"
            raise ValueError(msg)
        parsed.append((int(match.group(1)), match.group(2)))
    return parsed
