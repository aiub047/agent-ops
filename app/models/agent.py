"""
Pydantic models for Agent API requests and responses.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateAgentFromDefinitionRequest(BaseModel):
    """Request body to create a Bedrock agent from a YAML definition file."""

    definition_file: str = Field(
        ...,
        description=(
            "Name of the YAML file (without extension) in the agent-definition directory. "
            "Example: 'senior-software-architect'."
        ),
        examples=["senior-software-architect"],
    )
    prepare: bool = Field(
        True,
        description="If True, prepare the agent immediately after creation so it is ready to use.",
    )


class UpdateAgentFromDefinitionRequest(BaseModel):
    """Request body to update an existing Bedrock agent from a YAML definition file."""

    definition_file: str = Field(
        ...,
        description="Name of the YAML file (without extension) in the agent-definition directory.",
        examples=["senior-software-architect"],
    )
    prepare: bool = Field(
        True,
        description="If True, prepare the agent after update.",
    )


class AgentSummary(BaseModel):
    """Lightweight agent representation used in list responses."""

    agent_id: str = Field(..., alias="agentId")
    agent_name: str = Field(..., alias="agentName")
    status: str = Field(..., alias="agentStatus")
    description: str | None = None
    updated_at: datetime | None = Field(None, alias="updatedAt")

    model_config = {"populate_by_name": True}


class AgentResponse(BaseModel):
    """Full agent representation returned by create/get/update endpoints."""

    agent_id: str = Field(..., alias="agentId")
    agent_name: str = Field(..., alias="agentName")
    agent_arn: str | None = Field(None, alias="agentArn")
    agent_version: str | None = Field(None, alias="agentVersion")
    status: str = Field(..., alias="agentStatus")
    description: str | None = None
    instruction: str | None = None
    foundation_model: str | None = Field(None, alias="foundationModel")
    idle_session_ttl_in_seconds: int | None = Field(None, alias="idleSessionTTLInSeconds")
    created_at: datetime | None = Field(None, alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")
    tags: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}

