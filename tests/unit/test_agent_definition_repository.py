"""
Unit tests for AgentDefinitionRepository.
"""

from pathlib import Path

import pytest

from app.core.exceptions import AgentDefinitionNotFoundError, AgentDefinitionParseError
from app.repositories.agent_definition_repository import AgentDefinitionRepository


VALID_YAML = """
apiVersion: agentops/v1
kind: BedrockAgent
metadata:
  name: test-agent
spec:
  model:
    id: anthropic.claude-3-5-sonnet-20241022-v2:0
  instruction: You are a test assistant.
"""

INVALID_YAML = """
apiVersion: agentops/v1
kind: BedrockAgent
metadata:
  name: bad-agent
spec:
  # missing required 'model' and 'instruction'
  description: incomplete
"""


class TestAgentDefinitionRepository:
    def setup_method(self, tmp_path_factory) -> None:
        pass

    def test_get_returns_valid_definition(self, tmp_path: Path) -> None:
        d = tmp_path / "defs"
        d.mkdir()
        (d / "test-agent.agent.yaml").write_text(VALID_YAML, encoding="utf-8")
        repo = AgentDefinitionRepository(d)
        definition = repo.get("test-agent")
        assert definition.metadata.name == "test-agent"
        assert definition.spec.model.id == "anthropic.claude-3-5-sonnet-20241022-v2:0"

    def test_get_raises_not_found_for_missing_file(self, tmp_path: Path) -> None:
        repo = AgentDefinitionRepository(tmp_path)
        with pytest.raises(AgentDefinitionNotFoundError):
            repo.get("nonexistent-agent")

    def test_get_raises_parse_error_for_invalid_schema(self, tmp_path: Path) -> None:
        d = tmp_path / "defs"
        d.mkdir()
        (d / "bad-agent.agent.yaml").write_text(INVALID_YAML, encoding="utf-8")
        repo = AgentDefinitionRepository(d)
        with pytest.raises(AgentDefinitionParseError):
            repo.get("bad-agent")

    def test_get_raises_parse_error_for_malformed_yaml(self, tmp_path: Path) -> None:
        d = tmp_path / "defs"
        d.mkdir()
        (d / "broken.agent.yaml").write_text(":\t: invalid::", encoding="utf-8")
        repo = AgentDefinitionRepository(d)
        with pytest.raises(AgentDefinitionParseError):
            repo.get("broken")

    def test_list_definitions_returns_names(self, tmp_path: Path) -> None:
        d = tmp_path / "defs"
        d.mkdir()
        (d / "agent-a.agent.yaml").write_text(VALID_YAML, encoding="utf-8")
        (d / "agent-b.yaml").write_text(VALID_YAML, encoding="utf-8")
        repo = AgentDefinitionRepository(d)
        names = repo.list_definitions()
        assert "agent-a" in names
        assert "agent-b" in names

    def test_list_definitions_returns_empty_for_missing_dir(self, tmp_path: Path) -> None:
        repo = AgentDefinitionRepository(tmp_path / "nonexistent")
        assert repo.list_definitions() == []

