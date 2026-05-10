#!/usr/bin/env python3
"""
Demonstrate ``parse_pdf_to_markdown``: Docling PDF → Markdown with on-disk output.

Usage (from repository root)::

    python scripts/demo_docling_parser.py path/to/report.pdf
    python scripts/demo_docling_parser.py path/to/report.pdf --markdown-dir /tmp/md_out

Markdown is written next to the default layout under ``extracted/markdown/`` unless
``--markdown-dir`` is set. Logging goes to stderr at INFO level.
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
