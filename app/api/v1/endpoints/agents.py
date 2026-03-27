"""
Agent API endpoints (v1).

Provides CRUD operations for Amazon Bedrock Agents driven by YAML definition files.

Routes:
    POST   /agents              – create agent from definition file
    GET    /agents              – list all agents
    GET    /agents/definitions  – list available definition files
    GET    /agents/{agent_id}   – get a specific agent
    PUT    /agents/{agent_id}   – update agent from definition file
    DELETE /agents/{agent_id}   – delete agent
"""

from fastapi import APIRouter, Query, status

from app.api.dependencies import AgentServiceDep
from app.models.agent import (
    AgentResponse,
    AgentSummary,
    CreateAgentFromDefinitionRequest,
    UpdateAgentFromDefinitionRequest,
)
from app.models.common import PaginatedResponse

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/version", summary="Get API version")
def version() -> str:
    return "1.0.2"


@router.post(
    "",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Bedrock agent from a YAML definition file",
    response_description="The newly created agent.",
)
def create_agent(
        request: CreateAgentFromDefinitionRequest,
        service: AgentServiceDep,
) -> AgentResponse:
    """
    Read the agent definition YAML from the ``agent-definition`` directory by
    filename, validate it, and create the corresponding Amazon Bedrock agent.

    The ``definition_file`` parameter should be the base name of the YAML file
    without its extension (e.g. ``senior-software-architect``).
    """
    return service.create_agent_from_definition(
        definition_file=request.definition_file,
        prepare=request.prepare,
    )


@router.get(
    "",
    response_model=PaginatedResponse[AgentSummary],
    summary="List all Bedrock agents",
)
def list_agents(
        service: AgentServiceDep,
        max_results: int = Query(50, ge=1, le=100, description="Page size."),
        next_token: str | None = Query(None, description="Pagination token from a previous response."),
) -> PaginatedResponse[AgentSummary]:
    """Return a paginated list of all Amazon Bedrock agents in the configured region."""
    return service.list_agents(max_results=max_results, next_token=next_token)


@router.get(
    "/definitions",
    response_model=list[str],
    summary="List available agent definition files",
)
def list_definitions(service: AgentServiceDep) -> list[str]:
    """
    Return the names of all ``.agent.yaml`` files found in the
    ``agent-definition`` directory.  Use any of these names as the
    ``definition_file`` parameter when creating or updating an agent.
    """
    return service.list_definitions()


@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Get a Bedrock agent by ID",
)
def get_agent(
        agent_id: str,
        service: AgentServiceDep,
) -> AgentResponse:
    """Retrieve details for the Bedrock agent identified by *agent_id*."""
    return service.get_agent(agent_id)


@router.put(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Update a Bedrock agent from a YAML definition file",
)
def update_agent(
        agent_id: str,
        request: UpdateAgentFromDefinitionRequest,
        service: AgentServiceDep,
) -> AgentResponse:
    """
    Update an existing Bedrock agent using the specified YAML definition file.
    If ``prepare`` is ``true``, the agent is re-prepared after the update so
    it is immediately available for invocation.
    """
    return service.update_agent_from_definition(
        agent_id=agent_id,
        definition_file=request.definition_file,
        prepare=request.prepare,
    )


@router.delete(
    "/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Bedrock agent",
)
def delete_agent(
        agent_id: str,
        service: AgentServiceDep,
) -> None:
    """Permanently delete the Bedrock agent identified by *agent_id*."""
    service.delete_agent(agent_id)
