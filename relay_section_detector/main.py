"""End-to-end PDF → sections pipeline for relay test reports."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from config import Settings, load_config
from llm.section_detector import OpenAICompatibleSectionDetector, SectionPrediction
from postprocessing.merge_sections import export_sections_json, merge_section_predictions
from preprocessing.chunker import chunk_numbered_document
from preprocessing.line_numbering import number_markdown_lines

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )


def convert_pdf_to_markdown(pdf_path: Path, markdown_path: Path) -> str:
    """
    Convert ``pdf_path`` to markdown using Docling and persist to ``markdown_path``.

    Returns the markdown string for downstream stages.
    """
    from docling.document_converter import DocumentConverter

    if not pdf_path.is_file():
        msg = f"PDF not found: {pdf_path}"
        raise FileNotFoundError(msg)

    logger.info("Converting PDF to markdown via Docling: %s", pdf_path)
    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    markdown = result.document.export_to_markdown()
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(markdown, encoding="utf-8")
    logger.info("Wrote raw markdown (%s chars) to %s", len(markdown), markdown_path)
    return markdown


def run_pipeline(settings: Settings) -> Path:
    """
    Execute all stages and write ``output/sections.json``.

    Returns the path to the final JSON file.
    """
    output_dir = settings.output_dir.resolve()
    raw_md_path = output_dir / "raw_markdown.md"
    sections_path = output_dir / "sections.json"

    markdown = convert_pdf_to_markdown(settings.pdf_path, raw_md_path)

    numbered = number_markdown_lines(
        markdown,
        padding_width=settings.line_number_padding,
    )
    chunks = chunk_numbered_document(
        numbered,
        chunk_lines=settings.chunk_lines,
        overlap_lines=settings.chunk_overlap_lines,
    )

    detector = OpenAICompatibleSectionDetector(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )

    all_predictions: list[SectionPrediction] = []
    for chunk in chunks:
        logger.info(
            "Processing chunk %s (lines %s–%s)",
            chunk.chunk_id,
            chunk.start_line,
            chunk.end_line,
        )
        preds = detector.complete_sections(chunk.text)
        all_predictions.extend(preds)

    merged = merge_section_predictions(all_predictions)
    export_sections_json(merged, sections_path)
    return sections_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Semantic section segmentation for industrial relay testing reports "
            "(PDF → Docling markdown → LLM → sections.json)."
        ),
    )
    parser.add_argument(
        "pdf",
        nargs="?",
        default=None,
        help="Optional PDF path (overrides RELAY_PDF_PATH / default samples/report.pdf).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    args = parse_args(argv)
    try:
        settings = load_config()
    except Exception as exc:  # pragma: no cover - CLI surface
        logger.exception("Failed to load configuration: %s", exc)
        return 1

    if args.pdf:
        settings = settings.model_copy(update={"pdf_path": Path(args.pdf)})

    try:
        out_path = run_pipeline(settings)
    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
        return 1

    logger.info("Pipeline complete: %s", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
