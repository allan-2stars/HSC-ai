from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

app = FastAPI(
    title="HSC AI Platform",
    description="NSW exam preparation platform — backend API",
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
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
