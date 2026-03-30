from gateframe.audit.log import AuditLog
from gateframe.core.context import WorkflowContext

from .contracts import escalation_check_contract, intake_contract, triage_decision_contract


def main() -> None:
    ctx = WorkflowContext(workflow_id="triage_001", escalation_threshold=0.5)
    audit = AuditLog()

    # Step 1: Intake -- passes
    intake_output = {
        "patient_id": "P-4821",
        "complaint": "Chest pain and shortness of breath",
        "severity": 8,
    }
    result1 = intake_contract.validate(intake_output)
    ctx.update(result1)
    audit.record(result1, workflow_context=ctx)
    print(f"Step 1 (intake): passed={result1.passed}, confidence={ctx.confidence:.2f}")

    # Step 2: Triage decision -- confidence 0.52, below minimum 0.6 -> SOFT_FAIL
    decision_output = {
        "action": "treat",
        "priority": "high",
        "confidence": 0.52,
        "rationale": "Symptoms consistent with cardiac event, awaiting ECG confirmation.",
    }
    result2 = triage_decision_contract.validate(decision_output)
    ctx.update(result2)
    audit.record(result2, workflow_context=ctx)
    print(f"Step 2 (triage_decision): passed={result2.passed}, confidence={ctx.confidence:.2f}")
    for failure in result2.failures:
        print(f"  SOFT_FAIL [{failure.rule_name}]: {failure.message}")

    # Step 3: Escalation check -- passes
    escalation_output = {
        "escalated": True,
        "assigned_role": "doctor",
        "notes": "Escalated to on-call cardiologist.",
    }
    result3 = escalation_check_contract.validate(escalation_output)
    ctx.update(result3)
    audit.record(result3, workflow_context=ctx)
    print(f"Step 3 (escalation_check): passed={result3.passed}, confidence={ctx.confidence:.2f}")

    print(f"\nThreshold breached: {ctx.threshold_breached}")
    print(f"Audit entries: {len(audit.entries)}")
    for entry in audit.entries:
        data = entry.to_dict()
        conf = data.get("confidence", 1.0)
        print(f"  [{data['contract_name']}] passed={data['passed']}, confidence={conf:.2f}")


if __name__ == "__main__":
    main()
