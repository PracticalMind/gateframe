from pydantic import BaseModel

from gateframe.core.contract import ValidationContract
from gateframe.core.escalation import EscalationRoute
from gateframe.core.failure import FailureMode
from gateframe.rules.semantic import SemanticRule
from gateframe.rules.structural import StructuralRule


class SampleOutput(BaseModel):
    message: str
    score: float


sample_contract = ValidationContract(
    name="sample",
    rules=[
        StructuralRule(schema=SampleOutput),
        SemanticRule(
            check=lambda output, **ctx: True,
            name="always_pass",
            description="A semantic rule that always passes",
            failure_mode=FailureMode.SOFT_FAIL,
        ),
    ],
    on_hard_fail=EscalationRoute.ABORT,
    on_soft_fail=EscalationRoute.FLAG_AND_CONTINUE,
)

NOT_A_CONTRACT = "just a string"
