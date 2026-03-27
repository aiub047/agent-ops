"""
Request logging middleware.

Logs every incoming request and its response status/duration so that
operational issues can be diagnosed from logs alone.
"""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that logs request metadata and response status for every
    HTTP call.  A unique ``X-Request-ID`` header is injected into each response
    so that distributed traces can be correlated.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        logger.info(
            "→ %s %s  request_id=%s",
            request.method,
            request.url.path,
            request_id,
        )

        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "← %s %s  status=%d  duration=%.1fms  request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        response.headers["X-Request-ID"] = request_id
        return response

