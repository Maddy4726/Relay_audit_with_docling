"""
Audit engine: run registered rules against a validated ``ReportPayload``.

Rules should be pure functions or small classes so they can be unit-tested independently of PDF I/O.
"""

from __future__ import annotations

from relay_report_audit.audit.rule_types import AuditFinding
from relay_report_audit.schemas.report_payload import ReportPayload


def run_audit(_payload: ReportPayload) -> list[AuditFinding]:
    """Placeholder: evaluate all applicable rules and return ordered findings."""
    return []
