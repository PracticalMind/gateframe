from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FailureMode(Enum):
    HARD_FAIL = "hard_fail"
    SOFT_FAIL = "soft_fail"
    RETRY = "retry"
    SILENT_FAIL = "silent_fail"


class FailureResult(BaseModel):
    rule_name: str
    rule_description: str = ""
    failure_mode: FailureMode
    message: str
    context: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    model_config = {"frozen": True}
