from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from gateframe.core.contract import ValidationResult

logger = structlog.get_logger()


class AuditEntry:
    __slots__ = (
        "timestamp",
        "contract_name",
        "passed",
        "rules_applied",
        "rules_failed",
        "failures",
    )

    def __init__(self, result: ValidationResult) -> None:
        self.timestamp = datetime.now(timezone.utc)
        self.contract_name = result.contract_name
        self.passed = result.passed
        self.rules_applied = result.rules_applied
        self.rules_failed = result.rules_failed
        self.failures = [
            {
                "rule_name": f.rule_name,
                "failure_mode": f.failure_mode.value,
                "message": f.message,
            }
            for f in result.failures
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "contract_name": self.contract_name,
            "passed": self.passed,
            "rules_applied": self.rules_applied,
            "rules_failed": self.rules_failed,
            "failures": self.failures,
        }


class AuditLog:
    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def record(self, result: ValidationResult) -> None:
        entry = AuditEntry(result)
        self._entries.append(entry)
        logger.info(
            "validation_event",
            contract=entry.contract_name,
            passed=entry.passed,
            rules_applied=entry.rules_applied,
            rules_failed=entry.rules_failed,
        )

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()
