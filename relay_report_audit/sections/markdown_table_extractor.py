"""
Deterministic extraction of GitHub-flavored markdown pipe tables from Docling output.

Scans markdown for ATX headings that match configured relay report section titles,
parses pipe tables under each section (until the next heading of the same or higher
outline level), and returns structured records with confidence scores.

No LLMs: purely rule-based parsing and heuristics.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Final, Iterator

logger = logging.getLogger(__name__)

# Normalized (upper, single-spaced) section titles to locate in markdown headings.
DEFAULT_TARGET_SECTIONS: Final[tuple[str, ...]] = (
    "CONTACT RESISTANCE TEST",
    "OVERLOAD PROTECTION",
    "INSULATION RESISTANCE TEST",
)

_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _normalize_section_title(raw: str) -> str:
    """Collapse whitespace, strip markdown emphasis markers, uppercase."""
    t = raw.strip().replace("`", "")
    t = re.sub(r"\*+", "", t)
    t = re.sub(r"\s+", " ", t).strip().upper()
    return t


def _parse_atx_heading(line: str) -> tuple[int, str] | None:
    m = _ATX_HEADING_RE.match(line.rstrip("\n"))
    if not m:
        return None
    return len(m.group(1)), m.group(2).strip()


def _split_pipe_row(line: str) -> list[str]:
    """
    Split a single markdown table row on unescaped `|` boundaries.

    Supports optional leading/trailing pipes. Escaped pipes `\\|` become literal `|`
    inside cell text.
    """
    s = line.rstrip("\n").strip()
    if "|" not in s:
        return []

    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]

    cells: list[str] = []
    buf: list[str] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt in ("\\", "|"):
                buf.append(nxt)
                i += 2
                continue
            buf.append(ch)
            i += 1
            continue
        if ch == "|":
            cells.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    cells.append("".join(buf).strip())
    return cells


def _is_separator_row(cells: list[str]) -> bool:
    if not cells:
        return False
    for c in cells:
        t = c.strip()
        # GFM allows three or more hyphens; Docling sometimes emits shorter rules.
        if not re.fullmatch(r":?-{1,}:?", t):
            return False
    return True


def _rows_cells_equal(a: list[str], b: list[str]) -> bool:
    if len(a) != len(b):
        return False
    return all(x.strip() == y.strip() for x, y in zip(a, b, strict=True))


def _align_row_to_header(headers: list[str], row: list[str]) -> tuple[list[str], bool]:
    """Pad or trim row to match header column count; return (aligned_row, was_ragged)."""
    h = len(headers)
    if len(row) == h:
        return row, False
    if len(row) < h:
        return row + [""] * (h - len(row)), True
    return row[:h], True


def _compute_confidence(
    *,
    had_separator: bool,
    ragged_rows: int,
    repeated_header_skips: int,
    num_rows: int,
    header_non_empty: bool,
) -> float:
    """Deterministic 0..1 score from structural signals."""
    score = 1.0
    if not had_separator:
        score -= 0.22
    if not header_non_empty:
        score -= 0.12
    if num_rows == 0:
        score -= 0.18
    score -= 0.06 * min(repeated_header_skips, 5)
    score -= 0.08 * min(ragged_rows, 6)
    return max(0.0, min(1.0, round(score, 4)))


@dataclass
class SectionTable:
    """One pipe table extracted from a relay markdown section."""

    section: str
    confidence: float
    headers: list[str]
    rows: list[list[str]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "section": self.section,
            "confidence": self.confidence,
            "headers": list(self.headers),
            "rows": [list(r) for r in self.rows],
        }


@dataclass
class _SectionSpan:
    title: str
    heading_level: int
    start_line: int
    end_line: int  # exclusive


def _iter_target_section_spans(
    lines: list[str],
    targets_normalized: set[str],
) -> Iterator[_SectionSpan]:
    """Yield spans of body lines (indices) under each matching ATX heading."""
    i = 0
    n = len(lines)
    while i < n:
        parsed = _parse_atx_heading(lines[i])
        if parsed is None:
            i += 1
            continue
        level, title = parsed
        norm = _normalize_section_title(title)
        if norm not in targets_normalized:
            i += 1
            continue

        start_body = i + 1
        j = start_body
        while j < n:
            inner = _parse_atx_heading(lines[j])
            if inner is not None:
                inner_level, _ = inner
                if inner_level <= level:
                    break
            j += 1

        logger.debug(
            "Matched section %r at line %d (level %d), body lines [%d, %d)",
            norm,
            i + 1,
            level,
            start_body + 1,
            j + 1,
        )
        yield _SectionSpan(title=norm, heading_level=level, start_line=start_body, end_line=j)
        i = j


def _append_continuation_to_previous_row(rows: list[list[str]], text: str) -> None:
    """Append a non-pipe continuation line to the most recently filled cell of the last row."""
    row = rows[-1]
    target = 0
    for j, cell in enumerate(row):
        if cell.strip():
            target = j
    prev = row[target]
    row[target] = f"{prev}\n{text}" if prev.strip() else text


def _extract_tables_in_span(
    lines: list[str],
    span: _SectionSpan,
) -> list[SectionTable]:
    """Find and parse all GFM pipe tables whose header+separator starts within span."""
    results: list[SectionTable] = []
    i = span.start_line
    end = span.end_line

    while i < end:
        header_line = lines[i]
        cells_header = _split_pipe_row(header_line)
        if len(cells_header) < 1:
            i += 1
            continue
        if _is_separator_row(cells_header):
            i += 1
            continue
        if i + 1 >= end:
            break
        sep_cells = _split_pipe_row(lines[i + 1])
        if not _is_separator_row(sep_cells) or len(sep_cells) != len(cells_header):
            i += 1
            continue

        headers = list(cells_header)
        had_separator = True
        data_start = i + 2
        rows: list[list[str]] = []
        ragged = 0
        repeated_skips = 0
        k = data_start

        while k < end:
            raw = lines[k]
            stripped = raw.strip()
            if stripped == "":
                break
            if _parse_atx_heading(raw) is not None:
                break

            # Stacked GFM table: new header row followed by a separator line.
            if rows and k + 1 < end:
                probe_sep = _split_pipe_row(lines[k + 1])
                if (
                    _is_separator_row(probe_sep)
                    and len(probe_sep) >= 1
                    and len(_split_pipe_row(lines[k])) == len(probe_sep)
                ):
                    logger.debug(
                        "End of table before stacked table at line %d (section %s)",
                        k + 1,
                        span.title,
                    )
                    break

            # Mid-table repeated header: separator line again
            cand = _split_pipe_row(raw)
            if _is_separator_row(cand) and k + 1 < end:
                nxt = _split_pipe_row(lines[k + 1])
                if len(nxt) == len(headers) and _rows_cells_equal(nxt, headers):
                    logger.debug(
                        "Skipping repeated header block at lines %d-%d inside section %s",
                        k + 1,
                        k + 2,
                        span.title,
                    )
                    repeated_skips += 1
                    k += 2
                    continue
                if len(nxt) == len(headers):
                    # New table with same width but different header text — end current table
                    logger.debug("New separator at line %d ends table in section %s", k + 1, span.title)
                    break

            row_cells = _split_pipe_row(raw)

            if len(row_cells) == 0:
                if rows and stripped and "|" not in raw:
                    logger.debug(
                        "Treating line %d as continuation (no pipes) in section %s",
                        k + 1,
                        span.title,
                    )
                    _append_continuation_to_previous_row(rows, stripped)
                    k += 1
                    continue
                break

            # Continuation line that re-opens with `|` but continues the previous row
            if (
                rows
                and 0 < len(row_cells) < len(headers)
                and stripped.startswith("|")
                and not _is_separator_row(row_cells)
            ):
                logger.debug(
                    "Merging partial pipe row at line %d into previous row (section %s)",
                    k + 1,
                    span.title,
                )
                for idx, cell in enumerate(row_cells):
                    prev = rows[-1][idx] if idx < len(rows[-1]) else ""
                    rows[-1][idx] = (prev + "\n" + cell).strip() if prev else cell
                k += 1
                continue

            aligned, was_ragged = _align_row_to_header(headers, row_cells)
            if was_ragged:
                ragged += 1
                logger.warning(
                    "Ragged column count at line %d in section %s: got %d cells expected %d",
                    k + 1,
                    span.title,
                    len(row_cells),
                    len(headers),
                )

            if _rows_cells_equal(aligned, headers):
                logger.debug("Skipping data row identical to header at line %d", k + 1)
                repeated_skips += 1
                k += 1
                continue

            rows.append(aligned)
            k += 1

        header_ok = any(h.strip() for h in headers)
        conf = _compute_confidence(
            had_separator=had_separator,
            ragged_rows=ragged,
            repeated_header_skips=repeated_skips,
            num_rows=len(rows),
            header_non_empty=header_ok,
        )

        logger.info(
            "Extracted table in section %s: %d columns, %d data rows, confidence=%.4f",
            span.title,
            len(headers),
            len(rows),
            conf,
        )
        results.append(
            SectionTable(
                section=span.title,
                confidence=conf,
                headers=headers,
                rows=rows,
            )
        )
        # Always advance past header + separator to avoid a zero-row infinite loop.
        i = max(k, i + 2)
        continue

    return results


def extract_relay_section_tables(
    markdown: str,
    *,
    target_sections: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    """
    Extract pipe tables from markdown for the configured relay section headings.

    Args:
        markdown: Full markdown document string (e.g. from Docling).
        target_sections: Optional override of default section titles (normalized the same way).

    Returns:
        A list of dicts, each with keys ``section``, ``confidence``, ``headers``, ``rows``.
        Multiple dicts per section are possible when several tables appear under one heading.
    """
    sections = target_sections if target_sections is not None else DEFAULT_TARGET_SECTIONS
    targets_norm = {_normalize_section_title(s) for s in sections}
    lines = markdown.splitlines()
    logger.info(
        "Scanning markdown (%d lines) for %d target section(s)",
        len(lines),
        len(targets_norm),
    )

    out: list[dict[str, Any]] = []
    for span in _iter_target_section_spans(lines, targets_norm):
        tables = _extract_tables_in_span(lines, span)
        if not tables:
            logger.warning("No pipe tables found under section heading %r", span.title)
        for t in tables:
            out.append(t.as_dict())
    return out


__all__ = [
    "DEFAULT_TARGET_SECTIONS",
    "SectionTable",
    "extract_relay_section_tables",
]
