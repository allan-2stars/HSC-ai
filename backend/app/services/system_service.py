"""System health and admin metrics service."""
import logging
import os
import time

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ai_job import AIGenerationJob, AIGenerationJobStatus
from app.models.base import Base
from app.models.exam import ExamTemplate, ExamTemplateStatus
from app.models.import_job import ImportJob, ImportJobStatus
from app.models.ocr_job import OCRJob, OCRJobStatus
from app.models.question import Question, QuestionStatus
from app.models.user import User, UserRole
from app.models.assignment import AssignedExam

logger = logging.getLogger("hsc-ai.system")

_START_TIME = time.time()
_LAST_LOGIN_CUTOFF_OVERRIDE: float | None = None  # epoch timestamp for testing


def set_last_login_cutoff_override(seconds_ago: float) -> None:
    """Override the 24h cutoff for testing. Pass seconds ago (e.g. 3600 for 1 hour)."""
    global _LAST_LOGIN_CUTOFF_OVERRIDE
    _LAST_LOGIN_CUTOFF_OVERRIDE = time.time() - seconds_ago


def clear_last_login_cutoff_override() -> None:
    global _LAST_LOGIN_CUTOFF_OVERRIDE
    _LAST_LOGIN_CUTOFF_OVERRIDE = None


# ── Health checks ──────────────────────────────────────────────────────────


async def check_database(db: AsyncSession) -> str:
    try:
        await db.execute(text("SELECT 1"))
        await db.commit()
        return "ok"
    except Exception as e:
        await db.rollback()
        logger.error("Database health check failed: %s", e)
        return "error"


async def check_redis() -> str:
    try:
        import redis.asyncio as aioredis  # noqa: F811

        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        return "ok"
    except Exception as e:
        logger.error("Redis health check failed: %s", e)
        return "error"


async def check_storage() -> str:
    try:
        import asyncio
        from minio import Minio  # noqa: F811

        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        await asyncio.to_thread(client.list_buckets)
        return "ok"
    except Exception as e:
        logger.error("Storage health check failed: %s", e)
        return "error"


async def get_migration_version(db: AsyncSession) -> str:
    try:
        result = await db.execute(text("SELECT version_num FROM alembic_version"))
        row = result.fetchone()
        return row[0] if row else "unknown"
    except Exception:
        await db.rollback()
        return "unknown"


def get_uptime_seconds() -> float:
    return time.time() - _START_TIME


def get_memory_usage_mb() -> float:
    """Returns RSS in MB. Uses resource module on Unix, psutil on Windows, or 0 as fallback."""
    try:
        import resource
        usage_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if os.name == "posix":
            return usage_kb / 1024.0  # Linux: KB → MB
        return usage_kb / 1048576.0  # macOS: bytes → MB
    except ImportError:
        try:
            import psutil
            return psutil.Process().memory_info().rss / 1048576.0
        except ImportError:
            return 0.0


async def build_health_data(db: AsyncSession) -> dict:
    return {
        "database_status": await check_database(db),
        "redis_status": await check_redis(),
        "storage_status": await check_storage(),
        "migration_version": await get_migration_version(db),
        "uptime_seconds": get_uptime_seconds(),
        "memory_usage_mb": round(get_memory_usage_mb(), 1),
    }


# ── User activity ──────────────────────────────────────────────────────────


async def get_active_user_counts(db: AsyncSession) -> dict:
    from datetime import datetime, timedelta, timezone

    cutoff_dt = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    if _LAST_LOGIN_CUTOFF_OVERRIDE is not None:
        cutoff_dt = datetime.fromtimestamp(_LAST_LOGIN_CUTOFF_OVERRIDE, tz=timezone.utc)

    async def _count(role: UserRole | None, label: str) -> int:
        stmt = select(func.count(User.id))
        if role:
            stmt = stmt.where(User.role == role, User.last_login_at >= cutoff_dt)
        else:
            stmt = stmt.where(User.last_login_at >= cutoff_dt)
        result = await db.execute(stmt)
        return result.scalar() or 0

    total = await _count(None, "all")
    parents = await _count(UserRole.parent, "parent")
    students = await _count(UserRole.student, "student")
    admins = await _count(UserRole.admin, "admin")

    total_users_result = await db.execute(select(func.count(User.id)))
    total_users = total_users_result.scalar() or 0

    return {
        "total_users": total_users,
        "active_users_24h": total,
        "active_parents_24h": parents,
        "active_students_24h": students,
        "active_admins_24h": admins,
    }


# ── Content / platform counts ──────────────────────────────────────────────


async def get_content_counts(db: AsyncSession) -> dict:
    result = await db.execute(
        select(
            func.count(Question.id).label("total"),
            func.count(Question.id).filter(Question.status == QuestionStatus.published).label("published"),
        )
    )
    row = result.one()
    return {
        "total_questions": row.total,
        "published_questions": row.published or 0,
    }


async def get_platform_counts(db: AsyncSession) -> dict:
    exams_result = await db.execute(
        select(func.count(ExamTemplate.id))
        .where(ExamTemplate.status == ExamTemplateStatus.published)
    )
    assignments_result = await db.execute(
        select(func.count(AssignedExam.id))
    )
    return {
        "total_exams": exams_result.scalar() or 0,
        "total_assignments": assignments_result.scalar() or 0,
    }


# ── Job auditing ───────────────────────────────────────────────────────────


async def get_job_summary(db: AsyncSession) -> dict:
    ocr = await _job_counts(db, OCRJob)
    ai = await _job_counts(db, AIGenerationJob)
    imports = await _job_counts(db, ImportJob)
    return {
        "ocr_jobs": ocr,
        "ai_jobs": ai,
        "import_jobs": imports,
    }


async def _job_counts(db: AsyncSession, model) -> dict:
    from app.models.ai_job import AIGenerationJob

    # AI generation jobs have no "processing" state — only pending/completed/failed
    if model is AIGenerationJob:
        active_statuses = ["pending"]
    else:
        active_statuses = ["pending", "processing"]

    result = await db.execute(
        select(
            func.count(model.id).label("total"),
            func.count(model.id).filter(model.status.in_(active_statuses)).label("active"),
            func.count(model.id).filter(model.status == 'completed').label("completed"),
            func.count(model.id).filter(model.status == 'failed').label("failed"),
        )
    )
    row = result.one()
    return {
        "total": row.total,
        "active": row.active or 0,
        "completed": row.completed or 0,
        "failed": row.failed or 0,
    }


async def get_failed_jobs(db: AsyncSession) -> list[dict]:
    jobs = []

    # OCR failed jobs
    ocr_result = await db.execute(
        select(OCRJob)
        .where(OCRJob.status == OCRJobStatus.failed)
        .order_by(OCRJob.created_at.desc())
        .limit(50)
    )
    for j in ocr_result.scalars().all():
        jobs.append({
            "type": "ocr",
            "id": j.id,
            "filename": j.filename,
            "status": "failed",
            "error": j.error_message,
            "created_at": j.created_at,
        })

    # AI generation failed jobs
    ai_result = await db.execute(
        select(AIGenerationJob)
        .where(AIGenerationJob.status == AIGenerationJobStatus.failed)
        .order_by(AIGenerationJob.created_at.desc())
        .limit(50)
    )
    for j in ai_result.scalars().all():
        jobs.append({
            "type": "ai_generation",
            "id": j.id,
            "provider": j.provider,
            "status": "failed",
            "error": j.error_message,
            "created_at": j.created_at,
        })

    # Import failed jobs
    import_result = await db.execute(
        select(ImportJob)
        .where(ImportJob.status == ImportJobStatus.failed)
        .order_by(ImportJob.created_at.desc())
        .limit(50)
    )
    for j in import_result.scalars().all():
        jobs.append({
            "type": "import",
            "id": j.id,
            "filename": j.filename,
            "status": "failed",
            "error": j.error_message,
            "created_at": j.created_at,
        })

    return sorted(jobs, key=lambda j: str(j["created_at"]), reverse=True)


async def get_orphaned_jobs(db: AsyncSession) -> list[dict]:
    """Pending jobs never started within ORPHAN_JOB_THRESHOLD_HOURS — worker likely crashed."""
    from datetime import datetime, timedelta, timezone

    threshold = datetime.now(tz=timezone.utc) - timedelta(hours=settings.ORPHAN_JOB_THRESHOLD_HOURS)
    orphaned = []

    ocr_result = await db.execute(
        select(OCRJob)
        .where(OCRJob.status == OCRJobStatus.pending, OCRJob.created_at < threshold)
        .order_by(OCRJob.created_at)
        .limit(50)
    )
    for j in ocr_result.scalars().all():
        orphaned.append({
            "type": "ocr",
            "id": j.id,
            "filename": j.filename,
            "status": "orphaned",
            "created_at": j.created_at,
            "hours_pending": round((datetime.now(tz=timezone.utc) - j.created_at).total_seconds() / 3600, 1),
        })

    import_result = await db.execute(
        select(ImportJob)
        .where(ImportJob.status == ImportJobStatus.pending, ImportJob.created_at < threshold)
        .order_by(ImportJob.created_at)
        .limit(50)
    )
    for j in import_result.scalars().all():
        orphaned.append({
            "type": "import",
            "id": j.id,
            "filename": j.filename,
            "status": "orphaned",
            "created_at": j.created_at,
            "hours_pending": round((datetime.now(tz=timezone.utc) - j.created_at).total_seconds() / 3600, 1),
        })

    return sorted(orphaned, key=lambda j: j.get("hours_pending", 0), reverse=True)


async def get_stuck_jobs(db: AsyncSession) -> list[dict]:
    from datetime import datetime, timedelta, timezone

    threshold = datetime.now(tz=timezone.utc) - timedelta(minutes=settings.STUCK_JOB_THRESHOLD_MINUTES)
    stuck = []

    # OCR stuck: processing but started_at older than threshold
    ocr_result = await db.execute(
        select(OCRJob)
        .where(
            OCRJob.status == OCRJobStatus.processing,
            OCRJob.started_at.isnot(None),
            OCRJob.started_at < threshold,
        )
        .order_by(OCRJob.started_at)
        .limit(50)
    )
    for j in ocr_result.scalars().all():
        stuck.append({
            "type": "ocr",
            "id": j.id,
            "filename": j.filename,
            "status": "stuck",
            "started_at": j.started_at,
            "duration_minutes": round((datetime.now(tz=timezone.utc) - j.started_at).total_seconds() / 60, 1),
        })

    # AI generation stuck: pending for too long (no "processing" state for AI jobs)
    ai_result = await db.execute(
        select(AIGenerationJob)
        .where(
            AIGenerationJob.status == AIGenerationJobStatus.pending,
            AIGenerationJob.created_at < threshold,
        )
        .order_by(AIGenerationJob.created_at)
        .limit(50)
    )
    for j in ai_result.scalars().all():
        stuck.append({
            "type": "ai_generation",
            "id": j.id,
            "provider": j.provider,
            "status": "stuck",
            "created_at": j.created_at,
            "duration_minutes": round((datetime.now(tz=timezone.utc) - j.created_at).total_seconds() / 60, 1) if j.created_at else 0,
        })

    # Import stuck
    import_result = await db.execute(
        select(ImportJob)
        .where(
            ImportJob.status == ImportJobStatus.processing,
            ImportJob.started_at.isnot(None),
            ImportJob.started_at < threshold,
        )
        .order_by(ImportJob.started_at)
        .limit(50)
    )
    for j in import_result.scalars().all():
        stuck.append({
            "type": "import",
            "id": j.id,
            "filename": j.filename,
            "status": "stuck",
            "started_at": j.started_at,
            "duration_minutes": round((datetime.now(tz=timezone.utc) - j.started_at).total_seconds() / 60, 1),
        })

    return sorted(stuck, key=lambda j: j.get("duration_minutes", 0), reverse=True)


# ── Table counts ───────────────────────────────────────────────────────────


async def get_table_counts(db: AsyncSession) -> dict[str, int]:
    """High-level table row counts only. No sensitive table data exposed."""
    tables = ["users", "questions", "question_versions", "exam_templates",
              "assigned_exams", "attempts", "ocr_jobs", "ai_generation_jobs",
              "import_jobs", "question_quality_reviews"]
    counts = {}
    for table in tables:
        try:
            result = await db.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
            row = result.fetchone()
            counts[table] = row[0] if row else 0
        except Exception:
            counts[table] = -1
    return counts


# ── Full dashboard ─────────────────────────────────────────────────────────


async def get_admin_system_dashboard(db: AsyncSession) -> dict:
    from app.core.database import engine

    db_status = "ok"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    health = {
        "database_status": db_status,
        "redis_status": await check_redis(),
        "storage_status": await check_storage(),
        "migration_version": await get_migration_version(db),
        "uptime_seconds": get_uptime_seconds(),
        "memory_usage_mb": round(get_memory_usage_mb(), 1),
    }

    active = await get_active_user_counts(db)
    content = await get_content_counts(db)
    platform = await get_platform_counts(db)
    jobs = await get_job_summary(db)
    failed = await get_failed_jobs(db)
    stuck = await get_stuck_jobs(db)
    orphaned = await get_orphaned_jobs(db)
    table_counts = await get_table_counts(db)

    return {
        **health,
        **active,
        **content,
        **platform,
        "jobs": jobs,
        "failed_jobs": failed,
        "stuck_jobs": stuck,
        "orphaned_jobs": orphaned,
        "table_counts": table_counts,
    }


# ── Startup diagnostics ────────────────────────────────────────────────────


async def run_startup_diagnostics(db: AsyncSession) -> None:
    logger.info("Starting HSC-ai backend — environment: %s", "development" if settings.DEBUG else "production")
    logger.info("App version: %s", settings.APP_VERSION)

    migration = await get_migration_version(db)
    logger.info("Migration version: %s", migration)

    db_ok = await check_database(db)
    if db_ok != "ok":
        logger.critical("Database connectivity check FAILED — check DATABASE_URL and PostgreSQL status")
        raise SystemExit(1)
    logger.info("Database connectivity: ok")

    redis_ok = await check_redis()
    if redis_ok != "ok":
        logger.critical("Redis connectivity check FAILED — background jobs and caching degraded")
    else:
        logger.info("Redis connectivity: ok")

    storage_ok = await check_storage()
    if storage_ok != "ok":
        logger.warning("Storage (MinIO) connectivity check FAILED — storage features degraded")
    else:
        logger.info("Storage connectivity: ok")

    logger.info("Startup diagnostics complete — server ready")
