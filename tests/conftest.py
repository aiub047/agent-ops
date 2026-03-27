"""
Shared test fixtures for agent-ops test suite.
"""

from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings


SAMPLE_DEFINITION_YAML = """
apiVersion: agentops/v1
kind: BedrockAgent
metadata:
  name: test-agent
  version: 1.0.0
spec:
  description: Test agent for unit tests.
  model:
    id: anthropic.claude-3-5-sonnet-20241022-v2:0
    temperature: 0.2
    topP: 0.9
    maxTokens: 1024
  instruction: |
    You are a test assistant.
  aliases:
    - name: dev
  k8s:
    region: us-east-1
    roleArn: arn:aws:iam::123456789012:role/TestAgentRole
"""

SAMPLE_BEDROCK_AGENT = {
    "agentId": "ABCDEF1234",
    "agentName": "test-agent",
    "agentStatus": "NOT_PREPARED",
    "agentArn": "arn:aws:bedrock:us-east-1:123456789012:agent/ABCDEF1234",
    "agentVersion": "DRAFT",
    "foundationModel": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "description": "Test agent for unit tests.",
    "instruction": "You are a test assistant.",
    "idleSessionTTLInSeconds": 1800,
    "createdAt": "2026-01-01T00:00:00Z",
    "updatedAt": "2026-01-01T00:00:00Z",
}


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Return a Settings instance pointing to a temporary agent-definition directory."""
    return Settings(
        APP_ENV="local",
        AWS_REGION="us-east-1",
        DEFAULT_BEDROCK_AGENT_ROLE_ARN="arn:aws:iam::123456789012:role/BedrockAgentRole",
        AGENT_DEFINITION_DIR=str(tmp_path / "agent-definition"),
    )


@pytest.fixture
def definition_dir(tmp_path: Path) -> Path:
    """Create a temporary agent-definition directory with one sample YAML."""
    d = tmp_path / "agent-definition"
    d.mkdir()
    (d / "test-agent.agent.yaml").write_text(SAMPLE_DEFINITION_YAML, encoding="utf-8")
    return d


@pytest.fixture
def mock_bedrock_client() -> Generator[MagicMock, None, None]:
    """Patch boto3 client used by BedrockRepository."""
    with patch("boto3.Session") as mock_session:
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client

        mock_client.create_agent.return_value = {"agent": SAMPLE_BEDROCK_AGENT}
        mock_client.get_agent.return_value = {"agent": SAMPLE_BEDROCK_AGENT}
        mock_client.list_agents.return_value = {
            "agentSummaries": [
                {
                    "agentId": "ABCDEF1234",
                    "agentName": "test-agent",
                    "agentStatus": "PREPARED",
                }
            ]
        }
        mock_client.update_agent.return_value = {"agent": SAMPLE_BEDROCK_AGENT}
        mock_client.delete_agent.return_value = {}
        mock_client.prepare_agent.return_value = {"agentVersion": "DRAFT"}

        yield mock_client


@pytest.fixture
def test_client(definition_dir: Path, mock_bedrock_client: MagicMock) -> TestClient:
    """Return a TestClient with overridden settings and mocked AWS."""
    from app.api.dependencies import (
        get_bedrock_repository,
        get_definition_repository,
        get_settings,
    )
    from app.main import create_app
    from app.repositories.agent_definition_repository import AgentDefinitionRepository
    from app.repositories.bedrock_repository import BedrockRepository

    override_settings = Settings(
        APP_ENV="local",
        AWS_REGION="us-east-1",
        DEFAULT_BEDROCK_AGENT_ROLE_ARN="arn:aws:iam::123456789012:role/BedrockAgentRole",
        AGENT_DEFINITION_DIR=str(definition_dir),
    )

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: override_settings
    app.dependency_overrides[get_definition_repository] = lambda: AgentDefinitionRepository(
        definition_dir=str(definition_dir)
    )
    app.dependency_overrides[get_bedrock_repository] = lambda: BedrockRepository(
        region_name="us-east-1"
    )
    return TestClient(app)

