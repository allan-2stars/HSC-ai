from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_parent, get_current_student, get_current_admin
from app.models.exam import Attempt, AttemptStatus
from app.models.user import StudentProfile, User
from app.schemas.analytics import (
    ExamHistoryItem,
    RecommendationsResponse,
    SkillPerformanceResponse,
    StudentProgressResponse,
    StudentSummaryResponse,
    TopicPerformanceResponse,
    TrendItem,
)
from app.services import analytics_service, family_service

router = APIRouter(tags=["analytics"])


async def _verify_ownership(student_id: str, parent_user: User, db: AsyncSession) -> StudentProfile:
    """Verify the student belongs to the authenticated parent."""
    parent_profile = await family_service.get_parent_profile(parent_user.id, db)
    result = await db.execute(
        select(StudentProfile).where(
            StudentProfile.id == student_id,
            StudentProfile.parent_id == parent_profile.id,
        )
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: student does not belong to this parent",
        )
    return student


# ── Parent Analytics ─────────────────────────────────────────────────────────


@router.get(
    "/parents/students/{student_id}/analytics/summary",
    response_model=StudentSummaryResponse,
)
async def parent_student_summary(
    student_id: str,
    parent_user: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    await _verify_ownership(student_id, parent_user, db)
    return await analytics_service.calculate_student_summary(student_id, db)


@router.get(
    "/parents/students/{student_id}/analytics/topics",
    response_model=TopicPerformanceResponse,
)
async def parent_student_topics(
    student_id: str,
    parent_user: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    await _verify_ownership(student_id, parent_user, db)
    topics = await analytics_service.calculate_topic_performance(student_id, db)
    return {"topics": topics}


@router.get(
    "/parents/students/{student_id}/analytics/skills",
    response_model=SkillPerformanceResponse,
)
async def parent_student_skills(
    student_id: str,
    parent_user: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    await _verify_ownership(student_id, parent_user, db)
    skills = await analytics_service.calculate_skill_performance(student_id, db)
    return {"skills": skills}


@router.get(
    "/parents/students/{student_id}/analytics/recommendations",
    response_model=RecommendationsResponse,
)
async def parent_student_recommendations(
    student_id: str,
    parent_user: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    await _verify_ownership(student_id, parent_user, db)
    return await analytics_service.get_recommendations(student_id, db)


# ── Student Self-View ────────────────────────────────────────────────────────


@router.get(
    "/students/me/progress",
    response_model=StudentProgressResponse,
)
async def student_own_progress(
    student_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    from app.services.exam_service import get_student_profile_for_user
    profile = await get_student_profile_for_user(student_user.id, db)
    student_id = profile.id

    summary = await analytics_service.calculate_student_summary(student_id, db)
    recs = await analytics_service.get_recommendations(student_id, db)
    return {
        "summary": summary,
        "weak_topics": recs["weak_topics"],
        "strong_topics": recs["strong_topics"],
        "weak_skills": recs["weak_skills"],
        "strong_skills": recs["strong_skills"],
        "slow_topics": recs.get("slow_topics", []),
    }


# ── Trend ────────────────────────────────────────────────────────────────────


@router.get(
    "/parents/students/{student_id}/analytics/trend",
    response_model=list[TrendItem],
)
async def parent_student_trend(
    student_id: str,
    limit: int = 20,
    parent_user: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    await _verify_ownership(student_id, parent_user, db)
    return await analytics_service.calculate_trend(student_id, db, limit=limit)


@router.get(
    "/students/me/trend",
    response_model=list[TrendItem],
)
async def student_own_trend(
    limit: int = 20,
    student_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    from app.services.exam_service import get_student_profile_for_user
    profile = await get_student_profile_for_user(student_user.id, db)
    return await analytics_service.calculate_trend(profile.id, db, limit=limit)


# ── Exam History ─────────────────────────────────────────────────────────────


@router.get(
    "/students/me/history",
    response_model=list[ExamHistoryItem],
)
async def student_exam_history(
    student_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    from app.services.exam_service import get_student_profile_for_user
    profile = await get_student_profile_for_user(student_user.id, db)
    student_id = profile.id

    result = await db.execute(
        select(Attempt)
        .options(selectinload(Attempt.exam_instance))
        .where(
            Attempt.student_id == student_id,
            Attempt.status.in_([AttemptStatus.submitted, AttemptStatus.expired]),
        )
        .order_by(Attempt.submitted_at.desc())
        .limit(50)
    )
    attempts = list(result.scalars().all())

    history = []
    for a in attempts:
        history.append(ExamHistoryItem(
            attempt_id=a.id,
            exam_title=a.exam_instance.title,
            status=a.status.value,
            score_percent=a.score_percent,
            total_questions=a.total_questions,
            correct_count=a.correct_count,
            completed_at=a.submitted_at.isoformat() if a.submitted_at else None,
        ))
    return history
