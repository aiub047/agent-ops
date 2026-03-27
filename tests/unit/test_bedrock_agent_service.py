"""
Unit tests for BedrockAgentService.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.repositories.agent_definition_repository import AgentDefinitionRepository
from app.repositories.bedrock_repository import BedrockRepository
from app.services.bedrock_agent_service import BedrockAgentService
from tests.conftest import SAMPLE_BEDROCK_AGENT

ROLE_ARN = "arn:aws:iam::123456789012:role/BedrockAgentRole"

SAMPLE_DEFINITION_YAML_WITH_ROLE = f"""
apiVersion: agentops/v1
kind: BedrockAgent
metadata:
  name: test-agent
spec:
  model:
    id: anthropic.claude-3-5-sonnet-20241022-v2:0
  instruction: You are a test assistant.
  deployment:
    region: us-east-1
    roleArn: {ROLE_ARN}
"""


@pytest.fixture
def definition_repo(tmp_path: Path) -> AgentDefinitionRepository:
    d = tmp_path / "defs"
    d.mkdir()
    (d / "test-agent.agent.yaml").write_text(SAMPLE_DEFINITION_YAML_WITH_ROLE, encoding="utf-8")
    return AgentDefinitionRepository(d)


@pytest.fixture
def bedrock_repo() -> MagicMock:
    repo = MagicMock(spec=BedrockRepository)
    repo.create_agent.return_value = SAMPLE_BEDROCK_AGENT
    repo.get_agent.return_value = SAMPLE_BEDROCK_AGENT
    repo.list_agents.return_value = {"agentSummaries": [
        {"agentId": "ABCDEF1234", "agentName": "test-agent", "agentStatus": "PREPARED"}
    ]}
    repo.update_agent.return_value = SAMPLE_BEDROCK_AGENT
    repo.prepare_agent.return_value = "DRAFT"
    return repo


@pytest.fixture
def service(bedrock_repo: MagicMock, definition_repo: AgentDefinitionRepository) -> BedrockAgentService:
    return BedrockAgentService(
        bedrock_repo=bedrock_repo,
        definition_repo=definition_repo,
        default_role_arn=ROLE_ARN,
    )


class TestBedrockAgentService:
    def test_create_agent_from_definition(
        self, service: BedrockAgentService, bedrock_repo: MagicMock
    ) -> None:
        result = service.create_agent_from_definition("test-agent", prepare=True)
        bedrock_repo.create_agent.assert_called_once()
        bedrock_repo.prepare_agent.assert_called_once_with(SAMPLE_BEDROCK_AGENT["agentId"])
        assert result.agent_id == SAMPLE_BEDROCK_AGENT["agentId"]

    def test_create_agent_without_prepare(
        self, service: BedrockAgentService, bedrock_repo: MagicMock
    ) -> None:
        service.create_agent_from_definition("test-agent", prepare=False)
        bedrock_repo.prepare_agent.assert_not_called()

    def test_get_agent(self, service: BedrockAgentService, bedrock_repo: MagicMock) -> None:
        result = service.get_agent("ABCDEF1234")
        bedrock_repo.get_agent.assert_called_once_with("ABCDEF1234")
        assert result.agent_name == "test-agent"

    def test_list_agents(self, service: BedrockAgentService, bedrock_repo: MagicMock) -> None:
        result = service.list_agents()
        assert result.total == 1
        assert result.items[0].agent_id == "ABCDEF1234"

    def test_update_agent_from_definition(
        self, service: BedrockAgentService, bedrock_repo: MagicMock
    ) -> None:
        result = service.update_agent_from_definition("ABCDEF1234", "test-agent", prepare=True)
        bedrock_repo.update_agent.assert_called_once()
        bedrock_repo.prepare_agent.assert_called_once_with("ABCDEF1234")
        assert result.agent_id == "ABCDEF1234"

    def test_delete_agent(self, service: BedrockAgentService, bedrock_repo: MagicMock) -> None:
        service.delete_agent("ABCDEF1234")
        bedrock_repo.delete_agent.assert_called_once_with("ABCDEF1234")

    def test_list_definitions(self, service: BedrockAgentService) -> None:
        names = service.list_definitions()
        assert "test-agent" in names

