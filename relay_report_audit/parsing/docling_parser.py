"""
Convert relay test report PDFs to Markdown using Docling.

Runs the standard PDF pipeline, serializes the ``DoclingDocument`` to Markdown
with GitHub-flavored tables and heading-based section structure, persists the
result under ``extracted/markdown/``, and returns the Markdown string.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Final

from docling.datamodel.base_models import ConversionStatus
from docling.document_converter import DocumentConverter
from docling.exceptions import ConversionError

if TYPE_CHECKING:
    from docling.datamodel.document import ConversionResult

logger = logging.getLogger(__name__)

_DEFAULT_MARKDOWN_SUBDIR: Final[str] = "extracted/markdown"
_FORBIDDEN_FILENAME_CHARS: Final[frozenset[str]] = frozenset('<>:"/\\|?*\n\r\t')


class DoclingPdfParseError(RuntimeError):
    """Raised when a PDF cannot be converted to Markdown by Docling."""


def _sanitize_filename_stem(stem: str) -> str:
    """Produce a safe single-segment filename stem for cross-platform writes."""
    cleaned = "".join("_" if ch in _FORBIDDEN_FILENAME_CHARS else ch for ch in stem)
    cleaned = cleaned.strip().rstrip(".")
    if not cleaned:
        cleaned = "document"
    return cleaned[:200]


def _default_markdown_dir() -> Path:
    """Directory where extracted Markdown files are stored (relative to CWD unless overridden)."""
    return Path(_DEFAULT_MARKDOWN_SUBDIR).resolve()


def _write_markdown_file(markdown: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(markdown, encoding="utf-8", newline="\n")
    logger.info("Wrote Markdown (%d chars) to %s", len(markdown), destination)


def _export_markdown(conv_result: ConversionResult) -> str:
    """
    Serialize Docling's document to Markdown.

    ``compact_tables=False`` keeps column padding for readable pipe tables;
    headings and nested groups follow Docling's structure in the output.
    """
    return conv_result.document.export_to_markdown(
        compact_tables=False,
        enable_chart_tables=True,
        escape_html=True,
        escape_underscores=True,
    )


def _log_conversion_outcome(conv_result: ConversionResult, pdf_path: Path) -> None:
    if conv_result.status == ConversionStatus.PARTIAL_SUCCESS:
        logger.warning(
            "Docling conversion completed with PARTIAL_SUCCESS for %s (%d error item(s))",
            pdf_path,
            len(conv_result.errors),
        )
        for err in conv_result.errors:
            logger.warning(
                "Docling error component=%s message=%s",
                getattr(err, "component_type", "?"),
                getattr(err, "error_message", str(err)),
            )
    else:
        logger.info("Docling conversion status=%s for %s", conv_result.status, pdf_path)


def parse_pdf_to_markdown(
    pdf_path: str | Path,
    *,
    markdown_dir: str | Path | None = None,
    output_filename: str | Path | None = None,
    converter: DocumentConverter | None = None,
) -> str:
    """
    Parse a PDF with Docling, export to Markdown, save under ``markdown_dir``, and return the text.

    Args:
        pdf_path: Filesystem path to the input ``.pdf`` file.
        markdown_dir: Directory to write ``<stem>.md`` into. Defaults to ``extracted/markdown``
            (resolved from the current working directory).
        output_filename: Optional output file name (e.g. ``custom.md``). If relative, it is placed
            under ``markdown_dir``. If absolute, ``markdown_dir`` is ignored for the path.
        converter: Optional preconfigured ``DocumentConverter`` (useful for tests or custom pipelines).

    Returns:
        The full Markdown string extracted from the document.

    Raises:
        FileNotFoundError: If ``pdf_path`` does not exist.
        DoclingPdfParseError: If Docling reports conversion failure.
        OSError: If the Markdown file cannot be written.
    """
    pdf_path = Path(pdf_path).expanduser().resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found or not a file: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        logger.warning("Input path does not end with .pdf: %s", pdf_path)

    out_dir = Path(markdown_dir).expanduser().resolve() if markdown_dir else _default_markdown_dir()

    if output_filename is None:
        md_path = out_dir / f"{_sanitize_filename_stem(pdf_path.stem)}.md"
    else:
        out_name = Path(output_filename)
        md_path = out_name if out_name.is_absolute() else out_dir / out_name

    logger.info("Starting Docling PDF→Markdown for %s", pdf_path)
    conv = converter if converter is not None else DocumentConverter()

    try:
        conv_result = conv.convert(str(pdf_path))
    except ConversionError as exc:
        logger.error("Docling conversion failed for %s", pdf_path, exc_info=True)
        raise DoclingPdfParseError(f"Docling could not convert PDF: {pdf_path}") from exc
    except Exception as exc:  # pragma: no cover - defensive guard around third-party boundary
        logger.exception("Unexpected error during Docling conversion for %s", pdf_path)
        raise DoclingPdfParseError(f"Unexpected failure while converting PDF: {pdf_path}") from exc

    _log_conversion_outcome(conv_result, pdf_path)

    if conv_result.status not in (ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS):
        msg = f"Conversion ended with status {conv_result.status} for {pdf_path}"
        logger.error(msg)
        raise DoclingPdfParseError(msg)

    try:
        markdown = _export_markdown(conv_result)
    except Exception as exc:
        logger.exception("Failed to export Docling document to Markdown for %s", pdf_path)
        raise DoclingPdfParseError(f"Markdown export failed for PDF: {pdf_path}") from exc

    if not markdown.strip():
        logger.warning("Docling produced empty Markdown for %s", pdf_path)

    try:
        _write_markdown_file(markdown, md_path)
    except OSError as exc:
        logger.error("Could not write Markdown output to %s", md_path, exc_info=True)
        raise

    logger.info("Finished PDF→Markdown for %s", pdf_path)
    return markdown


__all__ = [
    "DoclingPdfParseError",
    "parse_pdf_to_markdown",
]
