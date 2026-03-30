from dataclasses import dataclass

import pytest

from gateframe.core.failure import FailureMode
from gateframe.rules.confidence import ConfidenceRule


class TestConfidenceRuleConstruction:
    def test_missing_both_args_raises(self) -> None:
        with pytest.raises(ValueError, match="requires either"):
            ConfidenceRule()

    def test_both_args_raises(self) -> None:
        with pytest.raises(ValueError, match="not both"):
            ConfidenceRule(field="confidence", check=lambda o, **c: True)

    def test_field_mode_constructs(self) -> None:
        rule = ConfidenceRule(field="confidence", minimum=0.7)
        assert rule.name == "confidence_check"

    def test_check_mode_constructs(self) -> None:
        rule = ConfidenceRule(check=lambda o, **c: True)
        assert rule.name == "confidence_check"


class TestConfidenceRuleThresholdMode:
    def test_above_minimum_passes(self) -> None:
        rule = ConfidenceRule(field="confidence", minimum=0.7)
        assert rule.validate({"confidence": 0.9}) is None

    def test_at_minimum_passes(self) -> None:
        rule = ConfidenceRule(field="confidence", minimum=0.7)
        assert rule.validate({"confidence": 0.7}) is None

    def test_below_minimum_fails(self) -> None:
        rule = ConfidenceRule(field="confidence", minimum=0.7)
        result = rule.validate({"confidence": 0.42})
        assert result is not None
        assert result.message == "Confidence 0.42 is below minimum threshold 0.7."

    def test_above_maximum_fails(self) -> None:
        rule = ConfidenceRule(field="confidence", maximum=0.9)
        result = rule.validate({"confidence": 0.95})
        assert result is not None
        assert result.message == "Confidence 0.95 exceeds maximum threshold 0.9."

    def test_at_maximum_passes(self) -> None:
        rule = ConfidenceRule(field="confidence", maximum=0.9)
        assert rule.validate({"confidence": 0.9}) is None

    def test_no_bounds_passes(self) -> None:
        rule = ConfidenceRule(field="confidence")
        assert rule.validate({"confidence": 0.5}) is None

    def test_missing_field_fails(self) -> None:
        rule = ConfidenceRule(field="confidence", minimum=0.7)
        result = rule.validate({"score": 0.9})
        assert result is not None
        assert "field 'confidence' not found in output" in result.message

    def test_non_numeric_field_fails(self) -> None:
        rule = ConfidenceRule(field="confidence", minimum=0.7)
        result = rule.validate({"confidence": "high"})
        assert result is not None
        assert "field 'confidence' is not numeric (got str)" in result.message

    def test_bool_treated_as_non_numeric(self) -> None:
        rule = ConfidenceRule(field="confidence", minimum=0.7)
        result = rule.validate({"confidence": True})
        assert result is not None
        assert "is not numeric" in result.message

    def test_object_attribute_access(self) -> None:
        @dataclass
        class Output:
            confidence: float

        rule = ConfidenceRule(field="confidence", minimum=0.6)
        assert rule.validate(Output(confidence=0.8)) is None

        result = rule.validate(Output(confidence=0.3))
        assert result is not None
        assert "below minimum threshold" in result.message

    def test_object_missing_attribute_fails(self) -> None:
        rule = ConfidenceRule(field="confidence", minimum=0.7)
        result = rule.validate(object())
        assert result is not None
        assert "not found in output" in result.message

    def test_default_failure_mode_is_soft_fail(self) -> None:
        rule = ConfidenceRule(field="confidence", minimum=0.7)
        result = rule.validate({"confidence": 0.1})
        assert result is not None
        assert result.failure_mode == FailureMode.SOFT_FAIL

    def test_custom_failure_mode(self) -> None:
        rule = ConfidenceRule(
            field="confidence",
            minimum=0.7,
            failure_mode=FailureMode.HARD_FAIL,
        )
        result = rule.validate({"confidence": 0.1})
        assert result is not None
        assert result.failure_mode == FailureMode.HARD_FAIL


class TestConfidenceRuleCallableMode:
    def test_check_passes(self) -> None:
        rule = ConfidenceRule(check=lambda o, **c: True)
        assert rule.validate({"confidence": 0.5}) is None

    def test_check_fails(self) -> None:
        rule = ConfidenceRule(check=lambda o, **c: False)
        result = rule.validate({"confidence": 0.5})
        assert result is not None
        assert result.failure_mode == FailureMode.SOFT_FAIL

    def test_exception_in_check(self) -> None:
        def bad_check(output: object, **ctx: object) -> bool:
            raise ValueError("calibration error")

        rule = ConfidenceRule(check=bad_check)
        result = rule.validate({})
        assert result is not None
        assert "raised an exception" in result.message
        assert result.context["exception_type"] == "ValueError"

    def test_context_forwarded(self) -> None:
        received: dict = {}

        def capture(output: object, **ctx: object) -> bool:
            received.update(ctx)
            return True

        rule = ConfidenceRule(check=capture)
        rule.validate({}, step=2, workflow_id="wf1")
        assert received["step"] == 2
        assert received["workflow_id"] == "wf1"

    def test_custom_failure_message(self) -> None:
        rule = ConfidenceRule(
            check=lambda o, **c: False,
            failure_message="Confidence calibration failed.",
        )
        result = rule.validate({})
        assert result is not None
        assert result.message == "Confidence calibration failed."

    def test_default_name(self) -> None:
        rule = ConfidenceRule(check=lambda o, **c: True)
        assert rule.name == "confidence_check"

    def test_custom_name(self) -> None:
        rule = ConfidenceRule(check=lambda o, **c: True, name="calibration_check")
        assert rule.name == "calibration_check"
