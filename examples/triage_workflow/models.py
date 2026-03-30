from pydantic import BaseModel


class TriageIntake(BaseModel):
    patient_id: str
    complaint: str
    severity: int


class TriageDecision(BaseModel):
    action: str
    priority: str
    confidence: float
    rationale: str


class EscalationCheck(BaseModel):
    escalated: bool
    assigned_role: str
    notes: str
