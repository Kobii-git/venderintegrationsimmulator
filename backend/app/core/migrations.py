from pathlib import Path

from alembic import command
from alembic.config import Config
from app.core.config import get_settings


def run_migrations() -> None:
    """Apply Alembic migrations to the configured database."""
    settings = get_settings()
    settings.ensure_data_dir()

    alembic_ini = Path(__file__).resolve().parents[2] / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini))
    alembic_cfg.set_main_option("script_location", str(alembic_ini.parent / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.resolved_database_url)
    command.upgrade(alembic_cfg, "head")
