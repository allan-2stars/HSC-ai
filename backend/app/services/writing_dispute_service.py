"""M5.5 — Disputes, reopen, and publication version history for writing reviews.

- Students/parents can raise a dispute against a published review.
- Admin can accept/reject/resolve disputes.
- Admin can reopen a published review (status → reopened).
- On republish, a WritingReviewPublicationVersion snapshot is created.
- Student/parent views show the latest publication version.
"""
import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import StudentProfile
from app.models.writing import (
    WritingDisputeStatus,
    WritingFeedback,
    WritingReview,
    WritingReviewDispute,
    WritingReviewPublicationVersion,
    WritingReviewStatus,
    WritingSubmission,
    WritingTask,
)
from app.services import audit_service

logger = logging.getLogger("hsc-ai.disputes")
DISCLAIMER = (
    "Writing feedback is educational guidance and does not represent "
    "official Selective School marking."
)


# ── Helpers ─────────────────────────────────────────────────────────────────


async def _get_review(review_id: str, db: AsyncSession) -> WritingReview:
    result = await db.execute(select(WritingReview).where(WritingReview.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


async def _get_dispute(dispute_id: str, db: AsyncSession) -> WritingReviewDispute:
    result = await db.execute(select(WritingReviewDispute).where(WritingReviewDispute.id == dispute_id))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Dispute not found")
    return d


async def _latest_publication_version(review_id: str, db: AsyncSession) -> WritingReviewPublicationVersion | None:
    result = await db.execute(
        select(WritingReviewPublicationVersion)
        .where(WritingReviewPublicationVersion.review_id == review_id)
        .order_by(WritingReviewPublicationVersion.version_number.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# ── Dispute creation (student/parent) ───────────────────────────────────────


async def create_dispute(
    review_id: str,
    reason: str,
    role: str,
    user_id: str | None,
    student_id: str | None,
    db: AsyncSession,
) -> dict:
    """Create a dispute against a published review. Called by students and parents.
    For students: the review must be for their submission. For parents: must be for
    one of their children."""
    review = await _get_review(review_id, db)

    if review.status != WritingReviewStatus.published:
        raise HTTPException(status_code=422, detail="Can only dispute a published review")

    # Verify the caller owns this review
    if role == "student" and student_id:
        sub_result = await db.execute(
            select(WritingSubmission.student_id)
            .where(WritingSubmission.id == review.submission_id)
        )
        submission_student_id = sub_result.scalar_one_or_none()
        if submission_student_id != student_id:
            raise HTTPException(status_code=403, detail="Not your submission")

    if role == "parent" and student_id:
        sub_result = await db.execute(
            select(WritingSubmission.student_id)
            .where(WritingSubmission.id == review.submission_id)
        )
        submission_student_id = sub_result.scalar_one_or_none()
        if submission_student_id != student_id:
            raise HTTPException(status_code=403, detail="Not your student's submission")

    dispute = WritingReviewDispute(
        review_id=review_id,
        raised_by_user_id=user_id,
        raised_by_role=role,
        reason=reason,
        status=WritingDisputeStatus.open,
    )
    db.add(dispute)
    await audit_service.log_action(
        db,
        action="writing_review.dispute_created",
        actor_user_id=user_id,
        actor_role=role,
        target_type="writing_review_dispute",
        target_id=dispute.id,
        metadata={"review_id": review_id},
    )
    await db.commit()
    await db.refresh(dispute)
    return _dispute_to_dict(dispute)


async def list_disputes_for_review(
    review_id: str, student_id: str | None, role: str, db: AsyncSession
) -> list[dict]:
    """List disputes visible to the caller. Students/parents see only their own;
    admins see all."""
    review = await _get_review(review_id, db)

    stmt = select(WritingReviewDispute).where(WritingReviewDispute.review_id == review_id)

    if role in ("student", "parent"):
        # Only see disputes raised by the caller
        sub_result = await db.execute(
            select(WritingSubmission.student_id)
            .where(WritingSubmission.id == review.submission_id)
        )
        submission_student_id = sub_result.scalar_one_or_none()
        if student_id and submission_student_id != student_id:
            raise HTTPException(status_code=403, detail="Not your submission")

    stmt = stmt.order_by(WritingReviewDispute.created_at.desc())
    result = await db.execute(stmt)
    return [_dispute_to_dict(d) for d in result.scalars().all()]


def _dispute_to_dict(d: WritingReviewDispute) -> dict:
    return {
        "id": d.id,
        "review_id": d.review_id,
        "raised_by_role": d.raised_by_role,
        "reason": d.reason,
        "status": d.status.value,
        "admin_response": d.admin_response,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "resolved_at": d.resolved_at.isoformat() if d.resolved_at else None,
    }


# ── Admin: dispute management ────────────────────────────────────────────────


async def list_all_disputes(db: AsyncSession, status_str: str | None = None) -> list[dict]:
    stmt = (
        select(WritingReviewDispute, WritingTask.title, StudentProfile.display_name)
        .join(WritingReview, WritingReview.id == WritingReviewDispute.review_id)
        .join(WritingSubmission, WritingSubmission.id == WritingReview.submission_id)
        .join(WritingTask, WritingTask.id == WritingSubmission.writing_task_id)
        .join(StudentProfile, StudentProfile.id == WritingSubmission.student_id)
    )
    if status_str:
        try:
            stmt = stmt.where(WritingReviewDispute.status == WritingDisputeStatus(status_str))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid dispute status: {status_str}")
    stmt = stmt.order_by(WritingReviewDispute.created_at.desc())
    rows = (await db.execute(stmt)).all()

    return [
        {
            **_dispute_to_dict(dispute),
            "task_title": task_title,
            "student_name": student_name,
        }
        for dispute, task_title, student_name in rows
    ]


async def accept_dispute(dispute_id: str, admin_profile_id: str, actor_user_id: str | None, db: AsyncSession) -> dict:
    d = await _get_dispute(dispute_id, db)
    if d.status != WritingDisputeStatus.open:
        raise HTTPException(status_code=422, detail="Dispute is not in open state")
    d.status = WritingDisputeStatus.accepted
    d.resolved_by_admin_id = admin_profile_id
    d.resolved_at = datetime.now(tz=timezone.utc)
    await audit_service.log_action(
        db,
        action="writing_review.dispute_accepted",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_review_dispute",
        target_id=dispute_id,
        metadata={"review_id": d.review_id},
    )
    await db.commit()
    await db.refresh(d)
    return _dispute_to_dict(d)


async def reject_dispute(
    dispute_id: str, admin_profile_id: str, response: str, actor_user_id: str | None, db: AsyncSession
) -> dict:
    d = await _get_dispute(dispute_id, db)
    if d.status != WritingDisputeStatus.open:
        raise HTTPException(status_code=422, detail="Dispute is not in open state")
    d.status = WritingDisputeStatus.rejected
    d.admin_response = response
    d.resolved_by_admin_id = admin_profile_id
    d.resolved_at = datetime.now(tz=timezone.utc)
    await audit_service.log_action(
        db,
        action="writing_review.dispute_rejected",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_review_dispute",
        target_id=dispute_id,
        metadata={"review_id": d.review_id},
    )
    await db.commit()
    await db.refresh(d)
    return _dispute_to_dict(d)


async def resolve_dispute(dispute_id: str, admin_profile_id: str, actor_user_id: str | None, db: AsyncSession) -> dict:
    d = await _get_dispute(dispute_id, db)
    if d.status not in (WritingDisputeStatus.accepted, WritingDisputeStatus.open):
        raise HTTPException(status_code=422, detail="Dispute is not in acceptable state")
    d.status = WritingDisputeStatus.resolved
    d.resolved_by_admin_id = admin_profile_id
    d.resolved_at = datetime.now(tz=timezone.utc)
    await audit_service.log_action(
        db,
        action="writing_review.dispute_resolved",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_review_dispute",
        target_id=dispute_id,
        metadata={"review_id": d.review_id},
    )
    await db.commit()
    await db.refresh(d)
    return _dispute_to_dict(d)


# ── Admin: reopen ───────────────────────────────────────────────────────────


async def reopen_review(review_id: str, actor_user_id: str | None, db: AsyncSession) -> dict:
    """Reopen a published review for revision. Changes status to reopened so the
    reviewer can edit feedback/scores."""
    review = await _get_review(review_id, db)
    if review.status != WritingReviewStatus.published:
        raise HTTPException(status_code=422, detail="Can only reopen a published review")

    review.status = WritingReviewStatus.reopened
    await audit_service.log_action(
        db,
        action="writing_review.reopened",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_review",
        target_id=review_id,
    )
    await db.commit()
    await db.refresh(review)
    return {
        "id": review.id,
        "status": review.status.value,
        "submission_id": review.submission_id,
    }


# ── Admin: republish ────────────────────────────────────────────────────────


async def republish_review(review_id: str, actor_user_id: str, admin_profile_id: str, db: AsyncSession) -> dict:
    """Republish a reopened review. Creates a new publication version snapshot."""
    review = await _get_review(review_id, db)
    if review.status not in (WritingReviewStatus.reviewed, WritingReviewStatus.reopened):
        raise HTTPException(
            status_code=422,
            detail="Can only republish a reviewed or reopened review. Save feedback first.",
        )

    from app.services.writing_review_service import _latest_feedback
    fb = await _latest_feedback(review.id, db)
    if fb is None:
        raise HTTPException(status_code=422, detail="Cannot republish without feedback")

    from app.services import writing_rubric_service
    await writing_rubric_service.assert_rubric_complete_for_publish(review, db)

    # Bind latest rubric version
    rubric_id = await writing_rubric_service._review_task_rubric_id(review, db)
    if rubric_id:
        latest_version = await writing_rubric_service._latest_version(rubric_id, db)
        if latest_version:
            review.rubric_version_id = latest_version.id

    # Determine next publication version number
    current_max = (await db.execute(
        select(func.max(WritingReviewPublicationVersion.version_number))
        .where(WritingReviewPublicationVersion.review_id == review_id)
    )).scalar()
    next_version = (current_max or 0) + 1

    # Build snapshot
    from app.services.writing_rubric_service import _dimensions_for_review, _review_task_rubric_id as _rtri
    rubric_block = await writing_rubric_service.rubric_block_for_review(review, db)
    snapshot = {
        "overall_comment": fb.overall_comment,
        "dimensions": fb.dimensions,
        "rubric": rubric_block["scores"] if rubric_block else [],
        "rubric_title": rubric_block["title"] if rubric_block else None,
        "disclaimer": DISCLAIMER,
    }

    pub_version = WritingReviewPublicationVersion(
        review_id=review_id,
        version_number=next_version,
        rubric_version_id=review.rubric_version_id,
        feedback_id=fb.id,
        published_by_admin_id=admin_profile_id,
        snapshot_json=snapshot,
    )
    db.add(pub_version)

    review.status = WritingReviewStatus.published
    review.published_at = datetime.now(tz=timezone.utc)

    await audit_service.log_action(
        db,
        action="writing_review.republished",
        actor_user_id=actor_user_id,
        actor_role="admin",
        target_type="writing_review",
        target_id=review_id,
        metadata={"version_number": next_version, "feedback_version": fb.version},
    )
    await db.commit()
    await db.refresh(review)
    await db.refresh(pub_version)
    return {
        "id": review.id,
        "status": review.status.value,
        "publication_version": next_version,
        "published_at": review.published_at.isoformat() if review.published_at else None,
    }


# ── Admin: publication version history ──────────────────────────────────────


async def list_publication_versions(review_id: str, db: AsyncSession) -> list[dict]:
    await _get_review(review_id, db)
    result = await db.execute(
        select(WritingReviewPublicationVersion)
        .where(WritingReviewPublicationVersion.review_id == review_id)
        .order_by(WritingReviewPublicationVersion.version_number.desc())
    )
    versions = result.scalars().all()
    return [
        {
            "id": v.id,
            "version_number": v.version_number,
            "rubric_version_id": v.rubric_version_id,
            "feedback_id": v.feedback_id,
            "published_at": v.published_at.isoformat() if v.published_at else None,
            "published_by_admin_id": v.published_by_admin_id,
        }
        for v in versions
    ]


async def get_publication_version_detail(version_id: str, db: AsyncSession) -> dict:
    result = await db.execute(
        select(WritingReviewPublicationVersion)
        .where(WritingReviewPublicationVersion.id == version_id)
    )
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Publication version not found")
    return {
        "id": v.id,
        "version_number": v.version_number,
        "review_id": v.review_id,
        "published_at": v.published_at.isoformat() if v.published_at else None,
        "snapshot": v.snapshot_json,
    }
