from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database — postgresql+asyncpg driver required
    DATABASE_URL: str = "postgresql+asyncpg://hscai:hscai@localhost:5432/hscai"

    # Redis — used for session storage and ARQ job queue
    REDIS_URL: str = "redis://localhost:6379/0"

    # MinIO — S3-compatible object storage (self-hosted)
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "hscai"
    MINIO_SECURE: bool = False

    # CORS — comma-separated list parsed at startup
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
