from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import AnyHttpUrl, BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AcademicPeriod(BaseModel):
    start: str = Field(..., description="Fecha de inicio (YYYY-MM-DD)")
    end: str = Field(..., description="Fecha de cierre (YYYY-MM-DD)")
    total_weeks: int = Field(..., ge=1, description="Cantidad de semanas académicas")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_token: str = Field(alias="TELEGRAM_TOKEN")
    telegram_admin_ids: str = Field(alias="TELEGRAM_ADMIN_IDS")
    bot_language: str = Field(default="es", alias="BOT_LANGUAGE")
    bot_log_level: str = Field(default="INFO", alias="BOT_LOG_LEVEL")

    database_url: str = Field(alias="DATABASE_URL")
    sync_database_url: str = Field(alias="SYNC_DATABASE_URL")
    db_pool_size: int = Field(default=10, alias="DB_POOL_SIZE")
    db_echo: bool = Field(default=False, alias="DB_ECHO")

    redis_url: str = Field(alias="REDIS_URL")
    redis_bot_prefix: str = Field(default="cisec", alias="REDIS_BOT_PREFIX")

    api_base_url: AnyHttpUrl = Field(alias="API_BASE_URL")
    fastapi_host: str = Field(default="0.0.0.0", alias="FASTAPI_HOST")
    fastapi_port: int = Field(default=8000, alias="FASTAPI_PORT")

    ollama_base_url: AnyHttpUrl = Field(alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3:8b-instruct", alias="OLLAMA_MODEL")
    ollama_timeout_seconds: int = Field(default=60, alias="OLLAMA_TIMEOUT_SECONDS")
    ollama_max_tokens: int = Field(default=512, alias="OLLAMA_MAX_TOKENS")
    ollama_temperature: float = Field(default=0.6, alias="OLLAMA_TEMPERATURE")

    academic_period: AcademicPeriod = Field(
        default_factory=lambda: AcademicPeriod(start="2025-09-08", end="2025-12-20", total_weeks=15),
        alias="ACADEMIC_PERIOD",
    )

    period_start: str = Field(default="2025-09-08", alias="PERIOD_START")
    period_end: str = Field(default="2025-12-20", alias="PERIOD_END")
    total_weeks: int = Field(default=15, alias="TOTAL_WEEKS")

    data_dir: str = Field(default="./data", alias="DATA_DIR")
    syllabus_dir: str = Field(default="./data/syllabus", alias="SYLLABUS_DIR")
    patient_notes_dir: str = Field(default="./data/patient_notes", alias="PATIENT_NOTES_DIR")
    ifom_json_path: str = Field(default="./data/ifom_bank.json", alias="IFOM_JSON_PATH")

    rate_limit_per_minute: int = Field(default=20, alias="RATE_LIMIT_PER_MINUTE")
    broadcast_chunk_size: int = Field(default=25, alias="BROADCAST_CHUNK_SIZE")

    default_patient_slug: str = Field(default="sofia-gastro", alias="DEFAULT_PATIENT_SLUG")

    @property
    def admin_ids(self) -> List[int]:
        return [int(i.strip()) for i in self.telegram_admin_ids.split(",") if i.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
