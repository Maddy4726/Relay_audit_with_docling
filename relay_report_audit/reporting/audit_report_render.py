"""
Human-readable rendering for ``AuditSynthesisResult`` (Markdown + plain text).

Deterministic templates only — no LLM, no imports from engineering validators
or aggregation logic beyond the synthesis schema types.
"""

from __future__ import annotations

import json
from typing import Any, Final

from relay_report_audit.schemas.audit_synthesis import (
    AuditFindingRecord,
    AuditSynthesisResult,
    SectionAuditSummary,
)

RENDERER_VERSION: Final[str] = "1"

_SEVERITY_ORDER: Final[dict[str, int]] = {"FAIL": 0, "WARN": 1, "REVIEW": 2}


def _sorted_findings(findings: list[AuditFindingRecord]) -> list[AuditFindingRecord]:
    return sorted(
        findings,
        key=lambda f: (_SEVERITY_ORDER.get(f.severity, 9), f.priority_rank, f.ordinal, f.section_slug, f.type),
    )


def _evidence_brief(evidence: dict[str, Any], *, max_len: int = 400) -> str:
    """Produce a single-line traceable evidence summary (deterministic)."""
    if not evidence:
        return "(no evidence payload)"
    ce = evidence.get("check_evidence")
    if isinstance(ce, dict):
        i_list = ce.get("points_I_A")
        t_list = ce.get("points_t_sec")
        if isinstance(i_list, list) and isinstance(t_list, list) and len(i_list) == len(t_list):
            pairs = [f"I={i}A t={t}s" for i, t in zip(i_list, t_list)]
            if pairs:
                return "Injection vs operated: " + "; ".join(pairs)
        if "measured_operated_seconds" in ce and "expected_delay_seconds" in ce:
            return (
                f"measured={ce.get('measured_operated_seconds')}s "
                f"expected_delay={ce.get('expected_delay_seconds')}s"
            )
        if "calculated_time_seconds" in ce and "operated_time_seconds" in ce:
            return (
                f"calculated={ce.get('calculated_time_seconds')}s "
                f"operated={ce.get('operated_time_seconds')}s"
            )
        if ce.get("raw_operated_cell") is not None:
            return f"raw_operated_cell={ce.get('raw_operated_cell')!r}"
    flags = evidence.get("flags")
    if isinstance(flags, list) and flags:
        return "flags: " + ", ".join(str(x) for x in flags)
    if "threshold" in evidence and "confidence" in evidence:
        return f"confidence={evidence.get('confidence')} threshold={evidence.get('threshold')}"
    # Fallback: stable JSON subset for traceability (no random key order in py3.7+ dict preserves insert order — use sorted keys)
    try:
        s = json.dumps(evidence, sort_keys=True, ensure_ascii=False, default=str)
    except TypeError:
        s = str(evidence)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def _operator_remarks(result: AuditSynthesisResult) -> str:
    s = result.summary
    st = result.overall_status
    parts = [
        f"The document audit completed with overall status **{st}**.",
        (
            f"Sections: {s.pass_sections} PASS, {s.warn_sections} WARN, "
            f"{s.fail_sections} FAIL, {s.review_sections} REVIEW (by section-level rollup)."
        ),
    ]
    if st == "PASS" and not result.findings:
        parts.append("No blocking or warning findings were recorded in the synthesis pass.")
    elif st == "FAIL":
        parts.append("At least one section failed engineering checks — review Key Findings before acceptance.")
    elif st == "WARN":
        parts.append("Some sections have warning-level engineering margins — confirm tolerances are acceptable.")
    elif st == "REVIEW":
        parts.append("Extraction or typed-output quality requires human verification on flagged sections.")
    return " ".join(parts)


def _operator_remarks_plain(result: AuditSynthesisResult) -> str:
    # Same content without markdown bold
    t = _operator_remarks(result).replace("**", "")
    return t


def _confidence_block_md(result: AuditSynthesisResult) -> str:
    c = result.confidence
    lines = [
        f"- **Document confidence:** {c.document_confidence:.3f} (0–1 scale; mean of section confidences).",
    ]
    if c.low_confidence_sections:
        lines.append("- **Low extraction confidence (sections):**")
        for ref in c.low_confidence_sections:
            lines.append(
                f"  - `{ref.section_slug}` — {ref.heading_normalized} "
                f"(conf={ref.confidence:.3f}, {ref.extractor_id}, {ref.reason})"
            )
    else:
        lines.append("- **Low extraction confidence:** none flagged.")
    return "\n".join(lines)


def _confidence_block_plain(result: AuditSynthesisResult) -> str:
    c = result.confidence
    lines = [
        f"Document confidence: {c.document_confidence:.3f} (0-1 scale; mean of section confidences).",
    ]
    if c.low_confidence_sections:
        lines.append("Low extraction confidence (sections):")
        for ref in c.low_confidence_sections:
            lines.append(
                f"  - {ref.section_slug} | {ref.heading_normalized} | "
                f"conf={ref.confidence:.3f} | {ref.extractor_id} | {ref.reason}"
            )
    else:
        lines.append("Low extraction confidence: none flagged.")
    return "\n".join(lines)


def _section_status_table_md(summaries: list[SectionAuditSummary]) -> str:
    if not summaries:
        return "_No sections._"
    rows = [
        "| # | Section | Status | Conf | Extractor |",
        "|---|---------|--------|------|-------------|",
    ]
    for s in sorted(summaries, key=lambda x: x.ordinal):
        rows.append(
            f"| {s.ordinal} | {s.heading_normalized} | **{s.status}** | "
            f"{s.confidence:.3f} | `{s.extractor_id}` |"
        )
    return "\n".join(rows)


def _section_status_plain(summaries: list[SectionAuditSummary]) -> str:
    if not summaries:
        return "(no sections)"
    lines = ["#  Section slug  |  Status  |  Conf  |  Extractor"]
    for s in sorted(summaries, key=lambda x: x.ordinal):
        lines.append(
            f"{s.ordinal:3d}  {s.section_slug:40s}  {s.status:6s}  {s.confidence:.3f}  {s.extractor_id}"
        )
    return "\n".join(lines)


def _grouped_findings_md(findings: list[AuditFindingRecord]) -> str:
    if not findings:
        return "_No findings._\n"
    by_slug: dict[str, list[AuditFindingRecord]] = {}
    order: list[str] = []
    for f in _sorted_findings(findings):
        if f.section_slug not in by_slug:
            order.append(f.section_slug)
            by_slug[f.section_slug] = []
        by_slug[f.section_slug].append(f)
    chunks: list[str] = []
    n = 1
    for slug in order:
        grp = by_slug[slug]
        head = grp[0].section
        chunks.append(f"### {n}. {head}\n\n*Section slug:* `{slug}`\n")
        for f in grp:
            msg = f.message or f.type.replace("_", " ")
            ev = _evidence_brief(f.evidence)
            line = f"- **{f.severity}** ({f.type}): {msg}\n  - Evidence: {ev}"
            if f.source_line_1based is not None:
                line += f"\n  - Source line: {f.source_line_1based}"
            chunks.append(line + "\n")
        n += 1
    return "\n".join(chunks)


def _grouped_findings_plain(findings: list[AuditFindingRecord]) -> str:
    if not findings:
        return "(no findings)\n"
    by_slug: dict[str, list[AuditFindingRecord]] = {}
    order: list[str] = []
    for f in _sorted_findings(findings):
        if f.section_slug not in by_slug:
            order.append(f.section_slug)
            by_slug[f.section_slug] = []
        by_slug[f.section_slug].append(f)
    lines: list[str] = []
    n = 1
    for slug in order:
        grp = by_slug[slug]
        lines.append(f"{n}. {grp[0].section}  [{slug}]")
        for f in grp:
            msg = f.message or f.type.replace("_", " ")
            ev = _evidence_brief(f.evidence)
            lines.append(f"   - {f.severity}: {f.type}: {msg}")
            lines.append(f"     Evidence: {ev}")
            if f.source_line_1based is not None:
                lines.append(f"     Source line: {f.source_line_1based}")
        lines.append("")
        n += 1
    return "\n".join(lines)


def render_audit_report_markdown(
    result: AuditSynthesisResult,
    *,
    title: str = "Relay Audit Summary",
) -> str:
    """Return a concise engineering Markdown audit report."""
    s = result.summary
    lines = [
        f"# {title}",
        "",
        f"**Overall status:** {result.overall_status}",
        "",
        f"_Renderer v{RENDERER_VERSION} (deterministic)._",
        "",
        "## Operator remarks",
        "",
        _operator_remarks(result),
        "",
        "## Summary",
        "",
        f"- **PASS sections:** {s.pass_sections}",
        f"- **WARN sections:** {s.warn_sections}",
        f"- **FAIL sections:** {s.fail_sections}",
        f"- **REVIEW sections:** {s.review_sections}",
        "",
        "## Confidence",
        "",
        _confidence_block_md(result),
        "",
        "## Section status",
        "",
        _section_status_table_md(result.section_summaries),
        "",
        "## Key findings",
        "",
        "(Ordered **FAIL → WARN → REVIEW**, then document order.)",
        "",
        _grouped_findings_md(result.findings),
        "## Review recommendations",
        "",
    ]
    if result.review_recommendations:
        for r in result.review_recommendations:
            lines.append(f"- {r}")
    else:
        lines.append("_None._")
    lines.append("")
    return "\n".join(lines)


def render_audit_report_plain_text(
    result: AuditSynthesisResult,
    *,
    title: str = "RELAY AUDIT SUMMARY",
) -> str:
    """Return a plain-text audit summary suitable for logs or email bodies."""
    s = result.summary
    width = 72
    bar = "=" * width
    lines = [
        bar,
        title.center(width),
        bar,
        "",
        f"OVERALL STATUS: {result.overall_status}",
        f"(renderer v{RENDERER_VERSION}, deterministic)",
        "",
        "OPERATOR REMARKS",
        "-" * width,
        _operator_remarks_plain(result),
        "",
        "SUMMARY (sections)",
        "-" * width,
        f"  PASS:    {s.pass_sections}",
        f"  WARN:    {s.warn_sections}",
        f"  FAIL:    {s.fail_sections}",
        f"  REVIEW:  {s.review_sections}",
        "",
        "CONFIDENCE",
        "-" * width,
        _confidence_block_plain(result),
        "",
        "SECTION STATUS",
        "-" * width,
        _section_status_plain(result.section_summaries),
        "",
        "KEY FINDINGS (FAIL > WARN > REVIEW)",
        "-" * width,
        _grouped_findings_plain(result.findings),
        "REVIEW RECOMMENDATIONS",
        "-" * width,
    ]
    if result.review_recommendations:
        for r in result.review_recommendations:
            lines.append(f"  * {r}")
    else:
        lines.append("  (none)")
    lines.extend(["", bar, ""])
    return "\n".join(lines)


__all__ = [
    "RENDERER_VERSION",
    "render_audit_report_markdown",
    "render_audit_report_plain_text",
]
