"""
Integration tests for the /api/v1/agents endpoints.
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from tests.conftest import SAMPLE_BEDROCK_AGENT


class TestAgentsAPI:
    def test_health_check(self, test_client: TestClient) -> None:
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_create_agent(self, test_client: TestClient, mock_bedrock_client: MagicMock) -> None:
        response = test_client.post(
            "/api/v1/agents",
            json={"definition_file": "test-agent", "prepare": False},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["agentId"] == SAMPLE_BEDROCK_AGENT["agentId"]
        assert data["agentName"] == "test-agent"

    def test_create_agent_not_found(self, test_client: TestClient) -> None:
        response = test_client.post(
            "/api/v1/agents",
            json={"definition_file": "nonexistent", "prepare": False},
        )
        assert response.status_code == 404

    def test_list_agents(self, test_client: TestClient, mock_bedrock_client: MagicMock) -> None:
        response = test_client.get("/api/v1/agents")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] >= 0

    def test_list_definitions(self, test_client: TestClient) -> None:
        response = test_client.get("/api/v1/agents/definitions")
        assert response.status_code == 200
        names = response.json()
        assert "test-agent" in names

    def test_get_agent(self, test_client: TestClient, mock_bedrock_client: MagicMock) -> None:
        response = test_client.get(f"/api/v1/agents/{SAMPLE_BEDROCK_AGENT['agentId']}")
        assert response.status_code == 200
        assert response.json()["agentId"] == SAMPLE_BEDROCK_AGENT["agentId"]

    def test_update_agent(self, test_client: TestClient, mock_bedrock_client: MagicMock) -> None:
        response = test_client.put(
            f"/api/v1/agents/{SAMPLE_BEDROCK_AGENT['agentId']}",
            json={"definition_file": "test-agent", "prepare": False},
        )
        assert response.status_code == 200

    def test_delete_agent(self, test_client: TestClient, mock_bedrock_client: MagicMock) -> None:
        response = test_client.delete(f"/api/v1/agents/{SAMPLE_BEDROCK_AGENT['agentId']}")
        assert response.status_code == 204

