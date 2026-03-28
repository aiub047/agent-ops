"""
Bedrock Agent Service.

Orchestrates agent CRUD operations by combining the AgentDefinitionRepository
(reads YAML files) with the BedrockRepository (calls AWS Bedrock APIs).
Implements AgentServiceProtocol so it can be swapped in tests.
"""

from app.core.exceptions import BedrockServiceError
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

        return AgentResponse.model_validate(raw)

    def get_agent(self, agent_id: str) -> AgentResponse:
        """
        Retrieve a single Bedrock agent by ID.

        Args:
            agent_id: Bedrock-assigned agent identifier.

        Returns:
            AgentResponse: Agent details.
        """
        raw = self._bedrock.get_agent(agent_id)
        return AgentResponse.model_validate(raw)

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

        return AgentResponse.model_validate(raw)

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
            return self.create_agent(definition, prepare=prepare)

        logger.info(
            "Agent '%s' (%s) exists; updating in-place (recreate=False).",
            agent_name,
            existing_id,
        )
        return self.update_agent(existing_id, definition, prepare=prepare)

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
        """
        Return all foundation models and cross-region inference profiles usable
        in an agent definition YAML.

        Foundation models are filtered to text-output, on-demand models.
        Inference profiles are system-defined cross-region profiles (``us.*``,
        ``eu.*``, ``ap.*``) required by models like Meta Llama.

        Returns:
            BedrockModelsResponse: Combined listing of model IDs and profile IDs.
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

    # ── Private helpers ───────────────────────────────────────────────────────

    def _resolve_role_arn(self, definition: AgentDefinition) -> str:
        """
        Return the IAM role ARN for the agent.

        Resolution order:
        1. ``spec.k8s.roleArn`` in the agent definition YAML (preferred –
           gives each agent its own least-privilege role).
        2. ``default_role_arn`` supplied at service construction time (from the
           ``DEFAULT_BEDROCK_AGENT_ROLE_ARN`` env var) – a convenience fallback
           for simple/shared setups.

        Raises:
            BedrockServiceError: If neither source provides a role ARN.
        """
        role_arn = (definition.spec.deployment.role_arn or self._default_role_arn or "").strip()
        if not role_arn:
            raise BedrockServiceError(
                f"No IAM role ARN found for agent '{definition.metadata.name}'. "
                "Set 'spec.k8s.roleArn' in the agent definition YAML, "
                "or set DEFAULT_BEDROCK_AGENT_ROLE_ARN in the environment as a fallback."
            )
        return role_arn

    def _build_create_params(self, definition: AgentDefinition) -> dict:
        spec = definition.spec
        params: dict = {
            "agentName": definition.metadata.name,
            "agentResourceRoleArn": self._resolve_role_arn(definition),
            "foundationModel": spec.model.id,
            "instruction": spec.instruction,
            "idleSessionTTLInSeconds": spec.session.idle_ttl_seconds,
        }
        if spec.description:
            params["description"] = spec.description
        if definition.metadata.tags:
            params["tags"] = definition.metadata.tags
        if spec.guardrails.enabled and spec.guardrails.guardrail_id:
            params["guardrailConfiguration"] = {
                "guardrailIdentifier": spec.guardrails.guardrail_id,
                "guardrailVersion": spec.guardrails.guardrail_version or "DRAFT",
            }
        return params

    def _build_update_params(self, definition: AgentDefinition) -> dict:
        spec = definition.spec
        params: dict = {
            "agentName": definition.metadata.name,
            "agentResourceRoleArn": self._resolve_role_arn(definition),
            "foundationModel": spec.model.id,
            "instruction": spec.instruction,
            "idleSessionTTLInSeconds": spec.session.idle_ttl_seconds,
        }
        if spec.description:
            params["description"] = spec.description
        if spec.guardrails.enabled and spec.guardrails.guardrail_id:
            params["guardrailConfiguration"] = {
                "guardrailIdentifier": spec.guardrails.guardrail_id,
                "guardrailVersion": spec.guardrails.guardrail_version or "DRAFT",
            }
        return params

