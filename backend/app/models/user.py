import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class UserRole(str, enum.Enum):
    parent = "parent"
    student = "student"
    admin = "admin"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole, name="user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    parent_profile: Mapped["ParentProfile | None"] = relationship(
        back_populates="user", uselist=False
    )
    student_profile: Mapped["StudentProfile | None"] = relationship(
        back_populates="user", uselist=False
    )
    admin_profile: Mapped["AdminProfile | None"] = relationship(
        back_populates="user", uselist=False
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user")


class ParentProfile(Base, TimestampMixin):
    __tablename__ = "parent_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Nullable FK reserved for future school/tutor organisation support (not V1)
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True, default=None)

    user: Mapped["User"] = relationship(back_populates="parent_profile")
    students: Mapped[list["StudentProfile"]] = relationship(back_populates="parent")
    subscriptions: Mapped[list["Subscription"]] = relationship(  # type: ignore[name-defined]
        back_populates="parent"
    )


class StudentProfile(Base, TimestampMixin):
    __tablename__ = "student_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    parent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("parent_profiles.id", ondelete="CASCADE"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    year_level: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    first_login_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Nullable FK reserved for future school support
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True, default=None)

    user: Mapped["User"] = relationship(back_populates="student_profile")
    parent: Mapped["ParentProfile"] = relationship(back_populates="students")


class AdminProfile(Base, TimestampMixin):
    __tablename__ = "admin_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)

    user: Mapped["User"] = relationship(back_populates="admin_profile")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")
