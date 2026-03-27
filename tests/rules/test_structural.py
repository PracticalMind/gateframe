from pydantic import BaseModel

from gateframe.core.failure import FailureMode, FailureResult
from gateframe.rules.structural import StructuralRule


class _SampleOutput(BaseModel):
    name: str
    score: float


class TestStructuralRule:

    def _make_rule(self, **overrides: object) -> StructuralRule:
        defaults: dict = {"schema": _SampleOutput}
        defaults.update(overrides)
        return StructuralRule(**defaults)

    def test_valid_dict_passes(self) -> None:
        rule = self._make_rule()
        result = rule.validate({"name": "test", "score": 0.9})
        assert result is None

    def test_valid_model_instance_passes(self) -> None:
        rule = self._make_rule()
        output = _SampleOutput(name="test", score=0.9)
        assert rule.validate(output) is None

    def test_missing_field_returns_failure(self) -> None:
        rule = self._make_rule()
        result = rule.validate({"name": "test"})
        assert isinstance(result, FailureResult)
        assert result.failure_mode is FailureMode.HARD_FAIL
        assert "score" in result.message

    def test_wrong_type_returns_failure(self) -> None:
        rule = self._make_rule()
        result = rule.validate({"name": "test", "score": "not_a_float"})
        assert isinstance(result, FailureResult)
        assert "score" in result.message

    def test_non_dict_non_model_returns_failure(self) -> None:
        rule = self._make_rule()
        result = rule.validate("just a string")
        assert isinstance(result, FailureResult)
        assert "str" in result.message

    def test_default_name_from_schema(self) -> None:
        rule = self._make_rule()
        assert rule.name == "structural:_SampleOutput"

    def test_custom_name(self) -> None:
        rule = self._make_rule(name="my_rule")
        assert rule.name == "my_rule"

    def test_custom_failure_mode(self) -> None:
        rule = self._make_rule(failure_mode=FailureMode.SOFT_FAIL)
        result = rule.validate({"name": "test"})
        assert result is not None
        assert result.failure_mode is FailureMode.SOFT_FAIL

    def test_failure_context_has_validation_errors(self) -> None:
        rule = self._make_rule()
        result = rule.validate({"name": "test"})
        assert result is not None
        assert "validation_errors" in result.context

    def test_multiple_errors_reported(self) -> None:
        rule = self._make_rule()
        result = rule.validate({})
        assert result is not None
        assert "name" in result.message
        assert "score" in result.message
