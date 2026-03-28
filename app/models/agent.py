"""
Pydantic models for Agent API requests and responses.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ...existing code...

class BedrockModelSummary(BaseModel):
    """A single foundation model available for on-demand use."""

    model_id: str = Field(..., description="The ID to use in spec.model.id (foundation models).")
    model_name: str = Field(..., description="Human-readable model name.")
    provider_name: str = Field(..., description="Model provider (e.g. Amazon, Anthropic, Meta).")
    input_modalities: list[str] = Field(default_factory=list, description="Supported input types.")
    output_modalities: list[str] = Field(default_factory=list, description="Supported output types.")
    inference_types_supported: list[str] = Field(default_factory=list)


class BedrockInferenceProfileSummary(BaseModel):
    """
    A system-defined cross-region inference profile.

    Use the ``profile_id`` as ``spec.model.id`` in your agent definition YAML
    for models (e.g. Meta Llama) that require an inference profile rather than
    direct on-demand invocation.
    """

    profile_id: str = Field(..., description="The ID to use in spec.model.id (e.g. us.meta.llama3-3-70b-instruct-v1:0).")
    profile_name: str = Field(..., description="Human-readable profile name.")
    status: str = Field(..., description="Profile status (ACTIVE, etc.).")
    profile_type: str = Field(..., description="Profile type (SYSTEM_DEFINED).")
    description: str | None = None


class BedrockModelsResponse(BaseModel):
    """Combined response listing usable model IDs for Bedrock agent definitions."""

    foundation_models: list[BedrockModelSummary] = Field(
        default_factory=list,
        description="Foundation models available with on-demand throughput.",
    )
    inference_profiles: list[BedrockInferenceProfileSummary] = Field(
        default_factory=list,
        description=(
            "Cross-region inference profiles (us.* / eu.* / ap.*). "
            "Use these IDs for models such as Meta Llama that require an inference profile."
        ),
    )
    total_foundation_models: int = Field(0, description="Count of foundation models returned.")
    total_inference_profiles: int = Field(0, description="Count of inference profiles returned.")


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

