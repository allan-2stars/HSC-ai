from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.question import (
    ContentOwnershipType,
    DifficultyLevel,
    PoolType,
    Question,
    QuestionPool,
    QuestionPoolMembership,
    QuestionStatus,
    QuestionType,
    QuestionVersion,
    SourceType,
)


_BLOCKED_OWNERSHIP = frozenset({
    ContentOwnershipType.internal_draft,
    ContentOwnershipType.restricted_reference_only,
})

_VALID_TRANSITIONS: dict[QuestionStatus, frozenset[QuestionStatus]] = {
    QuestionStatus.draft: frozenset({QuestionStatus.review}),
    QuestionStatus.review: frozenset({QuestionStatus.approved, QuestionStatus.rejected}),
    QuestionStatus.rejected: frozenset({QuestionStatus.draft}),
    QuestionStatus.approved: frozenset({QuestionStatus.published, QuestionStatus.archived}),
    QuestionStatus.published: frozenset({QuestionStatus.archived}),
    QuestionStatus.archived: frozenset(),
}


# ── Question CRUD ─────────────────────────────────────────────────────────────

async def create_question(
    subject_id: str,
    exam_type_id: str,
    year_level: int,
    difficulty: DifficultyLevel,
    question_type: QuestionType,
    source_type: SourceType,
    content_ownership: ContentOwnershipType,
    stem: str,
    full_explanation: str,
    created_by_admin_id: str,
    db: AsyncSession,
    topic_id: str | None = None,
    copyright_note: str | None = None,
    correct_answer: str | None = None,
    marks: int = 1,
    options_json: list | None = None,
) -> Question:
    question = Question(
        subject_id=subject_id,
        exam_type_id=exam_type_id,
        year_level=year_level,
        topic_id=topic_id,
        difficulty=difficulty,
        question_type=question_type,
        status=QuestionStatus.draft,
        source_type=source_type,
        content_ownership=content_ownership,
        copyright_note=copyright_note,
        created_by_admin_id=created_by_admin_id,
        current_version_id=None,
    )
    db.add(question)
    await db.flush()

    version = QuestionVersion(
        question_id=question.id,
        version_number=1,
        stem=stem,
        correct_answer=correct_answer,
        full_explanation=full_explanation,
        marks=marks,
        options_json=options_json,
        created_by_admin_id=created_by_admin_id,
        created_at=datetime.now(tz=timezone.utc),
    )
    db.add(version)
    await db.flush()

    question.current_version_id = version.id
    await db.commit()

    return await get_question(question.id, db)


async def get_question(question_id: str, db: AsyncSession) -> Question:
    result = await db.execute(
        select(Question)
        .options(selectinload(Question.current_version))
        .where(Question.id == question_id)
    )
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return question


async def list_questions(
    db: AsyncSession,
    status_filter: QuestionStatus | None = None,
    subject_id: str | None = None,
    exam_type_id: str | None = None,
) -> list[Question]:
    query = select(Question).options(selectinload(Question.current_version))
    if status_filter is not None:
        query = query.where(Question.status == status_filter)
    if subject_id:
        query = query.where(Question.subject_id == subject_id)
    if exam_type_id:
        query = query.where(Question.exam_type_id == exam_type_id)
    result = await db.execute(query.order_by(Question.created_at.desc()))
    return list(result.scalars().all())


async def add_version(
    question_id: str,
    stem: str,
    full_explanation: str,
    created_by_admin_id: str,
    db: AsyncSession,
    correct_answer: str | None = None,
    marks: int = 1,
    options_json: list | None = None,
) -> QuestionVersion:
    question = await get_question(question_id, db)

    result = await db.execute(
        select(func.max(QuestionVersion.version_number)).where(
            QuestionVersion.question_id == question_id
        )
    )
    max_ver = result.scalar_one_or_none() or 0

    version = QuestionVersion(
        question_id=question.id,
        version_number=max_ver + 1,
        stem=stem,
        correct_answer=correct_answer,
        full_explanation=full_explanation,
        marks=marks,
        options_json=options_json,
        created_by_admin_id=created_by_admin_id,
        created_at=datetime.now(tz=timezone.utc),
    )
    db.add(version)
    await db.flush()

    question.current_version_id = version.id
    if question.status not in (QuestionStatus.draft, QuestionStatus.archived):
        question.status = QuestionStatus.review

    await db.commit()
    await db.refresh(version)
    return version


async def list_versions(question_id: str, db: AsyncSession) -> list[QuestionVersion]:
    result = await db.execute(
        select(QuestionVersion)
        .where(QuestionVersion.question_id == question_id)
        .order_by(QuestionVersion.version_number)
    )
    return list(result.scalars().all())


async def transition_status(
    question_id: str, new_status: QuestionStatus, db: AsyncSession
) -> Question:
    question = await get_question(question_id, db)

    allowed = _VALID_TRANSITIONS.get(question.status, frozenset())
    if new_status not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot transition from '{question.status}' to '{new_status}'",
        )

    if new_status == QuestionStatus.published and question.content_ownership in _BLOCKED_OWNERSHIP:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Questions with '{question.content_ownership}' ownership cannot be published. "
                "Update the content_ownership classification first."
            ),
        )

    question.status = new_status
    await db.commit()

    return await get_question(question_id, db)


# ── Pool management ───────────────────────────────────────────────────────────

async def create_pool(
    name: str,
    created_by_admin_id: str,
    db: AsyncSession,
    description: str | None = None,
    subject_id: str | None = None,
    exam_type_id: str | None = None,
    year_level: int | None = None,
) -> QuestionPool:
    pool = QuestionPool(
        name=name,
        description=description,
        subject_id=subject_id,
        exam_type_id=exam_type_id,
        year_level=year_level,
        pool_type=PoolType.static,
        created_by_admin_id=created_by_admin_id,
    )
    db.add(pool)
    await db.commit()
    await db.refresh(pool)
    return pool


async def get_pool(pool_id: str, db: AsyncSession) -> QuestionPool:
    result = await db.execute(select(QuestionPool).where(QuestionPool.id == pool_id))
    pool = result.scalar_one_or_none()
    if not pool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pool not found")
    return pool


async def list_pools(db: AsyncSession) -> list[QuestionPool]:
    result = await db.execute(select(QuestionPool).order_by(QuestionPool.name))
    return list(result.scalars().all())


async def add_to_pool(pool_id: str, question_id: str, admin_id: str, db: AsyncSession) -> None:
    await get_pool(pool_id, db)
    await get_question(question_id, db)

    existing = await db.execute(
        select(QuestionPoolMembership)
        .where(QuestionPoolMembership.pool_id == pool_id)
        .where(QuestionPoolMembership.question_id == question_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Question already in pool")

    membership = QuestionPoolMembership(
        pool_id=pool_id,
        question_id=question_id,
        added_at=datetime.now(tz=timezone.utc),
        added_by_admin_id=admin_id,
    )
    db.add(membership)
    await db.commit()


async def list_pool_members(pool_id: str, db: AsyncSession) -> list[Question]:
    await get_pool(pool_id, db)
    result = await db.execute(
        select(Question)
        .join(QuestionPoolMembership, QuestionPoolMembership.question_id == Question.id)
        .where(QuestionPoolMembership.pool_id == pool_id)
        .options(selectinload(Question.current_version))
        .order_by(QuestionPoolMembership.added_at)
    )
    return list(result.scalars().all())


async def remove_from_pool(pool_id: str, question_id: str, db: AsyncSession) -> None:
    result = await db.execute(
        select(QuestionPoolMembership)
        .where(QuestionPoolMembership.pool_id == pool_id)
        .where(QuestionPoolMembership.question_id == question_id)
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not in pool")
    await db.delete(membership)
    await db.commit()
