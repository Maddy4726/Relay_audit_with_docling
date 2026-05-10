"""Unit tests for CT ratio markdown extraction."""

from __future__ import annotations

import logging
import unittest

from relay_report_audit.sections.ct_ratio_extract import (
    extract_ct_ratio_test_dict,
    extract_ct_ratio_test_from_markdown,
)


class TestCTRatioExtract(unittest.TestCase):
    def setUp(self) -> None:
        logging.basicConfig(level=logging.INFO)

    def test_double_header_bhilai_style(self) -> None:
        md = """
3. RATIO TEST: (BY PRIMARY INJECTION)

2. 3.1 CT (CTR: 150 / 5 A)

|            |                                 | Measured current in Secondary ( A )   | Measured current in Secondary ( A )   | Measured current in Secondary ( A )   | Measured current in Secondary ( A )   |
| Phase Ref. | Injected current in Primary (A) | RELAY                                 | ENERGY METER                          | ICT                                   | AMMETER                               |
|------------|---------------------------------|---------------------------------------|---------------------------------------|---------------------------------------|---------------------------------------|
| R          | 150                             | 150                                   | -                                     | -                                     | 150                                   |
| Y          | 150                             | 150                                   | -                                     | -                                     | 150                                   |
"""
        r = extract_ct_ratio_test_from_markdown(md)
        self.assertEqual(r.ct_ratio, "150/5")
        self.assertEqual(len(r.measurements), 2)
        self.assertEqual(r.measurements[0].phase, "R")
        self.assertEqual(r.measurements[0].primary_current, 150.0)
        self.assertEqual(r.measurements[0].relay_secondary_current, 150.0)
        self.assertEqual(r.measurements[0].ammeter_secondary_current, 150.0)
        self.assertIsNone(r.measurements[0].energy_meter_secondary_current)
        self.assertGreater(r.confidence, 0.4)

    def test_user_example_shape(self) -> None:
        md = """
## CT RATIO TEST

CTR: 100/5 A

| Phase | Primary (A) | Relay (A) | Ammeter (A) |
| ----- | ------------- | --------- | ------------ |
| R | 100 | 5 | 100 |
"""
        d = extract_ct_ratio_test_dict(md)
        self.assertEqual(d["ct_ratio"], "100/5")
        self.assertEqual(len(d["measurements"]), 1)
        m = d["measurements"][0]
        self.assertEqual(m["phase"], "R")
        self.assertEqual(m["primary_current"], 100.0)
        self.assertEqual(m["relay_secondary_current"], 5.0)
        self.assertEqual(m["ammeter_secondary_current"], 100.0)
        self.assertNotIn("energy_meter_secondary_current", m)

    def test_milliamps_normalization(self) -> None:
        md = """
- 3.1 CT (CTR: 50/1 A)

| Phase Ref. | Injected current in Primary (A) | RELAY | AMMETER |
| ---------- | -------------------------------- | ----- | ------- |
| R | 10 | 200 mA | 212 mA |
"""
        r = extract_ct_ratio_test_from_markdown(md)
        self.assertEqual(r.ct_ratio, "50/1")
        self.assertAlmostEqual(r.measurements[0].relay_secondary_current or 0, 0.2, places=5)

    def test_list_marker_section(self) -> None:
        md = """
- 3.1 CT RATIO (CTR 80/5)

| Phase | Injected current in Primary (A) | RELAY |
| ----- | -------------------------------- | ----- |
| B | 80 | 80 |
"""
        r = extract_ct_ratio_test_from_markdown(md)
        self.assertEqual(r.ct_ratio, "80/5")
        self.assertEqual(r.measurements[0].phase, "B")

    def test_no_section_returns_empty(self) -> None:
        md = "# OTHER\\n\\n| a | b |\\n| - | - |\\n| 1 | 2 |\\n"
        r = extract_ct_ratio_test_from_markdown(md)
        self.assertEqual(r.measurements, [])
        self.assertEqual(r.ct_ratio, "")


    def test_docling_split_header_banner_then_sep_then_labels(self) -> None:
        """Banner row, separator, then real headers (Docling quirk on some PDFs)."""
        md = """
3. RATIO TEST: (BY PRIMARY INJECTION)

2. 3.1 CT (CTR: 200/5 A)

| Banner | Banner | Banner |
| --- | --- | --- |
| Phase Ref. | Injected current in Primary (A) | RELAY |
| R | 200 | 200 |
"""
        r = extract_ct_ratio_test_from_markdown(md)
        self.assertEqual(r.ct_ratio, "200/5")
        self.assertEqual(len(r.measurements), 1)
        self.assertEqual(r.measurements[0].primary_current, 200.0)


if __name__ == "__main__":
    unittest.main()
