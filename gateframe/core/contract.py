from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from gateframe.core.failure import FailureResult
from gateframe.core.rule import Rule


class ValidationResult(BaseModel):
    passed: bool
    contract_name: str
    failures: list[FailureResult] = Field(default_factory=list)
    rules_applied: int
    rules_failed: int
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    model_config = {"frozen": True}


class ValidationContract:
    def __init__(self, name: str, rules: list[Rule]) -> None:
        self.name = name
        self.rules = rules

    def validate(self, output: Any, **context: Any) -> ValidationResult:  # noqa: ANN401
        failures: list[FailureResult] = []

        for rule in self.rules:
            result = rule.validate(output, **context)
            if result is not None:
                failures.append(result)

        return ValidationResult(
            passed=len(failures) == 0,
            contract_name=self.name,
            failures=failures,
            rules_applied=len(self.rules),
            rules_failed=len(failures),
        )
