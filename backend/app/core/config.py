from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Integration Simulator"
    app_version: str = "0.4.0"
    app_environment: AppEnvironment = AppEnvironment.DEVELOPMENT
    debug: bool = False
    log_level: str = "INFO"

    # Paths
    data_dir: str = "./data"
    database_url: str | None = None
    products_dir: str = "products"
    static_dir: str | None = None

    # Security
    secret_key: str | None = None

    # Simulation runtime / scheduler
    scheduler_min_interval_seconds: int = 1
    scheduler_max_interval_seconds: int = 3600
    scheduler_max_event_count: int = 10_000
    scheduler_max_concurrent_simulations: int = 10
    scheduler_resume_on_restart: bool = False

    # Event/delivery history retention
    event_retention_days: int = 30
    event_retention_max_per_simulation: int = 10_000
    event_retention_cleanup_on_startup: bool = True
    event_retention_cleanup_interval_seconds: int = 3600

    # Fault injection safety limits
    fault_max_burst_count: int = 50
    fault_max_burst_rate_per_second: float = 5.0
    fault_large_run_confirmation_threshold: int = 20
    fault_max_delivery_delay_ms: int = 30_000
    fault_max_duplicate_sends: int = 3
    fault_max_large_field_kb: int = 512

    # Security / deployment
    enable_openapi_docs: bool = True
    ssrf_warn_on_private_destinations: bool = True

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.upper()

    @field_validator("event_retention_cleanup_interval_seconds")
    @classmethod
    def validate_cleanup_interval(cls, value: int) -> int:
        if value < 60:
            raise ValueError("event_retention_cleanup_interval_seconds must be at least 60")
        return value

    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    @property
    def resolved_data_dir(self) -> Path:
        path = Path(self.data_dir)
        if path.is_absolute():
            return path
        return self.repo_root / path

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        db_path = self.resolved_data_dir / "integration_simulator.db"
        return f"sqlite:///{db_path}"

    @property
    def resolved_products_dir(self) -> str:
        path = Path(self.products_dir)
        if path.is_absolute():
            return str(path)
        return str(self.repo_root / self.products_dir)

    @property
    def resolved_static_dir(self) -> Path:
        if self.static_dir:
            path = Path(self.static_dir)
            return path if path.is_absolute() else self.repo_root / path
        return self.repo_root / "frontend" / "dist"

    def ensure_data_dir(self) -> None:
        """Create data directory if it does not exist."""
        self.resolved_data_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
