from pydantic import BaseModel


class SimilarProblem(BaseModel):
    id: str
    title: str
    score: float


class SimilarityResult(BaseModel):
    similar_problems: list[SimilarProblem]
    has_duplicates: bool


class FilterResult(BaseModel):
    status: str  # "pending" | "needs_review" | "rejected"
    reason: str | None
    signals: list[str]


class TranslationResult(BaseModel):
    title_en: str
    description_en: str


class ClusteringResult(BaseModel):
    clusters_updated: int
    problems_processed: int
    duration_ms: int


class HealthResponse(BaseModel):
    status: str
    embedding_provider: str
    llm_provider: str
