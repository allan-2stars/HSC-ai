"""Writing mode — task management, student responses, autosave, submission."""
import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import StudentProfile
from app.models.writing import (
    WritingSubmission,
    WritingSubmissionStatus,
    WritingTask,
    WritingTaskStatus,
)

logger = logging.getLogger("hsc-ai.writing")


def _compute_word_count(content: str) -> int:
    return len(content.strip().split()) if content.strip() else 0


def _validate_status_enum(value: str, enum_cls, label: str):
    try:
        return enum_cls(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid {label}: '{value}'",
        )


# ── Admin: Writing Tasks ───────────────────────────────────────────────────


async def create_writing_task(
    db: AsyncSession,
    title: str,
    prompt: str,
    subject_id: str,
    exam_type_id: str,
    admin_profile_id: str,
    instructions: str | None = None,
    word_limit: int | None = None,
    recommended_time_minutes: int | None = None,
) -> WritingTask:
    task = WritingTask(
        title=title,
        prompt=prompt,
        instructions=instructions,
        word_limit=word_limit,
        recommended_time_minutes=recommended_time_minutes,
        subject_id=subject_id,
        exam_type_id=exam_type_id,
        created_by_admin_id=admin_profile_id,
        status=WritingTaskStatus.draft,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def list_writing_tasks(
    db: AsyncSession,
    status_str: str | None = None,
) -> list[WritingTask]:
    stmt = select(WritingTask).order_by(WritingTask.created_at.desc())
    if status_str:
        status_filter = _validate_status_enum(status_str, WritingTaskStatus, "task status")
        stmt = stmt.where(WritingTask.status == status_filter)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_writing_task(task_id: str, db: AsyncSession) -> WritingTask:
    result = await db.execute(select(WritingTask).where(WritingTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Writing task not found")
    return task


async def update_writing_task_status(
    task_id: str, new_status: WritingTaskStatus, db: AsyncSession
) -> WritingTask:
    task = await get_writing_task(task_id, db)
    task.status = new_status
    await db.commit()
    await db.refresh(task)
    return task


# ── Student: Submissions ───────────────────────────────────────────────────


async def get_or_create_submission(
    task_id: str, student_id: str, db: AsyncSession
) -> WritingSubmission:
    """Get existing submission or create a new one. Concurrency-safe via
    unique constraint — if two requests race and one creates the row first,
    the second will get an IntegrityError and retry the SELECT."""
    # Verify task exists and is published
    task = await get_writing_task(task_id, db)
    if task.status != WritingTaskStatus.published:
        raise HTTPException(status_code=422, detail="Writing task is not published")

    # Fast path: find existing
    result = await db.execute(
        select(WritingSubmission)
        .where(
            WritingSubmission.writing_task_id == task_id,
            WritingSubmission.student_id == student_id,
        )
    )
    sub = result.scalar_one_or_none()
    if sub:
        return sub

    # Slow path: create new, handle race
    sub = WritingSubmission(
        writing_task_id=task_id,
        student_id=student_id,
        content="",
        word_count=0,
        status=WritingSubmissionStatus.draft,
        started_at=datetime.now(tz=timezone.utc),
    )
    db.add(sub)
    try:
        await db.commit()
        await db.refresh(sub)
        return sub
    except IntegrityError:
        await db.rollback()
        # Race: another request already created it. Retrieve the winner.
        result = await db.execute(
            select(WritingSubmission)
            .where(
                WritingSubmission.writing_task_id == task_id,
                WritingSubmission.student_id == student_id,
            )
        )
        sub = result.scalar_one_or_none()
        if sub:
            return sub
        raise HTTPException(status_code=500, detail="Failed to create submission after conflict")


async def save_submission(
    submission_id: str,
    student_id: str,
    content: str,
    db: AsyncSession,
) -> WritingSubmission:
    """Save draft content. Word count computed server-side.
    Uses SELECT FOR UPDATE for atomicity."""
    result = await db.execute(
        select(WritingSubmission)
        .where(WritingSubmission.id == submission_id)
        .with_for_update()
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.student_id != student_id:
        raise HTTPException(status_code=403, detail="Not your submission")
    if sub.status == WritingSubmissionStatus.submitted:
        raise HTTPException(status_code=422, detail="Cannot edit submitted response")

    # Verify parent task not archived
    task = await get_writing_task(sub.writing_task_id, db)
    if task.status == WritingTaskStatus.archived:
        raise HTTPException(status_code=422, detail="Cannot edit submission for an archived task")

    sub.content = content
    sub.word_count = _compute_word_count(content)
    await db.commit()
    await db.refresh(sub)
    return sub


async def submit_submission(
    submission_id: str,
    student_id: str,
    db: AsyncSession,
    student_user_id: str | None = None,
) -> WritingSubmission:
    """Submit final response. Uses SELECT FOR UPDATE for atomicity.
    Recomputes word count server-side. Opens a pending human review."""
    result = await db.execute(
        select(WritingSubmission)
        .where(WritingSubmission.id == submission_id)
        .with_for_update()
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.student_id != student_id:
        raise HTTPException(status_code=403, detail="Not your submission")
    if sub.status == WritingSubmissionStatus.submitted:
        raise HTTPException(status_code=422, detail="Already submitted")

    # Verify parent task not archived
    task = await get_writing_task(sub.writing_task_id, db)
    if task.status == WritingTaskStatus.archived:
        raise HTTPException(status_code=422, detail="Cannot submit to an archived task")

    sub.word_count = _compute_word_count(sub.content)
    sub.status = WritingSubmissionStatus.submitted
    sub.submitted_at = datetime.now(tz=timezone.utc)

    # Open the human review lifecycle for this submission.
    from app.services import writing_review_service
    await writing_review_service.create_review_for_submission(
        sub.id, db, student_user_id=student_user_id
    )

    await db.commit()
    await db.refresh(sub)
    return sub


async def get_student_submission(
    submission_id: str, student_id: str, db: AsyncSession
) -> WritingSubmission:
    result = await db.execute(
        select(WritingSubmission).where(WritingSubmission.id == submission_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.student_id != student_id:
        raise HTTPException(status_code=403, detail="Not your submission")
    return sub


async def list_student_submissions(
    student_id: str, db: AsyncSession
) -> list[dict]:
    result = await db.execute(
        select(WritingSubmission, WritingTask.title)
        .join(WritingTask, WritingTask.id == WritingSubmission.writing_task_id)
        .where(WritingSubmission.student_id == student_id)
        .order_by(WritingSubmission.updated_at.desc())
    )
    rows = result.fetchall()
    return [
        {
            "id": sub.id,
            "writing_task_id": sub.writing_task_id,
            "task_title": task_title,
            "student_id": sub.student_id,
            "word_count": sub.word_count,
            "status": sub.status.value,
            "started_at": sub.started_at,
            "submitted_at": sub.submitted_at,
            "created_at": sub.created_at,
            "updated_at": sub.updated_at,
        }
        for sub, task_title in rows
    ]


async def list_student_available_tasks(
    student_id: str, db: AsyncSession
) -> list[dict]:
    """List published writing tasks with submission status for this student."""
    tasks_result = await db.execute(
        select(WritingTask)
        .where(WritingTask.status == WritingTaskStatus.published)
        .order_by(WritingTask.created_at.desc())
    )
    tasks = list(tasks_result.scalars().all())

    subs_result = await db.execute(
        select(WritingSubmission).where(WritingSubmission.student_id == student_id)
    )
    submissions_by_task = {
        s.writing_task_id: s for s in subs_result.scalars().all()
    }

    return [
        {
            "id": t.id,
            "title": t.title,
            "prompt": t.prompt,
            "instructions": t.instructions,
            "word_limit": t.word_limit,
            "recommended_time_minutes": t.recommended_time_minutes,
            "subject_id": t.subject_id,
            "exam_type_id": t.exam_type_id,
            "status": t.status.value,
            "created_at": t.created_at,
            "submission": {
                "id": s.id,
                "status": s.status.value,
                "word_count": s.word_count,
                "started_at": s.started_at,
                "submitted_at": s.submitted_at,
            } if (s := submissions_by_task.get(t.id)) else None,
        }
        for t in tasks
    ]


# ── Parent: View Submissions ───────────────────────────────────────────────


async def get_student_submissions_for_parent(
    student_id: str, parent_student_ids: list[str], db: AsyncSession
) -> list[dict]:
    if student_id not in parent_student_ids:
        raise HTTPException(status_code=403, detail="Not your student")
    return await list_student_submissions(student_id, db)


# ── Admin: Review Submissions ──────────────────────────────────────────────


async def list_all_submissions(
    db: AsyncSession,
    task_id: str | None = None,
    status_str: str | None = None,
) -> list[dict]:
    stmt = (
        select(WritingSubmission, WritingTask.title, StudentProfile.display_name)
        .join(WritingTask, WritingTask.id == WritingSubmission.writing_task_id)
        .join(StudentProfile, StudentProfile.id == WritingSubmission.student_id)
    )
    if task_id:
        stmt = stmt.where(WritingSubmission.writing_task_id == task_id)
    if status_str:
        status_filter = _validate_status_enum(status_str, WritingSubmissionStatus, "submission status")
        stmt = stmt.where(WritingSubmission.status == status_filter)
    stmt = stmt.order_by(WritingSubmission.updated_at.desc())
    result = await db.execute(stmt)
    rows = result.fetchall()

    return [
        {
            "id": sub.id,
            "writing_task_id": sub.writing_task_id,
            "task_title": task_title,
            "student_id": sub.student_id,
            "student_name": student_name,
            "word_count": sub.word_count,
            "status": sub.status.value,
            "content": sub.content,
            "started_at": sub.started_at.isoformat() if sub.started_at else None,
            "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
            "created_at": sub.created_at.isoformat() if sub.created_at else None,
            "updated_at": sub.updated_at.isoformat() if sub.updated_at else None,
        }
        for sub, task_title, student_name in rows
    ]
