from datetime import datetime

from pydantic import BaseModel, field_validator

from app.models.question import (
    ContentOwnershipType,
    DifficultyLevel,
    PoolType,
    QuestionStatus,
    QuestionType,
    SourceType,
)


class QuestionVersionResponse(BaseModel):
    id: str
    question_id: str
    version_number: int
    stem: str
    correct_answer: str | None
    full_explanation: str
    marks: int
    options_json: list | None
    metadata_json: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class QuestionResponse(BaseModel):
    id: str
    subject_id: str
    exam_type_id: str
    year_level: int
    topic_id: str | None
    difficulty: DifficultyLevel
    question_type: QuestionType
    status: QuestionStatus
    source_type: SourceType
    content_ownership: ContentOwnershipType
    copyright_note: str | None
    current_version: QuestionVersionResponse | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QuestionCreateRequest(BaseModel):
    subject_id: str
    exam_type_id: str
    year_level: int
    topic_id: str | None = None
    difficulty: DifficultyLevel
    question_type: QuestionType
    source_type: SourceType
    content_ownership: ContentOwnershipType
    copyright_note: str | None = None
    stem: str
    correct_answer: str | None = None
    full_explanation: str
    marks: int = 1
    options_json: list | None = None

    @field_validator("year_level")
    @classmethod
    def valid_year(cls, v: int) -> int:
        if v not in range(3, 13):
            raise ValueError("year_level must be between 3 and 12")
        return v

    @field_validator("stem")
    @classmethod
    def stem_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("stem cannot be empty")
        return v

    @field_validator("full_explanation")
    @classmethod
    def explanation_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("full_explanation cannot be empty")
        return v

    @field_validator("marks")
    @classmethod
    def marks_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("marks must be at least 1")
        return v


class QuestionVersionCreateRequest(BaseModel):
    stem: str
    correct_answer: str | None = None
    full_explanation: str
    marks: int = 1
    options_json: list | None = None

    @field_validator("stem")
    @classmethod
    def stem_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("stem cannot be empty")
        return v

    @field_validator("full_explanation")
    @classmethod
    def explanation_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("full_explanation cannot be empty")
        return v


class QuestionStatusRequest(BaseModel):
    status: QuestionStatus


class PoolCreateRequest(BaseModel):
    name: str
    description: str | None = None
    subject_id: str | None = None
    exam_type_id: str | None = None
    year_level: int | None = None

    @field_validator("name")
    @classmethod
    def name_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()


class PoolResponse(BaseModel):
    id: str
    name: str
    description: str | None
    subject_id: str | None
    exam_type_id: str | None
    year_level: int | None
    pool_type: PoolType
    created_at: datetime

    model_config = {"from_attributes": True}


class PoolMemberAddRequest(BaseModel):
    question_id: str
