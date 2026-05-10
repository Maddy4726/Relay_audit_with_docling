"""Unit tests for protection operation engineering validation."""

from __future__ import annotations

import unittest

from relay_report_audit.schemas.protection_operation_validation import (
    ProtectionOperationValidationResult,
)
from relay_report_audit.sections.protection_metadata_extract import (
    extract_all_protection_metadata_blocks_from_body,
)
from relay_report_audit.validation.protection_operation_validate import (
    validate_protection_operation_measurements,
)


class TestProtectionOperationValidate(unittest.TestCase):
    def test_dtoc_delay_pass(self) -> None:
        meta = [
            {
                "raw_metadata_text": "Set Current = 2 x In Delay = 1.00 Sec",
                "normalized": {"delay_seconds": 1.0, "pickup_multiple_in": 2.0},
            }
        ]
        tables = [
            {
                "headers": ["Phase", "Injected Current (A)", "Operated Time (Sec)"],
                "rows": [["RYB", "10", "1.02"]],
                "confidence": 1.0,
                "header_depth": 1,
                "grouped_headers": None,
            }
        ]
        r = validate_protection_operation_measurements(
            heading_normalized="SHORT CIRCUIT (DTOC)",
            metadata_blocks=meta,
            tables=tables,
        )
        self.assertIn(r.status, ("PASS", "WARN"))
        types = [c.type for c in r.checks]
        self.assertIn("dtoc_delay_consistency", types)
        self.assertTrue(any(c.status == "PASS" for c in r.checks if c.type == "dtoc_delay_consistency"))

    def test_dtoc_micro_delay_sanity(self) -> None:
        meta = [
            {
                "raw_metadata_text": "Delay = 0.08 mSec",
                "normalized": {"delay_seconds": 8e-5, "pickup_multiple_in": 9.0},
            }
        ]
        tables = [
            {
                "headers": ["Phase", "Injected Current (A)", "Operated Time (Sec)"],
                "rows": [["RYB", "45", "0.138"]],
                "confidence": 1.0,
                "header_depth": 1,
                "grouped_headers": None,
            }
        ]
        r = validate_protection_operation_measurements(
            heading_normalized="4.2 SHORT CIRCUIT (DTOC)",
            metadata_blocks=meta,
            tables=tables,
        )
        chk = next(c for c in r.checks if c.type == "dtoc_delay_consistency")
        self.assertEqual(chk.status, "PASS")
        self.assertEqual(chk.evidence.get("comparison_mode"), "micro_delay_sanity")

    def test_inverse_time_monotonicity_pass(self) -> None:
        meta = [
            {
                "raw_metadata_text": "STAGE 1: CURVE: DT Delay = 1.00 Sec",
                "normalized": {"curve_type": "DT", "delay_seconds": 1.0, "stage_label": "STAGE 1"},
            },
            {
                "raw_metadata_text": "IDMT STAGE 2: CURVE: SI TMS = 0.34",
                "normalized": {"curve_type": "SI", "tms": 0.34, "pickup_multiple_in": 0.21},
            },
        ]
        tab0 = {
            "headers": ["Phase", "Injected Current (A)", "Operated Time (Sec)"],
            "rows": [["RYB", "12.35", "1.057"]],
            "confidence": 1.0,
            "header_depth": 1,
            "grouped_headers": None,
        }
        tab1 = {
            "headers": [
                "Phase",
                "Injected Current (A) — X2",
                "Injected Current (A) — X4",
                "Injected Current (A) — X6",
                "Operated Time (Sec) — X2",
                "Operated Time (Sec) — X4",
                "Operated Time (Sec) — X6",
            ],
            "rows": [["RYB", "2.1", "4.2", "6.3", "3.491", "1.736", "1.336"]],
            "confidence": 1.0,
            "header_depth": 2,
            "grouped_headers": [
                {"group": "Injected Current (A)", "columns": ["X2", "X4", "X6"]},
                {"group": "Operated Time (Sec)", "columns": ["X2", "X4", "X6"]},
            ],
        }
        r = validate_protection_operation_measurements(
            heading_normalized="4.4 NEGATIVE SEQUENCE",
            metadata_blocks=meta,
            tables=[tab0, tab1],
        )
        mono = next(c for c in r.checks if c.type == "inverse_time_monotonicity")
        self.assertEqual(mono.status, "PASS")
        self.assertEqual(mono.evidence.get("points_t_sec"), [3.491, 1.736, 1.336])

    def test_inverse_time_monotonicity_fail(self) -> None:
        meta = [
            {
                "raw_metadata_text": "STAGE 1",
                "normalized": {"curve_type": "DT", "delay_seconds": 1.0},
            },
            {
                "raw_metadata_text": "IDMT",
                "normalized": {"curve_type": "SI", "tms": 0.5},
            },
        ]
        tab0 = {
            "headers": ["Phase", "Injected Current (A)", "Operated Time (Sec)"],
            "rows": [["RYB", "1", "1.0"]],
            "confidence": 1.0,
            "header_depth": 1,
            "grouped_headers": None,
        }
        tab = {
            "headers": [
                "Phase",
                "Injected Current (A) — X2",
                "Injected Current (A) — X4",
                "Injected Current (A) — X6",
                "Operated Time (Sec) — X2",
                "Operated Time (Sec) — X4",
                "Operated Time (Sec) — X6",
            ],
            "rows": [["RYB", "1", "2", "3", "1.0", "2.0", "3.0"]],
            "confidence": 1.0,
            "header_depth": 2,
            "grouped_headers": [
                {"group": "Injected Current (A)", "columns": ["X2", "X4", "X6"]},
                {"group": "Operated Time (Sec)", "columns": ["X2", "X4", "X6"]},
            ],
        }
        r = validate_protection_operation_measurements(
            heading_normalized="NEGATIVE SEQUENCE",
            metadata_blocks=meta,
            tables=[tab0, tab],
        )
        mono = next(c for c in r.checks if c.type == "inverse_time_monotonicity")
        self.assertEqual(mono.status, "FAIL")

    def test_thermal_operated_vs_calculated(self) -> None:
        meta = [
            {
                "raw_metadata_text": "Set Current = 0.71 x In Time const.= 11.8 min",
                "normalized": {"pickup_multiple_in": 0.71, "time_constant_min": 11.8},
            }
        ]
        tables = [
            {
                "headers": ["Phase", "Injected Current (A)", "Calculated Time (Sec)", "Operated Time (Sec)"],
                "rows": [["RYB", "21.3", "19.94", "19.751"]],
                "confidence": 1.0,
                "header_depth": 1,
                "grouped_headers": None,
            }
        ]
        r = validate_protection_operation_measurements(
            heading_normalized="4.3 THERMAL O/L",
            metadata_blocks=meta,
            tables=tables,
        )
        chk = r.checks[0]
        self.assertEqual(chk.type, "thermal_overload_timing_consistency")
        self.assertEqual(chk.status, "PASS")

    def test_startup_within_limit(self) -> None:
        meta = [
            {
                "raw_metadata_text": "Time St. Up = 10 Sec",
                "normalized": {"startup_time_limit_seconds": 10.0},
            }
        ]
        tables = [
            {
                "headers": ["Phase", "Injected Current (A)", "Operated Time (Sec)"],
                "rows": [["RYB", "12.5", "10.068"]],
                "confidence": 1.0,
                "header_depth": 1,
                "grouped_headers": None,
            }
        ]
        r = validate_protection_operation_measurements(
            heading_normalized="PROLONGED START/ STARTUP SUPERVISION",
            metadata_blocks=meta,
            tables=tables,
        )
        self.assertEqual(r.checks[0].type, "startup_supervision_timing_consistency")
        self.assertEqual(r.checks[0].status, "PASS")

    def test_stall_upper_bound(self) -> None:
        meta = [
            {
                "raw_metadata_text": "Logic Delay time = 12 Sec",
                "normalized": {"stall_logic_delay_seconds": 12.0},
            }
        ]
        tables = [
            {
                "headers": ["Phase", "Injected Current (A)", "Operated Time (Sec)"],
                "rows": [["RYB", "10", "10.041"]],
                "confidence": 1.0,
                "header_depth": 1,
                "grouped_headers": None,
            }
        ]
        r = validate_protection_operation_measurements(
            heading_normalized="STALL DURING RUNNING (DTOC)",
            metadata_blocks=meta,
            tables=tables,
        )
        self.assertEqual(r.checks[0].status, "PASS")

    def test_earth_fault_non_numeric_skip(self) -> None:
        meta = [
            {
                "raw_metadata_text": "Time = 0.5 Sec",
                "normalized": {"earth_fault_time_seconds": 0.5, "pickup_multiple_in": 0.04},
            }
        ]
        tables = [
            {
                "headers": ["Phase", "Injected Current (A)", "Operated Time (Sec)"],
                "rows": [["Io", "1.9", "Operated"]],
                "confidence": 1.0,
                "header_depth": 1,
                "grouped_headers": None,
            }
        ]
        r = validate_protection_operation_measurements(
            heading_normalized="4.7 EARTH FAULT PROTECTION (E/F)",
            metadata_blocks=meta,
            tables=tables,
        )
        chk = r.checks[0]
        self.assertEqual(chk.type, "earth_fault_timing_consistency")
        self.assertEqual(chk.status, "SKIP")
        self.assertEqual(chk.evidence.get("raw_operated_cell"), "Operated")

    def test_pydantic_round_trip(self) -> None:
        r = ProtectionOperationValidationResult(status="PASS", checks=[])
        d = r.model_dump()
        r2 = ProtectionOperationValidationResult.model_validate(d)
        self.assertEqual(r2.status, "PASS")

    def test_extract_all_metadata_two_tables(self) -> None:
        body = """STAGE 1: Set Current = 2.47 x In CURVE: DT Delay = 1.00 Sec

| Phase | Injected Current (A) | Operated Time (Sec) |
|-------|----------------------|---------------------|
| RYB   | 12                   | 1.0                 |

IDMT STAGE 2: Set Current = 0.21 x In CURVE: SI TMS = 0.34

| Phase | I |
|-------|---|
| RYB   | 1 |
"""
        blocks = extract_all_protection_metadata_blocks_from_body(body)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[1].normalized.get("tms"), 0.34)


if __name__ == "__main__":
    unittest.main()
