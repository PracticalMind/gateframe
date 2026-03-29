"""Agent pipeline example: 4-step workflow with confidence degradation and escalation."""

from gateframe.audit.log import AuditLog
from gateframe.core.context import WorkflowContext
from gateframe.core.escalation import EscalationRouter

from .contracts import (
    action_plan_contract,
    classification_contract,
    execution_contract,
    summary_contract,
)


def main() -> None:
    ctx = WorkflowContext(
        workflow_id="incident_response_001",
        escalation_threshold=0.5,
    )
    router = EscalationRouter()
    audit = AuditLog()

    # Step 1: Classification -- passes cleanly
    step1_output = {
        "category": "infrastructure",
        "confidence": 0.92,
        "reasoning": "CPU usage spike correlated with deployment at 14:32 UTC",
    }
    result1 = classification_contract.validate(step1_output)
    ctx.update(result1)
    audit.record(result1, workflow_context=ctx)
    print(f"Step 1 (classification): passed={result1.passed}, confidence={ctx.confidence:.2f}")

    # Step 2: Action plan -- soft fail (high risk without approval)
    step2_output = {
        "steps": ["Roll back deployment", "Check error logs", "Notify team"],
        "estimated_risk": "high",
        "requires_approval": False,  # this triggers soft fail
    }
    result2 = action_plan_contract.validate(step2_output)
    ctx.update(result2)
    audit.record(result2, workflow_context=ctx)
    print(f"Step 2 (action_plan): passed={result2.passed}, confidence={ctx.confidence:.2f}")

    # Step 3: Execution -- soft fail (failed without explanation)
    step3_output = {
        "action_taken": "Attempted rollback",
        "success": False,
        "details": "Timeout",  # too short, triggers soft fail
    }
    result3 = execution_contract.validate(step3_output)
    ctx.update(result3)
    audit.record(result3, workflow_context=ctx)
    print(f"Step 3 (execution): passed={result3.passed}, confidence={ctx.confidence:.2f}")

    # Step 4: Summary -- passes structurally
    step4_output = {
        "outcome": "Partial resolution",
        "actions_completed": ["Rollback attempted", "Logs checked"],
        "follow_up_needed": True,
    }
    result4 = summary_contract.validate(step4_output)
    ctx.update(result4)
    audit.record(result4, workflow_context=ctx)
    print(f"Step 4 (summary): passed={result4.passed}, confidence={ctx.confidence:.2f}")

    # Check threshold
    print(f"\nThreshold breached: {ctx.threshold_breached}")
    if ctx.threshold_breached:
        escalation = router.route_threshold_breach(ctx)
        if escalation:
            print(f"Escalation: {escalation.route.value} -- {escalation.reason}")

    # Audit trail
    print(f"\nAudit entries: {len(audit.entries)}")
    for entry in audit.entries:
        data = entry.to_dict()
        print(f"  [{data['contract_name']}] passed={data['passed']}", end="")
        if data.get("confidence") is not None:
            print(f", confidence={data['confidence']:.2f}", end="")
        print()


if __name__ == "__main__":
    main()
