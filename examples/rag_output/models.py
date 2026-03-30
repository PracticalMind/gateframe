from pydantic import BaseModel


class RagAnswer(BaseModel):
    answer: str
    citations: list[str]
    confidence: float
    grounded: bool
