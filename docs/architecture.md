# Architecture

## Overview

Agent-Ops API follows a layered architecture to ensure separation of concerns,
testability, and clean extensibility.

```
┌─────────────────────────────────────────────────┐
│                  HTTP Clients                   │
└────────────────────────┬────────────────────────┘
                         │
┌────────────────────────▼────────────────────────┐
│           FastAPI  (Transport Layer)            │
│   app/api/v1/endpoints/agents.py                │
│   app/middleware/  (logging, error handling)    │
└────────────────────────┬────────────────────────┘
                         │
┌────────────────────────▼────────────────────────┐
│           Service Layer  (Business Logic)       │
│   app/services/bedrock_agent_service.py         │
└──────────────┬──────────────────────────────────┘
               │                   │
┌──────────────▼──────┐  ┌─────────▼───────────────┐
│ AgentDefinition     │  │ BedrockRepository        │
│ Repository          │  │ (boto3 bedrock-agent)    │
│ (YAML → Pydantic)   │  │                          │
└─────────────────────┘  └──────────────────────────┘
               │                   │
┌──────────────▼──────┐  ┌─────────▼───────────────┐
│ agent-definition/   │  │ Amazon Bedrock API       │
│ *.agent.yaml        │  │ (AWS)                    │
└─────────────────────┘  └──────────────────────────┘
```

---

## Layer Responsibilities

### Transport (API) Layer
- `app/api/v1/endpoints/agents.py` – FastAPI route handlers; thin, no business logic
- `app/middleware/error_handler.py` – Converts domain exceptions → structured JSON HTTP responses
- `app/middleware/request_logging.py` – Request/response logging + `X-Request-ID` header injection
- `app/api/dependencies.py` – FastAPI `Depends` providers for DI

### Service Layer
- `app/services/bedrock_agent_service.py` – Orchestrates repositories; contains all business rules
- `app/services/protocols.py` – `AgentServiceProtocol` interface; enables test substitution

### Repository Layer
- `app/repositories/agent_definition_repository.py` – Reads + validates YAML files from disk
- `app/repositories/bedrock_repository.py` – Wraps boto3 calls; translates `ClientError` → domain exceptions

### Schema / Model Layer
- `app/schemas/agent_definition.py` – Pydantic models matching the YAML file structure
- `app/models/agent.py` – API request/response models
- `app/models/common.py` – Shared models (`ErrorResponse`, `PaginatedResponse`, `HealthResponse`)

### Core
- `app/core/config.py` – `Settings(BaseSettings)` with env-file auto-selection
- `app/core/logging.py` – JSON (prod) or human-readable (local/dev) structured logging
- `app/core/exceptions.py` – Domain exception hierarchy

---

## Design Decisions

### YAML as Agent Contract
Agent definitions are stored as versioned YAML files in `agent-definition/`.
This gives developers a Git-friendly, diff-able, reviewable record of every agent change.

### Protocol / Dependency Inversion
`AgentServiceProtocol` decouples the API layer from the concrete `BedrockAgentService`.
This makes unit testing easy — mock the protocol, no AWS calls needed.

### Environment-Based Configuration
`APP_ENV` selects the `.env.{env}` file automatically. Sensitive values are never hardcoded.
Production should inject secrets via AWS SSM Parameter Store or Secrets Manager.

### Structured Logging
JSON logging in prod enables seamless CloudWatch Logs Insights queries.
Human-readable format in local/dev reduces developer friction.

---

## Request Flow: Create Agent

```
POST /api/v1/agents
  body: { "definition_file": "senior-software-architect", "prepare": true }

  1. agents.py (router)
       └─ calls service.create_agent_from_definition(...)
  2. BedrockAgentService
       ├─ AgentDefinitionRepository.get("senior-software-architect")
       │     └─ reads & validates agent-definition/senior-software-architect.agent.yaml
       ├─ BedrockRepository.create_agent(agentName=..., foundationModel=..., instruction=..., ...)
       │     └─ boto3 → AWS Bedrock CreateAgent API
       └─ BedrockRepository.prepare_agent(agentId)
             └─ boto3 → AWS Bedrock PrepareAgent API
  3. Returns AgentResponse (201 Created)
```

