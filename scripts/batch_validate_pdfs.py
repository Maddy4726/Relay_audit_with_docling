#!/usr/bin/env python3
"""
CLI: run deterministic batch validation over a folder of relay report PDFs.

Example:
  python3 scripts/batch_validate_pdfs.py --input-dir ./pdfs --output-dir ./batch_out
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from relay_report_audit.harness.batch_validation import BatchHarnessConfig, run_batch_pdf_validation


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Batch validate relay report PDFs (Docling + report JSON + audit).")
    p.add_argument("--input-dir", type=Path, required=True, help="Directory containing *.pdf files.")
    p.add_argument("--output-dir", type=Path, required=True, help="Directory for markdown, json, logs, summary.")
    p.add_argument(
        "--low-confidence-threshold",
        type=float,
        default=0.72,
        help="Sections below this extraction confidence emit diagnostics (default 0.72).",
    )
    p.add_argument(
        "--document-confidence-warn",
        type=float,
        default=0.75,
        help="Document mean confidence advisory threshold for warnings (default 0.75).",
    )
    p.add_argument(
        "--no-debug-artifacts",
        action="store_true",
        help="Do not copy markdown/JSON into debug/ for failed or partial runs.",
    )
    args = p.parse_args(argv)

    cfg = BatchHarnessConfig(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        low_confidence_threshold=args.low_confidence_threshold,
        document_low_confidence_warn=args.document_confidence_warn,
        save_debug_artifacts=not args.no_debug_artifacts,
    )
    summary = run_batch_pdf_validation(cfg)
    print(summary.model_dump_json(indent=2))
    return 0 if summary.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
