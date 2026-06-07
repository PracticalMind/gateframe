import threading
from typing import Any

import pytest

from gateframe.core.context import StepRecord, WorkflowContext
from gateframe.core.contract import ValidationResult
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


class _PassingRule(Rule):
    def validate(self, output: Any, **context: Any) -> FailureResult | None:
        return None


def _make_result(
    passed: bool = True,
    failures: list[FailureResult] | None = None,
    contract_name: str = "test",
) -> ValidationResult:
    if failures is None:
        failures = []
    failure_modes = {f.failure_mode for f in failures}
    return ValidationResult(
        passed=passed,
        contract_name=contract_name,
        failures=failures,
        rules_applied=1,
        rules_failed=len(failures),
        has_hard_fail=FailureMode.HARD_FAIL in failure_modes,
        has_soft_fail=FailureMode.SOFT_FAIL in failure_modes,
    )


def _soft_failure(name: str = "rule_a") -> FailureResult:
    return FailureResult(
        rule_name=name,
        failure_mode=FailureMode.SOFT_FAIL,
        message=f"{name}: soft fail.",
    )


def _silent_failure(name: str = "rule_b") -> FailureResult:
    return FailureResult(
        rule_name=name,
        failure_mode=FailureMode.SILENT_FAIL,
        message=f"{name}: silent fail.",
    )


def _hard_failure(name: str = "rule_c") -> FailureResult:
    return FailureResult(
        rule_name=name,
        failure_mode=FailureMode.HARD_FAIL,
        message=f"{name}: hard fail.",
    )


def _retry_failure(name: str = "rule_d") -> FailureResult:
    return FailureResult(
        rule_name=name,
        failure_mode=FailureMode.RETRY,
        message=f"{name}: retry.",
    )


class TestWorkflowContext:
    def test_initial_confidence_is_one(self) -> None:
        ctx = WorkflowContext("wf1")
        assert ctx.confidence == 1.0

    def test_custom_initial_confidence(self) -> None:
        ctx = WorkflowContext("wf1", initial_confidence=0.8)
        assert ctx.confidence == 0.8

    def test_soft_fail_degrades_confidence(self) -> None:
        ctx = WorkflowContext("wf1")
        result = _make_result(passed=False, failures=[_soft_failure()])
        ctx.update(result)
        assert ctx.confidence == pytest.approx(0.85)

    def test_multiple_soft_fails_stack(self) -> None:
        ctx = WorkflowContext("wf1")
        result = _make_result(
            passed=False,
            failures=[_soft_failure("a"), _soft_failure("b"), _soft_failure("c")],
        )
        ctx.update(result)
        assert ctx.confidence == pytest.approx(0.55)

    def test_hard_fail_does_not_degrade(self) -> None:
        ctx = WorkflowContext("wf1")
        result = _make_result(passed=False, failures=[_hard_failure()])
        ctx.update(result)
        assert ctx.confidence == 1.0

    def test_retry_does_not_degrade(self) -> None:
        ctx = WorkflowContext("wf1")
        result = _make_result(passed=False, failures=[_retry_failure()])
        ctx.update(result)
        assert ctx.confidence == 1.0

    def test_silent_fail_degrades_confidence(self) -> None:
        ctx = WorkflowContext("wf1")
        result = _make_result(passed=False, failures=[_silent_failure()])
        ctx.update(result)
        assert ctx.confidence == pytest.approx(0.9)

    def test_cross_step_cumulative_degradation(self) -> None:
        ctx = WorkflowContext("wf1")
        ctx.update(_make_result(passed=False, failures=[_soft_failure()]))
        ctx.update(_make_result(passed=False, failures=[_soft_failure()]))
        assert ctx.confidence == pytest.approx(0.70)

    def test_threshold_breach_detected(self) -> None:
        ctx = WorkflowContext("wf1", escalation_threshold=0.8)
        ctx.update(_make_result(passed=False, failures=[_soft_failure(), _soft_failure()]))
        assert ctx.threshold_breached is True

    def test_threshold_not_breached(self) -> None:
        ctx = WorkflowContext("wf1", escalation_threshold=0.5)
        ctx.update(_make_result(passed=False, failures=[_soft_failure()]))
        assert ctx.threshold_breached is False

    def test_confidence_floor_at_zero(self) -> None:
        ctx = WorkflowContext("wf1", soft_fail_penalty=0.5)
        for _ in range(5):
            ctx.update(_make_result(passed=False, failures=[_soft_failure()]))
        assert ctx.confidence == 0.0

    def test_custom_penalties(self) -> None:
        ctx = WorkflowContext("wf1", soft_fail_penalty=0.25, silent_fail_penalty=0.2)
        ctx.update(_make_result(passed=False, failures=[_soft_failure()]))
        assert ctx.confidence == pytest.approx(0.75)
        ctx.update(_make_result(passed=False, failures=[_silent_failure()]))
        assert ctx.confidence == pytest.approx(0.55)

    def test_history_records_each_step(self) -> None:
        ctx = WorkflowContext("wf1")
        ctx.update(_make_result(passed=True))
        ctx.update(_make_result(passed=False, failures=[_soft_failure()]))
        assert ctx.step_count == 2
        assert ctx.history[0].passed is True
        assert ctx.history[1].passed is False

    def test_history_returns_copy(self) -> None:
        ctx = WorkflowContext("wf1")
        ctx.update(_make_result())
        history = ctx.history
        history.clear()
        assert ctx.step_count == 1

    def test_to_dict_structure(self) -> None:
        ctx = WorkflowContext("wf1")
        ctx.update(_make_result())
        data = ctx.to_dict()
        assert data["workflow_id"] == "wf1"
        assert "confidence" in data
        assert "escalation_threshold" in data
        assert "threshold_breached" in data
        assert "step_count" in data
        assert "history" in data
        assert len(data["history"]) == 1

    def test_passing_step_keeps_confidence(self) -> None:
        ctx = WorkflowContext("wf1")
        ctx.update(_make_result(passed=True))
        assert ctx.confidence == 1.0

    def test_reset_restores_initial_confidence_and_clears_history(self) -> None:
        ctx = WorkflowContext("wf1", initial_confidence=0.8)
        ctx.update(_make_result(passed=False, failures=[_soft_failure()]))
        assert ctx.confidence == pytest.approx(0.65)
        assert ctx.step_count == 1

        ctx.reset()

        assert ctx.confidence == pytest.approx(0.8)
        assert ctx.step_count == 0
        assert ctx.history == []
        assert ctx.threshold_breached is False

    def test_concurrent_updates_do_not_corrupt_confidence(self) -> None:
        ctx = WorkflowContext("wf_concurrent", soft_fail_penalty=0.01)
        result = _make_result(passed=False, failures=[_soft_failure()])

        def do_updates() -> None:
            for _ in range(50):
                ctx.update(result)

        threads = [threading.Thread(target=do_updates) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert ctx.step_count == 200
        assert 0.0 <= ctx.confidence <= 1.0

    def test_concurrent_update_and_reset(self) -> None:
        ctx = WorkflowContext("wf_reset_race")
        result = _make_result(passed=False, failures=[_soft_failure()])

        errors: list[Exception] = []

        def do_updates() -> None:
            try:
                for _ in range(30):
                    ctx.update(result)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        def do_resets() -> None:
            try:
                for _ in range(10):
                    ctx.reset()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=do_updates) for _ in range(3)]
        threads += [threading.Thread(target=do_resets) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert 0.0 <= ctx.confidence <= 1.0


class TestStepRecord:
    def test_to_dict(self) -> None:
        record = StepRecord(
            step_index=0,
            contract_name="test",
            passed=False,
            confidence_before=1.0,
            confidence_after=0.85,
            penalty_applied=0.15,
            failure_modes=[FailureMode.SOFT_FAIL],
        )
        data = record.to_dict()
        assert data["step_index"] == 0
        assert data["contract_name"] == "test"
        assert data["passed"] is False
        assert data["confidence_before"] == 1.0
        assert data["confidence_after"] == 0.85
        assert data["penalty_applied"] == 0.15
        assert data["failure_modes"] == ["soft_fail"]
        assert "timestamp" in data
