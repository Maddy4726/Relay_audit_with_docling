"""
Deterministic CT ratio test extraction from Docling markdown.

Locates CT / ratio / primary-injection sections, parses nominal CTR from prose,
extracts pipe tables including two-row grouped headers, maps device columns, and
returns validated Pydantic models. No LLMs.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass

from pydantic import ValidationError

from relay_report_audit.schemas.ct_ratio import CTMeasurement, CTRatioTestResult
from relay_report_audit.sections.markdown_table_extractor import (
    _is_separator_row,
    _normalize_section_title,
    _parse_atx_heading,
    _parse_list_marker_section,
    _split_pipe_row,
)

logger = logging.getLogger(__name__)

_CTR_RATIO_RE = re.compile(
    r"(?:CTR\s*[: ]?\s*)?(\d+)\s*/\s*(\d+)\s*(?:A\b)?",
    re.IGNORECASE,
)

_PHASE_COL_RE = re.compile(r"phase|ref|pole", re.IGNORECASE)
_PRIMARY_COL_RE = re.compile(r"inject|primary", re.IGNORECASE)
_RELAY_COL_RE = re.compile(r"\brelay\b", re.IGNORECASE)
_ENERGY_METER_COL_RE = re.compile(r"energy\s*meter|kwh", re.IGNORECASE)
_ICT_COL_RE = re.compile(r"\bict\b|transduc", re.IGNORECASE)
_AMMETER_COL_RE = re.compile(r"ammeter", re.IGNORECASE)

_CELL_NUM_RE = re.compile(
    r"^\s*([+-]?\d+(?:[.,]\d+)?(?:\s*\d{3})*(?:[eE][+-]?\d+)?)\s*(.*)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _LineSpan:
    start_line: int
    end_line: int  # exclusive


def _is_ct_ratio_section_title(norm: str) -> bool:
    """Heuristic: section belongs to CT ratio / primary injection testing."""
    if re.search(r"\bCT\b", norm) and ("RATIO" in norm or "CTR" in norm or "PRIMARY" in norm):
        return True
    if "RATIO TEST" in norm and ("PRIMARY" in norm or "INJECTION" in norm):
        return True
    if "CBCT" in norm and "RATIO" in norm:
        return True
    return False


def _parse_numbered_prose_heading(line: str) -> str | None:
    """
    Match Docling-style numbered titles without list markers, e.g. ``3. RATIO TEST: ...``
    or ``2. 3.1 CT (CTR: ... )``.
    """
    s = line.strip()
    for pat in (r"^\s*\d+\.\d+\s+(.+)$", r"^\s*\d+\.\s+(.+)$"):
        m = re.match(pat, s)
        if m:
            return _normalize_section_title(m.group(1))
    return None


def _iter_ct_ratio_spans(lines: list[str]) -> list[_LineSpan]:
    """Find line spans for CT ratio sections (ATX headings and list markers)."""
    spans: list[_LineSpan] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        atx = _parse_atx_heading(line)
        if atx is not None:
            level, title = atx
            norm = _normalize_section_title(title)
            if _is_ct_ratio_section_title(norm):
                start_body = i + 1
                j = start_body
                while j < n:
                    inner = _parse_atx_heading(lines[j])
                    if inner is not None and inner[0] <= level:
                        break
                    j += 1
                logger.debug(
                    "CT span (ATX) lines [%d, %d) title_norm=%r",
                    start_body + 1,
                    j + 1,
                    norm,
                )
                spans.append(_LineSpan(start_line=start_body, end_line=j))
                i = j
                continue

        lst = _parse_list_marker_section(line)
        if lst is not None:
            list_no, rest = lst
            norm = _normalize_section_title(rest)
            if _is_ct_ratio_section_title(norm):
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
                    "CT span (list %s) lines [%d, %d) title_norm=%r",
                    list_no,
                    start_body + 1,
                    j + 1,
                    norm,
                )
                spans.append(_LineSpan(start_line=start_body, end_line=j))
                i = j
                continue

        prose = _parse_numbered_prose_heading(line)
        if prose is not None and _is_ct_ratio_section_title(prose):
            start_body = i + 1
            j = start_body
            while j < n:
                raw = lines[j]
                if _parse_atx_heading(raw) is not None:
                    break
                if _parse_list_marker_section(raw) is not None:
                    break
                p = _parse_numbered_prose_heading(raw)
                if p is not None and not _is_ct_ratio_section_title(p):
                    break
                j += 1
            logger.debug(
                "CT span (numbered prose) lines [%d, %d) title_norm=%r",
                start_body + 1,
                j + 1,
                prose,
            )
            spans.append(_LineSpan(start_line=start_body, end_line=j))
            i = j
            continue

        i += 1
    return spans


def _extract_ct_ratio_string(lines: list[str], span: _LineSpan) -> tuple[str | None, float]:
    """Parse nominal ``primary/secondary`` from span text; returns (ratio, local_confidence)."""
    best: tuple[str, float] | None = None
    scan_lo = max(0, span.start_line - 5)
    for k in range(scan_lo, min(span.end_line, span.start_line + 120)):
        for m in _CTR_RATIO_RE.finditer(lines[k]):
            num, den = m.group(1), m.group(2)
            ratio = f"{int(num)}/{int(den)}"
            score = 0.75
            ctx = lines[k].upper()
            if "CTR" in ctx:
                score = 1.0
            elif "CT" in ctx:
                score = 0.92
            if best is None or score > best[1]:
                best = (ratio, score)
                logger.debug("CTR candidate %r from line %d (score=%.2f)", ratio, k + 1, score)
    if best is None:
        return None, 0.0
    return best[0], best[1]


def _merge_double_header(top: list[str], bot: list[str]) -> list[str]:
    """Merge two header rows; prefer concrete labels from the lower row."""
    n = max(len(top), len(bot))
    merged: list[str] = []
    for i in range(n):
        a = top[i].strip() if i < len(top) else ""
        b = bot[i].strip() if i < len(bot) else ""
        generic_a = "measured current" in a.lower() and "secondary" in a.lower()
        if b:
            merged.append(b if generic_a or not a else f"{a} {b}".strip())
        else:
            merged.append(a)
    return merged


def _align_cells(row: list[str], width: int) -> list[str]:
    if len(row) >= width:
        return row[:width]
    return row + [""] * (width - len(row))


def _looks_like_phase_primary_header_row(cells: list[str]) -> bool:
    """Detect the concrete device/phase header row after a Docling banner row."""
    text = " ".join(c.strip() for c in cells if c.strip()).upper()
    return "PHASE" in text and ("INJECT" in text or "PRIMARY" in text)


def _parse_tables_in_span(
    lines: list[str],
    span: _LineSpan,
) -> list[tuple[list[str], list[list[str]], int, float]]:
    """
    Yield ``(merged_headers, data_rows, header_row_count, table_confidence)`` per table.

    Supports optional two-row headers before the separator row.
    """
    out: list[tuple[list[str], list[list[str]], int, float]] = []
    i = span.start_line
    end = span.end_line

    while i < end:
        r1 = _split_pipe_row(lines[i])
        if len(r1) < 2 or _is_separator_row(r1):
            i += 1
            continue
        if i + 1 >= end:
            break

        r2_line = _split_pipe_row(lines[i + 1])
        sep_idx: int
        merged: list[str]
        header_rows = 1
        data_start: int

        if _is_separator_row(r2_line):
            sep_idx = i + 1
            sep = r2_line
            merged = list(r1)
            data_start = sep_idx + 1
            # Docling sometimes emits: banner header row, separator, then real column headers.
            if i + 2 < end:
                r3 = _split_pipe_row(lines[i + 2])
                w = len(sep)
                if (
                    len(r3) >= 2
                    and not _is_separator_row(r3)
                    and _looks_like_phase_primary_header_row(r3)
                    and len(_align_cells(r1, w)) == w
                ):
                    merged = _merge_double_header(_align_cells(r1, w), _align_cells(r3, w))
                    data_start = sep_idx + 2
                    header_rows = 2
                    logger.debug(
                        "Merged split CT header (banner+sep+labels) starting line %d",
                        i + 1,
                    )
        elif i + 2 < end:
            sep = _split_pipe_row(lines[i + 2])
            if _is_separator_row(sep):
                w = max(len(r1), len(r2_line), len(sep))
                r1a = _align_cells(r1, w)
                r2a = _align_cells(r2_line, w)
                sepa = _align_cells(sep, w)
                if len({len(r1a), len(r2a), len(sepa)}) == 1:
                    merged = _merge_double_header(r1a, r2a)
                    sep_idx = i + 2
                    header_rows = 2
                    data_start = sep_idx + 1
                else:
                    i += 1
                    continue
            else:
                i += 1
                continue
        else:
            i += 1
            continue

        sep = _split_pipe_row(lines[sep_idx])
        if len(sep) != len(merged):
            logger.debug("Skipping table at line %d: separator width mismatch", i + 1)
            i += 1
            continue

        rows: list[list[str]] = []
        ragged = 0
        k = data_start
        while k < end:
            raw = lines[k]
            if raw.strip() == "":
                break
            if _parse_atx_heading(raw) is not None:
                break
            if _parse_list_marker_section(raw) is not None:
                break
            cells = _split_pipe_row(raw)
            if len(cells) < 2 and "|" not in raw:
                break
            if _is_separator_row(cells):
                break
            al = _align_cells(cells, len(merged))
            if len(cells) != len(merged):
                ragged += 1
            rows.append(al)
            k += 1

        tconf = max(0.35, min(1.0, 1.0 - 0.08 * ragged - (0.0 if header_rows == 2 else 0.03)))
        logger.info(
            "CT table at line %d: cols=%d header_rows=%d data_rows=%d conf=%.3f",
            i + 1,
            len(merged),
            header_rows,
            len(rows),
            tconf,
        )
        out.append((merged, rows, header_rows, tconf))
        i = max(k, sep_idx + 1, i + header_rows + 1)

    return out


def _pick_col(headers: list[str], pattern: re.Pattern[str]) -> int | None:
    for idx, h in enumerate(headers):
        if pattern.search(h.strip()):
            return idx
    return None


def _parse_current_value(cell: str) -> float | None:
    """Parse amps from cell; supports milliamperes suffix."""
    s = cell.strip()
    if not s or s == "-":
        return None
    if s.startswith(">"):
        return None
    m = _CELL_NUM_RE.match(s)
    if not m:
        return None
    num, rest = m.group(1), m.group(2).strip()
    raw = num.strip()
    if raw.count(",") == 1 and raw.count(".") == 0:
        raw = raw.replace(",", ".")
    else:
        raw = raw.replace(",", "")
    try:
        v = float(raw)
    except ValueError:
        return None
    if not math.isfinite(v):
        return None
    if re.search(r"(m\s*a|milli\s*amp)\b", rest, re.IGNORECASE) or re.search(
        r"(m\s*a|milli\s*amp)\b", s, re.IGNORECASE
    ):
        v /= 1000.0
    return v


def _score_table(headers: list[str]) -> float:
    """Heuristic preference for the main CT injection matrix."""
    h = " ".join(headers).upper()
    score = 0.0
    if _PHASE_COL_RE.search(h):
        score += 0.35
    if _PRIMARY_COL_RE.search(h):
        score += 0.35
    if "SECONDARY" in h:
        score += 0.32
    if _RELAY_COL_RE.search(h) or _AMMETER_COL_RE.search(h):
        score += 0.3
    return score


def _build_measurements(
    headers: list[str],
    rows: list[list[str]],
) -> tuple[list[CTMeasurement], int, int]:
    """Return (measurements, parse_errors, device_column_count)."""
    pi = _pick_col(headers, _PRIMARY_COL_RE)
    ph = _pick_col(headers, _PHASE_COL_RE)
    ri = _pick_col(headers, _RELAY_COL_RE)
    ei = _pick_col(headers, _ENERGY_METER_COL_RE)
    ii = _pick_col(headers, _ICT_COL_RE)
    ai = _pick_col(headers, _AMMETER_COL_RE)

    if ph is None or pi is None:
        logger.warning("CT table missing phase (%s) or primary (%s) column", ph, pi)
        return [], 1, 0

    used = sum(1 for x in (ri, ei, ii, ai) if x is not None)
    out: list[CTMeasurement] = []
    errs = 0

    for r_idx, row in enumerate(rows):
        if max(ph, pi) >= len(row):
            errs += 1
            continue
        phase = str(row[ph]).strip()
        prim = _parse_current_value(str(row[pi]))
        if prim is None:
            errs += 1
            logger.debug("CT row %d: bad primary %r", r_idx, row[pi] if pi < len(row) else "")
            continue

        def col_val(idx: int | None) -> float | None:
            if idx is None or idx >= len(row):
                return None
            return _parse_current_value(str(row[idx]))

        try:
            m = CTMeasurement(
                phase=phase,
                primary_current=prim,
                relay_secondary_current=col_val(ri),
                energy_meter_secondary_current=col_val(ei),
                transducer_secondary_current=col_val(ii),
                ammeter_secondary_current=col_val(ai),
            )
        except ValidationError as exc:
            errs += 1
            logger.warning("CT row %d failed validation: %s", r_idx, exc)
            continue
        out.append(m)

    return out, errs, used


def _aggregate_confidence(
    *,
    ctr_conf: float,
    ctr_found: bool,
    table_pick_score: float,
    measurements: int,
    parse_errors: int,
    device_cols: int,
    table_conf: float,
) -> float:
    score = 0.22
    if ctr_found:
        score += 0.28 * ctr_conf
    score += 0.28 * min(1.0, table_pick_score)
    score += 0.12 * min(device_cols, 4) / 4.0
    if measurements:
        score += 0.12
    score -= 0.06 * min(parse_errors, 6)
    score *= 0.85 + 0.15 * table_conf
    return max(0.0, min(1.0, round(score, 4)))


def extract_ct_ratio_test_from_markdown(markdown: str) -> CTRatioTestResult:
    """
    Extract CT ratio nominal string and per-phase measurements from markdown.

    Chooses the best-scoring table inside detected CT ratio spans (phase + primary
    + at least one secondary device column).
    """
    lines = markdown.splitlines()
    logger.info("CT ratio extract: markdown lines=%d", len(lines))
    spans = _iter_ct_ratio_spans(lines)
    if not spans:
        logger.warning("No CT ratio section spans detected")
        return CTRatioTestResult(ct_ratio="", confidence=0.0, measurements=[])

    best_ratio: str | None = None
    best_ctr_conf = 0.0
    for sp in spans:
        r, c = _extract_ct_ratio_string(lines, sp)
        if r is not None and c >= best_ctr_conf:
            best_ratio, best_ctr_conf = r, c
            logger.info("Using CTR %r (local confidence=%.3f) from span lines", r, c)

    if best_ratio is None:
        logger.warning("Nominal CT ratio not found in prose")
        best_ratio = ""

    best_tables: list[tuple[float, list[str], list[list[str]], float]] = []
    for sp in spans:
        for merged_h, data_rows, _hdr_rows, tconf in _parse_tables_in_span(lines, sp):
            pick = _score_table(merged_h)
            if pick < 0.62:
                logger.debug("Skip table: low CT score=%.2f headers=%r", pick, merged_h[:6])
                continue
            best_tables.append((pick, merged_h, data_rows, tconf))

    if not best_tables:
        logger.warning("No qualifying CT ratio tables found")
        return CTRatioTestResult(
            ct_ratio=best_ratio,
            confidence=0.18 if best_ratio else 0.0,
            measurements=[],
        )

    best_tables.sort(key=lambda x: (x[0], len(x[2]), x[3]), reverse=True)
    pick_score, headers, rows, table_conf = best_tables[0]
    logger.info(
        "Selected CT table rows=%d pick_score=%.3f table_conf=%.3f headers=%r",
        len(rows),
        pick_score,
        table_conf,
        headers,
    )

    measurements, parse_errors, device_cols = _build_measurements(headers, rows)
    conf = _aggregate_confidence(
        ctr_conf=best_ctr_conf,
        ctr_found=bool(best_ratio),
        table_pick_score=pick_score,
        measurements=len(measurements),
        parse_errors=parse_errors,
        device_cols=device_cols,
        table_conf=table_conf,
    )

    logger.info(
        "CT ratio extraction done: ctr=%s measurements=%d confidence=%.4f",
        best_ratio,
        len(measurements),
        conf,
    )
    return CTRatioTestResult(ct_ratio=best_ratio, confidence=conf, measurements=measurements)


def extract_ct_ratio_test_dict(markdown: str) -> dict:
    """JSON-friendly dict (``model_dump``)."""
    return extract_ct_ratio_test_from_markdown(markdown).model_dump(exclude_none=True)


__all__ = [
    "extract_ct_ratio_test_from_markdown",
    "extract_ct_ratio_test_dict",
]
