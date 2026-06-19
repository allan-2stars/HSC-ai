import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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


class WritingFeedbackDraftStatus(str, enum.Enum):
    generated = "generated"
    accepted = "accepted"
    discarded = "discarded"


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
    rubric_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("writing_rubrics.id"), nullable=True, index=True
    )

    subject: Mapped["Subject"] = relationship()  # type: ignore[name-defined]
    exam_type: Mapped["ExamType"] = relationship()  # type: ignore[name-defined]
    created_by_admin: Mapped["AdminProfile"] = relationship()  # type: ignore[name-defined]
    rubric: Mapped["WritingRubric"] = relationship()


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
    # M5.6 — freeze the rubric version used at publish time
    rubric_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("writing_rubric_versions.id"), nullable=True, index=True
    )

    submission: Mapped["WritingSubmission"] = relationship()
    reviewer: Mapped["AdminProfile"] = relationship()  # type: ignore[name-defined]
    rubric_version: Mapped["WritingRubricVersion | None"] = relationship()


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


# ── AI feedback drafts (M5.3) ────────────────────────────────────────────────


class WritingFeedbackDraft(Base, TimestampMixin):
    """AI-generated *draft* feedback for a review. Admin/reviewer-only — never
    exposed to students or parents. Generating, listing, or discarding a draft never
    mutates official feedback, rubric scores, or publish state. Only an explicit human
    'accept' action copies a draft into the official (versioned) feedback record."""

    __tablename__ = "writing_feedback_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    review_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("writing_reviews.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=WritingFeedbackDraftStatus.generated.value, index=True
    )
    # {"strengths": [...], "improvements": [...], "next_steps": [...], "overall_feedback": "..."}
    draft_feedback_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    generated_by_admin_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("admin_profiles.id"), nullable=True
    )

    review: Mapped["WritingReview"] = relationship()


# ── Rubrics (M5.2) ──────────────────────────────────────────────────────────


class WritingRubric(Base, TimestampMixin):
    """A reusable rubric template. Subject / exam_type / framework are optional
    (null = a global/platform rubric)."""

    __tablename__ = "writing_rubrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    framework_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("curriculum_frameworks.id"), nullable=True, index=True
    )
    subject_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("subjects.id"), nullable=True, index=True
    )
    exam_type_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("exam_types.id"), nullable=True, index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    dimensions: Mapped[list["WritingRubricDimension"]] = relationship(
        back_populates="rubric",
        order_by="WritingRubricDimension.display_order",
        cascade="all, delete-orphan",
    )


class WritingRubricDimension(Base, TimestampMixin):
    __tablename__ = "writing_rubric_dimensions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    rubric_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("writing_rubrics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    rubric: Mapped["WritingRubric"] = relationship(back_populates="dimensions")


class WritingReviewScore(Base, TimestampMixin):
    """A reviewer's rating + comment for one dimension of one review. Editable
    until the review is published, then frozen at the service layer. One row per
    (review, dimension)."""

    __tablename__ = "writing_review_scores"
    __table_args__ = (
        UniqueConstraint("review_id", "dimension_version_id", name="uq_review_score_review_dimversion"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_score_rating_range"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    review_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("writing_reviews.id"), nullable=False, index=True
    )
    # M5.2 legacy — references the live dimension (used during active review before publish)
    dimension_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("writing_rubric_dimensions.id"), nullable=True, index=True
    )
    # M5.6 — frozen dimension version; must match rubric_version on the review
    dimension_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("writing_rubric_dimension_versions.id"), nullable=True, index=True
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by_admin_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("admin_profiles.id"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="human")

    dimension: Mapped["WritingRubricDimension | None"] = relationship(foreign_keys=[dimension_id])
    dimension_version: Mapped["WritingRubricDimensionVersion | None"] = relationship(foreign_keys=[dimension_version_id])


# ── Rubric Versions (M5.6) ─────────────────────────────────────────────────


class WritingRubricVersion(Base):
    """Immutable snapshot of a rubric at the time a version was created. Editing
    any rubric field or dimension creates a new version. Old versions never change."""

    __tablename__ = "writing_rubric_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    rubric_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("writing_rubrics.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_admin_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    rubric: Mapped["WritingRubric"] = relationship()
    dimension_versions: Mapped[list["WritingRubricDimensionVersion"]] = relationship(
        order_by="WritingRubricDimensionVersion.display_order",
    )


class WritingRubricDimensionVersion(Base):
    """Immutable snapshot of a rubric dimension at version creation time."""

    __tablename__ = "writing_rubric_dimension_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    rubric_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("writing_rubric_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_dimension_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("writing_rubric_dimensions.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    rubric_version: Mapped["WritingRubricVersion"] = relationship(back_populates="dimension_versions")
