"""M5.8 — Student Writing Portfolio. Read-only collection of published writing work.

- Published reviews only. No drafts, AI drafts, or score suggestions.
- Uses rubric/dimension version snapshots where available.
- Student/parent see only their own/child data. Admin can inspect any student.
"""
import logging
from collections import defaultdict

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import StudentProfile
from app.models.writing import (
    WritingFeedback,
    WritingReview,
    WritingReviewDispute,
    WritingReviewPublicationVersion,
    WritingReviewScore,
    WritingReviewStatus,
    WritingRubricDimension,
    WritingRubricDimensionVersion,
    WritingRubricVersion,
    WritingSubmission,
    WritingTask,
)

logger = logging.getLogger("hsc-ai.portfolio")

DISCLAIMER = (
    "Writing feedback is educational guidance and does not represent "
    "official Selective School marking."
)


def _empty_portfolio() -> dict:
    return {"items": [], "count": 0}


# ── Portfolio list ────────────────────────────────────────────────────────


async def build_portfolio_list(student_id: str, db: AsyncSession) -> dict:
    """Return all published portfolio items for a student, most recent first."""
    rows = (await db.execute(
        select(
            WritingSubmission.id,
            WritingTask.id,
            WritingTask.title,
            WritingSubmission.submitted_at,
            WritingReview.published_at,
            WritingSubmission.word_count,
            WritingReview.id,
        )
        .join(WritingReview, WritingReview.submission_id == WritingSubmission.id)
        .join(WritingTask, WritingTask.id == WritingSubmission.writing_task_id)
        .where(WritingSubmission.student_id == student_id)
        .where(WritingReview.status == WritingReviewStatus.published)
        .order_by(WritingReview.published_at.desc())
    )).all()

    if not rows:
        return _empty_portfolio()

    review_ids = [r[6] for r in rows]

    # Ratings per review
    score_rows = (await db.execute(
        select(WritingReviewScore.review_id, WritingRubricDimensionVersion.name, WritingReviewScore.rating)
        .outerjoin(WritingRubricDimensionVersion,
                   WritingRubricDimensionVersion.id == WritingReviewScore.dimension_version_id)
        .where(WritingReviewScore.review_id.in_(review_ids))
    )).all()

    review_ratings: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for rev_id, dim_name, rating in score_rows:
        if dim_name:
            review_ratings[rev_id].append((dim_name, rating))

    # Fallback: scores without dimension_version_id
    legacy = (await db.execute(
        select(WritingReviewScore.review_id, WritingRubricDimension.name, WritingReviewScore.rating)
        .join(WritingRubricDimension, WritingRubricDimension.id == WritingReviewScore.dimension_id)
        .where(WritingReviewScore.review_id.in_(review_ids))
        .where(WritingReviewScore.dimension_version_id.is_(None))
    )).all()
    for rev_id, dim_name, rating in legacy:
        review_ratings[rev_id].append((dim_name, rating))

    # Disputes
    dispute_map = dict(
        (await db.execute(
            select(WritingReviewDispute.review_id, func.count(WritingReviewDispute.id))
            .where(WritingReviewDispute.review_id.in_(review_ids))
            .group_by(WritingReviewDispute.review_id)
        )).all()
    )

    # Reopened
    reopen_map = dict(
        (await db.execute(
            select(WritingReviewPublicationVersion.review_id,
                   func.count(WritingReviewPublicationVersion.id))
            .where(WritingReviewPublicationVersion.review_id.in_(review_ids))
            .group_by(WritingReviewPublicationVersion.review_id)
        )).all()
    )

    # Latest feedback per review
    fb_rows = (await db.execute(
        select(WritingFeedback.review_id, WritingFeedback.overall_comment)
        .where(WritingFeedback.review_id.in_(review_ids))
        .order_by(WritingFeedback.version.desc())
    )).all()
    fb_map: dict[str, str] = {}
    for rid, comment in fb_rows:
        if rid not in fb_map:
            fb_map[rid] = comment

    items = []
    for sub_id, task_id, task_title, submitted_at, published_at, word_count, review_id in rows:
        dims = review_ratings.get(review_id, [])
        ratings = [r for _, r in dims]
        avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None

        # Strengths / weaknesses
        sorted_dims = sorted(dims, key=lambda x: x[1], reverse=True)
        strongest = [{"dimension_name": n, "rating": r} for n, r in sorted_dims[:2]]
        weakest = [{"dimension_name": n, "rating": r} for n, r in sorted_dims[-2:]] if len(sorted_dims) >= 2 else []

        items.append({
            "submission_id": sub_id,
            "task_id": task_id,
            "task_title": task_title,
            "submitted_at": submitted_at.isoformat() if submitted_at else None,
            "published_at": published_at.isoformat() if published_at else None,
            "word_count": word_count,
            "average_rating": avg_rating,
            "strongest_dimensions": strongest,
            "weakest_dimensions": weakest,
            "latest_feedback_summary": fb_map.get(review_id, "")[:200] if fb_map.get(review_id) else None,
            "has_dispute": dispute_map.get(review_id, 0) > 0,
            "was_reopened": reopen_map.get(review_id, 0) > 0,
        })

    return {"items": items, "count": len(items)}


# ── Portfolio detail ──────────────────────────────────────────────────────


async def build_portfolio_detail(submission_id: str, student_id: str, db: AsyncSession) -> dict:
    """Return full detail for a single portfolio item."""
    # Verify ownership
    sub = (await db.execute(
        select(WritingSubmission)
        .where(WritingSubmission.id == submission_id)
        .where(WritingSubmission.student_id == student_id)
    )).scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    review = (await db.execute(
        select(WritingReview)
        .where(WritingReview.submission_id == submission_id)
        .where(WritingReview.status == WritingReviewStatus.published)
    )).scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="No published review for this submission")

    task = (await db.execute(
        select(WritingTask).where(WritingTask.id == sub.writing_task_id)
    )).scalar_one_or_none()

    # Latest feedback
    fb = (await db.execute(
        select(WritingFeedback)
        .where(WritingFeedback.review_id == review.id)
        .order_by(WritingFeedback.version.desc())
        .limit(1)
    )).scalar_one_or_none()

    # Scores
    score_rows = (await db.execute(
        select(WritingReviewScore, WritingRubricDimensionVersion.name)
        .outerjoin(WritingRubricDimensionVersion,
                   WritingRubricDimensionVersion.id == WritingReviewScore.dimension_version_id)
        .where(WritingReviewScore.review_id == review.id)
    )).all()

    scores = []
    for s, dim_name in score_rows:
        name = dim_name or "Dimension"
        scores.append({
            "dimension_id": s.dimension_id,
            "name": name,
            "rating": s.rating,
            "comment": s.comment,
        })

    # Legacy fallback
    legacy_scores = (await db.execute(
        select(WritingReviewScore, WritingRubricDimension.name)
        .join(WritingRubricDimension, WritingRubricDimension.id == WritingReviewScore.dimension_id)
        .where(WritingReviewScore.review_id == review.id)
        .where(WritingReviewScore.dimension_version_id.is_(None))
    )).all()
    for s, dim_name in legacy_scores:
        existed = any(sc["dimension_id"] == s.dimension_id for sc in scores)
        if not existed:
            scores.append({
                "dimension_id": s.dimension_id,
                "name": dim_name,
                "rating": s.rating,
                "comment": s.comment,
            })

    # Rubric version title
    rubric_title = None
    if review.rubric_version_id:
        rv = (await db.execute(
            select(WritingRubricVersion.title)
            .where(WritingRubricVersion.id == review.rubric_version_id)
        )).scalar_one_or_none()
        rubric_title = rv

    # Publication version
    pub_ver = (await db.execute(
        select(func.max(WritingReviewPublicationVersion.version_number))
        .where(WritingReviewPublicationVersion.review_id == review.id)
    )).scalar() or 1

    # Disputes
    disputes = (await db.execute(
        select(WritingReviewDispute)
        .where(WritingReviewDispute.review_id == review.id)
        .order_by(WritingReviewDispute.created_at.desc())
    )).scalars().all()

    dispute_statuses = [
        {"id": d.id, "status": d.status.value, "reason": d.reason, "admin_response": d.admin_response}
        for d in disputes
    ]

    return {
        "submission_id": submission_id,
        "task_id": sub.writing_task_id,
        "task_title": task.title if task else None,
        "task_prompt": task.prompt if task else None,
        "task_instructions": task.instructions if task else None,
        "submitted_content": sub.content,
        "word_count": sub.word_count,
        "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
        "published_at": review.published_at.isoformat() if review.published_at else None,
        "publication_version": pub_ver,
        "was_reopened": pub_ver > 1,
        "rubric_title": rubric_title,
        "feedback": {
            "overall_comment": fb.overall_comment if fb else None,
            "version": fb.version if fb else None,
            "dimensions": fb.dimensions if fb else None,
        } if fb else None,
        "scores": scores,
        "disputes": dispute_statuses,
        "disclaimer": DISCLAIMER,
    }
