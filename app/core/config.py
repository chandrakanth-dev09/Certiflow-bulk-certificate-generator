from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "CertiFlow"
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "sqlite:///./certiflow.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None
    STORAGE_DIR: str = "storage/certificates"
    MAX_BATCH_SIZE: int = 500
    MAX_CSV_SIZE: int = 5 * 1024 * 1024
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
BASE_DIR = Path(__file__).resolve().parents[2]
