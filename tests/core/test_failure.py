from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from gateframe.core.failure import FailureMode, FailureResult


class TestFailureMode:
    def test_has_four_members(self) -> None:
        assert len(FailureMode) == 4

    def test_hard_fail_value(self) -> None:
        assert FailureMode.HARD_FAIL.value == "hard_fail"

    def test_soft_fail_value(self) -> None:
        assert FailureMode.SOFT_FAIL.value == "soft_fail"

    def test_retry_value(self) -> None:
        assert FailureMode.RETRY.value == "retry"

    def test_silent_fail_value(self) -> None:
        assert FailureMode.SILENT_FAIL.value == "silent_fail"

    def test_constructible_from_string(self) -> None:
        assert FailureMode("hard_fail") is FailureMode.HARD_FAIL

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            FailureMode("invalid")


class TestFailureResult:
    def _make_result(self, **overrides: object) -> FailureResult:
        defaults = {
            "rule_name": "test_rule",
            "failure_mode": FailureMode.HARD_FAIL,
            "message": "Field 'name' expected type str, got int.",
        }
        defaults.update(overrides)
        return FailureResult(**defaults)  # type: ignore[arg-type]

    def test_required_fields(self) -> None:
        result = self._make_result()
        assert result.rule_name == "test_rule"
        assert result.failure_mode is FailureMode.HARD_FAIL
        assert result.message == "Field 'name' expected type str, got int."

    def test_default_description_is_empty(self) -> None:
        result = self._make_result()
        assert result.rule_description == ""

    def test_custom_description(self) -> None:
        result = self._make_result(rule_description="Checks name is a string")
        assert result.rule_description == "Checks name is a string"

    def test_default_context_is_empty_dict(self) -> None:
        result = self._make_result()
        assert result.context == {}

    def test_custom_context(self) -> None:
        ctx = {"field": "name", "expected": "str", "got": "int"}
        result = self._make_result(context=ctx)
        assert result.context == ctx

    def test_timestamp_is_auto_populated(self) -> None:
        before = datetime.now(timezone.utc)
        result = self._make_result()
        after = datetime.now(timezone.utc)
        assert before <= result.timestamp <= after

    def test_timestamp_is_utc(self) -> None:
        result = self._make_result()
        assert result.timestamp.tzinfo is not None

    def test_is_frozen(self) -> None:
        result = self._make_result()
        with pytest.raises(ValidationError):
            result.rule_name = "changed"  # type: ignore[misc]

    def test_missing_rule_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            FailureResult(
                failure_mode=FailureMode.HARD_FAIL,
                message="something failed",
            )  # type: ignore[call-arg]

    def test_missing_message_raises(self) -> None:
        with pytest.raises(ValidationError):
            FailureResult(
                rule_name="test",
                failure_mode=FailureMode.HARD_FAIL,
            )  # type: ignore[call-arg]

    def test_serialization_roundtrip(self) -> None:
        result = self._make_result(context={"key": "value"})
        data = result.model_dump()
        restored = FailureResult(**data)
        assert restored == result
