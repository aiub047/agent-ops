"""
Bedrock Repository.

Wraps the low-level boto3 ``bedrock-agent`` client and translates AWS SDK
exceptions into domain exceptions so upper layers stay decoupled from boto3.
"""

import time
from typing import Any, NoReturn

import boto3
from botocore.exceptions import ClientError, ParamValidationError

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
        # Separate client for control-plane operations (model listing, inference profiles).
        self._bedrock_client = session.client("bedrock", region_name=region_name)

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
        except ParamValidationError as exc:
            raise BedrockServiceError(f"Invalid parameters for create_agent: {exc}") from exc
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
        except ParamValidationError as exc:
            raise BedrockServiceError(f"Invalid parameters for update_agent({agent_id}): {exc}") from exc
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
        except ParamValidationError as exc:
            raise BedrockServiceError(f"Invalid parameters for delete_agent({agent_id}): {exc}") from exc
        except ClientError as exc:
            self._handle_client_error(exc, context=f"delete_agent({agent_id})")

    # ── Model / inference-profile listing ────────────────────────────────────

    def list_foundation_models(self) -> list[dict[str, Any]]:
        """
        Return all text-output foundation models that support on-demand throughput.

        Filters applied:
        * ``byOutputModality=TEXT`` – only text-generation models.
        * ``byInferenceType=ON_DEMAND`` – excludes models that require
          provisioned throughput (not usable in agent definitions).

        Returns:
            list[dict]: Each item contains at least ``modelId``, ``modelName``,
            ``providerName``, ``inputModalities``, and ``inferenceTypesSupported``.
        """
        logger.info("Listing Bedrock foundation models")
        try:
            response = self._bedrock_client.list_foundation_models(
                byOutputModality="TEXT",
                byInferenceType="ON_DEMAND",
            )
            return response.get("modelSummaries", [])
        except ClientError as exc:
            self._handle_client_error(exc, context="list_foundation_models")

    def list_inference_profiles(self) -> list[dict[str, Any]]:
        """
        Return all system-defined cross-region inference profiles.

        These are the ``us.*`` / ``eu.*`` / ``ap.*`` prefixed IDs that Bedrock
        requires for models (like Meta Llama) that do not allow bare on-demand
        invocation via their foundation-model ID.

        Returns:
            list[dict]: Each item contains at least ``inferenceProfileId``,
            ``inferenceProfileName``, ``status``, and ``type``.
        """
        logger.info("Listing Bedrock inference profiles")
        try:
            response = self._bedrock_client.list_inference_profiles(
                typeEquals="SYSTEM_DEFINED",
            )
            return response.get("inferenceProfileSummaries", [])
        except ClientError as exc:
            self._handle_client_error(exc, context="list_inference_profiles")

    # Bedrock agent statuses that indicate the agent is still transitioning and
    # cannot yet accept a PrepareAgent or UpdateAgent call.
    _TRANSIENT_STATUSES: frozenset[str] = frozenset({"CREATING", "UPDATING", "PREPARING", "VERSIONING"})

    def wait_until_stable(
        self,
        agent_id: str,
        *,
        poll_interval: float = 3.0,
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        """
        Poll ``GetAgent`` until the agent leaves all transient states.

        Bedrock agent creation/update is asynchronous. Calling ``PrepareAgent``
        while the agent is still in ``CREATING`` (or ``UPDATING``) raises a
        ``ValidationException``. This method blocks until the agent reaches a
        stable status (``NOT_PREPARED``, ``PREPARED``, ``FAILED``, etc.) or the
        timeout is exceeded.

        Args:
            agent_id: Bedrock agent identifier.
            poll_interval: Seconds to wait between status checks.
            timeout: Maximum seconds to wait before raising an error.

        Returns:
            dict: The latest ``agent`` object from Bedrock.

        Raises:
            BedrockServiceError: If the agent enters ``FAILED`` status or the
                timeout is exceeded while still in a transient state.
        """
        deadline = time.monotonic() + timeout
        while True:
            agent = self.get_agent(agent_id)
            status: str = agent.get("agentStatus", "")
            logger.debug("Agent %s status: %s", agent_id, status)

            if status == "FAILED":
                raise BedrockServiceError(
                    f"Agent {agent_id} entered FAILED status while waiting for it to become stable."
                )

            if status not in self._TRANSIENT_STATUSES:
                logger.info("Agent %s is now stable with status: %s", agent_id, status)
                return agent

            if time.monotonic() >= deadline:
                raise BedrockServiceError(
                    f"Timed out waiting for agent {agent_id} to leave transient status '{status}' "
                    f"after {timeout}s. Try increasing the timeout."
                )

            logger.info(
                "Agent %s is in transient status '%s', retrying in %.1fs…",
                agent_id,
                status,
                poll_interval,
            )
            time.sleep(poll_interval)

    def wait_until_deleted(
        self,
        agent_id: str,
        *,
        poll_interval: float = 3.0,
        timeout: float = 120.0,
    ) -> None:
        """
        Poll ``GetAgent`` until the agent no longer exists.

        ``DeleteAgent`` returns before the name is fully released in Bedrock.
        Calling ``CreateAgent`` with the same name immediately after delete can
        raise a ``ConflictException``.  This method blocks until
        ``GetAgent`` returns ``ResourceNotFoundException``, confirming the agent
        has been fully removed and the name is free to reuse.

        Args:
            agent_id: Bedrock agent identifier that was just deleted.
            poll_interval: Seconds to wait between status checks.
            timeout: Maximum seconds to wait before raising an error.

        Raises:
            BedrockServiceError: If the timeout is exceeded before the agent
                disappears.
        """
        deadline = time.monotonic() + timeout
        while True:
            try:
                self.get_agent(agent_id)
            except AgentNotFoundError:
                logger.info("Agent %s has been fully deleted.", agent_id)
                return

            if time.monotonic() >= deadline:
                raise BedrockServiceError(
                    f"Timed out waiting for agent {agent_id} to be fully deleted "
                    f"after {timeout}s."
                )

            logger.info(
                "Agent %s still exists after delete; retrying in %.1fs…",
                agent_id,
                poll_interval,
            )
            time.sleep(poll_interval)

    def list_tags_for_resource(self, resource_arn: str) -> dict[str, str]:
        """
        Return the tags attached to a Bedrock resource.

        The Bedrock ``GetAgent`` and ``CreateAgent`` responses do **not** include
        tags in the returned ``agent`` object; tags are stored separately and must
        be fetched via this call using the agent's ARN.

        Args:
            resource_arn: Full ARN of the Bedrock resource (e.g. agent ARN).

        Returns:
            dict[str, str]: Key/value tag map (empty dict when none are set).
        """
        logger.debug("Fetching tags for resource: %s", resource_arn)
        try:
            response = self._client.list_tags_for_resource(resourceArn=resource_arn)
            return response.get("tags", {})
        except ClientError as exc:
            # Non-fatal: log and return empty rather than breaking the main call.
            code = exc.response["Error"]["Code"]
            logger.warning("Could not fetch tags for %s [%s]: %s", resource_arn, code, exc)
            return {}

    def prepare_agent(self, agent_id: str) -> str:
        """
        Wait for the agent to be stable, then call ``PrepareAgent``.

        Bedrock requires the agent to be out of ``CREATING``/``UPDATING`` state
        before ``PrepareAgent`` can be invoked. This method transparently polls
        until the agent is ready and then issues the prepare call.

        Args:
            agent_id: Bedrock agent identifier.

        Returns:
            str: The prepared agent version string.
        """
        logger.info("Waiting for agent %s to be stable before preparing…", agent_id)
        self.wait_until_stable(agent_id)

        logger.info("Preparing Bedrock agent: %s", agent_id)
        try:
            response = self._client.prepare_agent(agentId=agent_id)
            return response.get("agentVersion", "DRAFT")
        except ClientError as exc:
            self._handle_client_error(exc, context=f"prepare_agent({agent_id})")

    # ── Error handling ────────────────────────────────────────────────────────

    @staticmethod
    def _handle_client_error(exc: ClientError, context: str) -> NoReturn:
        code = exc.response["Error"]["Code"]
        message = exc.response["Error"]["Message"]
        logger.error("Bedrock ClientError [%s] during %s: %s", code, context, message)

        if code in ("ResourceNotFoundException",):
            raise AgentNotFoundError(f"Agent not found ({context}): {message}") from exc

        raise BedrockServiceError(
            f"AWS Bedrock error during {context} [{code}]: {message}"
        ) from exc

