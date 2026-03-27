from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from gateframe.core.failure import FailureMode, FailureResult
from gateframe.core.rule import Rule


class StructuralRule(Rule):
    def __init__(
        self,
        schema: type[BaseModel],
        failure_mode: FailureMode = FailureMode.HARD_FAIL,
        name: str = "",
        description: str = "",
    ) -> None:
        resolved_name = name or f"structural:{schema.__name__}"
        super().__init__(resolved_name, description)
        self.schema = schema
        self.failure_mode = failure_mode

    def validate(self, output: Any, **context: Any) -> FailureResult | None:  # noqa: ANN401
        if isinstance(output, self.schema):
            return None

        if isinstance(output, dict):
            try:
                self.schema.model_validate(output)
                return None
            except ValidationError as exc:
                return self._build_failure(exc)

        return FailureResult(
            rule_name=self.name,
            rule_description=self.description,
            failure_mode=self.failure_mode,
            message=(
                f"{self.name} failed: expected dict or {self.schema.__name__}, "
                f"got {type(output).__name__}."
            ),
            context={"expected_type": self.schema.__name__, "actual_type": type(output).__name__},
        )

    def _build_failure(self, exc: ValidationError) -> FailureResult:
        errors = exc.errors()
        parts = []
        for err in errors:
            loc = ".".join(str(segment) for segment in err["loc"])
            parts.append(f"{loc}: {err['msg']}")
        detail = "; ".join(parts)

        return FailureResult(
            rule_name=self.name,
            rule_description=self.description,
            failure_mode=self.failure_mode,
            message=f"{self.name} failed: {detail}.",
            context={"validation_errors": errors},
        )
