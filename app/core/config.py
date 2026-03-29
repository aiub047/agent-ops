"""
Configuration management using Pydantic BaseSettings.

Loads settings from environment variables and .env files based on the APP_ENV value.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Supports multiple environments: local, dev, prod.
    All sensitive values must be provided via environment variables
    and must never be hardcoded in the codebase.
    """

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    APP_NAME: str = "agent-ops-api"
    APP_VERSION: str = "1.0.13"
    APP_ENV: Literal["local", "dev", "prod"] = "local"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── AWS ───────────────────────────────────────────────────────────────────
    AWS_REGION: str = "us-east-1"
    AWS_PROFILE: str | None = None  # For local/dev; use IAM role in prod
    AWS_ACCESS_KEY_ID: str | None = None  # Optional; prefer profile or IAM role
    AWS_SECRET_ACCESS_KEY: str | None = None

    # ── Bedrock ───────────────────────────────────────────────────────────────
    # Optional fallback role ARN used when an agent definition does not specify
    # its own roleArn under spec.k8s. Each agent should ideally declare
    # its own role in the YAML definition for least-privilege isolation.
    DEFAULT_BEDROCK_AGENT_ROLE_ARN: str | None = None

    # ── Agent definitions ─────────────────────────────────────────────────────
    AGENT_DEFINITION_DIR: str = "agent-definition"


@lru_cache
def get_settings() -> Settings:
    """
    Return a cached Settings instance.

    The appropriate .env file is selected based on the APP_ENV environment
    variable so that `APP_ENV=dev` loads `.env.dev`, etc.

    Returns:
        Settings: The application settings instance.
    """
    import os

    app_env = os.getenv("APP_ENV", "local")
    env_file = ENV_DIR / f".env.{app_env}"
    return Settings(_env_file=str(env_file))  # type: ignore[call-arg]
