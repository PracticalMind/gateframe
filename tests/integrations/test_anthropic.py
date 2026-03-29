from dataclasses import dataclass, field

import pytest
from pydantic import BaseModel

from gateframe.core.contract import ValidationContract
from gateframe.integrations.anthropic import (
    AnthropicValidator,
    extract_json,
    extract_metadata,
    extract_text,
)
from gateframe.rules.structural import StructuralRule


@dataclass
class MockTextBlock:
    type: str = "text"
    text: str = "Hello world"


@dataclass
class MockToolBlock:
    type: str = "tool_use"
    id: str = "tool_1"
    name: str = "my_tool"


@dataclass
class MockUsage:
    input_tokens: int = 100
    output_tokens: int = 50


@dataclass
class MockMessage:
    content: list = field(default_factory=lambda: [MockTextBlock()])
    model: str = "claude-sonnet-4-20250514"
    stop_reason: str = "end_turn"
    usage: MockUsage = field(default_factory=MockUsage)


class TestExtractText:
    def test_extracts_text_blocks(self) -> None:
        assert extract_text(MockMessage()) == "Hello world"

    def test_concatenates_multiple_text_blocks(self) -> None:
        msg = MockMessage(content=[MockTextBlock(text="Hello "), MockTextBlock(text="world")])
        assert extract_text(msg) == "Hello world"

    def test_skips_non_text_blocks(self) -> None:
        msg = MockMessage(content=[MockToolBlock(), MockTextBlock(text="Hello")])
        assert extract_text(msg) == "Hello"

    def test_no_text_blocks_raises(self) -> None:
        msg = MockMessage(content=[MockToolBlock()])
        with pytest.raises(ValueError, match="No text blocks"):
            extract_text(msg)

    def test_no_content_raises(self) -> None:
        msg = MockMessage(content=None)
        with pytest.raises(ValueError, match="no content"):
            extract_text(msg)


class TestExtractJson:
    def test_valid_json(self) -> None:
        msg = MockMessage(content=[MockTextBlock(text='{"key": "value"}')])
        assert extract_json(msg) == {"key": "value"}

    def test_invalid_json_raises(self) -> None:
        msg = MockMessage(content=[MockTextBlock(text="not json")])
        with pytest.raises(ValueError, match="Failed to parse"):
            extract_json(msg)


class TestExtractMetadata:
    def test_metadata_fields(self) -> None:
        meta = extract_metadata(MockMessage())
        assert meta["model"] == "claude-sonnet-4-20250514"
        assert meta["stop_reason"] == "end_turn"
        assert meta["input_tokens"] == 100
        assert meta["output_tokens"] == 50


class TestAnthropicValidator:
    def test_validate_json(self) -> None:
        class JsonOutput(BaseModel):
            key: str

        rule = StructuralRule(schema=JsonOutput)
        contract = ValidationContract("test", [rule])
        validator = AnthropicValidator(contract, parse_json=True)
        msg = MockMessage(content=[MockTextBlock(text='{"key": "value"}')])
        result = validator.validate(msg)
        assert result.passed is True
