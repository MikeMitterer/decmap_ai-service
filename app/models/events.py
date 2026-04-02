from typing import Literal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Payload models
# ---------------------------------------------------------------------------


class ProblemApprovedPayload(BaseModel):
    id: str
    cluster_id: str | None = None


class ProblemRejectedPayload(BaseModel):
    id: str
    reason: str


class ProblemDeletedPayload(BaseModel):
    id: str


class ClusterUpdatedPayload(BaseModel):
    id: str
    label: str
    problem_count: int


class SolutionApprovedPayload(BaseModel):
    id: str
    problem_id: str
    is_ai_generated: bool


class SolutionDeletedPayload(BaseModel):
    id: str
    problem_id: str


class VoteChangedPayload(BaseModel):
    entity_id: str
    entity_type: Literal["problem", "solution"]
    new_score: int


# ---------------------------------------------------------------------------
# Event models
# ---------------------------------------------------------------------------


class ProblemApprovedEvent(BaseModel):
    type: Literal["problem.approved"] = "problem.approved"
    payload: ProblemApprovedPayload


class ProblemRejectedEvent(BaseModel):
    type: Literal["problem.rejected"] = "problem.rejected"
    payload: ProblemRejectedPayload


class ProblemDeletedEvent(BaseModel):
    type: Literal["problem.deleted"] = "problem.deleted"
    payload: ProblemDeletedPayload


class ClusterUpdatedEvent(BaseModel):
    type: Literal["cluster.updated"] = "cluster.updated"
    payload: ClusterUpdatedPayload


class SolutionApprovedEvent(BaseModel):
    type: Literal["solution.approved"] = "solution.approved"
    payload: SolutionApprovedPayload


class SolutionDeletedEvent(BaseModel):
    type: Literal["solution.deleted"] = "solution.deleted"
    payload: SolutionDeletedPayload


class VoteChangedEvent(BaseModel):
    type: Literal["vote.changed"] = "vote.changed"
    payload: VoteChangedPayload


WebSocketEvent = (
    ProblemApprovedEvent
    | ProblemRejectedEvent
    | ProblemDeletedEvent
    | ClusterUpdatedEvent
    | SolutionApprovedEvent
    | SolutionDeletedEvent
    | VoteChangedEvent
)
