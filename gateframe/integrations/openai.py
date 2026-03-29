from __future__ import annotations

import json
from typing import Any

from gateframe.core.contract import ValidationContract, ValidationResult


def _require_openai() -> None:
    try:
        import openai  # noqa: F401
    except ImportError:
        raise ImportError(
            "openai SDK is required for this integration. "
            "Install it with: pip install gateframe[openai]"
        ) from None


def extract_text(completion: Any, choice_index: int = 0) -> str:  # noqa: ANN401
    """Extract message content from an OpenAI ChatCompletion response."""
    choices = getattr(completion, "choices", None)
    if not choices or choice_index >= len(choices):
        raise ValueError(
            f"No choice at index {choice_index}. "
            f"Response has {len(choices) if choices else 0} choices."
        )
    message = choices[choice_index].message
    content = getattr(message, "content", None)
    if content is None:
        raise ValueError("Choice message has no content (content is None).")
    return content


def extract_json(completion: Any, choice_index: int = 0) -> dict[str, Any]:  # noqa: ANN401
    """Extract text, then parse as JSON. Raises ValueError with raw text on failure."""
    text = extract_text(completion, choice_index)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Failed to parse response as JSON: {exc}. Raw text: {text[:200]}"
        ) from exc
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object, got {type(data).__name__}.")
    return data


def extract_metadata(completion: Any) -> dict[str, Any]:  # noqa: ANN401
    """Extract model metadata from a ChatCompletion response."""
    meta: dict[str, Any] = {"model": getattr(completion, "model", None)}
    choices = getattr(completion, "choices", [])
    if choices:
        meta["finish_reason"] = getattr(choices[0], "finish_reason", None)
    usage = getattr(completion, "usage", None)
    if usage:
        meta["prompt_tokens"] = getattr(usage, "prompt_tokens", None)
        meta["completion_tokens"] = getattr(usage, "completion_tokens", None)
        meta["total_tokens"] = getattr(usage, "total_tokens", None)
    return meta


class OpenAIValidator:
    def __init__(
        self,
        contract: ValidationContract,
        *,
        parse_json: bool = False,
        choice_index: int = 0,
    ) -> None:
        self._contract = contract
        self._parse_json = parse_json
        self._choice_index = choice_index

    def validate(self, completion: Any, **context: Any) -> ValidationResult:  # noqa: ANN401
        if self._parse_json:
            output = extract_json(completion, self._choice_index)
        else:
            output = extract_text(completion, self._choice_index)

        metadata = extract_metadata(completion)
        merged = {**metadata, **context}
        return self._contract.validate(output, **merged)
