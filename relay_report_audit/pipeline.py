"""
End-to-end pipeline orchestration: PDF → Docling → sections → extraction → validation → audit → report.

This module defines the high-level stages only; each stage delegates to a dedicated subpackage
so new relay vendors/formats can plug in without rewriting the graph.
"""

from __future__ import annotations

from relay_report_audit.config import AuditSettings


def run_audit_pipeline(pdf_path: str, settings: AuditSettings | None = None) -> None:
    """Wire stages together once implementations exist; currently a structural placeholder."""
    _ = pdf_path
    _ = settings or AuditSettings()
    # PDF → Docling → section detection → Qwen extraction → JSON validation → audit → final report
    pass
