from pydantic import BaseModel


class ClassificationOutput(BaseModel):
    category: str
    confidence: float
    reasoning: str


class ActionPlanOutput(BaseModel):
    steps: list[str]
    estimated_risk: str
    requires_approval: bool


class ExecutionOutput(BaseModel):
    action_taken: str
    success: bool
    details: str


class SummaryOutput(BaseModel):
    outcome: str
    actions_completed: list[str]
    follow_up_needed: bool
