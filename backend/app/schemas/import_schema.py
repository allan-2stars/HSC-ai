from datetime import datetime

from pydantic import BaseModel


class ImportPreviewRow(BaseModel):
    row: int
    stem: str
    correct_answer: str
    difficulty: str
    subject_id: str
    exam_type_id: str
    topic_name: str = ""
    outcome_code: str = ""
    explanation: str = ""
    source_type: str = "imported"


class ImportErrorRow(BaseModel):
    row: int
    errors: list[str]


class ImportDuplicateRow(BaseModel):
    row: int
    question_text: str


class ImportPreviewResponse(BaseModel):
    total_rows: int
    valid_count: int
    invalid_count: int
    duplicate_count: int
    valid: list[ImportPreviewRow]
    invalid: list[ImportErrorRow]
    duplicates: list[ImportDuplicateRow]


class ImportExecuteRequest(BaseModel):
    skip_duplicates: bool = True


class ImportResultResponse(BaseModel):
    job_id: str
    filename: str
    format: str
    status: str
    imported_count: int
    skipped_count: int
    failed_count: int
    duplicate_count: int
    mapping_count: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ImportJobListResponse(BaseModel):
    id: str
    filename: str
    format: str
    status: str
    imported_count: int
    failed_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TemplateResponse(BaseModel):
    format: str
    download_url: str
    description: str
