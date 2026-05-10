"""
Build a structured ``ReportDocumentJson`` from Docling markdown: one JSON object per
heading, with tables, optional typed payloads, numeric ``outline``, and ``parent``.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Final

from relay_report_audit.schemas.report_document import (
    ReportDocumentJson,
    ReportSectionJson,
    SectionTableData,
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
_DEFAULT_JSON_SUBDIR: Final[str] = "extracted/report_json"
_FORBIDDEN_FILENAME_CHARS: Final[frozenset[str]] = frozenset('<>:"/\\|?*\n\r\t')


def default_report_json_dir() -> Path:
    """Default directory for persisted ``ReportDocumentJson`` files (under cwd unless absolute)."""
    return Path(_DEFAULT_JSON_SUBDIR).resolve()


def _sanitize_json_stem(stem: str) -> str:
    cleaned = "".join("_" if ch in _FORBIDDEN_FILENAME_CHARS else ch for ch in stem)
    cleaned = cleaned.strip().rstrip(".")
    return (cleaned[:200] if cleaned else "report_sections")


def _resolve_json_output_path(
    json_dir: str | Path,
    *,
    output_filename: str | Path | None,
    json_stem: str | None,
) -> Path:
    base = Path(json_dir).expanduser().resolve()
    if output_filename is not None:
        p = Path(output_filename)
        if p.is_absolute():
            return p
        name = p.name
        if not name.lower().endswith(".json"):
            name = f"{name}.json"
        return base / name
    stem = _sanitize_json_stem(json_stem or "report_sections")
    return base / f"{stem}.json"


def write_report_document_json_file(
    doc: ReportDocumentJson,
    path: str | Path,
    *,
    indent: int = 2,
) -> Path:
    """Serialize ``doc`` to UTF-8 JSON; create parent directories as needed."""
    out = Path(path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = doc.model_dump_json(indent=indent)
    out.write_text(payload + "\n", encoding="utf-8")
    logger.info("Wrote report JSON (%d sections) to %s", len(doc.sections), out)
    return out


def _parse_numbered_prose_heading(line: str) -> str | None:
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


def _parse_outline_ints(raw: str, kind: str) -> list[int] | None:
    """Parse leading numeric clause like ``4.2`` or list ``- 5.0`` into ``[4, 2]`` / ``[5, 0]``."""
    s = raw.strip()
    if kind == "list":
        m = re.match(r"^\s*[-*+]\s*((?:\d+\.)*\d+)", s)
    elif kind == "numbered":
        m = re.match(r"^\s*((?:\d+\.)*\d+)", s)
    else:
        return None
    if not m:
        return None
    token = m.group(1)
    parts = token.split(".")
    out: list[int] = []
    for p in parts:
        if not p.isdigit():
            return None
        out.append(int(p))
    return out or None


def _strict_prefix(a: list[int], b: list[int]) -> bool:
    return len(a) < len(b) and b[: len(a)] == a


def _longest_prefix_parent(
    prior: list[ReportSectionJson],
    outline: list[int],
) -> str | None:
    best_slug: str | None = None
    best_len = -1
    for s in prior:
        if not s.outline:
            continue
        if _strict_prefix(s.outline, outline) and len(s.outline) > best_len:
            best_len = len(s.outline)
            best_slug = s.section_slug
    return best_slug


def _nearest_caps_parent(prior: list[ReportSectionJson]) -> str | None:
    for s in reversed(prior):
        if s.heading_kind == "caps":
            return s.section_slug
    return None


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


def _tables_models(tdicts: list[dict]) -> list[SectionTableData]:
    out: list[SectionTableData] = []
    for t in tdicts:
        out.append(
            SectionTableData(
                headers=list(t.get("headers") or []),
                rows=[list(r) for r in (t.get("rows") or [])],
                confidence=float(t.get("confidence") or 0.0),
                header_depth=int(t.get("header_depth") or 1),
                grouped_headers=t.get("grouped_headers"),
            )
        )
    return out


def build_report_document(
    markdown: str,
    *,
    json_dir: str | Path | None = None,
    output_filename: str | Path | None = None,
    json_stem: str | None = None,
    json_indent: int = 2,
) -> ReportDocumentJson:
    """
    Produce one ``ReportSectionJson`` per detected heading, with parent/outline metadata.

    When ``json_dir`` is set, the same model is written as UTF-8 JSON under that directory
    (default filename ``report_sections.json``, or ``json_stem`` / ``output_filename``).

    Parent assignment (deterministic, no LLM):

    #. If the heading has a numeric ``outline`` (list / numbered clause), set
       ``parent_section_slug`` to the nearest **previous** section whose ``outline`` is a
       strict prefix (e.g. ``[4]`` parent of ``[4, 2]`` when present).
    #. Else if it has a **multi-segment** ``outline`` but no prefix match, use the
       nearest **previous** ``caps`` banner (e.g. ``TRANSFORMER TESTING`` for ``[5, 0]``).
       Single-segment outlines (e.g. ``[3]`` for ``3. RATIO TEST``) do **not** use this
       fallback, to avoid attaching unrelated chapters.
    #. Otherwise ``parent_section_slug`` is ``None``.
    """
    lines = markdown.splitlines()
    n = len(lines)
    headers = _discover_headers(lines)
    logger.info("Report document: %d lines, %d headings", n, len(headers))

    built: list[ReportSectionJson] = []
    ordinal = 0

    def append_section(
        *,
        line_1based: int,
        kind: str,
        raw: str,
        norm: str,
        body_md: str,
    ) -> None:
        nonlocal ordinal, built
        slug = _slug(norm)
        outline = _parse_outline_ints(raw, kind) if kind in ("list", "numbered") else None
        parent: str | None = None
        if outline:
            parent = _longest_prefix_parent(built, outline)
            if parent is None and len(outline) >= 2:
                parent = _nearest_caps_parent(built)

        ext = _classify_extractor(norm, raw)
        typed: dict | None = None
        conf = 0.0
        tables_raw: list[dict]

        if ext == "contact_resistance":
            synth = f"## {_CONTACT_RES_NORM}\n\n{body_md}"
            typed = extract_contact_resistance_section_dict(synth)
            conf = float(typed.get("confidence") or 0.0)
            tables_raw = extract_pipe_tables_from_markdown_fragment(body_md, section_label=slug)
        elif ext == "ct_ratio":
            synth = f"{raw}\n\n{body_md}"
            ctr = extract_ct_ratio_test_from_markdown(synth)
            typed = ctr.model_dump(exclude_none=True)
            conf = float(typed.get("confidence") or 0.0)
            tables_raw = extract_pipe_tables_from_markdown_fragment(body_md, section_label=slug)
            if not typed.get("measurements"):
                if tables_raw:
                    typed["tables_fallback"] = tables_raw
                    conf = max(conf, max(t.get("confidence") or 0.0 for t in tables_raw))
        elif ext == "preamble":
            tables_raw = extract_pipe_tables_from_markdown_fragment(body_md, section_label="PREAMBLE")
            conf = max((t.get("confidence") or 0.0 for t in tables_raw), default=0.0)
        else:
            tables_raw = extract_pipe_tables_from_markdown_fragment(body_md, section_label=slug)
            conf = max((t.get("confidence") or 0.0 for t in tables_raw), default=0.0)

        tables = _tables_models(tables_raw)

        built.append(
            ReportSectionJson(
                ordinal=ordinal,
                source_line_1based=line_1based,
                section_slug=slug,
                heading_kind=kind,  # type: ignore[arg-type]
                heading_raw=raw,
                heading_normalized=norm,
                outline=outline,
                parent_section_slug=parent,
                extractor_id=ext,  # type: ignore[arg-type]
                body_markdown=body_md,
                tables=tables,
                typed_payload=typed,
                confidence=round(conf, 4),
            )
        )
        ordinal += 1

    first_idx = headers[0][0] if headers else n
    if first_idx > 0:
        preamble_body = "\n".join(lines[0:first_idx])
        append_section(
            line_1based=1,
            kind="preamble",
            raw="__PREAMBLE__",
            norm="PREAMBLE",
            body_md=preamble_body,
        )

    for i, (hidx, kind, raw, norm) in enumerate(headers):
        body_end = headers[i + 1][0] if i + 1 < len(headers) else n
        body_md = "\n".join(lines[hidx + 1 : body_end])
        append_section(
            line_1based=hidx + 1,
            kind=kind,
            raw=raw,
            norm=norm,
            body_md=body_md,
        )
        logger.info(
            "Heading ord=%d line=%d slug=%s outline=%s parent=%s extractor=%s",
            ordinal - 1,
            hidx + 1,
            built[-1].section_slug,
            built[-1].outline,
            built[-1].parent_section_slug,
            built[-1].extractor_id,
        )

    doc = ReportDocumentJson(markdown_line_count=n, sections=built)
    if json_dir is not None:
        destination = _resolve_json_output_path(
            json_dir,
            output_filename=output_filename,
            json_stem=json_stem,
        )
        write_report_document_json_file(doc, destination, indent=json_indent)
    return doc


def build_report_document_to_json_file(
    markdown: str,
    *,
    json_dir: str | Path | None = None,
    output_filename: str | Path | None = None,
    json_stem: str | None = None,
    json_indent: int = 2,
) -> tuple[ReportDocumentJson, Path]:
    """
    Build the report document and persist JSON under ``extracted/report_json/`` by default.

    Returns the model and the path written.
    """
    base = default_report_json_dir() if json_dir is None else json_dir
    doc = build_report_document(
        markdown,
        json_dir=base,
        output_filename=output_filename,
        json_stem=json_stem,
        json_indent=json_indent,
    )
    path = _resolve_json_output_path(
        Path(base).expanduser().resolve(),
        output_filename=output_filename,
        json_stem=json_stem,
    )
    return doc, path


def build_report_document_dict(
    markdown: str,
    *,
    json_dir: str | Path | None = None,
    output_filename: str | Path | None = None,
    json_stem: str | None = None,
    json_indent: int = 2,
) -> dict:
    return build_report_document(
        markdown,
        json_dir=json_dir,
        output_filename=output_filename,
        json_stem=json_stem,
        json_indent=json_indent,
    ).model_dump()


__all__ = [
    "build_report_document",
    "build_report_document_dict",
    "build_report_document_to_json_file",
    "default_report_json_dir",
    "write_report_document_json_file",
]
