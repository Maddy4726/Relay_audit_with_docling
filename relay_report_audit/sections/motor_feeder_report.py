"""
Motor feeder / LCP style test report: discover every header in Docling markdown and
route each body to typed extractors (contact resistance, CT ratio) or generic tables.

Designed for the BHILAI-style PDF layout; additional PDFs may add more sections—this
module always emits one record per detected header so shorter/longer reports are
handled uniformly.
"""

from __future__ import annotations

import logging
import re
from typing import Final

from relay_report_audit.schemas.motor_feeder_report import (
    MotorFeederReportBundle,
    MotorFeederSectionRecord,
)
from relay_report_audit.sections.contact_resistance_extract import (
    extract_contact_resistance_section_dict,
)
from relay_report_audit.sections.ct_ratio_extract import (
    _is_ct_ratio_section_title,
    extract_ct_ratio_test_from_markdown,
)
from relay_report_audit.sections.markdown_table_extractor import (
    _normalize_section_title,
    _parse_atx_heading,
    _parse_list_marker_section,
    extract_pipe_tables_from_markdown_fragment,
)

logger = logging.getLogger(__name__)

_CONTACT_RES_NORM: Final[str] = "CONTACT RESISTANCE TEST"

_CAPS_LINE_RE = re.compile(r"^[A-Z0-9\s,.:/&()'\-]{6,}$")


def _parse_numbered_prose_heading(line: str) -> str | None:
    """Return normalized title text from ``N.N Title`` / ``N. Title`` lines (no list bullet)."""
    s = line.strip()
    for pat in (r"^\s*\d+\.\d+\s+(.+)$", r"^\s*\d+\.\s+(.+)$"):
        m = re.match(pat, s)
        if m:
            return _normalize_section_title(m.group(1))
    return None


def _is_caps_banner(line: str) -> bool:
    s = line.strip()
    if len(s) < 12 or "|" in s or s.startswith("#"):
        return False
    if "&amp;" in s:
        s = s.replace("&amp;", "&")
    if not _CAPS_LINE_RE.match(s):
        return False
    if s != s.upper():
        return False
    if not re.search(r"[A-Z]{5,}", s):
        return False
    digits = sum(ch.isdigit() for ch in s)
    if digits > len(s) * 0.35:
        return False
    return True


def _slug(norm: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", norm.lower()).strip("-")
    return (s[:120] if s else "section")


def _classify_extractor(normalized_title: str, raw_header: str) -> str:
    n = normalized_title.upper()
    if n == "PREAMBLE" or raw_header == "__PREAMBLE__":
        return "preamble"
    if "CONTACT" in n and "RESISTANCE" in n:
        return "contact_resistance"
    if _is_ct_ratio_section_title(n) or _is_ct_ratio_section_title(
        _normalize_section_title(raw_header)
    ):
        return "ct_ratio"
    return "generic_tables"


def _discover_headers(lines: list[str]) -> list[tuple[int, str, str, str]]:
    """
    Return tuples ``(line_index_0based, kind, raw_header, normalized_title)`` in file order.

    Priority per line: ATX → list marker → numbered prose → ALL CAPS banner.
    """
    found: list[tuple[int, str, str, str]] = []
    for idx, line in enumerate(lines):
        raw = line.strip()
        if not raw:
            continue
        atx = _parse_atx_heading(line)
        if atx is not None:
            _level, title = atx
            found.append((idx, "atx", raw, _normalize_section_title(title)))
            continue
        lst = _parse_list_marker_section(line)
        if lst is not None:
            _num, rest = lst
            found.append((idx, "list", raw, _normalize_section_title(rest)))
            continue
        prose_norm = _parse_numbered_prose_heading(line)
        if prose_norm is not None:
            found.append((idx, "numbered", raw, prose_norm))
            continue
        if _is_caps_banner(line):
            found.append((idx, "caps", raw, _normalize_section_title(raw)))
            continue
    return found


def process_motor_feeder_markdown(markdown: str) -> MotorFeederReportBundle:
    """
    Walk every report-style header and attach structured payloads.

    * **contact_resistance** — scoped markdown with synthetic ``##`` heading fed to the
      existing contact resistance pipeline.
    * **ct_ratio** — scoped markdown prefixed with the original header line for CTR text.
    * **generic_tables** — all pipe tables in the section body via the shared GFM parser.
    * **preamble** — content before the first header (if any).
    """
    lines = markdown.splitlines()
    n = len(lines)
    headers = _discover_headers(lines)
    logger.info("Motor feeder report: %d lines, %d header anchors", n, len(headers))

    sections: list[MotorFeederSectionRecord] = []
    order = 0

    first_idx = headers[0][0] if headers else n
    if first_idx > 0:
        preamble_body = "\n".join(lines[0:first_idx])
        tables = extract_pipe_tables_from_markdown_fragment(
            preamble_body,
            section_label="PREAMBLE",
        )
        conf = max((t.get("confidence") or 0.0) for t in tables) if tables else 0.0
        sections.append(
            MotorFeederSectionRecord(
                order_index=order,
                header_line_1based=1,
                header_kind="preamble",
                raw_header="__PREAMBLE__",
                normalized_title="PREAMBLE",
                section_slug="preamble",
                extractor_id="preamble",
                confidence=round(conf, 4),
                payload={"tables": tables, "table_count": len(tables)},
            )
        )
        order += 1

    for i, (hidx, kind, raw, norm) in enumerate(headers):
        body_end = headers[i + 1][0] if i + 1 < len(headers) else n
        body_lines = lines[hidx + 1 : body_end]
        body_md = "\n".join(body_lines)
        ext = _classify_extractor(norm, raw)
        slug = _slug(norm)
        conf = 0.0
        payload: dict = {}

        logger.info(
            "Section [%d] line=%d kind=%s slug=%s extractor=%s title=%r",
            order,
            hidx + 1,
            kind,
            slug,
            ext,
            raw[:80],
        )

        if ext == "contact_resistance":
            synth = f"## {_CONTACT_RES_NORM}\n\n{body_md}"
            payload = extract_contact_resistance_section_dict(synth)
            conf = float(payload.get("confidence") or 0.0)
        elif ext == "ct_ratio":
            synth = f"{raw}\n\n{body_md}"
            ctr = extract_ct_ratio_test_from_markdown(synth)
            payload = ctr.model_dump(exclude_none=True)
            conf = float(payload.get("confidence") or 0.0)
            if not payload.get("measurements"):
                fb = extract_pipe_tables_from_markdown_fragment(body_md, section_label=norm or slug)
                if fb:
                    payload["tables_fallback"] = fb
                    conf = max(conf, max(t.get("confidence") or 0.0 for t in fb))
        else:
            tables = extract_pipe_tables_from_markdown_fragment(body_md, section_label=norm or slug)
            payload = {
                "tables": tables,
                "table_count": len(tables),
                "confidence_tables": [t.get("confidence") for t in tables],
            }
            conf = max((t.get("confidence") or 0.0) for t in tables) if tables else 0.0

        sections.append(
            MotorFeederSectionRecord(
                order_index=order,
                header_line_1based=hidx + 1,
                header_kind=kind,
                raw_header=raw,
                normalized_title=norm,
                section_slug=slug,
                extractor_id=ext,
                confidence=round(conf, 4),
                payload=payload,
            )
        )
        order += 1

    return MotorFeederReportBundle(source_line_count=n, sections=sections)


def process_motor_feeder_markdown_dict(markdown: str) -> dict:
    """JSON-serializable bundle."""
    return process_motor_feeder_markdown(markdown).model_dump()


__all__ = [
    "process_motor_feeder_markdown",
    "process_motor_feeder_markdown_dict",
]
