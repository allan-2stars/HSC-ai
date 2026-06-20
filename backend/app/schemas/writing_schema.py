from datetime import datetime
from pydantic import BaseModel, Field


class WritingTaskCreate(BaseModel):
    title: str
    prompt: str
    instructions: str | None = None
    word_limit: int | None = None
    recommended_time_minutes: int | None = None
    subject_id: str
    exam_type_id: str


class WritingTaskResponse(BaseModel):
    id: str
    title: str
    prompt: str
    instructions: str | None
    word_limit: int | None
    recommended_time_minutes: int | None
    subject_id: str
    exam_type_id: str
    status: str
    created_at: str | None
    updated_at: str | None


class WritingSubmissionSave(BaseModel):
    content: str
    word_count: int = 0


class WritingSubmissionResponse(BaseModel):
    id: str
    writing_task_id: str
    student_id: str
    content: str
    word_count: int
    status: str
    started_at: str | None
    submitted_at: str | None
    created_at: str | None
    updated_at: str | None


class WritingSubmissionListItem(BaseModel):
    id: str
    writing_task_id: str
    task_title: str
    student_id: str
    student_name: str | None
    word_count: int
    status: str
    content: str | None = None
    started_at: str | None
    submitted_at: str | None


class AdminReviewNote(BaseModel):
    review_notes: str


# ── Human review workflow (M5.1) ───────────────────────────────────────────


class WritingFeedbackCreate(BaseModel):
    overall_comment: str
    dimensions: list | None = None


# ── Rubrics (M5.2) ──────────────────────────────────────────────────────────


class RubricDimensionInput(BaseModel):
    name: str
    description: str | None = None
    display_order: int = 0


class RubricCreate(BaseModel):
    title: str
    framework_id: str | None = None
    subject_id: str | None = None
    exam_type_id: str | None = None
    active: bool = True
    dimensions: list[RubricDimensionInput] | None = None


class RubricUpdate(BaseModel):
    title: str | None = None
    framework_id: str | None = None
    subject_id: str | None = None
    exam_type_id: str | None = None
    active: bool | None = None


class RubricDimensionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    display_order: int | None = None


class RubricAssign(BaseModel):
    rubric_id: str | None = None


class ReviewScoreInput(BaseModel):
    dimension_id: str
    rating: int = Field(ge=1, le=5)
    comment: str = ""


class ReviewScoresCreate(BaseModel):
    scores: list[ReviewScoreInput]


# ── AI feedback drafts (M5.3) ────────────────────────────────────────────────


class AIDraftGenerate(BaseModel):
    provider: str | None = None


# ── AI score suggestions (M5.4) ────────────────────────────────────────────────


class ScoreSuggestionItem(BaseModel):
    id: str
    review_id: str
    dimension_version_id: str
    dimension_name: str | None = None
    suggested_rating: int | None
    suggested_comment: str | None
    confidence: float | None
    provider: str
    status: str
    created_at: str | None


class ScoreSuggestionGenerateRequest(BaseModel):
    provider: str | None = None


# ── Disputes & Reopen (M5.5) ──────────────────────────────────────────────────


class WritingDisputeCreate(BaseModel):
    reason: str
