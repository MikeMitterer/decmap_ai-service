from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SimilarityPayload(BaseModel):
    text: str = Field(min_length=5, max_length=200)


class ProblemSubmittedPayload(BaseModel):
    problem_id: str
    title: str
    description: str
    ip_hash: str
    signals: list[str] = []
    honeypot: str | None = None
    submitted_at: datetime


class ProblemApprovedPayload(BaseModel):
    problem_id: str


class SolutionApprovedPayload(BaseModel):
    solution_id: str
    problem_id: str


class VoteChangedPayload(BaseModel):
    entity_id: str
    entity_type: Literal["problem", "solution"]
    new_score: int | None = None
