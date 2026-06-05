import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class OCRJobStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class OCRJob(Base):
    __tablename__ = "ocr_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_format: Mapped[str] = mapped_column(String(10), nullable=False)  # pdf, png, jpg, jpeg, webp
    uploaded_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("admin_profiles.id"), nullable=False
    )
    status: Mapped[OCRJobStatus] = mapped_column(
        SAEnum(OCRJobStatus, name="ocr_job_status"),
        default=OCRJobStatus.pending,
        nullable=False,
    )
    questions_detected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    questions_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ocr_results_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OCRPageResult(Base):
    __tablename__ = "ocr_page_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    ocr_job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ocr_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    structured_questions_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
