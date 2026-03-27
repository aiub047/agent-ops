# API Reference

Base URL: `http://localhost:8000`

Interactive docs (local/dev): `http://localhost:8000/docs`

---

## Health

### `GET /health`
Liveness probe.

**Response 200**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "environment": "local"
}
```

---

## Agents  `/api/v1/agents`

### `POST /api/v1/agents`
Create a Bedrock agent from a YAML definition file.

**Request body**
```json
{
  "definition_file": "senior-software-architect",
  "prepare": true
}
```

| Field             | Type    | Required | Description                                                        |
|-------------------|---------|----------|--------------------------------------------------------------------|
| `definition_file` | string  | ✅       | Filename (without extension) inside `agent-definition/` directory |
| `prepare`         | boolean |          | Call PrepareAgent after creation (default: `true`)                |

**Response 201**
```json
{
  "agentId": "ABCDEF1234",
  "agentName": "senior-software-architect",
  "agentArn": "arn:aws:bedrock:us-east-1:...:agent/ABCDEF1234",
  "agentVersion": "DRAFT",
  "agentStatus": "PREPARED",
  "foundationModel": "anthropic.claude-3-5-sonnet-20241022-v2:0",
  "description": "Senior Software Architect assistant...",
  "instruction": "You are a Senior Software Architect...",
  "idleSessionTTLInSeconds": 1800,
  "createdAt": "2026-01-01T00:00:00Z",
  "updatedAt": "2026-01-01T00:00:00Z"
}
```

**Error responses**

| Status | Condition                                  |
|--------|--------------------------------------------|
| 404    | Definition file not found                  |
| 422    | Definition file fails schema validation    |
| 502    | AWS Bedrock API error                      |

---

### `GET /api/v1/agents`
List all Bedrock agents (paginated).

**Query parameters**

| Parameter    | Type    | Default | Description                             |
|--------------|---------|---------|-----------------------------------------|
| `max_results`| integer | 50      | Page size (1–100)                       |
| `next_token` | string  |         | Pagination cursor from previous response|

**Response 200**
```json
{
  "items": [
    {
      "agentId": "ABCDEF1234",
      "agentName": "senior-software-architect",
      "agentStatus": "PREPARED"
    }
  ],
  "total": 1,
  "nextToken": null
}
```

---

### `GET /api/v1/agents/definitions`
List all YAML definition files available in the `agent-definition/` directory.

**Response 200**
```json
["senior-software-architect", "another-agent"]
```

---

### `GET /api/v1/agents/{agent_id}`
Get details of a specific Bedrock agent.

**Path parameters**

| Parameter  | Description              |
|------------|--------------------------|
| `agent_id` | Bedrock agent identifier |

**Response 200** – same shape as create response.

**Error responses**

| Status | Condition         |
|--------|-------------------|
| 404    | Agent not found   |
| 502    | Bedrock API error |

---

### `PUT /api/v1/agents/{agent_id}`
Update an existing agent from a YAML definition file.

**Path parameters**

| Parameter  | Description              |
|------------|--------------------------|
| `agent_id` | Bedrock agent identifier |

**Request body**
```json
{
  "definition_file": "senior-software-architect",
  "prepare": true
}
```

**Response 200** – updated agent, same shape as create response.

---

### `DELETE /api/v1/agents/{agent_id}`
Permanently delete a Bedrock agent.

**Path parameters**

| Parameter  | Description              |
|------------|--------------------------|
| `agent_id` | Bedrock agent identifier |

**Response 204** – No content.

**Error responses**

| Status | Condition         |
|--------|-------------------|
| 404    | Agent not found   |
| 502    | Bedrock API error |

---

## Error Response Format

All errors return a consistent body:

```json
{
  "error": "Human-readable error message.",
  "details": [
    { "field": "definition_file", "message": "Field required" }
  ],
  "request_id": null
}
```

