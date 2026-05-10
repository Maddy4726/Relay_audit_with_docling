"""
Audit finding types: severity, rule codes, references to payload paths, and remediation hints.

Kept small so reporting and APIs can depend on stable enums/dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FindingSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class AuditFinding:
    """Single rule outcome attached to a validated report."""

    code: str
    severity: FindingSeverity
    message: str
