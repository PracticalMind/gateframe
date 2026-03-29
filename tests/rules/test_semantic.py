from gateframe.core.failure import FailureMode
from gateframe.rules.semantic import LlmJudge, SemanticRule


class TestSemanticRule:
    def test_passing_check_returns_none(self) -> None:
        rule = SemanticRule(check=lambda output, **ctx: True, name="always_pass")
        assert rule.validate({"key": "value"}) is None

    def test_failing_check_returns_failure(self) -> None:
        rule = SemanticRule(check=lambda output, **ctx: False, name="always_fail")
        result = rule.validate({"key": "value"})
        assert result is not None
        assert result.rule_name == "always_fail"

    def test_custom_failure_message(self) -> None:
        rule = SemanticRule(
            check=lambda output, **ctx: False,
            name="msg_test",
            failure_message="Recommendation too short.",
        )
        result = rule.validate({})
        assert result is not None
        assert result.message == "Recommendation too short."

    def test_default_failure_mode_is_soft_fail(self) -> None:
        rule = SemanticRule(check=lambda output, **ctx: False, name="mode_test")
        result = rule.validate({})
        assert result is not None
        assert result.failure_mode is FailureMode.SOFT_FAIL

    def test_custom_failure_mode(self) -> None:
        rule = SemanticRule(
            check=lambda output, **ctx: False,
            name="mode_test",
            failure_mode=FailureMode.HARD_FAIL,
        )
        result = rule.validate({})
        assert result is not None
        assert result.failure_mode is FailureMode.HARD_FAIL

    def test_check_receives_context_kwargs(self) -> None:
        def check(output: object, **ctx: object) -> bool:
            return ctx.get("role") == "admin"

        rule = SemanticRule(check=check, name="ctx_test")
        assert rule.validate({}, role="admin") is None
        assert rule.validate({}, role="user") is not None

    def test_check_exception_returns_failure(self) -> None:
        def bad_check(output: object, **ctx: object) -> bool:
            raise ValueError("broken")

        rule = SemanticRule(check=bad_check, name="exc_test")
        result = rule.validate({})
        assert result is not None
        assert "exception" in result.message

    def test_exception_failure_contains_details(self) -> None:
        def bad_check(output: object, **ctx: object) -> bool:
            raise TypeError("wrong type")

        rule = SemanticRule(check=bad_check, name="exc_detail")
        result = rule.validate({})
        assert result is not None
        assert result.context["exception_type"] == "TypeError"
        assert result.context["exception_message"] == "wrong type"

    def test_heuristic_lambda_check(self) -> None:
        rule = SemanticRule(
            check=lambda output, **ctx: len(output.get("recommendation", "")) > 10,
            name="length_check",
            failure_message="Recommendation too short.",
        )
        assert rule.validate({"recommendation": "Escalate to senior engineer"}) is None
        result = rule.validate({"recommendation": "OK"})
        assert result is not None
        assert result.message == "Recommendation too short."

    def test_default_name(self) -> None:
        rule = SemanticRule(check=lambda output, **ctx: True)
        assert rule.name == "semantic_check"

    def test_description_stored(self) -> None:
        rule = SemanticRule(
            check=lambda output, **ctx: True,
            name="desc_test",
            description="Checks alignment",
        )
        assert rule.description == "Checks alignment"


class TestLlmJudge:
    def test_passing_response_detected(self) -> None:
        judge = LlmJudge(
            prompt_template="Evaluate: {output}",
            llm_call=lambda prompt: "PASS",
        )
        assert judge({"key": "value"}) is True

    def test_failing_response_detected(self) -> None:
        judge = LlmJudge(
            prompt_template="Evaluate: {output}",
            llm_call=lambda prompt: "FAIL",
        )
        assert judge({"key": "value"}) is False

    def test_custom_passing_response(self) -> None:
        judge = LlmJudge(
            prompt_template="Check: {output}",
            llm_call=lambda prompt: "APPROVED",
            passing_response="APPROVED",
        )
        assert judge({}) is True

    def test_prompt_template_formatted(self) -> None:
        captured: list[str] = []

        def mock_llm(prompt: str) -> str:
            captured.append(prompt)
            return "PASS"

        judge = LlmJudge(
            prompt_template="Output: {output}, Role: {role}",
            llm_call=mock_llm,
        )
        judge({"data": 1}, role="admin")
        assert "Role: admin" in captured[0]

    def test_case_insensitive_matching(self) -> None:
        judge = LlmJudge(
            prompt_template="{output}",
            llm_call=lambda prompt: "  pass  ",
        )
        assert judge({}) is True

    def test_partial_match(self) -> None:
        judge = LlmJudge(
            prompt_template="{output}",
            llm_call=lambda prompt: "The result is PASS based on criteria",
        )
        assert judge({}) is True
