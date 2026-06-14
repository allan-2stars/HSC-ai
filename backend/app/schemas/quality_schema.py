from datetime import datetime
from pydantic import BaseModel, field_validator


class QualityReviewCreate(BaseModel):
    question_id: str
    correctness_score: int = 3
    outcome_alignment_score: int = 3
    difficulty_score: int = 3
    explanation_score: int = 3
    overall_score: int = 3
    notes: str | None = None

    @field_validator(
        "correctness_score", "outcome_alignment_score",
        "difficulty_score", "explanation_score", "overall_score",
    )
    @classmethod
    def valid_score(cls, v: int) -> int:
        if v not in range(1, 6):
            raise ValueError("score must be 1-5")
        return v


class QualityReviewResponse(BaseModel):
    id: str
    question_id: str
    reviewer_admin_id: str
    correctness_score: int
    outcome_alignment_score: int
    difficulty_score: int
    explanation_score: int
    overall_score: int
    notes: str | None
    created_at: str | None


class QualityDashboardResponse(BaseModel):
    total_reviews: int
    unique_questions_reviewed: int
    average_scores: dict
    needs_revision_count: int
    reviews: list[QualityReviewResponse]


class SourceComparisonItem(BaseModel):
    source: str
    reviewed_count: int
    average_score: float


class ProviderComparisonItem(BaseModel):
    provider: str
    saved_count: int
    rejected_count: int
    rejection_rate: float
    publication_rate: float


class ProviderComparisonResponse(BaseModel):
    source: list[SourceComparisonItem] = []
    providers: list[ProviderComparisonItem] = []


class OutcomeQualityItem(BaseModel):
    outcome_code: str
    outcome_title: str
    total_questions: int
    reviewed_count: int
    average_quality: float
    needs_regeneration: int


class RegenerationCandidateItem(BaseModel):
    question_id: str
    review_id: str
    overall_score: int
    source_type: str
    question_status: str
    notes: str | None
