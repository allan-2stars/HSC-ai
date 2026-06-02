from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_parent, get_current_student
from app.models.user import User
from app.schemas.assignment import (
    AssignmentCreateRequest,
    AssignmentListResponse,
    AssignmentResponse,
    AssignmentSummaryResponse,
    AssignmentUpdateRequest,
)
from app.services import assignment_service, family_service

router = APIRouter(tags=["assignments"])


# ── Parent: Create Assignment ───────────────────────────────────────────────


@router.post(
    "/parents/students/{student_id}/assignments",
    response_model=AssignmentResponse,
    status_code=201,
)
async def create_assignment(
    student_id: str,
    body: AssignmentCreateRequest,
    parent_user: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    parent_profile = await family_service.get_parent_profile(parent_user.id, db)
    return await assignment_service.create_assignment(
        student_id=student_id,
        parent_profile_id=parent_profile.id,
        exam_instance_id=body.exam_instance_id,
        db=db,
        parent_user_id=parent_user.id,
        due_at=body.due_at,
    )


# ── Parent: List Assignments ────────────────────────────────────────────────


@router.get(
    "/parents/students/{student_id}/assignments",
    response_model=list[AssignmentListResponse],
)
async def list_student_assignments(
    student_id: str,
    parent_user: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    parent_profile = await family_service.get_parent_profile(parent_user.id, db)
    await assignment_service._verify_ownership(student_id, parent_profile.id, db)

    # Check overdue before returning
    await assignment_service.check_and_mark_overdue(student_id, db)

    assignments = await assignment_service.list_assignments_for_student(
        student_id, db, parent_id=parent_profile.id
    )
    return [
        AssignmentListResponse(
            id=a.id,
            student_id=a.student_id,
            exam_instance_id=a.exam_instance_id,
            title_snapshot=a.title_snapshot,
            due_at=a.due_at,
            status=a.status,
            student_name=a.student.display_name if a.student else None,
            created_at=a.created_at,
        )
        for a in assignments
    ]


@router.get(
    "/parents/assignments",
    response_model=list[AssignmentListResponse],
)
async def list_all_assignments(
    parent_user: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    parent_profile = await family_service.get_parent_profile(parent_user.id, db)
    assignments = await assignment_service.list_assignments_for_parent(
        parent_profile.id, db
    )
    return [
        AssignmentListResponse(
            id=a.id,
            student_id=a.student_id,
            exam_instance_id=a.exam_instance_id,
            title_snapshot=a.title_snapshot,
            due_at=a.due_at,
            status=a.status,
            student_name=a.student.display_name if a.student else None,
            created_at=a.created_at,
        )
        for a in assignments
    ]


# ── Parent: Assignment Summary ──────────────────────────────────────────────


@router.get(
    "/parents/students/{student_id}/assignment-summary",
    response_model=AssignmentSummaryResponse,
)
async def assignment_summary(
    student_id: str,
    parent_user: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    parent_profile = await family_service.get_parent_profile(parent_user.id, db)
    await assignment_service._verify_ownership(student_id, parent_profile.id, db)
    await assignment_service.check_and_mark_overdue(student_id, db)
    return await assignment_service.get_assignment_summary(student_id, db)


# ── Parent: Update/Cancel Assignment ────────────────────────────────────────


@router.patch(
    "/assignments/{assignment_id}",
    response_model=AssignmentResponse,
)
async def update_assignment(
    assignment_id: str,
    body: AssignmentUpdateRequest,
    parent_user: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    parent_profile = await family_service.get_parent_profile(parent_user.id, db)
    return await assignment_service.update_assignment(
        assignment_id=assignment_id,
        parent_profile_id=parent_profile.id,
        db=db,
        parent_user_id=parent_user.id,
        due_at=body.due_at,
        new_status=body.status,
    )


# ── Student: List My Assignments ────────────────────────────────────────────


@router.get(
    "/students/me/assignments",
    response_model=list[AssignmentListResponse],
)
async def list_my_assignments(
    student_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    from app.services.exam_service import get_student_profile_for_user
    profile = await get_student_profile_for_user(student_user.id, db)

    await assignment_service.check_and_mark_overdue(profile.id, db)

    assignments = await assignment_service.list_assignments_for_student(
        profile.id, db
    )
    return [
        AssignmentListResponse(
            id=a.id,
            student_id=a.student_id,
            exam_instance_id=a.exam_instance_id,
            title_snapshot=a.title_snapshot,
            due_at=a.due_at,
            status=a.status,
            student_name=None,
            created_at=a.created_at,
        )
        for a in assignments
    ]


# ── Student: Get Assignment Detail ──────────────────────────────────────────


@router.get(
    "/students/me/assignments/{assignment_id}",
    response_model=AssignmentResponse,
)
async def get_my_assignment(
    assignment_id: str,
    student_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    from app.services.exam_service import get_student_profile_for_user
    profile = await get_student_profile_for_user(student_user.id, db)

    assignment = await assignment_service.get_assignment(assignment_id, db)
    if assignment.student_id != profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: not your assignment",
        )
    return assignment
