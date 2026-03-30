from dataclasses import dataclass, field
from typing import Any

import pytest
from pydantic import BaseModel

from gateframe.core.contract import ValidationContract
from gateframe.integrations.langchain import (
    LangChainValidator,
    extract_json,
    extract_metadata,
    extract_text,
)
from gateframe.rules.structural import StructuralRule


@dataclass
class MockAIMessage:
    content: str = "LangChain response"
    type: str = "ai"
    response_metadata: dict = field(default_factory=dict)


@dataclass
class MockAIMessageWithDocs:
    content: str = "answer"
    type: str = "ai"
    response_metadata: dict = field(default_factory=dict)
    source_documents: list = field(default_factory=list)


class TestExtractText:
    def test_plain_string(self) -> None:
        assert extract_text("hello") == "hello"

    def test_ai_message(self) -> None:
        assert extract_text(MockAIMessage(content="response text")) == "response text"

    def test_dict_default_key(self) -> None:
        assert extract_text({"output": "chain result"}) == "chain result"

    def test_dict_custom_key(self) -> None:
        assert extract_text({"result": "value"}, output_key="result") == "value"

    def test_dict_missing_key_raises(self) -> None:
        with pytest.raises(ValueError, match="Key 'output' not found"):
            extract_text({"answer": "x"})

    def test_dict_non_string_value_raises(self) -> None:
        with pytest.raises(ValueError, match="Expected str"):
            extract_text({"output": 42})

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot extract text"):
            extract_text(12345)


class TestExtractJson:
    def test_valid_json_from_string(self) -> None:
        assert extract_json('{"key": "value"}') == {"key": "value"}

    def test_valid_json_from_ai_message(self) -> None:
        msg = MockAIMessage(content='{"result": 1}')
        assert extract_json(msg) == {"result": 1}

    def test_valid_json_from_dict(self) -> None:
        assert extract_json({"output": '{"x": 2}'}) == {"x": 2}

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(ValueError, match="Failed to parse"):
            extract_json("not json")

    def test_non_dict_json_raises(self) -> None:
        with pytest.raises(ValueError, match="Expected JSON object"):
            extract_json("[1, 2, 3]")


class TestExtractMetadata:
    def test_empty_for_plain_string(self) -> None:
        assert extract_metadata("hello") == {}

    def test_ai_message_response_metadata_merged(self) -> None:
        msg = MockAIMessage(response_metadata={"model_name": "gpt-4", "finish_reason": "stop"})
        meta = extract_metadata(msg)
        assert meta["model_name"] == "gpt-4"
        assert meta["finish_reason"] == "stop"

    def test_type_included(self) -> None:
        msg = MockAIMessage(type="ai")
        meta = extract_metadata(msg)
        assert meta["type"] == "ai"

    def test_source_document_count(self) -> None:
        msg = MockAIMessageWithDocs(source_documents=["doc1", "doc2", "doc3"])
        meta = extract_metadata(msg)
        assert meta["source_document_count"] == 3

    def test_none_values_omitted(self) -> None:
        msg = MockAIMessage(response_metadata={"model_name": None, "finish_reason": "stop"})
        meta = extract_metadata(msg)
        assert "model_name" not in meta
        assert meta["finish_reason"] == "stop"

    def test_missing_response_metadata_omitted(self) -> None:
        @dataclass
        class MinimalMsg:
            content: str = "hi"

        meta = extract_metadata(MinimalMsg())
        assert "model_name" not in meta


class TestLangChainValidator:
    def test_text_mode(self) -> None:
        class Output(BaseModel):
            pass

        contract = ValidationContract("test", [StructuralRule(schema=Output)])
        validator = LangChainValidator(contract, parse_json=False)
        result = validator.validate("plain text")
        assert result.passed is False

    def test_json_mode(self) -> None:
        class Output(BaseModel):
            key: str

        contract = ValidationContract("test", [StructuralRule(schema=Output)])
        validator = LangChainValidator(contract, parse_json=True)
        result = validator.validate('{"key": "value"}')
        assert result.passed is True

    def test_metadata_in_context(self) -> None:
        received_ctx: dict = {}

        from gateframe.core.failure import FailureResult
        from gateframe.core.rule import Rule

        class CtxCapture(Rule):
            def validate(self, output: Any, **context: Any) -> FailureResult | None:
                received_ctx.update(context)
                return None

        contract = ValidationContract("test", [CtxCapture("capture")])
        validator = LangChainValidator(contract)
        msg = MockAIMessage(content="hello", type="ai")
        validator.validate(msg)
        assert received_ctx.get("type") == "ai"

    def test_custom_output_key(self) -> None:
        class Output(BaseModel):
            answer: str

        contract = ValidationContract("test", [StructuralRule(schema=Output)])
        validator = LangChainValidator(contract, parse_json=True, output_key="result")
        result = validator.validate({"result": '{"answer": "yes"}'})
        assert result.passed is True
