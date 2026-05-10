"""
JSON → Pydantic validation bridge: strict typing, extra-field policy, and error aggregation.

Sits between extraction (dict / JSON-like output) and the audit engine.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from relay_report_audit.schemas.report_payload import ReportPayload


def validate_report_payload(data: dict[str, Any]) -> ReportPayload:
    """Parse and validate a raw payload; raises ``ValidationError`` on schema violations."""
    return ReportPayload.model_validate(data)


def format_validation_error(err: ValidationError) -> str:
    """Placeholder: human-readable summary for logs or the final audit report."""
    return err.json()
