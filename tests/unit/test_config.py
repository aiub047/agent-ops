"""
Unit tests for Settings configuration loading.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.config import Settings, get_settings


class TestSettings:
    def test_defaults(self) -> None:
        settings = Settings()
        assert settings.APP_ENV == "local"
        assert settings.AWS_REGION == "us-east-1"
        assert settings.AGENT_DEFINITION_DIR == "agent-definition"
        assert settings.LOG_LEVEL == "INFO"

    def test_env_override(self) -> None:
        with patch.dict(os.environ, {"AWS_REGION": "eu-west-1", "LOG_LEVEL": "DEBUG"}):
            settings = Settings()
            assert settings.AWS_REGION == "eu-west-1"
            assert settings.LOG_LEVEL == "DEBUG"

    def test_env_file_loading(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env.test"
        env_file.write_text("AWS_REGION=ap-southeast-1\nLOG_LEVEL=WARNING\n", encoding="utf-8")
        settings = Settings(_env_file=str(env_file))
        assert settings.AWS_REGION == "ap-southeast-1"
        assert settings.LOG_LEVEL == "WARNING"

    def test_get_settings_is_cached(self) -> None:
        """get_settings() must return the same instance on repeated calls."""
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
        get_settings.cache_clear()

    def test_app_env_validation(self) -> None:
        """APP_ENV must be one of: local, dev, prod."""
        with pytest.raises(Exception):
            Settings(APP_ENV="staging")  # type: ignore[arg-type]

