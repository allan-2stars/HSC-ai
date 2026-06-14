from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class QuestionQualityReview(Base):
    __tablename__ = "question_quality_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    question_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewer_admin_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("admin_profiles.id"), nullable=False
    )
    correctness_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    outcome_alignment_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    difficulty_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    explanation_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    overall_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    question: Mapped["Question"] = relationship()  # type: ignore[name-defined]
    reviewer: Mapped["AdminProfile"] = relationship()  # type: ignore[name-defined]
