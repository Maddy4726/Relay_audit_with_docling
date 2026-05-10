"""
Deterministic inference of grouped two-row pipe-table headers (e.g. protection tables).

Top row: repeated or forward-filled group titles (``Injected Current (A)``, …).
Second row: subcolumn labels (``X2``, ``X4``, ``X6``) repeated under each group.

No LLMs. Returns a :class:`GroupedTableHeaderLayout` or ``None`` when the pattern
does not apply.
"""

from __future__ import annotations

import logging
import re
from typing import Final

from relay_report_audit.schemas.grouped_table import GroupedTableHeaderLayout, TableColumnGroup

logger = logging.getLogger(__name__)

_SUBTOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"^(X\d+|TAP\s*\d+|PHASE|REF\.?|R|Y|B|RYB|RY|YB|RB|N\.?S\.?|PRIMARY|SECONDARY|[A-Z]{1,4}\d*)$",
    re.IGNORECASE,
)
_FLOATISH_RE: Final[re.Pattern[str]] = re.compile(
    r"^[\s]*[-+]?\d*\.?\d+([\s]*[/:][\s]*[-+]?\d*\.?\d+)?[\s]*$",
)


def _forward_fill_top_groups(top: list[str]) -> list[str] | None:
    """Return per-column effective group labels; ``None`` if still empty after fill."""
    eff: list[str] = []
    last = ""
    for c in top:
        s = c.strip()
        if s:
            last = s
        if not last and not s:
            eff.append("")
            continue
        eff.append(last if s == "" else s)
    if not eff or not eff[0]:
        return None
    # Leading empties before first non-empty: back-fill from first solid label
    first_i = next((i for i, x in enumerate(eff) if x), None)
    if first_i is None:
        return None
    seed = eff[first_i]
    for i in range(first_i):
        eff[i] = seed
    return eff


def _numeric_cell_fraction(cells: list[str]) -> float:
    n = len(cells)
    if not n:
        return 0.0
    hits = 0
    for c in cells:
        t = c.strip()
        if t and _FLOATISH_RE.match(t):
            hits += 1
    return hits / n


def _looks_like_subheader_row(bot: list[str], top_filled: list[str]) -> bool:
    """Heuristic: second row is short tokens / tap ids, not prose or numeric data."""
    if _numeric_cell_fraction(bot) >= 0.45:
        return False
    nonempty = [b.strip() for b in bot if b.strip()]
    if len(nonempty) < 2:
        return False
    avg = sum(len(x) for x in nonempty) / len(nonempty)
    if avg > 36:
        return False
    # Mostly long prose in second row (unlikely subcolumns)
    longish = sum(1 for x in nonempty if len(x) > 28)
    if longish >= max(2, len(nonempty) // 2):
        return False
    # At least some cells look like typical sub-labels OR all short
    subish = sum(1 for x in nonempty if _SUBTOKEN_RE.match(x) or len(x) <= 6)
    if subish < min(2, len(nonempty)):
        # allow all short alphanumeric without matching SUBTOKEN
        short_tokens = sum(1 for x in nonempty if len(x) <= 10 and not any(ch.isspace() for ch in x))
        if short_tokens < min(2, len(nonempty)):
            return False
    distinct_groups = {g.strip() for g in top_filled if g.strip()}
    if len(distinct_groups) >= 2:
        pass
    elif len(distinct_groups) == 1 and len(top_filled) >= 3:
        # One physical group repeated across columns (e.g. only "Injected Current" band)
        pass
    else:
        return False
    return True


def _build_groups(eff_top: list[str], bot: list[str]) -> list[TableColumnGroup] | None:
    w = len(eff_top)
    groups: list[TableColumnGroup] = []
    i = 0
    while i < w:
        g = eff_top[i].strip()
        if not g:
            return None
        j = i
        while j < w and eff_top[j].strip() == g:
            j += 1
        subs = [bot[k].strip() for k in range(i, j)]
        if not subs or any(not s for s in subs):
            return None
        groups.append(TableColumnGroup(group=g, columns=list(subs)))
        i = j
    if len(groups) >= 2 and any(len(g.columns) < 2 for g in groups):
        return None
    if len(groups) < 2:
        if len(groups) == 1 and len(groups[0].columns) >= 3:
            return groups
        return None
    return groups


def _flat_headers(groups: list[TableColumnGroup]) -> list[str]:
    out: list[str] = []
    for g in groups:
        for sub in g.columns:
            combined = f"{g.group} — {sub}".strip()
            out.append(combined)
    return out


def infer_grouped_header_layout(
    row_top: list[str],
    row_bottom: list[str],
) -> GroupedTableHeaderLayout | None:
    """
    If ``row_top`` + ``row_bottom`` form a grouped / subcolumn header, return the layout.

    Otherwise return ``None`` (caller may still merge the two rows as a flat header).
    """
    if len(row_top) != len(row_bottom) or len(row_top) < 3:
        return None
    eff = _forward_fill_top_groups(row_top)
    if eff is None or len(eff) != len(row_top):
        return None
    if not _looks_like_subheader_row(row_bottom, eff):
        logger.debug("Grouped header heuristic declined (top=%r first cells)", eff[:4])
        return None
    built = _build_groups(eff, row_bottom)
    if not built:
        return None
    flat = _flat_headers(built)
    if len(flat) != len(row_top):
        return None
    try:
        return GroupedTableHeaderLayout(grouped_headers=built, flat_headers=flat)
    except Exception:  # pragma: no cover - pydantic validation
        return None


__all__ = ["infer_grouped_header_layout"]
