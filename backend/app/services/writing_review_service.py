"""M5.1 — Human review workflow for writing submissions.

State machine (writing_reviews.status):
    pending  → assigned        (admin assigns a reviewer)
    *        → under_review     (admin first opens the review detail)
    *        → reviewed         (admin saves a feedback version)
    reviewed → published        (admin publishes; gate: feedback must exist)

The submission itself is immutable. All review state lives in writing_reviews;
feedback is versioned and append-only in writing_feedback (latest version wins).
"""
import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import StudentProfile
from app.models.writing import (
    WritingFeedback,
    WritingReview,
    WritingReviewStatus,
    WritingSubmission,
    WritingTask,
)
from app.services import audit_service

logger = logging.getLogger("hsc-ai.writing-review")

DISCLAIMER = (
    "Writing feedback is educational guidance and does not represent "
    "official Selective School marking."
)


def _validate_review_status(value: str) -> WritingReviewStatus:
    try:
        return WritingReviewStatus(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid review status: '{value}'",
        )


# ── Lifecycle hook: review created when a response is submitted ──────────────


async def create_review_for_submission(
    submission_id: str, db: AsyncSession, student_user_id: str | None = None
) -> WritingReview:
    """Create the pending review for a freshly submitted response. The caller
    (submit flow) is responsible for committing.

    The review is created by the system (in response to a student submission),
    so the audit actor is 'system', not the student. The submitting student's
    user id is preserved in metadata for traceability."""
    review = WritingReview(
        submission_id=submission_id,
        status=WritingReviewStatus.pending,
    )
    db.add(review)
    await db.flush()
    await audit_service.log_action(
        db,
        action="writing_review.created",
        actor_user_id=None,
        actor_role="system",
        target_type="writing_review",
        target_id=review.id,
        metadata={"submission_id": submission_id, "student_user_id": student_user_id},
    )
    return review


# ── Internal helpers ─────────────────────────────────────────────────────────


async def _get_review(review_id: str, db: AsyncSession) -> WritingReview:
    result = await db.execute(select(WritingReview).where(WritingReview.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


async def _latest_feedback(review_id: str, db: AsyncSession) -> WritingFeedback | None:
    result = await db.execute(
        select(WritingFeedback)
        .where(WritingFeedback.review_id == review_id)
        .order_by(WritingFeedback.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _feedback_to_dict(fb: WritingFeedback | None) -> dict | None:
    if fb is None:
        return None
    return {
        "version": fb.version,
        "overall_comment": fb.overall_comment,
        "dimensions": fb.dimensions,
        "created_at": fb.created_at.isoformat() if fb.created_at else None,
    }


def _review_to_dict(review: WritingReview, latest_version: int | None = None) -> dict:
    return {
        "id": review.id,
        "submission_id": review.submission_id,
        "status": review.status.value,
        "reviewer_admin_id": review.reviewer_admin_id,
        "assigned_at": review.assigned_at.isoformat() if review.assigned_at else None,
        "review_started_at": review.review_started_at.isoformat() if review.review_started_at else None,
        "published_at": review.published_at.isoformat() if review.published_at else None,
        "latest_feedback_version": latest_version,
    }


# ── Admin: queue ─────────────────────────────────────────────────────────────


async def list_reviews(db: AsyncSession, status_str: str | None = None) -> list[dict]:
    stmt = (
        select(
            WritingReview,
            WritingSubmission,
            WritingTask.title,
            StudentProfile.display_name,
        )
        .join(WritingSubmission, WritingSubmission.id == WritingReview.submission_id)
        .join(WritingTask, WritingTask.id == WritingSubmission.writing_task_id)
        .join(StudentProfile, StudentProfile.id == WritingSubmission.student_id)
    )
    if status_str:
        stmt = stmt.where(WritingReview.status == _validate_review_status(status_str))
    stmt = stmt.order_by(WritingSubmission.submitted_at.desc())
    rows = (await db.execute(stmt)).all()

    # Latest feedback version per review, in one grouped query.
    versions = dict(
        (await db.execute(
            select(WritingFeedback.review_id, func.max(WritingFeedback.version))
            .group_by(WritingFeedback.review_id)
        )).all()
    )

    return [
        {
            **_review_to_dict(review, versions.get(review.id)),
            "task_title": task_title,
            "student_name": student_name,
            "word_count": submission.word_count,
            "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
        }
        for review, submission, task_title, student_name in rows
    ]


# ── Admin: detail (opening transitions to under_review) ──────────────────────


async def get_review_detail(
    review_id: str, actor_user_id: str | None, db: AsyncSession
) -> dict:
    review = await _get_review(review_id, db)

    # First open marks the review as started.
    if review.review_started_at is None and review.status in (
        WritingReviewStatus.pending,
        WritingReviewStatus.assigned,
    ):
        review.status = WritingReviewStatus.under_review
        review.review_started_at = datetime.now(tz=timezone.utc)
        await audit_service.log_action(
            db,
            action="writing_review.opened",
            actor_user_id=actor_user_id,
            actor_role="admin",
            target_type="writing_review",
            target_id=review.id,
        )
        await db.commit()
        await db.refresh(review)

    # Load submission + joined display fields.
    row = (await db.execute(
        select(WritingSubmission, WritingTask.title, StudentProfile.display_name)
        .join(WritingTask, WritingTask.id == WritingSubmission.writing_task_id)
        .join(StudentProfile, StudentProfile.id == WritingSubmission.student_id)
        .where(WritingSubmission.id == review.submission_id)
    )).first()
    submission, task_title, student_name = row

    fb = await _latest_feedback(review.id, db)
    return {
        **_review_to_dict(review, fb.version if fb else None),
        "submission": {
            "id": submission.id,
            "content": submission.content,
            "word_count": submission.word_count,
            "student_name": student_name,
            "task_title": task_title,
            "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
        },
        "feedback": _feedback_to_dict(fb),
    }


# ── Admin: assign ────────────────────────────────────────────────────────────


async def assign_review(
    review_id: str,
    reviewer_admin_id: str,
    actor_user_id: str | None,
    db: AsyncSession,
) -> dict:
    review = await _get_review(review_id, db)
    if review.status in (WritingReviewStatus.reviewed, WritingReviewStatus.published):
        raise HTTPException(status_code=422, detail="Cannot reassign a completed review")
    review.reviewer_admin_id = reviewer_admin_id
    review.assigned_at = datetime.now(tz=timezone.utc)
    review.status = WritingReviewStatus.assigned
    await audit_service.log_action(
        db,
        action="writing_review.assigned",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_review",
        target_id=review.id,
        metadata={"reviewer_admin_id": reviewer_admin_id},
    )
    await db.commit()
    await db.refresh(review)
    fb = await _latest_feedback(review.id, db)
    return _review_to_dict(review, fb.version if fb else None)


# ── Admin: feedback (versioned, append-only) ─────────────────────────────────


async def add_feedback(
    review_id: str,
    overall_comment: str,
    dimensions: list | None,
    admin_profile_id: str,
    actor_user_id: str | None,
    db: AsyncSession,
) -> dict:
    review = await _get_review(review_id, db)
    if review.status == WritingReviewStatus.published:
        raise HTTPException(
            status_code=422, detail="Cannot edit feedback after publishing"
        )

    current_max = (await db.execute(
        select(func.max(WritingFeedback.version)).where(WritingFeedback.review_id == review_id)
    )).scalar()
    next_version = (current_max or 0) + 1

    feedback = WritingFeedback(
        review_id=review_id,
        version=next_version,
        overall_comment=overall_comment,
        dimensions=dimensions,
        created_by_admin_id=admin_profile_id,
    )
    db.add(feedback)
    review.status = WritingReviewStatus.reviewed
    await audit_service.log_action(
        db,
        action="writing_feedback.created",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_review",
        target_id=review.id,
        metadata={"version": next_version},
    )
    await db.commit()
    await db.refresh(review)
    await db.refresh(feedback)
    return {
        **_review_to_dict(review, feedback.version),
        "feedback": _feedback_to_dict(feedback),
    }


# ── Admin: publish (gate) ────────────────────────────────────────────────────


async def publish_review(
    review_id: str, actor_user_id: str | None, db: AsyncSession
) -> dict:
    review = await _get_review(review_id, db)
    if review.status == WritingReviewStatus.published:
        raise HTTPException(status_code=422, detail="Review already published")
    if review.status != WritingReviewStatus.reviewed:
        raise HTTPException(
            status_code=422, detail="Cannot publish: review is not complete (no feedback)"
        )
    fb = await _latest_feedback(review.id, db)
    if fb is None:
        raise HTTPException(status_code=422, detail="Cannot publish without feedback")

    review.status = WritingReviewStatus.published
    review.published_at = datetime.now(tz=timezone.utc)
    await audit_service.log_action(
        db,
        action="writing_review.published",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_review",
        target_id=review.id,
        metadata={"feedback_version": fb.version},
    )
    await db.commit()
    await db.refresh(review)
    return _review_to_dict(review, fb.version)


# ── Student / Parent: published feedback visibility ──────────────────────────


async def get_published_feedback_for_submission(
    submission_id: str, db: AsyncSession
) -> dict:
    """Return the latest published feedback for a submission, or raise 404 if
    the submission has no review or the review is not yet published. Never
    leaks unpublished feedback to students or parents."""
    review = (await db.execute(
        select(WritingReview).where(WritingReview.submission_id == submission_id)
    )).scalar_one_or_none()
    if not review or review.status != WritingReviewStatus.published:
        raise HTTPException(status_code=404, detail="No published feedback")

    fb = await _latest_feedback(review.id, db)
    if fb is None:  # defensive — published implies feedback exists
        raise HTTPException(status_code=404, detail="No published feedback")

    return {
        "submission_id": submission_id,
        "version": fb.version,
        "overall_comment": fb.overall_comment,
        "dimensions": fb.dimensions,
        "published_at": review.published_at.isoformat() if review.published_at else None,
        "disclaimer": DISCLAIMER,
    }
