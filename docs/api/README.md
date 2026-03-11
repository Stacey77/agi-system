# API Reference

## Authentication

All endpoints (except `/health*`) require the `X-API-Key` header:

```
X-API-Key: your-api-key
```

## Endpoints

### Health

#### `GET /health`
Basic liveness check.

**Response:**
```json
{"status": "healthy"}
```

#### `GET /health/detailed`
Component-level health check.

**Response:**
```json
{
  "status": "healthy",
  "components": {
    "execution_engine": "healthy",
    "memory": "healthy",
    "tool_registry": "healthy"
  }
}
```

---

### Agents

#### `GET /api/v1/agents/`
List all registered agents.

**Response:**
```json
[
  {"name": "planning_agent", "type": "planning", "status": "ready"},
  {"name": "research_agent", "type": "research", "status": "ready"}
]
```

#### `POST /api/v1/agents/{agent_name}/execute`
Execute a task with a specific agent.

**Request:**
```json
{"task": "Research latest AI papers", "parameters": {}}
```

**Response:**
```json
{"agent": "research_agent", "result": {"status": "completed", "sources": [...]}}
```

#### `GET /api/v1/agents/{agent_name}/status`
Get agent status and memory usage.

---

### Tasks

#### `POST /api/v1/tasks/`
Submit a complex task to the AGI system.

**Request:**
```json
{"objective": "Research and summarise AI trends", "parameters": {}}
```

**Response:**
```json
{"task_id": "uuid", "status": "completed"}
```

#### `GET /api/v1/tasks/{task_id}`
Get task status and result.

#### `DELETE /api/v1/tasks/{task_id}`
Cancel a running task.
