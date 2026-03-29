from dataclasses import dataclass, field

import pytest
from pydantic import BaseModel

from gateframe.core.contract import ValidationContract
from gateframe.integrations.litellm import (
    LiteLLMValidator,
    extract_json,
    extract_metadata,
    extract_text,
)
from gateframe.rules.structural import StructuralRule


@dataclass
class MockUsage:
    prompt_tokens: int = 15
    completion_tokens: int = 25
    total_tokens: int = 40


@dataclass
class MockMessage:
    content: str | None = "LiteLLM response"
    role: str = "assistant"


@dataclass
class MockChoice:
    message: MockMessage = field(default_factory=MockMessage)
    finish_reason: str = "stop"
    index: int = 0


@dataclass
class MockResponse:
    choices: list[MockChoice] = field(default_factory=lambda: [MockChoice()])
    model: str = "gpt-4"
    usage: MockUsage = field(default_factory=MockUsage)


class TestExtractText:
    def test_extracts_content(self) -> None:
        assert extract_text(MockResponse()) == "LiteLLM response"

    def test_no_choices_raises(self) -> None:
        with pytest.raises(ValueError, match="No choice at index"):
            extract_text(MockResponse(choices=[]))


class TestExtractJson:
    def test_valid_json(self) -> None:
        resp = MockResponse(choices=[MockChoice(message=MockMessage(content='{"result": 42}'))])
        assert extract_json(resp) == {"result": 42}

    def test_invalid_json_raises(self) -> None:
        resp = MockResponse(choices=[MockChoice(message=MockMessage(content="bad"))])
        with pytest.raises(ValueError, match="Failed to parse"):
            extract_json(resp)


class TestExtractMetadata:
    def test_metadata_fields(self) -> None:
        meta = extract_metadata(MockResponse())
        assert meta["model"] == "gpt-4"
        assert meta["prompt_tokens"] == 15
        assert meta["total_tokens"] == 40


class TestLiteLLMValidator:
    def test_validate_json(self) -> None:
        class Output(BaseModel):
            result: int

        contract = ValidationContract("test", [StructuralRule(schema=Output)])
        validator = LiteLLMValidator(contract, parse_json=True)
        resp = MockResponse(choices=[MockChoice(message=MockMessage(content='{"result": 42}'))])
        result = validator.validate(resp)
        assert result.passed is True
