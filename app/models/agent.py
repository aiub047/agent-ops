"""
Pydantic models for Agent API requests and responses.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


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

    profile_id: str = Field(...,
                            description="The ID to use in spec.model.id (e.g. us.meta.llama3-3-70b-instruct-v1:0).")
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


class CreateOrUpdateAgentRequest(BaseModel):
    """Request body for the create-or-update (upsert) endpoint.

    Looks up an existing agent by name derived from the definition file.
    If found, the agent is updated (or deleted and recreated when
    ``recreate=True``).  If not found, a new agent is created.
    """

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
        description="If True, prepare the agent immediately after the operation so it is ready to use.",
    )
    recreate: bool = Field(
        False,
        description=(
            "If True and an agent with the same name already exists, delete it and create a fresh one. "
            "If False (default), the existing agent is updated in-place."
        ),
    )


class DeployYmlSource(BaseModel):
    """Source control metadata attached to a ``/deploy-yml`` request.

    Captures where the YAML definition came from so deployments can be
    traced back to a specific commit or pull-request merge.
    """

    repo: str = Field(..., description="Repository name (e.g. 'bedrock-agent-definitions').")
    branch: str = Field(..., description="Branch the file was taken from (e.g. 'main').")
    commit_sha: str = Field(..., alias="commitSha", description="Git commit SHA.")
    file_path: str = Field(..., alias="filePath", description="Path to the YAML file inside the repo.")
    merged_by: str | None = Field(None, alias="mergedBy", description="User who triggered the deployment.")

    model_config = {"populate_by_name": True}


class DeployYmlRequest(BaseModel):
    """Request body for the ``POST /agents/deploy-yml`` endpoint.

    Accepts a raw YAML string and source-control metadata.

    * ``redeploy=true``  → create if new, update if already exists.
    * ``redeploy=false`` → create if new; return **409 Conflict** if already exists.

    When ``redeploy=true``, the ``recreate`` flag controls *how* the update is applied:

    * ``recreate=false`` *(default)* → update in-place via ``UpdateAgent`` (requires
      ``bedrock:UpdateAgent`` on the caller's IAM role).
    * ``recreate=true`` → delete the existing agent and create a fresh one.
      Use this when ``bedrock:UpdateAgent`` is not available, or when changing
      fields that Bedrock does not allow to be updated in-place (e.g. IAM role ARN).
    """

    agent_key: str = Field(
        ...,
        alias="agentKey",
        description="Logical key identifying the agent (used for logging/tracing).",
        examples=["feature-flag-agent"],
    )
    yaml_data: str | dict = Field(
        ...,
        alias="yamlData",
        description=(
            "Agent definition supplied either as a **JSON object** (recommended) "
            "or as a YAML-formatted string with newlines escaped as ``\\n``. "
            "The object form mirrors the .agent.yaml structure "
            "(apiVersion / kind / metadata / spec)."
        ),
    )
    redeploy: bool = Field(
        False,
        description=(
            "Controls behaviour when the agent already exists and ``recreate=false``:\n"
            "- ``false`` (default) + ``recreate=false`` → fail with **409 Conflict**.\n"
            "- ``true``  + ``recreate=false`` → update the agent in-place (HTTP 200)."
        ),
    )
    recreate: bool = Field(
        False,
        description=(
            "When ``true`` and the agent already exists, delete it and create a fresh one "
            "(HTTP 201), regardless of the ``redeploy`` flag.\n"
            "When ``false`` (default), behaviour is controlled by ``redeploy``:\n"
            "- ``redeploy=false`` → 409 Conflict if the agent exists.\n"
            "- ``redeploy=true``  → update the agent in-place (HTTP 200)."
        ),
    )
    source: DeployYmlSource = Field(
        ...,
        description="Source-control metadata describing the origin of the YAML.",
    )

    @field_validator("redeploy", mode="before")
    @classmethod
    def _coerce_redeploy(cls, v: Any) -> bool:
        """Accept string representations ('true'/'false') in addition to booleans."""
        if isinstance(v, str):
            if v.lower() == "true":
                return True
            if v.lower() == "false":
                return False
            raise ValueError(f"Invalid value for redeploy: '{v}'. Expected 'true' or 'false'.")
        return v

    @field_validator("recreate", mode="before")
    @classmethod
    def _coerce_recreate(cls, v: Any) -> bool:
        """Accept string representations ('true'/'false') in addition to booleans."""
        if isinstance(v, str):
            if v.lower() == "true":
                return True
            if v.lower() == "false":
                return False
            raise ValueError(f"Invalid value for recreate: '{v}'. Expected 'true' or 'false'.")
        return v

    model_config = {"populate_by_name": True}


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
