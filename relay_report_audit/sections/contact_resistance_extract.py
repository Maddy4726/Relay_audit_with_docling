"""
Deterministic CONTACT RESISTANCE TEST extraction from Docling markdown.

Consumes ``extract_relay_section_tables`` pipe-table output, maps columns with
header heuristics, normalizes numeric resistance to micro-ohms, and validates
each row through Pydantic. No LLM involvement.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Final

from pydantic import ValidationError

from relay_report_audit.schemas.contact_resistance import (
    ContactResistanceMeasurement,
    ContactResistanceSectionResult,
)
from relay_report_audit.sections.markdown_table_extractor import extract_relay_section_tables

logger = logging.getLogger(__name__)

_SECTION: Final[str] = "CONTACT RESISTANCE TEST"
_SECTION_FILTER: Final[tuple[str, ...]] = ("CONTACT RESISTANCE TEST",)

_PHASE_HEADER_RE = re.compile(
    r"(phase|pole|circuit|wire|element|contact|leg|branch|sym(bol)?)",
    re.IGNORECASE,
)
_RES_HEADER_RE = re.compile(
    r"(resist|value|meas|reading|drop|contact|mω|µω|μω|uω|mohm|uohm|micro)",
    re.IGNORECASE,
)
_UNIT_HEADER_RE = re.compile(r"(^unit$|uom|units?)", re.IGNORECASE)
_HEADER_UNIT_HINT_RE = re.compile(
    r"(µω|μω|uω|micro\s*ohm|mω|mohm|milli\s*ohm|\bohm\b|ω)",
    re.IGNORECASE,
)

_CELL_VALUE_RE = re.compile(
    r"^\s*([+-]?\d+(?:[.,]\d+)?(?:\s*\d{3})*(?:[eE][+-]?\d+)?)\s*(.*)$",
)


def _parse_leading_float(num_token: str) -> float | None:
    """Parse a numeric token with optional European decimal comma."""
    s = num_token.strip().replace("\u00a0", "").replace(" ", "")
    if not s:
        return None
    if s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        v = float(s)
    except ValueError:
        return None
    if not math.isfinite(v):
        return None
    return v


def _normalize_unit_token(unit_raw: str) -> str | None:
    """Map free-text unit residue to ``MICRO_OHM``, ``MILLI_OHM``, or ``OHM``."""
    if not unit_raw or not unit_raw.strip():
        return None
    raw = unit_raw.strip()
    u = raw.lower()
    u_compact = re.sub(
        r"\s+",
        "",
        u.replace("µ", "u").replace("μ", "u").replace("ω", "ohm").replace("Ω", "ohm"),
    )
    if "micro" in u or "uohm" in u_compact:
        return "MICRO_OHM"
    if "milli" in u or "mohm" in u_compact or re.fullmatch(r"m\s*ω", raw, re.IGNORECASE):
        return "MILLI_OHM"
    if "ohm" in u_compact or "ω" in raw or "Ω" in unit_raw:
        return "OHM"
    return None


def _infer_unit_from_header(header: str) -> str | None:
    m = _HEADER_UNIT_HINT_RE.search(header)
    if not m:
        return None
    return _normalize_unit_token(m.group(0))


def _micro_ohm_from(value: float, unit: str) -> float:
    if unit == "MICRO_OHM":
        return value
    if unit == "MILLI_OHM":
        return value * 1000.0
    if unit == "OHM":
        return value * 1_000_000.0
    raise ValueError(unit)


def _parse_resistance_cell(
    cell: str,
    *,
    default_unit: str | None,
    unit_override: str | None,
    assumed_table_default_milli: bool,
) -> tuple[float, str, bool] | None:
    """
    Return ``(micro_ohm, canonical_unit, used_assumed_milli_fallback)`` or ``None``.

    The third element is ``True`` when resistance came from a bare number while the
    table-level milliohm fallback was active (no header hint, no unit column).
    """
    cell = cell.strip()
    if not cell:
        return None

    m = _CELL_VALUE_RE.match(cell)
    if not m:
        return None
    value = _parse_leading_float(m.group(1))
    if value is None:
        return None

    rest = m.group(2).strip()
    unit = _normalize_unit_token(rest) if rest else None
    if unit is None:
        unit = unit_override or default_unit
    if unit is None:
        return None

    try:
        micro = _micro_ohm_from(value, unit)
    except ValueError:
        return None

    used_assumed_milli = bool(
        assumed_table_default_milli and not rest and unit_override is None,
    )
    return micro, unit, used_assumed_milli


def _pick_column(headers: list[str], pattern: re.Pattern[str]) -> int | None:
    for i, h in enumerate(headers):
        if pattern.search(h.strip()):
            return i
    return None


def _infer_column_mapping(headers: list[str]) -> tuple[int | None, int | None, int | None, str | None]:
    """``(phase_idx, resistance_idx, unit_idx, default_unit_from_resistance_header)``."""
    phase_i = _pick_column(headers, _PHASE_HEADER_RE)
    res_i = _pick_column(headers, _RES_HEADER_RE)
    unit_i = _pick_column(headers, _UNIT_HEADER_RE)

    default_unit: str | None = None
    if res_i is not None:
        default_unit = _infer_unit_from_header(headers[res_i])

    logger.debug(
        "CONTACT RESISTANCE column map: phase=%s resistance=%s unit=%s header_default_unit=%s",
        phase_i,
        res_i,
        unit_i,
        default_unit,
    )
    return phase_i, res_i, unit_i, default_unit


def _aggregate_confidence(
    table_confidence: float,
    *,
    mapping_ok: bool,
    assumed_default_milli: bool,
    parse_failures: int,
    data_rows_seen: int,
    validated_rows: int,
) -> float:
    score = float(table_confidence)
    if not mapping_ok:
        score -= 0.45
    if assumed_default_milli:
        score -= 0.1
    score -= 0.06 * min(parse_failures, 8)
    if data_rows_seen > 0 and validated_rows == 0:
        score -= 0.25
    elif validated_rows < data_rows_seen:
        score -= 0.035 * (data_rows_seen - validated_rows)
    return max(0.0, min(1.0, round(score, 4)))


def extract_contact_resistance_from_markdown(markdown: str) -> ContactResistanceSectionResult:
    """
    Extract and validate CONTACT RESISTANCE TEST rows from full Docling markdown.

    Rows that fail parsing or Pydantic checks are omitted and logged at WARNING.
    """
    logger.info("Starting CONTACT RESISTANCE typed extraction (markdown chars=%d)", len(markdown))
    tables = extract_relay_section_tables(markdown, target_sections=_SECTION_FILTER)
    if not tables:
        logger.warning("No CONTACT RESISTANCE TEST markdown tables found")
        return ContactResistanceSectionResult(confidence=0.0, measurements=[])

    measurements: list[ContactResistanceMeasurement] = []
    best_table_conf = max(float(t.get("confidence", 0.0)) for t in tables)

    parse_failures = 0
    data_rows_seen = 0
    mapping_ok = False
    assumed_default_milli = False

    for t_idx, table in enumerate(tables):
        if table.get("section") != _SECTION:
            continue
        headers = [str(h).strip() for h in table.get("headers", [])]
        rows_raw = table.get("rows", [])
        logger.info(
            "Processing CONTACT RESISTANCE table %d: cols=%d rows=%d table_confidence=%.4f",
            t_idx,
            len(headers),
            len(rows_raw),
            float(table.get("confidence", 0.0)),
        )

        phase_i, res_i, unit_i, header_default_unit = _infer_column_mapping(headers)
        if phase_i is None or res_i is None:
            logger.error(
                "Table %d: missing required columns (phase=%s resistance=%s); skipping table",
                t_idx,
                phase_i,
                res_i,
            )
            continue

        mapping_ok = True
        default_unit = header_default_unit
        table_assumed_milli = default_unit is None and unit_i is None
        if table_assumed_milli:
            default_unit = "MILLI_OHM"
            logger.warning(
                "Table %d: no unit column or header hint; milliohm fallback may apply to bare numbers",
                t_idx,
            )

        saw_explicit_unit = False

        for r_idx, row in enumerate(rows_raw):
            data_rows_seen += 1
            if max(phase_i, res_i) >= len(row):
                parse_failures += 1
                logger.warning("Table %d row %d: insufficient cells", t_idx, r_idx)
                continue

            phase = str(row[phase_i]).strip()
            res_cell = str(row[res_i]).strip()
            unit_cell = ""
            if unit_i is not None and unit_i < len(row):
                unit_cell = str(row[unit_i]).strip()
            unit_override = _normalize_unit_token(unit_cell) if unit_cell else None

            parsed = _parse_resistance_cell(
                res_cell,
                default_unit=default_unit,
                unit_override=unit_override,
                assumed_table_default_milli=table_assumed_milli,
            )
            if parsed is None:
                parse_failures += 1
                logger.warning(
                    "Table %d row %d: unparsable resistance cell %r (phase=%r)",
                    t_idx,
                    r_idx,
                    res_cell,
                    phase,
                )
                continue

            micro, used_unit, used_assumed_milli = parsed
            if table_assumed_milli and not used_assumed_milli:
                saw_explicit_unit = True
            try:
                measurement = ContactResistanceMeasurement(
                    phase=phase,
                    resistance_micro_ohm=micro,
                )
            except ValidationError as exc:
                parse_failures += 1
                logger.warning(
                    "Table %d row %d: validation failed phase=%r micro_ohm=%.6g: %s",
                    t_idx,
                    r_idx,
                    phase,
                    micro,
                    exc,
                )
                continue

            measurements.append(measurement)
            logger.debug(
                "Table %d row %d: OK phase=%r micro_ohm=%.6g parsed_unit=%s assumed_milli_fallback=%s",
                t_idx,
                r_idx,
                measurement.phase,
                measurement.resistance_micro_ohm,
                used_unit,
                used_assumed_milli,
            )

        if table_assumed_milli and not saw_explicit_unit:
            assumed_default_milli = True

    conf = _aggregate_confidence(
        best_table_conf,
        mapping_ok=mapping_ok,
        assumed_default_milli=assumed_default_milli,
        parse_failures=parse_failures,
        data_rows_seen=data_rows_seen,
        validated_rows=len(measurements),
    )

    if not mapping_ok:
        logger.error("No CONTACT RESISTANCE table had both phase and resistance columns")
        conf = min(conf, 0.15)

    logger.info(
        "CONTACT RESISTANCE extraction finished: validated=%d skipped=%d confidence=%.4f",
        len(measurements),
        parse_failures,
        conf,
    )
    return ContactResistanceSectionResult(confidence=conf, measurements=measurements)


def extract_contact_resistance_section_dict(markdown: str) -> dict:
    """JSON-serializable dict (``model_dump``) for API layers."""
    return extract_contact_resistance_from_markdown(markdown).model_dump()


__all__ = [
    "extract_contact_resistance_from_markdown",
    "extract_contact_resistance_section_dict",
]
