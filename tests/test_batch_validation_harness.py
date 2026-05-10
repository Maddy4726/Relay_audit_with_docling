"""Integration-style tests for the batch PDF validation harness (mocked PDF I/O)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from relay_report_audit.harness.batch_validation import (
    BatchHarnessConfig,
    collect_relay_report_diagnostics,
    process_relay_markdown_for_batch,
    run_batch_pdf_validation,
)
from relay_report_audit.sections.report_document_extract import build_report_document


class TestBatchValidationHarness(unittest.TestCase):
    def test_collect_empty_table_diagnostic(self) -> None:
        md = "## T\n\n| a | b |\n|---|---|\n|   |   |\n"
        doc = build_report_document(md)
        diag, _ = collect_relay_report_diagnostics(
            doc,
            low_confidence_threshold=0.1,
            document_low_confidence_warn=0.1,
        )
        types = [d.type for d in diag]
        self.assertIn("empty_table", types)

    def test_process_markdown_batch_smoke(self) -> None:
        from tempfile import TemporaryDirectory

        md = "## ONE\n\n|x|y|\n|-|-|\n|1|2|\n"
        with TemporaryDirectory() as tmp:
            doc, _diag, _warns, counts = process_relay_markdown_for_batch(
                md,
                stem="smoke",
                json_dir=Path(tmp),
                low_confidence_threshold=0.72,
                document_low_confidence_warn=0.75,
            )
        self.assertGreater(len(doc.sections), 0)
        self.assertIsNotNone(doc.audit_synthesis)
        self.assertEqual(len(counts), 4)

    def test_batch_run_with_tmpdir(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            t = Path(tmp)
            inp = t / "in"
            outp = t / "out"
            inp.mkdir()
            (inp / "good.pdf").write_bytes(b"%PDF-1.1\n%\xe2\xe3\xcf\xd3\n")
            (inp / "bad.pdf").write_bytes(b"%PDF-1.1\n%\xe2\xe3\xcf\xd3\n")

            def fake_parse(pdf: Path, **kwargs: object) -> str:
                if pdf.name.startswith("bad"):
                    raise OSError("simulated failure")
                return "## OK\n\n|a|b|\n|-|-|\n|1|2|\n"

            with patch("relay_report_audit.harness.batch_validation.parse_pdf_to_markdown", side_effect=fake_parse):
                summary = run_batch_pdf_validation(
                    BatchHarnessConfig(input_dir=inp, output_dir=outp, save_debug_artifacts=True)
                )
            self.assertEqual(summary.total_reports, 2)
            self.assertEqual(summary.failed, 1)
            self.assertEqual(summary.successful, 1)
            self.assertTrue((outp / "batch_summary.json").is_file())
            self.assertTrue((outp / "batch_operator_summary.txt").is_file())
            data = json.loads((outp / "batch_summary.json").read_text(encoding="utf-8"))
            self.assertIn("common_failures", data)
            self.assertTrue(any("OSError" in cf["type"] for cf in data["common_failures"]))


if __name__ == "__main__":
    unittest.main()
