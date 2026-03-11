# User Guide

## Getting Started

### 1. Installation

```bash
git clone https://github.com/Stacey77/agi-system.git
cd agi-system
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your OpenAI/Anthropic API keys
```

### 2. Start the Server

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

### 3. Verify

```bash
curl http://localhost:8000/health
# {"status": "healthy"}
```

---

## Using the Writing Assistant

```bash
curl -X POST http://localhost:8000/api/v1/agents/writing_agent/execute \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "task": "Write an article on climate change",
    "parameters": {"requirements": {"tone": "academic", "format": "article"}}
  }'
```

## Using the Research Tool

```bash
curl -X POST http://localhost:8000/api/v1/agents/research_agent/execute \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"task": "Find recent developments in quantum computing"}'
```

## Submitting a Complex Task

For multi-step research + writing tasks, use the tasks endpoint:

```bash
curl -X POST http://localhost:8000/api/v1/tasks/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"objective": "Research AI trends and write a comprehensive summary"}'
```

Poll for completion:

```bash
curl http://localhost:8000/api/v1/tasks/{task_id}
```

## Agent Types

| Agent | Best For |
|-------|---------|
| `planning_agent` | Breaking down complex objectives |
| `research_agent` | Information gathering |
| `analysis_agent` | Data analysis and statistics |
| `writing_agent` | Content creation |
| `review_agent` | Quality checking outputs |
