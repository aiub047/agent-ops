"""
Error handler middleware.

Maps domain exceptions from app.core.exceptions to structured JSON HTTP responses
so that no raw Python exceptions are ever returned to API consumers.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.exceptions import AgentOpsError
from app.core.logging import get_logger
from app.models.common import ErrorResponse

logger = get_logger(__name__)


async def agent_ops_exception_handler(request: Request, exc: AgentOpsError) -> JSONResponse:
    """
    Convert AgentOpsError subclasses into a standard ErrorResponse JSON body.

    Args:
        request: The incoming HTTP request (used for logging context).
        exc: The raised domain exception.

    Returns:
        JSONResponse with the appropriate HTTP status code.
    """
    logger.warning(
        "Domain error [%s] on %s %s: %s",
        type(exc).__name__,
        request.method,
        request.url.path,
        exc.message,
    )
    body = ErrorResponse(error=exc.message)
    return JSONResponse(status_code=exc.http_status, content=body.model_dump())


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all for unexpected exceptions.

    Logs the full traceback and returns a generic 500 response without
    leaking internal details to the caller.

    Args:
        request: The incoming HTTP request.
        exc: The unexpected exception.

    Returns:
        JSONResponse with status 500.
    """
    logger.exception(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    body = ErrorResponse(error="An internal server error occurred.")
    return JSONResponse(status_code=500, content=body.model_dump())


async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """
    Convert Pydantic ValidationError into a structured 422 response.

    Args:
        request: The incoming HTTP request.
        exc: The Pydantic validation error.

    Returns:
        JSONResponse with status 422.
    """
    body = ErrorResponse(
        error="Request validation failed.",
        details=[
            {"field": " → ".join(str(loc) for loc in e["loc"]), "message": e["msg"]}
            for e in exc.errors()
        ],
    )
    return JSONResponse(status_code=422, content=body.model_dump())

