from datetime import datetime

from pydantic import BaseModel, field_validator


# ── Framework ────────────────────────────────────────────────────────────────

class FrameworkCreate(BaseModel):
    name: str
    description: str | None = None
    exam_type_id: str | None = None
    version: str = "2026"

    @field_validator("name")
    @classmethod
    def name_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()


class FrameworkResponse(BaseModel):
    id: str
    name: str
    description: str | None
    exam_type_id: str | None
    version: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Outcome ──────────────────────────────────────────────────────────────────

class OutcomeCreate(BaseModel):
    framework_id: str
    code: str
    title: str
    description: str | None = None
    sort_order: int = 0

    @field_validator("code")
    @classmethod
    def code_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("code cannot be empty")
        return v.strip()

    @field_validator("title")
    @classmethod
    def title_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title cannot be empty")
        return v.strip()


class OutcomeResponse(BaseModel):
    id: str
    framework_id: str
    code: str
    title: str
    description: str | None
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Question Mapping ─────────────────────────────────────────────────────────

class QuestionMappingCreate(BaseModel):
    question_id: str
    outcome_id: str
    weight: float = 1.0

    @field_validator("weight")
    @classmethod
    def weight_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("weight must be positive")
        return v


class QuestionMappingResponse(BaseModel):
    id: str
    question_id: str
    outcome_id: str
    weight: float
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Coverage ─────────────────────────────────────────────────────────────────

class OutcomeCoverageItem(BaseModel):
    outcome_id: str
    code: str
    title: str
    approved_question_count: int
    draft_question_count: int
    total_question_count: int
    coverage_status: str  # "red", "amber", "green"


class CoverageReportResponse(BaseModel):
    framework_id: str
    framework_name: str
    total_outcomes: int
    mapped_outcomes: int
    covered_outcomes: int
    coverage_percentage: float
    outcomes: list[OutcomeCoverageItem]


class UnmappedQuestionItem(BaseModel):
    question_id: str
    stem: str
    status: str
    subject_name: str | None

    model_config = {"from_attributes": True}


# ── Dashboard ────────────────────────────────────────────────────────────────

class FrameworkSummaryItem(BaseModel):
    framework_id: str
    framework_name: str
    total_outcomes: int
    mapped_outcomes: int
    covered_outcomes: int
    coverage_percentage: float
    red_count: int
    amber_count: int
    green_count: int


class TopGapItem(BaseModel):
    framework_name: str
    outcome_code: str
    outcome_title: str
    outcome_id: str


class DashboardSummaryResponse(BaseModel):
    overall_coverage_pct: float
    total_frameworks: int
    total_outcomes: int
    total_mapped: int
    total_covered: int
    unmapped_question_count: int
    all_red_outcome_count: int
    frameworks: list[FrameworkSummaryItem]
    top_gaps: list[TopGapItem]
