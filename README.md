# Gateframe

Behavioral validation for LLM outputs. Not schema validation - tools like Instructor and Pydantic AI already handle that. gateframe validates whether an LLM output *behaves correctly* given the context it was generated in, stays within decision boundaries, and fails in ways your system can recover from.

```python
from pydantic import BaseModel
from gateframe.core.contract import ValidationContract
from gateframe.core.failure import FailureMode
from gateframe.rules.structural import StructuralRule

class TriageOutput(BaseModel):
    severity: str
    recommendation: str
    confidence: float

contract = ValidationContract(
    name="triage_check",
    rules=[
        StructuralRule(schema=TriageOutput),
    ],
)

result = contract.validate({
    "severity": "high",
    "recommendation": "Escalate to on-call engineer",
    "confidence": 0.92,
})

assert result.passed
```

When validation fails, you get structured failure records - not just a boolean:

```python
result = contract.validate({"severity": "high"})

assert not result.passed
for failure in result.failures:
    print(failure.message)
    # structural:TriageOutput failed: recommendation: Field required; confidence: Field required.
```

## Failure modes

gateframe distinguishes four failure modes instead of binary pass/fail:

**HARD_FAIL** - Stop execution, escalate. The output is wrong in a way that cannot be auto-recovered.

```python
# Missing required fields in a medical triage output
StructuralRule(schema=TriageOutput, failure_mode=FailureMode.HARD_FAIL)
```

**SOFT_FAIL** - Flag the output and continue with degraded confidence. Something is off but not critical.

```python
# Output has all fields but confidence is below threshold
StructuralRule(schema=TriageOutput, failure_mode=FailureMode.SOFT_FAIL)
```

**RETRY** - Re-prompt with failure context. The output is fixable by trying again.

```python
# Malformed JSON that might parse on a second attempt
StructuralRule(schema=TriageOutput, failure_mode=FailureMode.RETRY)
```

**SILENT_FAIL** - The most dangerous kind. Output looks valid but violates semantic or boundary rules. gateframe makes these visible instead of letting them pass through.

## When to use gateframe

Use it when:
- You need to validate LLM outputs beyond schema checks - behavioral contracts, decision boundaries, cross-step propagation
- You need structured failure records for debugging production incidents
- You want to distinguish between "retry this", "flag this", and "stop everything"

Don't use it when:
- You only need schema extraction from LLM outputs (use Instructor or Pydantic AI)
- You need offline model evaluation or benchmarking (use DeepEval or RAGAS)
- You need content safety filtering (use a dedicated guardrails tool)

## Installation

```bash
pip install gateframe
```

For development:

```bash
git clone https://github.com/practicalmind-ai/gateframe.git
cd gateframe
pip install -e ".[dev]"
```

## Quickstart

```python
from pydantic import BaseModel
from gateframe.core.contract import ValidationContract
from gateframe.rules.structural import StructuralRule
from gateframe.audit.log import AuditLog

# Define your expected output schema
class AgentResponse(BaseModel):
    action: str
    reasoning: str

# Create a contract with rules
contract = ValidationContract(
    name="agent_response_check",
    rules=[StructuralRule(schema=AgentResponse)],
)

# Validate LLM output
result = contract.validate({
    "action": "send_email",
    "reasoning": "User requested a follow-up email to the client.",
})

# Log the validation event
audit = AuditLog()
audit.record(result)
```

## Running tests

```bash
pip install -e ".[dev]"
pytest -q
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
