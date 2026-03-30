from __future__ import annotations

from collections.abc import Callable
from typing import Any

from gateframe.core.failure import FailureMode, FailureResult
from gateframe.core.rule import Rule


class ConfidenceRule(Rule):
    def __init__(
        self,
        *,
        field: str | None = None,
        minimum: float | None = None,
        maximum: float | None = None,
        check: Callable[..., bool] | None = None,
        name: str = "confidence_check",
        description: str = "",
        failure_mode: FailureMode = FailureMode.SOFT_FAIL,
        failure_message: str = "",
    ) -> None:
        if field is None and check is None:
            raise ValueError("ConfidenceRule requires either 'field' or 'check'.")
        if field is not None and check is not None:
            raise ValueError("ConfidenceRule accepts either 'field' or 'check', not both.")
        super().__init__(name, description)
        self._field = field
        self._minimum = minimum
        self._maximum = maximum
        self._check = check
        self.failure_mode = failure_mode
        self._failure_message = failure_message

    def validate(self, output: Any, **context: Any) -> FailureResult | None:  # noqa: ANN401
        if self._check is not None:
            return self._validate_callable(output, **context)
        return self._validate_threshold(output)

    def _validate_callable(self, output: Any, **context: Any) -> FailureResult | None:  # noqa: ANN401
        assert self._check is not None
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
        message = self._failure_message or f"{self.name} failed: confidence check returned False."
        return FailureResult(
            rule_name=self.name,
            rule_description=self.description,
            failure_mode=self.failure_mode,
            message=message,
        )

    def _validate_threshold(self, output: Any) -> FailureResult | None:  # noqa: ANN401
        assert self._field is not None
        field = self._field

        if isinstance(output, dict):
            if field not in output:
                return FailureResult(
                    rule_name=self.name,
                    rule_description=self.description,
                    failure_mode=self.failure_mode,
                    message=f"{self.name} failed: field '{field}' not found in output.",
                )
            value = output[field]
        else:
            if not hasattr(output, field):
                return FailureResult(
                    rule_name=self.name,
                    rule_description=self.description,
                    failure_mode=self.failure_mode,
                    message=f"{self.name} failed: field '{field}' not found in output.",
                )
            value = getattr(output, field)

        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return FailureResult(
                rule_name=self.name,
                rule_description=self.description,
                failure_mode=self.failure_mode,
                message=(
                    f"{self.name} failed: field '{field}' is not numeric"
                    f" (got {type(value).__name__})."
                ),
            )

        if self._minimum is not None and value < self._minimum:
            return FailureResult(
                rule_name=self.name,
                rule_description=self.description,
                failure_mode=self.failure_mode,
                message=f"Confidence {value} is below minimum threshold {self._minimum}.",
            )

        if self._maximum is not None and value > self._maximum:
            return FailureResult(
                rule_name=self.name,
                rule_description=self.description,
                failure_mode=self.failure_mode,
                message=f"Confidence {value} exceeds maximum threshold {self._maximum}.",
            )

        return None
