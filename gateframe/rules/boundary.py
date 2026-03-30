from __future__ import annotations

from collections.abc import Callable
from typing import Any

from gateframe.core.failure import FailureMode, FailureResult
from gateframe.core.rule import Rule


class BoundaryRule(Rule):
    def __init__(
        self,
        check: Callable[..., bool],
        name: str = "boundary_check",
        description: str = "",
        failure_mode: FailureMode = FailureMode.HARD_FAIL,
        failure_message: str = "",
    ) -> None:
        super().__init__(name, description)
        self._check = check
        self.failure_mode = failure_mode
        self._failure_message = failure_message

    def validate(self, output: Any, **context: Any) -> FailureResult | None:  # noqa: ANN401
        try:
            passed = self._check(output, **context)
        except Exception as exc:
            return FailureResult(
                rule_name=self.name,
                rule_description=self.description,
                failure_mode=self.failure_mode,
                message=f"{self.name} raised an exception: {exc}",
                context={"exception_type": type(exc).__name__, "exception_message": str(exc)},
            )

        if passed:
            return None

        message = self._failure_message or f"{self.name} failed: boundary check returned False."
        return FailureResult(
            rule_name=self.name,
            rule_description=self.description,
            failure_mode=self.failure_mode,
            message=message,
        )


class AllowedValues:
    def __init__(self, field: str, allowed: set[Any]) -> None:
        self._field = field
        self._allowed = allowed

    def __call__(self, output: Any, **context: Any) -> bool:  # noqa: ANN401
        if isinstance(output, dict):
            value = output.get(self._field)
        else:
            value = getattr(output, self._field, None)
        return value in self._allowed
