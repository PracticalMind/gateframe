from __future__ import annotations

import json
from typing import Any

from gateframe.core.contract import ValidationContract, ValidationResult


def _require_anthropic() -> None:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        raise ImportError(
            "anthropic SDK is required for this integration. "
            "Install it with: pip install gateframe[anthropic]"
        ) from None


def extract_text(message: Any) -> str:  # noqa: ANN401
    """Extract text content from an Anthropic Message. Concatenates all text blocks."""
    content = getattr(message, "content", None)
    if content is None:
        raise ValueError("Message has no content attribute.")

    texts = []
    for block in content:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            texts.append(getattr(block, "text", ""))

    if not texts:
        raise ValueError("No text blocks found in message content.")
    return "".join(texts)


def extract_json(message: Any) -> dict[str, Any]:  # noqa: ANN401
    """Extract text, then parse as JSON. Raises ValueError with raw text on failure."""
    text = extract_text(message)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Failed to parse response as JSON: {exc}. Raw text: {text[:200]}"
        ) from exc
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object, got {type(data).__name__}.")
    return data


def extract_metadata(message: Any) -> dict[str, Any]:  # noqa: ANN401
    """Extract model metadata from an Anthropic Message."""
    meta: dict[str, Any] = {
        "model": getattr(message, "model", None),
        "stop_reason": getattr(message, "stop_reason", None),
    }
    usage = getattr(message, "usage", None)
    if usage:
        meta["input_tokens"] = getattr(usage, "input_tokens", None)
        meta["output_tokens"] = getattr(usage, "output_tokens", None)
    return meta


class AnthropicValidator:
    def __init__(
        self,
        contract: ValidationContract,
        *,
        parse_json: bool = False,
    ) -> None:
        self._contract = contract
        self._parse_json = parse_json

    def validate(self, message: Any, **context: Any) -> ValidationResult:  # noqa: ANN401
        output = extract_json(message) if self._parse_json else extract_text(message)

        metadata = extract_metadata(message)
        merged = {**metadata, **context}
        return self._contract.validate(output, **merged)
