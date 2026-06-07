from typing import Any

import pytest

from gateframe.core.contract import ValidationContract
from gateframe.core.failure import FailureMode, FailureResult
from gateframe.core.retry import RetryPolicy
from gateframe.core.rule import Rule


class _PassingRule(Rule):
    def validate(self, output: Any, **context: Any) -> FailureResult | None:
        return None


class _FailingRule(Rule):
    def __init__(self, name: str = "failing", mode: FailureMode = FailureMode.RETRY) -> None:
        super().__init__(name)
        self._mode = mode

    def validate(self, output: Any, **context: Any) -> FailureResult | None:
        return FailureResult(rule_name=self.name, failure_mode=self._mode, message="rejected")


class _PassOnAttempt(Rule):
    """Passes on the Nth call (1-indexed)."""

    def __init__(self, pass_on: int) -> None:
        super().__init__("pass_on_attempt")
        self._pass_on = pass_on
        self._calls = 0

    def validate(self, output: Any, **context: Any) -> FailureResult | None:
        self._calls += 1
        if self._calls >= self._pass_on:
            return None
        return FailureResult(rule_name=self.name, failure_mode=FailureMode.RETRY, message="not yet")


class TestRetryPolicy:
    def test_passes_on_first_attempt(self) -> None:
        contract = ValidationContract("c", [_PassingRule("r")])
        policy = RetryPolicy(max_retries=2)
        result = policy.run(contract, prompt_fn=lambda **ctx: {})
        assert result.succeeded is True
        assert result.attempts == 1

    def test_retries_until_pass(self) -> None:
        rule = _PassOnAttempt(pass_on=3)
        contract = ValidationContract("c", [rule])
        policy = RetryPolicy(max_retries=3)
        result = policy.run(contract, prompt_fn=lambda **ctx: {})
        assert result.succeeded is True
        assert result.attempts == 3

    def test_exhausts_retries_and_fails(self) -> None:
        contract = ValidationContract("c", [_FailingRule(mode=FailureMode.RETRY)])
        policy = RetryPolicy(max_retries=2)
        result = policy.run(contract, prompt_fn=lambda **ctx: {})
        assert result.succeeded is False
        assert result.attempts == 3  # 1 initial + 2 retries

    def test_does_not_retry_on_hard_fail(self) -> None:
        contract = ValidationContract("c", [_FailingRule(mode=FailureMode.HARD_FAIL)])
        policy = RetryPolicy(max_retries=3)
        result = policy.run(contract, prompt_fn=lambda **ctx: {})
        assert result.succeeded is False
        assert result.attempts == 1

    def test_does_not_retry_on_soft_fail(self) -> None:
        contract = ValidationContract("c", [_FailingRule(mode=FailureMode.SOFT_FAIL)])
        policy = RetryPolicy(max_retries=3)
        result = policy.run(contract, prompt_fn=lambda **ctx: {})
        assert result.succeeded is False
        assert result.attempts == 1

    def test_retry_failures_passed_to_prompt_fn(self) -> None:
        received: list = []

        def prompt_fn(**ctx: Any) -> dict:
            received.append(ctx.get("retry_failures"))
            return {}

        contract = ValidationContract("c", [_FailingRule(mode=FailureMode.RETRY)])
        policy = RetryPolicy(max_retries=1)
        policy.run(contract, prompt_fn=prompt_fn)

        assert received[0] is None  # first call has no retry context
        assert received[1] is not None  # second call has failures injected
        assert received[1][0].failure_mode is FailureMode.RETRY

    def test_context_forwarded_to_contract(self) -> None:
        class _ContextRule(Rule):
            def validate(self, output: Any, **context: Any) -> FailureResult | None:
                if context.get("role") != "admin":
                    return FailureResult(
                        rule_name=self.name,
                        failure_mode=FailureMode.HARD_FAIL,
                        message="forbidden",
                    )
                return None

        contract = ValidationContract("c", [_ContextRule("role_check")])
        policy = RetryPolicy()
        result = policy.run(contract, prompt_fn=lambda **ctx: {}, role="admin")
        assert result.succeeded is True

    def test_history_contains_all_attempts(self) -> None:
        contract = ValidationContract("c", [_FailingRule(mode=FailureMode.RETRY)])
        policy = RetryPolicy(max_retries=2)
        result = policy.run(contract, prompt_fn=lambda **ctx: {})
        assert len(result.history) == 3

    def test_max_retries_zero_means_single_attempt(self) -> None:
        contract = ValidationContract("c", [_FailingRule(mode=FailureMode.RETRY)])
        policy = RetryPolicy(max_retries=0)
        result = policy.run(contract, prompt_fn=lambda **ctx: {})
        assert result.attempts == 1
        assert result.succeeded is False

    def test_negative_max_retries_raises(self) -> None:
        with pytest.raises(ValueError, match="max_retries"):
            RetryPolicy(max_retries=-1)

    def test_retry_result_final_is_last_result(self) -> None:
        contract = ValidationContract("c", [_FailingRule(mode=FailureMode.RETRY)])
        policy = RetryPolicy(max_retries=1)
        result = policy.run(contract, prompt_fn=lambda **ctx: {})
        assert result.final is result.history[-1]
