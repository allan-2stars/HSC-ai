from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class CurriculumFramework(Base, TimestampMixin):
    __tablename__ = "curriculum_frameworks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    exam_type_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("exam_types.id"), nullable=True, index=True
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="2026")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    outcomes: Mapped[list["CurriculumOutcome"]] = relationship(
        back_populates="framework",
        order_by="CurriculumOutcome.sort_order",
        cascade="all, delete-orphan",
    )


class CurriculumOutcome(Base):
    __tablename__ = "curriculum_outcomes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    framework_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("curriculum_frameworks.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    framework: Mapped["CurriculumFramework"] = relationship(back_populates="outcomes")
    question_mappings: Mapped[list["QuestionOutcomeMapping"]] = relationship(
        back_populates="outcome", cascade="all, delete-orphan"
    )


class QuestionOutcomeMapping(Base):
    __tablename__ = "question_outcome_mappings"
    __table_args__ = (
        UniqueConstraint("question_id", "outcome_id", name="uq_question_outcome"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    question_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    outcome_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("curriculum_outcomes.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    weight: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    outcome: Mapped["CurriculumOutcome"] = relationship(back_populates="question_mappings")
    question: Mapped["Question"] = relationship()  # type: ignore[name-defined]
