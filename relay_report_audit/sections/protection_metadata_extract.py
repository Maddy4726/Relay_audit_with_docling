"""
Deterministic extraction of protection relay settings from free-text lines (Docling).

Parses prose before the first GFM pipe table in a section body. No LLMs.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Final

from relay_report_audit.schemas.protection_metadata import ProtectionMetadataBlock

logger = logging.getLogger(__name__)

_FLOAT: Final[str] = r"([-+]?\d*\.?\d+)"


def extract_protection_body_prose(body_md: str) -> str:
    """Return markdown lines before the first pipe-table row (``|...|``)."""
    lines: list[str] = []
    for line in body_md.splitlines():
        s = line.strip()
        if s.startswith("|") and s.count("|") >= 2:
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _split_prose_chunks(prose: str) -> list[str]:
    """Split on blank-line runs; merge orphan ``Time =`` lines into previous chunk."""
    parts = [p.strip() for p in re.split(r"\n\s*\n+", prose.strip()) if p.strip()]
    merged: list[str] = []
    for p in parts:
        if merged and re.match(r"^Time\s*=", p, re.I):
            merged[-1] = merged[-1] + "\n\n" + p
        else:
            merged.append(p)
    return merged


def _parse_float(tok: str) -> float | None:
    try:
        return float(tok.replace(",", ""))
    except ValueError:
        return None


def _strip_stage_prefix(text: str) -> tuple[str | None, str]:
    m = re.match(
        r"^\s*((?:STAGE\s*\d+|IDMT\s+STAGE\s*\d+))\s*:\s*(.*)$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, text


def _parse_delay_to_seconds(val: float, unit: str | None) -> float:
    u = (unit or "sec").lower().replace(".", "")
    if u in ("msec", "ms"):
        return val * 0.001
    if u in ("sec", "s", ""):
        return val
    return val


def parse_protection_metadata_chunk(raw: str) -> ProtectionMetadataBlock:
    """Parse a single prose chunk into ``raw`` + ``normalized`` fields."""
    stage_label, body = _strip_stage_prefix(raw)
    norm: dict[str, Any] = {}
    if stage_label:
        norm["stage_label"] = stage_label

    text = body

    m_set = re.search(r"Set\s+Current\s*=\s*" + _FLOAT + r"\s*x\s*In(?:\s*A)?", text, re.I)
    if m_set:
        v = _parse_float(m_set.group(1))
        if v is not None:
            norm["pickup_multiple_in"] = v

    m_tc = re.search(r"Time\s*const\.?\s*=\s*" + _FLOAT + r"\s*(min)?", text, re.I)
    if m_tc:
        v = _parse_float(m_tc.group(1))
        if v is not None:
            norm["time_constant_min"] = v

    m_delay = re.search(
        r"Delay\s*=\s*" + _FLOAT + r"\s*(mSec|ms|Sec|s)?",
        text,
        re.I,
    )
    if m_delay:
        v = _parse_float(m_delay.group(1))
        if v is not None:
            norm["delay_seconds"] = _parse_delay_to_seconds(v, m_delay.group(2))

    m_curve = re.search(r"CURVE\s*:\s*([A-Z]{1,4})\b", text, re.I)
    if m_curve:
        norm["curve_type"] = m_curve.group(1).upper()

    m_tms = re.search(r"TMS\s*=\s*" + _FLOAT, text, re.I)
    if m_tms:
        v = _parse_float(m_tms.group(1))
        if v is not None:
            norm["tms"] = v

    m_motor = re.search(
        r"Motor\s*St\.\s*Current\s*=\s*" + _FLOAT + r"\s*x\s*In\s*A",
        text,
        re.I,
    )
    if m_motor:
        v = _parse_float(m_motor.group(1))
        if v is not None:
            norm["motor_stall_current_multiple_in"] = v

    m_tup = re.search(r"Time\s*St\.\s*Up\s*=\s*" + _FLOAT + r"\s*(Sec|s)?", text, re.I)
    if m_tup:
        v = _parse_float(m_tup.group(1))
        if v is not None:
            norm["startup_time_limit_seconds"] = v

    m_logic = re.search(
        r"Logic\s+Delay\s*time\s*=\s*" + _FLOAT + r"\s*(Sec|s)?",
        text,
        re.I,
    )
    if m_logic:
        v = _parse_float(m_logic.group(1))
        if v is not None:
            norm["stall_logic_delay_seconds"] = v

    m_time_ef = re.search(r"(?:^|\n)\s*Time\s*=\s*" + _FLOAT, text, re.I)
    if m_time_ef:
        v = _parse_float(m_time_ef.group(1))
        if v is not None:
            norm["earth_fault_time_seconds"] = v

    if "curve_type" in norm and "tms" in norm:
        norm["protection_scheme_hint"] = "idmt"
    elif "curve_type" in norm and norm.get("curve_type") == "DT" and "delay_seconds" in norm:
        norm["protection_scheme_hint"] = "dtoc_dt"
    elif "time_constant_min" in norm:
        norm["protection_scheme_hint"] = "thermal_inverse_time"
    elif "motor_stall_current_multiple_in" in norm:
        norm["protection_scheme_hint"] = "startup_supervision"
    elif "stall_logic_delay_seconds" in norm:
        norm["protection_scheme_hint"] = "stall_during_run"
    elif "earth_fault_time_seconds" in norm:
        norm["protection_scheme_hint"] = "earth_fault"
    elif "delay_seconds" in norm and "pickup_multiple_in" in norm:
        norm["protection_scheme_hint"] = "dtoc"

    return ProtectionMetadataBlock(raw_metadata_text=raw.strip(), normalized=norm)


def parse_protection_metadata_blocks(prose: str) -> list[ProtectionMetadataBlock]:
    """Parse all prose chunks (e.g. separate IDMT stages)."""
    if not prose.strip():
        return []
    chunks = _split_prose_chunks(prose)
    out = [parse_protection_metadata_chunk(c) for c in chunks]
    logger.debug("Protection metadata: %d chunk(s) parsed", len(out))
    return out


def is_protection_test_section_heading(normalized_title: str) -> bool:
    """Whether this section title is one of the target protection tests."""
    u = normalized_title.upper()
    needles = (
        "SHORT CIRCUIT",
        "THERMAL O/L",
        "THERMAL O",
        "NEGATIVE SEQUENCE",
        "STARTUP SUPERVISION",
        "PROLONGED START",
        "STALL DURING RUNNING",
        "STALL DURING",
        "EARTH FAULT",
    )
    return any(n in u for n in needles)


__all__ = [
    "extract_protection_body_prose",
    "is_protection_test_section_heading",
    "parse_protection_metadata_blocks",
    "parse_protection_metadata_chunk",
]
