"""
Pydantic models that mirror the agent definition YAML / JSON schema.

These models are used to parse and validate agent definitions supplied
via YAML files in the ``agent-definition`` directory or as inline JSON
in the ``/deploy-yml`` API request body.

Example top-level structure::

    apiVersion: agentops/v1
    kind: BedrockAgent
    metadata:
      name: senior-software-architect
      ...
    spec:
      model:
        id: us.meta.llama3-3-70b-instruct-v1:0
      instruction: |
        ...
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Shared helpers ────────────────────────────────────────────────────────────

def _none_if_placeholder(v: str | None) -> str | None:
    """
    Return ``None`` when a field value is an un-replaced documentation
    placeholder such as ``"optional-*"`` or an empty string.

    This lets callers submit template YAML files verbatim without having to
    strip every optional field that was not filled in.
    """
    if isinstance(v, str) and (not v.strip() or v.strip().lower().startswith("optional-")):
        return None
    return v


# ── Metadata ──────────────────────────────────────────────────────────────────

class AgentMetadata(BaseModel):
    """Metadata section of an agent definition file."""

    name: str = Field(..., description="Unique agent name used as the Bedrock agent name.")
    display_name: str | None = Field(None, alias="displayName")
    version: str = Field("1.0.0", description="Semantic version of this definition.")
    owner: str | None = None
    description: str | None = Field(None, description="Optional metadata-level description.")
    labels: dict[str, str] = Field(default_factory=dict, description="Free-form key/value labels.")
    tags: dict[str, str] = Field(default_factory=dict, description="AWS resource tags.")
    annotations: dict[str, str] = Field(
        default_factory=dict,
        description="Arbitrary annotations (e.g. GitLab path, commit SHA).",
    )
    created_by: str | None = Field(None, alias="createdBy")
    updated_by: str | None = Field(None, alias="updatedBy")

    model_config = {"populate_by_name": True}


# ── Model ─────────────────────────────────────────────────────────────────────

class ModelConfig(BaseModel):
    """Bedrock foundation model / inference-profile configuration."""

    id: str = Field(..., description="Bedrock model or inference-profile ID.")
    provider: str | None = Field(None, description="Model provider (e.g. 'meta', 'amazon').")
    region: str | None = Field(None, description="AWS region for the model endpoint.")
    temperature: float = Field(0.2, ge=0.0, le=1.0)
    top_p: float = Field(0.9, ge=0.0, le=1.0, alias="topP")
    top_k: int | None = Field(None, alias="topK")
    max_tokens: int = Field(1024, gt=0, alias="maxTokens")
    stop_sequences: list[str] = Field(default_factory=list, alias="stopSequences")
    streaming: bool = False
    additional_model_request_fields: dict[str, Any] = Field(
        default_factory=dict, alias="additionalModelRequestFields"
    )

    model_config = {"populate_by_name": True}


# ── Prompt override ───────────────────────────────────────────────────────────

class PromptInferenceConfig(BaseModel):
    """Inference parameters for a single prompt configuration."""

    maximum_length: int = Field(2048, alias="maximumLength")
    stop_sequences: list[str] = Field(default_factory=list, alias="stopSequences")
    temperature: float = Field(0.2, ge=0.0, le=1.0)
    top_k: int = Field(50, alias="topK")
    top_p: float = Field(0.9, ge=0.0, le=1.0, alias="topP")

    model_config = {"populate_by_name": True}


class PromptConfiguration(BaseModel):
    """Configuration for a single prompt type (PRE_PROCESSING, ORCHESTRATION, etc.)."""

    prompt_type: str = Field(..., alias="promptType")
    prompt_state: str = Field("ENABLED", alias="promptState")
    base_prompt_template: str | None = Field(None, alias="basePromptTemplate")
    inference_configuration: PromptInferenceConfig | None = Field(
        None, alias="inferenceConfiguration"
    )
    parser_mode: str = Field("DEFAULT", alias="parserMode")
    prompt_creation_mode: str = Field("DEFAULT", alias="promptCreationMode")

    _sanitize_template = field_validator("base_prompt_template", mode="before")(_none_if_placeholder)

    model_config = {"populate_by_name": True}


class PromptOverrideConfiguration(BaseModel):
    """Override the default prompt templates for the agent."""

    override_lambda_arn: str | None = Field(None, alias="overrideLambdaArn")
    prompt_configurations: list[PromptConfiguration] = Field(
        default_factory=list, alias="promptConfigurations"
    )

    _sanitize_lambda_arn = field_validator("override_lambda_arn", mode="before")(_none_if_placeholder)

    model_config = {"populate_by_name": True}


# ── Action groups ─────────────────────────────────────────────────────────────

class LambdaExecutor(BaseModel):
    """Lambda executor configuration for an action group."""

    type: Literal["lambda"] = "lambda"
    arn: str = Field(..., description="ARN of the Lambda function.")
    timeout_seconds: int | None = Field(None, alias="timeoutSeconds")

    model_config = {"populate_by_name": True}


class ApiSchemaS3(BaseModel):
    """S3-hosted OpenAPI schema reference."""

    bucket: str | None = None
    key: str | None = None


class ApiSchemaPayload(BaseModel):
    """Inline OpenAPI schema payload."""

    openapi: str | None = None


class ApiSchema(BaseModel):
    """OpenAPI schema for an action group — file path, S3, or inline payload."""

    type: Literal["openapi"] = "openapi"
    file: str | None = Field(None, description="Relative path to the OpenAPI spec file (YAML-file form).")
    s3: ApiSchemaS3 | None = Field(None, description="S3-hosted OpenAPI spec.")
    payload: ApiSchemaPayload | None = Field(None, description="Inline OpenAPI spec payload.")


class FunctionParameter(BaseModel):
    """JSON-Schema-style parameter block for a function definition."""

    type: str = "object"
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)


class FunctionDef(BaseModel):
    """A single function exposed by an action group."""

    name: str
    description: str | None = None
    parameters: FunctionParameter | None = None


class FunctionSchema(BaseModel):
    """Function schema for an action group (alternative to apiSchema)."""

    functions: list[FunctionDef] = Field(default_factory=list)


class ActionGroup(BaseModel):
    """A single action group definition."""

    name: str
    description: str | None = None
    executor: LambdaExecutor
    api_schema: ApiSchema | None = Field(None, alias="apiSchema")
    function_schema: FunctionSchema | None = Field(None, alias="functionSchema")
    enabled: bool = True

    model_config = {"populate_by_name": True}


# ── Knowledge bases ───────────────────────────────────────────────────────────

class RetrievalConfig(BaseModel):
    """Knowledge base retrieval parameters."""

    top_k: int = Field(5, alias="topK", ge=1)
    score_threshold: float = Field(0.7, alias="scoreThreshold", ge=0.0, le=1.0)
    search_type: str | None = Field(None, alias="searchType")
    override_search_type: str | None = Field(None, alias="overrideSearchType")
    filter: dict[str, Any] | None = Field(None, description="Metadata filter expression.")

    model_config = {"populate_by_name": True}


class KnowledgeBase(BaseModel):
    """A knowledge base attached to the agent."""

    id: str
    description: str | None = None
    enabled: bool = True
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    prompt_template: str | None = Field(None, alias="promptTemplate")

    model_config = {"populate_by_name": True}


# ── Guardrails ────────────────────────────────────────────────────────────────

class Guardrails(BaseModel):
    """Guardrail configuration for the agent."""

    enabled: bool = True
    guardrail_id: str | None = Field(None, alias="guardrailId")
    guardrail_version: str | None = Field(None, alias="guardrailVersion")

    _sanitize_guardrail_id = field_validator("guardrail_id", mode="before")(_none_if_placeholder)

    @model_validator(mode="after")
    def _disable_when_no_id(self) -> "Guardrails":
        """Disable guardrails automatically when the guardrailId is absent or a placeholder."""
        if self.enabled and not self.guardrail_id:
            self.enabled = False
        return self

    model_config = {"populate_by_name": True}


# ── Session / memory ──────────────────────────────────────────────────────────

class SessionConfig(BaseModel):
    """Session management settings (legacy YAML form)."""

    idle_ttl_seconds: int = Field(1800, alias="idleTtlSeconds", ge=60)
    memory_enabled: bool = Field(False, alias="memoryEnabled")

    model_config = {"populate_by_name": True}


class MemoryConfig(BaseModel):
    """Agent memory configuration."""

    enabled: bool = False
    type: str = Field("SESSION", description="Memory type, e.g. 'SESSION'.")


# ── Aliases ───────────────────────────────────────────────────────────────────

class AliasRouting(BaseModel):
    """Traffic routing for an alias."""

    traffic_percent: int = Field(100, alias="trafficPercent", ge=0, le=100)

    model_config = {"populate_by_name": True}


class AgentAlias(BaseModel):
    """An alias pointing to a version of the agent."""

    name: str
    description: str | None = None
    routing: AliasRouting = Field(default_factory=AliasRouting)
    tags: dict[str, str] = Field(default_factory=dict)


# ── Observability ─────────────────────────────────────────────────────────────

class Observability(BaseModel):
    """Observability and tracing settings."""

    log_level: str = Field("info", alias="logLevel")
    trace_enabled: bool = Field(True, alias="traceEnabled")
    metrics_enabled: bool = Field(False, alias="metricsEnabled")

    model_config = {"populate_by_name": True}


# ── Response contract ─────────────────────────────────────────────────────────

class ResponseContract(BaseModel):
    """Expected response structure from the agent."""

    format: Literal["markdown", "json", "text"] = "markdown"
    sections: list[str] = Field(default_factory=list)
    max_section_count: int | None = Field(None, alias="maxSectionCount")
    require_structured_output: bool = Field(False, alias="requireStructuredOutput")

    model_config = {"populate_by_name": True}


# ── Deployment ────────────────────────────────────────────────────────────────

class DeploymentConfig(BaseModel):
    """Deployment target configuration."""

    region: str = "us-east-1"
    role_arn: str | None = Field(
        None,
        alias="roleArn",
        description=(
            "IAM role ARN that Amazon Bedrock assumes when running this agent. "
            "Falls back to DEFAULT_BEDROCK_AGENT_ROLE_ARN env var if omitted."
        ),
    )
    agent_name_override: str | None = Field(
        None,
        alias="agentNameOverride",
        description="Override the Bedrock agent name (defaults to metadata.name).",
    )
    auto_prepare: bool = Field(True, alias="autoPrepare")
    create_alias: bool = Field(False, alias="createAlias")
    default_alias_name: str | None = Field(None, alias="defaultAliasName")
    publish: bool = False
    terraform_workspace: str | None = Field(None, alias="terraformWorkspace")
    tags: dict[str, str] = Field(default_factory=dict)

    _sanitize_role_arn = field_validator("role_arn", mode="before")(_none_if_placeholder)
    _sanitize_name_override = field_validator("agent_name_override", mode="before")(_none_if_placeholder)

    model_config = {"populate_by_name": True}


# ── Lifecycle ─────────────────────────────────────────────────────────────────

class LifecycleConfig(BaseModel):
    """Agent lifecycle management settings."""

    desired_state: str = Field("DEPLOYED", alias="desiredState")
    deletion_policy: str = Field("RETAIN", alias="deletionPolicy")

    model_config = {"populate_by_name": True}


# ── Spec / top-level ──────────────────────────────────────────────────────────

class AgentSpec(BaseModel):
    """The spec section containing all agent behaviour and runtime settings."""

    description: str | None = None
    model: ModelConfig
    instruction: str

    # Agent-level Bedrock settings
    agent_collaboration: str = Field(
        "DISABLED",
        alias="agentCollaboration",
        description="Collaboration mode: DISABLED, SUPERVISOR, or SUPERVISOR_ROUTER.",
    )
    idle_session_ttl_in_seconds: int = Field(
        1800,
        alias="idleSessionTtlInSeconds",
        ge=60,
        description="Idle session TTL in seconds (spec-level; takes precedence over session.idleTtlSeconds).",
    )
    customer_encryption_key_arn: str | None = Field(
        None, alias="customerEncryptionKeyArn"
    )
    service_role_arn: str | None = Field(
        None,
        alias="serviceRoleArn",
        description="Bedrock agent service role ARN (alternative to deployment.roleArn).",
    )
    foundation_model: str | None = Field(
        None,
        alias="foundationModel",
        description="Shorthand model ID (takes precedence over model.id when set).",
    )

    _sanitize_enc_key = field_validator("customer_encryption_key_arn", mode="before")(_none_if_placeholder)
    _sanitize_service_role = field_validator("service_role_arn", mode="before")(_none_if_placeholder)
    prompt_override_configuration: PromptOverrideConfiguration | None = Field(
        None, alias="promptOverrideConfiguration"
    )

    # Behaviour
    goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    response_contract: ResponseContract | None = Field(None, alias="responseContract")

    # Resources
    session: SessionConfig = Field(default_factory=SessionConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    guardrails: Guardrails = Field(default_factory=Guardrails)
    knowledge_bases: list[KnowledgeBase] = Field(default_factory=list, alias="knowledgeBases")
    action_groups: list[ActionGroup] = Field(default_factory=list, alias="actionGroups")
    aliases: list[AgentAlias] = Field(default_factory=list)

    # Ops
    observability: Observability = Field(default_factory=Observability)
    deployment: DeploymentConfig = Field(default_factory=DeploymentConfig)
    lifecycle: LifecycleConfig | None = None

    model_config = {"populate_by_name": True}


class AgentDefinition(BaseModel):
    """
    Top-level model for an agent definition.

    Mirrors the ``apiVersion / kind / metadata / spec`` structure used in
    both ``.agent.yaml`` files and inline JSON API requests.
    """

    api_version: str = Field("agentops/v1", alias="apiVersion")
    kind: Literal["BedrockAgent"] = "BedrockAgent"
    metadata: AgentMetadata
    spec: AgentSpec

    model_config = {"populate_by_name": True}

