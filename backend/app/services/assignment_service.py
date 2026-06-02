from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.assignment import AssignedExam, AssignmentStatus
from app.models.exam import Attempt, AttemptStatus, ExamInstance, ExamInstanceStatus
from app.models.user import ParentProfile, StudentProfile, User
from app.services import audit_service


async def _verify_ownership(
    student_id: str, parent_profile_id: str, db: AsyncSession
) -> StudentProfile:
    result = await db.execute(
        select(StudentProfile).where(
            StudentProfile.id == student_id,
            StudentProfile.parent_id == parent_profile_id,
        )
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: student does not belong to this parent",
        )
    return student


# ── CRUD ─────────────────────────────────────────────────────────────────────


async def create_assignment(
    student_id: str,
    parent_profile_id: str,
    exam_instance_id: str,
    db: AsyncSession,
    parent_user_id: str = "",
    due_at: datetime | None = None,
) -> AssignedExam:
    student = await _verify_ownership(student_id, parent_profile_id, db)

    # Verify instance is published
    result = await db.execute(
        select(ExamInstance).where(ExamInstance.id == exam_instance_id)
    )
    instance = result.scalar_one_or_none()
    if not instance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam instance not found")
    if instance.status != ExamInstanceStatus.published:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot assign unpublished exam instance",
        )

    assignment = AssignedExam(
        student_id=student_id,
        exam_instance_id=exam_instance_id,
        assigned_by_parent_id=parent_profile_id,
        title_snapshot=instance.title,
        due_at=due_at,
        status=AssignmentStatus.assigned,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    await audit_service.log_action(
        db=db,
        action="assignment_created",
        actor_user_id=parent_user_id,
        actor_role="parent",
        target_type="assigned_exam",
        target_id=assignment.id,
        metadata={"student_id": student_id, "exam_instance_id": exam_instance_id},
    )
    await db.commit()

    return assignment


async def get_assignment(assignment_id: str, db: AsyncSession) -> AssignedExam:
    result = await db.execute(
        select(AssignedExam)
        .options(
            selectinload(AssignedExam.exam_instance),
            selectinload(AssignedExam.student),
        )
        .where(AssignedExam.id == assignment_id)
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return assignment


async def list_assignments_for_student(
    student_id: str, db: AsyncSession, parent_id: str | None = None
) -> list[AssignedExam]:
    query = (
        select(AssignedExam)
        .options(
            selectinload(AssignedExam.exam_instance),
            selectinload(AssignedExam.student),
        )
        .where(AssignedExam.student_id == student_id)
    )
    if parent_id:
        query = query.where(AssignedExam.assigned_by_parent_id == parent_id)
    result = await db.execute(query.order_by(AssignedExam.created_at.desc()))
    return list(result.scalars().all())


async def list_assignments_for_parent(
    parent_profile_id: str, db: AsyncSession
) -> list[AssignedExam]:
    result = await db.execute(
        select(StudentProfile)
        .where(StudentProfile.parent_id == parent_profile_id)
    )
    students = list(result.scalars().all())
    if not students:
        return []

    student_ids = [s.id for s in students]
    result = await db.execute(
        select(AssignedExam)
        .options(
            selectinload(AssignedExam.exam_instance),
            selectinload(AssignedExam.student),
        )
        .where(AssignedExam.student_id.in_(student_ids))
        .order_by(AssignedExam.created_at.desc())
    )
    return list(result.scalars().all())


async def update_assignment(
    assignment_id: str,
    parent_profile_id: str,
    db: AsyncSession,
    parent_user_id: str = "",
    due_at: datetime | None = None,
    new_status: AssignmentStatus | None = None,
) -> AssignedExam:
    assignment = await get_assignment(assignment_id, db)

    if assignment.assigned_by_parent_id != parent_profile_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: not your assignment",
        )

    if new_status == AssignmentStatus.cancelled:
        if assignment.status in (AssignmentStatus.completed, AssignmentStatus.cancelled):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot cancel assignment with status '{assignment.status.value}'",
            )
        assignment.status = AssignmentStatus.cancelled

        await audit_service.log_action(
            db=db,
            action="assignment_cancelled",
            actor_user_id=parent_user_id,
            actor_role="parent",
            target_type="assigned_exam",
            target_id=assignment_id,
        )
        await db.commit()
        return await get_assignment(assignment_id, db)

    if due_at is not None:
        assignment.due_at = due_at

        await audit_service.log_action(
            db=db,
            action="assignment_updated",
            actor_user_id=parent_user_id,
            actor_role="parent",
            target_type="assigned_exam",
            target_id=assignment_id,
        )
        await db.commit()
        return await get_assignment(assignment_id, db)

    return assignment


async def get_assignment_summary(student_id: str, db: AsyncSession) -> dict:
    result = await db.execute(
        select(AssignedExam).where(AssignedExam.student_id == student_id)
    )
    assignments = list(result.scalars().all())

    counts = {"assigned": 0, "started": 0, "completed": 0, "overdue": 0, "cancelled": 0}
    for a in assignments:
        key = a.status.value if hasattr(a.status, "value") else a.status
        if key in counts:
            counts[key] += 1
    return counts


# ── Lifecycle transitions ────────────────────────────────────────────────────


async def check_and_mark_overdue(student_id: str, db: AsyncSession) -> int:
    """Mark all assigned/started assignments past their due date as overdue. Returns count."""
    now = datetime.now(tz=timezone.utc)
    result = await db.execute(
        select(AssignedExam).where(
            AssignedExam.student_id == student_id,
            AssignedExam.status.in_([AssignmentStatus.assigned, AssignmentStatus.started]),
            AssignedExam.due_at.isnot(None),
            AssignedExam.due_at < now,
        )
    )
    overdue = list(result.scalars().all())

    for a in overdue:
        a.status = AssignmentStatus.overdue

    if overdue:
        await db.commit()

    return len(overdue)


async def transition_on_attempt_start(
    assignment_id: str, attempt_id: str, db: AsyncSession
) -> None:
    """Mark assignment as started and link the attempt."""
    assignment = await get_assignment(assignment_id, db)

    if assignment.status == AssignmentStatus.assigned:
        assignment.status = AssignmentStatus.started
        await db.commit()

        await audit_service.log_action(
            db=db,
            action="assignment_started",
            actor_user_id=None,
            actor_role="system",
            target_type="assigned_exam",
            target_id=assignment_id,
            metadata={"attempt_id": attempt_id},
        )
        await db.commit()

    # Link the attempt back to the assignment
    result = await db.execute(select(Attempt).where(Attempt.id == attempt_id))
    attempt = result.scalar_one_or_none()
    if attempt and not attempt.assigned_exam_id:
        attempt.assigned_exam_id = assignment_id
        await db.commit()


async def transition_on_attempt_submit(
    assignment_id: str, db: AsyncSession
) -> None:
    """Mark assignment as completed when attempt is submitted."""
    assignment = await get_assignment(assignment_id, db)

    if assignment.status in (AssignmentStatus.assigned, AssignmentStatus.started, AssignmentStatus.overdue):
        assignment.status = AssignmentStatus.completed
        await db.commit()

        await audit_service.log_action(
            db=db,
            action="assignment_completed",
            actor_user_id=None,
            actor_role="system",
            target_type="assigned_exam",
            target_id=assignment_id,
        )
        await db.commit()
