# AI Factory — Infrastructure Guide

> **Pillar 2 of the Three-Way Empire**: Scalable and efficient AI infrastructure.

AI Factory is the infrastructure backbone of the AGI System platform. Where AI Foundry accelerates application development, AI Factory ensures those applications have the compute, data, networking, and operational scaffolding to run reliably at any scale — from a single developer laptop to a multi-region Kubernetes cluster serving millions of requests.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                       AI Factory                             │
│                                                              │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐    │
│  │  Compute &    │  │  Data &       │  │  Operations & │    │
│  │  Orchestration│  │  Memory Layer │  │  Observability│    │
│  │               │  │               │  │               │    │
│  │ • Kubernetes  │  │ • ChromaDB    │  │ • Prometheus  │    │
│  │ • Docker      │  │ • PostgreSQL  │  │ • Structured  │    │
│  │ • Terraform   │  │ • Redis       │  │   Logging     │    │
│  │ • AWS VPC     │  │ • S3          │  │ • Health APIs │    │
│  └───────────────┘  └───────────────┘  └───────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

---

## Infrastructure Layers

### Compute & Orchestration

#### Kubernetes (Production)
Production workloads run on Kubernetes with namespace isolation:

```bash
# Deploy to Kubernetes
kubectl apply -f infrastructure/kubernetes/namespace.yaml

kubectl create secret generic agi-secrets \
  --namespace=agi-system \
  --from-literal=openai-api-key=$OPENAI_API_KEY \
  --from-literal=anthropic-api-key=$ANTHROPIC_API_KEY

kubectl apply -f infrastructure/kubernetes/deployment.yaml
kubectl apply -f infrastructure/kubernetes/service.yaml

# Monitor rollout
kubectl rollout status deployment/agi-system -n agi-system
```

Key configuration in `infrastructure/kubernetes/deployment.yaml`:
- **Resource limits**: CPU and memory bounds per pod
- **Readiness/liveness probes**: `/health` and `/health/detailed` endpoints
- **Replica autoscaling**: HPA based on CPU utilisation
- **Rolling updates**: zero-downtime deployments with `maxSurge: 1`

#### Docker Compose (Local / Staging)
`docker-compose.yml` wires together all services for local development:

```bash
cp .env.example .env     # fill in API keys
docker-compose up -d
```

| Service | Port | Purpose |
|---|---|---|
| `agents-service` | 8000 | FastAPI application |
| `api-gateway` | 8080 | Nginx reverse proxy |
| `vector-db` | 8001 | ChromaDB vector store |
| `redis` | 6379 | Cache and pub/sub |

#### Container Image
The `Containerfile` produces a minimal `python:3.11-slim` image:
- Multi-layer cache: `requirements.txt` before source
- Non-root user execution
- `HEALTHCHECK` built in
- Single `CMD`: `uvicorn src.api.main:app --host 0.0.0.0 --port 8000`

```bash
# Build with Podman or Docker
podman build -t agi-system .
podman run -p 8000:8000 --env-file .env agi-system
```

#### Terraform (AWS)
`infrastructure/terraform/main.tf` provisions a full AWS stack:

| Resource | Type | Notes |
|---|---|---|
| VPC | `aws_vpc` | `10.0.0.0/16`, DNS enabled |
| RDS PostgreSQL | `db.t3.medium` | Multi-AZ in production |
| S3 | `aws_s3_bucket` | Versioned, environment-scoped |
| Secrets Manager | (referenced) | LLM API keys, DB password |

```bash
cd infrastructure/terraform
terraform init
terraform plan  -var="db_username=admin" -var="db_password=$DB_PASS"
terraform apply
```

---

### Data & Memory Layer

AI Factory manages four categories of persistent state:

#### Vector Memory (ChromaDB)
Long-term semantic memory for agents is stored in ChromaDB and surfaced via `MemoryManager`:

```
GET  /api/v1/memory/search?q=<query>&agent=<name>&limit=10
POST /api/v1/memory/store
```

ChromaDB runs as a sidecar container (`vector-db`) with a persistent volume, ensuring embeddings survive restarts.

#### Relational Storage (PostgreSQL / SQLite)
- **Task persistence**: `tasks.db` (SQLite) stores async task states locally; swap to PostgreSQL for multi-instance deployments by setting `DATABASE_URL`.
- **Eval results**: stored and queryable via `GET /api/v1/eval/results`.
- **Session history**: per-turn message logs retained in the sessions store.

#### Cache (Redis)
Redis provides:
- Rate-limit counters (`RateLimitMiddleware`)
- Session store for multi-turn conversations
- Pub/sub backbone for future event-driven agent triggers

#### Object Storage (S3)
S3 is provisioned by Terraform for:
- Document ingestion (source files for `DocumentParserTool`)
- Evaluation dataset snapshots
- Export artefacts

---

### Operations & Observability

#### Health API
Two-level health check surface:

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness — `{"status": "healthy"}` |
| `GET /health/detailed` | Component readiness: task_queue, llm, agent_factory, auth |

Kubernetes liveness and readiness probes point to these endpoints.

#### Metrics
`MetricsMiddleware` instruments every HTTP request:
- Request count by route, method, status code
- Latency histograms (P50, P95, P99)
- Token usage per agent (via `TokenTracker`)
- Active task queue depth

Metrics are exposed in Prometheus text format at `GET /metrics`.

#### Structured Logging
All services emit JSON-structured log lines with:
- `timestamp`, `level`, `logger`, `message`
- `agent_name`, `task_id`, `request_id` (where applicable)
- Configurable log format via `LOG_FORMAT=json|text` env var

#### System Info API
`GET /api/v1/system/info` returns non-sensitive runtime data for dashboards:
```json
{
  "version": "0.1.0",
  "python": "3.11.x",
  "llm_provider": "openai",
  "uptime_seconds": 3600,
  "agents": ["planning_agent", "research_agent", "..."],
  "tools": ["web_search", "calculator", "..."]
}
```

---

## CI/CD Pipeline

`.github/workflows/deploy.yml` automates the full lifecycle:

```
Push / PR  ──▶  Lint (ruff) + Typecheck (mypy)
                     │
                 Unit Tests (pytest, 355+)
                     │
             [merge to main only]
                     │
            Docker Build + Push (GHCR)
                     │
          Kubernetes Rolling Deploy
                     │
           Rollout Verification (kubectl)
```

Environment variables for CI are stored as GitHub Actions secrets and injected at deploy time — no secrets in code or image layers.

---

## Scaling Characteristics

| Dimension | Approach |
|---|---|
| Horizontal scale | Stateless FastAPI pods behind k8s HPA |
| LLM throughput | Per-API-key rate limiting; provider-level token budgets |
| Memory scale | ChromaDB persistent volume; swap to managed vector DB (Pinecone, Weaviate) |
| Storage scale | S3-backed document store; RDS read replicas for PostgreSQL |
| Task throughput | `TaskQueue` with configurable worker pool; SQLite → PostgreSQL for high concurrency |

---

## Security Controls

| Control | Implementation |
|---|---|
| Authentication | JWT bearer tokens + API key header (`X-API-Key`) |
| Authorisation | Admin-only routes for key CRUD and runtime agent creation |
| Secrets management | Environment variables; Kubernetes secrets; AWS Secrets Manager via Terraform |
| Network isolation | VPC + security groups (Terraform); namespace isolation (Kubernetes) |
| Rate limiting | `RateLimitMiddleware` — configurable per key per minute |
| Container security | Non-root user; read-only root FS; minimal base image |
| TLS | Nginx/Ingress terminates TLS; internal traffic stays in-cluster |

---

## Further Reading

- [Deployment Guide](../deployment/README.md)
- [AI Foundry — Platform Overview](../ai-foundry/platform-overview.md)
- [Agentic Studio — Market Landscape](../agentic-studio/market-landscape.md)
- [AIPG — AI Proving Ground](../aipg/proving-ground.md)
