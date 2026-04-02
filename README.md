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

- **LangChain**: Foundation layer providing tools, memory chains, and LLM integrations.
  Each agent type has a dedicated prompt template; the `LangChainAgentChain` wraps any
  OpenAI/Anthropic-compatible LLM and gracefully falls back to a mock response when no
  credentials are configured.
- **CrewAI**: Multi-agent coordination, task delegation, and crew orchestration.
  The `CrewBuilder` converts registered `AgentConfig` objects into CrewAI `Agent` / `Task`
  objects and runs them via `Crew.kickoff()`.  Falls back to mock output when CrewAI
  dependencies or LLM credentials are absent.

## Integrations

| Module | Purpose |
|--------|---------|
| `src/integrations/langchain_integration.py` | `LangChainLLMProvider`, `AgentPromptBuilder`, `LangChainAgentChain` |
| `src/integrations/crewai_integration.py` | `CrewAIAgentBuilder`, `CrewAITaskBuilder`, `CrewBuilder` |

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

### Run a CrewAI Crew

```bash
curl -X POST http://localhost:8000/api/v1/crews/run \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "objective": "Research and summarise recent AI developments",
    "agent_names": ["research_agent", "writing_agent"],
    "tasks": [
      {"description": "Research recent AI papers and news"},
      {"description": "Write a concise summary report"}
    ]
  }'
```

### List Crew-Capable Agents

```bash
curl http://localhost:8000/api/v1/crews/agents
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

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License
