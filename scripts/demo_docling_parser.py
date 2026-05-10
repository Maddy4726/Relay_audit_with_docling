#!/usr/bin/env python3
"""
Demonstrate ``parse_pdf_to_markdown``: Docling PDF → Markdown with on-disk output.

Usage (from repository root)::

    python scripts/demo_docling_parser.py path/to/report.pdf
    python scripts/demo_docling_parser.py path/to/report.pdf --markdown-dir /tmp/md_out

Markdown is written next to the default layout under ``extracted/markdown/`` unless
``--markdown-dir`` is set. A per-heading report JSON file is written under
``extracted/report_json/`` unless ``--no-report-json`` is set. Logging goes to stderr at
INFO level.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="Path to the input PDF file")
    parser.add_argument(
        "--markdown-dir",
        type=Path,
        default=None,
        help="Override output directory (default: extracted/markdown under cwd)",
    )
    parser.add_argument(
        "-o",
        "--output-name",
        type=str,
        default=None,
        help="Optional output .md filename (placed under markdown-dir if relative)",
    )
    parser.add_argument(
        "--no-report-json",
        action="store_true",
        help="Skip writing per-heading report JSON (default: write under --json-dir)",
    )
    parser.add_argument(
        "--json-dir",
        type=Path,
        default=None,
        help="Directory for report JSON (default: extracted/report_json under cwd)",
    )
    parser.add_argument(
        "--json-stem",
        type=str,
        default=None,
        help="Filename stem for report JSON (default: PDF basename without extension)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable DEBUG logging")
    args = parser.parse_args(argv)

    _configure_logging(args.verbose)

    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from relay_report_audit.parsing.docling_parser import (  # noqa: E402
        DoclingPdfParseError,
        parse_pdf_to_markdown,
    )
    from relay_report_audit.sections.report_document_extract import (  # noqa: E402
        build_report_document_to_json_file,
        default_report_json_dir,
    )

    try:
        text = parse_pdf_to_markdown(
            args.pdf,
            markdown_dir=args.markdown_dir,
            output_filename=args.output_name,
        )
    except FileNotFoundError as exc:
        logging.getLogger(__name__).error("%s", exc)
        return 2
    except DoclingPdfParseError as exc:
        logging.getLogger(__name__).error("%s", exc)
        return 3
    except OSError as exc:
        logging.getLogger(__name__).error("I/O error: %s", exc)
        return 4

    preview = text[:500] + ("…" if len(text) > 500 else "")
    logging.getLogger(__name__).info("Extracted %d characters. Preview:\n%s", len(text), preview)

    if not args.no_report_json:
        stem = args.json_stem or args.pdf.stem
        json_base = args.json_dir if args.json_dir is not None else default_report_json_dir()
        _doc, json_path = build_report_document_to_json_file(
            text,
            json_dir=json_base,
            json_stem=stem,
        )
        logging.getLogger(__name__).info("Report JSON written to %s", json_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
