from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from gateframe.core.failure import FailureMode, FailureResult
from gateframe.core.rule import Rule


class SemanticRule(Rule):
    def __init__(
        self,
        check: Callable[..., bool],
        name: str = "semantic_check",
        description: str = "",
        failure_mode: FailureMode = FailureMode.SOFT_FAIL,
        failure_message: str = "",
    ) -> None:
        super().__init__(name, description)
        self._check = check
        self.failure_mode = failure_mode
        self._failure_message = failure_message

    def validate(self, output: Any, **context: Any) -> FailureResult | None:  # noqa: ANN401
        try:
            passed = self._check(output, **context)
        except Exception as exc:
            return FailureResult(
                rule_name=self.name,
                rule_description=self.description,
                failure_mode=self.failure_mode,
                message=f"{self.name} raised an exception: {exc}",
                context={"exception_type": type(exc).__name__, "exception_message": str(exc)},
            )

        if passed:
            return None

        message = self._failure_message or f"{self.name} failed: semantic check returned False."
        return FailureResult(
            rule_name=self.name,
            rule_description=self.description,
            failure_mode=self.failure_mode,
            message=message,
        )


class LlmJudge:
    """EXPENSIVE: Each call invokes the provided LLM function.
    The caller supplies the actual LLM call -- gateframe does not import any LLM SDK.

    Set ``cache=True`` to memoize results keyed on the rendered prompt.  This avoids
    redundant LLM calls when the same output+context is validated more than once within
    the lifetime of the judge instance (e.g. retry loops, multi-step pipelines).
    ``max_cache_size`` caps the in-memory LRU store; the oldest entry is evicted when
    the limit is reached.
    """

    def __init__(
        self,
        prompt_template: str,
        llm_call: Callable[[str], str],
        passing_response: str = "PASS",
        *,
        cache: bool = False,
        max_cache_size: int = 256,
    ) -> None:
        self._prompt_template = prompt_template
        self._llm_call = llm_call
        self._passing_response = passing_response
        self._cache: OrderedDict[str, bool] | None = OrderedDict() if cache else None
        self._max_cache_size = max_cache_size

    def __call__(self, output: Any, **context: Any) -> bool:  # noqa: ANN401
        prompt = self._prompt_template.format(output=output, **context)

        if self._cache is not None and prompt in self._cache:
            self._cache.move_to_end(prompt)
            return self._cache[prompt]

        result = self._passing_response.lower() in self._llm_call(prompt).strip().lower()

        if self._cache is not None:
            if len(self._cache) >= self._max_cache_size:
                self._cache.popitem(last=False)
            self._cache[prompt] = result

        return result

    def cache_clear(self) -> None:
        """Evict all cached prompt results."""
        if self._cache is not None:
            self._cache.clear()

    @property
    def cache_size(self) -> int:
        """Number of cached entries (0 when caching is disabled)."""
        return len(self._cache) if self._cache is not None else 0
