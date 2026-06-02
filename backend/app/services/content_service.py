from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import ExamType, SkillTag, Subject, Topic


# ── Subject ──────────────────────────────────────────────────────────────────

async def create_subject(code: str, name: str, db: AsyncSession) -> Subject:
    existing = await db.execute(select(Subject).where(Subject.code == code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Subject code already exists")
    subject = Subject(code=code, name=name)
    db.add(subject)
    await db.commit()
    await db.refresh(subject)
    return subject


async def list_subjects(db: AsyncSession) -> list[Subject]:
    result = await db.execute(
        select(Subject).where(Subject.is_active == True).order_by(Subject.name)  # noqa: E712
    )
    return list(result.scalars().all())


async def get_subject(subject_id: str, db: AsyncSession) -> Subject:
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    return subject


async def update_subject(
    subject_id: str, name: str | None, is_active: bool | None, db: AsyncSession
) -> Subject:
    subject = await get_subject(subject_id, db)
    if name is not None:
        subject.name = name
    if is_active is not None:
        subject.is_active = is_active
    await db.commit()
    await db.refresh(subject)
    return subject


# ── ExamType ─────────────────────────────────────────────────────────────────

async def create_exam_type(code: str, name: str, db: AsyncSession) -> ExamType:
    existing = await db.execute(select(ExamType).where(ExamType.code == code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ExamType code already exists")
    exam_type = ExamType(code=code, name=name)
    db.add(exam_type)
    await db.commit()
    await db.refresh(exam_type)
    return exam_type


async def list_exam_types(db: AsyncSession) -> list[ExamType]:
    result = await db.execute(
        select(ExamType).where(ExamType.is_active == True).order_by(ExamType.name)  # noqa: E712
    )
    return list(result.scalars().all())


async def get_exam_type(exam_type_id: str, db: AsyncSession) -> ExamType:
    result = await db.execute(select(ExamType).where(ExamType.id == exam_type_id))
    exam_type = result.scalar_one_or_none()
    if not exam_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ExamType not found")
    return exam_type


async def update_exam_type(
    exam_type_id: str, name: str | None, is_active: bool | None, db: AsyncSession
) -> ExamType:
    exam_type = await get_exam_type(exam_type_id, db)
    if name is not None:
        exam_type.name = name
    if is_active is not None:
        exam_type.is_active = is_active
    await db.commit()
    await db.refresh(exam_type)
    return exam_type


# ── Topic ────────────────────────────────────────────────────────────────────

async def create_topic(
    subject_id: str, name: str, description: str | None, db: AsyncSession
) -> Topic:
    await get_subject(subject_id, db)
    topic = Topic(subject_id=subject_id, name=name, description=description)
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return topic


async def list_topics(db: AsyncSession, subject_id: str | None = None) -> list[Topic]:
    query = select(Topic).where(Topic.is_active == True)  # noqa: E712
    if subject_id:
        query = query.where(Topic.subject_id == subject_id)
    result = await db.execute(query.order_by(Topic.name))
    return list(result.scalars().all())


async def get_topic(topic_id: str, db: AsyncSession) -> Topic:
    result = await db.execute(select(Topic).where(Topic.id == topic_id))
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    return topic


async def update_topic(
    topic_id: str,
    name: str | None,
    description: str | None,
    is_active: bool | None,
    db: AsyncSession,
) -> Topic:
    topic = await get_topic(topic_id, db)
    if name is not None:
        topic.name = name
    if description is not None:
        topic.description = description
    if is_active is not None:
        topic.is_active = is_active
    await db.commit()
    await db.refresh(topic)
    return topic


# ── SkillTag ─────────────────────────────────────────────────────────────────

async def create_skill_tag(name: str, subject_id: str | None, db: AsyncSession) -> SkillTag:
    tag = SkillTag(name=name, subject_id=subject_id)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


async def list_skill_tags(db: AsyncSession) -> list[SkillTag]:
    result = await db.execute(
        select(SkillTag).where(SkillTag.is_active == True).order_by(SkillTag.name)  # noqa: E712
    )
    return list(result.scalars().all())


async def get_skill_tag(skill_tag_id: str, db: AsyncSession) -> SkillTag:
    result = await db.execute(select(SkillTag).where(SkillTag.id == skill_tag_id))
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SkillTag not found")
    return tag


async def update_skill_tag(
    skill_tag_id: str, name: str | None, is_active: bool | None, db: AsyncSession
) -> SkillTag:
    tag = await get_skill_tag(skill_tag_id, db)
    if name is not None:
        tag.name = name
    if is_active is not None:
        tag.is_active = is_active
    await db.commit()
    await db.refresh(tag)
    return tag
