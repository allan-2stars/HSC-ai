import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class WritingTaskStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class WritingSubmissionStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"


class WritingReviewStatus(str, enum.Enum):
    pending = "pending"
    assigned = "assigned"
    under_review = "under_review"
    reviewed = "reviewed"
    published = "published"


class WritingTask(Base, TimestampMixin):
    __tablename__ = "writing_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    word_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recommended_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subject_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subjects.id"), nullable=False, index=True
    )
    exam_type_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("exam_types.id"), nullable=False, index=True
    )
    status: Mapped[WritingTaskStatus] = mapped_column(
        SAEnum(WritingTaskStatus, name="writing_task_status"),
        default=WritingTaskStatus.draft,
        nullable=False,
        index=True,
    )
    created_by_admin_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("admin_profiles.id"), nullable=False
    )

    subject: Mapped["Subject"] = relationship()  # type: ignore[name-defined]
    exam_type: Mapped["ExamType"] = relationship()  # type: ignore[name-defined]
    created_by_admin: Mapped["AdminProfile"] = relationship()  # type: ignore[name-defined]


class WritingSubmission(Base, TimestampMixin):
    __tablename__ = "writing_submissions"
    __table_args__ = (
        UniqueConstraint("writing_task_id", "student_id", name="uq_writing_submission_task_student"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    writing_task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("writing_tasks.id"), nullable=False, index=True
    )
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("student_profiles.id"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[WritingSubmissionStatus] = mapped_column(
        SAEnum(WritingSubmissionStatus, name="writing_submission_status"),
        default=WritingSubmissionStatus.draft,
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    writing_task: Mapped["WritingTask"] = relationship()
    student: Mapped["StudentProfile"] = relationship()  # type: ignore[name-defined]


class WritingReview(Base, TimestampMixin):
    """Human review lifecycle for a submitted writing response. One review per
    submission. The submission itself stays immutable; all review state lives here."""

    __tablename__ = "writing_reviews"
    __table_args__ = (
        UniqueConstraint("submission_id", name="uq_writing_review_submission"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    submission_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("writing_submissions.id"), nullable=False, index=True
    )
    reviewer_admin_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("admin_profiles.id"), nullable=True, index=True
    )
    status: Mapped[WritingReviewStatus] = mapped_column(
        SAEnum(WritingReviewStatus, name="writing_review_status"),
        default=WritingReviewStatus.pending,
        nullable=False,
        index=True,
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    submission: Mapped["WritingSubmission"] = relationship()
    reviewer: Mapped["AdminProfile"] = relationship()  # type: ignore[name-defined]


class WritingFeedback(Base):
    """Versioned, append-only feedback authored during a review. Each save inserts
    a new version; rows are never updated or deleted (enforced by DB trigger).
    The highest version is the current feedback."""

    __tablename__ = "writing_feedback"
    __table_args__ = (
        UniqueConstraint("review_id", "version", name="uq_writing_feedback_review_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    review_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("writing_reviews.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    overall_comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Rubric-safe slot: free-form per-dimension comments now; maps to rubric criteria later.
    dimensions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_by_admin_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("admin_profiles.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    review: Mapped["WritingReview"] = relationship()
