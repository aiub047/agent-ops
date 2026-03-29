"""
Bedrock Agent Service.

Orchestrates agent CRUD operations by combining the AgentDefinitionRepository
(reads YAML files) with the BedrockRepository (calls AWS Bedrock APIs).
Implements AgentServiceProtocol so it can be swapped in tests.
"""

from app.core.exceptions import AgentConflictError, BedrockServiceError
from app.core.logging import get_logger
from app.models.agent import (
    AgentResponse,
    AgentSummary,
    BedrockInferenceProfileSummary,
    BedrockModelSummary,
    BedrockModelsResponse,
)
from app.models.common import PaginatedResponse
from app.repositories.agent_definition_repository import AgentDefinitionRepository
from app.repositories.bedrock_repository import BedrockRepository
from app.schemas.agent_definition import AgentDefinition

logger = get_logger(__name__)


class BedrockAgentService:
    """
    Business-logic layer for Amazon Bedrock Agent management.

    Args:
        bedrock_repo: Repository that wraps the boto3 bedrock-agent client.
        definition_repo: Repository that reads/validates agent YAML files.
        default_role_arn: Fallback IAM role ARN used when an agent definition
            does not declare its own ``spec.k8s.roleArn``.  Each agent
            should ideally carry its own role for least-privilege isolation.
    """

    def __init__(
        self,
        bedrock_repo: BedrockRepository,
        definition_repo: AgentDefinitionRepository,
        default_role_arn: str | None = None,
    ) -> None:
        self._bedrock = bedrock_repo
        self._definitions = definition_repo
        self._default_role_arn = default_role_arn

    # ── Public API ────────────────────────────────────────────────────────────

    def create_agent_from_definition(
        self,
        definition_file: str,
        prepare: bool = True,
    ) -> AgentResponse:
        """
        Load a definition by filename, then create the Bedrock agent.

        Args:
            definition_file: Filename without extension (e.g. 'senior-software-architect').
            prepare: Whether to call PrepareAgent after creation.

        Returns:
            AgentResponse: Created agent details.
        """
        definition = self._definitions.get(definition_file)
        return self.create_agent(definition, prepare=prepare)

    def create_agent(
        self,
        definition: AgentDefinition,
        prepare: bool = True,
    ) -> AgentResponse:
        """
        Create a Bedrock agent from a parsed AgentDefinition.

        Args:
            definition: Validated agent definition model.
            prepare: Whether to call PrepareAgent after creation.

        Returns:
            AgentResponse: Created agent details.
        """
        logger.info("Creating agent '%s'", definition.metadata.name)
        params = self._build_create_params(definition)
        raw = self._bedrock.create_agent(**params)
        agent_id: str = raw["agentId"]

        if prepare:
            self._bedrock.prepare_agent(agent_id)
            raw = self._bedrock.get_agent(agent_id)

        return AgentResponse.model_validate(self._enrich_with_tags(raw))

    def get_agent(self, agent_id: str) -> AgentResponse:
        """
        Retrieve a single Bedrock agent by ID.

        Args:
            agent_id: Bedrock-assigned agent identifier.

        Returns:
            AgentResponse: Agent details.
        """
        raw = self._bedrock.get_agent(agent_id)
        return AgentResponse.model_validate(self._enrich_with_tags(raw))

    def list_agents(
        self,
        max_results: int = 50,
        next_token: str | None = None,
    ) -> PaginatedResponse[AgentSummary]:
        """
        Return a paginated list of all agents.

        Args:
            max_results: Page size (max 50).
            next_token: Pagination cursor from previous response.

        Returns:
            PaginatedResponse[AgentSummary]: Paginated agent summaries.
        """
        response = self._bedrock.list_agents(max_results=max_results, next_token=next_token)
        summaries = [
            AgentSummary.model_validate(item)
            for item in response.get("agentSummaries", [])
        ]
        return PaginatedResponse(
            items=summaries,
            total=len(summaries),
            nextToken=response.get("nextToken"),
        )

    def update_agent_from_definition(
        self,
        agent_id: str,
        definition_file: str,
        prepare: bool = True,
    ) -> AgentResponse:
        """
        Load a definition by filename, then update the Bedrock agent.

        Args:
            agent_id: Bedrock-assigned agent identifier to update.
            definition_file: Filename without extension.
            prepare: Whether to prepare after update.

        Returns:
            AgentResponse: Updated agent details.
        """
        definition = self._definitions.get(definition_file)
        return self.update_agent(agent_id, definition, prepare=prepare)

    def update_agent(
        self,
        agent_id: str,
        definition: AgentDefinition,
        prepare: bool = True,
    ) -> AgentResponse:
        """
        Update an existing Bedrock agent with a new definition.

        Args:
            agent_id: Bedrock-assigned agent identifier.
            definition: Validated agent definition model.
            prepare: Whether to prepare after update.

        Returns:
            AgentResponse: Updated agent details.
        """
        logger.info("Updating agent '%s' (%s)", definition.metadata.name, agent_id)
        params = self._build_update_params(definition)
        raw = self._bedrock.update_agent(agent_id, **params)

        if prepare:
            self._bedrock.prepare_agent(agent_id)
            raw = self._bedrock.get_agent(agent_id)

        return AgentResponse.model_validate(self._enrich_with_tags(raw))

    def delete_agent(self, agent_id: str) -> None:
        """
        Permanently delete a Bedrock agent.

        Args:
            agent_id: Bedrock-assigned agent identifier.
        """
        logger.info("Deleting agent '%s'", agent_id)
        self._bedrock.delete_agent(agent_id)

    def list_definitions(self) -> list[str]:
        """Return the names of all YAML definitions in the agent-definition directory."""
        return self._definitions.list_definitions()

    def list_bedrock_models(self) -> BedrockModelsResponse:
        """
        Return all foundation models and cross-region inference profiles that
        can be used as ``spec.model.id`` in an agent definition YAML.

        * **foundation_models** – on-demand text models addressable by their
          bare model ID (e.g. ``amazon.titan-text-express-v1``).
        * **inference_profiles** – system-defined cross-region profiles such as
          ``us.meta.llama3-3-70b-instruct-v1:0``.  Use these for models that
          raise *"on-demand throughput isn't supported"* when addressed by their
          bare model ID.

        Returns:
            BedrockModelsResponse: Combined listing of usable model IDs.
        """
        raw_models = self._bedrock.list_foundation_models()
        raw_profiles = self._bedrock.list_inference_profiles()

        foundation_models = [
            BedrockModelSummary(
                model_id=m.get("modelId", ""),
                model_name=m.get("modelName", ""),
                provider_name=m.get("providerName", ""),
                input_modalities=m.get("inputModalities", []),
                output_modalities=m.get("outputModalities", []),
                inference_types_supported=m.get("inferenceTypesSupported", []),
            )
            for m in raw_models
        ]

        inference_profiles = [
            BedrockInferenceProfileSummary(
                profile_id=p.get("inferenceProfileId", ""),
                profile_name=p.get("inferenceProfileName", ""),
                status=p.get("status", ""),
                profile_type=p.get("type", ""),
                description=p.get("description"),
            )
            for p in raw_profiles
        ]

        return BedrockModelsResponse(
            foundation_models=foundation_models,
            inference_profiles=inference_profiles,
            total_foundation_models=len(foundation_models),
            total_inference_profiles=len(inference_profiles),
        )

    def create_or_update_agent_from_definition(
        self,
        definition_file: str,
        prepare: bool = True,
        recreate: bool = False,
    ) -> AgentResponse:
        """
        Upsert a Bedrock agent from a YAML definition file.

        Looks up an existing agent whose name matches ``metadata.name`` in the
        definition file.  Behaviour depends on whether a match is found and on
        the ``recreate`` flag:

        * **Not found** → create a new agent (same as ``create_agent``).
        * **Found, recreate=False** (default) → update the existing agent
          in-place (same as ``update_agent``).
        * **Found, recreate=True** → delete the existing agent, then create a
          fresh one.  Use this when you need a clean slate (e.g. after changing
          the agent's IAM role ARN, which cannot be updated in-place).

        Args:
            definition_file: Filename without extension (e.g. 'senior-software-architect').
            prepare: Whether to prepare the agent after the operation.
            recreate: When True and an agent already exists, delete-then-recreate
                instead of updating in-place.

        Returns:
            AgentResponse: The resulting agent details.
        """
        definition = self._definitions.get(definition_file)
        agent_name = definition.metadata.name
        existing_id = self._find_agent_by_name(agent_name)

        if existing_id is None:
            logger.info(
                "No existing agent named '%s' found; creating new.", agent_name
            )
            return self.create_agent(definition, prepare=prepare)

        if recreate:
            logger.info(
                "Agent '%s' (%s) exists; deleting and recreating (recreate=True).",
                agent_name,
                existing_id,
            )
            self._bedrock.delete_agent(existing_id)
            self._bedrock.wait_until_deleted(existing_id)
            return self.create_agent(definition, prepare=prepare)

        logger.info(
            "Agent '%s' (%s) exists; updating in-place (recreate=False).",
            agent_name,
            existing_id,
        )
        return self.update_agent(existing_id, definition, prepare=prepare)

    def deploy_yml(
        self,
        agent_key: str,
        yaml_data: str | dict,
        redeploy: bool,
        recreate: bool = False,
    ) -> tuple[AgentResponse, bool]:
        """
        Deploy a Bedrock agent from a YAML definition with explicit redeploy control.

        *yaml_data* may be supplied as:

        * A **dict** (JSON object in the request body) — used directly without
          any parsing step.  This is the recommended form because it avoids
          JSON encoding issues with multi-line strings.
        * A **str** — parsed with ``yaml.safe_load``.  Newlines inside a JSON
          string must be escaped as ``\\n``; literal newlines are invalid JSON.

        Applies one of four strategies based on *redeploy* and *recreate*:

        * ``redeploy=False, recreate=False`` → **create-only**: create if new;
          raise :class:`~app.core.exceptions.AgentConflictError` (HTTP 409) if
          the agent already exists.
        * ``redeploy=True,  recreate=False`` → **upsert in-place**: create if new,
          update the existing agent via ``UpdateAgent`` if found (HTTP 200).
          Requires ``bedrock:UpdateAgent`` on the caller's IAM role.
        * ``redeploy=True,  recreate=True``  → **delete + recreate**: create if new,
          or delete the existing agent and create a fresh one (HTTP 201).
        * ``redeploy=False, recreate=True``  → **force recreate**: create if new,
          or delete the existing agent and create a fresh one (HTTP 201).
          Use this when you want a clean replacement without allowing silent in-place
          updates.

        Args:
            agent_key: Logical key for the agent (used in log messages for traceability).
            yaml_data: Agent definition as a dict (JSON object) or a YAML string.
            redeploy: Controls update behaviour when the agent already exists.
            recreate: When ``True`` and ``redeploy=True``, delete then recreate the
                agent instead of updating in-place.  Defaults to ``False``.

        Returns:
            tuple[AgentResponse, bool]: The resulting agent details and a flag that
            is ``True`` when the agent was **created** (HTTP 201) or ``False`` when
            it was **updated** (HTTP 200).

        Raises:
            BedrockServiceError: If the YAML is malformed or fails schema validation.
            AgentConflictError: If ``redeploy=False`` and the agent already exists.
        """
        logger.info(
            "deploy_yml: Processing agent key '%s' (redeploy=%s, recreate=%s)",
            agent_key, redeploy, recreate,
        )

        if isinstance(yaml_data, dict):
            raw = yaml_data
        else:
            try:
                raw = yaml.safe_load(yaml_data)
            except yaml.YAMLError as exc:
                raise BedrockServiceError(f"Malformed YAML: {exc}") from exc

        if not isinstance(raw, dict):
            raise BedrockServiceError("Agent definition must be a mapping at the top level.")

        try:
            definition = AgentDefinition.model_validate(raw)
        except ValidationError as exc:
            raise BedrockServiceError(
                f"Agent definition failed schema validation: {exc}"
            ) from exc

        agent_name = definition.metadata.name
        existing_id = self._find_agent_by_name(agent_name)

        # ── Agent does not exist → always create ─────────────────────────────
        if existing_id is None:
            logger.info("deploy_yml: Agent '%s' not found; creating new.", agent_name)
            return self.create_agent(definition, prepare=True), True

        # ── Agent exists ──────────────────────────────────────────────────────
        if recreate:
            # redeploy=true|false + recreate=true → delete then create fresh
            logger.info(
                "deploy_yml: Agent '%s' (%s) exists; deleting and recreating (recreate=True).",
                agent_name, existing_id,
            )
            self._bedrock.delete_agent(existing_id)
            self._bedrock.wait_until_deleted(existing_id)
            return self.create_agent(definition, prepare=True), True

        if not redeploy:
            # redeploy=false + recreate=false → conflict
            raise AgentConflictError(
                f"Agent '{agent_name}' (id={existing_id}) already exists. "
                "Set redeploy=true to update it, or recreate=true to delete and recreate it."
            )

        # redeploy=true + recreate=false → update in-place
        logger.info(
            "deploy_yml: Agent '%s' (%s) exists; updating in-place "
            "(redeploy=True, recreate=False).",
            agent_name, existing_id,
        )
        return self.update_agent(existing_id, definition, prepare=True), False

    # ── Private helpers ───────────────────────────────────────────────────────

    def _find_agent_by_name(self, name: str) -> str | None:
        """
        Scan all Bedrock agents (handling pagination) and return the *agentId*
        of the first agent whose name matches *name*, or ``None`` if not found.

        Args:
            name: Agent name to search for (case-sensitive, matches ``metadata.name``
                in the definition YAML).

        Returns:
            str | None: The Bedrock agent ID, or ``None`` if no match is found.
        """
        next_token: str | None = None
        while True:
            response = self._bedrock.list_agents(
                max_results=50, next_token=next_token
            )
            for summary in response.get("agentSummaries", []):
                if summary.get("agentName") == name:
                    return summary["agentId"]
            next_token = response.get("nextToken")
            if not next_token:
                return None

    # ── Private helpers ───────────────────────────────────────────────────────

    def _enrich_with_tags(self, raw: dict) -> dict:
        """
        Inject the agent's resource tags into *raw* (in-place and returned).

        Bedrock's ``CreateAgent``, ``UpdateAgent``, and ``GetAgent`` responses
        all omit ``tags`` from the returned ``agent`` object.  Tags are a
        separate resource attribute and must be fetched with
        ``ListTagsForResource``.  This helper performs that extra call using
        the ``agentArn`` already present in *raw* and merges the result back
        so that ``AgentResponse`` always reflects the real tag set.

        Args:
            raw: The ``agent`` dict returned by any Bedrock agent API call.

        Returns:
            dict: The same *raw* dict, now with a ``"tags"`` key populated.
        """
        agent_arn: str | None = raw.get("agentArn")
        if agent_arn:
            raw["tags"] = self._bedrock.list_tags_for_resource(agent_arn)
        return raw

    def _resolve_role_arn(self, definition: AgentDefinition) -> str:
        """
        Return the IAM role ARN for the agent.

        Resolution order:
        1. ``spec.serviceRoleArn`` — explicit service role in the spec.
        2. ``spec.deployment.roleArn`` — role declared in the deployment block.
        3. ``default_role_arn`` — fallback from the
           ``DEFAULT_BEDROCK_AGENT_ROLE_ARN`` environment variable.

        Raises:
            BedrockServiceError: If none of the sources provide a role ARN.
        """
        spec = definition.spec
        role_arn = (
            spec.service_role_arn
            or spec.deployment.role_arn
            or self._default_role_arn
            or ""
        ).strip()
        if not role_arn:
            raise BedrockServiceError(
                f"No IAM role ARN found for agent '{definition.metadata.name}'. "
                "Set 'spec.serviceRoleArn' or 'spec.deployment.roleArn' in the definition, "
                "or set DEFAULT_BEDROCK_AGENT_ROLE_ARN in the environment as a fallback."
            )
        return role_arn

    def _build_create_params(self, definition: AgentDefinition) -> dict:
        spec = definition.spec
        # foundationModel shorthand takes precedence over spec.model.id
        model_id = spec.foundation_model or spec.model.id
        # agentNameOverride takes precedence over metadata.name
        agent_name = spec.deployment.agent_name_override or definition.metadata.name
        # spec-level TTL takes precedence over legacy session.idle_ttl_seconds
        idle_ttl = spec.idle_session_ttl_in_seconds or spec.session.idle_ttl_seconds
        # Merge metadata tags and deployment tags (deployment tags win on conflict)
        tags = {**definition.metadata.tags, **spec.deployment.tags}

        params: dict = {
            "agentName": agent_name,
            "agentResourceRoleArn": self._resolve_role_arn(definition),
            "foundationModel": model_id,
            "instruction": spec.instruction,
            "idleSessionTTLInSeconds": idle_ttl,
        }
        if spec.description:
            params["description"] = spec.description
        if tags:
            params["tags"] = tags
        if spec.agent_collaboration and spec.agent_collaboration != "DISABLED":
            params["agentCollaboration"] = spec.agent_collaboration
        if spec.customer_encryption_key_arn:
            params["customerEncryptionKeyArn"] = spec.customer_encryption_key_arn
        if spec.guardrails.enabled and spec.guardrails.guardrail_id:
            params["guardrailConfiguration"] = {
                "guardrailIdentifier": spec.guardrails.guardrail_id,
                "guardrailVersion": spec.guardrails.guardrail_version or "DRAFT",
            }
        if spec.prompt_override_configuration:
            params["promptOverrideConfiguration"] = self._serialize_prompt_override(
                spec.prompt_override_configuration
            )
        return params

    def _build_update_params(self, definition: AgentDefinition) -> dict:
        spec = definition.spec
        model_id = spec.foundation_model or spec.model.id
        agent_name = spec.deployment.agent_name_override or definition.metadata.name
        idle_ttl = spec.idle_session_ttl_in_seconds or spec.session.idle_ttl_seconds

        params: dict = {
            "agentName": agent_name,
            "agentResourceRoleArn": self._resolve_role_arn(definition),
            "foundationModel": model_id,
            "instruction": spec.instruction,
            "idleSessionTTLInSeconds": idle_ttl,
        }
        if spec.description:
            params["description"] = spec.description
        if spec.agent_collaboration and spec.agent_collaboration != "DISABLED":
            params["agentCollaboration"] = spec.agent_collaboration
        if spec.customer_encryption_key_arn:
            params["customerEncryptionKeyArn"] = spec.customer_encryption_key_arn
        if spec.guardrails.enabled and spec.guardrails.guardrail_id:
            params["guardrailConfiguration"] = {
                "guardrailIdentifier": spec.guardrails.guardrail_id,
                "guardrailVersion": spec.guardrails.guardrail_version or "DRAFT",
            }
        if spec.prompt_override_configuration:
            params["promptOverrideConfiguration"] = self._serialize_prompt_override(
                spec.prompt_override_configuration
            )
        return params

    @staticmethod
    def _serialize_prompt_override(config: "PromptOverrideConfiguration") -> dict:
        """
        Serialize a ``PromptOverrideConfiguration`` into a boto3-compatible dict.

        Two normalisation steps are applied after standard Pydantic serialization:

        1. **Key rename**: The user-facing field ``overrideLambdaArn`` is renamed to
           ``overrideLambda`` because that is what the boto3 Bedrock SDK expects.

        2. **DEFAULT-mode stripping**: When a ``PromptConfiguration`` has
           ``promptCreationMode = DEFAULT``, the Bedrock API only accepts
           ``promptType`` and ``promptCreationMode`` in that object.  Sending any
           other field (``promptState``, ``inferenceConfiguration``,
           ``basePromptTemplate``, ``parserMode``) raises a ``ValidationException``.
           This method removes all such fields automatically.

        Args:
            config: The parsed prompt override configuration.

        Returns:
            dict: boto3-ready ``promptOverrideConfiguration`` value.
        """
        data = config.model_dump(by_alias=True, exclude_none=True)

        # boto3 SDK uses "overrideLambda"; our schema alias is "overrideLambdaArn"
        if "overrideLambdaArn" in data:
            data["overrideLambda"] = data.pop("overrideLambdaArn")

        # Strip all fields that are incompatible with promptCreationMode=DEFAULT.
        # Only promptType and promptCreationMode are allowed in that mode.
        _DEFAULT_MODE_ONLY = {"promptType", "promptCreationMode"}
        for pc in data.get("promptConfigurations", []):
            if pc.get("promptCreationMode") == "DEFAULT":
                for key in list(pc.keys()):
                    if key not in _DEFAULT_MODE_ONLY:
                        del pc[key]

        return data

