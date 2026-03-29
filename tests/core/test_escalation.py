from typing import Any

import pytest

from gateframe.core.context import WorkflowContext
from gateframe.core.contract import ValidationContract, ValidationResult
from gateframe.core.escalation import EscalationResult, EscalationRoute, EscalationRouter
from gateframe.core.failure import FailureMode, FailureResult
from gateframe.core.rule import Rule


class _FailingRule(Rule):
    def __init__(self, name: str, mode: FailureMode) -> None:
        super().__init__(name)
        self._mode = mode

    def validate(self, output: Any, **context: Any) -> FailureResult | None:
        return FailureResult(
            rule_name=self.name,
            failure_mode=self._mode,
            message=f"{self.name}: rejected.",
        )


class TestEscalationRoute:
    def test_has_five_members(self) -> None:
        assert len(EscalationRoute) == 5

    def test_values(self) -> None:
        assert EscalationRoute.HUMAN_REVIEW.value == "human_review"
        assert EscalationRoute.FALLBACK_MODEL.value == "fallback_model"
        assert EscalationRoute.SAFE_DEFAULT.value == "safe_default"
        assert EscalationRoute.ABORT.value == "abort"
        assert EscalationRoute.FLAG_AND_CONTINUE.value == "flag_and_continue"

    def test_constructible_from_string(self) -> None:
        assert EscalationRoute("human_review") is EscalationRoute.HUMAN_REVIEW

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            EscalationRoute("invalid")


class TestEscalationResult:
    def test_fields(self) -> None:
        result = EscalationResult(
            route=EscalationRoute.ABORT,
            reason="test reason",
            context={"key": "value"},
        )
        assert result.route is EscalationRoute.ABORT
        assert result.reason == "test reason"
        assert result.context == {"key": "value"}

    def test_to_dict(self) -> None:
        result = EscalationResult(
            route=EscalationRoute.HUMAN_REVIEW,
            reason="needs review",
            context={"contract": "triage"},
        )
        data = result.to_dict()
        assert data["route"] == "human_review"
        assert data["reason"] == "needs review"
        assert data["context"] == {"contract": "triage"}


class TestEscalationRouter:
    def test_no_escalation_on_pass(self) -> None:
        router = EscalationRouter()
        result = ValidationResult(
            passed=True, contract_name="test", rules_applied=1, rules_failed=0,
        )
        assert router.route(result) is None

    def test_hard_fail_triggers_configured_route(self) -> None:
        router = EscalationRouter(on_hard_fail=EscalationRoute.HUMAN_REVIEW)
        contract = ValidationContract("test", [_FailingRule("r1", FailureMode.HARD_FAIL)])
        result = contract.validate({})
        escalation = router.route(result)
        assert escalation is not None
        assert escalation.route is EscalationRoute.HUMAN_REVIEW

    def test_soft_fail_flag_and_continue_returns_none(self) -> None:
        router = EscalationRouter(on_soft_fail=EscalationRoute.FLAG_AND_CONTINUE)
        contract = ValidationContract("test", [_FailingRule("r1", FailureMode.SOFT_FAIL)])
        result = contract.validate({})
        assert router.route(result) is None

    def test_soft_fail_with_escalation_route(self) -> None:
        router = EscalationRouter(on_soft_fail=EscalationRoute.FALLBACK_MODEL)
        contract = ValidationContract("test", [_FailingRule("r1", FailureMode.SOFT_FAIL)])
        result = contract.validate({})
        escalation = router.route(result)
        assert escalation is not None
        assert escalation.route is EscalationRoute.FALLBACK_MODEL

    def test_default_routes(self) -> None:
        router = EscalationRouter()
        assert router.on_hard_fail is EscalationRoute.ABORT
        assert router.on_soft_fail is EscalationRoute.FLAG_AND_CONTINUE
        assert router.on_threshold_breach is EscalationRoute.HUMAN_REVIEW

    def test_threshold_breach_triggers_route(self) -> None:
        router = EscalationRouter(on_threshold_breach=EscalationRoute.ABORT)
        ctx = WorkflowContext("wf1", escalation_threshold=0.8, initial_confidence=0.5)
        escalation = router.route_threshold_breach(ctx)
        assert escalation is not None
        assert escalation.route is EscalationRoute.ABORT

    def test_threshold_not_breached_returns_none(self) -> None:
        router = EscalationRouter()
        ctx = WorkflowContext("wf1", escalation_threshold=0.3, initial_confidence=1.0)
        assert router.route_threshold_breach(ctx) is None

    def test_hard_fail_takes_priority_over_soft_fail(self) -> None:
        router = EscalationRouter(
            on_hard_fail=EscalationRoute.ABORT,
            on_soft_fail=EscalationRoute.FALLBACK_MODEL,
        )
        contract = ValidationContract(
            "test",
            [_FailingRule("r1", FailureMode.HARD_FAIL), _FailingRule("r2", FailureMode.SOFT_FAIL)],
        )
        result = contract.validate({})
        escalation = router.route(result)
        assert escalation is not None
        assert escalation.route is EscalationRoute.ABORT
