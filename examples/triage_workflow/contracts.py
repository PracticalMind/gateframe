from gateframe.core.contract import ValidationContract
from gateframe.rules.boundary import AllowedValues, BoundaryRule
from gateframe.rules.confidence import ConfidenceRule
from gateframe.rules.semantic import SemanticRule
from gateframe.rules.structural import StructuralRule

from .models import EscalationCheck, TriageDecision, TriageIntake

intake_contract = ValidationContract(
    name="intake",
    rules=[
        StructuralRule(schema=TriageIntake),
        SemanticRule(
            check=lambda output, **ctx: 1 <= output.get("severity", 0) <= 10,
            name="severity_range",
            failure_message="Severity must be between 1 and 10.",
        ),
    ],
)

triage_decision_contract = ValidationContract(
    name="triage_decision",
    rules=[
        StructuralRule(schema=TriageDecision),
        BoundaryRule(
            check=AllowedValues("action", {"treat", "observe", "refer", "discharge"}),
            name="action_boundary",
            failure_message="Action must be one of: treat, observe, refer, discharge.",
        ),
        BoundaryRule(
            check=AllowedValues("priority", {"low", "medium", "high", "critical"}),
            name="priority_boundary",
            failure_message="Priority must be one of: low, medium, high, critical.",
        ),
        ConfidenceRule(
            field="confidence",
            minimum=0.6,
            name="decision_confidence",
        ),
    ],
)

escalation_check_contract = ValidationContract(
    name="escalation_check",
    rules=[
        StructuralRule(schema=EscalationCheck),
        BoundaryRule(
            check=AllowedValues("assigned_role", {"nurse", "doctor", "specialist", "admin"}),
            name="role_boundary",
            failure_message="assigned_role must be one of: nurse, doctor, specialist, admin.",
        ),
    ],
)
