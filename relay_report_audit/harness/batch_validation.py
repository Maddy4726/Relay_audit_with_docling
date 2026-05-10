"""
End-to-end batch validation harness: folder of PDFs → markdown → report JSON + audit.

Deterministic diagnostics, structured per-report logs, batch summary JSON, and
operator-facing text. Parser/build failures are captured per file without
aborting the batch.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from relay_report_audit.parsing.docling_parser import DoclingPdfParseError, parse_pdf_to_markdown
from relay_report_audit.reporting.audit_report_render import render_audit_report_plain_text
from relay_report_audit.schemas.batch_validation import (
    BatchValidationSummary,
    CommonFailureAggregate,
    DiagnosticRecord,
    SingleReportBatchResult,
)
from relay_report_audit.schemas.report_document import ReportDocumentJson
from relay_report_audit.sections.protection_metadata_extract import is_protection_test_section_heading
from relay_report_audit.sections.report_document_extract import build_report_document

logger = logging.getLogger(__name__)

_BLOCKING_DIAGNOSTIC_TYPES: Final[frozenset[str]] = frozenset(
    {
        "missing_protection_metadata",
        "missing_grouped_headers",
        "malformed_section_tables_not_extracted",
        "empty_table",
    }
)


@dataclass
class BatchHarnessConfig:
    """Tunable paths and thresholds for a batch run."""

    input_dir: Path
    output_dir: Path
    low_confidence_threshold: float = 0.72
    document_low_confidence_warn: float = 0.75
    save_debug_artifacts: bool = True
    markdown_subdir: str = "markdown"
    json_subdir: str = "json"
    logs_subdir: str = "logs"
    debug_subdir: str = "debug"


def _empty_table_rows(rows: list[list[str]]) -> bool:
    if not rows:
        return True

    def row_blank(r: list[str]) -> bool:
        return not any((c or "").strip() for c in r)

    return all(row_blank(r) for r in rows)


def _body_has_pipe_table_markers(body: str) -> bool:
    b = body or ""
    return "\n|" in b or b.strip().startswith("|")


def collect_relay_report_diagnostics(
    doc: ReportDocumentJson,
    *,
    low_confidence_threshold: float,
    document_low_confidence_warn: float,
) -> tuple[list[DiagnosticRecord], list[str]]:
    """Return (diagnostics, human-readable warnings) for one parsed document."""
    diagnostics: list[DiagnosticRecord] = []
    warnings: list[str] = []

    for sec in doc.sections:
        slug = sec.section_slug
        hn = sec.heading_normalized
        body = sec.body_markdown or ""

        if sec.heading_kind != "preamble":
            for ti, table in enumerate(sec.tables):
                rows = table.rows or []
                if _empty_table_rows(rows):
                    diagnostics.append(
                        DiagnosticRecord(
                            type="empty_table",
                            section_slug=slug,
                            heading_normalized=hn,
                            evidence={
                                "table_index": ti,
                                "header_depth": table.header_depth,
                                "headers": list(table.headers),
                            },
                        )
                    )

        if sec.heading_kind != "preamble" and _body_has_pipe_table_markers(body) and not sec.tables:
            diagnostics.append(
                DiagnosticRecord(
                    type="malformed_section_tables_not_extracted",
                    section_slug=slug,
                    heading_normalized=hn,
                    evidence={"body_preview": body[:500]},
                )
            )

        if is_protection_test_section_heading(hn):
            meta = sec.protection_metadata or []
            if not meta:
                diagnostics.append(
                    DiagnosticRecord(
                        type="missing_protection_metadata",
                        section_slug=slug,
                        heading_normalized=hn,
                        evidence={"extractor_id": sec.extractor_id},
                    )
                )

        if "NEGATIVE SEQUENCE" in hn.upper() and len(sec.tables) >= 2:
            t1 = sec.tables[1]
            if t1.grouped_headers is None:
                diagnostics.append(
                    DiagnosticRecord(
                        type="missing_grouped_headers",
                        section_slug=slug,
                        heading_normalized=hn,
                        evidence={
                            "table_count": len(sec.tables),
                            "second_table_headers": list(t1.headers),
                            "header_depth": t1.header_depth,
                        },
                    )
                )

        if float(sec.confidence) < low_confidence_threshold and sec.heading_kind != "preamble":
            diagnostics.append(
                DiagnosticRecord(
                    type="low_section_confidence",
                    section_slug=slug,
                    heading_normalized=hn,
                    evidence={"confidence": float(sec.confidence), "threshold": low_confidence_threshold},
                )
            )
            warnings.append(
                f"Low extraction confidence in '{hn}' ({slug}): {float(sec.confidence):.3f} "
                f"< {low_confidence_threshold:.2f}"
            )

    if doc.audit_synthesis is not None:
        dc = float(doc.audit_synthesis.confidence.document_confidence)
        if dc < document_low_confidence_warn:
            warnings.append(
                f"Document-level confidence {dc:.3f} is below advisory threshold "
                f"{document_low_confidence_warn:.2f}"
            )

    return diagnostics, warnings


def _audit_finding_counts(doc: ReportDocumentJson) -> tuple[int, int, int, str | None]:
    if doc.audit_synthesis is None:
        return 0, 0, 0, None
    a = doc.audit_synthesis
    fail = warn = rev = 0
    for f in a.findings:
        if f.severity == "FAIL":
            fail += 1
        elif f.severity == "WARN":
            warn += 1
        elif f.severity == "REVIEW":
            rev += 1
    return fail, warn, rev, a.overall_status


def _classify_outcome(
    *,
    had_exception: bool,
    audit_overall: str | None,
    diagnostics: list[DiagnosticRecord],
) -> tuple[str, bool]:
    """
    Return (status, save_debug).

    status in {succeeded, failed, partial_review}
    """
    if had_exception or audit_overall is None:
        return "failed", True
    if audit_overall == "FAIL":
        return "failed", True
    blocking = any(d.type in _BLOCKING_DIAGNOSTIC_TYPES for d in diagnostics)
    if audit_overall in ("WARN", "REVIEW") or blocking:
        return "partial_review", True
    return "succeeded", False


def _setup_report_logger(log_path: Path, stem: str) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lg = logging.getLogger(f"relay_batch.{stem}")
    lg.handlers.clear()
    lg.setLevel(logging.DEBUG)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    lg.addHandler(fh)
    lg.propagate = False
    return lg


def _json_log_line(level: str, **fields: Any) -> str:
    payload = {"level": level, **fields}
    return json.dumps(payload, ensure_ascii=False, default=str)


def process_relay_markdown_for_batch(
    markdown: str,
    *,
    stem: str,
    json_dir: Path,
    low_confidence_threshold: float,
    document_low_confidence_warn: float,
) -> tuple[ReportDocumentJson, list[DiagnosticRecord], list[str], tuple[int, int, int, str | None]]:
    """Build document + diagnostics (used by tests and internally after PDF parse)."""
    doc = build_report_document(markdown, json_dir=json_dir, json_stem=stem, json_indent=2)
    diagnostics, warns = collect_relay_report_diagnostics(
        doc,
        low_confidence_threshold=low_confidence_threshold,
        document_low_confidence_warn=document_low_confidence_warn,
    )
    counts = _audit_finding_counts(doc)
    return doc, diagnostics, warns, counts


def run_batch_pdf_validation(config: BatchHarnessConfig) -> BatchValidationSummary:
    """
    Process every ``*.pdf`` under ``config.input_dir`` (non-recursive).

    Writes:
    - ``{output_dir}/markdown/*.md``
    - ``{output_dir}/json/*.json``
    - ``{output_dir}/logs/*.log``
    - ``{output_dir}/batch_summary.json``
    - ``{output_dir}/batch_operator_summary.txt``
    - ``{output_dir}/debug/{stem}/`` on failure or partial_review when ``save_debug_artifacts``
    """
    inp = config.input_dir.expanduser().resolve()
    out = config.output_dir.expanduser().resolve()
    md_root = out / config.markdown_subdir
    js_root = out / config.json_subdir
    log_root = out / config.logs_subdir
    dbg_root = out / config.debug_subdir
    for d in (md_root, js_root, log_root, dbg_root):
        d.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(inp.glob("*.pdf"))
    reports: list[SingleReportBatchResult] = []
    failure_counter: Counter[str] = Counter()

    root_log = out / "batch_run.log"
    root_log.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(root_log, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    batch_logger = logging.getLogger("relay_batch_run")
    batch_logger.handlers.clear()
    batch_logger.setLevel(logging.INFO)
    batch_logger.addHandler(fh)
    batch_logger.propagate = False

    for pdf in pdfs:
        stem = pdf.stem
        t0 = time.perf_counter()
        lg = _setup_report_logger(log_root / f"{stem}.log", stem)
        md_path = md_root / f"{stem}.md"
        js_path = js_root / f"{stem}.json"
        had_exc = False
        err_type: str | None = None
        err_msg: str | None = None
        doc: ReportDocumentJson | None = None
        diagnostics: list[DiagnosticRecord] = []
        warns: list[str] = []
        counts = (0, 0, 0, None)

        lg.info(_json_log_line("INFO", event="batch_item_start", pdf=str(pdf)))
        batch_logger.info(_json_log_line("INFO", event="batch_item_start", stem=stem, pdf=str(pdf)))

        try:
            markdown = parse_pdf_to_markdown(pdf, markdown_dir=md_root, output_filename=md_path.name)
        except (DoclingPdfParseError, OSError, FileNotFoundError) as exc:
            had_exc = True
            err_type = type(exc).__name__
            err_msg = str(exc)
            lg.error(_json_log_line("ERROR", event="pdf_parse_failed", error_type=err_type, message=err_msg))
            batch_logger.error(
                _json_log_line("ERROR", event="pdf_parse_failed", stem=stem, error_type=err_type, message=err_msg)
            )
            duration = time.perf_counter() - t0
            rep = SingleReportBatchResult(
                stem=stem,
                pdf_path=str(pdf),
                status="failed",
                duration_seconds=duration,
                error_type=err_type,
                error_message=err_msg,
                markdown_path=str(md_path) if md_path.is_file() else None,
                json_path=None,
                log_path=str(log_root / f"{stem}.log"),
            )
            reports.append(rep)
            failure_counter[err_type or "unknown"] += 1
            if config.save_debug_artifacts:
                dest = dbg_root / stem
                dest.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(pdf, dest / pdf.name)
                except OSError:
                    lg.warning("Could not copy source PDF to debug folder")
            continue
        except Exception as exc:  # noqa: BLE001 — batch boundary: never stop
            had_exc = True
            err_type = type(exc).__name__
            err_msg = str(exc)
            lg.exception(_json_log_line("ERROR", event="pdf_parse_unexpected", error_type=err_type, message=err_msg))
            batch_logger.error(
                _json_log_line("ERROR", event="pdf_parse_unexpected", stem=stem, error_type=err_type, message=err_msg)
            )
            duration = time.perf_counter() - t0
            reports.append(
                SingleReportBatchResult(
                    stem=stem,
                    pdf_path=str(pdf),
                    status="failed",
                    duration_seconds=duration,
                    error_type=err_type,
                    error_message=err_msg,
                    markdown_path=str(md_path) if md_path.is_file() else None,
                    json_path=None,
                    log_path=str(log_root / f"{stem}.log"),
                )
            )
            failure_counter[err_type or "unexpected"] += 1
            continue

        try:
            doc, diagnostics, warns, counts = process_relay_markdown_for_batch(
                markdown,
                stem=stem,
                json_dir=js_root,
                low_confidence_threshold=config.low_confidence_threshold,
                document_low_confidence_warn=config.document_low_confidence_warn,
            )
        except Exception as exc:  # noqa: BLE001
            had_exc = True
            err_type = type(exc).__name__
            err_msg = str(exc)
            lg.exception(_json_log_line("ERROR", event="build_document_failed", error_type=err_type, message=err_msg))
            batch_logger.error(
                _json_log_line(
                    "ERROR", event="build_document_failed", stem=stem, error_type=err_type, message=err_msg
                )
            )
            duration = time.perf_counter() - t0
            reports.append(
                SingleReportBatchResult(
                    stem=stem,
                    pdf_path=str(pdf),
                    status="failed",
                    duration_seconds=duration,
                    error_type=err_type,
                    error_message=err_msg,
                    markdown_path=str(md_path) if md_path.is_file() else None,
                    json_path=None,
                    log_path=str(log_root / f"{stem}.log"),
                )
            )
            failure_counter[f"build:{err_type}"] += 1
            if config.save_debug_artifacts:
                dest = dbg_root / stem
                dest.mkdir(parents=True, exist_ok=True)
                if md_path.is_file():
                    shutil.copy2(md_path, dest / md_path.name)
            continue

        fail_n, warn_n, rev_n, overall = counts
        status, need_debug = _classify_outcome(
            had_exception=False,
            audit_overall=overall,
            diagnostics=diagnostics,
        )
        duration = time.perf_counter() - t0
        dc = float(doc.audit_synthesis.confidence.document_confidence) if doc.audit_synthesis else None

        for d in diagnostics:
            failure_counter[d.type] += 1

        lg.info(
            _json_log_line(
                "INFO",
                event="diagnostics_complete",
                diagnostics=[d.model_dump() for d in diagnostics],
                warnings=warns,
            )
        )

        rep = SingleReportBatchResult(
            stem=stem,
            pdf_path=str(pdf),
            status=status,  # type: ignore[arg-type]
            duration_seconds=duration,
            markdown_path=str(md_path),
            json_path=str(js_path),
            log_path=str(log_root / f"{stem}.log"),
            document_confidence=dc,
            section_count=len(doc.sections),
            audit_overall=overall,
            audit_fail_findings=fail_n,
            audit_warn_findings=warn_n,
            audit_review_findings=rev_n,
            diagnostics=diagnostics,
            warnings=warns,
        )
        reports.append(rep)

        lg.info(
            _json_log_line(
                "INFO",
                event="batch_item_done",
                status=status,
                duration_seconds=duration,
                sections=len(doc.sections),
                audit_overall=overall,
            )
        )
        batch_logger.info(
            _json_log_line(
                "INFO",
                event="batch_item_done",
                stem=stem,
                status=status,
                duration_seconds=round(duration, 3),
                audit_overall=overall,
            )
        )

        if config.save_debug_artifacts and need_debug:
            dest = dbg_root / stem
            dest.mkdir(parents=True, exist_ok=True)
            if md_path.is_file():
                shutil.copy2(md_path, dest / md_path.name)
            if Path(js_path).is_file():
                shutil.copy2(js_path, dest / Path(js_path).name)
            # operator per-report snippet
            if doc.audit_synthesis is not None:
                (dest / "operator_audit.txt").write_text(
                    render_audit_report_plain_text(doc.audit_synthesis),
                    encoding="utf-8",
                )

    ok = sum(1 for r in reports if r.status == "succeeded")
    partial = sum(1 for r in reports if r.status == "partial_review")
    failed = sum(1 for r in reports if r.status == "failed")
    common = [
        CommonFailureAggregate(type=k, count=v)
        for k, v in sorted(failure_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    summary = BatchValidationSummary(
        total_reports=len(reports),
        successful=ok,
        partial_review=partial,
        failed=failed,
        common_failures=common,
        reports=reports,
        output_dir=str(out),
    )

    summary_path = out / "batch_summary.json"
    summary_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")

    op_lines = [
        f"Batch output: {out}",
        f"Total PDFs: {summary.total_reports}",
        f"Successful: {summary.successful}",
        f"Partial / review: {summary.partial_review}",
        f"Failed: {summary.failed}",
        "",
        "Common failure / diagnostic counts:",
    ]
    for c in summary.common_failures[:25]:
        op_lines.append(f"  - {c.type}: {c.count}")
    op_lines.extend(["", "Per-report status:", ""])
    for r in reports:
        op_lines.append(
            f"  {r.stem}: {r.status} ({r.duration_seconds:.2f}s) "
            f"audit={r.audit_overall or 'n/a'} sections={r.section_count}"
        )
    (out / "batch_operator_summary.txt").write_text("\n".join(op_lines) + "\n", encoding="utf-8")

    batch_logger.info(
        _json_log_line(
            "INFO",
            event="batch_complete",
            total=summary.total_reports,
            successful=ok,
            partial_review=partial,
            failed=failed,
        )
    )

    return summary


__all__ = [
    "BatchHarnessConfig",
    "collect_relay_report_diagnostics",
    "process_relay_markdown_for_batch",
    "run_batch_pdf_validation",
]
