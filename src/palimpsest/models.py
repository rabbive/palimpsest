from typing import Literal

from pydantic import BaseModel, Field


class Fact(BaseModel):
    id: str
    dialogue_id: str
    session_idx: int
    session_ts: str = ""
    subject: str
    predicate: str
    object: str
    polarity: Literal["affirm", "negate"] = "affirm"
    source_span: str
    status: Literal["current", "historical"] = "current"
    superseded_by: str | None = None
    supersedes: str | None = None
    confidence: float = 1.0


class ExtractedFacts(BaseModel):
    """Structured-output envelope for one session's extraction call."""

    facts: list[Fact]


ReconcileLabel = Literal["NEW", "DUPLICATE", "REFINEMENT", "SUPERSESSION", "CONTRADICTION"]


class ReconcileDecision(BaseModel):
    label: ReconcileLabel
    candidate: Fact
    prior_fact_id: str | None = None
    reason: str


class Abstention(BaseModel):
    abstained: bool = True
    missing_slots: list[str]
    reason: str
    partial_matches: list[str] = Field(default_factory=list)


class Answer(BaseModel):
    text: str
    abstention: Abstention | None = None
    provenance: list[str] = Field(default_factory=list)
    intent: str = "CURRENT"


class EvalResult(BaseModel):
    dialogue_id: str
    category: str
    question: str
    arm: Literal["A", "B", "C"]
    llm_response: str
    llm_judge_score: float | None = None
