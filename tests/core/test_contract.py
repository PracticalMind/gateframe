from typing import Any

import pytest
from pydantic import ValidationError

from gateframe.core.contract import ValidationContract, ValidationResult
from gateframe.core.escalation import EscalationRoute
from gateframe.core.failure import FailureMode, FailureResult
from gateframe.core.rule import Rule


class _PassingRule(Rule):
    def validate(self, output: Any, **context: Any) -> FailureResult | None:
        return None


class _FailingRule(Rule):
    def __init__(
        self,
        name: str = "failing_rule",
        mode: FailureMode = FailureMode.HARD_FAIL,
    ) -> None:
        super().__init__(name)
        self._mode = mode

    def validate(self, output: Any, **context: Any) -> FailureResult | None:
        return FailureResult(
            rule_name=self.name,
            failure_mode=self._mode,
            message=f"{self.name}: output rejected.",
        )


class TestValidationContract:
    def test_all_rules_pass(self) -> None:
        contract = ValidationContract("test", [_PassingRule("a"), _PassingRule("b")])
        result = contract.validate({"key": "value"})
        assert result.passed is True
        assert result.failures == []
        assert result.rules_applied == 2
        assert result.rules_failed == 0

    def test_single_failure(self) -> None:
        contract = ValidationContract("test", [_PassingRule("a"), _FailingRule("b")])
        result = contract.validate({"key": "value"})
        assert result.passed is False
        assert len(result.failures) == 1
        assert result.failures[0].rule_name == "b"

    def test_multiple_failures(self) -> None:
        contract = ValidationContract("test", [_FailingRule("a"), _FailingRule("b")])
        result = contract.validate({})
        assert result.passed is False
        assert len(result.failures) == 2
        assert result.rules_applied == 2
        assert result.rules_failed == 2

    def test_empty_rules_list(self) -> None:
        contract = ValidationContract("empty", [])
        result = contract.validate("anything")
        assert result.passed is True
        assert result.rules_applied == 0

    def test_contract_name_in_result(self) -> None:
        contract = ValidationContract("triage_check", [_PassingRule("a")])
        result = contract.validate({})
        assert result.contract_name == "triage_check"

    def test_result_has_timestamp(self) -> None:
        contract = ValidationContract("test", [_PassingRule("a")])
        result = contract.validate({})
        assert result.timestamp is not None
        assert result.timestamp.tzinfo is not None

    def test_result_is_frozen(self) -> None:
        contract = ValidationContract("test", [_PassingRule("a")])
        result = contract.validate({})
        with pytest.raises(ValidationError):
            result.passed = False  # type: ignore[misc]

    def test_context_forwarded_to_rules(self) -> None:
        class _ContextRule(Rule):
            def validate(self, output: Any, **context: Any) -> FailureResult | None:
                if context.get("role") != "admin":
                    return FailureResult(
                        rule_name=self.name,
                        failure_mode=FailureMode.HARD_FAIL,
                        message="Only admin allowed.",
                    )
                return None

        contract = ValidationContract("auth", [_ContextRule("role_check")])
        assert contract.validate({}, role="admin").passed is True
        assert contract.validate({}, role="user").passed is False


    def test_has_hard_fail_flag_set(self) -> None:
        contract = ValidationContract("test", [_FailingRule("r1", FailureMode.HARD_FAIL)])
        result = contract.validate({})
        assert result.has_hard_fail is True
        assert result.has_soft_fail is False

    def test_has_soft_fail_flag_set(self) -> None:
        contract = ValidationContract("test", [_FailingRule("r1", FailureMode.SOFT_FAIL)])
        result = contract.validate({})
        assert result.has_soft_fail is True
        assert result.has_hard_fail is False

    def test_no_failure_flags_when_passed(self) -> None:
        contract = ValidationContract("test", [_PassingRule("a")])
        result = contract.validate({})
        assert result.has_hard_fail is False
        assert result.has_soft_fail is False

    def test_escalation_routes_stored(self) -> None:
        contract = ValidationContract(
            "test",
            [_PassingRule("a")],
            on_hard_fail=EscalationRoute.HUMAN_REVIEW,
            on_soft_fail=EscalationRoute.FLAG_AND_CONTINUE,
        )
        assert contract.on_hard_fail is EscalationRoute.HUMAN_REVIEW
        assert contract.on_soft_fail is EscalationRoute.FLAG_AND_CONTINUE

    def test_escalation_routes_default_to_none(self) -> None:
        contract = ValidationContract("test", [_PassingRule("a")])
        assert contract.on_hard_fail is None
        assert contract.on_soft_fail is None


class TestValidationResult:
    def test_serialization_roundtrip(self) -> None:
        result = ValidationResult(
            passed=False,
            contract_name="test",
            failures=[
                FailureResult(
                    rule_name="r1",
                    failure_mode=FailureMode.HARD_FAIL,
                    message="Failed.",
                )
            ],
            rules_applied=1,
            rules_failed=1,
        )
        data = result.model_dump()
        restored = ValidationResult(**data)
        assert restored == result
