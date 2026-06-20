"""M5.7 — Student Writing Analytics. Read-only analytics over published review data.

- Uses published reviews only. Excludes drafts, unpublished, AI drafts, score suggestions.
- Uses rubric/dimension version snapshots where available, falls back to live dimensions.
- Student/parent see only their own/child data. Admin gets aggregate.
- No mutation of any existing data.
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

logger = logging.getLogger("hsc-ai.writing-analytics")


def _empty_analytics() -> dict:
    return {
        "summary": {
            "published_reviews": 0,
            "average_rating": None,
            "average_word_count": None,
            "disputes_count": 0,
            "reopened_count": 0,
        },
        "dimension_averages": [],
        "progress_over_time": [],
        "strengths": [],
        "weaknesses": [],
        "latest_feedback": None,
    }


async def build_student_analytics(student_id: str, db: AsyncSession) -> dict:
    """Build full analytics for a single student."""
    rows = (await db.execute(
        select(
            WritingReview.id,
            WritingReview.published_at,
            WritingSubmission.word_count,
            WritingTask.title,
        )
        .join(WritingSubmission, WritingSubmission.id == WritingReview.submission_id)
        .join(WritingTask, WritingTask.id == WritingSubmission.writing_task_id)
        .where(WritingSubmission.student_id == student_id)
        .where(WritingReview.status == WritingReviewStatus.published)
        .order_by(WritingReview.published_at.asc())
    )).all()

    if not rows:
        return _empty_analytics()

    review_ids = [r[0] for r in rows]

    # Ratings — try dimension_version first, fall back to live dimensions
    score_rows_v = (await db.execute(
        select(WritingReviewScore.review_id, WritingRubricDimensionVersion.name, WritingReviewScore.rating)
        .outerjoin(WritingRubricDimensionVersion, WritingRubricDimensionVersion.id == WritingReviewScore.dimension_version_id)
        .where(WritingReviewScore.review_id.in_(review_ids))
    )).all()

    ratings_by_dim: dict[str, list[int]] = defaultdict(list)
    review_ratings: dict[str, list[int]] = defaultdict(list)

    for rev_id, dim_name, rating in score_rows_v:
        if dim_name:
            ratings_by_dim[dim_name].append(rating)
            review_ratings[rev_id].append(rating)

    # Fallback — scores without dimension_version_id
    legacy = (await db.execute(
        select(WritingReviewScore.review_id, WritingRubricDimension.name, WritingReviewScore.rating)
        .join(WritingRubricDimension, WritingRubricDimension.id == WritingReviewScore.dimension_id)
        .where(WritingReviewScore.review_id.in_(review_ids))
        .where(WritingReviewScore.dimension_version_id.is_(None))
    )).all()
    for rev_id, dim_name, rating in legacy:
        ratings_by_dim[dim_name].append(rating)
        review_ratings[rev_id].append(rating)

    # Counts
    dispute_count = (await db.execute(
        select(func.count(WritingReviewDispute.id)).where(WritingReviewDispute.review_id.in_(review_ids))
    )).scalar() or 0

    reopened_count = (await db.execute(
        select(func.count(WritingReviewPublicationVersion.id)).where(WritingReviewPublicationVersion.review_id.in_(review_ids))
    )).scalar() or 0

    all_ratings = [r for ratings in review_ratings.values() for r in ratings]
    avg_rating = round(sum(all_ratings) / len(all_ratings), 1) if all_ratings else None
    avg_word_count = round(sum(r[2] for r in rows) / len(rows), 1) if rows else None

    dimension_averages = [
        {"dimension_name": name, "average_rating": round(sum(ratios) / len(ratios), 1), "attempts": len(ratios)}
        for name, ratios in sorted(ratings_by_dim.items())
    ]

    # Strengths / weaknesses
    qualified = [(d["dimension_name"], d["average_rating"]) for d in dimension_averages]
    qualified.sort(key=lambda x: x[1], reverse=True)
    strengths = [{"dimension_name": n, "average_rating": r} for n, r in qualified[:3]]
    weaknesses = [{"dimension_name": n, "average_rating": r} for n, r in qualified[-3:]] if len(qualified) >= 2 else []

    progress = []
    for r in rows:
        rev_id, pub_at, wc, task_title = r[0], r[1], r[2], r[3]
        ratings = review_ratings.get(rev_id, [])
        avg = round(sum(ratings) / len(ratings), 1) if ratings else None
        progress.append({
            "published_at": pub_at.isoformat() if pub_at else None,
            "task_title": task_title,
            "average_rating": avg,
            "word_count": wc,
        })

    latest_feedback = None
    if rows:
        last_review_id = rows[-1][0]
        fb_row = (await db.execute(
            select(WritingFeedback.overall_comment, WritingTask.title, WritingReview.published_at)
            .join(WritingReview, WritingReview.id == WritingFeedback.review_id)
            .join(WritingSubmission, WritingSubmission.id == WritingReview.submission_id)
            .join(WritingTask, WritingTask.id == WritingSubmission.writing_task_id)
            .where(WritingFeedback.review_id == last_review_id)
            .order_by(WritingFeedback.version.desc())
            .limit(1)
        )).first()
        if fb_row:
            latest_feedback = {
                "task_title": fb_row[1],
                "published_at": fb_row[2].isoformat() if fb_row[2] else None,
                "overall_comment": fb_row[0],
            }

    return {
        "summary": {
            "published_reviews": len(rows),
            "average_rating": avg_rating,
            "average_word_count": avg_word_count,
            "disputes_count": dispute_count,
            "reopened_count": reopened_count,
        },
        "dimension_averages": dimension_averages,
        "progress_over_time": progress,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "latest_feedback": latest_feedback,
    }


async def build_task_analytics(student_id: str, db: AsyncSession) -> list[dict]:
    """Per-task breakdown for a student."""
    rows = (await db.execute(
        select(
            WritingTask.id,
            WritingTask.title,
            WritingReview.published_at,
            WritingSubmission.word_count,
            WritingReview.id,
        )
        .join(WritingSubmission, WritingSubmission.writing_task_id == WritingTask.id)
        .join(WritingReview, WritingReview.submission_id == WritingSubmission.id)
        .where(WritingSubmission.student_id == student_id)
        .where(WritingReview.status == WritingReviewStatus.published)
        .order_by(WritingReview.published_at.desc())
    )).all()

    results = []
    for task_id, title, published_at, word_count, review_id in rows:
        avg_r = (await db.execute(
            select(func.avg(WritingReviewScore.rating))
            .where(WritingReviewScore.review_id == review_id)
        )).scalar()
        results.append({
            "task_id": task_id,
            "task_title": title,
            "published_at": published_at.isoformat() if published_at else None,
            "word_count": word_count,
            "average_rating": round(float(avg_r), 1) if avg_r else None,
        })
    return results


async def build_admin_overview(db: AsyncSession) -> dict:
    """Aggregate writing analytics for admin dashboard."""
    published_count = (await db.execute(
        select(func.count(WritingReview.id))
        .where(WritingReview.status == WritingReviewStatus.published)
    )).scalar() or 0

    all_avg = (await db.execute(
        select(func.avg(WritingReviewScore.rating))
        .join(WritingReview, WritingReview.id == WritingReviewScore.review_id)
        .where(WritingReview.status == WritingReviewStatus.published)
    )).scalar()

    avg_word = (await db.execute(
        select(func.avg(WritingSubmission.word_count))
        .join(WritingReview, WritingReview.submission_id == WritingSubmission.id)
        .where(WritingReview.status == WritingReviewStatus.published)
    )).scalar()

    dispute_count = (await db.execute(
        select(func.count(WritingReviewDispute.id))
    )).scalar() or 0

    dim_rows = (await db.execute(
        select(
            WritingRubricDimensionVersion.name,
            func.avg(WritingReviewScore.rating),
            func.count(WritingReviewScore.id),
        )
        .join(WritingReview, WritingReview.id == WritingReviewScore.review_id)
        .join(WritingRubricDimensionVersion,
              WritingRubricDimensionVersion.id == WritingReviewScore.dimension_version_id)
        .where(WritingReview.status == WritingReviewStatus.published)
        .group_by(WritingRubricDimensionVersion.name)
        .order_by(func.avg(WritingReviewScore.rating))
    )).all()

    dim_averages = [
        {"dimension_name": name, "average_rating": round(float(avg), 1), "count": int(cnt)}
        for name, avg, cnt in dim_rows
    ]

    recent = (await db.execute(
        select(
            WritingTask.title,
            StudentProfile.display_name,
            WritingReview.published_at,
            WritingSubmission.word_count,
        )
        .join(WritingSubmission, WritingSubmission.id == WritingReview.submission_id)
        .join(WritingTask, WritingTask.id == WritingSubmission.writing_task_id)
        .join(StudentProfile, StudentProfile.id == WritingSubmission.student_id)
        .where(WritingReview.status == WritingReviewStatus.published)
        .order_by(WritingReview.published_at.desc())
        .limit(10)
    )).all()

    recent_activity = [
        {"task_title": t, "student_name": s, "published_at": p.isoformat() if p else None, "word_count": w}
        for t, s, p, w in recent
    ]

    return {
        "published_reviews": published_count,
        "average_rating": round(float(all_avg), 1) if all_avg else None,
        "average_word_count": round(float(avg_word), 1) if avg_word else None,
        "disputes_count": dispute_count,
        "dimension_averages": dim_averages,
        "recent_activity": recent_activity,
    }
