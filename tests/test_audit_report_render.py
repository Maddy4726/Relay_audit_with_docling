"""Tests for deterministic audit report Markdown / plain-text rendering."""

from __future__ import annotations

import unittest

from relay_report_audit.reporting.audit_report_render import (
    RENDERER_VERSION,
    render_audit_report_markdown,
    render_audit_report_plain_text,
)
from relay_report_audit.schemas.audit_synthesis import (
    AuditConfidenceSummary,
    AuditFindingRecord,
    AuditSummaryCounts,
    AuditSynthesisResult,
    SectionAuditSummary,
)


def _minimal_result() -> AuditSynthesisResult:
    return AuditSynthesisResult(
        overall_status="WARN",
        summary=AuditSummaryCounts(
            pass_sections=8,
            warn_sections=2,
            fail_sections=1,
            review_sections=1,
        ),
        section_summaries=[
            SectionAuditSummary(
                ordinal=0,
                section_slug="negative-sequence-dtoc",
                heading_normalized="NEGATIVE SEQUENCE:(DTOC)",
                extractor_id="generic_tables",
                status="WARN",
                confidence=0.91,
                protection_checks={"PASS": 2, "WARN": 1},
                typed_payload_flags=[],
            ),
            SectionAuditSummary(
                ordinal=1,
                section_slug="earth",
                heading_normalized="EARTH FAULT",
                extractor_id="generic_tables",
                status="REVIEW",
                confidence=0.55,
                protection_checks={"SKIP": 1},
                typed_payload_flags=[],
            ),
        ],
        findings=[
            AuditFindingRecord(
                severity="REVIEW",
                priority_rank=2,
                section="EARTH FAULT",
                section_slug="earth",
                source_line_1based=157,
                ordinal=1,
                type="earth_fault_timing_consistency",
                message="Operated time cell is non-numeric; cannot compare to setting.",
                evidence={
                    "section_slug": "earth",
                    "check_evidence": {"raw_operated_cell": "Operated"},
                },
            ),
            AuditFindingRecord(
                severity="WARN",
                priority_rank=1,
                section="NEGATIVE SEQUENCE:(DTOC)",
                section_slug="negative-sequence-dtoc",
                source_line_1based=115,
                ordinal=0,
                type="inverse_time_si_curve_shape",
                message="Scatter of t*|M^0.02-1| across points exceeds loose SI-shape band.",
                evidence={
                    "check_evidence": {
                        "points_I_A": [2.1, 4.2, 6.3],
                        "points_t_sec": [3.491, 1.736, 1.336],
                    },
                },
            ),
            AuditFindingRecord(
                severity="FAIL",
                priority_rank=0,
                section="SHORT CIRCUIT",
                section_slug="short-circuit",
                source_line_1based=99,
                ordinal=2,
                type="dtoc_delay_consistency",
                message="|measured - setting| too large.",
                evidence={
                    "check_evidence": {
                        "measured_operated_seconds": 2.0,
                        "expected_delay_seconds": 0.00008,
                    },
                },
            ),
        ],
        confidence=AuditConfidenceSummary(
            document_confidence=0.93,
            low_confidence_sections=[],
        ),
        review_recommendations=[
            "Verify negative-sequence stage timing calibration.",
            "Re-run earth-fault timing injection test.",
        ],
    )


class TestAuditReportRender(unittest.TestCase):
    def test_markdown_structure(self) -> None:
        md = render_audit_report_markdown(_minimal_result())
        self.assertIn("# Relay Audit Summary", md)
        self.assertIn("**Overall status:** WARN", md)
        self.assertIn("## Summary", md)
        self.assertIn("**PASS sections:** 8", md)
        self.assertIn("## Key findings", md)
        self.assertIn("## Review recommendations", md)
        self.assertIn("Verify negative-sequence", md)
        self.assertIn(RENDERER_VERSION, md)
        self.assertIn("## Confidence", md)
        self.assertIn("**Document confidence:** 0.930", md)

    def test_findings_fail_before_warn_in_output(self) -> None:
        md = render_audit_report_markdown(_minimal_result())
        key = md.split("## Key findings", 1)[1]
        self.assertRegex(
            key,
            r"### 1\. SHORT CIRCUIT[\s\S]*### 2\. NEGATIVE SEQUENCE:\(DTOC\)[\s\S]*### 3\. EARTH FAULT",
        )

    def test_evidence_injection_times_line(self) -> None:
        md = render_audit_report_markdown(_minimal_result())
        self.assertIn("I=2.1A t=3.491s", md)
        self.assertIn("I=6.3A t=1.336s", md)

    def test_plain_text_contains_blocks(self) -> None:
        txt = render_audit_report_plain_text(_minimal_result())
        self.assertIn("RELAY AUDIT SUMMARY", txt)
        self.assertIn("OVERALL STATUS: WARN", txt)
        self.assertIn("KEY FINDINGS", txt)
        self.assertIn("REVIEW RECOMMENDATIONS", txt)
        self.assertIn("Document confidence: 0.930", txt)
        self.assertIn("I=2.1A t=3.491s", txt)

    def test_empty_findings_markdown(self) -> None:
        r = AuditSynthesisResult(
            overall_status="PASS",
            summary=AuditSummaryCounts(pass_sections=1, warn_sections=0, fail_sections=0, review_sections=0),
            section_summaries=[
                SectionAuditSummary(
                    ordinal=0,
                    section_slug="a",
                    heading_normalized="A",
                    extractor_id="generic_tables",
                    status="PASS",
                    confidence=1.0,
                    protection_checks={},
                    typed_payload_flags=[],
                )
            ],
            findings=[],
            confidence=AuditConfidenceSummary(document_confidence=1.0, low_confidence_sections=[]),
            review_recommendations=[],
        )
        md = render_audit_report_markdown(r)
        self.assertIn("_No findings._", md)


if __name__ == "__main__":
    unittest.main()
