"""
Domain exception hierarchy for agent-ops.

All application-specific exceptions inherit from AgentOpsError so that
the middleware can catch and convert them into appropriate HTTP responses
without leaking internal details to API consumers.
"""

from http import HTTPStatus


class AgentOpsError(Exception):
    """Base exception for all agent-ops domain errors."""

    http_status: int = HTTPStatus.INTERNAL_SERVER_ERROR.value
    default_message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


# ── Agent Definition errors ───────────────────────────────────────────────────

class AgentDefinitionNotFoundError(AgentOpsError):
    """Raised when the requested agent definition YAML file does not exist."""

    http_status = HTTPStatus.NOT_FOUND.value
    default_message = "Agent definition file not found."


class AgentDefinitionParseError(AgentOpsError):
    """Raised when a YAML definition file cannot be parsed or fails schema validation."""

    http_status = HTTPStatus.UNPROCESSABLE_ENTITY.value
    default_message = "Agent definition file is invalid or malformed."


# ── Bedrock / AWS errors ──────────────────────────────────────────────────────

class AgentNotFoundError(AgentOpsError):
    """Raised when a Bedrock agent with the given ID does not exist."""

    http_status = HTTPStatus.NOT_FOUND.value
    default_message = "Agent not found."


class BedrockServiceError(AgentOpsError):
    """Raised when an AWS Bedrock API call fails."""

    http_status = HTTPStatus.BAD_GATEWAY.value
    default_message = "Bedrock service error."


class AgentConflictError(AgentOpsError):
    """Raised when an agent with the same name already exists."""

    http_status = HTTPStatus.CONFLICT.value
    default_message = "An agent with the same name already exists."

