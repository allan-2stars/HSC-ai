from datetime import datetime

from pydantic import BaseModel, field_validator

from app.models.exam import (
    AttemptStatus,
    ExamInstanceStatus,
    ExamTemplateStatus,
)


# ── Admin: ExamTemplate ─────────────────────────────────────────────────────

class ExamTemplateCreate(BaseModel):
    title: str
    description: str | None = None
    exam_type_id: str
    subject_id: str | None = None
    year_level: int | None = None
    duration_minutes: int

    @field_validator("title")
    @classmethod
    def title_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title cannot be empty")
        return v.strip()

    @field_validator("duration_minutes")
    @classmethod
    def duration_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("duration_minutes must be at least 1")
        return v


class ExamTemplateStatusUpdate(BaseModel):
    status: ExamTemplateStatus


class ExamSectionCreate(BaseModel):
    title: str
    order_index: int = 0
    duration_minutes: int | None = None
    instructions: str | None = None

    @field_validator("title")
    @classmethod
    def title_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title cannot be empty")
        return v.strip()


class ExamSectionQuestionCreate(BaseModel):
    question_id: str
    order_index: int = 0
    marks: int = 1

    @field_validator("marks")
    @classmethod
    def marks_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("marks must be at least 1")
        return v


class ExamSectionQuestionResponse(BaseModel):
    id: str
    exam_section_id: str
    question_id: str
    order_index: int
    marks: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ExamSectionResponse(BaseModel):
    id: str
    exam_template_id: str
    title: str
    order_index: int
    duration_minutes: int | None
    instructions: str | None
    section_questions: list[ExamSectionQuestionResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExamTemplateResponse(BaseModel):
    id: str
    title: str
    description: str | None
    exam_type_id: str
    subject_id: str | None
    year_level: int | None
    duration_minutes: int
    status: ExamTemplateStatus
    created_by_admin_id: str
    sections: list[ExamSectionResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExamTemplateListResponse(BaseModel):
    id: str
    title: str
    exam_type_id: str
    status: ExamTemplateStatus
    duration_minutes: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Admin: ExamInstance ─────────────────────────────────────────────────────

class ExamInstanceCreate(BaseModel):
    title: str | None = None
    template_id: str


class ExamInstanceQuestionResponse(BaseModel):
    id: str
    exam_instance_id: str
    exam_section_id: str
    question_id: str
    question_version_id: str
    order_index: int
    marks: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ExamInstanceResponse(BaseModel):
    id: str
    exam_template_id: str
    title: str
    duration_minutes: int
    status: ExamInstanceStatus
    published_at: datetime | None
    instance_questions: list[ExamInstanceQuestionResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExamInstanceListResponse(BaseModel):
    id: str
    title: str
    duration_minutes: int
    status: ExamInstanceStatus
    published_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Student: Available Exams ────────────────────────────────────────────────

class ExamInstanceAvailableResponse(BaseModel):
    id: str
    title: str
    duration_minutes: int
    question_count: int
    total_marks: int

    model_config = {"from_attributes": True}


# ── Student: Attempt ────────────────────────────────────────────────────────

class AttemptQuestionResponse(BaseModel):
    exam_instance_question_id: str
    question_id: str
    question_version_id: str
    stem: str
    correct_answer: str | None
    full_explanation: str
    marks: int
    options_json: list | None
    order_index: int


class AttemptStartResponse(BaseModel):
    attempt_id: str
    exam_instance_id: str
    title: str
    duration_minutes: int
    started_at: datetime
    expires_at: datetime
    total_questions: int
    questions: list[AttemptQuestionResponse]


class AnswerSaveRequest(BaseModel):
    exam_instance_question_id: str
    selected_option: str | None = None
    time_spent_seconds: int = 0

    @field_validator("time_spent_seconds")
    @classmethod
    def time_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("time_spent_seconds must be non-negative")
        return v


class AttemptAnswerResponse(BaseModel):
    id: str
    exam_instance_question_id: str
    selected_option: str | None
    is_correct: bool | None
    time_spent_seconds: int
    answered_at: datetime

    model_config = {"from_attributes": True}


class IntegrityEventRequest(BaseModel):
    event_type: str

    @field_validator("event_type")
    @classmethod
    def valid_event_type(cls, v: str) -> str:
        allowed = {"tab_hidden", "tab_visible", "fullscreen_enter", "fullscreen_exit", "copy_attempt", "paste_attempt"}
        if v not in allowed:
            raise ValueError(f"event_type must be one of: {', '.join(sorted(allowed))}")
        return v


class AttemptSubmitResponse(BaseModel):
    attempt_id: str
    status: AttemptStatus
    score_raw: int
    score_percent: float
    total_questions: int
    correct_count: int
    submitted_at: datetime


class AttemptResultQuestionResponse(BaseModel):
    exam_instance_question_id: str
    question_id: str
    stem: str
    correct_answer: str | None
    full_explanation: str
    marks: int
    options_json: list | None
    order_index: int
    selected_option: str | None
    is_correct: bool | None
    marks_awarded: int


class AttemptResultResponse(BaseModel):
    attempt_id: str
    exam_instance_id: str
    title: str
    status: AttemptStatus
    started_at: datetime
    expires_at: datetime
    submitted_at: datetime | None
    score_raw: int | None
    score_percent: float | None
    total_questions: int
    correct_count: int | None
    questions: list[AttemptResultQuestionResponse]


class AttemptListResponse(BaseModel):
    id: str
    exam_instance_id: str
    exam_title: str
    status: AttemptStatus
    started_at: datetime
    submitted_at: datetime | None
    score_percent: float | None
    total_questions: int
    correct_count: int | None

    model_config = {"from_attributes": True}
