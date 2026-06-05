from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.curriculum import (
    CurriculumFramework,
    CurriculumOutcome,
    QuestionOutcomeMapping,
)
from app.models.question import Question, QuestionStatus


# ── Framework CRUD ───────────────────────────────────────────────────────────

async def create_framework(
    name: str,
    db: AsyncSession,
    description: str | None = None,
    exam_type_id: str | None = None,
    version: str = "2026",
) -> CurriculumFramework:
    framework = CurriculumFramework(
        name=name.strip(),
        description=description,
        exam_type_id=exam_type_id,
        version=version,
    )
    db.add(framework)
    await db.commit()
    return await get_framework(framework.id, db)


async def get_framework(framework_id: str, db: AsyncSession) -> CurriculumFramework:
    result = await db.execute(
        select(CurriculumFramework)
        .options(selectinload(CurriculumFramework.outcomes))
        .where(CurriculumFramework.id == framework_id)
    )
    fw = result.scalar_one_or_none()
    if not fw:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Framework not found")
    return fw


async def list_frameworks(db: AsyncSession) -> list[CurriculumFramework]:
    result = await db.execute(
        select(CurriculumFramework)
        .options(selectinload(CurriculumFramework.outcomes))
        .order_by(CurriculumFramework.name)
    )
    return list(result.scalars().all())


# ── Outcome CRUD ─────────────────────────────────────────────────────────────

async def create_outcome(
    framework_id: str,
    code: str,
    title: str,
    db: AsyncSession,
    description: str | None = None,
    sort_order: int = 0,
) -> CurriculumOutcome:
    await get_framework(framework_id, db)

    existing = await db.execute(
        select(CurriculumOutcome).where(CurriculumOutcome.code == code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Outcome with code '{code}' already exists",
        )

    outcome = CurriculumOutcome(
        framework_id=framework_id,
        code=code.strip(),
        title=title.strip(),
        description=description,
        sort_order=sort_order,
    )
    db.add(outcome)
    await db.commit()
    await db.refresh(outcome)
    return outcome


async def list_outcomes(
    db: AsyncSession,
    framework_id: str | None = None,
) -> list[CurriculumOutcome]:
    query = select(CurriculumOutcome)
    if framework_id:
        query = query.where(CurriculumOutcome.framework_id == framework_id)
    result = await db.execute(query.order_by(CurriculumOutcome.sort_order))
    return list(result.scalars().all())


# ── Question Mapping ─────────────────────────────────────────────────────────

async def create_question_mapping(
    question_id: str,
    outcome_id: str,
    db: AsyncSession,
    weight: float = 1.0,
) -> QuestionOutcomeMapping:
    question = await db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    outcome = await db.get(CurriculumOutcome, outcome_id)
    if not outcome:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outcome not found")

    # Check for duplicate
    existing = await db.execute(
        select(QuestionOutcomeMapping).where(
            QuestionOutcomeMapping.question_id == question_id,
            QuestionOutcomeMapping.outcome_id == outcome_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Question is already mapped to this outcome",
        )

    mapping = QuestionOutcomeMapping(
        question_id=question_id,
        outcome_id=outcome_id,
        weight=weight,
    )
    db.add(mapping)
    await db.commit()
    await db.refresh(mapping)
    return mapping


async def delete_question_mapping(mapping_id: str, db: AsyncSession) -> None:
    mapping = await db.get(QuestionOutcomeMapping, mapping_id)
    if not mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found")
    await db.delete(mapping)
    await db.commit()


# ── Coverage Calculation ─────────────────────────────────────────────────────

_COVERAGE_THRESHOLDS = {
    "red": 0,
    "amber": 25,
    "green": 100,
}


def _coverage_status(count: int) -> str:
    if count < _COVERAGE_THRESHOLDS["amber"]:
        return "red"
    elif count < _COVERAGE_THRESHOLDS["green"]:
        return "amber"
    return "green"


async def get_framework_coverage(
    framework_id: str, db: AsyncSession
) -> dict:
    framework = await get_framework(framework_id, db)
    outcomes = framework.outcomes

    if not outcomes:
        return {
            "framework_id": framework_id,
            "framework_name": framework.name,
            "total_outcomes": 0,
            "mapped_outcomes": 0,
            "covered_outcomes": 0,
            "coverage_percentage": 0.0,
            "outcomes": [],
        }

    outcome_ids = [o.id for o in outcomes]

    # Count approved questions per outcome
    result = await db.execute(
        select(
            CurriculumOutcome.id,
            func.count(Question.id).label("approved_count"),
        )
        .outerjoin(
            QuestionOutcomeMapping,
            QuestionOutcomeMapping.outcome_id == CurriculumOutcome.id,
        )
        .outerjoin(Question, Question.id == QuestionOutcomeMapping.question_id)
        .where(
            CurriculumOutcome.id.in_(outcome_ids),
            ((Question.status == QuestionStatus.approved) | (Question.status == QuestionStatus.published) | (Question.id.is_(None))),
        )
        .group_by(CurriculumOutcome.id)
    )
    approved_by_outcome = {row[0]: row[1] for row in result.fetchall()}

    # Count draft questions per outcome
    result = await db.execute(
        select(
            CurriculumOutcome.id,
            func.count(Question.id).label("draft_count"),
        )
        .outerjoin(
            QuestionOutcomeMapping,
            QuestionOutcomeMapping.outcome_id == CurriculumOutcome.id,
        )
        .outerjoin(Question, Question.id == QuestionOutcomeMapping.question_id)
        .where(
            CurriculumOutcome.id.in_(outcome_ids),
            ((Question.status.notin_([QuestionStatus.approved, QuestionStatus.published])) | (Question.id.is_(None))),
        )
        .group_by(CurriculumOutcome.id)
    )
    draft_by_outcome = {row[0]: row[1] for row in result.fetchall()}

    mapped_count = 0
    covered_count = 0
    outcome_items = []

    for o in outcomes:
        approved = approved_by_outcome.get(o.id, 0)
        draft = draft_by_outcome.get(o.id, 0)
        total = approved + draft

        if total > 0:
            mapped_count += 1
        if approved > 0:
            covered_count += 1

        outcome_items.append({
            "outcome_id": o.id,
            "code": o.code,
            "title": o.title,
            "approved_question_count": approved,
            "draft_question_count": draft,
            "total_question_count": total,
            "coverage_status": _coverage_status(approved),
        })

    total = len(outcomes)
    coverage_pct = round((covered_count / total) * 100, 1) if total > 0 else 0.0

    red_count = sum(1 for o in outcome_items if o["coverage_status"] == "red")
    amber_count = sum(1 for o in outcome_items if o["coverage_status"] == "amber")
    green_count = sum(1 for o in outcome_items if o["coverage_status"] == "green")

    return {
        "framework_id": framework_id,
        "framework_name": framework.name,
        "total_outcomes": total,
        "mapped_outcomes": mapped_count,
        "covered_outcomes": covered_count,
        "coverage_percentage": coverage_pct,
        "red_count": red_count,
        "amber_count": amber_count,
        "green_count": green_count,
        "outcomes": outcome_items,
    }


async def get_unmapped_questions(db: AsyncSession) -> list[dict]:
    """Return questions with no outcome mappings."""
    subquery = (
        select(QuestionOutcomeMapping.question_id)
        .distinct()
    )
    result = await db.execute(
        select(Question)
        .options(selectinload(Question.current_version))
        .where(Question.id.notin_(subquery))
        .order_by(Question.created_at.desc())
        .limit(200)
    )
    questions = list(result.scalars().all())

    return [
        {
            "question_id": q.id,
            "stem": (q.current_version.stem if q.current_version else "")[:200],
            "status": q.status.value if hasattr(q.status, "value") else str(q.status),
            "subject_name": None,
        }
        for q in questions
    ]


# ── Dashboard Summary ────────────────────────────────────────────────────────

async def get_dashboard_summary(db: AsyncSession) -> dict:
    """Aggregated curriculum coverage summary across all frameworks."""
    frameworks = await list_frameworks(db)

    framework_summaries = []
    total_outcomes = 0
    total_mapped = 0
    total_covered = 0
    all_gaps: list[dict] = []

    for fw in frameworks:
        coverage = await get_framework_coverage(fw.id, db)
        total_outcomes += coverage["total_outcomes"]
        total_mapped += coverage["mapped_outcomes"]
        total_covered += coverage["covered_outcomes"]

        red_count = sum(1 for o in coverage["outcomes"] if o["coverage_status"] == "red")
        amber_count = sum(1 for o in coverage["outcomes"] if o["coverage_status"] == "amber")
        green_count = sum(1 for o in coverage["outcomes"] if o["coverage_status"] == "green")

        framework_summaries.append({
            "framework_id": fw.id,
            "framework_name": fw.name,
            "total_outcomes": coverage["total_outcomes"],
            "mapped_outcomes": coverage["mapped_outcomes"],
            "covered_outcomes": coverage["covered_outcomes"],
            "coverage_percentage": coverage["coverage_percentage"],
            "red_count": red_count,
            "amber_count": amber_count,
            "green_count": green_count,
        })

        # Collect top gaps: outcomes with 0 approved questions, sorted
        for o in coverage["outcomes"]:
            if o["coverage_status"] == "red" and o["total_question_count"] == 0:
                all_gaps.append({
                    "framework_name": fw.name,
                    "outcome_code": o["code"],
                    "outcome_title": o["title"],
                    "outcome_id": o["outcome_id"],
                })

    overall_pct = round((total_covered / total_outcomes) * 100, 1) if total_outcomes > 0 else 0.0

    # Unmapped questions count
    unmapped = await get_unmapped_questions(db)
    all_red_outcomes = total_outcomes - total_covered if total_outcomes > 0 else 0

    return {
        "overall_coverage_pct": overall_pct,
        "total_frameworks": len(frameworks),
        "total_outcomes": total_outcomes,
        "total_mapped": total_mapped,
        "total_covered": total_covered,
        "unmapped_question_count": len(unmapped),
        "all_red_outcome_count": all_red_outcomes,
        "frameworks": framework_summaries,
        "top_gaps": all_gaps[:20],
    }
