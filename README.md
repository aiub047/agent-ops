# Agent-Ops API

RESTful API for creating and managing **Amazon Bedrock Agents** driven by versioned YAML definition files.

---

## Quick Start

```bash
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell

# 2. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt   # for testing + linting

# 3. Configure local environment (copy template and fill in your values)
copy .env.example .env.local

# 4. Run the API
$env:APP_ENV="local"; python main.py
# or
$env:APP_ENV="local"; uvicorn app.main:app --reload
```

API docs available at **http://localhost:8000/docs** (local/dev only).

---

## Project Structure

```
agent-ops/
├── app/
│   ├── api/v1/endpoints/agents.py   ← CRUD HTTP routes
│   ├── core/                        ← config, logging, exceptions
│   ├── middleware/                  ← error handling, request logging
│   ├── models/                      ← API request/response Pydantic models
│   ├── repositories/                ← YAML loader + boto3 Bedrock client
│   ├── schemas/                     ← Agent definition YAML models
│   ├── services/                    ← Business logic
│   └── main.py                      ← FastAPI app factory
├── agent-definition/                ← Agent YAML files (versioned in Git)
├── tests/
│   ├── unit/
│   └── integration/
├── .env.example
├── requirements.txt
└── main.py                          ← Uvicorn entry point
```

---

## Agent Definition Files

Place YAML files in the `agent-definition/` directory:

```
agent-definition/
└── senior-software-architect.agent.yaml
```

Use the filename (without extension) as `definition_file` in API requests.

---

## API Endpoints

| Method   | Path                          | Description                         |
|----------|-------------------------------|-------------------------------------|
| `POST`   | `/api/v1/agents`              | Create agent from YAML definition   |
| `GET`    | `/api/v1/agents`              | List all Bedrock agents             |
| `GET`    | `/api/v1/agents/definitions`  | List available definition files     |
| `GET`    | `/api/v1/agents/{agent_id}`   | Get a specific agent                |
| `PUT`    | `/api/v1/agents/{agent_id}`   | Update agent from YAML definition   |
| `DELETE` | `/api/v1/agents/{agent_id}`   | Delete agent                        |
| `GET`    | `/health`                     | Health / liveness check             |

---

## Environment Variables

| Variable                 | Description                                    | Default            |
|--------------------------|------------------------------------------------|--------------------|
| `APP_ENV`                | Environment: `local`, `dev`, `prod`            | `local`            |
| `AWS_REGION`             | AWS region                                     | `us-east-1`        |
| `AWS_PROFILE`            | AWS named profile (local/dev)                  | —                  |
| `BEDROCK_AGENT_ROLE_ARN` | IAM role ARN for Bedrock agents                | —                  |
| `AGENT_DEFINITION_DIR`   | Path to agent definition directory             | `agent-definition` |
| `LOG_LEVEL`              | Log level (`DEBUG`, `INFO`, `WARNING`, ...)    | `INFO`             |

---

## Running Tests

```bash
pytest                        # all tests
pytest tests/unit/            # unit tests only
pytest tests/integration/     # integration tests only
```

---

## Docker

```bash
docker build -t agent-ops-api .
docker-compose up
```

