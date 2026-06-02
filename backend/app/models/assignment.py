import enum
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.models.base import Base, TimestampMixin


class AssignmentStatus(str, enum.Enum):
    assigned = "assigned"
    started = "started"
    completed = "completed"
    overdue = "overdue"
    cancelled = "cancelled"


class AssignedExam(Base, TimestampMixin):
    __tablename__ = "assigned_exams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("student_profiles.id"), nullable=False, index=True
    )
    exam_instance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("exam_instances.id"), nullable=False, index=True
    )
    assigned_by_parent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("parent_profiles.id"), nullable=False
    )
    title_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[AssignmentStatus] = mapped_column(
        SAEnum(AssignmentStatus, name="assignment_status"),
        default=AssignmentStatus.assigned,
        nullable=False,
        index=True,
    )

    student: Mapped["StudentProfile"] = relationship()  # type: ignore[name-defined]
    exam_instance: Mapped["ExamInstance"] = relationship()
    assigned_by: Mapped["ParentProfile"] = relationship()  # type: ignore[name-defined]
