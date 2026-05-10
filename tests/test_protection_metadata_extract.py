"""Unit tests for deterministic protection free-text metadata extraction."""

from __future__ import annotations

import unittest

from relay_report_audit.sections.protection_metadata_extract import (
    extract_protection_body_prose,
    is_protection_test_section_heading,
    parse_protection_metadata_blocks,
    parse_protection_metadata_chunk,
)
from relay_report_audit.sections.report_document_extract import build_report_document


class TestProtectionMetadataExtract(unittest.TestCase):
    def test_thermal_pickup_and_time_constant(self) -> None:
        raw = "Set Current = 0.71 x In Time const.= 11.8 min"
        b = parse_protection_metadata_chunk(raw)
        self.assertEqual(b.raw_metadata_text, raw)
        self.assertAlmostEqual(b.normalized["pickup_multiple_in"], 0.71)
        self.assertAlmostEqual(b.normalized["time_constant_min"], 11.8)
        self.assertEqual(b.normalized.get("protection_scheme_hint"), "thermal_inverse_time")

    def test_idmt_curve_and_tms(self) -> None:
        raw = "CURVE: SI TMS = 0.34"
        b = parse_protection_metadata_chunk(raw)
        self.assertEqual(b.normalized["curve_type"], "SI")
        self.assertAlmostEqual(b.normalized["tms"], 0.34)
        self.assertEqual(b.normalized.get("protection_scheme_hint"), "idmt")

    def test_short_circuit_delay_msec_to_seconds(self) -> None:
        raw = "Set Current =    9.00 x In Delay =      0.08   mSec"
        b = parse_protection_metadata_chunk(raw)
        self.assertAlmostEqual(b.normalized["pickup_multiple_in"], 9.0)
        self.assertAlmostEqual(b.normalized["delay_seconds"], 0.00008)
        self.assertEqual(b.normalized.get("protection_scheme_hint"), "dtoc")

    def test_negative_sequence_stage1_dt(self) -> None:
        raw = (
            "STAGE 1: Set Current =   2.47    x In      CURVE: DT          Delay = 1.00 Sec"
        )
        b = parse_protection_metadata_chunk(raw)
        self.assertEqual(b.normalized.get("stage_label"), "STAGE 1")
        self.assertAlmostEqual(b.normalized["pickup_multiple_in"], 2.47)
        self.assertEqual(b.normalized["curve_type"], "DT")
        self.assertAlmostEqual(b.normalized["delay_seconds"], 1.0)
        self.assertEqual(b.normalized.get("protection_scheme_hint"), "dtoc_dt")

    def test_negative_sequence_idmt_stage2(self) -> None:
        raw = "IDMT STAGE 2: Set Current =    0.21    x In       CURVE:  SI         TMS =    0.34"
        b = parse_protection_metadata_chunk(raw)
        self.assertEqual(b.normalized.get("stage_label"), "IDMT STAGE 2")
        self.assertAlmostEqual(b.normalized["pickup_multiple_in"], 0.21)
        self.assertEqual(b.normalized["curve_type"], "SI")
        self.assertAlmostEqual(b.normalized["tms"], 0.34)
        self.assertEqual(b.normalized.get("protection_scheme_hint"), "idmt")

    def test_two_blocks_from_prose(self) -> None:
        prose = (
            "STAGE 1: Set Current = 2.47 x In CURVE: DT Delay = 1.00 Sec\n\n"
            "IDMT STAGE 2: Set Current = 0.21 x In CURVE: SI TMS = 0.34"
        )
        blocks = parse_protection_metadata_blocks(prose)
        self.assertEqual(len(blocks), 2)
        self.assertIn("delay_seconds", blocks[0].normalized)
        self.assertIn("tms", blocks[1].normalized)

    def test_startup_supervision(self) -> None:
        raw = (
            "Set Current =  0.71  x  In, Motor St. Current=   2.5 x In A, Time St. Up =  10 Sec"
        )
        b = parse_protection_metadata_chunk(raw)
        self.assertAlmostEqual(b.normalized["pickup_multiple_in"], 0.71)
        self.assertAlmostEqual(b.normalized["motor_stall_current_multiple_in"], 2.5)
        self.assertAlmostEqual(b.normalized["startup_time_limit_seconds"], 10.0)
        self.assertEqual(b.normalized.get("protection_scheme_hint"), "startup_supervision")

    def test_stall_logic_delay(self) -> None:
        raw = "Set Current =   1.43   x In, Logic Delay time =   12  Sec"
        b = parse_protection_metadata_chunk(raw)
        self.assertAlmostEqual(b.normalized["pickup_multiple_in"], 1.43)
        self.assertAlmostEqual(b.normalized["stall_logic_delay_seconds"], 12.0)
        self.assertEqual(b.normalized.get("protection_scheme_hint"), "stall_during_run")

    def test_earth_fault_merged_time_line(self) -> None:
        raw = "Set Current =      0.040     x In A\n\nTime =     0.50   Sec"
        b = parse_protection_metadata_chunk(raw)
        self.assertAlmostEqual(b.normalized["pickup_multiple_in"], 0.04)
        self.assertAlmostEqual(b.normalized["earth_fault_time_seconds"], 0.5)
        self.assertEqual(b.normalized.get("protection_scheme_hint"), "earth_fault")

    def test_extract_prose_before_table(self) -> None:
        body = "Set Current = 1 x In\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
        self.assertEqual(extract_protection_body_prose(body), "Set Current = 1 x In")

    def test_is_protection_heading(self) -> None:
        self.assertTrue(is_protection_test_section_heading("4.2 SHORT CIRCUIT: (DTOC)"))
        self.assertTrue(is_protection_test_section_heading("PROLONGED START/ STARTUP SUPERVISION"))
        self.assertFalse(is_protection_test_section_heading("CONTACT RESISTANCE TEST"))

    def test_build_report_document_ss31_snippet(self) -> None:
        md = """## 4.3 THERMAL O/L:

Set Current =   0.71 x In Time const.=     11.8    min

| Phase | A |
|-------|---|
| RYB   | 1 |
"""
        doc = build_report_document(md)
        sec = next(s for s in doc.sections if "THERMAL" in s.heading_normalized.upper())
        self.assertIsNotNone(sec.protection_metadata)
        assert sec.protection_metadata is not None
        self.assertEqual(len(sec.protection_metadata), 1)
        n = sec.protection_metadata[0]["normalized"]
        self.assertAlmostEqual(n["pickup_multiple_in"], 0.71)
        self.assertAlmostEqual(n["time_constant_min"], 11.8)


if __name__ == "__main__":
    unittest.main()
