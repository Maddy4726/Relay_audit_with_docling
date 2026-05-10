"""Audit engine: business rules over validated ``ReportPayload``, producing findings."""

from relay_report_audit.audit.aggregation import synthesize_report_audit

__all__ = ["synthesize_report_audit"]
