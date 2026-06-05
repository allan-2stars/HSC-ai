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
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AIGenerationJobStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class AIGenerationJob(Base):
    __tablename__ = "ai_generation_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    framework_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("curriculum_frameworks.id"), nullable=True
    )
    outcome_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("curriculum_outcomes.id"), nullable=True
    )
    subject_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subjects.id"), nullable=False
    )
    exam_type_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("exam_types.id"), nullable=False
    )
    difficulty_mix_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    requested_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    saved_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[AIGenerationJobStatus] = mapped_column(
        SAEnum(AIGenerationJobStatus, name="ai_generation_job_status"),
        default=AIGenerationJobStatus.pending,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_usage_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by_admin_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("admin_profiles.id"), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
