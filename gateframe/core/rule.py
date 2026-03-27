from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from gateframe.core.failure import FailureResult


class Rule(ABC):
    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description

    @abstractmethod
    def validate(self, output: Any, **context: Any) -> FailureResult | None:  # noqa: ANN401
        ...
