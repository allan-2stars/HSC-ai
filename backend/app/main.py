import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

logger = logging.getLogger("hsc-ai.system")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.DEBUG:
        from app.core.database import SessionLocal
        from app.services.system_service import run_startup_diagnostics

        # Any failure opening the DB session (unreachable, misconfigured) is fatal.
        # Failures inside run_startup_diagnostics raise SystemExit for DB, log and
        # continue for Redis/MinIO.
        try:
            async with SessionLocal() as db:
                await run_startup_diagnostics(db)
        except SystemExit:
            raise
        except Exception:
            logger.critical(
                "Cannot open database session at startup — "
                "check DATABASE_URL and PostgreSQL status"
            )
            raise SystemExit(1)
    yield


app = FastAPI(
    title="HSC AI Platform",
    description="NSW exam preparation platform — backend API",
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.v1.router import router as v1_router  # noqa: E402

app.include_router(v1_router)


@app.get("/api/health", tags=["health"])
async def health_check() -> dict:
    """Returns service status including live database and Redis connectivity checks."""
    from sqlalchemy import text
    from app.core.database import engine
    import redis.asyncio as aioredis

    db_status = "error"
    redis_status = "error"

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        pass

    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        redis_status = "ok"
    except Exception:
        pass

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"

    return {
        "status": overall,
        "service": "hsc-ai-backend",
        "version": settings.APP_VERSION,
        "database": db_status,
        "redis": redis_status,
    }


@app.get("/api/health/detailed", tags=["health"])
async def health_detailed() -> dict:
    """Public operational health — no user data, no row counts, no job details."""
    from app.core.database import SessionLocal
    from app.services.system_service import build_health_data

    async with SessionLocal() as db:
        return await build_health_data(db)
