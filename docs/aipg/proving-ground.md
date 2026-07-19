# AI Proving Ground (AIPG) — Overview

> **Advanced Technology Platform**: Unrivaled access to the world's leading AI technologies in a safe, governed environment.

The AI Proving Ground (AIPG) is the experimentation and evaluation layer of the AGI System platform. It provides a structured environment where teams can assess, benchmark, and validate AI technologies — from LLM providers and agent frameworks to specialised models — before committing them to production workloads. AIPG turns AI technology selection from guesswork into an evidence-based process.

---

## Mission

> *"Try anything. Measure everything. Promote only what works."*

AI adoption fails most often not in production — but in the gap between a promising demo and a reliable, scalable deployment. AIPG closes that gap by giving teams a dedicated space to:

1. **Evaluate** competing AI technologies against real workloads
2. **Benchmark** performance, cost, and quality at scale
3. **Validate** security, compliance, and integration requirements
4. **Promote** proven technologies into AI Foundry application templates

---

## Platform Capabilities

### 1. Evaluation Engine
The built-in eval runner (`/api/v1/eval`) executes standardised benchmark suites against any registered agent or LLM provider:

```bash
# Run the standard benchmark suite against all agents
POST /api/v1/eval/run
{
  "agent_names": ["research_agent", "analysis_agent", "coding_agent"],
  "benchmark": "standard"
}

# Retrieve results
GET /api/v1/eval/results
```

Standard benchmarks include:
- Summarisation quality
- Factual accuracy (Q&A)
- Code generation correctness
- Instruction-following fidelity
- Latency and token efficiency

### 2. Multi-Provider LLM Assessment
AIPG makes it trivial to swap LLM providers behind any agent and compare results:

```python
from src.llm.provider import create_llm

# Test the same task across providers
providers = ["openai/gpt-4o", "anthropic/claude-3-5-sonnet", "mock"]
for p in providers:
    vendor, model = p.split("/")
    llm = create_llm(provider=vendor, model=model)
    result = await agent_with_llm(llm).process_task(benchmark_task)
    record_result(p, result)
```

The `mock` provider enables baseline comparison without LLM cost, establishing a deterministic floor for evaluation.

### 3. Kally AI — Closed-Loop Feedback System
`KallyAgent` is AIPG's continuous improvement engine. It ingests operational signals from any part of the platform and generates prioritised improvement recommendations:

```
Signal Ingest  ──▶  Anomaly Detection  ──▶  Root Cause Analysis  ──▶  Recommendations
     │                                                                        │
     └──────────────────── Actions Taken Log ◀──────────────────────────────┘
```

**API surface:**
```
POST /api/v1/platform/kally/signals    # ingest a signal
POST /api/v1/platform/kally/analyse    # trigger analysis cycle
GET  /api/v1/platform/kally/report     # get health report + recommendations
POST /api/v1/platform/kally/reset      # clear signal buffer
```

**Example: ingesting a latency signal:**
```json
POST /api/v1/platform/kally/signals
{
  "source": "research_agent",
  "metric": "p95_latency_ms",
  "value": 4800,
  "threshold": 3000,
  "severity": "warning"
}
```

Kally's `ClosedLoopReport` includes:
- `signals_analysed`: total signals ingested
- `anomalies_detected`: count of threshold breaches
- `recommendations`: prioritised action list
- `health_score`: 0.0–1.0 composite score
- `actions_taken`: auto-remediation log

### 4. Technology Landscape Registry
AIPG maintains a live inventory of all AI/ML tools in the platform via `ToolLandscape`:

```
GET  /api/v1/platform/tools              # browse all tools
GET  /api/v1/platform/tools?category=ai_ml
POST /api/v1/platform/tools              # register new tool
```

Example catalogue entries (from `src/platform/tool_landscape.py`):

| Tool | Category | Tier |
|---|---|---|
| ChromaDB | AI/ML | Both |
| Kally AI | AI/ML | Internal |
| Terraform | Infrastructure | Internal |
| LangChain | AI/ML | Both |
| CrewAI | AI/ML | Both |

New tools entering AIPG are registered here first, proven through evaluation, then promoted to AI Foundry templates.

### 5. Digital Twin Integration
AIPG connects to the [Digital Twin](../digital-twin/overview.md) layer to enable AI model evaluation against **live data mirrors** of real production systems. This means benchmark scenarios reflect actual operational conditions, not synthetic datasets.

---

## Evaluation Workflow

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌───────────────┐
│   Define    │────▶│   Execute    │────▶│   Analyse    │────▶│    Promote    │
│  Benchmark  │     │   Against    │     │   Results    │     │   to Foundry  │
│  Criteria   │     │  Candidates  │     │  (Kally AI)  │     │   Templates   │
└─────────────┘     └──────────────┘     └──────────────┘     └───────────────┘
       ▲                                         │
       └─────────── Iterate & Refine ────────────┘
```

**Step-by-step:**
1. **Define**: Specify evaluation criteria (accuracy, latency, cost/token, safety)
2. **Execute**: Run `POST /api/v1/eval/run` with the candidate agent or provider
3. **Analyse**: Use Kally signals and eval results to identify winners and gaps
4. **Iterate**: Tune prompts, temperature, tools, or switch providers; re-run
5. **Promote**: Winning configuration is codified as an AI Foundry template

---

## Security and Governance in AIPG

Running experiments should never compromise production systems. AIPG enforces:

| Control | Detail |
|---|---|
| **Namespace isolation** | AIPG workloads run in a dedicated Kubernetes namespace |
| **Read-only production data** | Digital Twin mirrors provide read-only snapshots — no write-back |
| **Rate-limited LLM access** | `RateLimitMiddleware` prevents runaway experiment costs |
| **Audit logging** | Every eval run, Kally signal, and tool registration is logged with `request_id` |
| **Admin-gated promotion** | Moving a technology from AIPG to Foundry requires admin approval |

---

## Access Patterns

| Role | Permitted Actions |
|---|---|
| **Developer** | Submit eval runs, browse tool landscape, view Kally reports |
| **Platform Engineer** | Register tools, configure benchmarks, manage namespaces |
| **Admin** | Promote technologies, manage API keys, reset Kally state |

Authentication via JWT or `X-API-Key` header — same mechanism as the rest of the platform.

---

## Roadmap

| Capability | Status |
|---|---|
| Standard benchmark suites | ✅ Available |
| Multi-provider LLM eval | ✅ Available |
| Kally closed-loop feedback | ✅ Available |
| Tool landscape registry | ✅ Available |
| Automated cost-per-eval tracking | 🔄 Planned |
| A/B traffic splitting (shadow mode) | 🔄 Planned |
| Digital Twin–backed benchmarks | 🔄 Planned |
| Automated promotion gates (CI/CD) | 🔄 Planned |

---

## Further Reading

- [Digital Twin Overview](../digital-twin/overview.md)
- [AI Foundry — Platform Overview](../ai-foundry/platform-overview.md)
- [AI Factory — Infrastructure Guide](../ai-factory/infrastructure-guide.md)
- [Agentic Studio — Market Landscape](../agentic-studio/market-landscape.md)
- [API Reference — Eval](../api/README.md)
