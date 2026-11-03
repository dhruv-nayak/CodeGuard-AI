from typing import Literal

from pydantic import BaseModel, Field

Provider = Literal["auto", "openai", "gemini", "ollama"]


class ReviewRequest(BaseModel):
    filename: str = Field(default="submitted.py", max_length=120)
    language: Literal["python", "javascript", "typescript", "java", "php", "sql", "html"] = "python"
    code: str = Field(min_length=1, max_length=50000)
    ai_provider: Provider = "auto"


class Finding(BaseModel):
    rule_id: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    title: str
    message: str
    line: int | None = None
    recommendation: str


class AIFinding(BaseModel):
    severity: Literal["critical", "high", "medium", "low", "info"]
    title: str
    explanation: str
    recommendation: str
    line: int | None = None


class AIReview(BaseModel):
    summary: str
    findings: list[AIFinding] = Field(default_factory=list)
    improved_code: str | None = None
    generated_tests: str | None = None


class ReviewResponse(BaseModel):
    review_id: str
    filename: str
    language: str
    status: Literal["completed", "partial"]
    score: int
    summary: str
    findings: list[Finding]
    suggested_tests: list[str]
    ai_reviewed: bool
    ai_provider: str | None = None
    ai_review: AIReview | None = None
    limitations: list[str]
