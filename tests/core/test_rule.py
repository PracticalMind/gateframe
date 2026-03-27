from typing import Any

import pytest

from gateframe.core.failure import FailureMode, FailureResult
from gateframe.core.rule import Rule


class _PassingRule(Rule):
    def validate(self, output: Any, **context: Any) -> FailureResult | None:
        return None


class _FailingRule(Rule):
    def validate(self, output: Any, **context: Any) -> FailureResult | None:
        return FailureResult(
            rule_name=self.name,
            rule_description=self.description,
            failure_mode=FailureMode.HARD_FAIL,
            message=f"Output was {output!r}, expected something else.",
        )


class TestRule:

    def test_cannot_instantiate_directly(self) -> None:
        with pytest.raises(TypeError):
            Rule("test")  # type: ignore[abstract]

    def test_name_and_description(self) -> None:
        rule = _PassingRule("check_format", "Ensures output is formatted")
        assert rule.name == "check_format"
        assert rule.description == "Ensures output is formatted"

    def test_default_description_is_empty(self) -> None:
        rule = _PassingRule("check_format")
        assert rule.description == ""

    def test_passing_rule_returns_none(self) -> None:
        rule = _PassingRule("check")
        assert rule.validate("anything") is None

    def test_failing_rule_returns_failure_result(self) -> None:
        rule = _FailingRule("check", "desc")
        result = rule.validate("bad")
        assert isinstance(result, FailureResult)
        assert result.rule_name == "check"
        assert result.rule_description == "desc"
        assert result.failure_mode is FailureMode.HARD_FAIL

    def test_context_passed_to_validate(self) -> None:
        class _ContextRule(Rule):
            def validate(self, output: Any, **context: Any) -> FailureResult | None:
                if context.get("strict"):
                    return FailureResult(
                        rule_name=self.name,
                        failure_mode=FailureMode.HARD_FAIL,
                        message="Strict mode enabled.",
                    )
                return None

        rule = _ContextRule("ctx_check")
        assert rule.validate("data") is None
        assert rule.validate("data", strict=True) is not None
