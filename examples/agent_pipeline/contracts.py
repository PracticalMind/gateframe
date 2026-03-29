from gateframe.core.contract import ValidationContract
from gateframe.core.escalation import EscalationRoute
from gateframe.core.failure import FailureMode
from gateframe.rules.semantic import SemanticRule
from gateframe.rules.structural import StructuralRule

from .models import ActionPlanOutput, ClassificationOutput, ExecutionOutput, SummaryOutput

classification_contract = ValidationContract(
    name="classification",
    rules=[
        StructuralRule(schema=ClassificationOutput),
        SemanticRule(
            check=lambda output, **ctx: output.get("confidence", 0) >= 0.5,
            name="minimum_confidence",
            description="Classification confidence must be at least 0.5",
            failure_mode=FailureMode.SOFT_FAIL,
            failure_message="Classification confidence below 0.5 threshold.",
        ),
    ],
    on_hard_fail=EscalationRoute.ABORT,
    on_soft_fail=EscalationRoute.FLAG_AND_CONTINUE,
)

action_plan_contract = ValidationContract(
    name="action_plan",
    rules=[
        StructuralRule(schema=ActionPlanOutput),
        SemanticRule(
            check=lambda output, **ctx: len(output.get("steps", [])) > 0,
            name="has_steps",
            description="Action plan must have at least one step",
            failure_mode=FailureMode.HARD_FAIL,
            failure_message="Action plan has no steps.",
        ),
        SemanticRule(
            check=lambda output, **ctx: (
                output.get("requires_approval", False)
                if output.get("estimated_risk") == "high"
                else True
            ),
            name="high_risk_needs_approval",
            description="High risk actions must require approval",
            failure_mode=FailureMode.SOFT_FAIL,
            failure_message="High risk plan does not require approval.",
        ),
    ],
    on_hard_fail=EscalationRoute.HUMAN_REVIEW,
    on_soft_fail=EscalationRoute.FLAG_AND_CONTINUE,
)

execution_contract = ValidationContract(
    name="execution",
    rules=[
        StructuralRule(schema=ExecutionOutput),
        SemanticRule(
            check=lambda output, **ctx: (
                output.get("success", False) or len(output.get("details", "")) > 10
            ),
            name="failure_explained",
            description="Failed executions must have detailed explanation",
            failure_mode=FailureMode.SOFT_FAIL,
            failure_message="Execution failed without sufficient explanation.",
        ),
    ],
)

summary_contract = ValidationContract(
    name="summary",
    rules=[
        StructuralRule(schema=SummaryOutput),
    ],
)
