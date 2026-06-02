import secrets
import string
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import ParentProfile, StudentProfile, User, UserRole
from app.services.audit_service import log_action

MAX_STUDENTS_PER_PARENT = 3


async def get_parent_profile(user_id: str, db: AsyncSession) -> ParentProfile:
    result = await db.execute(
        select(ParentProfile).where(ParentProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent profile not found")
    return profile


async def get_student_count(parent_id: str, db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(StudentProfile)
        .join(User, User.id == StudentProfile.user_id)
        .where(StudentProfile.parent_id == parent_id)
        .where(User.is_active == True)  # noqa: E712
    )
    return result.scalar_one()


async def list_students(parent_id: str, db: AsyncSession) -> list[StudentProfile]:
    result = await db.execute(
        select(StudentProfile)
        .join(User, User.id == StudentProfile.user_id)
        .where(StudentProfile.parent_id == parent_id)
        .where(User.is_active == True)  # noqa: E712
    )
    return list(result.scalars().all())


async def create_student(
    parent_id: str,
    display_name: str,
    year_level: int | None,
    initial_password: str | None,
    db: AsyncSession,
    actor_user_id: str,
) -> tuple[StudentProfile, str, str]:
    """Returns (StudentProfile, login_email, temp_password)."""
    count = await get_student_count(parent_id, db)
    if count >= MAX_STUDENTS_PER_PARENT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Maximum of {MAX_STUDENTS_PER_PARENT} students per parent account",
        )

    short_id = str(uuid4())[:8]
    login_email = f"s{short_id}@students.hscai.internal"
    temp_password = initial_password or _generate_password()

    student_user = User(
        email=login_email,
        password_hash=hash_password(temp_password),
        role=UserRole.student,
    )
    db.add(student_user)
    await db.flush()

    profile = StudentProfile(
        user_id=student_user.id,
        parent_id=parent_id,
        display_name=display_name,
        year_level=year_level,
        first_login_completed=False,
    )
    db.add(profile)

    await log_action(
        db,
        action="student.created",
        actor_user_id=actor_user_id,
        actor_role=UserRole.parent.value,
        target_type="student_profile",
        target_id=profile.id,
        metadata={"display_name": display_name},
    )

    await db.commit()
    await db.refresh(profile)
    return profile, login_email, temp_password


async def update_student(
    student_id: str,
    parent_id: str,
    display_name: str | None,
    year_level: int | None,
    db: AsyncSession,
) -> StudentProfile:
    profile = await _get_student_for_parent(student_id, parent_id, db)
    if display_name is not None:
        profile.display_name = display_name
    if year_level is not None:
        profile.year_level = year_level
    await db.commit()
    await db.refresh(profile)
    return profile


async def deactivate_student(
    student_id: str,
    parent_id: str,
    db: AsyncSession,
    actor_user_id: str,
) -> None:
    profile = await _get_student_for_parent(student_id, parent_id, db)
    result = await db.execute(select(User).where(User.id == profile.user_id))
    user = result.scalar_one()
    user.is_active = False

    await log_action(
        db,
        action="student.deactivated",
        actor_user_id=actor_user_id,
        actor_role=UserRole.parent.value,
        target_type="student_profile",
        target_id=student_id,
    )
    await db.commit()


async def complete_first_login(
    student_user_id: str,
    new_password: str,
    db: AsyncSession,
) -> None:
    user_result = await db.execute(select(User).where(User.id == student_user_id))
    user = user_result.scalar_one()
    user.password_hash = hash_password(new_password)

    profile_result = await db.execute(
        select(StudentProfile).where(StudentProfile.user_id == student_user_id)
    )
    profile = profile_result.scalar_one()
    profile.first_login_completed = True

    await log_action(
        db,
        action="student.first_login_completed",
        actor_user_id=student_user_id,
        actor_role=UserRole.student.value,
        target_type="student_profile",
        target_id=profile.id,
    )
    await db.commit()


# ── helpers ──────────────────────────────────────────────────────

async def _get_student_for_parent(
    student_id: str, parent_id: str, db: AsyncSession
) -> StudentProfile:
    result = await db.execute(
        select(StudentProfile)
        .where(StudentProfile.id == student_id)
        .where(StudentProfile.parent_id == parent_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found or not owned by this parent",
        )
    return profile


def _generate_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
