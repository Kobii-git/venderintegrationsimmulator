from app.core.config import AppEnvironment, get_settings


def test_settings_defaults(test_settings) -> None:
    settings = test_settings
    assert settings.app_name == "Integration Simulator"
    assert settings.app_environment == AppEnvironment.DEVELOPMENT
    assert settings.log_level == "WARNING"
    assert settings.resolved_database_url.startswith("sqlite:///")


def test_settings_database_url_override(monkeypatch, tmp_path) -> None:
    custom_url = f"sqlite:///{tmp_path}/custom.db"
    monkeypatch.setenv("DATABASE_URL", custom_url)
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.resolved_database_url == custom_url
    get_settings.cache_clear()


def test_settings_ensure_data_dir(test_settings) -> None:
    settings = test_settings
    settings.ensure_data_dir()
    assert settings.resolved_data_dir.is_dir()
