"""
Service Protocol (interface) for agent management operations.

Defines the contract that all concrete service implementations must satisfy,
enabling dependency injection and easy unit-test substitution.
"""

from typing import Protocol, runtime_checkable

from app.models.agent import AgentResponse, AgentSummary, BedrockModelsResponse
from app.models.common import PaginatedResponse
from app.schemas.agent_definition import AgentDefinition


@runtime_checkable
class AgentServiceProtocol(Protocol):
    """Abstract interface for the agent management service."""

    def create_agent(
        self,
        definition: AgentDefinition,
        prepare: bool = True,
    ) -> AgentResponse:
        """Create a new Bedrock agent from a parsed definition."""
        ...

    def get_agent(self, agent_id: str) -> AgentResponse:
        """Return the details of a single agent by its Bedrock ID."""
        ...

    def list_agents(
        self,
        max_results: int = 50,
        next_token: str | None = None,
    ) -> PaginatedResponse[AgentSummary]:
        """Return a paginated list of all agents."""
        ...

    def update_agent(
        self,
        agent_id: str,
        definition: AgentDefinition,
        prepare: bool = True,
    ) -> AgentResponse:
        """Update an existing agent with a new definition."""
        ...

    def delete_agent(self, agent_id: str) -> None:
        """Permanently delete an agent."""
        ...

    def list_bedrock_models(self) -> BedrockModelsResponse:
        """Return all usable foundation model IDs and inference profile IDs."""
        ...

    def create_or_update_agent_from_definition(
        self,
        definition_file: str,
        prepare: bool = True,
        recreate: bool = False,
    ) -> AgentResponse:
        """Create a new agent or update (or recreate) an existing one by name."""
        ...

    def deploy_yml(
        self,
        agent_key: str,
        yaml_data: str | dict,
        redeploy: bool,
        recreate: bool = False,
    ) -> tuple[AgentResponse, bool]:
        """Deploy from inline YAML string or JSON object; conflict-guard when redeploy=False.

        Returns:
            tuple[AgentResponse, bool]: Agent details and ``True`` if the agent was
            **created** (HTTP 201), ``False`` if it was **updated** (HTTP 200).

        When ``redeploy=True`` and the agent already exists:
        * ``recreate=False`` — update in-place (requires ``bedrock:UpdateAgent``).
        * ``recreate=True``  — delete then create fresh (no ``bedrock:UpdateAgent`` needed).
        """
        ...

