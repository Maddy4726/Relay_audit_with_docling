"""Tests for full-report section processing (motor feeder style)."""

from __future__ import annotations

import logging
import unittest
from pathlib import Path

from relay_report_audit.sections.motor_feeder_report import process_motor_feeder_markdown


class TestMotorFeederReport(unittest.TestCase):
    def setUp(self) -> None:
        logging.basicConfig(level=logging.INFO)

    def test_ss31_pdf_markdown_section_count(self) -> None:
        path = Path("extracted/markdown/SS31_CUB_NO._59_DESCALING_PUMP_MOTOR-1702.md")
        if not path.exists():
            self.skipTest("SS31 fixture markdown not present")
        md = path.read_text(encoding="utf-8")
        bundle = process_motor_feeder_markdown(md)
        kinds = {s.extractor_id for s in bundle.sections}
        self.assertIn("contact_resistance", kinds)
        self.assertIn("ct_ratio", kinds)
        self.assertIn("generic_tables", kinds)
        self.assertGreaterEqual(len(bundle.sections), 18)

    def test_mini_report_routing(self) -> None:
        md = """
## CIRCUIT BREAKER

- 2.4 CONTACT RESISTANCE TEST:

| Phase | Value (mΩ) |
| ----- | ---------- |
| R | 1 |

3. RATIO TEST: (BY PRIMARY INJECTION)

2. 3.1 CT (CTR: 10/5 A)

| Phase Ref. | Injected current in Primary (A) | RELAY |
| ---------- | -------------------------------- | ----- |
| R | 10 | 10 |

GENERIC FOOTER SECTION

| A | B |
| - | - |
| 1 | 2 |
"""
        b = process_motor_feeder_markdown(md)
        by_slug = {s.section_slug: s for s in b.sections}
        self.assertIn("contact-resistance-test", by_slug)
        self.assertEqual(by_slug["contact-resistance-test"].extractor_id, "contact_resistance")
        self.assertIn("ratio-test-by-primary-injection", by_slug)
        self.assertEqual(by_slug["ratio-test-by-primary-injection"].extractor_id, "ct_ratio")


if __name__ == "__main__":
    unittest.main()
