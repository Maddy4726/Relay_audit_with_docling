"""
Deterministic repair of protection-style trip tables parsed from Docling markdown.

Docling sometimes emits rows where numeric ``Injected Current`` and ``Operated Time``
values are shifted one column left, leaving a composite phase token (e.g. ``RYB``)
in the last column. This module rotates such rows right by one cell when headers
and cell shapes match — no LLMs.
"""

from __future__ import annotations

import re
from typing import Final

_PHASE_LAST_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*(RYB|R\s*Y\s*B|R|Y|B|RY|YB|RB|IO|NV)\s*$",
    re.IGNORECASE,
)


def _norm_header(h: str) -> str:
    return re.sub(r"\s+", " ", h.strip()).lower()


def _is_trip_style_headers(headers: list[str]) -> bool:
    """True for Phase / Injected / Operated (or Calculated) style protection trip tables."""
    if len(headers) < 3:
        return False
    h0 = _norm_header(headers[0])
    if "ref" in h0 and "operation" in h0:
        return False
    if "phase" not in h0:
        return False
    mid = " ".join(_norm_header(h) for h in headers[1:-1])
    last = _norm_header(headers[-1])
    if "inject" not in mid and "current" not in mid:
        return False
    if not any(k in last for k in ("operat", "time", "sec", "delay", "calc")):
        return False
    return True


def _leading_scalar_token(cell: str) -> str | None:
    """First numeric token in a cell (handles ``>500``, ``45.0``, ``10``)."""
    t = cell.strip().lstrip(">").strip()
    if not t:
        return None
    m = re.match(r"^([-+]?\d*\.?\d+)", t.replace(",", ""))
    return m.group(1) if m else None


def _cell_looks_numeric_measurement(cell: str) -> bool:
    t = cell.strip()
    if not t:
        return False
    if _PHASE_LAST_RE.match(t):
        return False
    tok = _leading_scalar_token(t)
    if tok is None:
        return False
    try:
        float(tok)
    except ValueError:
        return False
    return True


def _last_cell_is_phase_or_composite(cell: str) -> bool:
    t = cell.strip()
    if not t:
        return False
    if _PHASE_LAST_RE.match(t):
        return True
    compact = re.sub(r"\s+", "", t).upper()
    if len(compact) <= 5 and re.fullmatch(r"[A-Z]+", compact) and compact not in {"OPEN", "CLOSE"}:
        return True
    return False


def maybe_repair_protection_table_row(headers: list[str], row: list[str]) -> list[str]:
    """
    If a row is one column left-shifted under trip-style headers, rotate right by one.

    Example (3 columns): ``[45.0, 0.138, RYB]`` → ``[RYB, 45.0, 0.138]``.
    Same rule for wider tables when the last cell is a phase token and all prior
    cells look like numeric measurements.
    """
    if len(row) != len(headers) or len(headers) < 3:
        return row
    if not _is_trip_style_headers(headers):
        return row
    if not _last_cell_is_phase_or_composite(row[-1]):
        return row
    if any(not _cell_looks_numeric_measurement(row[i]) for i in range(len(row) - 1)):
        return row
    if _last_cell_is_phase_or_composite(row[0]):
        return row
    return [row[-1]] + row[:-1]


__all__ = ["maybe_repair_protection_table_row"]
