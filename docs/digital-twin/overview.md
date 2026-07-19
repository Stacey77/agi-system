# Digital Twin — Overview

> **Advanced Technology Platform**: A live, data-connected model of a physical asset, process, or environment that reflects what is happening in real time.

A Digital Twin is more than a simulation — it is a continuously synchronised mirror of a real-world system. By ingesting live telemetry, event streams, and operational data, a Digital Twin reflects current reality with enough fidelity to monitor operations, safely test changes, and drive decisions that feed back into the physical world.

Within the AGI System platform, Digital Twins serve as the **data foundation** for AI applications, evaluations, and autonomous agents — ensuring AI decisions are grounded in current, operational truth rather than stale snapshots or synthetic data.

---

## What Makes a Digital Twin "Digital"?

| Aspect | Traditional Model | Digital Twin |
|---|---|---|
| Data freshness | Historical / batch | Real-time / streaming |
| State synchronisation | Periodic | Continuous |
| Feedback loop | One-way (read) | Bidirectional (read + write-back) |
| Use for AI | Training datasets | Live inference context |
| Failure testing | Destructive | Safe shadow environment |

---

## Digital Twin Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Physical World                            │
│   Assets │ Processes │ Environments │ Systems               │
└──────────────────────┬──────────────────────────────────────┘
                       │  telemetry, events, sensor data
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Data Ingestion Layer                        │
│   Streaming APIs │ IoT connectors │ Event webhooks           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Digital Twin Core                           │
│                                                              │
│   ┌────────────────┐   ┌────────────────┐                   │
│   │  State Store   │   │  Time-Series   │                   │
│   │  (current      │   │  History       │                   │
│   │   reality)     │   │  (trends)      │                   │
│   └────────────────┘   └────────────────┘                   │
│                                                              │
│   ┌────────────────┐   ┌────────────────┐                   │
│   │  Change Event  │   │  Simulation    │                   │
│   │  Stream        │   │  Sandbox       │                   │
│   └────────────────┘   └────────────────┘                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  AI Platform Layer                           │
│   AI Foundry apps │ AIPG eval │ Agentic Studio agents        │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Concepts

### State Store
The State Store holds the **current** representation of every tracked asset or process. It answers the question: *"What is true right now?"*

- Key-value pairs with rich metadata and relationships
- Updated continuously as physical-world events arrive
- Versioned: every change appends to an immutable log
- Queryable as a graph (assets → sub-components → relationships)

### Time-Series History
Beyond current state, the Digital Twin retains the full history of how state evolved:

- Fine-grained timestamps for every state change
- Supports trend analysis, anomaly detection, and forecasting
- Queryable via time-range filters: *"Show me machine utilisation for the last 30 days"*
- Powers the Kally AI feedback loops in AIPG

### Simulation Sandbox
The sandbox allows **safe testing of changes** before applying them to the physical world:

1. Take a snapshot of current twin state
2. Apply a proposed change (config update, process modification, new AI model behaviour)
3. Run the simulation forward in time using historical patterns
4. Measure predicted outcomes (throughput, error rate, cost)
5. Discard the sandbox or promote the change to production

This is the key capability that separates a Digital Twin from a monitoring dashboard: *you can experiment with reality without breaking it.*

### Change Event Stream
Every state transition publishes an event to the change stream. Agents and applications can subscribe to these events via webhooks (`/api/v1/webhooks`) to trigger automated responses:

```json
POST /api/v1/webhooks
{
  "event": "twin.state_changed",
  "filter": "asset_id=machine-42 AND metric=temperature AND value>85",
  "callback_url": "https://my-service/alert"
}
```

---

## Integration with the AGI System Platform

### AI Foundry Applications
AI Foundry applications consume Digital Twin data as live context for LLM prompts and agent decision-making:

```python
# Research agent enriched with live twin state
task = {
    "task": "Analyse current production line efficiency",
    "parameters": {
        "twin_context": digital_twin.get_current_state("production_line_1"),
        "time_range": "last_24h"
    }
}
result = await research_agent.process_task(task)
```

### AIPG Evaluation
The [AI Proving Ground](../aipg/proving-ground.md) connects to Digital Twin mirrors for benchmark scenarios that reflect live operational conditions. Evaluations run against real data without touching production systems.

### Kally AI Feedback Loop
`KallyAgent` ingests Digital Twin telemetry as signals, detecting operational anomalies and recommending AI model or infrastructure adjustments:

```
Twin telemetry ──▶ KallyAgent signals ──▶ Anomaly detection ──▶ Recommendations
                         ▲                                              │
                         └──────────── Implemented changes ────────────┘
```

### Agentic Studio
Autonomous coding agents in Agentic Studio can use Digital Twin data to:
- Generate infrastructure-as-code that matches live resource topology
- Produce monitoring dashboards aligned to actual system metrics
- Write integration tests against twin-mirrored service states

---

## Use Cases

### Operational Monitoring
> *"Show me which machines are currently outside normal operating parameters."*

The Digital Twin provides a real-time dashboard where every sensor value, process KPI, and system metric is reflected with sub-second lag. AI agents surface anomalies proactively rather than waiting for alerts.

### Predictive Maintenance
> *"When will this asset likely fail, and what is the maintenance window impact?"*

Time-series history trains predictive models; the simulation sandbox projects forward. The result is a maintenance recommendation with a confidence interval — before any disruption occurs.

### Change Impact Assessment
> *"What happens to throughput if we adjust this process parameter by 10%?"*

The simulation sandbox applies the hypothetical change to a twin snapshot and runs the simulation. Results are available in minutes; zero risk to the physical environment.

### AI Model Grounding
> *"Ensure this LLM response reflects current operational reality, not training data."*

Rather than relying on potentially stale training data, AI applications inject live twin state as retrieval-augmented context — ensuring responses are relevant and current.

### Digital-Native Products
> *"Build a product that is inherently data-connected from day one."*

New products designed around a Digital Twin skip the retrofit problem: observability, control, and AI integration are structural, not bolted on after the fact.

---

## Data Governance

| Principle | Implementation |
|---|---|
| **Read-only production access** | Physical-world connectors write to the twin; applications only read |
| **Data provenance** | Every state record includes source, timestamp, and confidence |
| **Access control** | Twin data access gated by the same JWT/API-key auth as the rest of the platform |
| **Retention policies** | Configurable per asset; time-series history compacted at defined intervals |
| **Audit trail** | All reads and simulation runs are logged with `request_id` |

---

## Roadmap

| Capability | Status |
|---|---|
| Webhook-based change event subscriptions | ✅ Available (via `/api/v1/webhooks`) |
| Kally AI telemetry ingestion | ✅ Available |
| Time-series history query API | 🔄 Planned |
| Simulation sandbox API | 🔄 Planned |
| IoT / MQTT connector | 🔄 Planned |
| Graph-based asset relationship queries | 🔄 Planned |
| Digital Twin ↔ AIPG evaluation bridge | 🔄 Planned |

---

## Further Reading

- [AI Proving Ground (AIPG)](../aipg/proving-ground.md)
- [AI Foundry — Platform Overview](../ai-foundry/platform-overview.md)
- [AI Factory — Infrastructure Guide](../ai-factory/infrastructure-guide.md)
- [Agentic Studio — Market Landscape](../agentic-studio/market-landscape.md)
- [API Reference](../api/README.md)
