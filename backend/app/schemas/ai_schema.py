from datetime import datetime
from pydantic import BaseModel


class AIGenerationRequest(BaseModel):
    outcome_id: str
    framework_id: str | None = None
    subject_id: str
    exam_type_id: str
    count: int = 5
    difficulty_mix: dict | None = None
    provider: str = "mock"


class AIGeneratedQuestionItem(BaseModel):
    question_text: str
    options: list
    correct_answer: str
    explanation: str
    difficulty: str
    curriculum_outcome_code: str
    provider: str
    valid: bool
    errors: list[str]


class AIGenerationPreviewResponse(BaseModel):
    questions: list[AIGeneratedQuestionItem]
    summary: dict


class AIGenerationExecuteResponse(BaseModel):
    job_id: str
    provider: str
    requested_count: int
    generated_count: int
    saved_count: int
    rejected_count: int
    status: str
    estimated_cost: float | None = None
    completed_at: datetime | None


class AIJobListResponse(BaseModel):
    id: str
    provider: str
    outcome_id: str | None
    subject_id: str
    exam_type_id: str
    requested_count: int
    saved_count: int
    status: str
    created_at: datetime


class AIJobDetailResponse(BaseModel):
    id: str
    provider: str
    framework_id: str | None
    outcome_id: str | None
    subject_id: str
    exam_type_id: str
    requested_count: int
    generated_count: int
    saved_count: int
    rejected_count: int
    status: str
    error_message: str | None
    token_usage_json: dict | None = None
    estimated_cost: float | None = None
    created_at: datetime
    completed_at: datetime | None
