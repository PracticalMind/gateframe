from dataclasses import dataclass

import pytest

from gateframe.core.failure import FailureMode
from gateframe.rules.boundary import AllowedValues, BoundaryRule


class TestBoundaryRule:
    def test_passes_when_check_returns_true(self) -> None:
        rule = BoundaryRule(check=lambda output, **ctx: True)
        assert rule.validate("x") is None

    def test_fails_when_check_returns_false(self) -> None:
        rule = BoundaryRule(check=lambda output, **ctx: False)
        result = rule.validate("x")
        assert result is not None
        assert result.failure_mode == FailureMode.HARD_FAIL

    def test_default_failure_mode_is_hard_fail(self) -> None:
        rule = BoundaryRule(check=lambda output, **ctx: False)
        result = rule.validate("x")
        assert result is not None
        assert result.failure_mode == FailureMode.HARD_FAIL

    def test_custom_failure_mode(self) -> None:
        rule = BoundaryRule(check=lambda output, **ctx: False, failure_mode=FailureMode.SOFT_FAIL)
        result = rule.validate("x")
        assert result is not None
        assert result.failure_mode == FailureMode.SOFT_FAIL

    def test_default_name(self) -> None:
        rule = BoundaryRule(check=lambda output, **ctx: True)
        assert rule.name == "boundary_check"

    def test_custom_name(self) -> None:
        rule = BoundaryRule(check=lambda output, **ctx: True, name="role_check")
        assert rule.name == "role_check"

    def test_default_failure_message(self) -> None:
        rule = BoundaryRule(check=lambda output, **ctx: False, name="role_check")
        result = rule.validate("x")
        assert result is not None
        assert "role_check" in result.message
        assert "boundary check returned False" in result.message

    def test_custom_failure_message(self) -> None:
        rule = BoundaryRule(
            check=lambda output, **ctx: False,
            failure_message="Action not permitted for this role.",
        )
        result = rule.validate("x")
        assert result is not None
        assert result.message == "Action not permitted for this role."

    def test_exception_in_check_returns_failure(self) -> None:
        def bad_check(output: object, **ctx: object) -> bool:
            raise RuntimeError("scope lookup failed")

        rule = BoundaryRule(check=bad_check)
        result = rule.validate("x")
        assert result is not None
        assert "raised an exception" in result.message
        assert result.context["exception_type"] == "RuntimeError"

    def test_context_forwarded_to_check(self) -> None:
        received: dict = {}

        def capture(output: object, **ctx: object) -> bool:
            received.update(ctx)
            return True

        rule = BoundaryRule(check=capture)
        rule.validate("x", role="admin", step=3)
        assert received["role"] == "admin"
        assert received["step"] == 3

    def test_failure_result_rule_name(self) -> None:
        rule = BoundaryRule(check=lambda output, **ctx: False, name="scope_check")
        result = rule.validate("x")
        assert result is not None
        assert result.rule_name == "scope_check"


class TestAllowedValues:
    def test_member_passes(self) -> None:
        av = AllowedValues(field="action", allowed={"approve", "reject"})
        assert av({"action": "approve"}) is True

    def test_non_member_fails(self) -> None:
        av = AllowedValues(field="action", allowed={"approve", "reject"})
        assert av({"action": "escalate"}) is False

    def test_missing_field_fails(self) -> None:
        av = AllowedValues(field="action", allowed={"approve"})
        assert av({}) is False

    def test_object_attribute_access(self) -> None:
        @dataclass
        class Output:
            action: str

        av = AllowedValues(field="action", allowed={"approve"})
        assert av(Output(action="approve")) is True
        assert av(Output(action="deny")) is False

    def test_object_missing_attribute_fails(self) -> None:
        av = AllowedValues(field="role", allowed={"admin"})
        assert av(object()) is False

    def test_composed_with_boundary_rule(self) -> None:
        av = AllowedValues(field="priority", allowed={"low", "medium", "high"})
        rule = BoundaryRule(check=av, name="priority_check")

        assert rule.validate({"priority": "high"}) is None

        result = rule.validate({"priority": "critical"})
        assert result is not None
        assert result.failure_mode == FailureMode.HARD_FAIL

    def test_none_value_not_in_set(self) -> None:
        av = AllowedValues(field="action", allowed={"approve"})
        assert av({"action": None}) is False

    @pytest.mark.parametrize("value", ["approve", "reject", "escalate"])
    def test_parametrized_membership(self, value: str) -> None:
        av = AllowedValues(field="action", allowed={"approve", "reject"})
        expected = value in {"approve", "reject"}
        assert av({"action": value}) is expected
