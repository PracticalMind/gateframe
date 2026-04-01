# Gateframe

[![CI](https://github.com/PracticalMind/gateframe/actions/workflows/ci.yml/badge.svg)](https://github.com/PracticalMind/gateframe/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gateframe)](https://pypi.org/project/gateframe/)
[![Python](https://img.shields.io/pypi/pyversions/gateframe)](https://pypi.org/project/gateframe/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

Behavioral validation for LLM outputs in production workflows.

Schema validation, "does this JSON have the right keys?", is a solved problem. Instructor, Pydantic AI, and similar tools handle it well. gateframe solves a different problem: **does this output behave correctly given the context it was generated in?** Does it stay within the decision boundaries this workflow requires? When it fails, does it fail in a way your system can recover from, or does it fail silently?

```python
from pydantic import BaseModel
from gateframe import (
    ValidationContract,
    StructuralRule,
    BoundaryRule,
    ConfidenceRule,
    AllowedValues,
    FailureMode,
)

class TriageDecision(BaseModel):
    action: str
    priority: str
    confidence: float
    rationale: str

contract = ValidationContract(
    name="triage_decision",
    rules=[
        StructuralRule(schema=TriageDecision),
        BoundaryRule(
            check=AllowedValues("action", {"treat", "observe", "refer", "discharge"}),
            name="action_boundary",
            failure_message="Action must be one of: treat, observe, refer, discharge.",
        ),
        ConfidenceRule(field="confidence", minimum=0.7),
    ],
)

result = contract.validate({
    "action": "prescribe",       # not in allowed set -> HARD_FAIL
    "priority": "high",
    "confidence": 0.52,          # below 0.7 -> SOFT_FAIL
    "rationale": "...",
})

print(result.passed)             # False
for failure in result.failures:
    print(f"[{failure.failure_mode.value}] {failure.rule_name}: {failure.message}")
# [hard_fail] action_boundary: Action must be one of: treat, observe, refer, discharge.
# [soft_fail] confidence_check: Confidence 0.52 is below minimum threshold 0.7.
```

---

## The problem

Most LLM pipelines validate outputs the same way: parse the JSON, check the schema, move on. That catches structural errors. It misses the errors that actually cause production incidents:

- A model recommends an action that is structurally valid but outside its authorized scope
- Confidence is low but the workflow proceeds as if it weren't
- A soft failure in step 2 silently degrades the reliability of everything downstream
- A validation failure gives you `False`, and no context for debugging

gateframe makes these failures explicit, structured, and recoverable.

---

## Failure modes

gateframe distinguishes four failure types instead of binary pass/fail.

**`HARD_FAIL`**, Stop. The output violates a hard constraint that cannot be auto-recovered.

```python
# Model chose an action outside its authorized scope
BoundaryRule(
    check=AllowedValues("action", {"treat", "observe", "refer"}),
    failure_mode=FailureMode.HARD_FAIL,  # default for BoundaryRule
)
```

**`SOFT_FAIL`**, Flag and continue with degraded confidence. Something is off but not critical enough to halt.

```python
# Model confidence is low, continue but track the degradation
ConfidenceRule(
    field="confidence",
    minimum=0.7,
    failure_mode=FailureMode.SOFT_FAIL,  # default for ConfidenceRule
)
```

**`RETRY`**, Re-prompt with the failure context. The output is likely fixable by trying again.

```python
# Malformed output that might parse correctly on a second attempt
StructuralRule(schema=MyOutput, failure_mode=FailureMode.RETRY)
```

**`SILENT_FAIL`**, The most dangerous kind. The output looks valid but violates a semantic or boundary rule. gateframe makes these visible instead of letting them pass through undetected.

```python
SemanticRule(
    check=lambda output, **ctx: output["severity"] != "low" or output["escalated"] is False,
    failure_mode=FailureMode.SILENT_FAIL,
    failure_message="Low-severity cases should not be auto-escalated.",
)
```

---

## Multi-step workflow validation

Validation state carries forward across steps. A soft failure in step 2 degrades the confidence score that step 4 sees.

```python
from gateframe import WorkflowContext, ValidationContract, EscalationRouter
from gateframe.audit.log import AuditLog

ctx = WorkflowContext(workflow_id="incident_response_001", escalation_threshold=0.5)
router = EscalationRouter()
audit = AuditLog()

# Step 1
result1 = contract_step1.validate(output1)
ctx.update(result1)
audit.record(result1, workflow_context=ctx)

# Step 2, ctx carries forward degraded confidence from step 1
result2 = contract_step2.validate(output2)
ctx.update(result2)
audit.record(result2, workflow_context=ctx)

print(ctx.confidence)           # degraded from 1.0 by soft failures
print(ctx.threshold_breached)   # True if confidence < escalation_threshold

if ctx.threshold_breached:
    escalation = router.route_threshold_breach(ctx)
    print(escalation.route.value)  # "human_review", "abort", etc.
```

---

## Provider integrations

gateframe validates outputs from any provider. Integrations are thin wrappers, gateframe does not import any LLM SDK at the core level.

```python
# OpenAI
from gateframe.integrations.openai import OpenAIValidator
validator = OpenAIValidator(contract, parse_json=True)
result = validator.validate(openai_completion)

# Anthropic
from gateframe.integrations.anthropic import AnthropicValidator
validator = AnthropicValidator(contract, parse_json=True)
result = validator.validate(anthropic_message)

# LiteLLM
from gateframe.integrations.litellm import LiteLLMValidator
validator = LiteLLMValidator(contract, parse_json=True)
result = validator.validate(litellm_response)

# LangChain
from gateframe.integrations.langchain import LangChainValidator
validator = LangChainValidator(contract, parse_json=False)
result = validator.validate(chain_output)
```

Install the integration you need:

```bash
pip install "gateframe[openai]"
pip install "gateframe[anthropic]"
pip install "gateframe[litellm]"
pip install "gateframe[langchain]"
```

---

## Audit trail

Every validation event is logged with structured context. Use the built-in exporters or implement your own.

```python
from gateframe.audit.log import AuditLog
from gateframe.audit.exporters import JsonFileExporter

audit = AuditLog(exporters=[JsonFileExporter("audit.jsonl")])
audit.record(result, workflow_context=ctx)
audit.flush()
```

Each entry includes: timestamp, contract name, rules applied, rules failed, failure details, workflow ID, and accumulated confidence score.

---

## Trend analysis

`ContractTrendAnalyzer` reads an existing JSONL audit log and computes per-contract pass-rate trends across workflow runs. Use it to detect reliability regressions before they become incidents.

```python
from pathlib import Path
from gateframe.audit.trend import ContractTrendAnalyzer

analyzer = ContractTrendAnalyzer(Path("audit.jsonl"), window=20)
report = analyzer.analyze()

if report.any_regression:
    for ct in report.regressions:
        print(f"{ct.contract_name}: {ct.direction} (slope={ct.slope:.4f})")
```

The `window` parameter controls how many most-recent workflow runs are included. A contract is flagged as regressing when its pass-rate slope falls below `-0.02` (two percentage points per run) by default.

---

## When to use gateframe

Use it when:
- You need to validate LLM output behavior beyond schema checks, decision boundaries, scope enforcement, semantic constraints
- You need structured, recoverable failure records rather than bare exceptions
- You're running multi-step workflows where soft failures in early steps should affect confidence downstream
- You need an audit trail for post-incident debugging

Don't use it when:
- You only need schema extraction from LLM outputs, use [Instructor](https://github.com/jxnl/instructor) or [Pydantic AI](https://ai.pydantic.dev/)
- You need offline model evaluation or benchmarking, use [DeepEval](https://github.com/confident-ai/deepeval) or [RAGAS](https://github.com/explodinggradients/ragas)
- You need content safety filtering, use a dedicated guardrails tool

---

## Installation

```bash
pip install gateframe
```

For development:

```bash
git clone https://github.com/practicalmind-ai/gateframe.git
cd gateframe
pip install -e ".[dev]"
python -m pytest tests/ -v
```

---

## Examples

**[triage_workflow](examples/triage_workflow/)**, 3-step medical triage pipeline. Demonstrates StructuralRule, BoundaryRule, ConfidenceRule, and WorkflowContext together. Step 2 has confidence below threshold, shows how SOFT_FAIL degrades the workflow score without halting it.

**[rag_output](examples/rag_output/)**, RAG answer validation with two scenarios. Scenario B demonstrates simultaneous soft failures (low confidence + ungrounded answer) and how they accumulate in the workflow context.

**[agent_pipeline](examples/agent_pipeline/)**, 4-step agent workflow with escalation. Demonstrates how multiple soft failures across steps push cumulative confidence below the escalation threshold.

---

## CLI

```bash
# Inspect a contract file, lists all contracts and their rules
gateframe inspect contracts.py

# Replay an audit log
gateframe replay audit.jsonl

# Detect pass-rate regressions across workflow runs
gateframe trend audit.jsonl --window 20
```

---

## License

MIT, see [LICENSE](LICENSE).
