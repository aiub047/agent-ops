# Agent Definition Schema

Agent definition files live in the `agent-definition/` directory and follow the naming convention:

```
<agent-name>.agent.yaml
```

---

## Top-Level Structure

```yaml
apiVersion: agentops/v1       # required
kind: BedrockAgent            # required, must be "BedrockAgent"
metadata:                     # required
  ...
spec:                         # required
  ...
```

---

## `metadata`

| Field         | Type              | Required | Description                              |
|---------------|-------------------|----------|------------------------------------------|
| `name`        | string            | ✅       | Unique agent name, used as the filename  |
| `displayName` | string            |          | Human-friendly display name             |
| `version`     | string            |          | Semantic version of this definition (default: `1.0.0`) |
| `owner`       | string            |          | Owning team or individual               |
| `tags`        | map[string,string]|          | Arbitrary key-value tags                |

---

## `spec`

| Field             | Type             | Required | Description                                   |
|-------------------|------------------|----------|-----------------------------------------------|
| `description`     | string           |          | Short description of the agent's purpose      |
| `model`           | ModelConfig      | ✅       | Foundation model configuration                |
| `instruction`     | string           | ✅       | System prompt / instruction for the agent     |
| `goals`           | list[string]     |          | High-level agent goals                        |
| `constraints`     | list[string]     |          | Constraints the agent must follow             |
| `responseContract`| ResponseContract |          | Expected output structure                     |
| `session`         | SessionConfig    |          | Session TTL and memory settings               |
| `guardrails`      | Guardrails       |          | Bedrock guardrail configuration               |
| `knowledgeBases`  | list[KnowledgeBase]|        | Attached knowledge bases                      |
| `actionGroups`    | list[ActionGroup]|          | Action groups (Lambda-backed tools)           |
| `aliases`         | list[AgentAlias] |          | Agent aliases for versioned deployments       |
| `observability`   | Observability    |          | Logging and tracing settings                  |
| `deployment`      | DeploymentConfig |          | Target AWS region and Terraform workspace     |

### `model`

| Field        | Type    | Default | Description                                           |
|--------------|---------|---------|-------------------------------------------------------|
| `id`         | string  | —       | Bedrock model ID, e.g. `anthropic.claude-3-5-sonnet-20241022-v2:0` |
| `temperature`| float   | `0.2`   | Sampling temperature (0.0–1.0)                        |
| `topP`       | float   | `0.9`   | Top-p nucleus sampling (0.0–1.0)                      |
| `maxTokens`  | integer | `1024`  | Maximum tokens in response                            |

### `session`

| Field              | Type    | Default | Description                          |
|--------------------|---------|---------|--------------------------------------|
| `idleTtlSeconds`   | integer | `1800`  | Session idle TTL in seconds (min 60) |
| `memoryEnabled`    | boolean | `false` | Enable cross-session memory          |

### `guardrails`

| Field              | Type    | Default | Description                              |
|--------------------|---------|---------|------------------------------------------|
| `enabled`          | boolean | `true`  | Whether guardrails are active            |
| `guardrailId`      | string  |         | Bedrock guardrail identifier             |
| `guardrailVersion` | string  |         | Guardrail version (default: `DRAFT`)     |

### `actionGroups[]`

| Field         | Type          | Required | Description                           |
|---------------|---------------|----------|---------------------------------------|
| `name`        | string        | ✅       | Action group name                     |
| `description` | string        |          | Description of the action group       |
| `executor`    | LambdaExecutor| ✅       | Lambda function that executes actions |
| `apiSchema`   | ApiSchema     |          | OpenAPI spec for the action group     |
| `enabled`     | boolean       | `true`   | Whether this group is active          |

### `knowledgeBases[]`

| Field         | Type            | Required | Description                          |
|---------------|-----------------|----------|--------------------------------------|
| `id`          | string          | ✅       | Bedrock knowledge base identifier    |
| `description` | string          |          | Description of the knowledge base    |
| `retrieval`   | RetrievalConfig |          | Retrieval parameters                 |

---

## Full Example

See [`agent-definition/senior-software-architect.agent.yaml`](../agent-definition/senior-software-architect.agent.yaml).

