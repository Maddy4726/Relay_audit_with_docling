"""Tests for deterministic audit synthesis / aggregation."""

from __future__ import annotations

import unittest

from relay_report_audit.audit.aggregation import (
    AuditSynthesisSettings,
    register_severity,
    reset_severity_registry,
    severity_priority,
    synthesize_report_audit,
)
from relay_report_audit.schemas.report_document import ReportSectionJson


def _section(**kwargs: object) -> ReportSectionJson:
    base = dict(
        ordinal=0,
        source_line_1based=1,
        section_slug="s",
        heading_kind="atx",
        heading_raw="H",
        heading_normalized="H",
        outline=None,
        parent_section_slug=None,
        extractor_id="generic_tables",
        body_markdown="",
        tables=[],
        typed_payload=None,
        protection_metadata=None,
        protection_engineering_validation=None,
        confidence=0.95,
    )
    base.update(kwargs)
    return ReportSectionJson.model_validate(base)  # type: ignore[arg-type]


class TestAuditAggregation(unittest.TestCase):
    def tearDown(self) -> None:
        reset_severity_registry()

    def test_empty_sections_pass(self) -> None:
        r = synthesize_report_audit([])
        self.assertEqual(r.overall_status, "PASS")
        self.assertEqual(r.summary.pass_sections, 0)
        self.assertEqual(r.confidence.document_confidence, 0.0)

    def test_fail_dominates_warn(self) -> None:
        s1 = _section(
            ordinal=0,
            section_slug="a",
            heading_normalized="A",
            protection_engineering_validation={
                "status": "WARN",
                "checks": [{"type": "x", "status": "WARN", "message": "m", "evidence": {"k": 1}}],
            },
        )
        s2 = _section(
            ordinal=1,
            section_slug="b",
            heading_normalized="B",
            protection_engineering_validation={
                "status": "FAIL",
                "checks": [{"type": "y", "status": "FAIL", "message": "bad", "evidence": {"raw": "z"}}],
            },
        )
        r = synthesize_report_audit([s1, s2])
        self.assertEqual(r.overall_status, "FAIL")
        self.assertEqual(r.summary.fail_sections, 1)
        self.assertEqual(r.summary.warn_sections, 1)
        fail_findings = [f for f in r.findings if f.severity == "FAIL"]
        self.assertEqual(len(fail_findings), 1)
        self.assertIn("check", fail_findings[0].evidence)
        self.assertEqual(fail_findings[0].evidence["check_evidence"], {"raw": "z"})

    def test_skip_checks_do_not_fail_section(self) -> None:
        s = _section(
            ordinal=0,
            section_slug="earth",
            heading_normalized="EARTH FAULT",
            protection_engineering_validation={
                "status": "SKIP",
                "checks": [{"type": "earth_fault_timing_consistency", "status": "SKIP", "evidence": {}}],
            },
            confidence=0.95,
        )
        r = synthesize_report_audit([s])
        self.assertEqual(r.overall_status, "PASS")
        self.assertEqual(r.summary.pass_sections, 1)
        self.assertEqual(r.findings, [])

    def test_low_confidence_review(self) -> None:
        s = _section(
            ordinal=0,
            section_slug="weak",
            heading_normalized="WEAK SECTION",
            confidence=0.5,
            extractor_id="generic_tables",
        )
        r = synthesize_report_audit([s], settings=AuditSynthesisSettings(section_confidence_review=0.72))
        self.assertEqual(r.overall_status, "REVIEW")
        self.assertEqual(r.summary.review_sections, 1)
        self.assertEqual(len(r.confidence.low_confidence_sections), 1)
        self.assertEqual(r.confidence.low_confidence_sections[0].reason, "section_confidence_below_threshold")
        self.assertTrue(any(f.type == "low_section_confidence" for f in r.findings))

    def test_typed_payload_ct_empty_measurements(self) -> None:
        s = _section(
            ordinal=0,
            section_slug="ct",
            heading_normalized="CT RATIO",
            extractor_id="ct_ratio",
            typed_payload={"confidence": 0.9, "measurements": []},
            confidence=0.9,
        )
        r = synthesize_report_audit([s])
        self.assertEqual(r.overall_status, "REVIEW")
        self.assertTrue(any("ct_ratio_empty_measurements" in f.evidence.get("flags", []) for f in r.findings))

    def test_register_severity(self) -> None:
        register_severity("HOLD", 5)
        self.assertEqual(severity_priority("HOLD"), 5)
        self.assertLess(severity_priority("HOLD"), severity_priority("WARN"))

    def test_findings_sorted_by_priority(self) -> None:
        s = _section(
            ordinal=0,
            section_slug="mix",
            heading_normalized="MIX",
            protection_engineering_validation={
                "checks": [
                    {"type": "w", "status": "WARN", "evidence": {}},
                    {"type": "f", "status": "FAIL", "evidence": {}},
                ]
            },
        )
        r = synthesize_report_audit([s])
        self.assertEqual(r.findings[0].severity, "FAIL")
        self.assertEqual(r.findings[1].severity, "WARN")


if __name__ == "__main__":
    unittest.main()
