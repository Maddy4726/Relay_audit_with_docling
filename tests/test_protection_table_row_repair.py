"""Protection trip table row repair and grouped headers (Docling-style markdown)."""

from __future__ import annotations

import unittest

from relay_report_audit.sections.markdown_table_extractor import (
    extract_pipe_tables_from_markdown_fragment,
)


def _row_dict(headers: list[str], row: list[str]) -> dict[str, str]:
    return {h.strip(): row[i].strip() for i, h in enumerate(headers)}


class TestProtectionTableRowRepair(unittest.TestCase):
    def _first_table(self, md: str) -> tuple[list[str], list[str]]:
        tables = extract_pipe_tables_from_markdown_fragment(md, section_label="PROT")
        self.assertEqual(len(tables), 1, tables)
        t = tables[0]
        return list(t["headers"]), list(t["rows"][0])

    def test_dtoc_short_circuit_shifted_row(self) -> None:
        md = """
|   Phase |   Injected Current (A) | Operated Time (Sec)   |
|---------|------------------------|-----------------------|
|    45.0 |                  0.138 | RYB                   |
"""
        headers, row = self._first_table(md)
        d = _row_dict(headers, row)
        self.assertEqual(d["Phase"], "RYB")
        self.assertEqual(d["Injected Current (A)"], "45.0")
        self.assertEqual(d["Operated Time (Sec)"], "0.138")

    def test_thermal_overload_already_correct(self) -> None:
        md = """
| Phase   |   Injected Current (A) |   Calculated Time (Sec) |   Operated Time (Sec) |
|---------|------------------------|-------------------------|-----------------------|
| RYB     |                   21.3 |                   19.94 |                19.751 |
"""
        headers, row = self._first_table(md)
        d = _row_dict(headers, row)
        self.assertEqual(d["Phase"], "RYB")
        self.assertEqual(d["Injected Current (A)"], "21.3")

    def test_negative_sequence_stage1(self) -> None:
        md = """
|   Phase |   Injected Current (A) | Operated Time (Sec)   |
|---------|------------------------|-----------------------|
|   12.35 |                  1.057 | RYB                   |
"""
        headers, row = self._first_table(md)
        d = _row_dict(headers, row)
        self.assertEqual(d["Phase"], "RYB")
        self.assertEqual(d["Injected Current (A)"], "12.35")
        self.assertEqual(d["Operated Time (Sec)"], "1.057")

    def test_startup_supervision(self) -> None:
        md = """
|   Phase |   Injected Current (A) | Operated Time (Sec)   |
|---------|------------------------|-----------------------|
|    12.5 |                 10.068 | RYB                   |
"""
        headers, row = self._first_table(md)
        d = _row_dict(headers, row)
        self.assertEqual(d["Phase"], "RYB")
        self.assertEqual(d["Injected Current (A)"], "12.5")

    def test_stall_during_running(self) -> None:
        md = """
|   Phase |   Injected Current (A) | Operated Time (Sec)   |
|---------|------------------------|-----------------------|
|    10.0 |                 10.041 | RYB                   |
"""
        headers, row = self._first_table(md)
        d = _row_dict(headers, row)
        self.assertEqual(d["Phase"], "RYB")
        self.assertEqual(d["Operated Time (Sec)"], "10.041")

    def test_negative_sequence_idmt_grouped_headers(self) -> None:
        md = """
| Phase   | Injected Current (A)   | Injected Current (A)   | Injected Current (A)   | Operated Time (Sec)   | Operated Time (Sec)   | Operated Time (Sec)   |
|---------|------------------------|------------------------|------------------------|-----------------------|-----------------------|-----------------------|
| Phase   | X2                     | X4                     | X6                     | X2                    | X4                    | X6                    |
| RYB     | 2.1                    | 4.2                    | 6.3                    | 3.491                 | 1.736                 | 1.336                 |
"""
        tables = extract_pipe_tables_from_markdown_fragment(md, section_label="NEG")
        self.assertEqual(len(tables), 1)
        t = tables[0]
        self.assertEqual(t.get("header_depth"), 2)
        gh = t.get("grouped_headers")
        self.assertIsNotNone(gh)
        self.assertEqual(len(gh), 2)
        self.assertEqual(gh[0]["group"], "Injected Current (A)")
        self.assertEqual(gh[0]["columns"], ["X2", "X4", "X6"])
        self.assertEqual(gh[1]["group"], "Operated Time (Sec)")
        self.assertEqual(t["headers"][0], "Phase")
        self.assertIn("Injected Current (A) — X2", t["headers"][1])
        row = t["rows"][0]
        self.assertEqual(row[0], "RYB")


if __name__ == "__main__":
    unittest.main()
