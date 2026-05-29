# AGI System — CLAUDE.md

Production FastAPI AGI system. Python 3.11, 88 REST endpoints, 15 packages in `src/`.

## Dev Commands

```bash
cp .env.example .env && make install-dev   # first-time setup
make dev          # uvicorn --reload on :8000
make test-unit    # pytest tests/unit/ (355 tests)
make test-cov     # coverage → htmlcov/
make lint         # ruff check src/ tests/
make format       # ruff format
make typecheck    # mypy src/
make health       # curl /api/v1/health (server must be running)
```

## Key Files

| Concern | Path |
|---|---|
| App factory + lifespan | `src/api/main.py` — `create_app()`, `lifespan()` |
| Config (pydantic-settings) | `src/config.py` — `get_settings()`, reads `.env` |
| Agent base + AgentType enum | `src/agents/base_agent.py` |
| Agent factory + registration | `src/agents/agent_factory.py`, `_register_default_agents()` in `main.py` |
| Auth middleware | `src/api/middleware/auth.py` |
| Rate limiting | `src/api/middleware/rate_limit.py` |
| Metrics / tracing | `src/api/middleware/metrics.py`, `tracing.py` |
| Task queue + workers | `src/tasks/queue.py`, `persistence.py` (SQLite: `tasks.db`) |
| Task scheduler | `src/tasks/scheduler.py` — `TaskScheduler` |
| Memory (unified API) | `src/memory/memory_manager.py` |
| Hybrid memory | `src/memory/hybrid_memory.py` |
| Vector store (ChromaDB) | `src/memory/vector_store.py` |
| Session management | `src/sessions/session_manager.py` (SQLite: `sessions.db`) |
| Webhooks | `src/webhooks/dispatcher.py` — retry-backed dispatch |
| JWT auth | `src/auth/jwt_manager.py` |
| API key store | `src/auth/key_store.py` — `KeyStore` |
| LLM provider | `src/llm/provider.py` — `LLMProvider`, `create_llm()` |

## Agents

Defined by `AgentType` enum in `src/agents/base_agent.py`. One file per agent in `src/agents/`; exceptions: `src/ide/ide_agent.py`, `src/cde/cde_agent.py`, `src/execution/execution_agent.py`.

```
PLANNING  RESEARCH  ANALYSIS  WRITING  REVIEW
CODING    SUMMARIZATION  IDE   CDE     KALLY  EXECUTION
```

`BaseAgent` provides: `run_with_retry()` (retry + circuit breaker — opens for 60 s after `AgentConfig.circuit_break_threshold` consecutive failures, default 5), `_invoke_llm()`, `_stream_llm()`, `recall_similar_tasks()`, `set_tool_registry()`.

## REST Routers (88 endpoints)

All registered via `app.include_router()` in `create_app()`. OpenAPI tags: `_OPENAPI_TAGS` in `main.py`. Prometheus metrics at `/metrics`.

`health` `agents` `tasks` (SSE stream) `crew` `ide` `cde` `platform` `webhooks` `sessions` `eval` `auth` `system` `scheduler` `usage` `memory` — each in `src/api/endpoints/<name>.py`.

## Auth

- **Dev bypass**: `API_KEYS` unset or `[]` — no auth enforced.
- **API key**: `X-API-Key: sk-...` — keys stored in `KeyStore`.
- **JWT**: `Authorization: Bearer <token>` — config: `JWT_SECRET`, `JWT_EXPIRY_SECONDS` (default 3600).
- Keys carry roles consumed by `RateLimitMiddleware`.

## Environment Variables

| Var | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `openai` | `openai` or `anthropic` |
| `OPENAI_API_KEY` | — | Omit for mock mode |
| `ANTHROPIC_API_KEY` | — | Omit for mock mode |
| `JWT_SECRET` | random | Set stable value in prod |
| `JWT_EXPIRY_SECONDS` | `3600` | |
| `API_KEYS` | — | JSON: `[{"key":"sk-...","name":"...","role":"..."}]` |
| `REDIS_URL` | `""` | Falls back to `asyncio.Queue` |
| `TASK_DB_PATH` | `tasks.db` | SQLite task persistence |
| `RATE_LIMIT_REQUESTS` | `100` | Requests per window |
| `RATE_LIMIT_WINDOW` | `60.0` | Window in seconds |
| `CORS_ORIGINS` | `*` | Comma-separated |
| `LOG_FORMAT` | `json` | `json` or `text` |
| `LOG_LEVEL` | `INFO` | |
| `OTEL_SERVICE_NAME` | `agi-system` | OpenTelemetry |

## Memory & Orchestration

Memory layers: short-term (in-process dict on `AgentMemory`), long-term/episodic (ChromaDB `VectorStore`), hybrid (`HybridMemory`). Unified API: `MemoryManager`.

Orchestration: CrewAI (`src/crew/`), LangGraph (within agent pipelines), `ExecutionAgent` (`src/execution/execution_engine.py`).

## Testing

- `pytest.ini`: `asyncio_mode = auto`, `testpaths = tests`.
- Canonical pattern: `TestClient` + mock `app.state` — see `tests/unit/test_memory_api.py`.
- Never use real LLM keys in unit tests; mock `_invoke_llm` or use the mock provider.
- Integration tests require a running server or fixtures (`tests/integration/`).

## How to Add Things

**New agent:**
1. Create `src/agents/<name>_agent.py` subclassing `BaseAgent`.
2. Add enum value to `AgentType` in `src/agents/base_agent.py`.
3. Register in `_register_default_agents()` in `src/api/main.py`.

**New endpoint:**
1. Create `src/api/endpoints/<name>.py` with `router = APIRouter(...)`.
2. `app.include_router(router, ...)` in `create_app()` in `src/api/main.py`.
3. Append an OpenAPI tag object to `_OPENAPI_TAGS` in the same file.

## Docker / Kubernetes

```bash
make docker-build    # builds infrastructure/docker/Dockerfile.agents
make docker-up       # docker compose up -d
make podman-build    # Containerfile at repo root
make podman-up       # podman-compose -f podman-compose.yml up -d
make helm-install    # Helm chart: infrastructure/helm/agi-system/
make rancher-up      # podman-build + helm-install
make k8s-apply       # raw manifests: infrastructure/kubernetes/
```
