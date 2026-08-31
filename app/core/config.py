from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Student Management System"
    environment: str = "development"
    database_url: str = "sqlite:///./data/student_management.db"
    jwt_secret: str = "development-only-change-this-secret"
    jwt_expire_minutes: int = 30
    cookie_secure: bool = False
    storage_path: Path = Path("storage")
    export_path: Path = Path("exports")
    backup_path: Path = Path("backups")
    backup_offsite_path: Path | None = None
    backup_interval_hours: int = 24
    backup_retention_days: int = 30
    backup_encrypt: bool = True
    audit_retention_days: int = 3650
    quality_stale_days: int = 180
    task_retention_days: int = 14
    task_workers: int = 2
    recycle_retention_days: int = 30
    source_retention_days: int = 3650
    data_encryption_key: str | None = None
    alert_disk_free_gb: int = 10
    alert_task_failure_threshold: int = 3
    notification_webhook_url: str | None = None
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "student-qwen-cuda:latest"
    ai_enabled: bool = True
    update_repository: str = "Star-Moon10/Student-Management-System"
    update_channel: str = "stable"
    update_github_token: str | None = None
    update_max_package_mb: int = 300

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_production and settings.jwt_secret == "development-only-change-this-secret":
        raise RuntimeError("JWT_SECRET must be configured in production")
    if settings.is_production and not settings.cookie_secure:
        raise RuntimeError("COOKIE_SECURE must be enabled in production")
    return settings
