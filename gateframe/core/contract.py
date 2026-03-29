from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from gateframe.core.escalation import EscalationRoute
from gateframe.core.failure import FailureMode, FailureResult
from gateframe.core.rule import Rule


class ValidationResult(BaseModel):
    passed: bool
    contract_name: str
    failures: list[FailureResult] = Field(default_factory=list)
    rules_applied: int
    rules_failed: int
    has_hard_fail: bool = False
    has_soft_fail: bool = False
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    model_config = {"frozen": True}


class ValidationContract:
    def __init__(
        self,
        name: str,
        rules: list[Rule],
        on_hard_fail: EscalationRoute | None = None,
        on_soft_fail: EscalationRoute | None = None,
    ) -> None:
        self.name = name
        self.rules = rules
        self.on_hard_fail = on_hard_fail
        self.on_soft_fail = on_soft_fail

    def validate(self, output: Any, **context: Any) -> ValidationResult:  # noqa: ANN401
        failures: list[FailureResult] = []

        for rule in self.rules:
            result = rule.validate(output, **context)
            if result is not None:
                failures.append(result)

        failure_modes = {f.failure_mode for f in failures}

        return ValidationResult(
            passed=len(failures) == 0,
            contract_name=self.name,
            failures=failures,
            rules_applied=len(self.rules),
            rules_failed=len(failures),
            has_hard_fail=FailureMode.HARD_FAIL in failure_modes,
            has_soft_fail=FailureMode.SOFT_FAIL in failure_modes,
        )
