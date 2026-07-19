# AI Foundry — Platform Overview

> **Pillar 1 of the Three-Way Empire**: Rapid development and deployment of AI applications.

AI Foundry is the application development accelerator within the AGI System platform. It provides the scaffolding, templates, integrations, and developer experience needed to go from AI idea to production deployment in days, not months. By abstracting infrastructure complexity and standardising LLM integration patterns, AI Foundry lets teams focus entirely on application logic and business value.

---

## Why AI Foundry?

| Challenge | AI Foundry Solution |
|---|---|
| LLM provider fragmentation | Unified `LLMProvider` abstraction (OpenAI, Anthropic, mock) |
| Boilerplate for agents, tools, memory | Pre-built `BaseAgent`, `ToolRegistry`, `MemoryManager` |
| Inconsistent auth and rate limiting | Shared JWT + API-key middleware, per-key rate limiter |
| Slow iteration cycles | Hot-reload dev server (`make dev`), deterministic fallbacks for offline testing |
| Observability gaps | Built-in metrics middleware, tracing, structured logging |

---

## Core Capabilities

### 1. Application Templates
AI Foundry ships with battle-tested application archetypes:

- **Chatbot / Conversational App** — multi-turn sessions, streaming SSE responses, per-session memory
- **Autonomous Research Pipeline** — planning → research → analysis → writing crew
- **Document Intelligence App** — ingest, parse, chunk, embed, and query documents
- **Code Generation Service** — language-aware `CodingAgent` with LLM-powered generate/review/explain

### 2. Agent Development Kit (ADK)
Every agent inherits from `BaseAgent` and gets for free:

- Circuit-breaker pattern (configurable `circuit_break_threshold`)
- Per-agent memory ring-buffer (`memory_size` records)
- Task result recording and retrieval
- Streaming via `stream_task()` async iterator
- Tool injection via `ToolRegistry`
- Token usage tracking via `TokenTracker`

```python
from src.agents.base_agent import AgentConfig, AgentType, BaseAgent

config = AgentConfig(
    name="my_agent",
    agent_type=AgentType.CODING,
    description="Custom code generator",
    capabilities=["code_generation"],
    tools=["web_search"],
    temperature=0.4,
)
agent = AgentFactory().create_agent(config)
result = await agent.process_task({"task": "Write a binary search in Python"})
```

### 3. Tool Ecosystem
Built-in tools are registered via `ToolRegistry` at startup:

| Tool | Class | Category |
|---|---|---|
| Web Search | `WebSearchTool` | information_retrieval |
| Calculator | `CalculatorTool` | computation |
| Document Parser | `DocumentParserTool` | information_retrieval |
| Database | `DatabaseTool` | data |

Custom tools implement `BaseTool` and declare `ToolMetadata` — then register with one call:
```python
tool_registry.register_tool(MyCustomTool())
```

### 4. LLM Integration Layer
`LLMProvider` abstracts provider differences:

```python
from src.llm.provider import create_llm

llm = create_llm(
    provider="openai",          # or "anthropic" | "mock"
    model="gpt-4o",
    temperature=0.7,
    max_tokens=4096,
)
```

The `mock` provider enables fully deterministic offline development — no API keys required for local iteration.

### 5. Developer Portal
The built-in `DeveloperPortal` provides service discovery for every API surface:

- Browse registered services by tier (internal / external)
- View per-service health, version, and docs URL
- Register new services at runtime: `POST /api/v1/platform/portal/services`

---

## Application Lifecycle

```
 Idea ──▶ Scaffold ──▶ Configure ──▶ Develop ──▶ Test ──▶ Deploy ──▶ Observe
          (ADK)        (.env)        (agents)    (pytest) (Docker) (metrics)
```

1. **Scaffold**: Fork the repo or use a template branch; `make install-dev` sets up the venv.
2. **Configure**: Copy `.env.example` → `.env`; set LLM provider keys and feature flags.
3. **Develop**: Implement agent logic inside `BaseAgent.process_task()`; add custom tools.
4. **Test**: `make test-unit` (355+ tests) with `pytest`; offline mocks keep CI fast and free.
5. **Deploy**: `docker-compose up -d` for local; Kubernetes manifests for production.
6. **Observe**: Metrics middleware exposes Prometheus-compatible counters; `/health/detailed` gives component status.

---

## Integration with AI Factory and Agentic Studio

AI Foundry sits at the **application layer**:

```
┌──────────────────────────────────────────────────────────┐
│  Agentic Studio  (IDE, CDE, AI coding assistant tooling) │
├──────────────────────────────────────────────────────────┤
│  AI Foundry       (application development & deployment) │  ◀ this doc
├──────────────────────────────────────────────────────────┤
│  AI Factory       (scalable infrastructure layer)        │
└──────────────────────────────────────────────────────────┘
```

Applications built with AI Foundry run **on** the infrastructure managed by AI Factory, and are **developed with** the tools provided by Agentic Studio.

---

## Key Metrics and Outcomes

| Metric | Target |
|---|---|
| Time from idea to first working endpoint | < 1 day |
| Agent creation boilerplate | < 20 lines of config |
| Offline test coverage (no LLM calls) | 100% of unit tests |
| Supported LLM providers | OpenAI, Anthropic, extensible |
| API surface | 88 REST endpoints |

---

## Further Reading

- [API Reference](../api/README.md)
- [User Guide](../user-guides/README.md)
- [Deployment Guide](../deployment/README.md)
- [AI Factory — Infrastructure Guide](../ai-factory/infrastructure-guide.md)
- [Agentic Studio — Market Landscape](../agentic-studio/market-landscape.md)
