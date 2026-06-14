from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
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
    __table_args__ = (
        CheckConstraint("correctness_score BETWEEN 1 AND 5", name="ck_quality_correctness_range"),
        CheckConstraint("outcome_alignment_score BETWEEN 1 AND 5", name="ck_quality_outcome_alignment_range"),
        CheckConstraint("difficulty_score BETWEEN 1 AND 5", name="ck_quality_difficulty_range"),
        CheckConstraint("explanation_score BETWEEN 1 AND 5", name="ck_quality_explanation_range"),
        CheckConstraint("overall_score BETWEEN 1 AND 5", name="ck_quality_overall_range"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    question_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewer_admin_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("admin_profiles.id", ondelete="SET NULL"), nullable=True
    )
    correctness_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    outcome_alignment_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    difficulty_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    explanation_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    overall_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    question: Mapped["Question"] = relationship()  # type: ignore[name-defined]
    reviewer: Mapped["AdminProfile | None"] = relationship()  # type: ignore[name-defined]
