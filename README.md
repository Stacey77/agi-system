# AGI System

A production-ready AGI-type system for building smart chatbots, writing assistants, and automated research tools using **LangChain** and **CrewAI** frameworks with a dedicated **Execution Agent**.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                      API Gateway                        │
│                    (FastAPI, port 8080)                  │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                   Execution Agent                        │
│              (Priority Score: 9.7/10)                    │
│         Central coordinator for all execution            │
└─────┬────────────┬────────────┬────────────┬────────────┘
      │            │            │            │
   Planning    Research     Analysis     Writing
   Agent       Agent        Agent        Agent
      │            │            │            │
└─────▼────────────▼────────────▼────────────▼────────────┐
│                   Tool Registry                          │
│    Web Search | Calculator | Doc Parser | Database       │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│              Hybrid Memory System                        │
│    LangChain Vector Store + CrewAI Agent Contexts        │
└─────────────────────────────────────────────────────────┘
```

## Dual-Framework Strategy

- **LangChain**: Foundation layer providing tools, memory chains, and LLM integrations
- **CrewAI**: Multi-agent coordination, task delegation, and crew orchestration

## Agents

| Agent | Description | Priority |
|-------|-------------|----------|
| **Execution Agent** | Central coordinator, validates and executes all tasks | **9.7** |
| Planning Agent | Task decomposition and dependency analysis | 8.5 |
| Research Agent | Multi-source information gathering | 8.0 |
| Analysis Agent | Data processing and insight extraction | 7.5 |
| Writing Agent | Content generation with outline→draft→edit pipeline | 7.5 |
| Review Agent | Quality assurance and fact-checking | 7.0 |

## Quick Start

```bash
# Clone the repository
git clone https://github.com/Stacey77/agi-system.git
cd agi-system

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run the application
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

## Docker Deployment

```bash
docker-compose up -d
```

Services:
- `agents-service` → http://localhost:8000
- `api-gateway` → http://localhost:8080
- `vector-db` (ChromaDB) → http://localhost:8001
- `redis` → localhost:6379

## Kubernetes Deployment

```bash
kubectl apply -f infrastructure/kubernetes/namespace.yaml
kubectl apply -f infrastructure/kubernetes/deployment.yaml
kubectl apply -f infrastructure/kubernetes/service.yaml
```

## API Usage

### Submit a Task

```bash
curl -X POST http://localhost:8000/api/v1/tasks/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"objective": "Research and summarize recent AI developments"}'
```

### Execute with a Specific Agent

```bash
curl -X POST http://localhost:8000/api/v1/agents/research_agent/execute \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"task": "Find recent papers on transformer architectures"}'
```

### Health Check

```bash
curl http://localhost:8000/health
```

## Project Structure

```
agi-system/
├── src/
│   ├── agents/          # Agent implementations
│   ├── execution/       # Execution engine and validation
│   ├── tools/           # Tool registry and implementations
│   ├── memory/          # Memory management
│   └── api/             # FastAPI application
├── config/              # Configuration files
├── tests/               # Test suite
├── infrastructure/      # Docker, K8s, Terraform
├── scripts/             # Deployment and maintenance
└── docs/                # Documentation
```

## Platform Vision — The Three-Way Empire

The AGI System is built on three interconnected pillars that together form a complete, enterprise-grade AI platform:

```
┌──────────────────────────────────────────────────────────────────┐
│  🧪 Agentic Studio  — AI coding assistants, IDE, CDE, vibe-coding │
├──────────────────────────────────────────────────────────────────┤
│  🏗️  AI Foundry     — rapid application development & deployment  │
├──────────────────────────────────────────────────────────────────┤
│  🏭 AI Factory     — scalable, efficient AI infrastructure        │
└──────────────────────────────────────────────────────────────────┘
          ▲
          │  underpinned by
          ▼
┌──────────────────────────────────────────────────────────────────┐
│  🔬 AI Proving Ground (AIPG)  — evaluate & validate AI tech       │
│  🔗 Digital Twin              — live, data-connected reality model │
└──────────────────────────────────────────────────────────────────┘
```

This practical approach results in **seamless integration**, **robust security**, and **measurable business outcomes** — making AI adoption a strategic and impactful journey.

| Pillar / Layer | What it does | Doc |
|---|---|---|
| **Agentic Studio** | AI coding assistants, vibecoding IDE, CDE, enterprise market landscape | [docs/agentic-studio/](docs/agentic-studio/) |
| **AI Foundry** | Application templates, ADK, tool ecosystem, LLM integration, developer portal | [docs/ai-foundry/platform-overview.md](docs/ai-foundry/platform-overview.md) |
| **AI Factory** | Kubernetes, Docker, Terraform, data/memory layer, CI/CD, observability | [docs/ai-factory/infrastructure-guide.md](docs/ai-factory/infrastructure-guide.md) |
| **AIPG** | Benchmark evaluation, multi-provider LLM assessment, Kally AI, tech governance | [docs/aipg/proving-ground.md](docs/aipg/proving-ground.md) |
| **Digital Twin** | Real-time asset mirroring, simulation sandbox, change event stream | [docs/digital-twin/overview.md](docs/digital-twin/overview.md) |

## Documentation

- [AI Foundry — Platform Overview](docs/ai-foundry/platform-overview.md)
- [AI Factory — Infrastructure Guide](docs/ai-factory/infrastructure-guide.md)
- [Agentic Studio — Market Landscape](docs/agentic-studio/market-landscape.md)
- [AI Proving Ground (AIPG)](docs/aipg/proving-ground.md)
- [Digital Twin Overview](docs/digital-twin/overview.md)
- [API Reference](docs/api/README.md)
- [User Guide](docs/user-guides/README.md)
- [Deployment Guide](docs/deployment/README.md)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License
