"""
Unit tests for BedrockRepository.wait_until_stable.
"""

from unittest.mock import MagicMock, patch, call

import pytest
from botocore.exceptions import ClientError

from app.core.exceptions import BedrockServiceError
from app.repositories.bedrock_repository import BedrockRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client_error(code: str, message: str = "error") -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": message}},
        operation_name="PrepareAgent",
    )


def _make_repo(get_agent_side_effects: list) -> BedrockRepository:
    """Return a BedrockRepository whose internal boto3 client is fully mocked."""
    with patch("boto3.Session") as mock_session_cls:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.client.return_value = MagicMock()
        repo = BedrockRepository(region_name="us-east-1")

    # Replace the already-injected _client with a fresh mock
    repo._client = MagicMock()
    # get_agent is called through the public method which uses self._client.get_agent
    responses = iter(get_agent_side_effects)
    repo._client.get_agent.side_effect = lambda **_: {"agent": next(responses)}
    return repo


# ---------------------------------------------------------------------------
# wait_until_stable
# ---------------------------------------------------------------------------

class TestWaitUntilStable:

    def test_already_stable_returns_immediately(self) -> None:
        """Agent already in NOT_PREPARED – no sleep required."""
        repo = _make_repo([{"agentStatus": "NOT_PREPARED", "agentId": "X"}])
        with patch("time.sleep") as mock_sleep:
            result = repo.wait_until_stable("X", poll_interval=1.0, timeout=30.0)
        mock_sleep.assert_not_called()
        assert result["agentStatus"] == "NOT_PREPARED"

    def test_waits_through_creating_state(self) -> None:
        """Agent starts CREATING, then becomes NOT_PREPARED after one poll."""
        repo = _make_repo([
            {"agentStatus": "CREATING", "agentId": "X"},
            {"agentStatus": "NOT_PREPARED", "agentId": "X"},
        ])
        with patch("time.sleep") as mock_sleep:
            result = repo.wait_until_stable("X", poll_interval=2.0, timeout=30.0)
        mock_sleep.assert_called_once_with(2.0)
        assert result["agentStatus"] == "NOT_PREPARED"

    def test_waits_through_multiple_transient_states(self) -> None:
        """Agent cycles through CREATING → PREPARING → PREPARED."""
        repo = _make_repo([
            {"agentStatus": "CREATING", "agentId": "X"},
            {"agentStatus": "PREPARING", "agentId": "X"},
            {"agentStatus": "PREPARED", "agentId": "X"},
        ])
        with patch("time.sleep") as mock_sleep:
            result = repo.wait_until_stable("X", poll_interval=1.0, timeout=30.0)
        assert mock_sleep.call_count == 2
        assert result["agentStatus"] == "PREPARED"

    def test_raises_on_failed_status(self) -> None:
        """Agent enters FAILED state – BedrockServiceError must be raised."""
        repo = _make_repo([
            {"agentStatus": "CREATING", "agentId": "X"},
            {"agentStatus": "FAILED", "agentId": "X"},
        ])
        with patch("time.sleep"):
            with pytest.raises(BedrockServiceError, match="FAILED status"):
                repo.wait_until_stable("X", poll_interval=1.0, timeout=30.0)

    def test_raises_on_timeout(self) -> None:
        """If the agent stays CREATING past the timeout, a BedrockServiceError is raised."""
        # Always return CREATING so we hit the timeout
        repo = _make_repo([{"agentStatus": "CREATING", "agentId": "X"}] * 100)

        # Simulate monotonic time advancing beyond the timeout after 2 polls
        monotonic_values = [0.0, 0.0, 999.0]  # start, first check inside loop, second check
        with patch("time.sleep"), patch("time.monotonic", side_effect=monotonic_values):
            with pytest.raises(BedrockServiceError, match="Timed out"):
                repo.wait_until_stable("X", poll_interval=1.0, timeout=10.0)


# ---------------------------------------------------------------------------
# prepare_agent – integration with wait_until_stable
# ---------------------------------------------------------------------------

class TestPrepareAgent:

    def test_prepare_agent_waits_then_prepares(self) -> None:
        """prepare_agent must call wait_until_stable before calling the AWS API."""
        repo = _make_repo([
            {"agentStatus": "CREATING", "agentId": "X"},
            {"agentStatus": "NOT_PREPARED", "agentId": "X"},
        ])
        repo._client.prepare_agent.return_value = {"agentVersion": "DRAFT", "agentStatus": "PREPARING"}

        with patch("time.sleep"):
            version = repo.prepare_agent("X")

        assert version == "DRAFT"
        repo._client.prepare_agent.assert_called_once_with(agentId="X")

    def test_prepare_agent_raises_on_client_error(self) -> None:
        """ClientError from prepare_agent must be translated to BedrockServiceError."""
        repo = _make_repo([{"agentStatus": "NOT_PREPARED", "agentId": "X"}])
        repo._client.prepare_agent.side_effect = _make_client_error(
            "ValidationException", "Prepare not allowed"
        )

        with pytest.raises(BedrockServiceError):
            repo.prepare_agent("X")

