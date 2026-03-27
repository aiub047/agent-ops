"""
End-to-end tests: full agent lifecycle (create → get → update → delete).

These tests run against a real AWS account (or LocalStack) and are skipped
by default in CI unless the E2E_TESTS=true environment variable is set.
Set E2E_TESTS=true and provide valid AWS credentials + BEDROCK_AGENT_ROLE_ARN
before running.
"""

import os
import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app

pytestmark = pytest.mark.skipif(
    os.getenv("E2E_TESTS", "false").lower() != "true",
    reason="E2E tests are skipped unless E2E_TESTS=true is set.",
)


@pytest.fixture(scope="module")
def e2e_client() -> TestClient:
    """TestClient backed by a real AWS-connected service."""
    get_settings.cache_clear()
    app = create_app()
    return TestClient(app)


class TestAgentLifecycle:
    """Full create → get → update → delete lifecycle against real AWS."""

    agent_id: str = ""

    def test_01_create_agent(self, e2e_client: TestClient) -> None:
        response = e2e_client.post(
            "/api/v1/agents",
            json={"definition_file": "senior-software-architect", "prepare": True},
        )
        assert response.status_code == 201
        data = response.json()
        assert "agentId" in data
        TestAgentLifecycle.agent_id = data["agentId"]

    def test_02_get_agent(self, e2e_client: TestClient) -> None:
        assert TestAgentLifecycle.agent_id, "agent_id not set – create test must run first"
        response = e2e_client.get(f"/api/v1/agents/{TestAgentLifecycle.agent_id}")
        assert response.status_code == 200
        assert response.json()["agentId"] == TestAgentLifecycle.agent_id

    def test_03_list_agents(self, e2e_client: TestClient) -> None:
        response = e2e_client.get("/api/v1/agents")
        assert response.status_code == 200
        ids = [item["agentId"] for item in response.json()["items"]]
        assert TestAgentLifecycle.agent_id in ids

    def test_04_update_agent(self, e2e_client: TestClient) -> None:
        assert TestAgentLifecycle.agent_id
        # Brief pause to avoid rapid consecutive mutations
        time.sleep(2)
        response = e2e_client.put(
            f"/api/v1/agents/{TestAgentLifecycle.agent_id}",
            json={"definition_file": "senior-software-architect", "prepare": True},
        )
        assert response.status_code == 200

    def test_05_delete_agent(self, e2e_client: TestClient) -> None:
        assert TestAgentLifecycle.agent_id
        response = e2e_client.delete(f"/api/v1/agents/{TestAgentLifecycle.agent_id}")
        assert response.status_code == 204

