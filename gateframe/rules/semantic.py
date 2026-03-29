from __future__ import annotations

from collections.abc import Callable
from typing import Any

from gateframe.core.failure import FailureMode, FailureResult
from gateframe.core.rule import Rule


class SemanticRule(Rule):
    def __init__(
        self,
        check: Callable[..., bool],
        name: str = "semantic_check",
        description: str = "",
        failure_mode: FailureMode = FailureMode.SOFT_FAIL,
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

        message = self._failure_message or f"{self.name} failed: semantic check returned False."
        return FailureResult(
            rule_name=self.name,
            rule_description=self.description,
            failure_mode=self.failure_mode,
            message=message,
        )


class LlmJudge:
    """EXPENSIVE: Each call invokes the provided LLM function.
    The caller supplies the actual LLM call -- gateframe does not import any LLM SDK."""

    def __init__(
        self,
        prompt_template: str,
        llm_call: Callable[[str], str],
        passing_response: str = "PASS",
    ) -> None:
        self._prompt_template = prompt_template
        self._llm_call = llm_call
        self._passing_response = passing_response

    def __call__(self, output: Any, **context: Any) -> bool:  # noqa: ANN401
        prompt = self._prompt_template.format(output=output, **context)
        response = self._llm_call(prompt)
        return self._passing_response.lower() in response.strip().lower()
