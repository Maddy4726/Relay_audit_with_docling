"""Unit tests for relay_report_audit.sections.markdown_table_extractor."""

from __future__ import annotations

import logging
import unittest

from relay_report_audit.sections.markdown_table_extractor import (
    DEFAULT_TARGET_SECTIONS,
    extract_relay_section_tables,
)


class TestMarkdownTableExtractor(unittest.TestCase):
    def setUp(self) -> None:
        logging.basicConfig(level=logging.DEBUG)

    def test_basic_table_and_confidence(self) -> None:
        md = """
## CONTACT RESISTANCE TEST

| Phase | Value (mΩ) | Limit |
| ----- | ---------- | ----- |
| A | 1.2 | 5 |
| B | 1.3 | 5 |
"""
        out = extract_relay_section_tables(md)
        self.assertEqual(len(out), 1)
        t = out[0]
        self.assertEqual(t["section"], "CONTACT RESISTANCE TEST")
        self.assertEqual(t["headers"], ["Phase", "Value (mΩ)", "Limit"])
        self.assertEqual(len(t["rows"]), 2)
        self.assertEqual(t["rows"][0], ["A", "1.2", "5"])
        self.assertGreater(t["confidence"], 0.85)

    def test_repeated_header_row_skipped(self) -> None:
        md = """
## OVERLOAD PROTECTION

| Function | Setting |
| -------- | ------- |
| Function | Setting |
| Pickup | 10 A |
"""
        out = extract_relay_section_tables(md)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["rows"], [["Pickup", "10 A"]])
        self.assertLess(out[0]["confidence"], 1.0)

    def test_mid_table_repeated_header_block(self) -> None:
        md = """
## INSULATION RESISTANCE TEST

| Circuit | MΩ |
| ------- | -- |
| X | 100 |
| --- | --- |
| Circuit | MΩ |
| Y | 200 |
"""
        out = extract_relay_section_tables(md)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["rows"], [["X", "100"], ["Y", "200"]])

    def test_multiline_cell_continuation(self) -> None:
        md = """
## CONTACT RESISTANCE TEST

| Value |
| ----- |
| Line1
continuation without pipe characters
| done |
"""
        out = extract_relay_section_tables(md)
        self.assertEqual(len(out), 1)
        self.assertEqual(
            out[0]["rows"][0][0],
            "Line1\ncontinuation without pipe characters",
        )
        self.assertEqual(out[0]["rows"][1][0], "done")

    def test_stacked_tables(self) -> None:
        md = """
## OVERLOAD PROTECTION

| A | B |
| - | - |
| 1 | 2 |
| U | V |
| - | - |
| 3 | 4 |
"""
        out = extract_relay_section_tables(md)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["rows"], [["1", "2"]])
        self.assertEqual(out[1]["rows"], [["3", "4"]])

    def test_unknown_section_ignored(self) -> None:
        md = """
## OTHER SECTION

| A | B |
| - | - |
| 1 | 2 |
"""
        out = extract_relay_section_tables(md)
        self.assertEqual(out, [])

    def test_default_targets_constant(self) -> None:
        self.assertIn("CONTACT RESISTANCE TEST", DEFAULT_TARGET_SECTIONS)


if __name__ == "__main__":
    unittest.main()
