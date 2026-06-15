from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database — postgresql+asyncpg driver
    DATABASE_URL: str = "postgresql+asyncpg://hscai:hscai@postgres:5432/hscai"

    # Alembic runs on the host; needs localhost instead of the Docker service name.
    # Defaults to DATABASE_URL with @postgres: replaced by @localhost:
    ALEMBIC_DATABASE_URL: str = ""

    def get_alembic_url(self) -> str:
        if self.ALEMBIC_DATABASE_URL:
            return self.ALEMBIC_DATABASE_URL
        return self.DATABASE_URL.replace("@postgres:", "@localhost:")

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # MinIO
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "hscai"
    MINIO_SECURE: bool = False

    # CORS
    CORS_ORIGINS: str = "http://localhost:3090,http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # ── JWT ──────────────────────────────────────────────────────────
    # M1: HS256 with a shared secret (temporary).
    # Plan: migrate to RS256 in M2 by providing JWT_PRIVATE_KEY / JWT_PUBLIC_KEY.
    # IMPORTANT: set JWT_SECRET_KEY to a long random string in production.
    JWT_SECRET_KEY: str = "CHANGE_ME_USE_LONG_RANDOM_SECRET_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Operations ─────────────────────────────────────────────────────
    STUCK_JOB_THRESHOLD_MINUTES: int = 30  # processing jobs older than this are "stuck"
    ORPHAN_JOB_THRESHOLD_HOURS: int = 24  # pending jobs older than this are "orphaned"
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"


settings = Settings()
