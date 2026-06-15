from datetime import datetime
from pydantic import BaseModel


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
    started_at: str | None
    submitted_at: str | None


class AdminReviewNote(BaseModel):
    review_notes: str
