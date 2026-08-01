# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0-rc.1] — 2026-08-01

### Added
- **Prompt injection sanitizer** (`src/api/security/sanitizer.py`) — strips role-override, instruction-leak, and jailbreak patterns from user-supplied text before it reaches the LLM. Applied to task submission, agent execution, agent streaming, and WebSocket endpoints.
- **`/api/v1/system/auth-status` endpoint** — reports whether authentication is enforced and whether JWT secret is stable. Suitable for use in monitoring and operator health checks.
- **`SECURITY.md`** — responsible disclosure policy and supported versions table.
- **Per-identity rate limiting** — rate-limit buckets are now keyed by the authenticated JWT subject or API key ID instead of the raw `X-API-Key` header value. Falls back to IP for unauthenticated requests.

### Changed
- **CORS default** changed from `*` (allow all) to `http://localhost:8000`. Set `CORS_ORIGINS` explicitly for any production deployment.
- **JWT secret handling** — a startup warning is now emitted when `JWT_SECRET` is not set via environment variable, making the ephemeral (per-restart) key state explicit and visible in logs.
- **Auth bypass warning** — a startup warning is now emitted when no API keys are configured (`API_KEYS` / `API_KEY` unset), making the open-access state explicit in logs.
- **CORS wildcard warning** — a startup warning is now emitted when `CORS_ORIGINS=*` is used outside of `LOG_LEVEL=DEBUG` mode.
- **Version bumped** to `1.0.0-rc.1` in `pyproject.toml`, FastAPI app metadata, and `/api/v1/system/info` response.
- **`auth_identity`** is now stored in `request.state` by the auth middleware (alongside `auth_role`), enabling downstream middleware to make per-user decisions.
- **`.env.example`** updated to document `JWT_SECRET` as required in production and add CORS guidance.

---

## [0.1.0] — Initial release

### Added
- FastAPI application with 88 REST endpoints across 16 route groups: `health`, `agents`, `tasks` (SSE), `crew`, `ide`, `cde`, `platform`, `webhooks`, `sessions`, `eval`, `auth`, `system`, `scheduler`, `usage`, `memory`.
- 12 AI agent types: `PLANNING`, `RESEARCH`, `ANALYSIS`, `WRITING`, `REVIEW`, `CODING`, `SUMMARIZATION`, `IDE`, `CDE`, `KALLY`, `EXECUTION`.
- `BaseAgent` with retry logic and circuit breaker (opens for 60 s after 5 consecutive failures).
- Three-layer memory architecture: short-term (in-process), long-term/episodic (ChromaDB), and hybrid (`HybridMemory` / `MemoryManager`).
- Async task queue backed by `asyncio.Queue` or Redis, with SQLite persistence.
- `TaskScheduler` for periodic/scheduled jobs.
- JWT authentication (`JWTManager`) and API key management (`KeyStore`).
- Role-aware token-bucket rate limiting middleware (`admin` bypass, `read` at 50% capacity).
- Prometheus metrics at `/metrics` and OpenTelemetry tracing support.
- CrewAI multi-agent orchestration (`src/crew/`).
- LangGraph integration within agent pipelines.
- Docker Compose, Podman, Helm chart, and Kubernetes raw manifests for deployment.
- 355 unit tests.
