"""
Pydantic models that mirror the agent definition YAML schema.

These models are used to parse and validate the YAML files stored in the
agent-definition directory. Each field maps 1-to-1 with a YAML key.

Example YAML structure::

    apiVersion: agentops/v1
    kind: BedrockAgent
    metadata:
      name: senior-software-architect
      ...
    spec:
      model:
        id: anthropic.claude-3-5-sonnet-20241022-v2:0
      instruction: |
        ...
"""

from typing import Literal

from pydantic import BaseModel, Field


class AgentMetadata(BaseModel):
    """Metadata section of an agent definition file."""

    name: str = Field(..., description="Unique agent name used as filename identifier.")
    display_name: str | None = Field(None, alias="displayName")
    version: str = Field("1.0.0", description="Semantic version of this definition.")
    owner: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class ModelConfig(BaseModel):
    """Bedrock foundation model configuration."""

    id: str = Field(..., description="Bedrock model identifier, e.g. anthropic.claude-3-5-sonnet-*")
    temperature: float = Field(0.2, ge=0.0, le=1.0)
    top_p: float = Field(0.9, ge=0.0, le=1.0, alias="topP")
    max_tokens: int = Field(1024, gt=0, alias="maxTokens")

    model_config = {"populate_by_name": True}


class LambdaExecutor(BaseModel):
    """Lambda executor configuration for an action group."""

    type: Literal["lambda"] = "lambda"
    arn: str = Field(..., description="ARN of the Lambda function.")


class ApiSchema(BaseModel):
    """OpenAPI schema reference for an action group."""

    type: Literal["openapi"] = "openapi"
    file: str = Field(..., description="Relative path to the OpenAPI spec file.")


class ActionGroup(BaseModel):
    """A single action group definition."""

    name: str
    description: str | None = None
    executor: LambdaExecutor
    api_schema: ApiSchema | None = Field(None, alias="apiSchema")
    enabled: bool = True

    model_config = {"populate_by_name": True}


class RetrievalConfig(BaseModel):
    """Knowledge base retrieval parameters."""

    top_k: int = Field(5, alias="topK", ge=1)
    score_threshold: float = Field(0.7, alias="scoreThreshold", ge=0.0, le=1.0)

    model_config = {"populate_by_name": True}


class KnowledgeBase(BaseModel):
    """A knowledge base attached to the agent."""

    id: str
    description: str | None = None
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)


class Guardrails(BaseModel):
    """Guardrail configuration for the agent."""

    enabled: bool = True
    guardrail_id: str | None = Field(None, alias="guardrailId")
    guardrail_version: str | None = Field(None, alias="guardrailVersion")

    model_config = {"populate_by_name": True}


class SessionConfig(BaseModel):
    """Session management settings."""

    idle_ttl_seconds: int = Field(1800, alias="idleTtlSeconds", ge=60)
    memory_enabled: bool = Field(False, alias="memoryEnabled")

    model_config = {"populate_by_name": True}


class AliasRouting(BaseModel):
    """Traffic routing for an alias."""

    traffic_percent: int = Field(100, alias="trafficPercent", ge=0, le=100)

    model_config = {"populate_by_name": True}


class AgentAlias(BaseModel):
    """An alias pointing to a version of the agent."""

    name: str
    routing: AliasRouting = Field(default_factory=AliasRouting)


class Observability(BaseModel):
    """Observability and tracing settings."""

    log_level: str = Field("info", alias="logLevel")
    trace_enabled: bool = Field(True, alias="traceEnabled")

    model_config = {"populate_by_name": True}


class DeploymentConfig(BaseModel):
    """Deployment target configuration."""

    region: str = "us-east-1"
    role_arn: str | None = Field(
        None,
        alias="roleArn",
        description=(
            "IAM role ARN that Amazon Bedrock assumes when running this agent. "
            "If omitted, falls back to the DEFAULT_BEDROCK_AGENT_ROLE_ARN env var."
        ),
    )
    terraform_workspace: str | None = Field(None, alias="terraformWorkspace")

    model_config = {"populate_by_name": True}


class ResponseContract(BaseModel):
    """Expected response structure from the agent."""

    format: Literal["markdown", "json", "text"] = "markdown"
    sections: list[str] = Field(default_factory=list)


class AgentSpec(BaseModel):
    """The spec section containing all agent behaviour and runtime settings."""

    description: str | None = None
    model: ModelConfig
    instruction: str
    goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    response_contract: ResponseContract | None = Field(None, alias="responseContract")
    session: SessionConfig = Field(default_factory=SessionConfig)
    guardrails: Guardrails = Field(default_factory=Guardrails)
    knowledge_bases: list[KnowledgeBase] = Field(default_factory=list, alias="knowledgeBases")
    action_groups: list[ActionGroup] = Field(default_factory=list, alias="actionGroups")
    aliases: list[AgentAlias] = Field(default_factory=list)
    observability: Observability = Field(default_factory=Observability)
    deployment: DeploymentConfig = Field(default_factory=DeploymentConfig)

    model_config = {"populate_by_name": True}


class AgentDefinition(BaseModel):
    """
    Top-level model for an agent definition YAML file.

    Mirrors the ``apiVersion / kind / metadata / spec`` structure so that
    the repository layer can parse any compliant YAML into this model.
    """

    api_version: str = Field("agentops/v1", alias="apiVersion")
    kind: Literal["BedrockAgent"] = "BedrockAgent"
    metadata: AgentMetadata
    spec: AgentSpec

    model_config = {"populate_by_name": True}

