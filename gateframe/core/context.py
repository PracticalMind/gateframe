from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from gateframe.core.contract import ValidationResult
from gateframe.core.failure import FailureMode

logger = structlog.get_logger()


class StepRecord:
    __slots__ = (
        "step_index",
        "contract_name",
        "passed",
        "confidence_before",
        "confidence_after",
        "penalty_applied",
        "failure_modes",
        "timestamp",
    )

    def __init__(
        self,
        step_index: int,
        contract_name: str,
        passed: bool,
        confidence_before: float,
        confidence_after: float,
        penalty_applied: float,
        failure_modes: list[FailureMode],
    ) -> None:
        self.step_index = step_index
        self.contract_name = contract_name
        self.passed = passed
        self.confidence_before = confidence_before
        self.confidence_after = confidence_after
        self.penalty_applied = penalty_applied
        self.failure_modes = failure_modes
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "contract_name": self.contract_name,
            "passed": self.passed,
            "confidence_before": self.confidence_before,
            "confidence_after": self.confidence_after,
            "penalty_applied": self.penalty_applied,
            "failure_modes": [m.value for m in self.failure_modes],
            "timestamp": self.timestamp.isoformat(),
        }


class WorkflowContext:
    def __init__(
        self,
        workflow_id: str,
        escalation_threshold: float = 0.5,
        initial_confidence: float = 1.0,
        soft_fail_penalty: float = 0.15,
        silent_fail_penalty: float = 0.1,
    ) -> None:
        self.workflow_id = workflow_id
        self.escalation_threshold = escalation_threshold
        self.confidence = initial_confidence
        self._initial_confidence = initial_confidence
        self._soft_fail_penalty = soft_fail_penalty
        self._silent_fail_penalty = silent_fail_penalty
        self._history: list[StepRecord] = []

    @property
    def history(self) -> list[StepRecord]:
        return list(self._history)

    @property
    def step_count(self) -> int:
        return len(self._history)

    @property
    def threshold_breached(self) -> bool:
        return self.confidence < self.escalation_threshold

    def update(self, result: ValidationResult) -> None:
        confidence_before = self.confidence
        penalty = self._compute_penalty(result)
        self.confidence = max(0.0, self.confidence - penalty)

        record = StepRecord(
            step_index=len(self._history),
            contract_name=result.contract_name,
            passed=result.passed,
            confidence_before=confidence_before,
            confidence_after=self.confidence,
            penalty_applied=penalty,
            failure_modes=[f.failure_mode for f in result.failures],
        )
        self._history.append(record)

        logger.info(
            "workflow_step",
            workflow_id=self.workflow_id,
            step_index=record.step_index,
            contract=result.contract_name,
            passed=result.passed,
            confidence=self.confidence,
            threshold_breached=self.threshold_breached,
        )

    def _compute_penalty(self, result: ValidationResult) -> float:
        penalty = 0.0
        for failure in result.failures:
            if failure.failure_mode is FailureMode.SOFT_FAIL:
                penalty += self._soft_fail_penalty
            elif failure.failure_mode is FailureMode.SILENT_FAIL:
                penalty += self._silent_fail_penalty
        return penalty

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "confidence": self.confidence,
            "escalation_threshold": self.escalation_threshold,
            "threshold_breached": self.threshold_breached,
            "step_count": self.step_count,
            "history": [r.to_dict() for r in self._history],
        }
