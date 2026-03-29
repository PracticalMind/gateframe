from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import structlog

from gateframe.core.contract import ValidationResult

if TYPE_CHECKING:
    from gateframe.core.context import WorkflowContext

logger = structlog.get_logger()


class AuditEntry:
    __slots__ = (
        "timestamp",
        "contract_name",
        "passed",
        "rules_applied",
        "rules_failed",
        "failures",
        "workflow_id",
        "confidence",
    )

    def __init__(
        self,
        result: ValidationResult,
        workflow_context: WorkflowContext | None = None,
    ) -> None:
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
        self.workflow_id = workflow_context.workflow_id if workflow_context else None
        self.confidence = workflow_context.confidence if workflow_context else None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "timestamp": self.timestamp.isoformat(),
            "contract_name": self.contract_name,
            "passed": self.passed,
            "rules_applied": self.rules_applied,
            "rules_failed": self.rules_failed,
            "failures": self.failures,
        }
        if self.workflow_id is not None:
            data["workflow_id"] = self.workflow_id
            data["confidence"] = self.confidence
        return data


class AuditLog:
    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def record(
        self,
        result: ValidationResult,
        workflow_context: WorkflowContext | None = None,
    ) -> None:
        entry = AuditEntry(result, workflow_context=workflow_context)
        self._entries.append(entry)
        log_kwargs: dict[str, Any] = {
            "contract": entry.contract_name,
            "passed": entry.passed,
            "rules_applied": entry.rules_applied,
            "rules_failed": entry.rules_failed,
        }
        if entry.workflow_id is not None:
            log_kwargs["workflow_id"] = entry.workflow_id
            log_kwargs["confidence"] = entry.confidence
        logger.info("validation_event", **log_kwargs)

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()
