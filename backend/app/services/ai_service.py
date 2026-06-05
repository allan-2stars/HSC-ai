"""AI question generation — provider calling, validation, preview, and execution."""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_job import AIGenerationJob, AIGenerationJobStatus
from app.models.content import ExamType, Subject
from app.models.curriculum import CurriculumOutcome, QuestionOutcomeMapping
from app.models.question import (
    ContentOwnershipType,
    DifficultyLevel,
    Question,
    QuestionStatus,
    QuestionType,
    QuestionVersion,
    SourceType,
)
from app.services.ai_providers import (
    GenerationParams,
    _estimate_cost,
    get_provider,
)

_VALID_DIFFICULTIES = {"easy", "medium", "hard"}


# ── Preview ──────────────────────────────────────────────────────────────────

async def preview_generation(
    outcome_id: str,
    subject_id: str,
    exam_type_id: str,
    count: int,
    difficulty_mix: dict,
    provider_name: str,
    db: AsyncSession,
) -> dict:
    """Generate preview questions without saving. Returns {questions, job_summary}."""
    outcome = await db.get(CurriculumOutcome, outcome_id)
    if not outcome:
        raise HTTPException(status_code=404, detail="Outcome not found")

    subject = await db.get(Subject, subject_id) if subject_id else None
    exam_type = await db.get(ExamType, exam_type_id) if exam_type_id else None

    provider = get_provider(provider_name)
    params = GenerationParams(
        outcome_code=outcome.code,
        outcome_title=outcome.title,
        subject_name=subject.name if subject else "",
        exam_type_name=exam_type.name if exam_type else "",
        count=count,
        difficulty_mix=difficulty_mix,
    )

    try:
        generated, token_usage = await provider(params)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Provider error: {e}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Provider API error: {e}")

    questions = []
    valid_count = 0
    invalid_count = 0

    for q in generated:
        errors = _validate_generated_question(q)
        questions.append({
            "question_text": q.question_text,
            "options": q.options,
            "correct_answer": q.correct_answer,
            "explanation": q.explanation,
            "difficulty": q.difficulty,
            "curriculum_outcome_code": q.curriculum_outcome_code,
            "provider": q.provider,
            "valid": len(errors) == 0,
            "errors": errors,
        })
        if errors:
            invalid_count += 1
        else:
            valid_count += 1

    estimated_cost = _estimate_cost(provider_name, token_usage) if token_usage else 0.0

    return {
        "questions": questions,
        "summary": {
            "total": len(generated),
            "valid": valid_count,
            "invalid": invalid_count,
            "estimated_cost": estimated_cost,
        },
    }


def _validate_generated_question(q) -> list[str]:
    """Validate a generated question. Returns list of error messages."""
    errors = []
    if not q.question_text or len(q.question_text.strip()) < 10:
        errors.append("question_text too short")
    if not q.options or len(q.options) < 2:
        errors.append("insufficient options (need 2+)")
    true_count = sum(1 for o in q.options if o.get("is_correct"))
    if true_count != 1:
        errors.append(f"expected exactly 1 correct answer, got {true_count}")
    if not q.correct_answer or not any(o.get("label") == q.correct_answer for o in q.options):
        errors.append("correct_answer does not match any option label")
    if q.difficulty not in _VALID_DIFFICULTIES:
        errors.append(f"invalid difficulty: {q.difficulty}")
    if not q.explanation or len(q.explanation.strip()) < 10:
        errors.append("explanation too short")
    return errors


# ── Execute ──────────────────────────────────────────────────────────────────

async def execute_generation(
    params: dict,
    admin_id: str,
    db: AsyncSession,
) -> AIGenerationJob:
    """Generate, validate, and save questions as draft."""
    outcome = await db.get(CurriculumOutcome, params["outcome_id"])
    if not outcome:
        raise HTTPException(status_code=404, detail="Outcome not found")

    # Create job
    job = AIGenerationJob(
        provider=params["provider"],
        framework_id=params.get("framework_id"),
        outcome_id=params["outcome_id"],
        subject_id=params["subject_id"],
        exam_type_id=params["exam_type_id"],
        requested_count=params["count"],
        difficulty_mix_json=params["difficulty_mix"],
        status=AIGenerationJobStatus.pending,
        created_by_admin_id=admin_id,
    )
    db.add(job)
    await db.commit()

    # Generate
    subject = await db.get(Subject, params["subject_id"]) if params.get("subject_id") else None
    exam_type = await db.get(ExamType, params["exam_type_id"]) if params.get("exam_type_id") else None

    provider = get_provider(params["provider"])
    gen_params = GenerationParams(
        outcome_code=outcome.code,
        outcome_title=outcome.title,
        subject_name=subject.name if subject else "",
        exam_type_name=exam_type.name if exam_type else "",
        count=params["count"],
        difficulty_mix=params["difficulty_mix"],
    )

    try:
        generated, token_usage = await provider(gen_params)
    except ValueError as e:
        job.status = AIGenerationJobStatus.failed
        job.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=422, detail=f"Provider error: {e}")
    except Exception as e:
        job.status = AIGenerationJobStatus.failed
        job.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=502, detail=f"Provider API error: {e}")

    job.generated_count = len(generated)
    if token_usage:
        job.token_usage_json = token_usage
        job.estimated_cost = _estimate_cost(params["provider"], token_usage)

    # Save valid questions
    saved = 0
    rejected = 0
    for q in generated:
        errors = _validate_generated_question(q)
        if errors:
            rejected += 1
            continue

        try:
            question = Question(
                subject_id=params["subject_id"],
                exam_type_id=params["exam_type_id"],
                year_level=5,
                difficulty=DifficultyLevel(q.difficulty),
                question_type=QuestionType.mcq,
                status=QuestionStatus.draft,
                source_type=SourceType.ai,
                content_ownership=ContentOwnershipType.original,
                created_by_admin_id=admin_id,
                current_version_id=None,
            )
            db.add(question)
            await db.flush()

            version = QuestionVersion(
                question_id=question.id,
                version_number=1,
                stem=q.question_text,
                correct_answer=q.correct_answer,
                full_explanation=q.explanation,
                marks=1,
                options_json=q.options,
                created_by_admin_id=admin_id,
                created_at=datetime.now(tz=timezone.utc),
            )
            db.add(version)
            await db.flush()
            question.current_version_id = version.id

            # Auto-map to outcome
            mapping = QuestionOutcomeMapping(
                question_id=question.id,
                outcome_id=outcome.id,
                weight=1.0,
            )
            db.add(mapping)
            saved += 1

        except Exception:
            rejected += 1

    job.saved_count = saved
    job.rejected_count = rejected
    job.status = AIGenerationJobStatus.completed
    job.completed_at = datetime.now(tz=timezone.utc)
    await db.commit()
    await db.refresh(job)
    return job


# ── Jobs ─────────────────────────────────────────────────────────────────────

async def list_ai_jobs(db: AsyncSession) -> list[AIGenerationJob]:
    result = await db.execute(
        select(AIGenerationJob).order_by(AIGenerationJob.created_at.desc()).limit(50)
    )
    return list(result.scalars().all())


async def get_ai_job(job_id: str, db: AsyncSession) -> AIGenerationJob:
    result = await db.execute(select(AIGenerationJob).where(AIGenerationJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="AI generation job not found")
    return job
