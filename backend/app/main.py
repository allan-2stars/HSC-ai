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


@app.get("/api/health", tags=["health"])
async def health_check() -> dict:
    """
    Health check endpoint.

    Returns service status. Does not verify database connectivity in M0;
    dependency checks are added in Milestone 1 alongside migrations.
    """
    return {
        "status": "ok",
        "service": "hsc-ai-backend",
        "version": settings.APP_VERSION,
    }
