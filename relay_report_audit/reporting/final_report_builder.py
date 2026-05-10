"""
Build the final audit artifact (JSON, HTML, PDF, etc.) from extraction + validation + findings.

Formatting concerns live here; the audit engine stays output-agnostic.
"""

from __future__ import annotations

from typing import Any

from relay_report_audit.audit.rule_types import AuditFinding
from relay_report_audit.schemas.report_payload import ReportPayload


def build_final_report(
    _payload: ReportPayload,
    _findings: list[AuditFinding],
) -> dict[str, Any]:
    """Placeholder: compose the customer-facing or archival audit report structure."""
    return {}
