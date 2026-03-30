from __future__ import annotations

import json
from typing import Any

from gateframe.core.contract import ValidationContract, ValidationResult


def _require_langchain() -> None:
    try:
        import langchain  # noqa: F401
    except ImportError:
        raise ImportError(
            "langchain is required for this integration. "
            "Install it with: pip install gateframe[langchain]"
        ) from None


def extract_text(response: Any, output_key: str = "output") -> str:  # noqa: ANN401
    """Extract text from a LangChain response (str, AIMessage, or dict)."""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        if output_key not in response:
            raise ValueError(f"Key '{output_key}' not found in response dict.")
        value = response[output_key]
        if not isinstance(value, str):
            raise ValueError(f"Expected str at key '{output_key}', got {type(value).__name__}.")
        return value
    content = getattr(response, "content", None)
    if content is not None:
        if not isinstance(content, str):
            raise ValueError(f"Expected str content, got {type(content).__name__}.")
        return content
    raise ValueError(f"Cannot extract text from response of type {type(response).__name__}.")


def extract_json(response: Any, output_key: str = "output") -> dict[str, Any]:  # noqa: ANN401
    """Extract text, then parse as JSON. Raises ValueError on failure."""
    text = extract_text(response, output_key=output_key)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Failed to parse response as JSON: {exc}. Raw text: {text[:200]}"
        ) from exc
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object, got {type(data).__name__}.")
    return data


def extract_metadata(response: Any) -> dict[str, Any]:  # noqa: ANN401
    """Extract available metadata from a LangChain response. Omits None values."""
    meta: dict[str, Any] = {}

    if isinstance(response, str):
        return meta

    response_metadata = getattr(response, "response_metadata", None)
    if isinstance(response_metadata, dict):
        for k, v in response_metadata.items():
            if v is not None:
                meta[k] = v

    type_val = getattr(response, "type", None)
    if type_val is not None:
        meta["type"] = type_val

    source_documents = getattr(response, "source_documents", None)
    if source_documents is not None:
        meta["source_document_count"] = len(source_documents)

    return meta


class LangChainValidator:
    def __init__(
        self,
        contract: ValidationContract,
        *,
        parse_json: bool = False,
        output_key: str = "output",
    ) -> None:
        self._contract = contract
        self._parse_json = parse_json
        self._output_key = output_key

    def validate(self, response: Any, **context: Any) -> ValidationResult:  # noqa: ANN401
        output = (
            extract_json(response, output_key=self._output_key)
            if self._parse_json
            else extract_text(response, output_key=self._output_key)
        )
        metadata = extract_metadata(response)
        merged = {**metadata, **context}
        return self._contract.validate(output, **merged)
