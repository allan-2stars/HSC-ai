import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ExamTemplateStatus(str, enum.Enum):
    draft = "draft"
    review = "review"
    approved = "approved"
    published = "published"
    archived = "archived"


class ExamInstanceStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class AttemptStatus(str, enum.Enum):
    in_progress = "in_progress"
    submitted = "submitted"
    expired = "expired"


class ExamTemplate(Base, TimestampMixin):
    __tablename__ = "exam_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    exam_type_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("exam_types.id"), nullable=False, index=True
    )
    subject_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("subjects.id"), nullable=True
    )
    year_level: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ExamTemplateStatus] = mapped_column(
        SAEnum(ExamTemplateStatus, name="exam_template_status"),
        default=ExamTemplateStatus.draft,
        nullable=False,
        index=True,
    )
    created_by_admin_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("admin_profiles.id"), nullable=False
    )

    sections: Mapped[list["ExamSection"]] = relationship(
        back_populates="template",
        order_by="ExamSection.order_index",
        cascade="all, delete-orphan",
    )
    created_by_admin: Mapped["AdminProfile"] = relationship(  # type: ignore[name-defined]
        foreign_keys=[created_by_admin_id]
    )


class ExamSection(Base, TimestampMixin):
    __tablename__ = "exam_sections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    exam_template_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("exam_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    template: Mapped["ExamTemplate"] = relationship(back_populates="sections")
    section_questions: Mapped[list["ExamSectionQuestion"]] = relationship(
        back_populates="section",
        order_by="ExamSectionQuestion.order_index",
        cascade="all, delete-orphan",
    )


class ExamSectionQuestion(Base):
    __tablename__ = "exam_section_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    exam_section_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("exam_sections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("questions.id"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    marks: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    section: Mapped["ExamSection"] = relationship(back_populates="section_questions")
    question: Mapped["Question"] = relationship()  # type: ignore[name-defined]


class ExamInstance(Base, TimestampMixin):
    __tablename__ = "exam_instances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    exam_template_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("exam_templates.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ExamInstanceStatus] = mapped_column(
        SAEnum(ExamInstanceStatus, name="exam_instance_status"),
        default=ExamInstanceStatus.draft,
        nullable=False,
        index=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    template: Mapped["ExamTemplate"] = relationship()
    instance_questions: Mapped[list["ExamInstanceQuestion"]] = relationship(
        back_populates="instance",
        order_by="ExamInstanceQuestion.order_index",
        cascade="all, delete-orphan",
    )


class ExamInstanceQuestion(Base):
    __tablename__ = "exam_instance_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    exam_instance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("exam_instances.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exam_section_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("exam_sections.id"), nullable=False
    )
    question_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("questions.id"), nullable=False
    )
    question_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("question_versions.id"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    marks: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    instance: Mapped["ExamInstance"] = relationship(back_populates="instance_questions")
    section: Mapped["ExamSection"] = relationship()
    question: Mapped["Question"] = relationship()  # type: ignore[name-defined]
    question_version: Mapped["QuestionVersion"] = relationship()  # type: ignore[name-defined]


class Attempt(Base, TimestampMixin):
    __tablename__ = "attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("student_profiles.id"), nullable=False, index=True
    )
    exam_instance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("exam_instances.id"), nullable=False, index=True
    )
    status: Mapped[AttemptStatus] = mapped_column(
        SAEnum(AttemptStatus, name="attempt_status"),
        default=AttemptStatus.in_progress,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score_raw: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    integrity_summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Link back to the parent assignment if this attempt was started from one.
    assigned_exam_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("assigned_exams.id"), nullable=True, index=True
    )

    student: Mapped["StudentProfile"] = relationship()  # type: ignore[name-defined]
    exam_instance: Mapped["ExamInstance"] = relationship()
    answers: Mapped[list["AttemptAnswer"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )
    integrity_events: Mapped[list["AttemptIntegrityEvent"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )


class AttemptAnswer(Base, TimestampMixin):
    __tablename__ = "attempt_answers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    attempt_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exam_instance_question_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("exam_instance_questions.id"), nullable=False
    )
    selected_option: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    attempt: Mapped["Attempt"] = relationship(back_populates="answers")
    exam_instance_question: Mapped["ExamInstanceQuestion"] = relationship()


class AttemptIntegrityEvent(Base):
    __tablename__ = "attempt_integrity_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    attempt_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    attempt: Mapped["Attempt"] = relationship(back_populates="integrity_events")
