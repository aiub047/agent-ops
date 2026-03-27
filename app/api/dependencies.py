"""
FastAPI dependency providers.

All injectable objects (settings, repositories, services) are defined here as
``Depends``-compatible functions so they can be overridden in tests with ease.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.repositories.agent_definition_repository import AgentDefinitionRepository
from app.repositories.bedrock_repository import BedrockRepository
from app.services.bedrock_agent_service import BedrockAgentService


# ── Settings ──────────────────────────────────────────────────────────────────

SettingsDep = Annotated[Settings, Depends(get_settings)]


# ── Repositories ──────────────────────────────────────────────────────────────

@lru_cache
def get_bedrock_repository() -> BedrockRepository:
    """Provide a cached BedrockRepository instance.

    Calls get_settings() directly (already cached via lru_cache) so that
    this function takes no arguments and remains safely hashable by lru_cache.
    Pydantic BaseSettings objects are not hashable, so they must never be
    passed as arguments to an lru_cache-decorated function.
    """
    settings = get_settings()
    return BedrockRepository(
        region_name=settings.AWS_REGION,
        profile_name=settings.AWS_PROFILE,
    )


@lru_cache
def get_definition_repository() -> AgentDefinitionRepository:
    """Provide a cached AgentDefinitionRepository instance.

    Same reasoning as get_bedrock_repository: no arguments so lru_cache
    can hash the call without touching the unhashable Settings object.
    """
    settings = get_settings()
    return AgentDefinitionRepository(definition_dir=settings.AGENT_DEFINITION_DIR)


# ── Services ──────────────────────────────────────────────────────────────────

def get_agent_service(
    settings: Settings = Depends(get_settings),
    bedrock_repo: BedrockRepository = Depends(get_bedrock_repository),
    definition_repo: AgentDefinitionRepository = Depends(get_definition_repository),
) -> BedrockAgentService:
    """Provide a BedrockAgentService instance per request."""
    return BedrockAgentService(
        bedrock_repo=bedrock_repo,
        definition_repo=definition_repo,
        default_role_arn=settings.DEFAULT_BEDROCK_AGENT_ROLE_ARN,
    )


AgentServiceDep = Annotated[BedrockAgentService, Depends(get_agent_service)]

