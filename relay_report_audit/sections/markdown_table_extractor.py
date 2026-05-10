"""
Deterministic extraction of GitHub-flavored markdown pipe tables from Docling output.

Scans markdown for section markers that match configured relay report titles:

* ATX headings (``## CONTACT RESISTANCE TEST``)
* Docling-style list labels (``- 2.4 CONTACT RESISTANCE TEST:``)

Then parses pipe tables under each span (until the next sibling heading/list marker
or ATX heading) and returns structured records with confidence scores.

No LLMs: purely rule-based parsing and heuristics.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Final, Iterator

from relay_report_audit.sections.grouped_table_header import infer_grouped_header_layout

logger = logging.getLogger(__name__)

# Normalized (upper, single-spaced) section titles to locate in markdown headings.
DEFAULT_TARGET_SECTIONS: Final[tuple[str, ...]] = (
    "CONTACT RESISTANCE TEST",
    "OVERLOAD PROTECTION",
    "INSULATION RESISTANCE TEST",
)

_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
# List markers: "- 2.4 TITLE" or "- 2.2INSULATION ..." (Docling sometimes omits space).
_LIST_MARKER_SPACED_RE = re.compile(r"^\s*[-*+]\s+(\d+(?:\.\d+)*)\s+(.+)$")
_LIST_MARKER_TIGHT_RE = re.compile(r"^\s*[-*+]\s+(\d+(?:\.\d+)+)([A-Za-z].*)$")


def _normalize_section_title(raw: str) -> str:
    """Collapse whitespace, strip markdown emphasis markers, uppercase, trim trailing punctuation."""
    t = raw.strip().replace("`", "")
    t = re.sub(r"\*+", "", t)
    t = re.sub(r"\s+", " ", t).strip().upper()
    while t and t[-1] in " .;:,-_":
        t = t[:-1].strip()
    return t


def _parse_list_marker_section(line: str) -> tuple[str, str] | None:
    """
    Parse a markdown list line that starts with a numeric clause (e.g. ``2.4``).

    Returns ``(numeric_prefix, title_rest)`` or ``None`` if the line is not this shape.
    """
    s = line.rstrip("\n")
    m = _LIST_MARKER_SPACED_RE.match(s)
    if m:
        return m.group(1), m.group(2).strip()
    m = _LIST_MARKER_TIGHT_RE.match(s)
    if m:
        return m.group(1), m.group(2).strip()
    return None


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


def _merge_stacked_header_lines(top: list[str], bot: list[str]) -> list[str]:
    """Join two non-grouped header rows into one label per column (CT-style fallback)."""
    if len(top) != len(bot):
        return list(top)
    merged: list[str] = []
    for a_raw, b_raw in zip(top, bot, strict=True):
        a, b = a_raw.strip(), b_raw.strip()
        if not b:
            merged.append(a_raw.strip())
        elif not a:
            merged.append(b)
        else:
            merged.append(f"{a} {b}".strip())
    return merged


def _compute_confidence(
    *,
    had_separator: bool,
    ragged_rows: int,
    repeated_header_skips: int,
    num_rows: int,
    header_non_empty: bool,
    grouped_header_detected: bool = False,
    two_row_header_fallback: bool = False,
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
    if grouped_header_detected:
        score += 0.04
    elif two_row_header_fallback:
        score += 0.02
    return max(0.0, min(1.0, round(score, 4)))


@dataclass
class SectionTable:
    """One pipe table extracted from a relay markdown section."""

    section: str
    confidence: float
    headers: list[str]
    rows: list[list[str]]
    grouped_headers: list[dict[str, Any]] | None = None
    header_depth: int = 1

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "section": self.section,
            "confidence": self.confidence,
            "headers": list(self.headers),
            "rows": [list(r) for r in self.rows],
            "header_depth": self.header_depth,
        }
        if self.grouped_headers is not None:
            d["grouped_headers"] = list(self.grouped_headers)
        return d


@dataclass
class _SectionSpan:
    title: str
    heading_level: int  # ATX depth, or 0 for list-marker sections
    start_line: int
    end_line: int  # exclusive


def _iter_target_section_spans(
    lines: list[str],
    targets_normalized: set[str],
) -> Iterator[_SectionSpan]:
    """Yield body line spans for each matching ATX heading or list-style section label."""
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        parsed = _parse_atx_heading(line)
        if parsed is not None:
            level, title = parsed
            norm = _normalize_section_title(title)
            if norm in targets_normalized:
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
                    "Matched ATX section %r at line %d (level %d), body lines [%d, %d)",
                    norm,
                    i + 1,
                    level,
                    start_body + 1,
                    j + 1,
                )
                yield _SectionSpan(title=norm, heading_level=level, start_line=start_body, end_line=j)
                i = j
                continue

        lst = _parse_list_marker_section(line)
        if lst is not None:
            list_no, rest = lst
            norm = _normalize_section_title(rest)
            if norm in targets_normalized:
                start_body = i + 1
                j = start_body
                while j < n:
                    if _parse_atx_heading(lines[j]) is not None:
                        break
                    nxt = _parse_list_marker_section(lines[j])
                    if nxt is not None and nxt[0] != list_no:
                        break
                    j += 1

                logger.debug(
                    "Matched list section %r at line %d (clause %s), body lines [%d, %d)",
                    norm,
                    i + 1,
                    list_no,
                    start_body + 1,
                    j + 1,
                )
                yield _SectionSpan(title=norm, heading_level=0, start_line=start_body, end_line=j)
                i = j
                continue

        i += 1


def _append_continuation_to_previous_row(rows: list[list[str]], text: str) -> None:
    """Append a non-pipe continuation line to the most recently filled cell of the last row."""
    row = rows[-1]
    target = 0
    for j, cell in enumerate(row):
        if cell.strip():
            target = j
    prev = row[target]
    row[target] = f"{prev}\n{text}" if prev.strip() else text


def extract_tables_between_lines(
    lines: list[str],
    start_line: int,
    end_line: int,
    *,
    section_label: str,
) -> list[SectionTable]:
    """Parse all GFM pipe tables whose header rows fall within ``[start_line, end_line)``."""
    results: list[SectionTable] = []
    i = start_line
    end = end_line

    while i < end:
        header_line = lines[i]
        cells_r1 = _split_pipe_row(header_line)
        if len(cells_r1) < 1:
            i += 1
            continue
        if _is_separator_row(cells_r1):
            i += 1
            continue
        if i + 1 >= end:
            break

        probe_l2 = _split_pipe_row(lines[i + 1])
        grouped_meta: list[dict[str, Any]] | None = None
        header_depth = 1
        two_row_fallback = False
        used_two_row_header = False
        headers: list[str]
        data_start: int

        if i + 2 < end and not _is_separator_row(probe_l2) and len(probe_l2) == len(cells_r1):
            sep_probe = _split_pipe_row(lines[i + 2])
            if _is_separator_row(sep_probe) and len(sep_probe) == len(cells_r1):
                layout = infer_grouped_header_layout(cells_r1, probe_l2)
                if layout is not None:
                    headers = list(layout.flat_headers)
                    grouped_meta = [g.model_dump() for g in layout.grouped_headers]
                else:
                    headers = _merge_stacked_header_lines(cells_r1, probe_l2)
                    two_row_fallback = True
                header_depth = 2
                data_start = i + 3
                used_two_row_header = True

        if not used_two_row_header:
            sep_cells = probe_l2
            if not _is_separator_row(sep_cells) or len(sep_cells) != len(cells_r1):
                i += 1
                continue
            headers = list(cells_r1)
            data_start = i + 2

        had_separator = True
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
                        section_label,
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
                        section_label,
                    )
                    repeated_skips += 1
                    k += 2
                    continue
                if len(nxt) == len(headers):
                    # New table with same width but different header text — end current table
                    logger.debug("New separator at line %d ends table in section %s", k + 1, section_label)
                    break

            row_cells = _split_pipe_row(raw)

            if len(row_cells) == 0:
                if rows and stripped and "|" not in raw:
                    logger.debug(
                        "Treating line %d as continuation (no pipes) in section %s",
                        k + 1,
                        section_label,
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
                    section_label,
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
                    section_label,
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
            grouped_header_detected=grouped_meta is not None,
            two_row_header_fallback=two_row_fallback,
        )

        logger.info(
            "Extracted table in section %s: %d columns, %d data rows, confidence=%.4f%s",
            section_label,
            len(headers),
            len(rows),
            conf,
            " (grouped header)" if grouped_meta else "",
        )
        results.append(
            SectionTable(
                section=section_label,
                confidence=conf,
                headers=headers,
                rows=rows,
                grouped_headers=grouped_meta,
                header_depth=header_depth,
            )
        )
        # Always advance past header rows + separator to avoid a zero-row infinite loop.
        i = max(k, i + header_depth + 1)
        continue

    return results


def _extract_tables_in_span(
    lines: list[str],
    span: _SectionSpan,
) -> list[SectionTable]:
    """Find and parse all GFM pipe tables whose header+separator starts within span."""
    return extract_tables_between_lines(
        lines,
        span.start_line,
        span.end_line,
        section_label=span.title,
    )


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


def extract_pipe_tables_from_markdown_fragment(
    markdown_fragment: str,
    *,
    section_label: str = "FRAGMENT",
) -> list[dict[str, Any]]:
    """Extract every GFM pipe table in a markdown snippet (no section heading filter)."""
    lines = markdown_fragment.splitlines()
    return [t.as_dict() for t in extract_tables_between_lines(lines, 0, len(lines), section_label=section_label)]


__all__ = [
    "DEFAULT_TARGET_SECTIONS",
    "SectionTable",
    "extract_pipe_tables_from_markdown_fragment",
    "extract_relay_section_tables",
    "extract_tables_between_lines",
    "infer_grouped_header_layout",
]
