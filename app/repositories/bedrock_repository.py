"""
Bedrock Repository.

Wraps the low-level boto3 ``bedrock-agent`` client and translates AWS SDK
exceptions into domain exceptions so upper layers stay decoupled from boto3.
"""

from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.core.exceptions import AgentNotFoundError, BedrockServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)


class BedrockRepository:
    """
    Thin data-access wrapper around the AWS ``bedrock-agent`` boto3 client.

    All methods raise :class:`~app.core.exceptions.AgentNotFoundError` for
    404-equivalent errors and :class:`~app.core.exceptions.BedrockServiceError`
    for all other AWS errors.

    Args:
        region_name: AWS region to target.
        profile_name: Optional AWS profile (used for local/dev; omit in prod).
    """

    def __init__(self, region_name: str, profile_name: str | None = None) -> None:
        session = (
            boto3.Session(profile_name=profile_name)
            if profile_name
            else boto3.Session()
        )
        self._client = session.client("bedrock-agent", region_name=region_name)

    # ── Agent CRUD ────────────────────────────────────────────────────────────

    def create_agent(self, **kwargs: Any) -> dict[str, Any]:
        """
        Call ``CreateAgent``.

        Args:
            **kwargs: Parameters passed directly to the boto3 ``create_agent`` call.

        Returns:
            dict: The ``agent`` object from the Bedrock response.
        """
        logger.info("Creating Bedrock agent: %s", kwargs.get("agentName"))
        try:
            response = self._client.create_agent(**kwargs)
            return response["agent"]
        except ClientError as exc:
            self._handle_client_error(exc, context="create_agent")

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        """
        Call ``GetAgent``.

        Args:
            agent_id: Bedrock agent identifier.

        Returns:
            dict: The ``agent`` object from the Bedrock response.
        """
        logger.info("Fetching Bedrock agent: %s", agent_id)
        try:
            response = self._client.get_agent(agentId=agent_id)
            return response["agent"]
        except ClientError as exc:
            self._handle_client_error(exc, context=f"get_agent({agent_id})")

    def list_agents(self, max_results: int = 50, next_token: str | None = None) -> dict[str, Any]:
        """
        Call ``ListAgents``.

        Args:
            max_results: Maximum number of results per page.
            next_token: Pagination token from a previous response.

        Returns:
            dict: Contains ``agentSummaries`` and optional ``nextToken``.
        """
        logger.info("Listing Bedrock agents")
        params: dict[str, Any] = {"maxResults": max_results}
        if next_token:
            params["nextToken"] = next_token
        try:
            return self._client.list_agents(**params)
        except ClientError as exc:
            self._handle_client_error(exc, context="list_agents")

    def update_agent(self, agent_id: str, **kwargs: Any) -> dict[str, Any]:
        """
        Call ``UpdateAgent``.

        Args:
            agent_id: Bedrock agent identifier.
            **kwargs: Additional parameters for the update call.

        Returns:
            dict: The updated ``agent`` object.
        """
        logger.info("Updating Bedrock agent: %s", agent_id)
        try:
            response = self._client.update_agent(agentId=agent_id, **kwargs)
            return response["agent"]
        except ClientError as exc:
            self._handle_client_error(exc, context=f"update_agent({agent_id})")

    def delete_agent(self, agent_id: str) -> None:
        """
        Call ``DeleteAgent``.

        Args:
            agent_id: Bedrock agent identifier.
        """
        logger.info("Deleting Bedrock agent: %s", agent_id)
        try:
            self._client.delete_agent(agentId=agent_id, skipResourceInUseCheck=False)
        except ClientError as exc:
            self._handle_client_error(exc, context=f"delete_agent({agent_id})")

    def prepare_agent(self, agent_id: str) -> str:
        """
        Call ``PrepareAgent`` to make the agent available for testing/invocation.

        Args:
            agent_id: Bedrock agent identifier.

        Returns:
            str: The prepared agent version string.
        """
        logger.info("Preparing Bedrock agent: %s", agent_id)
        try:
            response = self._client.prepare_agent(agentId=agent_id)
            return response.get("agentVersion", "DRAFT")
        except ClientError as exc:
            self._handle_client_error(exc, context=f"prepare_agent({agent_id})")

    # ── Error handling ────────────────────────────────────────────────────────

    @staticmethod
    def _handle_client_error(exc: ClientError, context: str) -> None:
        code = exc.response["Error"]["Code"]
        message = exc.response["Error"]["Message"]
        logger.error("Bedrock ClientError [%s] during %s: %s", code, context, message)

        if code in ("ResourceNotFoundException",):
            raise AgentNotFoundError(f"Agent not found ({context}): {message}") from exc

        raise BedrockServiceError(
            f"AWS Bedrock error during {context} [{code}]: {message}"
        ) from exc

