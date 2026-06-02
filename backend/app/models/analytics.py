from uuid import uuid4

from sqlalchemy import Float, ForeignKey, Integer, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TopicPerformance(Base):
    __tablename__ = "topic_performance"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("topics.id"), nullable=False, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accuracy_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    average_time_seconds: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False, default=0)
    last_calculated_at: Mapped[str] = mapped_column(
        String(36), nullable=True
    )  # stored as ISO timestamp for simplicity

    student: Mapped["StudentProfile"] = relationship()  # type: ignore[name-defined]
    topic: Mapped["Topic"] = relationship()  # type: ignore[name-defined]


class SkillPerformance(Base):
    __tablename__ = "skill_performance"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_tag_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("skill_tags.id"), nullable=False, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accuracy_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    average_time_seconds: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False, default=0)
    last_calculated_at: Mapped[str] = mapped_column(
        String(36), nullable=True
    )

    student: Mapped["StudentProfile"] = relationship()  # type: ignore[name-defined]
    skill_tag: Mapped["SkillTag"] = relationship()  # type: ignore[name-defined]
