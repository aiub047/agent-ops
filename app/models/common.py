"""
Common Pydantic models shared across API request and response schemas.
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Single error detail item."""

    field: str | None = None
    message: str


class ErrorResponse(BaseModel):
    """Standard error response body returned for all HTTP error responses."""

    error: str
    details: list[ErrorDetail] = Field(default_factory=list)
    request_id: str | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated list response."""

    items: list[T]
    total: int
    next_token: str | None = Field(None, alias="nextToken")

    model_config = {"populate_by_name": True}


class HealthResponse(BaseModel):
    """Response body for the health-check endpoint."""

    status: str = "ok"
    version: str
    environment: str
    extra: dict[str, Any] = Field(default_factory=dict)

