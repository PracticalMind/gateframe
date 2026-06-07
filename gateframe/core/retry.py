from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from gateframe.core.contract import ValidationContract, ValidationResult
from gateframe.core.failure import FailureMode


@dataclass
class RetryResult:
    """Outcome of a RetryPolicy.run() call.

    Attributes:
        final: The last ValidationResult produced (pass or exhausted retries).
        attempts: Total number of validate calls made (1 = no retry needed).
        succeeded: True if any attempt passed validation.
    """

    final: ValidationResult
    attempts: int
    succeeded: bool
    history: list[ValidationResult] = field(default_factory=list)


class RetryPolicy:
    """Executes a ValidationContract with automatic retry on RETRY failure mode.

    The caller supplies a ``prompt_fn`` callable that returns a fresh output
    on each invocation (e.g. re-calls the LLM).  On each attempt, if the
    result contains a RETRY failure, ``prompt_fn`` is called again with the
    previous failures injected as ``retry_failures`` context so the caller
    can craft a follow-up prompt.

    Args:
        max_retries: Maximum number of *additional* attempts after the first.
            Total attempts = max_retries + 1.

    Example::

        policy = RetryPolicy(max_retries=2)
        result = policy.run(
            contract,
            prompt_fn=lambda **ctx: call_llm(ctx.get("retry_failures")),
        )
        if result.succeeded:
            use(result.final)
    """

    def __init__(self, max_retries: int = 3) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        self.max_retries = max_retries

    def run(
        self,
        contract: ValidationContract,
        prompt_fn: Callable[..., Any],
        **context: Any,
    ) -> RetryResult:
        """Run *contract* against output from *prompt_fn*, retrying on RETRY failures.

        Args:
            contract: The ValidationContract to evaluate.
            prompt_fn: Called each attempt to produce the output to validate.
                Receives ``**context`` plus ``retry_failures`` (list of
                FailureResult) on retry attempts so callers can adjust prompts.
            **context: Extra keyword arguments forwarded to both ``prompt_fn``
                and ``contract.validate()``.

        Returns:
            A :class:`RetryResult` with the final result and attempt metadata.
        """
        history: list[ValidationResult] = []
        retry_failures: list = []

        for attempt in range(self.max_retries + 1):
            call_context = dict(context)
            if retry_failures:
                call_context["retry_failures"] = retry_failures

            output = prompt_fn(**call_context)
            result = contract.validate(output, **call_context)
            history.append(result)

            if result.passed:
                return RetryResult(
                    final=result,
                    attempts=attempt + 1,
                    succeeded=True,
                    history=history,
                )

            has_retry = any(f.failure_mode is FailureMode.RETRY for f in result.failures)
            if not has_retry or attempt == self.max_retries:
                break

            retry_failures = [f for f in result.failures if f.failure_mode is FailureMode.RETRY]

        return RetryResult(
            final=history[-1],
            attempts=len(history),
            succeeded=False,
            history=history,
        )
