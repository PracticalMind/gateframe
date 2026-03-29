from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from gateframe.core.context import WorkflowContext
    from gateframe.core.contract import ValidationResult

logger = structlog.get_logger()


class EscalationRoute(Enum):
    HUMAN_REVIEW = "human_review"
    FALLBACK_MODEL = "fallback_model"
    SAFE_DEFAULT = "safe_default"
    ABORT = "abort"
    FLAG_AND_CONTINUE = "flag_and_continue"


class EscalationResult:
    __slots__ = ("route", "reason", "context")

    def __init__(self, route: EscalationRoute, reason: str, context: dict[str, Any]) -> None:
        self.route = route
        self.reason = reason
        self.context = context

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route.value,
            "reason": self.reason,
            "context": self.context,
        }


class EscalationRouter:
    def __init__(
        self,
        on_hard_fail: EscalationRoute = EscalationRoute.ABORT,
        on_soft_fail: EscalationRoute = EscalationRoute.FLAG_AND_CONTINUE,
        on_threshold_breach: EscalationRoute = EscalationRoute.HUMAN_REVIEW,
    ) -> None:
        self.on_hard_fail = on_hard_fail
        self.on_soft_fail = on_soft_fail
        self.on_threshold_breach = on_threshold_breach

    def route(self, result: ValidationResult) -> EscalationResult | None:
        if result.passed:
            return None

        if result.has_hard_fail:
            logger.warning(
                "escalation_triggered",
                route=self.on_hard_fail.value,
                reason="hard_fail",
                contract=result.contract_name,
            )
            return EscalationResult(
                route=self.on_hard_fail,
                reason="Validation produced HARD_FAIL.",
                context={"contract": result.contract_name, "failures": result.rules_failed},
            )

        if result.has_soft_fail:
            if self.on_soft_fail is EscalationRoute.FLAG_AND_CONTINUE:
                logger.info("soft_fail_flagged", contract=result.contract_name)
                return None
            logger.warning(
                "escalation_triggered",
                route=self.on_soft_fail.value,
                reason="soft_fail",
                contract=result.contract_name,
            )
            return EscalationResult(
                route=self.on_soft_fail,
                reason="Validation produced SOFT_FAIL with escalation configured.",
                context={"contract": result.contract_name, "failures": result.rules_failed},
            )

        return None

    def route_threshold_breach(self, ctx: WorkflowContext) -> EscalationResult | None:
        if not ctx.threshold_breached:
            return None

        logger.warning(
            "threshold_breach_escalation",
            workflow_id=ctx.workflow_id,
            confidence=ctx.confidence,
            threshold=ctx.escalation_threshold,
        )
        return EscalationResult(
            route=self.on_threshold_breach,
            reason=(
                f"Confidence {ctx.confidence:.2f} dropped below "
                f"threshold {ctx.escalation_threshold}."
            ),
            context=ctx.to_dict(),
        )
