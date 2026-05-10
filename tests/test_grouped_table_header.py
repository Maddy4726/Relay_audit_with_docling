"""Unit tests for grouped / hierarchical pipe-table header inference."""

from __future__ import annotations

import unittest

from relay_report_audit.sections.grouped_table_header import infer_grouped_header_layout
from relay_report_audit.sections.markdown_table_extractor import (
    extract_pipe_tables_from_markdown_fragment,
)


class TestGroupedTableHeader(unittest.TestCase):
    def test_protection_style_injected_and_operated_time(self) -> None:
        top = [
            "Injected Current (A)",
            "Injected Current (A)",
            "Injected Current (A)",
            "Operated Time (Sec)",
            "Operated Time (Sec)",
            "Operated Time (Sec)",
        ]
        bot = ["X2", "X4", "X6", "X2", "X4", "X6"]
        layout = infer_grouped_header_layout(top, bot)
        self.assertIsNotNone(layout)
        assert layout is not None
        gh = layout.grouped_headers
        self.assertEqual(len(gh), 2)
        self.assertEqual(gh[0].group, "Injected Current (A)")
        self.assertEqual(gh[0].columns, ["X2", "X4", "X6"])
        self.assertEqual(gh[1].group, "Operated Time (Sec)")
        self.assertEqual(gh[1].columns, ["X2", "X4", "X6"])
        self.assertEqual(len(layout.flat_headers), 6)
        self.assertIn("X2", layout.flat_headers[0])

    def test_forward_fill_empty_top_cells(self) -> None:
        top = ["Group A", "", "", "Group B", "", ""]
        bot = ["c1", "c2", "c3", "d1", "d2", "d3"]
        layout = infer_grouped_header_layout(top, bot)
        self.assertIsNotNone(layout)
        assert layout is not None
        self.assertEqual(len(layout.grouped_headers), 2)
        self.assertEqual(layout.grouped_headers[0].columns, ["c1", "c2", "c3"])

    def test_single_group_three_subcolumns(self) -> None:
        top = ["Meas", "Meas", "Meas"]
        bot = ["X2", "X4", "X6"]
        layout = infer_grouped_header_layout(top, bot)
        self.assertIsNotNone(layout)
        assert layout is not None
        self.assertEqual(len(layout.grouped_headers), 1)
        self.assertEqual(layout.grouped_headers[0].group, "Meas")
        self.assertEqual(layout.grouped_headers[0].columns, ["X2", "X4", "X6"])

    def test_reject_row2_mostly_numeric(self) -> None:
        top = ["A", "A", "B", "B"]
        bot = ["1.0", "2.0", "3.0", "4.0"]
        self.assertIsNone(infer_grouped_header_layout(top, bot))

    def test_reject_mismatched_width(self) -> None:
        self.assertIsNone(infer_grouped_header_layout(["A", "B"], ["x"]))

    def test_markdown_extractor_emits_grouped_metadata(self) -> None:
        md = """
| Injected Current (A) | Injected Current (A) | Injected Current (A) | Operated Time (Sec) | Operated Time (Sec) | Operated Time (Sec) |
| X2 | X4 | X6 | X2 | X4 | X6 |
| --- | --- | --- | --- | --- | --- |
| 10 | 20 | 30 | 0.1 | 0.2 | 0.3 |
"""
        out = extract_pipe_tables_from_markdown_fragment(md, section_label="PROTECTION")
        self.assertEqual(len(out), 1)
        t = out[0]
        self.assertEqual(t["header_depth"], 2)
        self.assertIsNotNone(t.get("grouped_headers"))
        self.assertEqual(len(t["grouped_headers"]), 2)
        self.assertEqual(len(t["headers"]), 6)
        self.assertEqual(len(t["rows"]), 1)
        self.assertEqual(t["rows"][0][0], "10")


if __name__ == "__main__":
    unittest.main()
