from gateframe.audit.log import AuditLog
from gateframe.core.context import WorkflowContext

from .contracts import answer_contract, retrieval_contract


def run_scenario(label: str, intake: dict, answer: dict) -> None:
    ctx = WorkflowContext(workflow_id=f"rag_{label}", escalation_threshold=0.5)
    audit = AuditLog()

    result1 = retrieval_contract.validate(intake)
    ctx.update(result1)
    audit.record(result1, workflow_context=ctx)
    print(f"  Step 1 (retrieval_check): passed={result1.passed}")

    result2 = answer_contract.validate(answer)
    ctx.update(result2)
    audit.record(result2, workflow_context=ctx)
    print(f"  Step 2 (answer_quality): passed={result2.passed}, confidence={ctx.confidence:.2f}")
    for failure in result2.failures:
        print(f"    [{failure.failure_mode.value}] {failure.rule_name}: {failure.message}")


def main() -> None:
    print("Scenario A: passing")
    run_scenario(
        "scenario_a",
        intake={
            "answer": "The capital of France is Paris.",
            "citations": ["doc_001"],
            "confidence": 0.92,
            "grounded": True,
        },
        answer={
            "answer": "The capital of France is Paris, as stated in the referenced document.",
            "citations": ["doc_001"],
            "confidence": 0.92,
            "grounded": True,
        },
    )

    print("\nScenario B: degraded confidence")
    run_scenario(
        "scenario_b",
        intake={
            "answer": "Possibly Paris, though sources are unclear.",
            "citations": ["doc_002"],
            "confidence": 0.41,
            "grounded": False,
        },
        answer={
            "answer": "Possibly Paris, though sources are unclear.",
            "citations": ["doc_002"],
            "confidence": 0.41,
            "grounded": False,
        },
    )


if __name__ == "__main__":
    main()
