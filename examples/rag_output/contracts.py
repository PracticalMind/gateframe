from gateframe.core.contract import ValidationContract
from gateframe.rules.confidence import ConfidenceRule
from gateframe.rules.semantic import SemanticRule
from gateframe.rules.structural import StructuralRule

from .models import RagAnswer

retrieval_contract = ValidationContract(
    name="retrieval_check",
    rules=[
        StructuralRule(schema=RagAnswer),
        SemanticRule(
            check=lambda output, **ctx: len(output.get("citations", [])) > 0,
            name="has_citations",
            failure_message="Answer must include at least one citation.",
        ),
    ],
)

answer_contract = ValidationContract(
    name="answer_quality",
    rules=[
        StructuralRule(schema=RagAnswer),
        SemanticRule(
            check=lambda output, **ctx: len(output.get("answer", "")) >= 20,
            name="answer_length",
            failure_message="Answer is too short to be useful (minimum 20 characters).",
        ),
        ConfidenceRule(
            field="confidence",
            minimum=0.65,
            name="answer_confidence",
        ),
        SemanticRule(
            check=lambda output, **ctx: output.get("grounded") is True,
            name="grounding_check",
            failure_message="Answer must be grounded in retrieved documents.",
        ),
    ],
)
