from dataclasses import dataclass, field

import pytest
from pydantic import BaseModel

from gateframe.core.contract import ValidationContract
from gateframe.core.failure import FailureMode
from gateframe.integrations.openai import (
    OpenAIValidator,
    extract_json,
    extract_metadata,
    extract_text,
)
from gateframe.rules.structural import StructuralRule


@dataclass
class MockUsage:
    prompt_tokens: int = 10
    completion_tokens: int = 20
    total_tokens: int = 30


@dataclass
class MockMessage:
    content: str | None = "Hello world"
    role: str = "assistant"


@dataclass
class MockChoice:
    message: MockMessage = field(default_factory=MockMessage)
    finish_reason: str = "stop"
    index: int = 0


@dataclass
class MockCompletion:
    choices: list[MockChoice] = field(default_factory=lambda: [MockChoice()])
    model: str = "gpt-4"
    usage: MockUsage = field(default_factory=MockUsage)


class TestExtractText:
    def test_extracts_content(self) -> None:
        assert extract_text(MockCompletion()) == "Hello world"

    def test_no_choices_raises(self) -> None:
        completion = MockCompletion(choices=[])
        with pytest.raises(ValueError, match="No choice at index"):
            extract_text(completion)

    def test_none_content_raises(self) -> None:
        completion = MockCompletion(choices=[MockChoice(message=MockMessage(content=None))])
        with pytest.raises(ValueError, match="content is None"):
            extract_text(completion)


class TestExtractJson:
    def test_valid_json(self) -> None:
        completion = MockCompletion(
            choices=[MockChoice(message=MockMessage(content='{"key": "value"}'))]
        )
        assert extract_json(completion) == {"key": "value"}

    def test_invalid_json_raises(self) -> None:
        completion = MockCompletion(choices=[MockChoice(message=MockMessage(content="not json"))])
        with pytest.raises(ValueError, match="Failed to parse"):
            extract_json(completion)


class TestExtractMetadata:
    def test_metadata_fields(self) -> None:
        meta = extract_metadata(MockCompletion())
        assert meta["model"] == "gpt-4"
        assert meta["finish_reason"] == "stop"
        assert meta["prompt_tokens"] == 10
        assert meta["completion_tokens"] == 20
        assert meta["total_tokens"] == 30


class TestOpenAIValidator:
    def test_validate_text(self) -> None:
        class TextOutput(BaseModel):
            pass

        rule = StructuralRule(schema=TextOutput, failure_mode=FailureMode.HARD_FAIL)
        contract = ValidationContract("test", [rule])
        validator = OpenAIValidator(contract, parse_json=False)
        # Text output won't match a Pydantic model, so this fails
        result = validator.validate(MockCompletion())
        assert result.passed is False

    def test_validate_json(self) -> None:
        class JsonOutput(BaseModel):
            key: str

        rule = StructuralRule(schema=JsonOutput)
        contract = ValidationContract("test", [rule])
        validator = OpenAIValidator(contract, parse_json=True)
        completion = MockCompletion(
            choices=[MockChoice(message=MockMessage(content='{"key": "value"}'))]
        )
        result = validator.validate(completion)
        assert result.passed is True

    def test_metadata_in_context(self) -> None:
        received_ctx: dict = {}

        from typing import Any

        from gateframe.core.failure import FailureResult
        from gateframe.core.rule import Rule

        class CtxCapture(Rule):
            def validate(self, output: Any, **context: Any) -> FailureResult | None:
                received_ctx.update(context)
                return None

        contract = ValidationContract("test", [CtxCapture("capture")])
        validator = OpenAIValidator(contract)
        validator.validate(MockCompletion())
        assert received_ctx["model"] == "gpt-4"
