import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    JSON,
    SmallInteger,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class DifficultyLevel(str, enum.Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class QuestionType(str, enum.Enum):
    mcq = "mcq"
    short_answer = "short_answer"
    extended_response = "extended_response"


class QuestionStatus(str, enum.Enum):
    draft = "draft"
    review = "review"
    approved = "approved"
    published = "published"
    archived = "archived"
    rejected = "rejected"


class SourceType(str, enum.Enum):
    manual = "manual"
    ocr = "ocr"
    ai = "ai"
    imported = "imported"


class ContentOwnershipType(str, enum.Enum):
    original = "original"
    licensed = "licensed"
    public_domain = "public_domain"
    approved_internal = "approved_internal"
    user_provided_with_rights = "user_provided_with_rights"
    internal_draft = "internal_draft"
    restricted_reference_only = "restricted_reference_only"


class MediaType(str, enum.Enum):
    image = "image"
    audio = "audio"


class PoolType(str, enum.Enum):
    static = "static"
    dynamic = "dynamic"


question_skill_tags = Table(
    "question_skill_tags",
    Base.metadata,
    Column(
        "question_id",
        String(36),
        ForeignKey("questions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "skill_tag_id",
        String(36),
        ForeignKey("skill_tags.id"),
        primary_key=True,
    ),
)


class Question(Base, TimestampMixin):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    subject_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subjects.id"), nullable=False, index=True
    )
    exam_type_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("exam_types.id"), nullable=False, index=True
    )
    year_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    topic_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("topics.id"), nullable=True
    )
    difficulty: Mapped[DifficultyLevel] = mapped_column(
        SAEnum(DifficultyLevel, name="difficulty_level"), nullable=False
    )
    question_type: Mapped[QuestionType] = mapped_column(
        SAEnum(QuestionType, name="question_type_enum"), nullable=False
    )
    status: Mapped[QuestionStatus] = mapped_column(
        SAEnum(QuestionStatus, name="question_status"),
        default=QuestionStatus.draft,
        nullable=False,
        index=True,
    )
    source_type: Mapped[SourceType] = mapped_column(
        SAEnum(SourceType, name="source_type"), nullable=False
    )
    content_ownership: Mapped[ContentOwnershipType] = mapped_column(
        SAEnum(ContentOwnershipType, name="content_ownership_type"), nullable=False
    )
    copyright_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Quality review fields
    quality_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_admin_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("admin_profiles.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # use_alter=True defers this FK until after question_versions table is created.
    current_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "question_versions.id",
            use_alter=True,
            name="fk_question_current_version_id",
        ),
        nullable=True,
    )
    created_by_admin_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("admin_profiles.id"), nullable=False
    )

    current_version: Mapped["QuestionVersion | None"] = relationship(
        foreign_keys=[current_version_id],
        post_update=True,
    )
    versions: Mapped[list["QuestionVersion"]] = relationship(
        back_populates="question",
        foreign_keys="[QuestionVersion.question_id]",
        order_by="QuestionVersion.version_number",
    )
    skill_tags: Mapped[list["SkillTag"]] = relationship(  # type: ignore[name-defined]
        secondary=question_skill_tags
    )
    created_by_admin: Mapped["AdminProfile"] = relationship(  # type: ignore[name-defined]
        foreign_keys=[created_by_admin_id]
    )


class QuestionVersion(Base):
    __tablename__ = "question_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    question_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("questions.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    correct_answer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    marks: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    options_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by_admin_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("admin_profiles.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    question: Mapped["Question"] = relationship(
        back_populates="versions", foreign_keys=[question_id]
    )
    media: Mapped[list["QuestionMedia"]] = relationship(
        back_populates="question_version", order_by="QuestionMedia.sort_order"
    )


class QuestionMedia(Base):
    __tablename__ = "question_media"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    question_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("question_versions.id"), nullable=False, index=True
    )
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    media_type: Mapped[MediaType] = mapped_column(
        SAEnum(MediaType, name="media_type"), nullable=False
    )
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)

    question_version: Mapped["QuestionVersion"] = relationship(back_populates="media")


class QuestionPool(Base, TimestampMixin):
    __tablename__ = "question_pools"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("subjects.id"), nullable=True
    )
    exam_type_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("exam_types.id"), nullable=True
    )
    year_level: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    pool_type: Mapped[PoolType] = mapped_column(
        SAEnum(PoolType, name="pool_type"), default=PoolType.static, nullable=False
    )
    query_criteria_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by_admin_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("admin_profiles.id"), nullable=False
    )

    memberships: Mapped[list["QuestionPoolMembership"]] = relationship(back_populates="pool")


class QuestionPoolMembership(Base):
    __tablename__ = "question_pool_memberships"

    pool_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("question_pools.id", ondelete="CASCADE"),
        primary_key=True,
    )
    question_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("questions.id"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    added_by_admin_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("admin_profiles.id"), nullable=False
    )

    pool: Mapped["QuestionPool"] = relationship(back_populates="memberships")
    question: Mapped["Question"] = relationship()
