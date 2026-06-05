from datetime import datetime
from pydantic import BaseModel


class OCRQuestionItem(BaseModel):
    stem: str
    correct_answer: str
    explanation: str
    options_json: list | None = None
    confidence: float = 0.5


class OCRJobPageResponse(BaseModel):
    page_number: int
    extracted_text: str = ""
    confidence: float = 0.0
    structured_questions_json: list | None = None


class OCRJobResponse(BaseModel):
    id: str
    filename: str
    file_format: str
    status: str
    questions_detected: int
    questions_created: int
    raw_text: str = ""
    pages: list[OCRJobPageResponse] = []
    questions: list[OCRQuestionItem] = []
    error_message: str | None = None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class OCRJobListResponse(BaseModel):
    id: str
    filename: str
    file_format: str
    status: str
    questions_detected: int
    questions_created: int
    created_at: datetime


class OCRCreateDraftsRequest(BaseModel):
    subject_id: str
    exam_type_id: str


class OCRBulkResultResponse(BaseModel):
    job_ids: list[str]
    total_files: int
    total_pages: int
    total_questions: int
    jobs: list[dict] = []

