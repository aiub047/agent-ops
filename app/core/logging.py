"""
Structured logging configuration for the application.

Uses JSON format in production and human-readable format for local/dev.
"""

import logging
import sys
from typing import Any

from app.core.config import get_settings


class _JsonFormatter(logging.Formatter):
    """Minimal JSON log formatter for structured logging in production."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        import traceback

        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineNo": record.lineno,
        }
        if record.exc_info:
            payload["exception"] = traceback.format_exception(*record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    """
    Configure the root logger based on the current environment.

    - Production: JSON structured output to stdout.
    - Local/Dev: Human-readable output with colour-friendly format.
    """
    settings = get_settings()
    level = logging.getLevelName(settings.LOG_LEVEL.upper())

    handler = logging.StreamHandler(sys.stdout)

    if settings.APP_ENV == "prod":
        handler.setFormatter(_JsonFormatter())
    else:
        fmt = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d - %(message)s"
        handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # Silence noisy third-party loggers
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        logging.Logger: Configured logger instance.
    """
    return logging.getLogger(name)

