"""
Deterministic audit synthesis: roll up ``ReportSectionJson`` rows into one result.

Engineering checks remain in ``protection_engineering_validation``; this module only
aggregates statuses, findings, and confidence — no per-check math.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Iterable, Sequence

from relay_report_audit.schemas.audit_synthesis import (
    AuditConfidenceSummary,
    AuditFindingRecord,
    AuditSummaryCounts,
    AuditSynthesisResult,
    LowConfidenceSectionRef,
    SectionAuditSummary,
)
from relay_report_audit.schemas.report_document import ReportSectionJson

# --- Extensible severity / priority (lower rank = more severe / higher priority) ---
_SEVERITY_BASE: Final[dict[str, int]] = {
    "FAIL": 0,
    "WARN": 10,
    "REVIEW": 20,
    "PASS": 100,
}

# Runtime overlays (see ``register_severity`` / ``reset_severity_registry``).
_EXTRA_SEVERITY: dict[str, int] = {}

FINDING_SEVERITY_RANK: Final[dict[str, int]] = {
    "FAIL": 0,
    "WARN": 1,
    "REVIEW": 2,
}


def severity_priority(status: str) -> int:
    """Return sortable priority for a section or overall status (lower = worse)."""
    u = status.upper()
    if u in _EXTRA_SEVERITY:
        return _EXTRA_SEVERITY[u]
    return _SEVERITY_BASE.get(u, 50)


def register_severity(name: str, priority: int) -> None:
    """
    Register a custom status name for roll-ups (lower ``priority`` = more severe).

    Prefer small positive integers; built-in FAIL/WARN/REVIEW/PASS use 0/10/20/100.
    """
    _EXTRA_SEVERITY[name.upper()] = priority


def reset_severity_registry() -> None:
    """Clear custom severities (intended for tests)."""
    _EXTRA_SEVERITY.clear()


@dataclass
class AuditSynthesisSettings:
    """Thresholds for REVIEW elevation (deterministic, tunable per deployment)."""

    section_confidence_review: float = 0.72
    contact_resistance_typed_review: float = 0.74
    ct_ratio_typed_review: float = 0.82


def _rollup_engineering_from_checks(checks: list[dict[str, Any]]) -> str | None:
    """
    Derive worst actionable status from protection check list.

    SKIP does not escalate; an all-SKIP list yields ``None`` (no engineering signal).
    """
    actionable = [c for c in checks if c.get("status") not in (None, "SKIP")]
    if not actionable:
        return None
    if any(c.get("status") == "FAIL" for c in actionable):
        return "FAIL"
    if any(c.get("status") == "WARN" for c in actionable):
        return "WARN"
    return "PASS"


def _count_check_statuses(checks: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in checks:
        st = str(c.get("status") or "UNKNOWN")
        counts[st] = counts.get(st, 0) + 1
    return counts


def _typed_payload_flags(section: ReportSectionJson, settings: AuditSynthesisSettings) -> list[str]:
    flags: list[str] = []
    tp = section.typed_payload
    if not isinstance(tp, dict):
        return flags
    ext = section.extractor_id
    tconf = tp.get("confidence")
    try:
        tc = float(tconf) if tconf is not None else section.confidence
    except (TypeError, ValueError):
        tc = section.confidence
    meas = tp.get("measurements")

    if ext == "contact_resistance":
        if not meas:
            flags.append("contact_resistance_empty_measurements")
        if tc < settings.contact_resistance_typed_review:
            flags.append("contact_resistance_low_typed_confidence")
    elif ext == "ct_ratio":
        if not meas:
            flags.append("ct_ratio_empty_measurements")
        if tc < settings.ct_ratio_typed_review:
            flags.append("ct_ratio_low_typed_confidence")
    return flags


def _derive_section_status(
    section: ReportSectionJson,
    *,
    settings: AuditSynthesisSettings,
) -> tuple[str, list[str]]:
    """
    Return (status, typed_flags).

    Precedence: FAIL > WARN > REVIEW > PASS (REVIEW from low confidence or typed flags).
    """
    typed_flags = _typed_payload_flags(section, settings)
    candidates: list[str] = ["PASS"]

    pev = section.protection_engineering_validation
    if isinstance(pev, dict):
        checks = pev.get("checks")
        if isinstance(checks, list):
            eng = _rollup_engineering_from_checks([c for c in checks if isinstance(c, dict)])
            if eng:
                candidates.append(eng)

    if section.confidence < settings.section_confidence_review:
        candidates.append("REVIEW")

    if typed_flags:
        candidates.append("REVIEW")

    # Worst wins
    return min(candidates, key=severity_priority), typed_flags


def _overall_from_section_statuses(statuses: Iterable[str]) -> str:
    st = list(statuses)
    if not st:
        return "PASS"
    return min(st, key=severity_priority)


def synthesize_report_audit(
    sections: Sequence[ReportSectionJson],
    *,
    settings: AuditSynthesisSettings | None = None,
) -> AuditSynthesisResult:
    """
    Build a single ``AuditSynthesisResult`` from ordered ``ReportSectionJson`` rows.

    Preserves full ``evidence`` dicts from each protection engineering check included
    as a finding (FAIL/WARN only). REVIEW findings carry synthesized evidence including
    section references and raw confidence values.
    """
    cfg = settings or AuditSynthesisSettings()
    summaries: list[SectionAuditSummary] = []
    findings: list[AuditFindingRecord] = []
    low_conf: list[LowConfidenceSectionRef] = []

    summary = AuditSummaryCounts()
    section_statuses: list[str] = []

    n = len(sections)
    doc_conf = 0.0
    if n:
        doc_conf = sum(float(s.confidence) for s in sections) / float(n)

    for section in sections:
        status, typed_flags = _derive_section_status(section, settings=cfg)
        section_statuses.append(status)

        pev = section.protection_engineering_validation
        checks: list[dict[str, Any]] = []
        if isinstance(pev, dict):
            raw_checks = pev.get("checks")
            if isinstance(raw_checks, list):
                checks = [c for c in raw_checks if isinstance(c, dict)]

        summaries.append(
            SectionAuditSummary(
                ordinal=section.ordinal,
                section_slug=section.section_slug,
                heading_normalized=section.heading_normalized,
                extractor_id=section.extractor_id,
                status=status,  # type: ignore[arg-type]
                confidence=float(section.confidence),
                protection_checks=_count_check_statuses(checks),
                typed_payload_flags=typed_flags,
            )
        )

        if status == "PASS":
            summary.pass_sections += 1
        elif status == "WARN":
            summary.warn_sections += 1
        elif status == "FAIL":
            summary.fail_sections += 1
        else:
            summary.review_sections += 1

        if section.confidence < cfg.section_confidence_review:
            low_conf.append(
                LowConfidenceSectionRef(
                    section_slug=section.section_slug,
                    heading_normalized=section.heading_normalized,
                    confidence=float(section.confidence),
                    extractor_id=section.extractor_id,
                    reason="section_confidence_below_threshold",
                )
            )

        # Findings from engineering checks (FAIL / WARN only; preserve evidence)
        for chk in checks:
            cst = chk.get("status")
            if cst not in ("FAIL", "WARN"):
                continue
            sev = cst  # type: ignore[assignment]
            findings.append(
                AuditFindingRecord(
                    severity=sev,  # type: ignore[arg-type]
                    priority_rank=FINDING_SEVERITY_RANK[str(sev)],
                    section=section.heading_normalized,
                    section_slug=section.section_slug,
                    source_line_1based=section.source_line_1based,
                    ordinal=section.ordinal,
                    type=str(chk.get("type") or "unknown_check"),
                    message=chk.get("message") if isinstance(chk.get("message"), str) else None,
                    evidence={
                        "section_slug": section.section_slug,
                        "heading_raw": section.heading_raw,
                        "heading_normalized": section.heading_normalized,
                        "source_line_1based": section.source_line_1based,
                        "ordinal": section.ordinal,
                        "extractor_id": section.extractor_id,
                        "section_confidence": float(section.confidence),
                        "check": chk,
                        "check_evidence": chk.get("evidence") if isinstance(chk.get("evidence"), dict) else {},
                    },
                )
            )

        # REVIEW findings from extraction / typed heuristics (not already covered by FAIL/WARN)
        if typed_flags and status != "FAIL":
            findings.append(
                AuditFindingRecord(
                    severity="REVIEW",
                    priority_rank=FINDING_SEVERITY_RANK["REVIEW"],
                    section=section.heading_normalized,
                    section_slug=section.section_slug,
                    source_line_1based=section.source_line_1based,
                    ordinal=section.ordinal,
                    type="typed_payload_review",
                    message="Typed extractor quality flags require human review.",
                    evidence={
                        "section_slug": section.section_slug,
                        "heading_raw": section.heading_raw,
                        "heading_normalized": section.heading_normalized,
                        "ordinal": section.ordinal,
                        "extractor_id": section.extractor_id,
                        "typed_payload": section.typed_payload,
                        "flags": typed_flags,
                        "section_confidence": float(section.confidence),
                    },
                )
            )

        if section.confidence < cfg.section_confidence_review and status != "FAIL":
            # Avoid duplicate when typed_flags already produced a REVIEW finding.
            if not typed_flags:
                findings.append(
                    AuditFindingRecord(
                        severity="REVIEW",
                        priority_rank=FINDING_SEVERITY_RANK["REVIEW"] + 1,
                        section=section.heading_normalized,
                        section_slug=section.section_slug,
                        source_line_1based=section.source_line_1based,
                        ordinal=section.ordinal,
                        type="low_section_confidence",
                        message=(
                            f"Section confidence {section.confidence:.3f} is below "
                            f"threshold {cfg.section_confidence_review:.2f}."
                        ),
                        evidence={
                            "section_slug": section.section_slug,
                            "heading_normalized": section.heading_normalized,
                            "ordinal": section.ordinal,
                            "extractor_id": section.extractor_id,
                            "confidence": float(section.confidence),
                            "threshold": cfg.section_confidence_review,
                        },
                    )
                )

    findings.sort(key=lambda f: (f.priority_rank, f.ordinal, f.section_slug, f.type))

    overall = _overall_from_section_statuses(section_statuses)

    recommendations = _build_review_recommendations(
        summary=summary,
        overall_status=overall,
        findings_count=len(findings),
    )

    return AuditSynthesisResult(
        overall_status=overall,  # type: ignore[arg-type]
        summary=summary,
        section_summaries=summaries,
        findings=findings,
        confidence=AuditConfidenceSummary(
            document_confidence=round(doc_conf, 4),
            low_confidence_sections=low_conf,
        ),
        review_recommendations=recommendations,
    )


def _build_review_recommendations(
    *,
    summary: AuditSummaryCounts,
    overall_status: str,
    findings_count: int,
) -> list[str]:
    """Deterministic recommendation bullets from aggregate counts."""
    out: list[str] = []
    if summary.fail_sections:
        out.append(
            f"Resolve {summary.fail_sections} section(s) with FAIL status before accepting the report; "
            "review protection engineering evidence attached to each finding."
        )
    if summary.warn_sections:
        out.append(
            f"Review {summary.warn_sections} section(s) with WARN status and confirm whether "
            "margins are acceptable for the installation."
        )
    if summary.review_sections:
        out.append(
            f"Manually verify {summary.review_sections} section(s) marked REVIEW "
            "(low extraction confidence and/or typed extractor flags)."
        )
    if overall_status == "PASS" and findings_count == 0:
        out.append("No blocking or warning findings were synthesized; spot-check critical protection settings in the source PDF.")
    return out


__all__ = [
    "AuditSynthesisSettings",
    "FINDING_SEVERITY_RANK",
    "register_severity",
    "reset_severity_registry",
    "severity_priority",
    "synthesize_report_audit",
]
