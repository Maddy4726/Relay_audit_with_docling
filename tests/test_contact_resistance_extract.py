"""Tests for CONTACT RESISTANCE deterministic typed extraction."""

from __future__ import annotations

import logging
import unittest

from relay_report_audit.sections.contact_resistance_extract import (
    extract_contact_resistance_from_markdown,
    extract_contact_resistance_section_dict,
)


class TestContactResistanceExtract(unittest.TestCase):
    def setUp(self) -> None:
        logging.basicConfig(level=logging.DEBUG)

    def test_milliohm_header_normalizes_to_microohm(self) -> None:
        md = """
## CONTACT RESISTANCE TEST

| Phase | Value (mΩ) | Limit |
| ----- | ---------- | ----- |
| R | 42.8 | 5 |
| Y | 0.05 | 5 |
"""
        result = extract_contact_resistance_from_markdown(md)
        self.assertEqual(result.section, "CONTACT RESISTANCE TEST")
        self.assertEqual(len(result.measurements), 2)
        by_phase = {m.phase: m.resistance_micro_ohm for m in result.measurements}
        self.assertAlmostEqual(by_phase["R"], 42_800.0, places=3)
        self.assertAlmostEqual(by_phase["Y"], 50.0, places=3)
        self.assertGreater(result.confidence, 0.5)

    def test_embedded_unit_in_cell(self) -> None:
        md = """
## CONTACT RESISTANCE TEST

| Pole | Reading |
| ---- | ------- |
| B | 120 µΩ |
"""
        result = extract_contact_resistance_from_markdown(md)
        self.assertEqual(len(result.measurements), 1)
        self.assertAlmostEqual(result.measurements[0].resistance_micro_ohm, 120.0, places=3)

    def test_dict_output_matches_schema(self) -> None:
        md = """
## CONTACT RESISTANCE TEST

| Phase | Resistance |
| ----- | ---------- |
| A-B | 1.2 mΩ |
"""
        d = extract_contact_resistance_section_dict(md)
        self.assertEqual(d["section"], "CONTACT RESISTANCE TEST")
        self.assertIn("confidence", d)
        self.assertEqual(len(d["measurements"]), 1)
        self.assertEqual(d["measurements"][0]["phase"], "A-B")
        self.assertAlmostEqual(d["measurements"][0]["resistance_micro_ohm"], 1200.0, places=3)
        self.assertGreaterEqual(d["confidence"], 0.99)

    def test_invalid_rows_skipped(self) -> None:
        md = """
## CONTACT RESISTANCE TEST

| Phase | Value (mΩ) |
| ----- | ---------- |
| R | 10 |
|  | 5 |
| Z | not_a_number |
"""
        result = extract_contact_resistance_from_markdown(md)
        self.assertEqual(len(result.measurements), 1)
        self.assertEqual(result.measurements[0].phase, "R")


if __name__ == "__main__":
    unittest.main()
